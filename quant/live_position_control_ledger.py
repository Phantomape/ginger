"""Read-only live position-control ledger.

This module reconciles the operator open-position snapshot with the daily
bracket-order report and live-drift state. It does not submit, rank, size, or
filter trades; it only emits a machine-checkable control ledger/state for
production consistency review.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # pragma: no cover - import mode differs between pytest and runners.
    from data_paths import DATA_ROOT, REPO_ROOT, atomic_write_json, atomic_write_text
except ImportError:  # pragma: no cover
    from quant.data_paths import DATA_ROOT, REPO_ROOT, atomic_write_json, atomic_write_text


RULE_VERSION = "live_position_control_ledger_v1"
DEFAULT_POSITIONS_PATH = REPO_ROOT / "operator_inputs" / "open_positions.json"
DEFAULT_REPORTS_DIR = DATA_ROOT / "daily" / "reports"
DEFAULT_LIVE_DRIFT_STATE_PATH = DATA_ROOT / "live_pilot" / "live_drift" / "state.json"
DEFAULT_SURFACE_DIR = DATA_ROOT / "live_pilot" / "position_control"
DEFAULT_LEDGER_PATH = DEFAULT_SURFACE_DIR / "ledger.jsonl"
DEFAULT_STATE_PATH = DEFAULT_SURFACE_DIR / "state.json"

_REPORT_DATE_RE = re.compile(r"report_(\d{8})", re.IGNORECASE)
_HEADER_DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_HEAT_RE = re.compile(r"PORTFOLIO HEAT:\s*([-+]?\d+(?:\.\d+)?)%\s*\(([^)]+)\)", re.IGNORECASE)
_ENTRY_SLOTS_RE = re.compile(r"ENTRY SLOTS.*?:\s*(\d+)\s+available", re.IGNORECASE)
_BRACKET_SUMMARY_RE = re.compile(
    r"Positions:\s*(\d+)\s*\|\s*Resting orders:\s*(\d+)\s*"
    r"\((\d+)\s*target-limit,\s*(\d+)\s*stop\)\s*\|\s*"
    r"Exit-now flags:\s*(\d+)\s*\|\s*Warnings:\s*(\d+)",
    re.IGNORECASE,
)
_ORDER_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9.\-]{0,9})\s+SELL\s+(STOP|LIMIT)\s+@\s+"
    r"([-+]?\d+(?:\.\d+)?)\s+x\s*([-+]?\d+(?:\.\d+)?)\s+GTC\s+\[(stop|target)\]\s*$",
    re.IGNORECASE,
)
_EXIT_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9.\-]{0,9})\s+(stop|target)\s+current\s+"
    r"([-+]?\d+(?:\.\d+)?)\s+([<>=!]+)\s+(.+)$",
    re.IGNORECASE,
)
_WARNING_RE = re.compile(r"^\s*!\s*([A-Z][A-Z0-9.\-]{0,9}):\s*(.+)$", re.IGNORECASE)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 6) -> float | None:
    number = _float_or_none(value)
    return round(number, digits) if number is not None else None


def _load_json(path: str | Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def _report_date_from_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    match = _REPORT_DATE_RE.search(Path(path).name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _report_date_from_text(text: str) -> str | None:
    match = _HEADER_DATE_RE.search(text)
    if not match:
        return None
    return "-".join(match.groups())


def latest_report_path(reports_dir: str | Path = DEFAULT_REPORTS_DIR) -> Path | None:
    """Return the latest daily report path by embedded report_YYYYMMDD date."""
    root = Path(reports_dir)
    if not root.exists():
        return None
    candidates = []
    for path in root.glob("report_*.txt"):
        report_date = _report_date_from_path(path)
        if report_date:
            candidates.append((report_date, path))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def _warning_flags(message: str) -> list[str]:
    lower = message.lower()
    flags: list[str] = []
    if "past recorded target" in lower:
        flags.append("stale_target")
    if "trailed" in lower and "entry stop could not be reconstructed" in lower:
        flags.append("fallback_stop")
    if "no resting limit" in lower:
        flags.append("no_resting_limit")
    if "stop already breached" in lower:
        flags.append("stop_already_breached")
    return flags or ["unclassified_warning"]


def parse_daily_report(text: str, path: str | Path | None = None) -> dict[str, Any]:
    """Parse bracket-control facts from a daily report text blob."""
    report_date = _report_date_from_path(path) or _report_date_from_text(text)
    heat = _HEAT_RE.search(text)
    slots = _ENTRY_SLOTS_RE.search(text)
    bracket = _BRACKET_SUMMARY_RE.search(text)

    orders_by_ticker: dict[str, list[dict[str, Any]]] = {}
    exit_now_by_ticker: dict[str, list[dict[str, Any]]] = {}
    warnings_by_ticker: dict[str, list[dict[str, Any]]] = {}

    for line in text.splitlines():
        order_match = _ORDER_RE.match(line)
        if order_match:
            ticker, order_type, price, shares, bracket_kind = order_match.groups()
            row = {
                "ticker": ticker.upper(),
                "side": "SELL",
                "order_type": order_type.upper(),
                "price": _round(price, 4),
                "shares": _round(shares, 6),
                "time_in_force": "GTC",
                "bracket_kind": bracket_kind.lower(),
                "source": "daily_report_manual_maintain_order",
            }
            orders_by_ticker.setdefault(row["ticker"], []).append(row)
            continue

        exit_match = _EXIT_RE.match(line)
        if exit_match:
            ticker, trigger_kind, current, comparator, reason = exit_match.groups()
            row = {
                "ticker": ticker.upper(),
                "trigger_kind": trigger_kind.lower(),
                "current_price": _round(current, 4),
                "comparator": comparator,
                "reason": reason.strip(),
                "source": "daily_report_exit_now",
            }
            exit_now_by_ticker.setdefault(row["ticker"], []).append(row)
            continue

        warning_match = _WARNING_RE.match(line)
        if warning_match:
            ticker, message = warning_match.groups()
            row = {
                "ticker": ticker.upper(),
                "message": message.strip(),
                "flags": _warning_flags(message),
                "source": "daily_report_warning",
            }
            warnings_by_ticker.setdefault(row["ticker"], []).append(row)

    all_warning_flags = sorted(
        {
            flag
            for rows in warnings_by_ticker.values()
            for row in rows
            for flag in row.get("flags", [])
        }
    )
    all_tickers = sorted(
        set(orders_by_ticker) | set(exit_now_by_ticker) | set(warnings_by_ticker)
    )
    bracket_summary = {}
    if bracket:
        positions, resting, target_limit, stop, exit_flags, warnings = bracket.groups()
        bracket_summary = {
            "positions": _int_or_none(positions),
            "resting_orders": _int_or_none(resting),
            "target_limit_orders": _int_or_none(target_limit),
            "stop_orders": _int_or_none(stop),
            "exit_now_flags": _int_or_none(exit_flags),
            "warnings": _int_or_none(warnings),
        }

    return {
        "status": "ok",
        "report_path": str(Path(path)) if path is not None else None,
        "report_date": report_date,
        "portfolio_heat_pct": _round(heat.group(1), 4) if heat else None,
        "portfolio_heat_status": heat.group(2).strip() if heat else None,
        "ok_to_add_reported": bool(heat and "ok to add" in heat.group(2).lower()),
        "entry_slots_available": _int_or_none(slots.group(1)) if slots else None,
        "bracket_summary": bracket_summary,
        "orders_by_ticker": orders_by_ticker,
        "exit_now_by_ticker": exit_now_by_ticker,
        "warnings_by_ticker": warnings_by_ticker,
        "warning_flags": all_warning_flags,
        "tickers": all_tickers,
        "manual_order_instruction_count": sum(len(rows) for rows in orders_by_ticker.values()),
        "exit_now_count": sum(len(rows) for rows in exit_now_by_ticker.values()),
        "warning_count": sum(len(rows) for rows in warnings_by_ticker.values()),
    }


def _normalize_position(row: Mapping[str, Any], group: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper().strip()
    return {
        "ticker": ticker,
        "position_id": str(row.get("position_id") or f"{group}:{ticker}"),
        "position_group": group,
        "direction": row.get("direction"),
        "shares": _round(row.get("shares"), 6),
        "avg_cost": _round(row.get("avg_cost"), 6),
        "entry_date": row.get("entry_date"),
        "target_price": _round(row.get("target_price"), 4),
        "stop_price": _round(row.get("stop_price"), 4),
        "entry_stop_price": _round(row.get("entry_stop_price"), 4),
        "opened_by_strategy": row.get("opened_by_strategy"),
        "sleeve": row.get("sleeve"),
        "slot_policy": row.get("slot_policy"),
        "risk_notes": row.get("risk_notes"),
        "source": row.get("source"),
        "market_val": _round(row.get("market_val"), 4),
        "unrealized_pl": _round(row.get("unrealized_pl"), 4),
        "strategy_bucket": _strategy_bucket(row, group),
    }


def _strategy_bucket(row: Mapping[str, Any], group: str) -> str:
    if group == "core_positions":
        return "core"
    sleeve = str(row.get("sleeve") or "").lower()
    opened_by = str(row.get("opened_by_strategy") or "").lower()
    if sleeve in {"legacy", "discretionary"} or opened_by in {"legacy", "discretionary"}:
        return "discretionary_legacy"
    if sleeve:
        return "sleeve"
    return "unknown"


def load_open_positions(path: str | Path = DEFAULT_POSITIONS_PATH) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _load_json(path, {})
    positions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for group in ("core_positions", "positions", "observations"):
        rows = payload.get(group, []) if isinstance(payload, Mapping) else []
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            row = _normalize_position(raw, group)
            if not row["ticker"]:
                continue
            key = row["position_id"]
            if key in seen_ids:
                continue
            seen_ids.add(key)
            positions.append(row)
    return dict(payload) if isinstance(payload, Mapping) else {}, positions


def _order_summary(orders: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(orders)
    stop_orders = [row for row in rows if row.get("bracket_kind") == "stop"]
    target_orders = [row for row in rows if row.get("bracket_kind") == "target"]
    return {
        "report_order_count": len(rows),
        "report_stop_order_present": bool(stop_orders),
        "report_target_order_present": bool(target_orders),
        "report_stop_price": stop_orders[0].get("price") if stop_orders else None,
        "report_target_price": target_orders[0].get("price") if target_orders else None,
        "report_orders": rows,
    }


def _positions_snapshot_stale(report_date: str | None, positions_as_of: str | None) -> bool:
    """True only when the positions snapshot is OLDER than the report date.

    ``open_positions.json`` stamps ``as_of`` with the UTC calendar date, so a
    normal post-close Pacific-evening run yields ``positions_as_of`` one day
    AHEAD of ``report_date`` — that is a fresher snapshot, not a mismatch
    (exp-20260727-004; strict equality had fired on 100% of ledger days).
    A snapshot dated before the report (e.g. the 2026-07-26 broker-refresh
    outage) is genuinely stale and must keep blocking adds.
    """
    if not report_date or not positions_as_of:
        return False
    return positions_as_of < report_date


def _row_control_blockers(
    *,
    row_source: str,
    report_date: str | None,
    positions_as_of: str | None,
    orders: list[dict[str, Any]],
    exit_now: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    position: Mapping[str, Any] | None,
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    notes: list[str] = []
    flags = sorted({flag for warning in warnings for flag in warning.get("flags", [])})

    if exit_now:
        blockers.append("exit_now")
    if "stale_target" in flags:
        blockers.append("stale_target")
    if "fallback_stop" in flags:
        blockers.append("fallback_stop")
    if orders:
        blockers.append("manual_bracket_orders_not_broker_confirmed")
    if row_source == "report_only":
        blockers.append("report_only_control_row")
    if _positions_snapshot_stale(report_date, positions_as_of):
        blockers.append("report_open_positions_asof_mismatch")
    if position and not orders and not exit_now and not warnings:
        blockers.append("missing_daily_report_control")

    if position:
        risk_notes = str(position.get("risk_notes") or "").lower()
        if "rejected" in risk_notes:
            notes.append("source_signal_rejected_alpha")
        if "discretionary live mirror" in risk_notes:
            notes.append("discretionary_live_mirror")
    return sorted(dict.fromkeys(blockers)), sorted(dict.fromkeys(notes))


def _build_rows(
    *,
    report: Mapping[str, Any],
    positions_payload: Mapping[str, Any],
    positions: list[dict[str, Any]],
    live_drift_state: Mapping[str, Any],
    generated_at: str,
) -> list[dict[str, Any]]:
    report_date = report.get("report_date")
    positions_as_of = positions_payload.get("as_of")
    positions_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for position in positions:
        positions_by_ticker.setdefault(position["ticker"], []).append(position)

    orders_by_ticker = report.get("orders_by_ticker", {}) or {}
    exit_by_ticker = report.get("exit_now_by_ticker", {}) or {}
    warnings_by_ticker = report.get("warnings_by_ticker", {}) or {}
    tickers = sorted(set(positions_by_ticker) | set(orders_by_ticker) | set(exit_by_ticker) | set(warnings_by_ticker))

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        ticker_positions = positions_by_ticker.get(ticker) or [None]
        for position in ticker_positions:
            row_source = "report_only"
            if position:
                row_source = (
                    "open_positions_observation"
                    if position.get("position_group") == "observations"
                    else "open_positions"
                )
            orders = list(orders_by_ticker.get(ticker, []))
            exit_now = list(exit_by_ticker.get(ticker, []))
            warnings = list(warnings_by_ticker.get(ticker, []))
            blockers, notes = _row_control_blockers(
                row_source=row_source,
                report_date=report_date,
                positions_as_of=positions_as_of,
                orders=orders,
                exit_now=exit_now,
                warnings=warnings,
                position=position,
            )
            control_id = (
                f"position:{position['position_id']}"
                if position
                else f"report:{ticker}:{report_date or 'unknown'}"
            )
            order_summary = _order_summary(orders)
            row = {
                "ledger_key": f"{report_date or positions_as_of or 'unknown'}|{control_id}|{RULE_VERSION}",
                "rule_version": RULE_VERSION,
                "generated_at": generated_at,
                "asof_date": report_date or positions_as_of,
                "report_date": report_date,
                "positions_as_of": positions_as_of,
                "report_path": report.get("report_path"),
                "live_drift_asof_date": live_drift_state.get("asof_date"),
                "ticker": ticker,
                "control_id": control_id,
                "row_source": row_source,
                "control_status": "blocked" if blockers else "covered",
                "control_blockers": blockers,
                "control_notes": notes,
                "exit_now": bool(exit_now),
                "exit_now_reasons": exit_now,
                "warning_count": len(warnings),
                "warning_flags": sorted({flag for warning in warnings for flag in warning.get("flags", [])}),
                "warnings": warnings,
                "manual_bracket_required": bool(orders or exit_now or warnings),
                "broker_order_coverage_status": (
                    "manual_instruction_not_broker_confirmed"
                    if orders
                    else "not_present_in_report"
                ),
                **order_summary,
                "production_impact": "observe_only_no_orders_no_ranking_no_sizing",
            }
            if position:
                row.update(position)
            else:
                row.update(
                    {
                        "position_id": None,
                        "position_group": None,
                        "direction": None,
                        "shares": None,
                        "avg_cost": None,
                        "entry_date": None,
                        "target_price": None,
                        "stop_price": None,
                        "entry_stop_price": None,
                        "opened_by_strategy": None,
                        "sleeve": None,
                        "slot_policy": None,
                        "risk_notes": None,
                        "source": None,
                        "market_val": None,
                        "unrealized_pl": None,
                        "strategy_bucket": "report_only",
                    }
                )
            rows.append(row)
    return rows


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows = []
    for line in target.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def append_position_control_ledger(
    rows: list[dict[str, Any]],
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    """Idempotently append ledger rows keyed by ledger_key."""
    path = Path(ledger_path)
    existing = _read_jsonl(path)
    existing_keys = {str(row.get("ledger_key")) for row in existing}
    new_rows = [row for row in rows if str(row.get("ledger_key")) not in existing_keys]
    if new_rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        all_rows = existing + new_rows
        text = "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in all_rows)
        try:
            atomic_write_text(text, path)
        except PermissionError:
            # This ledger is observe-only and idempotent. If Windows refuses the
            # final atomic rename for this local JSONL surface, fall back to a
            # direct rewrite so the control state is not silently absent.
            path.write_text(text, encoding="utf-8")
    return {
        "ledger_path": str(path),
        "rows_existing": len(existing),
        "rows_appended": len(new_rows),
        "rows_total": len(existing) + len(new_rows),
    }


def _write_json_best_effort(payload: Any, path: str | Path) -> None:
    target = Path(path)
    try:
        atomic_write_json(payload, target, indent=2, ensure_ascii=True)
    except PermissionError:
        # Same observe-only, idempotent surface as the JSONL ledger. A direct
        # write is preferable to a missing state when Windows refuses rename.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _build_state(
    *,
    report: Mapping[str, Any],
    positions_payload: Mapping[str, Any],
    positions: list[dict[str, Any]],
    live_drift_state: Mapping[str, Any],
    rows: list[dict[str, Any]],
    append_result: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    blockers = sorted({blocker for row in rows for blocker in row.get("control_blockers", [])})
    rows_by_status: dict[str, int] = {}
    for row in rows:
        status = str(row.get("control_status") or "unknown")
        rows_by_status[status] = rows_by_status.get(status, 0) + 1
    warning_flags = sorted({flag for row in rows for flag in row.get("warning_flags", [])})
    report_date = report.get("report_date")
    positions_as_of = positions_payload.get("as_of")
    date_mismatch = _positions_snapshot_stale(report_date, positions_as_of)

    return {
        "asof_date": report_date or positions_as_of,
        "report_date": report_date,
        "positions_as_of": positions_as_of,
        "generated_at": generated_at,
        "rule_version": RULE_VERSION,
        "status": "ok",
        "report_path": report.get("report_path"),
        "positions_path": str(DEFAULT_POSITIONS_PATH),
        "live_drift_state_path": str(DEFAULT_LIVE_DRIFT_STATE_PATH),
        "position_rows": len(rows),
        "open_position_count": len([p for p in positions if p.get("position_group") != "observations"]),
        "observation_position_count": len([p for p in positions if p.get("position_group") == "observations"]),
        "report_position_count": (report.get("bracket_summary") or {}).get("positions"),
        "report_resting_order_count": (report.get("bracket_summary") or {}).get("resting_orders"),
        "manual_order_instruction_count": report.get("manual_order_instruction_count", 0),
        "exit_now_count": report.get("exit_now_count", 0),
        "warning_count": report.get("warning_count", 0),
        "stale_target_count": sum(1 for row in rows if "stale_target" in row.get("control_blockers", [])),
        "fallback_stop_count": sum(1 for row in rows if "fallback_stop" in row.get("control_blockers", [])),
        "report_only_row_count": sum(1 for row in rows if row.get("row_source") == "report_only"),
        "missing_daily_report_control_count": sum(
            1 for row in rows if "missing_daily_report_control" in row.get("control_blockers", [])
        ),
        "report_open_positions_asof_mismatch": date_mismatch,
        "ok_to_add_reported": report.get("ok_to_add_reported"),
        "entry_slots_reported": report.get("entry_slots_available"),
        "ok_to_add_control_pass": not blockers,
        "ok_to_add_control_blockers": blockers,
        "rows_by_status": rows_by_status,
        "warning_flags": warning_flags,
        "ledger": dict(append_result),
        "live_drift_status": live_drift_state.get("status"),
        "live_drift_rule_version": live_drift_state.get("rule_version"),
        "production_impact": "observe_only_no_orders_no_ranking_no_sizing",
    }


def build_position_control_ledger(
    *,
    report_path: str | Path | None = None,
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
    positions_path: str | Path = DEFAULT_POSITIONS_PATH,
    live_drift_state_path: str | Path = DEFAULT_LIVE_DRIFT_STATE_PATH,
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    state_path: str | Path = DEFAULT_STATE_PATH,
    persist: bool = True,
) -> dict[str, Any]:
    """Build and optionally persist the position-control ledger/state."""
    generated_at = _utc_now_iso()
    selected_report_path = Path(report_path) if report_path is not None else latest_report_path(reports_dir)
    if selected_report_path and selected_report_path.exists():
        report = parse_daily_report(
            selected_report_path.read_text(encoding="utf-8-sig"),
            selected_report_path,
        )
    else:
        report = {
            "status": "missing_report",
            "report_path": str(selected_report_path) if selected_report_path else None,
            "report_date": None,
            "ok_to_add_reported": None,
            "entry_slots_available": None,
            "bracket_summary": {},
            "orders_by_ticker": {},
            "exit_now_by_ticker": {},
            "warnings_by_ticker": {},
            "manual_order_instruction_count": 0,
            "exit_now_count": 0,
            "warning_count": 0,
        }

    positions_payload, positions = load_open_positions(positions_path)
    live_drift_state = _load_json(live_drift_state_path, {})
    rows = _build_rows(
        report=report,
        positions_payload=positions_payload,
        positions=positions,
        live_drift_state=live_drift_state if isinstance(live_drift_state, Mapping) else {},
        generated_at=generated_at,
    )
    append_result = (
        append_position_control_ledger(rows, ledger_path=ledger_path)
        if persist
        else {"ledger_path": str(ledger_path), "rows_existing": 0, "rows_appended": len(rows), "rows_total": len(rows)}
    )
    state = _build_state(
        report=report,
        positions_payload=positions_payload,
        positions=positions,
        live_drift_state=live_drift_state if isinstance(live_drift_state, Mapping) else {},
        rows=rows,
        append_result=append_result,
        generated_at=generated_at,
    )
    if report.get("status") != "ok":
        state["status"] = str(report.get("status") or "missing_report")
        state["ok_to_add_control_pass"] = False
        blockers = set(state.get("ok_to_add_control_blockers", []))
        blockers.add("missing_daily_report")
        state["ok_to_add_control_blockers"] = sorted(blockers)
    if not positions_payload:
        state["status"] = "positions_unavailable"
        state["ok_to_add_control_pass"] = False
        blockers = set(state.get("ok_to_add_control_blockers", []))
        blockers.add("positions_unavailable")
        state["ok_to_add_control_blockers"] = sorted(blockers)
    if persist:
        _write_json_best_effort(state, state_path)
    return {"state": state, "rows": rows, "append_result": dict(append_result)}
