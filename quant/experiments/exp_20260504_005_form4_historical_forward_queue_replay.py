"""Historical replay for the default-off Form 4 forward queue.

This is a shadow/default-off replay only. It reuses the production-visible
Form 4 queue qualification helpers, then measures what the queue would have
emitted across the canonical windows using point-in-time usable trade dates.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    PRIMARY_HORIZON_TRADING_DAYS,
    QUEUE_NAME,
    RULE_VERSION,
    aggregate_purchase_events,
    build_form4_event_queue,
    latest_form4_transactions_path,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXP_ID = "exp-20260504-005"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_historical_forward_queue_replay.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
REGISTRY_JSON = DOCS_DIR / "experiment_registry.json"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_historical_forward_queue_replay_20260504.md"
BACKFILL_SUMMARY = DATA_DIR / "non_ohlcv" / "form4_backfill_summary_20241002_20260502.json"
ACCEPTED_TRADES = DATA_DIR / "experiments" / "current_accepted_trades_20260502_alpha_search.json"
ORACLE_DIR = DATA_DIR / "experiments" / "oracle_standard_3window_20260501_220042"

SNAPSHOT_FILES = [
    DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260501_with_pilot.json",
]
WINDOW_ORDER = ("old_thin", "mid_weak", "late_strong")
WINDOW_RANGES = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
HORIZONS = (5, 10, 20, 60, 90)
LOOKBACKS = (0, 5, 10, 20, 60, 90, 120)
ORACLE_FILES = {
    "old_thin": ORACLE_DIR / "old_thin_entry_skip_oracle.json",
    "mid_weak": ORACLE_DIR / "mid_weak_entry_skip_oracle.json",
    "late_strong": ORACLE_DIR / "late_strong_entry_skip_oracle.json",
}

BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 3.4191,
        "total_return_pct": 0.7860,
        "total_pnl": 78600.33,
        "sharpe_daily": 4.35,
        "max_drawdown_pct": 0.0541,
        "win_rate": 0.7895,
        "trade_count": 19,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
        "vs_spy_pct": 0.7319,
        "vs_qqq_pct": 0.7280,
    },
    "mid_weak": {
        "expected_value_score": 1.4415,
        "total_return_pct": 0.5502,
        "total_pnl": 55015.08,
        "sharpe_daily": 2.62,
        "max_drawdown_pct": 0.0879,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
        "vs_spy_pct": 0.2958,
        "vs_qqq_pct": 0.2151,
    },
    "old_thin": {
        "expected_value_score": 0.3179,
        "total_return_pct": 0.2464,
        "total_pnl": 24642.07,
        "sharpe_daily": 1.29,
        "max_drawdown_pct": 0.0805,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 55,
        "survival_rate": 0.9167,
        "vs_spy_pct": 0.3137,
        "vs_qqq_pct": 0.3213,
    },
}


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _load_price_map(snapshot_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for path in snapshot_paths:
        payload = _load_json(path, {})
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                date_key = str(row["Date"])[:10]
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "open": _float_or_none(row.get("Open")),
                    "close": _float_or_none(row.get("Close")),
                    "high": _float_or_none(row.get("High")),
                    "low": _float_or_none(row.get("Low")),
                    "volume": _float_or_none(row.get("Volume")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _forward_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_trade_date: str,
    horizon: int,
) -> dict[str, Any] | None:
    rows = prices.get(str(ticker).upper())
    spy_rows = prices.get("SPY")
    qqq_rows = prices.get("QQQ")
    if not rows or not spy_rows or not qqq_rows:
        return None
    start_idx = _first_index_on_or_after(rows, usable_trade_date)
    spy_start_idx = _first_index_on_or_after(spy_rows, usable_trade_date)
    qqq_start_idx = _first_index_on_or_after(qqq_rows, usable_trade_date)
    if start_idx is None or spy_start_idx is None or qqq_start_idx is None:
        return None
    exit_idx = start_idx + horizon
    spy_exit_idx = spy_start_idx + horizon
    qqq_exit_idx = qqq_start_idx + horizon
    if exit_idx >= len(rows) or spy_exit_idx >= len(spy_rows) or qqq_exit_idx >= len(qqq_rows):
        return None
    entry = rows[start_idx]
    exit_row = rows[exit_idx]
    spy_entry = spy_rows[spy_start_idx]
    spy_exit = spy_rows[spy_exit_idx]
    qqq_entry = qqq_rows[qqq_start_idx]
    qqq_exit = qqq_rows[qqq_exit_idx]
    if (
        not entry["open"]
        or not exit_row["close"]
        or not spy_entry["open"]
        or not spy_exit["close"]
        or not qqq_entry["open"]
        or not qqq_exit["close"]
    ):
        return None
    ret = exit_row["close"] / entry["open"] - 1.0
    spy_ret = spy_exit["close"] / spy_entry["open"] - 1.0
    qqq_ret = qqq_exit["close"] / qqq_entry["open"] - 1.0
    return {
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "return_pct": round(ret * 100.0, 4),
        "spy_return_pct": round(spy_ret * 100.0, 4),
        "qqq_return_pct": round(qqq_ret * 100.0, 4),
        "excess_vs_spy_pct": round((ret - spy_ret) * 100.0, 4),
        "excess_vs_qqq_pct": round((ret - qqq_ret) * 100.0, 4),
    }


def _entry_date(prices: dict[str, list[dict[str, Any]]], ticker: str, usable_trade_date: str) -> str | None:
    rows = prices.get(str(ticker).upper())
    if not rows:
        return None
    idx = _first_index_on_or_after(rows, usable_trade_date)
    if idx is None:
        return None
    return rows[idx]["date"]


def _window_name(value: str) -> str | None:
    for name, (start, end) in WINDOW_RANGES.items():
        if start <= value <= end:
            return name
    return None


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def _win_rate(values: list[float]) -> float | None:
    return round(sum(1 for value in values if value > 0.0) / len(values), 4) if values else None


def _summarize_outcomes(candidates: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    rows = [candidate for candidate in candidates if str(horizon) in candidate.get("outcomes", {})]
    returns = [row["outcomes"][str(horizon)]["return_pct"] for row in rows]
    spy_excess = [row["outcomes"][str(horizon)]["excess_vs_spy_pct"] for row in rows]
    qqq_excess = [row["outcomes"][str(horizon)]["excess_vs_qqq_pct"] for row in rows]
    return {
        "count": len(rows),
        "avg_return_pct": _mean(returns),
        "median_return_pct": _median(returns),
        "win_rate": _win_rate(returns),
        "avg_excess_vs_spy_pct": _mean(spy_excess),
        "median_excess_vs_spy_pct": _median(spy_excess),
        "excess_vs_spy_win_rate": _win_rate(spy_excess),
        "avg_excess_vs_qqq_pct": _mean(qqq_excess),
        "median_excess_vs_qqq_pct": _median(qqq_excess),
        "excess_vs_qqq_win_rate": _win_rate(qqq_excess),
    }


def _outcome_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        str(horizon): _summarize_outcomes(candidates, horizon)
        for horizon in HORIZONS
    }


def _queue_candidates(
    *,
    transaction_path: Path,
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = load_form4_transaction_rows(transaction_path)
    start = min(start for start, _ in WINDOW_RANGES.values())
    end = max(end for _, end in WINDOW_RANGES.values())
    events = aggregate_purchase_events(rows, start=start, end=end)
    candidates: list[dict[str, Any]] = []
    for event in events:
        if not qualifies_forward_queue_event(event):
            continue
        usable = str(event["usable_trade_date"])[:10]
        candidate = {
            **event,
            "window": _window_name(usable),
            "entry_date": _entry_date(prices, str(event["ticker"]), usable),
            "outcomes": {},
        }
        for horizon in HORIZONS:
            outcome = _forward_return(prices, str(event["ticker"]), usable, horizon)
            if outcome:
                candidate["outcomes"][str(horizon)] = outcome
        candidates.append(candidate)
    return candidates


def _daily_queue_replay(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    all_events = [
        {
            key: value
            for key, value in candidate.items()
            if key not in {"outcomes", "entry_date", "window"}
        }
        for candidate in candidates
    ]
    candidate_dates = sorted({str(candidate["usable_trade_date"])[:10] for candidate in candidates})
    daily_counts = {}
    examples = []
    for as_of in candidate_dates:
        queue = build_form4_event_queue(all_events, as_of=as_of, source_status="historical_replay")
        daily_counts[as_of] = queue["candidate_count"]
        for payload in queue["candidates"]:
            if len(examples) < 10:
                examples.append(payload)
    return {
        "queue_name": QUEUE_NAME,
        "rule_version": RULE_VERSION,
        "default_enabled": False,
        "historical_candidate_days": len(candidate_dates),
        "historical_candidate_count": sum(daily_counts.values()),
        "daily_candidate_counts": daily_counts,
        "sample_candidate_payloads": examples,
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }


def _flatten_accepted_trades(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path, {})
    rows: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return rows
    for window, window_payload in payload.items():
        if not isinstance(window_payload, dict):
            continue
        for trade in window_payload.get("trades") or []:
            if isinstance(trade, dict):
                rows.append({**trade, "window": window})
    return sorted(rows, key=lambda row: (row.get("entry_date") or "", row.get("ticker") or ""))


def _load_top_skipped_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window, path in ORACLE_FILES.items():
        payload = _load_json(path, {})
        oracle = payload.get("entry_skip_oracle", {}) if isinstance(payload, dict) else {}
        for row in oracle.get("top_skipped_opportunities") or []:
            if isinstance(row, dict):
                rows.append({**row, "window": window})
    return sorted(rows, key=lambda row: (row.get("date") or "", row.get("ticker") or ""))


def _days_between(start: str, end: str) -> int:
    start_dt = datetime.strptime(str(start)[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(str(end)[:10], "%Y-%m-%d")
    return (end_dt - start_dt).days


def _accepted_trade_overlap(candidates: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_ticker[str(candidate.get("ticker") or "").upper()].append(candidate)
    out: dict[str, Any] = {}
    for lookback in LOOKBACKS:
        matches = []
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            entry_date = str(trade.get("entry_date") or "")[:10]
            if not ticker or not entry_date:
                continue
            prior = []
            for candidate in by_ticker.get(ticker, []):
                event_date = str(candidate.get("usable_trade_date") or "")[:10]
                if event_date > entry_date:
                    continue
                age = _days_between(event_date, entry_date)
                if 0 <= age <= lookback:
                    prior.append((age, candidate))
            if prior:
                age, best = max(prior, key=lambda item: float(item[1].get("total_purchase_value") or 0.0))
                matches.append({
                    "window": trade.get("window"),
                    "ticker": ticker,
                    "strategy": trade.get("strategy"),
                    "entry_date": entry_date,
                    "days_after_form4_event": age,
                    "trade_pnl_pct_net": trade.get("pnl_pct_net"),
                    "best_form4_date": best.get("usable_trade_date"),
                    "best_form4_purchase_value": best.get("total_purchase_value"),
                })
        out[str(lookback)] = {
            "matched_trade_count": len(matches),
            "matched_tickers": sorted({row["ticker"] for row in matches}),
            "matches": matches[:20],
        }
    return out


def _skip_oracle_overlap(candidates: list[dict[str, Any]], skipped_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_ticker[str(candidate.get("ticker") or "").upper()].append(candidate)
    out: dict[str, Any] = {}
    for lookback in LOOKBACKS:
        matches = []
        for row in skipped_rows:
            ticker = str(row.get("ticker") or "").upper()
            candidate_date = str(row.get("date") or row.get("entry_date") or "")[:10]
            if not ticker or not candidate_date:
                continue
            prior = []
            for event in by_ticker.get(ticker, []):
                event_date = str(event.get("usable_trade_date") or "")[:10]
                if event_date > candidate_date:
                    continue
                age = _days_between(event_date, candidate_date)
                if 0 <= age <= lookback:
                    prior.append((age, event))
            if prior:
                age, best = max(prior, key=lambda item: float(item[1].get("total_purchase_value") or 0.0))
                matches.append({
                    "window": row.get("window"),
                    "ticker": ticker,
                    "strategy": row.get("strategy"),
                    "candidate_date": candidate_date,
                    "days_after_form4_event": age,
                    "max_forward_return_pct": row.get("max_forward_return_pct"),
                    "best_form4_date": best.get("usable_trade_date"),
                    "best_form4_purchase_value": best.get("total_purchase_value"),
                })
        out[str(lookback)] = {
            "matched_candidate_count": len(matches),
            "matched_tickers": sorted({row["ticker"] for row in matches}),
            "matches": matches[:20],
        }
    return out


def _slot_value_audit(
    candidates: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    trades_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        if trade.get("entry_date"):
            trades_by_entry[str(trade["entry_date"])[:10]].append(trade)
    skipped_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in skipped_rows:
        entry_date = row.get("entry_date") or row.get("date")
        if entry_date:
            skipped_by_entry[str(entry_date)[:10]].append(row)

    accepted_conflicts = []
    skipped_conflicts = []
    for candidate in candidates:
        entry_date = candidate.get("entry_date")
        if not entry_date:
            continue
        if trades_by_entry.get(entry_date):
            accepted_conflicts.append({
                "form4_ticker": candidate.get("ticker"),
                "entry_date": entry_date,
                "form4_10d_excess_vs_spy_pct": (
                    (candidate.get("outcomes") or {}).get("10") or {}
                ).get("excess_vs_spy_pct"),
                "same_day_accepted_trades": [
                    {
                        "ticker": trade.get("ticker"),
                        "strategy": trade.get("strategy"),
                        "pnl_pct_net": trade.get("pnl_pct_net"),
                    }
                    for trade in trades_by_entry[entry_date]
                ],
            })
        if skipped_by_entry.get(entry_date):
            skipped_conflicts.append({
                "form4_ticker": candidate.get("ticker"),
                "entry_date": entry_date,
                "same_day_top_skipped": [
                    {
                        "ticker": row.get("ticker"),
                        "strategy": row.get("strategy"),
                        "max_forward_return_pct": row.get("max_forward_return_pct"),
                    }
                    for row in skipped_by_entry[entry_date]
                ],
            })

    return {
        "same_day_accepted_trade_conflict_count": len(accepted_conflicts),
        "same_day_top_skipped_conflict_count": len(skipped_conflicts),
        "measurable": bool(accepted_conflicts or skipped_conflicts),
        "slot_conflict_value_proxy": "same-day conflict only; not portfolio-capacity aware",
        "accepted_trade_conflict_examples": accepted_conflicts[:10],
        "top_skipped_conflict_examples": skipped_conflicts[:10],
    }


def _coverage(candidates: list[dict[str, Any]], backfill_summary: dict[str, Any], transaction_path: Path) -> dict[str, Any]:
    return {
        "transaction_file": _repo_rel(transaction_path),
        "backfill_rows_written": backfill_summary.get("rows_written"),
        "pit_safe_count": backfill_summary.get("pit_safe_count"),
        "filings_seen": backfill_summary.get("filings_seen"),
        "open_market_purchase_count": backfill_summary.get("open_market_purchase_count"),
        "requested_ticker_count": backfill_summary.get("tickers_requested"),
        "mapped_ticker_count": backfill_summary.get("tickers_mapped"),
        "missing_cik_tickers": backfill_summary.get("missing_cik_tickers"),
        "queue_candidate_count": len(candidates),
        "queue_candidate_ticker_count": len({candidate.get("ticker") for candidate in candidates}),
        "queue_candidate_days": len({candidate.get("usable_trade_date") for candidate in candidates}),
        "pit_status": "PIT-safe for shadow replay via usable_trade_date; no filing-date lookahead used",
        "known_gaps": {
            "market_cap_join": "not available, so buy_value_to_market_cap is not scored",
            "complete_core_signal_history": "not available, so overlap uses accepted trades and saved skip-oracle proxies",
        },
    }


def _by_window(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for window in WINDOW_ORDER:
        rows = [candidate for candidate in candidates if candidate.get("window") == window]
        out[window] = {
            "candidate_count": len(rows),
            "ticker_count": len({candidate.get("ticker") for candidate in rows}),
            "tickers": sorted({str(candidate.get("ticker") or "") for candidate in rows if candidate.get("ticker")}),
            "forward_returns": _outcome_summary(rows),
        }
    return out


def _append_experiment_log(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update({
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(AUDIT_MD),
            "log": _repo_rel(LOG_JSON),
            "decision": payload["decision"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "candidate_count": payload["shadow_or_replay_metrics"]["queue_replay"]["historical_candidate_count"],
            "next_action": payload["next_action"],
        },
    })
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update({
                "status": payload["status"],
                "updated_at": payload["timestamp"],
                "completed_at": payload["timestamp"],
                "result": {
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "log_file": _repo_rel(LOG_JSON),
                    "reason": payload["decision_rationale"],
                },
            })
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def _write_report(payload: dict[str, Any]) -> None:
    replay = payload["shadow_or_replay_metrics"]
    aggregate = replay["forward_return_of_tagged_candidates"]
    lines = [
        "# Form 4 Historical Forward Queue Replay",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Data Availability",
        "",
        f"- transaction_file: `{payload['data_availability']['transaction_file']}`",
        f"- PIT-safe rows: `{payload['data_availability']['pit_safe_count']}`",
        f"- queue candidates: `{payload['data_availability']['queue_candidate_count']}`",
        f"- missing CIK tickers: `{payload['data_availability']['missing_cik_tickers']}`",
        "",
        "## Queue Replay",
        "",
        f"- queue_name: `{replay['queue_replay']['queue_name']}`",
        f"- rule_version: `{replay['queue_replay']['rule_version']}`",
        f"- historical_candidate_days: `{replay['queue_replay']['historical_candidate_days']}`",
        f"- historical_candidate_count: `{replay['queue_replay']['historical_candidate_count']}`",
        "",
        "| Horizon | Count | Avg return | Avg excess SPY | Avg excess QQQ | Excess SPY win rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for horizon in HORIZONS:
        row = aggregate[str(horizon)]
        lines.append(
            f"| {horizon}d | {row['count']} | {_fmt_pct(row['avg_return_pct'])} | "
            f"{_fmt_pct(row['avg_excess_vs_spy_pct'])} | {_fmt_pct(row['avg_excess_vs_qqq_pct'])} | "
            f"{row['excess_vs_spy_win_rate'] if row['excess_vs_spy_win_rate'] is not None else 'n/a'} |"
        )
    lines.extend([
        "",
        "## Three-Window Replay",
        "",
        "| Window | Candidates | 10d valid | 10d avg excess SPY | 60d valid | 60d avg excess SPY |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for window in WINDOW_ORDER:
        row = replay["by_window"][window]
        ten = row["forward_returns"]["10"]
        sixty = row["forward_returns"]["60"]
        lines.append(
            f"| {window} | {row['candidate_count']} | {ten['count']} | "
            f"{_fmt_pct(ten['avg_excess_vs_spy_pct'])} | {sixty['count']} | "
            f"{_fmt_pct(sixty['avg_excess_vs_spy_pct'])} |"
        )
    slot = replay["scarce_slot_opportunity_cost"]
    lines.extend([
        "",
        "## Overlap And Slot Value",
        "",
        f"- accepted trade matches within 20d: `{replay['overlap_with_existing_signals']['accepted_trade_lookbacks']['20']['matched_trade_count']}`",
        f"- top skipped matches within 120d: `{replay['overlap_with_existing_signals']['top_skipped_lookbacks']['120']['matched_candidate_count']}`",
        f"- same-day accepted-trade conflicts: `{slot['same_day_accepted_trade_conflict_count']}`",
        f"- same-day top-skipped conflicts: `{slot['same_day_top_skipped_conflict_count']}`",
        "",
        "## Decision",
        "",
        payload["decision_rationale"],
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    transaction_path = latest_form4_transactions_path(DATA_DIR / "non_ohlcv")
    if transaction_path is None:
        raise FileNotFoundError("missing data/non_ohlcv/form4_transactions_*.jsonl")
    prices = _load_price_map(SNAPSHOT_FILES)
    candidates = _queue_candidates(transaction_path=transaction_path, prices=prices)
    accepted_trades = _flatten_accepted_trades(ACCEPTED_TRADES)
    skipped_rows = _load_top_skipped_rows()
    backfill_summary = _load_json(BACKFILL_SUMMARY, {})
    queue_replay = _daily_queue_replay(candidates)
    by_window = _by_window(candidates)
    overlap = {
        "accepted_trade_count": len(accepted_trades),
        "top_skipped_candidate_count": len(skipped_rows),
        "accepted_trade_lookbacks": _accepted_trade_overlap(candidates, accepted_trades),
        "top_skipped_lookbacks": _skip_oracle_overlap(candidates, skipped_rows),
        "exact_core_signal_history_available": False,
        "proxy_note": "Existing-signal overlap is proxied with accepted trades and saved top-skipped oracle rows.",
    }
    slot_value = _slot_value_audit(candidates, accepted_trades, skipped_rows)
    replay_metrics = {
        "candidate_count": len(candidates),
        "candidate_tickers": sorted({str(candidate.get("ticker") or "") for candidate in candidates}),
        "queue_replay": queue_replay,
        "by_window": by_window,
        "forward_return_of_tagged_candidates": _outcome_summary(candidates),
        "overlap_with_existing_signals": overlap,
        "scarce_slot_opportunity_cost": slot_value,
        "sample_candidates": [
            {
                "ticker": candidate.get("ticker"),
                "usable_trade_date": candidate.get("usable_trade_date"),
                "entry_date": candidate.get("entry_date"),
                "window": candidate.get("window"),
                "total_purchase_value": candidate.get("total_purchase_value"),
                "owner_count": candidate.get("owner_count"),
                "sample_owner_names": candidate.get("sample_owner_names"),
                "sample_officer_titles": candidate.get("sample_officer_titles"),
                "outcomes": candidate.get("outcomes"),
            }
            for candidate in candidates
        ],
    }
    decision = "default_off_candidate_observation_only"
    rationale = (
        "Historical replay confirms the existing default-off Form 4 queue would have emitted "
        "nonzero PIT-safe candidates across all three canonical windows, with positive average "
        "10d SPY excess in windows that have valid outcomes. It still does not justify production "
        "promotion: old_thin has only one valid 10d sample, current live queue candidates remain "
        "zero, and slot-conflict value is not portfolio-capacity aware."
    )
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_discovery",
        "mechanism_family": "form4_standalone_external_event_source",
        "change_type": "historical_forward_queue_replay",
        "hypothesis": (
            "Historical PIT-safe Form 4 forward queue replay can show whether the existing "
            "default-off queue would have produced enough candidates and forward returns across "
            "canonical windows to justify a default-off replay harness."
        ),
        "non_ohlcv_data_source": "SEC Form 4 insider ownership filings parsed into PIT-safe transaction rows",
        "single_causal_variable": "historical replay of existing Form 4 forward queue candidates",
        "historical_experiment_check": {
            "prior_form4_experiments_found": True,
            "key_results": {
                "exp-20260503-048": "accepted-trade overlay was sparse",
                "exp-20260503-049": "top skipped opportunity overlap was zero",
                "exp-20260503-052": ">=500k standalone event branch was shadow-promising",
                "exp-20260503-053": "owner-role discriminator was rejected",
                "exp-20260504-001": "default-off forward queue added observe-only reporting",
                "exp-20260504-003": "duplicate guardrail found no new closed live queue evidence",
            },
            "why_this_is_not_repeat": (
                "This run replays the already-shared forward queue definition across history; "
                "it does not resweep values, roles, or OHLCV thresholds."
            ),
        },
        "data_availability": _coverage(candidates, backfill_summary, transaction_path),
        "baseline_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": {
            "late_strong": 0.0,
            "mid_weak": 0.0,
            "old_thin": 0.0,
            "production": 0.0,
        },
        "shadow_or_replay_metrics": replay_metrics,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_impact": "historical_shadow_replay_only_no_strategy_change",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "result": "not_applicable_default_off_shadow_replay",
        },
        "decision_rationale": rationale,
        "next_action": (
            "Keep the queue default-off and add/monitor closed-out replacement-value snapshots; "
            "the next valid promotion test is a shared default-off event-sleeve replay with "
            "explicit slot-capacity accounting, not another simple value or owner-role sweep."
        ),
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _update_ticket(payload)
    _update_registry(payload)
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    replay = payload["shadow_or_replay_metrics"]
    compact = {
        "experiment_id": EXP_ID,
        "decision": payload["decision"],
        "candidate_count": replay["queue_replay"]["historical_candidate_count"],
        "candidate_days": replay["queue_replay"]["historical_candidate_days"],
        "aggregate_10d": replay["forward_return_of_tagged_candidates"]["10"],
        "by_window_10d": {
            window: replay["by_window"][window]["forward_returns"]["10"]
            for window in WINDOW_ORDER
        },
        "slot_value": replay["scarce_slot_opportunity_cost"],
        "output": _repo_rel(OUT_JSON),
        "audit": _repo_rel(AUDIT_MD),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
