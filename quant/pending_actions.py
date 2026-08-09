"""Track unexecuted position-management advice across daily runs.

The daily pipeline recomputes fresh HOLD/REDUCE/EXIT states each day.  That is
correct for new rule triggers, but it can accidentally forget a prior REDUCE or
EXIT recommendation when the broker/open_positions file still shows the action
was not executed.  This module keeps that execution-memory layer separate from
alpha logic: it repeats stale operator tasks without inventing new strategy
rules.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from data_paths import atomic_write_json, data_artifact_path
from open_position_schema import ACCOUNT_POSITION_GROUPS, account_positions

PENDING_ACTIONS_FILENAME = "pending_actions.json"
ACTIONABLE = {"ADD", "REDUCE", "EXIT"}
POSITION_ACTIONABLE = {"REDUCE", "EXIT"}
ACTIVE_IDENTITY_STATUSES = {"bound_at_creation", "matched", "legacy_migrated"}


def _today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def _load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _normalize_entry_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        compact = text.replace("-", "")
        return text if compact.isdigit() else None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return None


def _compact_date(value: Any) -> str | None:
    date_text = _normalize_entry_date(value)
    return date_text.replace("-", "") if date_text else None


def _position_lifecycle_id(
    account: Any,
    ticker: Any,
    direction: Any,
    entry_date: Any,
) -> str | None:
    account_text = str(account or "").strip().lower()
    ticker_text = str(ticker or "").strip().upper()
    direction_text = str(direction or "").strip().lower()
    entry_date_text = _normalize_entry_date(entry_date)
    if not all((account_text, ticker_text, direction_text, entry_date_text)):
        return None
    return (
        f"v1:{account_text}:{ticker_text}:{direction_text}:"
        f"{entry_date_text}"
    )


def _position_snapshot_available(open_positions: dict | None) -> bool:
    if not isinstance(open_positions, dict) or not open_positions.get("account"):
        return False
    present_groups = [
        open_positions.get(group)
        for group in ACCOUNT_POSITION_GROUPS
        if group in open_positions
    ]
    if not present_groups or not all(
        isinstance(rows, list) for rows in present_groups
    ):
        return False
    for rows in present_groups:
        for row in rows:
            if not isinstance(row, dict):
                return False
            if not str(row.get("ticker") or "").strip():
                return False
            if not str(row.get("direction") or "").strip():
                return False
            if not _normalize_entry_date(row.get("entry_date")):
                return False
            try:
                shares = float(row.get("shares"))
            except (TypeError, ValueError):
                return False
            if not math.isfinite(shares) or shares < 0:
                return False
    return True


def _position_states(open_positions: dict | None) -> dict[str, dict]:
    """Build current-lot identity rows keyed by ticker.

    Moomoo can reuse ``position_id`` after a full exit and re-entry, so the
    broker id is audit context only.  The lifecycle boundary is the verified
    current-lot ``entry_date`` reconstructed by ``moomoo_open_positions``.
    Multiple rows for one ticker are deliberately treated as ambiguous rather
    than guessed across account-position groups.
    """
    payload_account = (
        str((open_positions or {}).get("account") or "").strip().lower()
        if isinstance(open_positions, dict)
        else ""
    )
    states: dict[str, dict] = {}
    for pos in account_positions(open_positions):
        ticker = str(pos.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        account = str(pos.get("account") or payload_account).strip().lower()
        direction = str(pos.get("direction") or "").strip().lower()
        entry_date = _normalize_entry_date(pos.get("entry_date"))
        try:
            shares = float(pos.get("shares") or 0)
        except (TypeError, ValueError):
            shares = 0.0
        broker_position_id = pos.get("position_id")
        lifecycle_id = _position_lifecycle_id(
            account,
            ticker,
            direction,
            entry_date,
        )
        state = {
            "account": account or None,
            "ticker": ticker,
            "direction": direction or None,
            "entry_date": entry_date,
            "shares": shares,
            "broker_position_id": (
                str(broker_position_id)
                if broker_position_id not in (None, "")
                else None
            ),
            "position_lifecycle_id": lifecycle_id,
            "ambiguous": False,
        }
        if ticker in states:
            states[ticker]["ambiguous"] = True
            states[ticker]["position_lifecycle_id"] = None
            continue
        states[ticker] = state
    return states


def _normalize_date(date_str: str | None) -> str:
    if not date_str:
        return _today_yyyymmdd()
    compact = str(date_str).replace("-", "")
    if len(compact) == 8 and compact.isdigit():
        return compact
    return _today_yyyymmdd()


def _unwrap_advice(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None
    parsed = payload.get("advice_parsed", payload)
    return parsed if isinstance(parsed, dict) else None


def load_pending_actions(data_dir: str = "data") -> list[dict]:
    path = data_artifact_path("pending_actions", data_dir)
    payload = _load_json(path)
    if isinstance(payload, dict):
        actions = payload.get("pending_actions", [])
        return actions if isinstance(actions, list) else []
    if isinstance(payload, list):
        return payload
    return []


def save_pending_actions(actions: list[dict], data_dir: str = "data") -> str:
    path = data_artifact_path("pending_actions", data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(),
        "pending_actions": actions,
    }
    atomic_write_json(payload, path, indent=2, ensure_ascii=False)
    return str(path)


def _make_pending_record(
    action: dict,
    current_positions: dict[str, dict],
    date_str: str,
    *,
    source_file: str | None = None,
) -> dict | None:
    ticker = str(action.get("ticker", "")).upper().strip()
    action_name = str(action.get("action", "")).upper().strip()
    if not ticker or action_name not in ACTIONABLE:
        return None
    if (
        str(action.get("decision_mode") or "").strip().lower()
        == "pending_unexecuted_action"
        or action.get("pending_action_id")
    ):
        # An execution-memory reminder is not fresh advice.  Re-registering it
        # would launder an old action into today's position lifecycle.
        return None
    position = current_positions.get(ticker)
    if not position or position.get("ambiguous"):
        return None
    lifecycle_id = position.get("position_lifecycle_id")
    entry_date = position.get("entry_date")
    if not lifecycle_id or not entry_date:
        return None
    if (_compact_date(entry_date) or "") > date_str:
        # Archive bootstrap must never bind historical advice to a lot that
        # opened later merely because the ticker is held today.
        return None

    raw_shares_to_sell = action.get("shares_to_sell")
    raw_shares_to_buy = action.get("shares_to_buy")
    shares_to_sell = None
    shares_to_buy = None
    if action_name == "EXIT":
        pass
    elif action_name == "ADD":
        try:
            shares_to_buy = int(raw_shares_to_buy)
        except (TypeError, ValueError):
            return None
        if shares_to_buy <= 0:
            return None
    else:
        try:
            shares_to_sell = int(raw_shares_to_sell)
        except (TypeError, ValueError):
            return None
        if shares_to_sell <= 0:
            return None

    original_shares = float(position.get("shares") or 0)
    if action_name == "EXIT":
        expected_remaining = 0.0
    elif action_name == "ADD":
        expected_remaining = original_shares + shares_to_buy
    else:
        expected_remaining = max(original_shares - shares_to_sell, 0.0)
    trigger = (
        action.get("exit_rule_triggered")
        or action.get("decision_mode")
        or ("ADD_ON" if action_name == "ADD" else "UNKNOWN")
    )
    return {
        "id": f"{date_str}:{ticker}:{action_name}:{trigger}:{lifecycle_id}",
        "status": "open",
        "first_advice_date": date_str,
        "last_seen_date": date_str,
        "ticker": ticker,
        "action": action_name,
        "shares_to_sell": shares_to_sell,
        "shares_to_buy": shares_to_buy,
        "original_shares": original_shares,
        "expected_remaining_shares": expected_remaining,
        "exit_rule_triggered": action.get("exit_rule_triggered") or "UNKNOWN",
        "original_reason": action.get("reason") or "",
        "decision_mode": action.get("decision_mode") or "forced_rule",
        "fill_timing": action.get("fill_timing"),
        "source_file": source_file,
        "account": position.get("account"),
        "direction": position.get("direction"),
        "position_entry_date": entry_date,
        "position_lifecycle_id": lifecycle_id,
        "broker_position_id": position.get("broker_position_id"),
        "position_identity_status": "bound_at_creation",
    }


def _is_executed(record: dict, current_shares: dict[str, float]) -> bool:
    ticker = str(record.get("ticker", "")).upper()
    now = current_shares.get(ticker, 0.0)
    if record.get("action") == "EXIT":
        return now <= 0
    try:
        expected_remaining = float(record.get("expected_remaining_shares"))
    except (TypeError, ValueError):
        return False
    if record.get("action") == "ADD":
        return now >= expected_remaining
    return now <= expected_remaining


def _close_record(
    record: dict,
    *,
    status: str,
    close_reason: str,
    date_str: str,
) -> dict:
    record["status"] = status
    record["closed_date"] = date_str
    record["close_reason"] = close_reason
    return record


def _active_open_action(record: dict) -> bool:
    return (
        record.get("status", "open") == "open"
        and bool(record.get("position_lifecycle_id"))
        and record.get("position_identity_status") in ACTIVE_IDENTITY_STATUSES
    )


def reconcile_pending_actions(
    actions: list[dict],
    open_positions: dict | None,
    as_of_date: str | None = None,
) -> list[dict]:
    """Reconcile actions against the exact current position lifecycle."""
    current_positions = _position_states(open_positions)
    snapshot_available = _position_snapshot_available(open_positions)
    date_str = _normalize_date(as_of_date)
    reconciled: list[dict] = []
    for record in actions:
        if not isinstance(record, dict):
            continue
        updated = dict(record)
        if updated.get("status", "open") != "open":
            reconciled.append(updated)
            continue
        first_advice_date = _compact_date(updated.get("first_advice_date"))
        if first_advice_date and first_advice_date > date_str:
            # Historical/as-of reads must not close or migrate an action before
            # the action existed.  Keep the stored row byte-semantically
            # unchanged; the query layer below also hides future rows.
            reconciled.append(updated)
            continue
        if not snapshot_available:
            # Never reconcile from a partially valid subset.  One malformed
            # sibling row means the account snapshot may be truncated, so even
            # an otherwise valid target row cannot safely close an action.
            updated["position_identity_status"] = "snapshot_unavailable"
            updated["identity_blocked_reason"] = (
                "open_position_snapshot_unavailable_or_malformed"
            )
            reconciled.append(updated)
            continue

        ticker = str(updated.get("ticker") or "").upper().strip()
        current = current_positions.get(ticker)
        if current is None:
            if str(updated.get("action") or "").upper() == "ADD":
                _close_record(
                    updated,
                    status="superseded",
                    close_reason="position_lifecycle_missing_before_add",
                    date_str=date_str,
                )
            else:
                _close_record(
                    updated,
                    status="executed",
                    close_reason="position_absent_from_valid_snapshot",
                    date_str=date_str,
                )
            reconciled.append(updated)
            continue

        current_lifecycle_id = current.get("position_lifecycle_id")
        if current.get("ambiguous") or not current_lifecycle_id:
            updated["position_identity_status"] = "quarantined_identity_unknown"
            updated["identity_blocked_reason"] = (
                "multiple_rows_for_ticker"
                if current.get("ambiguous")
                else "current_position_identity_incomplete"
            )
            reconciled.append(updated)
            continue

        bound_lifecycle_id = str(
            updated.get("position_lifecycle_id") or ""
        ).strip()
        if bound_lifecycle_id:
            if bound_lifecycle_id != current_lifecycle_id:
                updated["position_identity_status"] = "lifecycle_mismatch"
                updated["current_position_lifecycle_id"] = current_lifecycle_id
                updated["current_position_entry_date"] = current.get("entry_date")
                _close_record(
                    updated,
                    status="superseded",
                    close_reason="position_lifecycle_changed",
                    date_str=date_str,
                )
                reconciled.append(updated)
                continue
            updated["position_identity_status"] = "matched"
        else:
            advice_date = _compact_date(updated.get("first_advice_date"))
            current_entry_date = _compact_date(current.get("entry_date"))
            if not advice_date or not current_entry_date:
                updated["position_identity_status"] = (
                    "quarantined_identity_unknown"
                )
                updated["identity_blocked_reason"] = (
                    "legacy_action_missing_identity_evidence"
                )
                reconciled.append(updated)
                continue
            if current_entry_date > advice_date:
                updated["position_identity_status"] = "lifecycle_mismatch"
                updated["current_position_lifecycle_id"] = current_lifecycle_id
                updated["current_position_entry_date"] = current.get("entry_date")
                _close_record(
                    updated,
                    status="superseded",
                    close_reason="legacy_action_predates_current_lifecycle",
                    date_str=date_str,
                )
                reconciled.append(updated)
                continue
            if current_entry_date == advice_date:
                updated["position_identity_status"] = (
                    "quarantined_same_day_identity_ambiguous"
                )
                updated["identity_blocked_reason"] = (
                    "legacy_action_and_current_entry_share_day_granularity"
                )
                reconciled.append(updated)
                continue
            updated.update({
                "account": current.get("account"),
                "direction": current.get("direction"),
                "position_entry_date": current.get("entry_date"),
                "position_lifecycle_id": current_lifecycle_id,
                "broker_position_id": current.get("broker_position_id"),
                "position_identity_status": "legacy_migrated",
                "identity_migrated_at": date_str,
            })

        current_shares = {ticker: float(current.get("shares") or 0)}
        if _is_executed(updated, current_shares):
            _close_record(
                updated,
                status="executed",
                close_reason="open_positions_shares_reconciled",
                date_str=date_str,
            )
        reconciled.append(updated)
    return reconciled


def register_pending_actions_from_advice(
    parsed_advice: dict | None,
    open_positions: dict | None,
    *,
    existing_actions: list[dict] | None = None,
    as_of_date: str | None = None,
    source_file: str | None = None,
) -> list[dict]:
    """Add new REDUCE/EXIT advice entries and reconcile existing ones."""
    date_str = _normalize_date(as_of_date)
    current_positions = _position_states(open_positions)
    actions = reconcile_pending_actions(existing_actions or [], open_positions, date_str)
    open_ids = {a.get("id") for a in actions if a.get("status", "open") == "open"}

    parsed = _unwrap_advice(parsed_advice) or {}
    for section_name in ("position_actions", "add_on_trades"):
        for action in parsed.get(section_name, []) or []:
            if not isinstance(action, dict):
                continue
            record = _make_pending_record(
                action,
                current_positions,
                date_str,
                source_file=source_file,
            )
            if record and record["id"] not in open_ids:
                actions.append(record)
                open_ids.add(record["id"])
    return actions


def bootstrap_pending_actions_from_archives(
    data_dir: str,
    open_positions: dict | None,
    through_date: str | None = None,
) -> list[dict]:
    """Return no rows until point-in-time position snapshots are available.

    Historical advice plus today's open positions cannot reconstruct which lot
    an action belonged to or its then-current share count.  The old bootstrap
    path could therefore attach months-old exits to a current reopened lot.
    Keep the API for callers, but fail closed instead of fabricating identity.
    """
    del data_dir, open_positions, through_date
    return []


def get_open_pending_actions(
    open_positions: dict | None,
    *,
    data_dir: str = "data",
    as_of_date: str | None = None,
    bootstrap_if_empty: bool = False,
) -> list[dict]:
    stored_actions = load_pending_actions(data_dir)
    actions = stored_actions
    if not stored_actions and bootstrap_if_empty:
        actions = bootstrap_pending_actions_from_archives(data_dir, open_positions, as_of_date)
    actions = reconcile_pending_actions(actions, open_positions, as_of_date)
    if actions != stored_actions:
        # Persist terminal lifecycle decisions.  Otherwise an action marked
        # executed while flat can resurrect when the ticker is bought again.
        save_pending_actions(actions, data_dir)
    query_date = _normalize_date(as_of_date)
    return [
        action
        for action in actions
        if _active_open_action(action)
        and (_compact_date(action.get("first_advice_date")) or "99999999")
        <= query_date
    ]


def apply_pending_action_overrides(
    parsed_advice: dict | None,
    open_positions: dict | None,
    *,
    data_dir: str = "data",
    as_of_date: str | None = None,
) -> tuple[dict | None, list[dict]]:
    """Force unexecuted prior position/add-on actions back into today's advice."""
    if not isinstance(parsed_advice, dict):
        return parsed_advice, []
    pending = get_open_pending_actions(
        open_positions,
        data_dir=data_dir,
        as_of_date=as_of_date,
        bootstrap_if_empty=False,
    )
    pending_position_by_ticker = {
        str(p.get("ticker", "")).upper(): p
        for p in pending
        if p.get("action") in POSITION_ACTIONABLE
    }
    pending_adds_by_ticker = {
        str(p.get("ticker", "")).upper(): p
        for p in pending
        if p.get("action") == "ADD"
    }
    if not pending_position_by_ticker and not pending_adds_by_ticker:
        return parsed_advice, []

    updated = dict(parsed_advice)
    position_actions = []
    changed: list[dict] = []
    for action in updated.get("position_actions", []) or []:
        if not isinstance(action, dict):
            position_actions.append(action)
            continue
        ticker = str(action.get("ticker", "")).upper()
        pending_record = pending_position_by_ticker.get(ticker)
        if not pending_record:
            position_actions.append(action)
            continue
        if str(action.get("action", "")).upper() in POSITION_ACTIONABLE:
            position_actions.append(action)
            continue

        patched = dict(action)
        patched["action"] = pending_record["action"]
        patched["shares_to_sell"] = pending_record.get("shares_to_sell")
        patched["exit_rule_triggered"] = pending_record.get("exit_rule_triggered") or "PENDING_ACTION"
        patched["decision_mode"] = "pending_unexecuted_action"
        patched["pending_action_id"] = pending_record.get("id")
        patched["position_lifecycle_id"] = pending_record.get(
            "position_lifecycle_id"
        )
        patched["reason"] = (
            f"Previous {pending_record['action']} from "
            f"{pending_record.get('first_advice_date')} was not reflected in "
            f"open_positions; original trigger="
            f"{pending_record.get('exit_rule_triggered')}. "
            "Repeating until shares reconcile."
        )
        position_actions.append(patched)
        changed.append(pending_record)

    updated["position_actions"] = position_actions
    add_on_trades = [
        item for item in updated.get("add_on_trades", []) or []
        if isinstance(item, dict)
    ]
    existing_add_tickers = {
        str(item.get("ticker", "")).upper()
        for item in add_on_trades
        if str(item.get("action", "")).upper() == "ADD"
    }
    for ticker, pending_record in pending_adds_by_ticker.items():
        if ticker in existing_add_tickers:
            continue
        add_on_trades.append({
            "ticker": ticker,
            "action": "ADD",
            "shares_to_buy": pending_record.get("shares_to_buy"),
            "fill_timing": pending_record.get("fill_timing") or "next_session_open",
            "decision_mode": "pending_unexecuted_action",
            "pending_action_id": pending_record.get("id"),
            "position_lifecycle_id": pending_record.get(
                "position_lifecycle_id"
            ),
            "reason": (
                f"Previous ADD from {pending_record.get('first_advice_date')} "
                "was not reflected in open_positions; repeating until shares reconcile. "
                f"Original reason: {pending_record.get('original_reason') or 'n/a'}"
            ),
        })
        changed.append(pending_record)
    updated["add_on_trades"] = add_on_trades
    return updated, changed
