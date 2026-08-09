"""Daily live-vs-model drift reconciliation for the real-money book (exp-20260706-019).

Contract: docs/live_drift_reconciliation.md. For every long position in
operator_inputs/open_positions.json this builds one ledger row comparing the
moomoo-realized state against the backtest fill model's expectation for the
same (ticker, entry_date):

  fill_drift_pct       = avg_cost / modeled_entry_price - 1      (paid more?)
  realized_return_pct  = (market_val/shares) / avg_cost - 1      (moomoo mark)
  modeled_return_pct   = close_asof / modeled_entry_price - 1    (model mark)
  trajectory_drift_pct = realized - modeled                      (cumulative gap)

Observe-only: reads positions and OHLCV, writes data/live_pilot/live_drift/,
never touches orders, ranking, sizing, or exits. Exit-side reconciliation
(closed trades) is v2, gated on a materialized moomoo deal-history surface —
see the doc's reopen condition.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from data_paths import DATA_ROOT, atomic_write_json
    from fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage
    from open_position_schema import (
        CORE_STRATEGY_POSITION_TAGS,
        account_positions,
        position_consumes_core_slot,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.data_paths import DATA_ROOT, atomic_write_json
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, apply_slippage
    from quant.open_position_schema import (
        CORE_STRATEGY_POSITION_TAGS,
        account_positions,
        position_consumes_core_slot,
    )

RULE_VERSION = "live_drift_reconciliation_v4"

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS_PATH = REPO_ROOT / "operator_inputs" / "open_positions.json"
DEFAULT_SURFACE_DIR = DATA_ROOT / "live_pilot" / "live_drift"
DEFAULT_LEDGER_PATH = DEFAULT_SURFACE_DIR / "ledger.jsonl"
DEFAULT_STATE_PATH = DEFAULT_SURFACE_DIR / "state.json"
DEFAULT_ORDER_SNAPSHOTS_PATH = (
    DATA_ROOT / "live_pilot" / "broker_execution" / "order_snapshots.jsonl"
)
DEFAULT_QUANT_SIGNALS_DIR = DATA_ROOT / "daily" / "signals" / "quant"
WAREHOUSE_PATHS = (
    DATA_ROOT / "warehouse" / "warehouse_main_hot.sqlite",
    DATA_ROOT / "warehouse" / "warehouse_main.sqlite",
    DATA_ROOT / "tmp" / "warehouse_main_alpha_search_readcopy.sqlite",
)

# Alert thresholds (docs/live_drift_reconciliation.md): core-bucket notional-
# weighted trajectory drift below -1.5% for 10 consecutive sessions, or mean
# fill drift above +30bp, counts as an execution/model drift event.
ALERT_TRAJECTORY_DRIFT_PCT = -0.015
ALERT_CONSECUTIVE_SESSIONS = 10
ALERT_MEAN_FILL_DRIFT_PCT = 0.003

# moomoo avg_cost is the blended cost across ALL fills while entry_date is the
# FIRST fill's date, so a scaled-into position shows a huge fake "fill drift"
# vs the first session's open (observed +38% on legacy adds, first live run
# 2026-07-06). Rows beyond this threshold are flagged suspect_multi_fill and
# excluded from bucket aggregates and alerts.
SUSPECT_FILL_DRIFT_PCT = 0.10

_DISCRETIONARY_MARKERS = {"legacy", "manual", "discretionary", "operator", ""}
_STRATEGY_PROVENANCE_FIELDS = (
    "opened_by_strategy",
    "strategy",
    "entry_strategy",
    "source_strategy",
)
_LEGACY_ALERT_RULE_VERSIONS = {
    "live_drift_reconciliation_v1",
    "live_drift_reconciliation_v2",
    "live_drift_reconciliation_v3",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _round(value: Any, digits: int) -> float | None:
    out = _float_or_none(value)
    return round(out, digits) if out is not None else None


def strategy_bucket(position: dict[str, Any]) -> str:
    if position_consumes_core_slot(position, position.get("position_group")):
        return "core"
    sleeve = str(position.get("sleeve") or "").strip().lower()
    opened_by = str(position.get("opened_by_strategy") or "").strip().lower()
    if sleeve in ("discretionary",) or opened_by in _DISCRETIONARY_MARKERS:
        return "discretionary_legacy"
    return "sleeve"


def _entry_strategy_provenance(position: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return the first explicit strategy tag and its source field."""
    for field in _STRATEGY_PROVENANCE_FIELDS:
        value = position.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip().lower(), field
    return None, None


