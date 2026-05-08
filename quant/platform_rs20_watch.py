"""Default-off platform RS20 no-gap forward watch.

This module records candidates that the core entry path already skipped or
deferred. It is an observation ledger only: it does not rank candidates, size
positions, consume slots, or emit orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
WATCH_NAME = "PLATFORM_RS20_NO_GAP_FORWARD_WATCH"
RULE_VERSION = "platform_rs20_no_gap_v1"
PLATFORM_POOL = ("META", "NFLX", "GOOG", "AMZN", "SPOT", "DIS", "APP")
RS20_EXCESS_THRESHOLD = 0.05
GAP_UP_THRESHOLD = 0.03

DEFAULT_LEDGER_PATH = Path("data/platform_rs20_no_gap_forward_watch.jsonl")
DEFAULT_SUMMARY_PATH = Path("data/platform_rs20_no_gap_forward_watch_summary.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_platform_rs20_forward_watch(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "watch_name": WATCH_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "platform_missed_count": 0,
        "platform_rs20_missed_count": 0,
        "no_gap_rs20_watch_count": 0,
        "candidates": [],
        "all_platform_missed_rows": [],
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
    }


def build_platform_rs20_forward_watch(
    *,
    as_of: str,
    entry_execution_plan: dict[str, Any] | None,
    ohlcv_by_ticker: dict[str, Any] | None,
    features_by_ticker: dict[str, Any] | None = None,
    earnings_by_ticker: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build same-day platform RS20 no-gap watch rows from skipped entries."""
    as_of_date = str(as_of)[:10]
    generated_at = generated_at or datetime.now(timezone.utc)
    plan = entry_execution_plan or {}
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if "SPY" not in rows_by_ticker:
        return empty_platform_rs20_forward_watch(as_of_date, "missing_spy_ohlcv")

    missed_rows = _missed_entry_rows(plan)
    platform_rows = []
    candidates = []
    for missed in missed_rows:
        ticker = str(missed.get("ticker") or "").upper()
        if ticker not in PLATFORM_POOL:
            continue
        metrics = _entry_state_metrics(
            ticker=ticker,
            as_of=as_of_date,
            rows_by_ticker=rows_by_ticker,
            features_by_ticker=features_by_ticker or {},
            earnings_by_ticker=earnings_by_ticker or {},
        )
        row = _candidate_row(missed, metrics, as_of_date)
        platform_rows.append(row)
        if row["is_platform_rs20_leader"] and row["no_gap_up_3pct"]:
            candidate = dict(row)
            candidate["watch_rank"] = len(candidates) + 1
            candidates.append(candidate)

    rs20_rows = [row for row in platform_rows if row["is_platform_rs20_leader"]]
    by_decision = Counter(row["decision"] for row in candidates)
    by_ticker = Counter(row["ticker"] for row in candidates)
    return {
        "schema_version": SCHEMA_VERSION,
        "watch_name": WATCH_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "enabled": False,
        "trade_enabled": False,
        "candidate_count": len(candidates),
        "platform_missed_count": len(platform_rows),
        "platform_rs20_missed_count": len(rs20_rows),
        "no_gap_rs20_watch_count": len(candidates),
        "candidates": candidates,
        "all_platform_missed_rows": platform_rows,
        "summary": {
            "by_decision": dict(sorted(by_decision.items())),
            "by_ticker": dict(sorted(by_ticker.items())),
        },
        "parameters": {
            "platform_pool": list(PLATFORM_POOL),
            "rs20_excess_threshold": RS20_EXCESS_THRESHOLD,
            "gap_up_threshold": GAP_UP_THRESHOLD,
            "source_decisions": ["scarce_slot_breakout_deferred", "slot_sliced"],
            "forward_gate_min_candidates": 8,
            "forward_gate_max_single_ticker_positive_share": 0.5,
        },
        "data_source": {
            "status": "loaded",
            "source": "run.py entry_execution_plan plus same-day OHLCV",
        },
        "production_impact": _production_impact(),
    }


