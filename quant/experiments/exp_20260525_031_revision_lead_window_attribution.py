"""exp-20260525-031: EPS revision lead-window attribution.

Observed-only alpha search. This experiment asks whether a positive PIT
same-event EPS estimate revision can lead Ginger candidate objects by 0-3
trading days, rather than needing to occur on the exact candidate date.

It does not alter signal generation, ranking, sizing, exits, LLM/news, or
orders.
"""

from __future__ import annotations

import json
import math
import sys
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-031"
STEM = "revision_lead_window_attribution"
MECHANISM_FAMILY = "earnings_estimate_revision"
TRIAL_FAMILY = "eps_revision_lead_window_attribution"
CHANGED_VARIABLE = "positive_eps_revision_lead_window_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
    _coerce_date,
    _date_from_quant_signal_path,
    _float,
    _read_json,
    _read_jsonl,
    build_price_lookup,
    extract_candidate_rows,
    load_candidates,
    load_ledger_map,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BUCKET_A = "A_positive_eps_revision_lead_0_3td"
BUCKET_D = "D_no_positive_eps_revision_lead_0_3td"
BUCKETS = (BUCKET_A, BUCKET_D)
MAX_LEAD_TRADING_DAYS = 3
MIN_BUCKET_A_5D_OUTCOMES = 4
MIN_TOTAL_CLOSED_5D_OUTCOMES = 20
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def trading_dates_from_prices(prices: Any) -> list[date]:
    spy_dates = set(prices.by_ticker.get("SPY", {}).keys())
    if spy_dates:
        return sorted(spy_dates)
    all_dates: set[date] = set()
    for rows in prices.by_ticker.values():
        all_dates.update(rows.keys())
    return sorted(all_dates)


def trading_dates_from_ohlcv(data_dir: Path, prices: Any | None = None) -> list[date]:
    spy_dates: set[date] = set()
    all_dates: set[date] = set()
    for path in sorted((data_dir / "ohlcv").glob("ohlcv_snapshot_*.json")):
        payload = _read_json(path)
        ohlcv = payload.get("ohlcv") if isinstance(payload.get("ohlcv"), dict) else payload
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                raw_day = row.get("Date") or row.get("date")
                if not raw_day:
                    continue
                day = _coerce_date(raw_day)
                all_dates.add(day)
                if str(ticker).upper() == "SPY":
                    spy_dates.add(day)
    if prices is not None:
        for ticker, rows in prices.by_ticker.items():
            for day in rows:
                if day.weekday() >= 5:
                    continue
                all_dates.add(day)
                if str(ticker).upper() == "SPY":
                    spy_dates.add(day)
    if spy_dates:
        return sorted(spy_dates)
    if all_dates:
        return sorted(all_dates)
    return trading_dates_from_prices(prices) if prices is not None else []


def next_trading_date_on_or_after(day: str | date | datetime, trading_dates: list[date]) -> date | None:
    if not trading_dates:
        return None
    target = _coerce_date(day)
    idx = bisect_left(trading_dates, target)
    if idx >= len(trading_dates):
        return None
    return trading_dates[idx]


def trading_day_distance(start: date, end: date, trading_dates: list[date]) -> int | None:
    index = {day: idx for idx, day in enumerate(trading_dates)}
    if start not in index or end not in index:
        return None
    return index[end] - index[start]


def classify_revision_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "positive_revision": False,
            "revision_status": "missing_ledger_row",
            "eps_estimate_delta_prev": None,
        }
    delta_prev = _float(row.get("eps_estimate_delta_prev"), None)
    if not row.get("estimate_revision_usable"):
        return {
            "positive_revision": False,
            "revision_status": "ledger_row_not_usable",
            "eps_estimate_delta_prev": delta_prev,
        }
    if delta_prev is None:
        return {
            "positive_revision": False,
            "revision_status": "usable_ledger_missing_delta_prev",
            "eps_estimate_delta_prev": None,
        }
    return {
        "positive_revision": delta_prev > 0,
        "revision_status": "positive_delta_prev" if delta_prev > 0 else "non_positive_delta_prev",
        "eps_estimate_delta_prev": delta_prev,
    }


