"""Default-off SEC 10-K liquidity forward watch.

This module records PIT-safe, liquidity-qualified 10-K filing candidates for
forward observation. It does not rank candidates, size positions, consume slots,
or emit orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
WATCH_NAME = "SEC_10K_LIQUIDITY_FORWARD_WATCH"
RULE_VERSION = "sec_10k_liquidity_v1"
MIN_AVG_DOLLAR_VOLUME_20D = 5_000_000
ADV_GE_20M = 20_000_000
ADV_LOOKBACK_DAYS = 20
MIN_ADV_OBSERVATIONS = 20

DEFAULT_LEDGER_PATH = Path("data/sec_10k_liquidity_forward_watch.jsonl")
DEFAULT_SUMMARY_PATH = Path("data/sec_10k_liquidity_forward_watch_summary.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_sec_10k_forward_watch(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "watch_name": WATCH_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "trade_enabled": False,
        "sec_event_count": 0,
        "ten_k_event_count": 0,
        "pit_safe_10k_count": 0,
        "outside_universe_10k_count": 0,
        "ohlcv_covered_10k_count": 0,
        "liquidity_qualified_count": 0,
        "candidate_count": 0,
        "candidates": [],
        "all_10k_rows": [],
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
    }


def load_sec_filing_events(source_path: Path | str | None) -> list[dict[str, Any]]:
    if not source_path:
        return []
    path = Path(source_path)
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


def build_sec_10k_forward_watch(
    *,
    as_of: str,
    sec_filing_events: list[dict[str, Any]] | None = None,
    source_path: Path | str | None = None,
    ohlcv_by_ticker: dict[str, Any] | None,
    current_universe: set[str] | list[str] | tuple[str, ...] | None = None,
    core_signals: list[dict[str, Any]] | None = None,
    entry_execution_plan: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
    include_current_universe: bool = False,
    min_avg_dollar_volume_20d: float = MIN_AVG_DOLLAR_VOLUME_20D,
    min_adv_observations: int = MIN_ADV_OBSERVATIONS,
) -> dict[str, Any]:
    """Build a same-day 10-K liquidity watch snapshot from SEC event rows."""
    as_of_date = str(as_of)[:10]
    generated_at = generated_at or datetime.now(timezone.utc)
    if sec_filing_events is None:
        sec_filing_events = load_sec_filing_events(source_path)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = {str(ticker).upper() for ticker in (current_universe or set())}
    alternatives = _same_day_core_alternatives(core_signals or [], entry_execution_plan or {})

    all_10k_rows = []
    candidates = []
    for event in sec_filing_events or []:
        if not _is_10k(event):
            continue
        row = _watch_row(
            event=event,
            as_of=as_of_date,
            rows_by_ticker=rows_by_ticker,
            universe=universe,
            same_day_core_alternatives=alternatives,
            include_current_universe=include_current_universe,
            min_avg_dollar_volume_20d=min_avg_dollar_volume_20d,
            min_adv_observations=min_adv_observations,
        )
        all_10k_rows.append(row)
        if row["eligible"]:
            candidate = dict(row)
            candidate["watch_rank"] = len(candidates) + 1
            candidates.append(candidate)

    by_status = Counter(row["eligibility_status"] for row in all_10k_rows)
    by_bucket = Counter(row["liquidity_bucket"] for row in all_10k_rows)
    by_ticker = Counter(row["ticker"] for row in candidates)
    pit_safe_rows = [row for row in all_10k_rows if row.get("pit_safe_flag") is True]
    outside_rows = [row for row in all_10k_rows if not row.get("in_current_universe")]
    covered_rows = [row for row in all_10k_rows if row.get("avg_dollar_volume_20d") is not None]
    qualified_rows = [row for row in all_10k_rows if row.get("liquidity_qualified")]

    return {
        "schema_version": SCHEMA_VERSION,
        "watch_name": WATCH_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "enabled": False,
        "trade_enabled": False,
        "sec_event_count": len(sec_filing_events or []),
        "ten_k_event_count": len(all_10k_rows),
        "pit_safe_10k_count": len(pit_safe_rows),
        "outside_universe_10k_count": len(outside_rows),
        "ohlcv_covered_10k_count": len(covered_rows),
        "liquidity_qualified_count": len(qualified_rows),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "all_10k_rows": all_10k_rows,
        "summary": {
            "by_status": dict(sorted(by_status.items())),
            "by_liquidity_bucket": dict(sorted(by_bucket.items())),
            "candidate_by_ticker": dict(sorted(by_ticker.items())),
            "same_day_core_alternative_count": len(alternatives),
        },
        "parameters": {
            "forms": ["10-K"],
            "include_current_universe": include_current_universe,
            "min_avg_dollar_volume_20d": min_avg_dollar_volume_20d,
            "adv_lookback_days": ADV_LOOKBACK_DAYS,
            "min_adv_observations": min_adv_observations,
            "forward_gate_min_closed_candidates": 30,
            "forward_gate_min_positive_regimes": 2,
            "forward_gate_metric": "10d_excess_return_and_same_day_replacement_value",
        },
        "data_source": {
            "status": "loaded",
            "source_path": str(source_path) if source_path else None,
            "source": "sec_filing_events jsonl plus same-day OHLCV",
        },
        "production_impact": _production_impact(),
    }


def persist_sec_10k_forward_watch(
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
    history_by_bucket = Counter(str(row.get("liquidity_bucket") or "") for row in history)
    out = {
        "schema_version": SCHEMA_VERSION,
        "watch_name": WATCH_NAME,
        "rule_version": RULE_VERSION,
        "updated_at": utc_now_iso(),
        "asof_date": snapshot.get("asof_date"),
        "candidate_count": snapshot.get("candidate_count", 0),
        "ten_k_event_count": snapshot.get("ten_k_event_count", 0),
        "pit_safe_10k_count": snapshot.get("pit_safe_10k_count", 0),
        "outside_universe_10k_count": snapshot.get("outside_universe_10k_count", 0),
        "ohlcv_covered_10k_count": snapshot.get("ohlcv_covered_10k_count", 0),
        "liquidity_qualified_count": snapshot.get("liquidity_qualified_count", 0),
        "appended_count": appended,
        "ledger_row_count": len(history),
        "ledger_path": str(ledger),
        "summary_path": str(summary),
        "history_by_ticker": dict(sorted(history_by_ticker.items())),
        "history_by_liquidity_bucket": dict(sorted(history_by_bucket.items())),
        "candidates": snapshot.get("candidates") or [],
        "production_impact": _production_impact(),
    }
    with summary.open("w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {**snapshot, "persistence": out}


def _watch_row(
    *,
    event: dict[str, Any],
    as_of: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    universe: set[str],
    same_day_core_alternatives: list[dict[str, Any]],
    include_current_universe: bool,
    min_avg_dollar_volume_20d: float,
    min_adv_observations: int,
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    usable_trade_date = str(event.get("usable_trade_date") or event.get("filing_date") or as_of)[:10]
    in_current_universe = ticker in universe if universe else bool(event.get("in_current_universe", False))
    metrics = _liquidity_metrics(
        ticker=ticker,
        usable_trade_date=usable_trade_date,
        rows_by_ticker=rows_by_ticker,
    )
    pit_safe = event.get("pit_safe_flag") is True
    is_amendment = bool(event.get("is_amendment"))
    liquidity_qualified = (
        metrics.get("avg_dollar_volume_20d") is not None
        and metrics.get("adv_observation_count", 0) >= min_adv_observations
        and metrics["avg_dollar_volume_20d"] >= min_avg_dollar_volume_20d
    )
    status = _eligibility_status(
        ticker=ticker,
        pit_safe=pit_safe,
        is_amendment=is_amendment,
        in_current_universe=in_current_universe,
        include_current_universe=include_current_universe,
        metrics=metrics,
        liquidity_qualified=liquidity_qualified,
        min_adv_observations=min_adv_observations,
    )
    eligible = status == "eligible"
    return {
        "asof_date": as_of,
        "usable_trade_date": usable_trade_date,
        "ticker": ticker,
        "cik": event.get("cik"),
        "accession_number": event.get("accession_number"),
        "form_type": event.get("form_type"),
        "form_base": event.get("form_base"),
        "filing_date": str(event.get("filing_date") or "")[:10] or None,
        "accepted_at": event.get("accepted_at"),
        "archive_url": event.get("archive_url"),
        "pit_safe_flag": pit_safe,
        "pit_source": event.get("pit_source"),
        "is_amendment": is_amendment,
        "in_current_universe": in_current_universe,
        "avg_dollar_volume_20d": _safe_round(metrics.get("avg_dollar_volume_20d"), 2),
        "adv_observation_count": metrics.get("adv_observation_count", 0),
        "liquidity_bucket": liquidity_bucket(metrics.get("avg_dollar_volume_20d")),
        "liquidity_qualified": liquidity_qualified,
        "eligible": eligible,
        "eligibility_status": status,
        "same_day_core_alternative_count": len(same_day_core_alternatives),
        "same_day_core_alternatives": same_day_core_alternatives[:10],
        "watch_hypothesis": (
            "outside_universe_10k_liquidity_qualified_candidate_pool_expansion"
            if eligible
            else None
        ),
        "production_impact": _production_impact(),
    }


def liquidity_bucket(avg_dollar_volume: float | None) -> str:
    if avg_dollar_volume is None:
        return "adv_unknown"
    if avg_dollar_volume >= ADV_GE_20M:
        return "adv_ge_20m"
    if avg_dollar_volume >= MIN_AVG_DOLLAR_VOLUME_20D:
        return "adv_5m_20m"
    return "adv_lt_5m"


def _eligibility_status(
    *,
    ticker: str,
    pit_safe: bool,
    is_amendment: bool,
    in_current_universe: bool,
    include_current_universe: bool,
    metrics: dict[str, Any],
    liquidity_qualified: bool,
    min_adv_observations: int,
) -> str:
    if not ticker:
        return "missing_ticker"
    if not pit_safe:
        return "not_pit_safe"
    if is_amendment:
        return "amendment_excluded"
    if in_current_universe and not include_current_universe:
        return "current_universe_excluded"
    if metrics.get("avg_dollar_volume_20d") is None:
        return "missing_ohlcv"
    if metrics.get("adv_observation_count", 0) < min_adv_observations:
        return "insufficient_adv_history"
    if not liquidity_qualified:
        return "low_liquidity"
    return "eligible"


def _liquidity_metrics(
    *,
    ticker: str,
    usable_trade_date: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows = rows_by_ticker.get(ticker) or []
    idx = _latest_index_before(rows, usable_trade_date)
    if idx is None:
        return {"avg_dollar_volume_20d": None, "adv_observation_count": 0}
    start = max(0, idx - ADV_LOOKBACK_DAYS + 1)
    values = []
    for row in rows[start : idx + 1]:
        close = _as_float(row.get("close"))
        volume = _as_float(row.get("volume"))
        if close is None or volume is None:
            continue
        values.append(close * volume)
    if not values:
        return {"avg_dollar_volume_20d": None, "adv_observation_count": 0}
    return {
        "avg_dollar_volume_20d": sum(values) / len(values),
        "adv_observation_count": len(values),
    }


def _same_day_core_alternatives(
    core_signals: list[dict[str, Any]],
    entry_execution_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for rank, signal in enumerate(core_signals or [], start=1):
        if not isinstance(signal, dict):
            continue
        rows.append(_compact_signal(signal, rank=rank, source="selected_core_signal"))
    for signal in entry_execution_plan.get("deferred_breakout_signals") or []:
        rows.append(_compact_signal(signal, rank=signal.get("candidate_rank"), source="deferred_breakout_signal"))
    for rank, signal in enumerate(entry_execution_plan.get("slot_sliced_signals") or [], start=1):
        rows.append(_compact_signal(signal, rank=signal.get("candidate_rank", rank), source="slot_sliced_signal"))
    return [row for row in rows if row.get("ticker")]


def _compact_signal(signal: dict[str, Any], *, rank: Any, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "rank": rank,
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": signal.get("strategy"),
        "action": signal.get("action"),
        "sector": signal.get("sector"),
        "entry_price": _safe_round(signal.get("entry_price"), 4),
        "confidence_score": _safe_round(signal.get("confidence_score"), 4),
        "trade_quality_score": _safe_round(signal.get("trade_quality_score"), 4),
    }


def _is_10k(event: dict[str, Any]) -> bool:
    form = str(event.get("form_base") or event.get("form_type") or "").upper()
    return form == "10-K" or form.startswith("10-K")


def _normalise_ohlcv_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if hasattr(raw, "reset_index") and hasattr(raw, "to_dict"):
        records = raw.reset_index().to_dict("records")
    elif isinstance(raw, dict) and "rows" in raw:
        records = raw.get("rows") or []
    elif isinstance(raw, dict) and "data" in raw:
        records = raw.get("data") or []
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


def _latest_index_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    out = None
    for idx, row in enumerate(rows):
        if row.get("date") < as_of:
            out = idx
        else:
            break
    return out


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
        str(candidate.get("usable_trade_date") or candidate.get("asof_date") or ""),
        str(candidate.get("ticker") or ""),
        str(candidate.get("accession_number") or candidate.get("archive_url") or ""),
        str(candidate.get("rule_version") or RULE_VERSION),
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