def persist_platform_rs20_forward_watch(
    snapshot: dict[str, Any],
    *,
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
    summary_path: Path | str = DEFAULT_SUMMARY_PATH,
) -> dict[str, Any]:
    """Append new watch candidates and write a compact summary."""
    ledger = Path(ledger_path)
    summary = Path(summary_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)

    seen = _ledger_keys(ledger)
    appended = 0
    with ledger.open("a", encoding="utf-8") as handle:
        for candidate in snapshot.get("candidates") or []:
            key = _candidate_key(candidate)
            if key in seen:
                continue
            row = dict(candidate)
            row["schema_version"] = SCHEMA_VERSION
            row["watch_name"] = WATCH_NAME
            row["rule_version"] = RULE_VERSION
            row["logged_at"] = utc_now_iso()
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            seen.add(key)
            appended += 1

    history = _read_ledger_rows(ledger)
    history_by_ticker = Counter(str(row.get("ticker") or "") for row in history)
    history_by_decision = Counter(str(row.get("decision") or "") for row in history)
    out = {
        "schema_version": SCHEMA_VERSION,
        "watch_name": WATCH_NAME,
        "rule_version": RULE_VERSION,
        "updated_at": utc_now_iso(),
        "asof_date": snapshot.get("asof_date"),
        "candidate_count": snapshot.get("candidate_count", 0),
        "platform_missed_count": snapshot.get("platform_missed_count", 0),
        "platform_rs20_missed_count": snapshot.get("platform_rs20_missed_count", 0),
        "no_gap_rs20_watch_count": snapshot.get("no_gap_rs20_watch_count", 0),
        "appended_count": appended,
        "ledger_row_count": len(history),
        "ledger_path": str(ledger),
        "summary_path": str(summary),
        "history_by_ticker": dict(sorted(history_by_ticker.items())),
        "history_by_decision": dict(sorted(history_by_decision.items())),
        "candidates": snapshot.get("candidates") or [],
        "production_impact": _production_impact(),
    }
    with summary.open("w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {**snapshot, "persistence": out}


def _production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "parity_test_added": False,
        "replay_only": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }


def _missed_entry_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for signal in plan.get("deferred_breakout_signals") or []:
        rows.append(
            {
                **signal,
                "decision": "scarce_slot_breakout_deferred",
                "candidate_rank": signal.get("candidate_rank"),
            }
        )
    for rank, signal in enumerate(plan.get("slot_sliced_signals") or [], start=1):
        rows.append(
            {
                **signal,
                "decision": "slot_sliced",
                "candidate_rank": signal.get("candidate_rank", rank),
            }
        )
    return rows


def _candidate_row(
    missed: dict[str, Any],
    metrics: dict[str, Any],
    as_of_date: str,
) -> dict[str, Any]:
    tags = []
    if metrics.get("gap_pct") is not None:
        if metrics["gap_pct"] >= GAP_UP_THRESHOLD:
            tags.append("gap_up_3pct")
        elif metrics["gap_pct"] <= -GAP_UP_THRESHOLD:
            tags.append("gap_down_3pct")
    if metrics.get("excess_spy_return_20d") is not None:
        if metrics["excess_spy_return_20d"] >= RS20_EXCESS_THRESHOLD:
            tags.append("rs20_leader")
        elif metrics["excess_spy_return_20d"] <= -RS20_EXCESS_THRESHOLD:
            tags.append("rs20_laggard")
    no_gap = metrics.get("gap_pct") is not None and metrics["gap_pct"] < GAP_UP_THRESHOLD
    ticker = str(missed.get("ticker") or "").upper()
    return {
        "asof_date": as_of_date,
        "ticker": ticker,
        "strategy": missed.get("strategy"),
        "decision": missed.get("decision"),
        "candidate_rank": missed.get("candidate_rank"),
        "entry_price": _safe_round(missed.get("entry_price"), 4),
        "stop_price": _safe_round(missed.get("stop_price"), 4),
        "target_price": _safe_round(missed.get("target_price"), 4),
        "sector": missed.get("sector"),
        "confidence_score": _safe_round(missed.get("confidence_score"), 4),
        "trade_quality_score": _safe_round(missed.get("trade_quality_score"), 4),
        "available_slots": missed.get("available_slots"),
        "gap_pct": _safe_round(metrics.get("gap_pct"), 6),
        "stock_return_20d": _safe_round(metrics.get("stock_return_20d"), 6),
        "spy_return_20d": _safe_round(metrics.get("spy_return_20d"), 6),
        "excess_spy_return_20d": _safe_round(metrics.get("excess_spy_return_20d"), 6),
        "days_to_earnings": metrics.get("days_to_earnings"),
        "tags": sorted(set(tags)) or ["untagged"],
        "is_platform_rs20_leader": "rs20_leader" in tags,
        "no_gap_up_3pct": no_gap,
        "watch_hypothesis": (
            "missed_platform_rs20_leader_without_signal_day_gap_up"
            if "rs20_leader" in tags and no_gap
            else None
        ),
        "production_impact": _production_impact(),
    }