def build_positive_revision_index(
    ledger_map: dict[tuple[str, str], dict[str, Any]],
    trading_dates: list[date],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    status_counts: Counter[str] = Counter()
    positive_rows = 0
    effective_gap_rows = 0
    for (as_of, ticker), row in ledger_map.items():
        classified = classify_revision_row(row)
        status_counts[classified["revision_status"]] += 1
        if not classified["positive_revision"]:
            continue
        positive_rows += 1
        effective_date = next_trading_date_on_or_after(as_of, trading_dates)
        if effective_date is None:
            effective_gap_rows += 1
            continue
        enriched = {
            "ticker": ticker,
            "revision_as_of_date": str(as_of),
            "revision_effective_trade_date": effective_date.isoformat(),
            "eps_estimate": row.get("eps_estimate"),
            "eps_estimate_delta_prev": classified["eps_estimate_delta_prev"],
            "revision_direction_prev": row.get("revision_direction_prev"),
            "next_earnings_date": row.get("next_earnings_date"),
            "same_event_history_count": row.get("same_event_history_count"),
            "source_snapshot_path": row.get("source_snapshot_path"),
            "source_snapshot_pit_safe": row.get("source_snapshot_pit_safe"),
            "pit_caveat": row.get("pit_caveat"),
        }
        by_ticker[ticker].append(enriched)
    for rows in by_ticker.values():
        rows.sort(key=lambda item: (item["revision_effective_trade_date"], item["revision_as_of_date"]))
    return by_ticker, {
        "ledger_rows_total": len(ledger_map),
        "revision_status_counts": dict(status_counts),
        "positive_revision_rows": positive_rows,
        "positive_revision_rows_with_effective_trade_date": sum(len(rows) for rows in by_ticker.values()),
        "positive_revision_rows_missing_effective_trade_date": effective_gap_rows,
        "positive_revision_unique_tickers": sorted(by_ticker),
    }


def find_revision_lead_match(
    *,
    ticker: str,
    candidate_as_of: str | date | datetime,
    positive_revision_index: dict[str, list[dict[str, Any]]],
    trading_dates: list[date],
    max_lead_trading_days: int = MAX_LEAD_TRADING_DAYS,
) -> dict[str, Any]:
    ticker = str(ticker).upper()
    candidate_date = _coerce_date(candidate_as_of)
    candidate_effective = next_trading_date_on_or_after(candidate_date, trading_dates)
    if candidate_effective is None:
        return {
            "matched": False,
            "revision_lead_status": "candidate_missing_effective_trade_date",
            "candidate_effective_trade_date": None,
        }

    matches = []
    for row in positive_revision_index.get(ticker, []):
        revision_effective = _coerce_date(row["revision_effective_trade_date"])
        distance = trading_day_distance(revision_effective, candidate_effective, trading_dates)
        if distance is None:
            continue
        calendar_days = (candidate_date - _coerce_date(row["revision_as_of_date"])).days
        if 0 <= distance <= max_lead_trading_days and calendar_days >= 0:
            matches.append((distance, _coerce_date(row["revision_as_of_date"]), calendar_days, row))
    if not matches:
        return {
            "matched": False,
            "revision_lead_status": "no_positive_revision_in_lead_window",
            "candidate_effective_trade_date": candidate_effective.isoformat(),
        }

    distance, _revision_day, calendar_days, row = sorted(
        matches,
        key=lambda item: (item[0], -item[1].toordinal()),
    )[0]
    return {
        "matched": True,
        "revision_lead_status": "matched_positive_revision_lead",
        "candidate_effective_trade_date": candidate_effective.isoformat(),
        "revision_lead_trading_days": distance,
        "revision_lead_calendar_days": calendar_days,
        **row,
    }


def _feature_close(features_by_date: dict[str, dict[str, dict[str, Any]]], as_of: str, ticker: str) -> float | None:
    return _float((features_by_date.get(as_of, {}).get(ticker) or {}).get("close"), None)


def annotate_candidates(
    *,
    candidates: list[dict[str, Any]],
    features_by_date: dict[str, dict[str, dict[str, Any]]],
    ledger_map: dict[tuple[str, str], dict[str, Any]],
    positive_revision_index: dict[str, list[dict[str, Any]]],
    prices: Any,
    trading_dates: list[date],
) -> list[dict[str, Any]]:
    annotated = []
    for candidate in candidates:
        as_of = str(candidate.get("as_of_date"))
        ticker = str(candidate.get("ticker") or "").upper()
        match = find_revision_lead_match(
            ticker=ticker,
            candidate_as_of=as_of,
            positive_revision_index=positive_revision_index,
            trading_dates=trading_dates,
        )
        same_day_ledger = ledger_map.get((as_of, ticker))
        same_day_revision = classify_revision_row(same_day_ledger)
        base_price = _float(candidate.get("raw_price"), None)
        if base_price is None:
            base_price = _feature_close(features_by_date, as_of, ticker)
        forward = {
            f"{horizon}d": prices.forward_return(ticker, as_of, horizon, base_price=base_price)
            for horizon in FORWARD_HORIZONS
        }
        bucket = BUCKET_A if match["matched"] else BUCKET_D
        annotated.append(
            {
                **candidate,
                "bucket": bucket,
                "revision_lead_positive": match["matched"],
                **match,
                "same_day_revision_status": same_day_revision["revision_status"],
                "same_day_eps_estimate_delta_prev": same_day_revision["eps_estimate_delta_prev"],
                "same_day_positive_revision": same_day_revision["positive_revision"],
                "forward_outcomes": forward,
            }
        )
    return annotated


def _compact_row(row: dict[str, Any], horizon_key: str | None = None) -> dict[str, Any]:
    out = {
        "as_of_date": row.get("as_of_date"),
        "ticker": row.get("ticker"),
        "candidate_source": row.get("candidate_source"),
        "record_type": row.get("record_type"),
        "strategy": row.get("strategy"),
        "bucket": row.get("bucket"),
        "revision_lead_positive": row.get("revision_lead_positive"),
        "revision_lead_status": row.get("revision_lead_status"),
        "revision_as_of_date": row.get("revision_as_of_date"),
        "revision_effective_trade_date": row.get("revision_effective_trade_date"),
        "candidate_effective_trade_date": row.get("candidate_effective_trade_date"),
        "revision_lead_trading_days": row.get("revision_lead_trading_days"),
        "revision_lead_calendar_days": row.get("revision_lead_calendar_days"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "same_day_eps_estimate_delta_prev": row.get("same_day_eps_estimate_delta_prev"),
        "next_earnings_date": row.get("next_earnings_date"),
    }
    if horizon_key:
        outcome = row.get("forward_outcomes", {}).get(horizon_key, {})
        out.update(
            {
                "forward_return": outcome.get("return"),
                "pnl_proxy": outcome.get("pnl_proxy"),
                "future_date": outcome.get("future_date"),
            }
        )
    else:
        out["forward_outcomes"] = row.get("forward_outcomes")
    return out


def summarize_rows(rows: list[dict[str, Any]], horizon_key: str) -> dict[str, Any]:
    closed = [
        row
        for row in rows
        if (row.get("forward_outcomes", {}).get(horizon_key) or {}).get("closed")
    ]
    returns = [
        row["forward_outcomes"][horizon_key]["return"]
        for row in closed
        if row["forward_outcomes"][horizon_key].get("return") is not None
    ]
    pnl_rows = [
        (row, row["forward_outcomes"][horizon_key].get("pnl_proxy") or 0.0)
        for row in closed
    ]
    positive = [(row, pnl) for row, pnl in pnl_rows if pnl > 0]
    positive_total = sum(pnl for _row, pnl in positive)
    top5_positive = sum(pnl for _row, pnl in sorted(positive, key=lambda item: item[1], reverse=True)[:5])
    by_ticker_positive: Counter[str] = Counter()
    for row, pnl in positive:
        by_ticker_positive[str(row.get("ticker"))] += pnl
    worst = min(
        closed,
        key=lambda row: row["forward_outcomes"][horizon_key].get("return", 0.0),
        default=None,
    )
    return {
        "closed_outcomes": len(closed),
        "avg_return": round(sum(returns) / len(returns), 6) if returns else None,
        "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6) if returns else None,
        "tail_loss": round(min(returns), 6) if returns else None,
        "worst_row": _compact_row(worst, horizon_key) if worst else None,
        "top5_positive_contribution_share": (
            round(top5_positive / positive_total, 6) if positive_total > 0 else None
        ),
        "max_single_ticker_positive_share": (
            round(max(by_ticker_positive.values()) / positive_total, 6)
            if positive_total > 0 and by_ticker_positive
            else None
        ),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(by_ticker_positive.items())
        },
    }


def build_bucket_summary(annotated: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in annotated:
        by_bucket[row["bucket"]].append(row)
    summary = {}
    for bucket in BUCKETS:
        rows = by_bucket.get(bucket, [])
        summary[bucket] = {
            "candidate_count": len(rows),
            "candidate_source_breakdown": dict(Counter(row["candidate_source"] for row in rows)),
            "record_type_breakdown": dict(Counter(row["record_type"] for row in rows)),
            "ticker_count": len({row["ticker"] for row in rows}),
            "tickers": sorted({row["ticker"] for row in rows}),
            "horizons": {
                f"{horizon}d": summarize_rows(rows, f"{horizon}d")
                for horizon in FORWARD_HORIZONS
            },
        }
    return summary


def build_coverage(annotated: list[dict[str, Any]], revision_index_summary: dict[str, Any]) -> dict[str, Any]:
    closed_by_horizon = {
        f"{horizon}d": sum(
            1
            for row in annotated
            if (row.get("forward_outcomes", {}).get(f"{horizon}d") or {}).get("closed")
        )
        for horizon in FORWARD_HORIZONS
    }
    return {
        "candidate_objects_total": len(annotated),
        "positive_revision_lead_candidates": sum(1 for row in annotated if row.get("revision_lead_positive")),
        "positive_revision_lead_unique_tickers": sorted(
            {row["ticker"] for row in annotated if row.get("revision_lead_positive")}
        ),
        "candidate_source_breakdown": dict(Counter(row["candidate_source"] for row in annotated)),
        "record_type_breakdown": dict(Counter(row["record_type"] for row in annotated)),
        "revision_lead_status_counts": dict(Counter(row["revision_lead_status"] for row in annotated)),
        "same_day_revision_status_counts": dict(Counter(row["same_day_revision_status"] for row in annotated)),
        "closed_forward_outcomes": closed_by_horizon,
        "revision_index": revision_index_summary,
    }


def evaluate_gate(bucket_summary: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    bucket_a_5d = bucket_summary[BUCKET_A]["horizons"]["5d"]
    total_5d = coverage["closed_forward_outcomes"]["5d"]
    data_gap_reasons = []
    if bucket_a_5d["closed_outcomes"] < MIN_BUCKET_A_5D_OUTCOMES:
        data_gap_reasons.append("bucket_a_closed_5d_outcomes")
    if total_5d < MIN_TOTAL_CLOSED_5D_OUTCOMES:
        data_gap_reasons.append("total_closed_5d_outcomes")
    if data_gap_reasons:
        return {
            "passed": False,
            "decision": "observed_only_data_gap",
            "reason": "insufficient_positive_revision_lead_sample",
            "data_gap_reasons": data_gap_reasons,
            "bucket_a_closed_5d_outcomes": bucket_a_5d["closed_outcomes"],
            "minimum_bucket_a_closed_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
            "total_closed_5d_outcomes": total_5d,
            "minimum_total_closed_5d_outcomes": MIN_TOTAL_CLOSED_5D_OUTCOMES,
        }

    comparisons = []
    a_beats = True
    for horizon in ("5d", "10d"):
        a_avg = bucket_summary[BUCKET_A]["horizons"][horizon]["avg_return"]
        d_avg = bucket_summary[BUCKET_D]["horizons"][horizon]["avg_return"]
        passed = a_avg is not None and d_avg is not None and a_avg > d_avg
        comparisons.append(
            {
                "horizon": horizon,
                "bucket_a_avg_return": a_avg,
                "bucket_d_avg_return": d_avg,
                "passed": passed,
            }
        )
        a_beats = a_beats and passed

    concentration = {
        "top5_positive_contribution_share": bucket_a_5d["top5_positive_contribution_share"],
        "max_single_ticker_positive_share": bucket_a_5d["max_single_ticker_positive_share"],
        "top5_positive_contribution_guardrail": MAX_TOP5_POSITIVE_SHARE,
        "max_single_ticker_positive_guardrail": MAX_SINGLE_TICKER_POSITIVE_SHARE,
    }
    concentration["passed"] = (
        concentration["top5_positive_contribution_share"] is not None
        and concentration["max_single_ticker_positive_share"] is not None
        and concentration["top5_positive_contribution_share"] <= MAX_TOP5_POSITIVE_SHARE
        and concentration["max_single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    passed = bool(a_beats and concentration["passed"])
    return {
        "passed": passed,
        "decision": (
            "observed_only_promising_revision_lead_window"
            if passed
            else "rejected_revision_lead_window_attribution"
        ),
        "reason": "bucket_a_outperformance_and_concentration"
        if passed
        else "bucket_a_failed_outperformance_or_concentration",
        "comparisons": comparisons,
        "concentration": concentration,
        "bucket_a_closed_5d_outcomes": bucket_a_5d["closed_outcomes"],
        "total_closed_5d_outcomes": total_5d,
    }


def load_current_positions() -> list[dict[str, Any]]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return []
    payload = _read_json(path)
    rows = []
    for source_key in ("observations", "positions"):
        for row in payload.get(source_key) or []:
            if isinstance(row, dict) and row.get("ticker"):
                enriched = dict(row)
                enriched["position_source"] = source_key
                rows.append(enriched)
    return rows


def build_current_position_overlap(
    positions: list[dict[str, Any]],
    positive_revision_index: dict[str, list[dict[str, Any]]],
    trading_dates: list[date],
) -> dict[str, Any]:
    positive_revision_tickers = set(positive_revision_index)
    ticker_overlap = sorted({str(row.get("ticker", "")).upper() for row in positions} & positive_revision_tickers)
    entry_matches = []
    for row in positions:
        ticker = str(row.get("ticker") or "").upper()
        entry_date = row.get("entry_date")
        if not ticker or not entry_date:
            continue
        match = find_revision_lead_match(
            ticker=ticker,
            candidate_as_of=entry_date,
            positive_revision_index=positive_revision_index,
            trading_dates=trading_dates,
        )
        if match["matched"]:
            entry_matches.append(
                {
                    "ticker": ticker,
                    "entry_date": entry_date,
                    "shares": row.get("shares"),
                    "avg_cost": row.get("avg_cost"),
                    "opened_by_strategy": row.get("opened_by_strategy"),
                    "position_source": row.get("position_source"),
                    **match,
                }
            )
    return {
        "current_position_count": len(positions),
        "ticker_overlap_with_any_positive_revision": ticker_overlap,
        "ticker_overlap_count": len(ticker_overlap),
        "entry_lead_match_count": len(entry_matches),
        "entry_lead_matches": entry_matches,
    }


def _open_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": _repo_rel(path),
            "exists": False,
            "missing_required_fields": ["entry_date", "target_price"],
            "passed": False,
        }
    payload = _read_json(path)
    positions = (payload.get("observations") or []) + (payload.get("positions") or [])
    missing = []
    for idx, row in enumerate(positions):
        if not isinstance(row, dict):
            continue
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"index": idx, "ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(path),
        "exists": True,
        "checked_positions": len(positions),
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _compact_annotated_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_compact_row(row) for row in rows]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Revision Lead Window Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(payload["coverage"], indent=2, sort_keys=True),
        "```",
        "",
        "## Current Positions",
        "",
        "```json",
        json.dumps(payload["current_position_overlap"], indent=2, sort_keys=True),
        "```",
        "",
        "## Bucket Summary",
        "",
        "| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_summary"].items():
        h5 = row["horizons"]["5d"]
        h10 = row["horizons"]["10d"]
        h20 = row["horizons"]["20d"]
        lines.append(
            "| {bucket} | {candidates} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} | {h20_count} | {h20_avg} |".format(
                bucket=bucket,
                candidates=row["candidate_count"],
                h5_count=h5["closed_outcomes"],
                h5_avg="" if h5["avg_return"] is None else f"{h5['avg_return']:.4%}",
                h10_count=h10["closed_outcomes"],
                h10_avg="" if h10["avg_return"] is None else f"{h10['avg_return']:.4%}",
                h20_count=h20["closed_outcomes"],
                h20_avg="" if h20["avg_return"] is None else f"{h20['avg_return']:.4%}",
            )
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    candidates, features_by_date = load_candidates(data_dir)
    ledger_map = load_ledger_map(data_dir)
    prices = build_price_lookup(data_dir)
    trading_dates = trading_dates_from_ohlcv(data_dir, prices)
    positive_revision_index, revision_index_summary = build_positive_revision_index(
        ledger_map,
        trading_dates,
    )
    annotated = annotate_candidates(
        candidates=candidates,
        features_by_date=features_by_date,
        ledger_map=ledger_map,
        positive_revision_index=positive_revision_index,
        prices=prices,
        trading_dates=trading_dates,
    )
    bucket_summary = build_bucket_summary(annotated)
    coverage = build_coverage(annotated, revision_index_summary)
    gate = evaluate_gate(bucket_summary, coverage)
    current_position_overlap = build_current_position_overlap(
        load_current_positions(),
        positive_revision_index,
        trading_dates,
    )
    field_check = _open_position_field_check()
    decision = gate["decision"]
    status = "observed_only_data_gap" if decision == "observed_only_data_gap" else (
        "observed_only" if gate["passed"] else "rejected"
    )
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "PIT-safe positive same-event EPS estimate revisions may lead "
            "Ginger candidate objects by 0-3 trading days and improve forward "
            "5/10/20 trading-day outcomes versus candidates without a recent "
            "positive revision lead."
        ),
        "change_summary": (
            "Read-only candidate attribution for positive EPS estimate "
            "revision leads over a 0-3 trading-day window."
        ),
        "change_type": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "lead_window_0_3td_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260507-090",
            "exp-20260507-900",
            "exp-20260513-103",
            "exp-20260513-104",
            "exp-20260525-017",
            "exp-20260525-023",
            "exp-20260525-025",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "pit_positive_eps_revision_lead_window_attribution",
        "component": "quant/experiments/exp_20260525_031_revision_lead_window_attribution.py",
        "parameters": {
            "positive_revision_definition": "estimate_revision_usable && eps_estimate_delta_prev > 0",
            "lead_window_trading_days": [0, MAX_LEAD_TRADING_DAYS],
            "revision_effective_trade_date": "first OHLCV trading date on or after revision as_of_date",
            "candidate_sources": "daily persisted candidate objects from quant_signals_YYYYMMDD.json",
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "forward_horizons": list(FORWARD_HORIZONS),
            "gate_thresholds": {
                "min_bucket_a_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
                "min_total_closed_5d_outcomes": MIN_TOTAL_CLOSED_5D_OUTCOMES,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "candidate_artifacts": "data/daily/signals/quant/quant_signals_*.json",
            "estimate_revision_ledgers": "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
            "ohlcv_sources": [
                "data/ohlcv/ohlcv_snapshot_*.json",
                "data/daily/signals/trend/trend_signals_*.json",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/ranking research: a positive PIT EPS estimate revision "
                "may be absorbed by the candidate engine with a short delay, "
                "as in COHR's 2026-05-09 revision and 2026-05-11 pilot entry."
            ),
            "2_history_check": (
                "exp-20260513-104 found eight positive PIT same-event revision "
                "rows with positive short forward returns but no same-day "
                "candidate overlap. exp-20260525-017 used a stricter same-day "
                "7d delta bucket and still had no positive candidates."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only gate: Bucket A has enough closed 5d outcomes, "
                "total closed 5d outcomes are sufficient, Bucket A beats no-lead "
                "candidates on 5d and 10d average return, and concentration is "
                "inside top-5 and single-ticker guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_031_revision_lead_window_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/",
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "This experiment is read-only attribution; no before/after core metrics are changed.",
        },
        "gate2": {
            "passed": bool(field_check.get("passed", False)),
            "field_check": field_check,
            "rule_dependencies": [
                "daily persisted candidate objects",
                "PIT estimate_revision_ledger rows",
                "OHLCV trading calendar for lead-window distance",
                "local OHLCV/trend close rows for forward returns",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": False,
            "note": "Passing this observed-only gate can only unlock a later PEAD paper sleeve or ranking-component experiment.",
        },
        "coverage": coverage,
        "bucket_summary": bucket_summary,
        "current_position_overlap": current_position_overlap,
        "gate": gate,
        "annotated_candidates": _compact_annotated_rows(annotated),
        "sample_positive_revision_lead_candidates": [
            _compact_row(row)
            for row in annotated
            if row.get("revision_lead_positive")
        ][:20],
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "candidate_objects_total": coverage["candidate_objects_total"],
            "bucket_a_closed_5d_outcomes": gate.get("bucket_a_closed_5d_outcomes"),
            "total_closed_5d_outcomes": gate.get("total_closed_5d_outcomes"),
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "interpretation": (
            "This is attribution coverage only. It tests whether positive "
            "same-event EPS revisions show up as short leads before existing "
            "candidate objects; it does not promote live logic."
        ),
        "rejection_reason": None
        if gate["passed"]
        else (
            "insufficient positive revision lead sample"
            if decision == "observed_only_data_gap"
            else "positive revision lead bucket failed outperformance or concentration gate"
        ),
        "next_evidence_needed": (
            "If Bucket A remains sparse, continue PIT estimate-revision and "
            "candidate accumulation or add a default-off paper sleeve that "
            "tracks positive revision rows independently of same-day core candidates."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep = {
        key: payload[key]
        for key in (
            "experiment_id",
            "timestamp",
            "status",
            "hypothesis",
            "change_summary",
            "change_type",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "changed_variable",
            "prior_trial_count",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "component",
            "parameters",
            "date_range",
            "gate_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "coverage",
            "bucket_summary",
            "current_position_overlap",
            "gate",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "expected_value_score_delta",
            "llm_metrics",
            "production_impact",
            "decision",
            "rejection_reason",
            "next_evidence_needed",
            "related_files",
            "anti_js",
        )
    }
    return keep


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "codex",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": CHANGED_VARIABLE,
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "coverage": payload["coverage"],
                "current_position_overlap": payload["current_position_overlap"],
                "gate": payload["gate"],
                "output": _repo_rel(OUT_JSON),
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