def _static_execution_alert_metadata(position: dict[str, Any]) -> dict[str, Any]:
    provenance, provenance_field = _entry_strategy_provenance(position)
    bucket = strategy_bucket(position)
    if bucket != "core":
        exclusion_reason = "non_core_exposure"
    elif provenance not in CORE_STRATEGY_POSITION_TAGS:
        exclusion_reason = "entry_not_attributable_to_core_policy"
    else:
        exclusion_reason = "broker_entry_evidence_missing"
    return {
        "entry_strategy_provenance": provenance,
        "entry_strategy_provenance_field": provenance_field,
        "broker_entry_evidence_status": "not_evaluated",
        "policy_decision_evidence_status": "not_evaluated",
        "core_execution_alert_eligible": False,
        "core_execution_alert_exclusion_reason": exclusion_reason,
        "alert_eligibility_contract": RULE_VERSION,
    }


def _latest_order_facts(order_snapshots: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Return the latest canonical fact per order id, failing closed on bad rows."""
    latest: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, record in enumerate(order_snapshots):
        if not isinstance(record, dict) or record.get("record_type") != "broker_order_snapshot":
            return [], "broker_order_snapshots_malformed"
        fact = record.get("fact")
        order_id = fact.get("order_id") if isinstance(fact, dict) else None
        if not isinstance(order_id, str) or not order_id.strip():
            return [], "broker_order_snapshots_malformed"
        sequence = record.get("ledger_sequence")
        sequence_key = int(sequence) if isinstance(sequence, int) else index
        previous = latest.get(order_id)
        if previous is None or sequence_key >= previous[0]:
            latest[order_id] = (sequence_key, fact)
    return [item[1] for item in latest.values()], None


def _broker_entry_evidence(
    position: dict[str, Any],
    entry_market_session_date: str | None,
    order_snapshots: list[dict[str, Any]] | None,
    source_error: str | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "broker_entry_evidence_status": "broker_entry_evidence_missing",
        "broker_entry_order_ids": [],
        "broker_entry_filled_qty": 0.0,
        "broker_entry_sessions": [],
        "broker_entry_fill_outside_rth": [],
    }
    if source_error:
        result["broker_entry_evidence_status"] = source_error
        return result
    if order_snapshots is None:
        return result
    if entry_market_session_date is None:
        result["broker_entry_evidence_status"] = "entry_market_session_unavailable"
        return result
    facts, malformed = _latest_order_facts(order_snapshots)
    if malformed:
        result["broker_entry_evidence_status"] = malformed
        return result

    ticker = str(position.get("ticker") or "").upper()
    matching: list[dict[str, Any]] = []
    for fact in facts:
        create_date = str(fact.get("create_time") or "")[:10]
        dealt_qty = _float_or_none(fact.get("dealt_qty"))
        if (
            str(fact.get("ticker") or "").upper() == ticker
            and str(fact.get("trd_side") or "").upper() == "BUY"
            and create_date == entry_market_session_date
            and dealt_qty is not None
            and dealt_qty > 0
        ):
            matching.append(fact)
    if not matching:
        result["broker_entry_evidence_status"] = "matching_entry_buy_fill_missing"
        return result

    sessions = [str(fact.get("session") or "").upper() for fact in matching]
    outside = [fact.get("fill_outside_rth") for fact in matching]
    order_ids = [str(fact.get("order_id")) for fact in matching]
    filled_qty = sum(_float_or_none(fact.get("dealt_qty")) or 0.0 for fact in matching)
    result.update(
        {
            "broker_entry_order_ids": sorted(order_ids),
            "broker_entry_filled_qty": round(filled_qty, 8),
            "broker_entry_sessions": sorted(set(sessions)),
            "broker_entry_fill_outside_rth": sorted(set(outside), key=str),
        }
    )
    if any(session not in {"RTH", "ALL"} for session in sessions) or any(
        flag is not False for flag in outside
    ):
        result["broker_entry_evidence_status"] = "outside_regular_session_fill"
        return result
    shares = _float_or_none(position.get("shares"))
    if shares is None or shares <= 0 or filled_qty + 1e-8 < shares:
        result["broker_entry_evidence_status"] = "entry_fill_quantity_not_covered"
        return result
    result["broker_entry_evidence_status"] = "verified_regular_session_fill"
    return result


def _next_session_timing(signal: dict[str, Any]) -> bool:
    explicit = {
        str(signal.get(field) or "").strip().lower()
        for field in ("fill_timing", "entry_timing", "intended_entry_timing")
    }
    if explicit & {"next_session_open", "next-day open", "next_day_open"}:
        return True
    note = str(signal.get("entry_note") or "").strip().lower()
    return "next-day open" in note or "next session open" in note


def _executable_signal(signal: dict[str, Any]) -> bool:
    sizing = signal.get("sizing")
    shares = sizing.get("shares_to_buy") if isinstance(sizing, dict) else None
    if shares is None:
        shares = signal.get("shares_to_buy")
    quantity = _float_or_none(shares)
    return quantity is not None and quantity > 0


def _policy_decision_evidence(
    position: dict[str, Any],
    prior_market_session_date: str | None,
    quant_signals_fn: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "policy_decision_evidence_status": "policy_decision_snapshot_missing",
        "policy_decision_date": prior_market_session_date,
        "policy_decision_scope": "top_level_signals_final",
    }
    if prior_market_session_date is None:
        result["policy_decision_evidence_status"] = "prior_market_session_unavailable"
        return result
    if quant_signals_fn is None:
        return result
    try:
        payload = quant_signals_fn(prior_market_session_date)
    except Exception:
        result["policy_decision_evidence_status"] = "policy_decision_snapshot_malformed"
        return result
    if payload is None:
        return result
    signals = payload.get("signals") if isinstance(payload, dict) else None
    if not isinstance(signals, list) or any(not isinstance(item, dict) for item in signals):
        result["policy_decision_evidence_status"] = "policy_decision_snapshot_malformed"
        return result
    ticker = str(position.get("ticker") or "").upper()
    provenance, _ = _entry_strategy_provenance(position)
    ticker_matches = [
        signal for signal in signals if str(signal.get("ticker") or "").upper() == ticker
    ]
    if not ticker_matches:
        result["policy_decision_evidence_status"] = "matching_top_level_signal_missing"
        return result
    strategy_matches = [
        signal
        for signal in ticker_matches
        if str(signal.get("strategy") or "").strip().lower() == provenance
    ]
    if not strategy_matches:
        result["policy_decision_evidence_status"] = "top_level_signal_strategy_mismatch"
        return result
    executable = [signal for signal in strategy_matches if _executable_signal(signal)]
    if not executable:
        result["policy_decision_evidence_status"] = "top_level_signal_not_executable"
        return result
    timed = [signal for signal in executable if _next_session_timing(signal)]
    if not timed:
        result["policy_decision_evidence_status"] = "top_level_signal_not_next_session_open"
        return result
    result["policy_decision_evidence_status"] = "verified_prior_next_session_top_level_signal"
    result["policy_decision_strategy"] = provenance
    return result


def _execution_alert_metadata(
    position: dict[str, Any],
    *,
    entry_market_session_date: str | None = None,
    prior_market_session_date: str | None = None,
    order_snapshots: list[dict[str, Any]] | None = None,
    order_source_error: str | None = None,
    quant_signals_fn: Any = None,
) -> dict[str, Any]:
    metadata = _static_execution_alert_metadata(position)
    bucket = strategy_bucket(position)
    provenance, _ = _entry_strategy_provenance(position)
    if bucket != "core" or provenance not in CORE_STRATEGY_POSITION_TAGS:
        return metadata
    broker = _broker_entry_evidence(
        position, entry_market_session_date, order_snapshots, order_source_error
    )
    policy = _policy_decision_evidence(
        position, prior_market_session_date, quant_signals_fn
    )
    metadata.update(broker)
    metadata.update(policy)
    broker_ok = broker["broker_entry_evidence_status"] == "verified_regular_session_fill"
    policy_ok = (
        policy["policy_decision_evidence_status"]
        == "verified_prior_next_session_top_level_signal"
    )
    metadata["core_execution_alert_eligible"] = broker_ok and policy_ok
    if broker_ok and policy_ok:
        metadata["core_execution_alert_exclusion_reason"] = None
    elif not broker_ok:
        metadata["core_execution_alert_exclusion_reason"] = broker[
            "broker_entry_evidence_status"
        ]
    else:
        metadata["core_execution_alert_exclusion_reason"] = policy[
            "policy_decision_evidence_status"
        ]
    return metadata


def _position_id_key(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    key = str(value).strip()
    return key or None


def _row_execution_alert_eligible(row: dict[str, Any]) -> bool:
    """Require v4's full broker + prior-policy evidence, including legacy copies."""
    return (
        row.get("alert_eligibility_contract") == RULE_VERSION
        and row.get("core_execution_alert_eligible") is True
        and row.get("broker_entry_evidence_status") == "verified_regular_session_fill"
        and row.get("policy_decision_evidence_status")
        == "verified_prior_next_session_top_level_signal"
    )


def _row_market_session_date(row: dict[str, Any]) -> str | None:
    value = row.get("market_session_date") or row.get("asof_date")
    if not isinstance(value, str) or len(value) < 10:
        return None
    return value[:10]


def _alert_row_key(row: dict[str, Any]) -> tuple[str | None, str | None]:
    position_key = _position_id_key(row.get("position_id"))
    if position_key is None:
        position_key = str(row.get("ticker") or "").upper() or None
    return _row_market_session_date(row), position_key


def _overlay_current_rows(
    history: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay today's fresh rows for alerting without mutating append-only history."""
    current_keys = {_alert_row_key(row) for row in current_rows}
    overlaid = [
        dict(row)
        for row in history
        if _alert_row_key(row) not in current_keys
    ]
    overlaid.extend(dict(row) for row in current_rows)
    return overlaid


def _enrich_legacy_alert_rows(
    rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    market_sessions_by_ticker: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Enrich legacy alert copies from current v4 evidence, never the ledger."""
    metadata_by_position_id: dict[str, dict[str, Any]] = {}
    ambiguous_ids: set[str] = set()
    for row in current_rows:
        if not isinstance(row, dict):
            continue
        position_id = _position_id_key(row.get("position_id"))
        if position_id is None:
            continue
        metadata = {
            key: value
            for key, value in row.items()
            if key.startswith("entry_strategy_")
            or key.startswith("broker_entry_")
            or key.startswith("policy_decision_")
            or key in {
                "core_execution_alert_eligible",
                "core_execution_alert_exclusion_reason",
                "alert_eligibility_contract",
            }
        }
        previous = metadata_by_position_id.get(position_id)
        if previous is not None and previous != metadata:
            ambiguous_ids.add(position_id)
            continue
        metadata_by_position_id[position_id] = metadata

    for position_id in ambiguous_ids:
        metadata_by_position_id[position_id] = {
            "entry_strategy_provenance": None,
            "entry_strategy_provenance_field": "ambiguous_current_position_id",
            "broker_entry_evidence_status": "ambiguous_current_position_id",
            "policy_decision_evidence_status": "ambiguous_current_position_id",
            "core_execution_alert_eligible": False,
            "core_execution_alert_exclusion_reason": "ambiguous_current_position_id",
            "alert_eligibility_contract": RULE_VERSION,
        }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        alert_row = dict(row)
        if (
            alert_row.get("rule_version") in _LEGACY_ALERT_RULE_VERSIONS
        ):
            position_id = _position_id_key(alert_row.get("position_id"))
            metadata = metadata_by_position_id.get(position_id) if position_id else None
            if metadata is not None:
                alert_row.update(metadata)
                ticker = str(alert_row.get("ticker") or "").upper()
                legacy_asof = str(alert_row.get("asof_date") or "")[:10]
                canonical_sessions = (market_sessions_by_ticker or {}).get(ticker, [])
                completed = [day for day in canonical_sessions if day <= legacy_asof]
                if completed:
                    alert_row["market_session_date"] = completed[-1]
                    alert_row["market_session_date_source"] = (
                        "canonical_bars_in_memory_legacy_remap"
                    )
        enriched.append(alert_row)
    return enriched


def _load_order_snapshots(path: Path | str) -> tuple[list[dict[str, Any]], str | None]:
    source = Path(path)
    if not source.exists():
        return [], "broker_order_snapshots_missing"
    rows: list[dict[str, Any]] = []
    try:
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    return [], "broker_order_snapshots_malformed"
                rows.append(record)
    except (OSError, json.JSONDecodeError):
        return [], "broker_order_snapshots_malformed"
    if not rows:
        return [], "broker_order_snapshots_missing"
    _, malformed = _latest_order_facts(rows)
    return (rows, malformed)


def _load_quant_signals_snapshot(
    decision_date: str,
    directory: Path | str = DEFAULT_QUANT_SIGNALS_DIR,
) -> dict[str, Any] | None:
    path = Path(directory) / f"quant_signals_{decision_date.replace('-', '')}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("quant signals snapshot must be an object")
    return payload


def _bars_from_warehouse(ticker: str) -> list[dict[str, Any]]:
    last_error = None
    for path in WAREHOUSE_PATHS:
        if not path.exists():
            continue
        try:
            con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
            try:
                rows = con.execute(
                    "select date, open, close from ohlcv where ticker=? order by date",
                    (str(ticker).upper(),),
                ).fetchall()
            finally:
                con.close()
            if rows:
                return [{"date": r[0], "open": r[1], "close": r[2]} for r in rows]
        except sqlite3.OperationalError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise RuntimeError(f"warehouse unavailable: {last_error}")
    return []


def reconcile_position(
    position: dict[str, Any],
    bars: list[dict[str, Any]],
    as_of: str,
    *,
    order_snapshots: list[dict[str, Any]] | None = None,
    order_source_error: str | None = None,
    quant_signals_fn: Any = None,
) -> dict[str, Any]:
    """One ledger row for one long position; fail-safe with a reason."""
    ticker = str(position.get("ticker") or "").upper()
    row: dict[str, Any] = {
        "asof_date": str(as_of)[:10],
        "position_id": position.get("position_id"),
        "ticker": ticker,
        "strategy_bucket": strategy_bucket(position),
        "entry_date": str(position.get("entry_date") or "")[:10] or None,
        "shares": _float_or_none(position.get("shares")),
        "avg_cost": _float_or_none(position.get("avg_cost")),
        "market_val": _float_or_none(position.get("market_val")),
        "unrealized_pl": _float_or_none(position.get("unrealized_pl")),
        "rule_version": RULE_VERSION,
        "reconcilable": False,
        "reason": None,
    }
    row.update(_static_execution_alert_metadata(position))

    by_date = {
        str(bar.get("date") or "")[:10]: bar
        for bar in bars
        if isinstance(bar, dict) and len(str(bar.get("date") or "")) >= 10
    }
    dates = sorted(by_date)
    asof_dates = [date for date in dates if date <= row["asof_date"]]
    row["market_session_date"] = asof_dates[-1] if asof_dates else None
    entry_market_session_date = None
    if row["entry_date"]:
        entry_market_session_date = row["entry_date"] if row["entry_date"] in by_date else None
        if entry_market_session_date is None:
            later = [date for date in dates if date >= row["entry_date"]]
            entry_market_session_date = later[0] if later else None
    row["entry_market_session_date"] = entry_market_session_date
    prior_dates = [
        date
        for date in dates
        if entry_market_session_date is not None and date < entry_market_session_date
    ]
    prior_market_session_date = prior_dates[-1] if prior_dates else None
    row.update(
        _execution_alert_metadata(
            position,
            entry_market_session_date=entry_market_session_date,
            prior_market_session_date=prior_market_session_date,
            order_snapshots=order_snapshots,
            order_source_error=order_source_error,
            quant_signals_fn=quant_signals_fn,
        )
    )
    if str(position.get("direction") or "long").lower() != "long":
        row["reason"] = "non_long_direction_v2"
        return row
    if not row["entry_date"]:
        row["reason"] = "missing_entry_date"
        return row
    if row["avg_cost"] is None or row["avg_cost"] <= 0 or not row["shares"]:
        row["reason"] = "missing_cost_basis"
        return row

    entry_bar = by_date.get(entry_market_session_date) if entry_market_session_date else None
    entry_open = _float_or_none(entry_bar.get("open")) if entry_bar else None
    if entry_open is None or entry_open <= 0:
        row["reason"] = "missing_entry_bar"
        return row
    close_asof = _float_or_none(by_date[asof_dates[-1]].get("close")) if asof_dates else None
    if close_asof is None or close_asof <= 0:
        row["reason"] = "missing_asof_close"
        return row

    modeled_entry = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "buy")
    realized_mark = (
        row["market_val"] / row["shares"]
        if row["market_val"] is not None and row["shares"]
        else None
    )
    if realized_mark is None or realized_mark <= 0:
        row["reason"] = "missing_market_val"
        return row

    fill_drift = row["avg_cost"] / modeled_entry - 1.0
    realized_return = realized_mark / row["avg_cost"] - 1.0
    modeled_return = close_asof / modeled_entry - 1.0
    row.update(
        {
            "reconcilable": True,
            "modeled_entry_price": _round(modeled_entry, 4),
            "close_asof": _round(close_asof, 4),
            "fill_drift_pct": _round(fill_drift, 6),
            "realized_return_pct": _round(realized_return, 6),
            "modeled_return_pct": _round(modeled_return, 6),
            "trajectory_drift_pct": _round(realized_return - modeled_return, 6),
            "suspect_multi_fill": abs(fill_drift) > SUSPECT_FILL_DRIFT_PCT,
        }
    )
    return row


def _bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = buckets.setdefault(
            row["strategy_bucket"],
            {"positions": 0, "reconciled": 0, "notional_usd": 0.0, "_dw": 0.0, "_fd": []},
        )
        bucket["positions"] += 1
        if not row.get("reconcilable"):
            continue
        bucket["reconciled"] += 1
        if row.get("suspect_multi_fill"):
            bucket["suspect_multi_fill"] = bucket.get("suspect_multi_fill", 0) + 1
            continue
        notional = row.get("market_val") or 0.0
        bucket["notional_usd"] += notional
        bucket["_dw"] += notional * (row.get("trajectory_drift_pct") or 0.0)
        bucket["_fd"].append(row.get("fill_drift_pct") or 0.0)
    for bucket in buckets.values():
        notional = bucket["notional_usd"]
        bucket["weighted_trajectory_drift_pct"] = (
            round(bucket.pop("_dw") / notional, 6) if notional > 0 else None
        )
        fills = bucket.pop("_fd")
        bucket["mean_fill_drift_pct"] = (
            round(sum(fills) / len(fills), 6) if fills else None
        )
        bucket["notional_usd"] = round(notional, 2)
    return buckets


def evaluate_drift_alert(
    ledger_rows: list[dict[str, Any]],
    bucket: str = "core",
) -> dict[str, Any]:
    """Consecutive-breach alert over the per-session core-bucket weighted drift."""
    # A non-session rerun may carry a new wall-clock asof_date but the same
    # completed market session. The last in-memory copy wins deterministically.
    deduplicated: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for row in ledger_rows:
        deduplicated[_alert_row_key(row)] = row
    by_session: dict[str, list[dict[str, Any]]] = {}
    for row in deduplicated.values():
        market_session_date = _row_market_session_date(row)
        if (
            market_session_date is not None
            and row.get("strategy_bucket") == bucket
            and row.get("reconcilable")
            and not row.get("suspect_multi_fill")
        ):
            by_session.setdefault(market_session_date, []).append(row)
    sessions = sorted(by_session)
    breaches = []
    for session in sessions:
        rows = [
            row
            for row in by_session[session]
            if _row_execution_alert_eligible(row)
        ]
        notional = sum(r.get("market_val") or 0.0 for r in rows)
        drift = (
            sum((r.get("market_val") or 0.0) * (r.get("trajectory_drift_pct") or 0.0) for r in rows)
            / notional
            if notional > 0
            else None
        )
        breaches.append(drift is not None and drift < ALERT_TRAJECTORY_DRIFT_PCT)
    consecutive = 0
    for breached in reversed(breaches):
        if not breached:
            break
        consecutive += 1
    latest_rows = (
        [
            row
            for row in by_session.get(sessions[-1], [])
            if _row_execution_alert_eligible(row)
        ]
        if sessions
        else []
    )
    fills = [r.get("fill_drift_pct") or 0.0 for r in latest_rows]
    mean_fill = sum(fills) / len(fills) if fills else None
    return {
        "bucket": bucket,
        "sessions_observed": len(sessions),
        "consecutive_breach_sessions": consecutive,
        "trajectory_alert": consecutive >= ALERT_CONSECUTIVE_SESSIONS,
        "fill_alert": mean_fill is not None and mean_fill > ALERT_MEAN_FILL_DRIFT_PCT,
        "latest_mean_fill_drift_pct": round(mean_fill, 6) if mean_fill is not None else None,
        "thresholds": {
            "trajectory_drift_pct": ALERT_TRAJECTORY_DRIFT_PCT,
            "consecutive_sessions": ALERT_CONSECUTIVE_SESSIONS,
            "mean_fill_drift_pct": ALERT_MEAN_FILL_DRIFT_PCT,
        },
    }


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def build_live_drift_reconciliation(
    *,
    as_of: str,
    positions: list[dict[str, Any]] | None = None,
    positions_path: Path | str = DEFAULT_POSITIONS_PATH,
    bars_fn: Any = None,
    persist: bool = True,
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
    state_path: Path | str = DEFAULT_STATE_PATH,
    order_snapshots: list[dict[str, Any]] | None = None,
    order_snapshots_path: Path | str = DEFAULT_ORDER_SNAPSHOTS_PATH,
    quant_signals_fn: Any = None,
    quant_signals_dir: Path | str = DEFAULT_QUANT_SIGNALS_DIR,
) -> dict[str, Any]:
    """Build (and by default persist) today's reconciliation rows + summary."""
    as_of_date = str(as_of)[:10]
    if positions is None:
        try:
            payload = json.loads(Path(positions_path).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "asof_date": as_of_date,
                "rule_version": RULE_VERSION,
                "status": "positions_unavailable",
                "error": str(exc),
            }
        positions = account_positions(payload)

    if order_snapshots is None:
        order_snapshots, order_source_error = _load_order_snapshots(order_snapshots_path)
    elif isinstance(order_snapshots, list):
        _, order_source_error = _latest_order_facts(order_snapshots)
    else:
        order_snapshots = []
        order_source_error = "broker_order_snapshots_malformed"

    if quant_signals_fn is None:
        signal_cache: dict[str, dict[str, Any] | None] = {}

        def signal_lookup(decision_date: str) -> dict[str, Any] | None:
            if decision_date not in signal_cache:
                signal_cache[decision_date] = _load_quant_signals_snapshot(
                    decision_date, quant_signals_dir
                )
            return signal_cache[decision_date]

    else:
        signal_lookup = quant_signals_fn

    lookup = bars_fn or _bars_from_warehouse
    rows: list[dict[str, Any]] = []
    market_sessions_by_ticker: dict[str, list[str]] = {}
    for position in positions:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        try:
            bars = lookup(ticker)
        except Exception as exc:
            row = {
                "asof_date": as_of_date,
                "position_id": position.get("position_id"),
                "ticker": ticker,
                "strategy_bucket": strategy_bucket(position),
                "rule_version": RULE_VERSION,
                "reconcilable": False,
                "reason": f"bars_unavailable: {exc}",
            }
            row.update(
                _execution_alert_metadata(
                    position,
                    order_snapshots=order_snapshots,
                    order_source_error=order_source_error,
                    quant_signals_fn=signal_lookup,
                )
            )
            rows.append(row)
            continue
        market_sessions_by_ticker[ticker] = sorted(
            {
                str(bar.get("date") or "")[:10]
                for bar in bars
                if isinstance(bar, dict) and len(str(bar.get("date") or "")) >= 10
            }
        )
        rows.append(
            reconcile_position(
                position,
                bars,
                as_of_date,
                order_snapshots=order_snapshots,
                order_source_error=order_source_error,
                quant_signals_fn=signal_lookup,
            )
        )

    ledger_file = Path(ledger_path)
    history = _load_ledger(ledger_file)
    existing_keys = {_alert_row_key(row) for row in history}
    new_rows = [row for row in rows if _alert_row_key(row) not in existing_keys]

    alert_rows = _overlay_current_rows(history, rows)
    alert_rows = _enrich_legacy_alert_rows(
        alert_rows, rows, market_sessions_by_ticker
    )
    alert = evaluate_drift_alert(alert_rows)
    state = {
        "asof_date": as_of_date,
        "market_session_date": max(
            (row["market_session_date"] for row in rows if row.get("market_session_date")),
            default=None,
        ),
        "generated_at": _utc_now_iso(),
        "rule_version": RULE_VERSION,
        "status": "ok",
        "position_count": len(rows),
        "reconciled_count": sum(1 for r in rows if r.get("reconcilable")),
        "core_execution_alert_eligible_count": sum(
            1 for row in rows if _row_execution_alert_eligible(row)
        ),
        "unreconcilable": [
            {"ticker": r.get("ticker"), "reason": r.get("reason")}
            for r in rows
            if not r.get("reconcilable")
        ],
        "buckets": _bucket_summary(rows),
        "alert": alert,
        "appended_rows": len(new_rows),
        "contract": "docs/live_drift_reconciliation.md",
        "production_impact": "observe_only_no_orders_no_ranking_no_sizing",
    }

    if persist:
        ledger_file.parent.mkdir(parents=True, exist_ok=True)
        if new_rows:
            with ledger_file.open("a", encoding="utf-8") as handle:
                for row in new_rows:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
        atomic_write_json(state, Path(state_path))
    return state