def _entry_state_metrics(
    *,
    ticker: str,
    as_of: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    features_by_ticker: dict[str, Any],
    earnings_by_ticker: dict[str, Any],
) -> dict[str, Any]:
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    idx = _latest_index_on_or_before(rows, as_of)
    spy_idx = _latest_index_on_or_before(spy_rows, as_of)
    metrics: dict[str, Any] = {}
    if idx is None:
        return metrics
    current = rows[idx]
    previous = rows[idx - 1] if idx > 0 else None
    if previous:
        row_open = _as_float(current.get("open"))
        prev_close = _as_float(previous.get("close"))
        if row_open is not None and prev_close and prev_close > 0:
            metrics["gap_pct"] = (row_open / prev_close) - 1.0

    stock_return = _period_return(rows, idx, 20)
    spy_return = _period_return(spy_rows, spy_idx, 20) if spy_idx is not None else None
    if stock_return is not None:
        metrics["stock_return_20d"] = stock_return
    if spy_return is not None:
        metrics["spy_return_20d"] = spy_return
    if stock_return is not None and spy_return is not None:
        metrics["excess_spy_return_20d"] = stock_return - spy_return

    feature = _case_get(features_by_ticker, ticker) or {}
    earnings = _case_get(earnings_by_ticker, ticker) or {}
    dte = feature.get("days_to_earnings", earnings.get("days_to_earnings"))
    try:
        metrics["days_to_earnings"] = int(dte) if dte is not None else None
    except (TypeError, ValueError):
        metrics["days_to_earnings"] = None
    return metrics


def _normalise_ohlcv_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if hasattr(raw, "reset_index") and hasattr(raw, "to_dict"):
        records = raw.reset_index().to_dict("records")
    elif isinstance(raw, dict) and "rows" in raw:
        records = raw.get("rows") or []
    elif isinstance(raw, list):
        records = raw
    else:
        return []
    rows = []
    for item in records:
        if not isinstance(item, dict):
            continue
        date_value = _date_from_row(item)
        if not date_value:
            continue
        rows.append(
            {
                "date": date_value,
                "open": _as_float(_first_present(item, ("Open", "open"))),
                "high": _as_float(_first_present(item, ("High", "high"))),
                "low": _as_float(_first_present(item, ("Low", "low"))),
                "close": _as_float(_first_present(item, ("Close", "close"))),
                "volume": _as_float(_first_present(item, ("Volume", "volume"))),
            }
        )
    return sorted(rows, key=lambda row: row["date"])


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    out = None
    for idx, row in enumerate(rows):
        if row.get("date") <= as_of:
            out = idx
        else:
            break
    return out


def _period_return(rows: list[dict[str, Any]], idx: int | None, period: int) -> float | None:
    if idx is None or idx < period or idx >= len(rows):
        return None
    close_now = _as_float(rows[idx].get("close"))
    close_then = _as_float(rows[idx - period].get("close"))
    if close_now is None or close_then is None or close_then <= 0:
        return None
    return (close_now / close_then) - 1.0


def _case_get(mapping: dict[str, Any], ticker: str) -> Any:
    if ticker in mapping:
        return mapping[ticker]
    return mapping.get(ticker.upper()) or mapping.get(ticker.lower())


def _date_from_row(row: dict[str, Any]) -> str | None:
    raw = _first_present(row, ("Date", "date", "Datetime", "datetime", "index"))
    if raw is None:
        return None
    if hasattr(raw, "date"):
        return raw.date().isoformat()
    text = str(raw)
    if len(text) >= 10:
        return text[:10]
    return None


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _safe_round(value: Any, digits: int) -> Any:
    out = _as_float(value)
    return round(out, digits) if out is not None else None


def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(candidate.get("asof_date") or ""),
        str(candidate.get("ticker") or ""),
        str(candidate.get("strategy") or ""),
        str(candidate.get("decision") or ""),
    )


def _ledger_keys(path: Path) -> set[tuple[str, str, str, str]]:
    return {_candidate_key(row) for row in _read_ledger_rows(path)}


def _read_ledger_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows
