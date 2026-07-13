"""Append-only candidate-decision ledger for future meta-label training.

This is read-only research infrastructure. It records daily entry-planning
candidate decisions before outcomes are known, then appends fixed-horizon
cash/SPY/QQQ outcomes later against the frozen observation_id.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from us_market_calendar import is_us_equity_session
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from quant.us_market_calendar import is_us_equity_session


SCHEMA_VERSION = 1
RULE_VERSION = "candidate_decision_training_ledger_v1"
SURFACE_CONTRACT = "append_only_candidate_decision_training_ledger"
ENTRY_SEMANTICS = "next_session_open_after_signal_date"
EXIT_SEMANTICS = "fixed_10d_20d_close_observation"
UNIT_NOTIONAL_USD = 10000.0
HORIZONS = (10, 20)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "candidate_decision_training_ledger"
    / "rows.jsonl"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _rounded(value: Any, digits: int = 8) -> float | None:
    parsed = _as_float(value)
    return round(parsed, digits) if parsed is not None else None


def _date10(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else None


def next_session_after(day: str | date | None) -> str | None:
    base = _date10(day)
    if not base:
        return None
    try:
        current = datetime.fromisoformat(base).date()
    except ValueError:
        return None
    cursor = current + timedelta(days=1)
    for _ in range(14):
        if is_us_equity_session(cursor):
            return cursor.isoformat()
        cursor += timedelta(days=1)
    return None


def _hash(payload: Mapping[str, Any], length: int = 24) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def _decision(block: Any) -> dict[str, Any]:
    return dict(block) if isinstance(block, Mapping) else {}


def _candidate_status(row: Mapping[str, Any]) -> str:
    backtest = _decision(row.get("backtest_accounting"))
    reason = str(backtest.get("reason") or "")
    if backtest.get("decision") == "buy":
        return "selected"
    if reason:
        return reason
    return "deferred"


def _row_from_candidate(
    row: Mapping[str, Any],
    *,
    as_of: str,
    rank_fallback: int,
) -> dict[str, Any]:
    entry_date = next_session_after(as_of)
    live = _decision(row.get("live_accounting"))
    backtest = _decision(row.get("backtest_accounting"))
    total = _decision(row.get("total_accounting_shadow"))
    base = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "candidate_decision_snapshot",
        "rule_version": RULE_VERSION,
        "surface_contract": SURFACE_CONTRACT,
        "as_of": as_of,
        "generated_at": utc_now(),
        "trade_enabled": False,
        "rank": int(row.get("rank") or rank_fallback),
        "ticker": str(row.get("ticker") or "").upper(),
        "strategy": row.get("strategy"),
        "sector": row.get("sector"),
        "candidate_status": _candidate_status(row),
        "live_decision": live.get("decision"),
        "live_reason": live.get("reason"),
        "backtest_decision": backtest.get("decision"),
        "backtest_reason": backtest.get("reason"),
        "total_accounting_decision": total.get("decision"),
        "total_accounting_reason": total.get("reason"),
        "operator_review_reason": row.get("operator_review_reason"),
        "entry_semantics": ENTRY_SEMANTICS,
        "exit_semantics": EXIT_SEMANTICS,
        "entry_date": entry_date,
        "entry_date_status": "planned_next_session_open" if entry_date else "unresolved",
        "entry_price": _rounded(row.get("entry_price"), 4),
        "stop_price": _rounded(row.get("stop_price"), 4),
        "target_price": _rounded(row.get("target_price"), 4),
        "risk_reward_ratio": _rounded(row.get("risk_reward_ratio"), 6),
        "trade_quality_score": _rounded(row.get("trade_quality_score"), 6),
        "confidence_score": _rounded(row.get("confidence_score"), 6),
        "days_to_earnings": row.get("days_to_earnings"),
        "shares_to_buy": row.get("shares_to_buy"),
        "position_value_usd": _rounded(row.get("position_value_usd"), 2),
        "unit_notional_usd": UNIT_NOTIONAL_USD,
        "outcome_status": "pending_forward_close",
        "source": "quant.run.entry_candidate_review",
        "production_impact": {
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
        },
    }
    base["target_price_applicability"] = (
        "present_signal_contract" if base["target_price"] is not None else "missing_signal_contract"
    )
    identity = {
        key: base.get(key)
        for key in (
            "as_of",
            "rank",
            "ticker",
            "strategy",
            "entry_price",
            "stop_price",
            "target_price",
            "live_reason",
            "backtest_reason",
        )
    }
    base["observation_id"] = _hash({"rule_version": RULE_VERSION, **identity})
    return base


def build_candidate_decision_training_snapshot(
    *,
    as_of: str,
    entry_candidate_review: Mapping[str, Any] | None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only candidate decision snapshot from daily entry review."""
    candidates = []
    if isinstance(entry_candidate_review, Mapping):
        raw_candidates = entry_candidate_review.get("candidates") or []
        if isinstance(raw_candidates, list):
            candidates = [row for row in raw_candidates if isinstance(row, Mapping)]

    rows = [
        _row_from_candidate(row, as_of=as_of, rank_fallback=index)
        for index, row in enumerate(candidates, start=1)
    ]
    selected_count = sum(1 for row in rows if row.get("candidate_status") == "selected")
    missing_entry = sum(1 for row in rows if not row.get("entry_date"))
    missing_target = sum(1 for row in rows if row.get("target_price") is None)
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "surface_contract": SURFACE_CONTRACT,
        "as_of": as_of,
        "generated_at": utc_now(),
        "trade_enabled": False,
        "candidate_count": len(rows),
        "selected_count": selected_count,
        "entry_date_present_count": len(rows) - missing_entry,
        "entry_date_missing_count": missing_entry,
        "target_price_present_count": len(rows) - missing_target,
        "target_price_missing_count": missing_target,
        "rows": rows,
        "metadata": dict(metadata or {}),
        "production_impact": {
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "daily_snapshot_exposed": True,
            "append_only_forward_observation": True,
            "trade_enabled": False,
        },
    }


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(path: Path, state: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_candidate_decision_training_snapshot(
    snapshot: Mapping[str, Any],
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Append new candidate decision rows without mutating previous rows."""
    path = Path(ledger_path) if ledger_path is not None else DEFAULT_LEDGER_PATH
    state_path = path.with_name("state.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {
        str(row.get("observation_id"))
        for row in _records(path)
        if row.get("record_type") == "candidate_decision_snapshot"
        and row.get("observation_id")
    }
    rows = [dict(row) for row in snapshot.get("rows") or [] if isinstance(row, Mapping)]
    new_rows = [row for row in rows if str(row.get("observation_id") or "") not in existing]
    if new_rows:
        with path.open("a", encoding="utf-8") as handle:
            for row in new_rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    previous_state = _load_state(state_path)
    as_of = _date10(snapshot.get("as_of"))
    last_nonempty_as_of = as_of if rows else previous_state.get("last_nonempty_as_of")
    state = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "surface_contract": SURFACE_CONTRACT,
        "as_of": as_of,
        "last_run_as_of": as_of,
        "generated_at": snapshot.get("generated_at") or utc_now(),
        "trade_enabled": False,
        "candidate_count": int(snapshot.get("candidate_count") or len(rows)),
        "selected_count": int(snapshot.get("selected_count") or 0),
        "rows_seen": len(rows),
        "rows_written": len(new_rows),
        "rows_skipped_duplicate": len(rows) - len(new_rows),
        "last_nonempty_as_of": last_nonempty_as_of,
        "ledger_path": str(path),
        "state_path": str(state_path),
        "production_impact": snapshot.get("production_impact") or {},
    }
    _write_state(state_path, state)
    return {
        "ledger_path": str(path),
        "state_path": str(state_path),
        "rows_seen": len(rows),
        "rows_written": len(new_rows),
        "rows_skipped_duplicate": len(rows) - len(new_rows),
        "state_written": True,
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
    }


def _ohlcv_rows(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if raw is None:
        return out
    if hasattr(raw, "iterrows"):
        for index, row in raw.iterrows():
            date_value = row.get("Date") if hasattr(row, "get") else None
            date_value = date_value if date_value is not None else index
            out.append(
                {
                    "date": _date10(date_value),
                    "open": _as_float(row.get("Open") if hasattr(row, "get") else None),
                    "close": _as_float(row.get("Close") if hasattr(row, "get") else None),
                }
            )
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            out.append(
                {
                    "date": _date10(item.get("date") or item.get("Date")),
                    "open": _as_float(item.get("open") or item.get("Open")),
                    "close": _as_float(item.get("close") or item.get("Close")),
                }
            )
    clean = [
        row for row in out
        if row.get("date") and row.get("open") is not None and row.get("close") is not None
    ]
    clean.sort(key=lambda row: str(row["date"]))
    return clean


def _row_index(rows: list[Mapping[str, Any]], target_date: str) -> int | None:
    for index, row in enumerate(rows):
        if row.get("date") == target_date:
            return index
    return None


def _benchmark_return(rows: list[Mapping[str, Any]], entry_date: str, exit_date: str) -> float | None:
    entry = next((row for row in rows if row.get("date") == entry_date), None)
    exit_ = next((row for row in rows if row.get("date") == exit_date), None)
    if not entry or not exit_:
        return None
    entry_open = _as_float(entry.get("open"))
    exit_close = _as_float(exit_.get("close"))
    if entry_open is None or entry_open <= 0 or exit_close is None:
        return None
    return exit_close / entry_open - 1.0


def _outcome_id(observation_id: str, horizon: int, exit_date: str) -> str:
    return _hash(
        {
            "rule_version": RULE_VERSION,
            "observation_id": observation_id,
            "horizon": horizon,
            "exit_date": exit_date,
        }
    )


def settle_candidate_decision_training_outcomes(
    *,
    ohlcv_by_ticker: Mapping[str, Any],
    as_of: str | None = None,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Append fixed-horizon outcomes for decision rows whose exits are known."""
    path = Path(ledger_path) if ledger_path is not None else DEFAULT_LEDGER_PATH
    state_path = path.with_name("state.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _records(path)
    decisions = [
        row for row in records if row.get("record_type") == "candidate_decision_snapshot"
    ]
    existing_outcomes = {
        str(row.get("outcome_id"))
        for row in records
        if row.get("record_type") == "candidate_decision_outcome" and row.get("outcome_id")
    }
    normalized = {
        str(ticker).upper(): _ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    spy_rows = normalized.get("SPY", [])
    qqq_rows = normalized.get("QQQ", [])
    max_as_of = _date10(as_of) if as_of else None
    new_outcomes: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}

    for decision in decisions:
        ticker = str(decision.get("ticker") or "").upper()
        observation_id = str(decision.get("observation_id") or "")
        entry_date = _date10(decision.get("entry_date"))
        rows = normalized.get(ticker, [])
        if not observation_id or not entry_date:
            skipped["missing_observation_or_entry_date"] = skipped.get("missing_observation_or_entry_date", 0) + 1
            continue
        entry_index = _row_index(rows, entry_date)
        if entry_index is None:
            skipped["missing_ticker_entry_bar"] = skipped.get("missing_ticker_entry_bar", 0) + 1
            continue
        for horizon in HORIZONS:
            exit_index = entry_index + horizon
            if exit_index >= len(rows):
                skipped[f"{horizon}d_not_settled"] = skipped.get(f"{horizon}d_not_settled", 0) + 1
                continue
            exit_row = rows[exit_index]
            exit_date = str(exit_row.get("date") or "")
            if max_as_of and exit_date > max_as_of:
                skipped[f"{horizon}d_exit_after_as_of"] = skipped.get(f"{horizon}d_exit_after_as_of", 0) + 1
                continue
            outcome_id = _outcome_id(observation_id, horizon, exit_date)
            if outcome_id in existing_outcomes:
                skipped["duplicate_outcome"] = skipped.get("duplicate_outcome", 0) + 1
                continue
            entry_open = _as_float(rows[entry_index].get("open"))
            exit_close = _as_float(exit_row.get("close"))
            if entry_open is None or entry_open <= 0 or exit_close is None:
                skipped["missing_candidate_prices"] = skipped.get("missing_candidate_prices", 0) + 1
                continue
            candidate_return = exit_close / entry_open - 1.0
            spy_return = _benchmark_return(spy_rows, entry_date, exit_date)
            qqq_return = _benchmark_return(qqq_rows, entry_date, exit_date)
            if spy_return is None or qqq_return is None:
                skipped["missing_benchmark_prices"] = skipped.get("missing_benchmark_prices", 0) + 1
                continue
            new_outcomes.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "candidate_decision_outcome",
                    "rule_version": RULE_VERSION,
                    "surface_contract": SURFACE_CONTRACT,
                    "outcome_id": outcome_id,
                    "observation_id": observation_id,
                    "as_of": max_as_of,
                    "generated_at": utc_now(),
                    "ticker": ticker,
                    "strategy": decision.get("strategy"),
                    "candidate_status": decision.get("candidate_status"),
                    "horizon": f"{horizon}d",
                    "horizon_trading_days": horizon,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_open": round(entry_open, 4),
                    "exit_close": round(exit_close, 4),
                    "candidate_return_pct": round(candidate_return, 8),
                    "spy_return_pct": round(spy_return, 8),
                    "qqq_return_pct": round(qqq_return, 8),
                    "replacement_value_vs_cash_usd": round(UNIT_NOTIONAL_USD * candidate_return, 2),
                    "replacement_value_vs_spy_usd": round(UNIT_NOTIONAL_USD * (candidate_return - spy_return), 2),
                    "replacement_value_vs_qqq_usd": round(UNIT_NOTIONAL_USD * (candidate_return - qqq_return), 2),
                    "label_positive_cash": candidate_return > 0,
                    "label_positive_spy": candidate_return > spy_return,
                    "label_positive_qqq": candidate_return > qqq_return,
                    "label_source": "fixed_horizon_daily_ohlcv_next_open_entry",
                    "oracle_label_used": False,
                    "trade_enabled": False,
                }
            )
            existing_outcomes.add(outcome_id)

    if new_outcomes:
        with path.open("a", encoding="utf-8") as handle:
            for row in new_outcomes:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    previous_state = _load_state(state_path)
    state = {
        **previous_state,
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "surface_contract": SURFACE_CONTRACT,
        "last_settlement_as_of": max_as_of,
        "outcome_rows_written": len(new_outcomes),
        "settlement_skip_reasons": skipped,
        "ledger_path": str(path),
        "state_path": str(state_path),
        "trade_enabled": False,
    }
    _write_state(state_path, state)
    return {
        "ledger_path": str(path),
        "state_path": str(state_path),
        "decision_rows_seen": len(decisions),
        "outcome_rows_written": len(new_outcomes),
        "settlement_skip_reasons": skipped,
        "state_written": True,
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
    }
