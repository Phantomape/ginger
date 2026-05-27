"""exp-20260525-034: expectation revision universe watchlist attribution.

Observed-only alpha search. This experiment expands the first expectation
drift x residual leadership readout from candidate-only attribution to the
full PIT-usable estimate-revision ledger universe.

It does not alter signal generation, ranking, sizing, exits, LLM/news, paper
sleeves, or orders.
"""

from __future__ import annotations

import json
import math
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-034"
STEM = "expectation_revision_watchlist_attribution"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "expectation_revision_universe_watchlist_attribution"
CHANGED_VARIABLE = "pit_revision_universe_watchlist_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260525_017_expectation_residual_leadership_attribution import (  # noqa: E402
    FORWARD_HORIZONS,
    PAPER_NOTIONAL_USD,
    RESIDUAL_LEADER_STATES,
    _coerce_date,
    _float,
    _read_json,
    _read_jsonl,
    build_price_lookup,
    classify_bucket,
    load_candidates,
    load_ledger_map,
    residual_context_for_candidate,
)
from exp_20260525_031_revision_lead_window_attribution import (  # noqa: E402
    next_trading_date_on_or_after,
    trading_dates_from_ohlcv,
    trading_day_distance,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BUCKETS = (
    "A_positive_expectation_and_residual_leader",
    "B_positive_expectation_only",
    "C_residual_leader_only",
    "D_neither",
)
PRIMARY_BUCKET_KEY = "primary_bucket"
WIDE_BUCKET_KEY = "wide_watchlist_bucket"
MIN_BUCKET_A_5D_OUTCOMES = 8
MIN_PRIMARY_POSITIVE_ROWS = 30
MIN_TOTAL_CLOSED_5D_OUTCOMES = 30
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
CANDIDATE_HIT_WINDOWS = (3, 10)
CURRENT_POSITION_MATCH_WINDOW = 10


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


def next_weekday_on_or_after(value: str | date | datetime) -> date:
    day = _coerce_date(value)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def effective_trade_date_on_or_after(
    value: str | date | datetime,
    trading_dates: list[date],
) -> tuple[date | None, str]:
    known = next_trading_date_on_or_after(value, trading_dates)
    if known is not None:
        return known, "known_ohlcv_calendar"
    if not trading_dates or _coerce_date(value) > trading_dates[-1]:
        return None, "pending_future_trading_calendar"
    return None, "missing_trading_calendar_gap"


def classify_revision_signal(row: dict[str, Any]) -> dict[str, Any]:
    delta_7d = _float(row.get("eps_estimate_delta_7d"), None)
    delta_30d = _float(row.get("eps_estimate_delta_30d"), None)
    delta_prev = _float(row.get("eps_estimate_delta_prev"), None)
    usable = bool(row.get("estimate_revision_usable"))
    primary_positive = usable and delta_7d is not None and delta_7d > 0
    support_30d_positive = usable and delta_30d is not None and delta_30d > 0
    scout_prev_positive = usable and delta_prev is not None and delta_prev > 0
    bases = []
    if primary_positive:
        bases.append("primary_7d")
    if support_30d_positive:
        bases.append("support_30d")
    if scout_prev_positive:
        bases.append("scout_prev")
    if not usable:
        status = "ledger_row_not_usable"
    elif delta_7d is None:
        status = "pit_usable_missing_7d_delta"
    elif delta_7d > 0:
        status = "positive_eps_estimate_delta_7d"
    else:
        status = "non_positive_eps_estimate_delta_7d"
    return {
        "primary_expectation_positive": primary_positive,
        "support_30d_positive": support_30d_positive,
        "scout_prev_positive": scout_prev_positive,
        "wide_watchlist_positive": bool(bases),
        "watchlist_signal_basis": bases or ["none"],
        "expectation_status": status,
        "eps_estimate_delta_7d": delta_7d,
        "eps_estimate_delta_30d": delta_30d,
        "eps_estimate_delta_prev": delta_prev,
    }


def _feature_index(features_by_date: dict[str, dict[str, dict[str, Any]]]) -> list[date]:
    return sorted(_coerce_date(day) for day in features_by_date)


def latest_feature_date_on_or_before(
    target: str | date | datetime,
    feature_dates: list[date],
) -> date | None:
    if not feature_dates:
        return None
    idx = bisect_right(feature_dates, _coerce_date(target)) - 1
    if idx < 0:
        return None
    return feature_dates[idx]


def residual_context_for_watchlist_row(
    row: dict[str, Any],
    features_by_date: dict[str, dict[str, dict[str, Any]]],
    feature_dates: list[date],
) -> dict[str, Any]:
    feature_day = latest_feature_date_on_or_before(row["as_of_date"], feature_dates)
    if feature_day is None:
        return {
            "feature_context_date": None,
            "residual_context_status": "missing_feature_date",
            "residual_state": None,
            "residual_strength_score": None,
            "residual_leader": False,
        }
    features = features_by_date.get(feature_day.isoformat(), {})
    context = residual_context_for_candidate({"ticker": row["ticker"]}, features)
    context["feature_context_date"] = feature_day.isoformat()
    return context


def build_candidate_index(
    candidates: list[dict[str, Any]],
    trading_dates: list[date],
) -> dict[str, list[dict[str, Any]]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        ticker = str(candidate.get("ticker") or "").upper()
        if not ticker:
            continue
        eff, source = effective_trade_date_on_or_after(candidate["as_of_date"], trading_dates)
        if eff is None:
            continue
        by_ticker[ticker].append(
            {
                "ticker": ticker,
                "candidate_as_of_date": candidate.get("as_of_date"),
                "candidate_effective_trade_date": eff.isoformat(),
                "candidate_effective_date_source": source,
                "candidate_source": candidate.get("candidate_source"),
                "record_type": candidate.get("record_type"),
                "selected_signal": candidate.get("selected_signal"),
                "strategy": candidate.get("strategy"),
            }
        )
    for rows in by_ticker.values():
        rows.sort(key=lambda item: (item["candidate_effective_trade_date"], item["candidate_as_of_date"]))
    return by_ticker


def find_candidate_hit(
    *,
    ticker: str,
    effective_date: date | None,
    candidate_index: dict[str, list[dict[str, Any]]],
    trading_dates: list[date],
    max_trading_days: int,
) -> dict[str, Any]:
    if effective_date is None:
        return {"hit": False, "hit_status": "missing_watchlist_effective_trade_date"}
    if effective_date not in set(trading_dates):
        return {
            "hit": False,
            "hit_status": "watchlist_effective_trade_date_not_closed",
        }
    matches = []
    for candidate in candidate_index.get(str(ticker).upper(), []):
        candidate_effective = _coerce_date(candidate["candidate_effective_trade_date"])
        distance = trading_day_distance(effective_date, candidate_effective, trading_dates)
        if distance is None:
            continue
        if 0 <= distance <= max_trading_days:
            matches.append((distance, candidate))
    if not matches:
        return {"hit": False, "hit_status": f"no_candidate_within_{max_trading_days}td"}
    distance, candidate = sorted(matches, key=lambda item: item[0])[0]
    return {
        "hit": True,
        "hit_status": f"candidate_hit_within_{max_trading_days}td",
        "candidate_hit_trading_days": distance,
        "candidate_hit": candidate,
    }


def _pead_window_status(row: dict[str, Any], effective_date: date | None) -> dict[str, Any]:
    last_earnings = (
        row.get("last_earnings_date")
        or row.get("earnings_date")
        or row.get("reported_earnings_date")
    )
    if not effective_date:
        return {"pead_window": False, "pead_status": "missing_effective_trade_date"}
    if not last_earnings:
        return {"pead_window": False, "pead_status": "missing_last_earnings_date"}
    days = (effective_date - _coerce_date(last_earnings)).days
    return {
        "pead_window": 2 <= days <= 15,
        "pead_status": "inside_t2_t15_after_earnings" if 2 <= days <= 15 else "outside_t2_t15_after_earnings",
        "days_since_last_earnings": days,
    }


def annotate_watchlist_rows(
    *,
    ledger_map: dict[tuple[str, str], dict[str, Any]],
    features_by_date: dict[str, dict[str, dict[str, Any]]],
    prices: Any,
    trading_dates: list[date],
    candidate_index: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    feature_dates = _feature_index(features_by_date)
    annotated = []
    for (as_of, ticker), ledger_row in sorted(ledger_map.items()):
        if not ledger_row.get("estimate_revision_usable"):
            continue
        effective_date, effective_source = effective_trade_date_on_or_after(as_of, trading_dates)
        revision_signal = classify_revision_signal(ledger_row)
        residual = residual_context_for_watchlist_row(
            {"as_of_date": as_of, "ticker": ticker},
            features_by_date,
            feature_dates,
        )
        residual_leader = bool(residual.get("residual_leader"))
        primary_bucket = classify_bucket(
            revision_signal["primary_expectation_positive"],
            residual_leader,
        )
        wide_bucket = classify_bucket(
            revision_signal["wide_watchlist_positive"],
            residual_leader,
        )
        forward = {
            f"{horizon}d": prices.forward_return(
                ticker,
                effective_date,
                horizon,
            )
            if effective_date is not None
            else {
                "closed": False,
                "return": None,
                "pnl_proxy": None,
                "future_date": None,
                "gap_reason": "missing_effective_trade_date",
            }
            for horizon in FORWARD_HORIZONS
        }
        candidate_hits = {
            f"{window}td": find_candidate_hit(
                ticker=ticker,
                effective_date=effective_date,
                candidate_index=candidate_index,
                trading_dates=trading_dates,
                max_trading_days=window,
            )
            for window in CANDIDATE_HIT_WINDOWS
        }
        annotated.append(
            {
                "as_of_date": as_of,
                "ticker": ticker,
                "watchlist_effective_trade_date": effective_date.isoformat()
                if effective_date
                else None,
                "effective_date_source": effective_source,
                "estimate_revision_usable": bool(ledger_row.get("estimate_revision_usable")),
                "eps_estimate": ledger_row.get("eps_estimate"),
                "revenue_estimate": ledger_row.get("revenue_estimate"),
                "next_earnings_date": ledger_row.get("next_earnings_date"),
                "same_event_history_count": ledger_row.get("same_event_history_count"),
                "source_snapshot_path": ledger_row.get("source_snapshot_path"),
                "source_snapshot_pit_safe": ledger_row.get("source_snapshot_pit_safe"),
                "pit_caveat": ledger_row.get("pit_caveat"),
                **revision_signal,
                **residual,
                "primary_bucket": primary_bucket,
                "wide_watchlist_bucket": wide_bucket,
                "candidate_hits": candidate_hits,
                **_pead_window_status(ledger_row, effective_date),
                "forward_outcomes": forward,
            }
        )
    return annotated


def _compact_row(row: dict[str, Any], horizon_key: str | None = None) -> dict[str, Any]:
    theme_residuals = row.get("theme_residuals") if isinstance(row.get("theme_residuals"), dict) else {}
    ret20_excess_theme = max(theme_residuals.values()) if theme_residuals else None
    out = {
        "as_of_date": row.get("as_of_date"),
        "ticker": row.get("ticker"),
        "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
        "effective_date_source": row.get("effective_date_source"),
        "primary_bucket": row.get("primary_bucket"),
        "wide_watchlist_bucket": row.get("wide_watchlist_bucket"),
        "primary_expectation_positive": row.get("primary_expectation_positive"),
        "support_30d_positive": row.get("support_30d_positive"),
        "scout_prev_positive": row.get("scout_prev_positive"),
        "wide_watchlist_positive": row.get("wide_watchlist_positive"),
        "watchlist_signal_basis": row.get("watchlist_signal_basis"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
        "same_event_history_count": row.get("same_event_history_count"),
        "residual_leader": row.get("residual_leader"),
        "residual_state": row.get("residual_state"),
        "residual_strength_score": row.get("residual_strength_score"),
        "ret20_excess_spy": row.get("ret20_excess_spy"),
        "ret20_excess_qqq": row.get("ret20_excess_qqq"),
        "ret20_excess_sector": row.get("ret20_excess_sector"),
        "sector": row.get("sector"),
        "ret20_excess_theme": ret20_excess_theme,
        "theme_residuals": theme_residuals,
        "themes": row.get("themes"),
        "feature_context_date": row.get("feature_context_date"),
        "pead_status": row.get("pead_status"),
        "candidate_hit_3td": row.get("candidate_hits", {}).get("3td", {}).get("hit"),
        "candidate_hit_10td": row.get("candidate_hits", {}).get("10td", {}).get("hit"),
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


def build_bucket_summary(rows: list[dict[str, Any]], bucket_key: str) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_bucket[row[bucket_key]].append(row)
    summary = {}
    for bucket in BUCKETS:
        bucket_rows = by_bucket.get(bucket, [])
        summary[bucket] = {
            "row_count": len(bucket_rows),
            "ticker_count": len({row["ticker"] for row in bucket_rows}),
            "tickers": sorted({row["ticker"] for row in bucket_rows}),
            "residual_state_breakdown": dict(Counter(row.get("residual_state") or "missing" for row in bucket_rows)),
            "watchlist_signal_basis_breakdown": dict(
                Counter(
                    "+".join(row.get("watchlist_signal_basis") or ["none"])
                    for row in bucket_rows
                )
            ),
            "candidate_hit_counts": {
                f"{window}td": sum(
                    1
                    for row in bucket_rows
                    if row.get("candidate_hits", {}).get(f"{window}td", {}).get("hit")
                )
                for window in CANDIDATE_HIT_WINDOWS
            },
            "horizons": {
                f"{horizon}d": summarize_rows(bucket_rows, f"{horizon}d")
                for horizon in FORWARD_HORIZONS
            },
        }
    return summary


def evaluate_gate(
    bucket_summary: dict[str, Any],
    *,
    positive_rows: int,
    scope: str,
    promotable: bool,
) -> dict[str, Any]:
    bucket_a_5d = bucket_summary["A_positive_expectation_and_residual_leader"]["horizons"]["5d"]
    total_closed_5d = sum(
        row["horizons"]["5d"]["closed_outcomes"]
        for row in bucket_summary.values()
    )
    data_gap_reasons = []
    if bucket_a_5d["closed_outcomes"] < MIN_BUCKET_A_5D_OUTCOMES:
        data_gap_reasons.append("bucket_a_closed_5d_outcomes")
    if positive_rows < MIN_PRIMARY_POSITIVE_ROWS:
        data_gap_reasons.append("positive_expectation_rows")
    if total_closed_5d < MIN_TOTAL_CLOSED_5D_OUTCOMES:
        data_gap_reasons.append("total_closed_5d_outcomes")
    if data_gap_reasons:
        return {
            "passed": False,
            "decision": "observed_only_data_gap",
            "decision_scope": scope,
            "promotable": False,
            "reason": "insufficient_bucket_or_total_sample",
            "data_gap_reasons": data_gap_reasons,
            "bucket_a_closed_5d_outcomes": bucket_a_5d["closed_outcomes"],
            "minimum_bucket_a_closed_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
            "positive_expectation_rows": positive_rows,
            "minimum_positive_expectation_rows": MIN_PRIMARY_POSITIVE_ROWS,
            "total_closed_5d_outcomes": total_closed_5d,
            "minimum_total_closed_5d_outcomes": MIN_TOTAL_CLOSED_5D_OUTCOMES,
        }

    comparisons = []
    a_beats_all = True
    for horizon in ("5d", "10d"):
        a_avg = bucket_summary["A_positive_expectation_and_residual_leader"]["horizons"][horizon]["avg_return"]
        for bucket in BUCKETS[1:]:
            other_avg = bucket_summary[bucket]["horizons"][horizon]["avg_return"]
            passed = a_avg is not None and other_avg is not None and a_avg > other_avg
            comparisons.append(
                {
                    "horizon": horizon,
                    "comparison_bucket": bucket,
                    "bucket_a_avg_return": a_avg,
                    "other_avg_return": other_avg,
                    "passed": passed,
                }
            )
            a_beats_all = a_beats_all and passed

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
    passed = bool(a_beats_all and concentration["passed"] and promotable)
    return {
        "passed": passed,
        "decision": (
            "observed_only_promising_revision_watchlist"
            if passed
            else "rejected_or_scout_only_revision_watchlist"
        ),
        "decision_scope": scope,
        "promotable": promotable,
        "reason": "bucket_a_outperformance_and_concentration"
        if passed
        else "bucket_a_failed_outperformance_concentration_or_scope",
        "comparisons": comparisons,
        "concentration": concentration,
        "bucket_a_closed_5d_outcomes": bucket_a_5d["closed_outcomes"],
        "positive_expectation_rows": positive_rows,
        "total_closed_5d_outcomes": total_closed_5d,
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
    positive_rows: list[dict[str, Any]],
    trading_dates: list[date],
) -> dict[str, Any]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in positive_rows:
        by_ticker[row["ticker"]].append(row)
    position_tickers = {str(row.get("ticker") or "").upper() for row in positions}
    ticker_overlap = sorted(position_tickers & set(by_ticker))
    entry_matches = []
    for position in positions:
        ticker = str(position.get("ticker") or "").upper()
        entry_date = position.get("entry_date")
        if not ticker or not entry_date:
            continue
        entry_effective, _source = effective_trade_date_on_or_after(entry_date, trading_dates)
        if entry_effective is None or entry_effective not in set(trading_dates):
            continue
        matches = []
        for row in by_ticker.get(ticker, []):
            watchlist_effective = row.get("watchlist_effective_trade_date")
            if not watchlist_effective:
                continue
            watchlist_day = _coerce_date(watchlist_effective)
            distance = trading_day_distance(watchlist_day, entry_effective, trading_dates)
            if distance is not None and 0 <= distance <= CURRENT_POSITION_MATCH_WINDOW:
                matches.append((distance, row))
        if matches:
            distance, row = sorted(matches, key=lambda item: item[0])[0]
            entry_matches.append(
                {
                    "ticker": ticker,
                    "entry_date": entry_date,
                    "entry_effective_trade_date": entry_effective.isoformat(),
                    "revision_as_of_date": row.get("as_of_date"),
                    "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
                    "entry_lag_trading_days": distance,
                    "watchlist_signal_basis": row.get("watchlist_signal_basis"),
                    "primary_expectation_positive": row.get("primary_expectation_positive"),
                    "wide_watchlist_positive": row.get("wide_watchlist_positive"),
                    "residual_state": row.get("residual_state"),
                    "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
                    "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
                    "eps_estimate_delta_prev": row.get("eps_estimate_delta_prev"),
                    "shares": position.get("shares"),
                    "avg_cost": position.get("avg_cost"),
                    "opened_by_strategy": position.get("opened_by_strategy"),
                    "position_source": position.get("position_source"),
                }
            )
    return {
        "current_position_count": len(positions),
        "ticker_overlap_with_positive_watchlist": ticker_overlap,
        "ticker_overlap_count": len(ticker_overlap),
        "entry_watchlist_match_count": len(entry_matches),
        "entry_watchlist_matches": entry_matches,
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


def build_coverage(
    annotated: list[dict[str, Any]],
    ledger_map: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    unusable = [row for row in ledger_map.values() if not row.get("estimate_revision_usable")]
    positive_primary = [row for row in annotated if row.get("primary_expectation_positive")]
    positive_wide = [row for row in annotated if row.get("wide_watchlist_positive")]
    primary_bucket_a = [
        row
        for row in annotated
        if row.get(PRIMARY_BUCKET_KEY) == "A_positive_expectation_and_residual_leader"
    ]
    wide_bucket_a = [
        row
        for row in annotated
        if row.get(WIDE_BUCKET_KEY) == "A_positive_expectation_and_residual_leader"
    ]
    def hit_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            f"{window}td": sum(
                1
                for row in rows
                if row.get("candidate_hits", {}).get(f"{window}td", {}).get("hit")
            )
            for window in CANDIDATE_HIT_WINDOWS
        }

    closed_by_horizon = {
        f"{horizon}d": sum(
            1
            for row in annotated
            if (row.get("forward_outcomes", {}).get(f"{horizon}d") or {}).get("closed")
        )
        for horizon in FORWARD_HORIZONS
    }
    return {
        "ledger_rows_total": len(ledger_map),
        "pit_usable_revision_rows": len(annotated),
        "pit_unusable_revision_rows": len(unusable),
        "primary_positive_7d_rows": len(positive_primary),
        "primary_positive_7d_ticker_count": len({row["ticker"] for row in positive_primary}),
        "primary_positive_7d_tickers": sorted({row["ticker"] for row in positive_primary}),
        "support_30d_positive_rows": sum(1 for row in annotated if row.get("support_30d_positive")),
        "scout_prev_positive_rows": sum(1 for row in annotated if row.get("scout_prev_positive")),
        "wide_watchlist_positive_rows": len(positive_wide),
        "wide_watchlist_positive_ticker_count": len({row["ticker"] for row in positive_wide}),
        "wide_watchlist_positive_tickers": sorted({row["ticker"] for row in positive_wide}),
        "expectation_status_counts": dict(Counter(row.get("expectation_status") for row in annotated)),
        "watchlist_signal_basis_counts": dict(
            Counter("+".join(row.get("watchlist_signal_basis") or ["none"]) for row in annotated)
        ),
        "residual_context_status_counts": dict(Counter(row.get("residual_context_status") for row in annotated)),
        "residual_state_counts": dict(Counter(row.get("residual_state") or "missing" for row in annotated)),
        "residual_leader_rows": sum(1 for row in annotated if row.get("residual_leader")),
        "pead_status_counts": dict(Counter(row.get("pead_status") for row in annotated)),
        "candidate_hit_counts_all_usable_rows": hit_counts(annotated),
        "candidate_hit_counts_primary_positive_rows": hit_counts(positive_primary),
        "candidate_hit_counts_wide_positive_rows": hit_counts(positive_wide),
        "candidate_hit_counts_primary_bucket_a_rows": hit_counts(primary_bucket_a),
        "candidate_hit_counts_wide_bucket_a_rows": hit_counts(wide_bucket_a),
        "closed_forward_outcomes": closed_by_horizon,
        "effective_date_source_counts": dict(Counter(row.get("effective_date_source") for row in annotated)),
    }


def _compact_rows(rows: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    compact = [_compact_row(row) for row in rows]
    compact.sort(
        key=lambda row: (
            row.get("as_of_date") or "",
            row.get("residual_strength_score") if row.get("residual_strength_score") is not None else -999,
            row.get("ticker") or "",
        ),
        reverse=True,
    )
    return compact[:limit] if limit is not None else compact


def build_latest_watchlists(annotated: list[dict[str, Any]]) -> dict[str, Any]:
    if not annotated:
        return {
            "latest_as_of_date": None,
            "primary_positive_7d": [],
            "wide_positive": [],
        }
    latest = max(row["as_of_date"] for row in annotated)
    latest_rows = [row for row in annotated if row["as_of_date"] == latest]
    return {
        "latest_as_of_date": latest,
        "primary_positive_7d_count": sum(1 for row in latest_rows if row.get("primary_expectation_positive")),
        "wide_positive_count": sum(1 for row in latest_rows if row.get("wide_watchlist_positive")),
        "primary_positive_7d": _compact_rows(
            [row for row in latest_rows if row.get("primary_expectation_positive")],
            limit=50,
        ),
        "wide_positive": _compact_rows(
            [row for row in latest_rows if row.get("wide_watchlist_positive")],
            limit=50,
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Expectation Revision Watchlist Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha search. No entries, exits, ranking, sizing, paper sleeves, LLM/news, or orders changed.",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(payload["coverage"], indent=2, sort_keys=True),
        "```",
        "",
        "## Latest Watchlist",
        "",
        "```json",
        json.dumps(payload["latest_watchlists"], indent=2, sort_keys=True),
        "```",
        "",
        "## Primary Bucket Summary",
        "",
        "| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["primary_bucket_summary"].items():
        h5 = row["horizons"]["5d"]
        h10 = row["horizons"]["10d"]
        h20 = row["horizons"]["20d"]
        lines.append(
            "| {bucket} | {rows} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} | {h20_count} | {h20_avg} |".format(
                bucket=bucket,
                rows=row["row_count"],
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
            "## Wide Watchlist Bucket Summary",
            "",
            "| Bucket | Rows | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return | 20d Closed | 20d Avg Return |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for bucket, row in payload["wide_watchlist_bucket_summary"].items():
        h5 = row["horizons"]["5d"]
        h10 = row["horizons"]["10d"]
        h20 = row["horizons"]["20d"]
        lines.append(
            "| {bucket} | {rows} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} | {h20_count} | {h20_avg} |".format(
                bucket=bucket,
                rows=row["row_count"],
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
            "## Current Position Overlap",
            "",
            "```json",
            json.dumps(payload["current_position_overlap"], indent=2, sort_keys=True),
            "```",
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
    candidate_index = build_candidate_index(candidates, trading_dates)
    annotated = annotate_watchlist_rows(
        ledger_map=ledger_map,
        features_by_date=features_by_date,
        prices=prices,
        trading_dates=trading_dates,
        candidate_index=candidate_index,
    )
    primary_bucket_summary = build_bucket_summary(annotated, PRIMARY_BUCKET_KEY)
    wide_watchlist_bucket_summary = build_bucket_summary(annotated, WIDE_BUCKET_KEY)
    coverage = build_coverage(annotated, ledger_map)
    primary_gate = evaluate_gate(
        primary_bucket_summary,
        positive_rows=coverage["primary_positive_7d_rows"],
        scope="primary_7d_promotable_readout",
        promotable=True,
    )
    wide_gate = evaluate_gate(
        wide_watchlist_bucket_summary,
        positive_rows=coverage["wide_watchlist_positive_rows"],
        scope="wide_watchlist_scout_not_promotable",
        promotable=False,
    )
    positive_wide_rows = [row for row in annotated if row.get("wide_watchlist_positive")]
    current_position_overlap = build_current_position_overlap(
        load_current_positions(),
        positive_wide_rows,
        trading_dates,
    )
    field_check = _open_position_field_check()
    decision = primary_gate["decision"]
    status = "observed_only_data_gap" if decision == "observed_only_data_gap" else (
        "observed_only" if primary_gate["passed"] else "rejected"
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
            "PIT-safe positive expectation revision rows, observed before "
            "requiring same-day Ginger candidate membership, may identify a "
            "larger watchlist where residual leaders have superior 5/10/20 "
            "trading-day outcomes and later candidate/position conversion."
        ),
        "change_summary": (
            "Read-only watchlist attribution over the full PIT-usable "
            "estimate-revision ledger universe, joined to residual leadership, "
            "candidate hits, current positions, and forward outcomes."
        ),
        "change_type": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "pit_revision_universe_watchlist_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 8,
        "nearby_prior_experiments": [
            "exp-20260507-090",
            "exp-20260507-900",
            "exp-20260513-103",
            "exp-20260513-104",
            "exp-20260525-017",
            "exp-20260525-021",
            "exp-20260525-023",
            "exp-20260525-025",
            "exp-20260525-031",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "expanded_pit_revision_universe_watchlist_attribution",
        "component": "quant/experiments/exp_20260525_034_expectation_revision_watchlist_attribution.py",
        "parameters": {
            "primary_positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "wide_watchlist_definition": (
                "estimate_revision_usable && "
                "(eps_estimate_delta_7d > 0 || eps_estimate_delta_30d > 0 || eps_estimate_delta_prev > 0)"
            ),
            "wide_watchlist_policy": (
                "Larger watchlist for evidence accumulation only. It cannot "
                "promote live logic because it mixes 30d support and prev-delta "
                "scout signals with the primary 7d definition."
            ),
            "candidate_hit_windows_trading_days": list(CANDIDATE_HIT_WINDOWS),
            "current_position_match_window_trading_days": CURRENT_POSITION_MATCH_WINDOW,
            "residual_leader_states": sorted(RESIDUAL_LEADER_STATES),
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "gate_thresholds": {
                "min_bucket_a_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
                "min_primary_positive_rows": MIN_PRIMARY_POSITIVE_ROWS,
                "min_total_closed_5d_outcomes": MIN_TOTAL_CLOSED_5D_OUTCOMES,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "estimate_revision_ledgers": "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
            "candidate_artifacts": "data/daily/signals/quant/quant_signals_*.json",
            "ohlcv_sources": [
                "data/ohlcv/ohlcv_snapshot_*.json",
                "data/daily/signals/trend/trend_signals_*.json",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool/ranking research: expanding from candidate-only "
                "joins to the full PIT revision universe should reveal whether "
                "expectation-drift names later become residual leaders and Ginger "
                "candidates."
            ),
            "2_history_check": (
                "exp-20260525-017 had no strict same-day Bucket A. "
                "exp-20260525-031 found COHR as a same-event prev-delta lead, "
                "but the candidate-only sample was too sparse."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Primary observed-only gate: primary 7d Bucket A has enough "
                "closed outcomes, enough positive rows, beats B/C/D on 5d and "
                "10d average return, and passes concentration guardrails. "
                "Wide watchlist can guide data accumulation only."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_034_expectation_revision_watchlist_attribution.py"
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
                "PIT estimate_revision_ledger rows",
                "daily quant feature context for residual leadership",
                "persisted candidate objects for candidate-hit attribution",
                "local OHLCV/trend close rows for forward returns",
                "operator_inputs/open_positions.json for current-position overlap",
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
            "note": "A passing primary readout would only unlock a later PEAD paper sleeve or ranking-component experiment.",
        },
        "coverage": coverage,
        "primary_bucket_summary": primary_bucket_summary,
        "wide_watchlist_bucket_summary": wide_watchlist_bucket_summary,
        "latest_watchlists": build_latest_watchlists(annotated),
        "current_position_overlap": current_position_overlap,
        "gate": {
            "primary_7d_gate": primary_gate,
            "wide_watchlist_scout_gate": wide_gate,
        },
        "annotated_watchlist_rows": _compact_rows(annotated),
        "sample_primary_positive_rows": _compact_rows(
            [row for row in annotated if row.get("primary_expectation_positive")],
            limit=50,
        ),
        "sample_wide_positive_rows": _compact_rows(positive_wide_rows, limit=80),
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "pit_usable_revision_rows": coverage["pit_usable_revision_rows"],
            "primary_positive_7d_rows": coverage["primary_positive_7d_rows"],
            "wide_watchlist_positive_rows": coverage["wide_watchlist_positive_rows"],
            "primary_bucket_a_closed_5d_outcomes": primary_gate.get("bucket_a_closed_5d_outcomes"),
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
            "This is a larger data-accumulation watchlist. It tests whether "
            "PIT revision rows have bucket-level value before requiring same-day "
            "candidate membership. It does not promote live logic."
        ),
        "rejection_reason": None
        if primary_gate["passed"]
        else (
            "primary 7d expectation-residual watchlist lacks enough evidence "
            "or failed observed-only outperformance/concentration gates"
        ),
        "next_evidence_needed": (
            "Continue daily PIT revision ledgers and candidate artifacts; if "
            "primary Bucket A matures, test a separate default-off PEAD paper "
            "sleeve with explicit T+2 to T+10 earnings-date coverage."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep_keys = (
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
        "primary_bucket_summary",
        "wide_watchlist_bucket_summary",
        "latest_watchlists",
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
    return {key: payload[key] for key in keep_keys}


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
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "coverage": payload["coverage"],
                    "current_position_overlap": payload["current_position_overlap"],
                    "gate": payload["gate"],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
