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
import os
from datetime import datetime
from typing import Any

from data_paths import daily_artifact_glob, data_artifact_path
from open_position_schema import account_positions

PENDING_ACTIONS_FILENAME = "pending_actions.json"
ACTIONABLE = {"ADD", "REDUCE", "EXIT"}
POSITION_ACTIONABLE = {"REDUCE", "EXIT"}


def _today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def _load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _position_shares(open_positions: dict | None) -> dict[str, float]:
    shares: dict[str, float] = {}
    for pos in account_positions(open_positions):
        ticker = str(pos.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        try:
            shares[ticker] = float(pos.get("shares") or 0)
        except (TypeError, ValueError):
            shares[ticker] = 0.0
    return shares


def _normalize_date(date_str: str | None) -> str:
    if not date_str:
        return _today_yyyymmdd()
    compact = str(date_str).replace("-", "")
    if len(compact) == 8 and compact.isdigit():
        return compact
    return _today_yyyymmdd()


def _advice_path_date(path: str) -> str | None:
    name = os.path.basename(path)
    for prefix in ("investment_advice_", "llm_prompt_resp_"):
        if name.startswith(prefix) and name.endswith(".json"):
            date_str = name[len(prefix):-len(".json")]
            if len(date_str) == 8 and date_str.isdigit():
                return date_str
    return None


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
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return str(path)


def _make_pending_record(
    action: dict,
    current_shares: dict[str, float],
    date_str: str,
    *,
    source_file: str | None = None,
) -> dict | None:
    ticker = str(action.get("ticker", "")).upper().strip()
    action_name = str(action.get("action", "")).upper().strip()
    if not ticker or action_name not in ACTIONABLE:
        return None
    if ticker not in current_shares:
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

    original_shares = current_shares[ticker]
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
        "id": f"{date_str}:{ticker}:{action_name}:{trigger}",
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


def reconcile_pending_actions(
    actions: list[dict],
    open_positions: dict | None,
    as_of_date: str | None = None,
) -> list[dict]:
    """Mark open actions executed when open_positions shows shares were reduced."""
    current_shares = _position_shares(open_positions)
    date_str = _normalize_date(as_of_date)
    reconciled: list[dict] = []
    for record in actions:
        if not isinstance(record, dict):
            continue
        updated = dict(record)
        if updated.get("status", "open") == "open" and _is_executed(updated, current_shares):
            updated["status"] = "executed"
            updated["closed_date"] = date_str
            updated["close_reason"] = "open_positions_shares_reconciled"
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
    current_shares = _position_shares(open_positions)
    actions = reconcile_pending_actions(existing_actions or [], open_positions, date_str)
    open_ids = {a.get("id") for a in actions if a.get("status", "open") == "open"}

    parsed = _unwrap_advice(parsed_advice) or {}
    for section_name in ("position_actions", "add_on_trades"):
        for action in parsed.get(section_name, []) or []:
            if not isinstance(action, dict):
                continue
            record = _make_pending_record(action, current_shares, date_str, source_file=source_file)
            if record and record["id"] not in open_ids:
                actions.append(record)
                open_ids.add(record["id"])
    return actions


def bootstrap_pending_actions_from_archives(
    data_dir: str,
    open_positions: dict | None,
    through_date: str | None = None,
) -> list[dict]:
    """Reconstruct pending actions from saved advice files if no ledger exists yet."""
    through = _normalize_date(through_date)
    paths = []
    paths.extend(str(path) for path in daily_artifact_glob("investment_advice", data_dir))
    paths.extend(str(path) for path in daily_artifact_glob("llm_prompt_resp", data_dir))
    dated_paths = []
    for path in paths:
        date_str = _advice_path_date(path)
        if date_str and date_str <= through:
            dated_paths.append((date_str, path))
    dated_paths.sort()

    actions: list[dict] = []
    seen_sources: set[tuple[str, str]] = set()
    for date_str, path in dated_paths:
        payload = _load_json(path)
        parsed = _unwrap_advice(payload)
        if not parsed:
            continue
        source_key = (date_str, os.path.basename(path).split("_", 1)[0])
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        actions = register_pending_actions_from_advice(
            parsed,
            open_positions,
            existing_actions=actions,
            as_of_date=date_str,
            source_file=os.path.basename(path),
        )
    return reconcile_pending_actions(actions, open_positions, through)


def get_open_pending_actions(
    open_positions: dict | None,
    *,
    data_dir: str = "data",
    as_of_date: str | None = None,
    bootstrap_if_empty: bool = False,
) -> list[dict]:
    actions = load_pending_actions(data_dir)
    if not actions and bootstrap_if_empty:
        actions = bootstrap_pending_actions_from_archives(data_dir, open_positions, as_of_date)
    actions = reconcile_pending_actions(actions, open_positions, as_of_date)
    return [a for a in actions if a.get("status", "open") == "open"]


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
            "reason": (
                f"Previous ADD from {pending_record.get('first_advice_date')} "
                "was not reflected in open_positions; repeating until shares reconcile. "
                f"Original reason: {pending_record.get('original_reason') or 'n/a'}"
            ),
        })
        changed.append(pending_record)
    updated["add_on_trades"] = add_on_trades
    return updated, changed
