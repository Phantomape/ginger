"""Shared fail-closed execution sizing contract for paper sleeves.

Paper notionals are evidence units used by historical and forward ledgers.
They are not executable order sizes. This module keeps that distinction
machine-readable and only emits an experiment notional when the sleeve has a
complete execution envelope and all activation gates are open.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any


RULE_VERSION = "paper_sleeve_execution_sizing_contract_v1"
SCHEMA_VERSION = 1

PAPER_NOTIONAL_FIELDS = (
    "paper_notional_usd",
    "paper_event_notional_usd",
    "notional_usd",
    "notional",
    "intended_notional",
)

ENVELOPE_FIELD_ALIASES = {
    "max_position_notional_usd": (
        "max_position_notional_usd",
        "base_notional",
        "base_notional_usd",
        "event_notional_usd",
    ),
    "max_capital_pct": (
        "max_capital_pct",
        "max_capital_pct_of_bucket",
        "max_portfolio_pct",
    ),
    "min_dollar_volume": (
        "min_dollar_volume",
        "min_avg_dollar_volume_20d",
    ),
    "slippage": ("slippage_bps", "slippage_model"),
    "max_displacement": ("max_displacement", "core_displacement"),
    "max_concurrent_positions": (
        "max_concurrent",
        "max_concurrent_positions",
        "max_positions",
    ),
    "order_semantics": ("order_semantics", "entry_timing"),
    "kill_switch_drawdown_pct": ("kill_switch_drawdown_pct",),
    "failure_policy": ("failure_policy", "missed_fill_policy", "halt_policy"),
}


def freeze_paper_notional(
    row: dict[str, Any],
    *,
    fallback_notional_usd: float | None,
    fallback_source: str,
) -> float | None:
    """Freeze a paper evidence notional on a candidate or pending row."""
    source_field = None
    notional = None
    for field in PAPER_NOTIONAL_FIELDS:
        parsed = _positive_float(row.get(field))
        if parsed is not None:
            notional = parsed
            source_field = field
            break
    if notional is None:
        notional = _positive_float(fallback_notional_usd)
        source_field = fallback_source if notional is not None else None
    if notional is None:
        return None

    row["paper_notional_usd"] = round(notional, 2)
    row["paper_notional_frozen"] = True
    row.setdefault(
        "paper_notional_source",
        source_field or fallback_source,
    )
    return round(notional, 2)


def freeze_pending_paper_notionals(
    state: dict[str, Any],
    *,
    resolver: Callable[[dict[str, Any]], float | None],
) -> int:
    """Backfill legacy pending rows and preserve already-frozen notionals."""
    backfilled = 0
    for row in state.get("pending_entries") or []:
        if not isinstance(row, dict):
            continue
        had_frozen_notional = _positive_float(row.get("paper_notional_usd")) is not None
        frozen = freeze_paper_notional(
            row,
            fallback_notional_usd=resolver(row),
            fallback_source="legacy_pending_config_backfill",
        )
        if frozen is not None and not had_frozen_notional:
            backfilled += 1
    return backfilled


def apply_execution_sizing_contracts(
    surfaces: Mapping[str, dict[str, Any] | None],
) -> dict[str, Any]:
    """Annotate daily paper surfaces and return a compact aggregate audit."""
    surface_rows = []
    pending_actions = []
    for surface_name, snapshot in surfaces.items():
        if not isinstance(snapshot, dict):
            snapshot = {}
        contract = apply_execution_sizing_contract(
            snapshot,
            surface_name=surface_name,
        )
        surface_rows.append(_surface_summary(surface_name, snapshot, contract))
        pending_actions.extend(
            _pending_action_summaries(surface_name, snapshot)
        )

    status_counts: dict[str, int] = {}
    for row in surface_rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    unresolved_pending_action_count = sum(
        int(row.get("unresolved_pending_action_count") or 0) for row in surface_rows
    )
    effective_pending_action_count = sum(
        max(
            int(row.get("pending_count") or 0),
            int(row.get("pending_row_count") or 0),
        )
        for row in surface_rows
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "read_only": True,
        "trade_enabled": False,
        "alters_orders": False,
        "surface_count": len(surface_rows),
        "envelope_declared_count": sum(
            bool(row.get("execution_envelope_declared")) for row in surface_rows
        ),
        "envelope_complete_count": sum(
            bool(row.get("execution_envelope_complete")) for row in surface_rows
        ),
        "pending_action_count": effective_pending_action_count,
        "observed_pending_action_count": len(pending_actions),
        "unresolved_pending_action_count": unresolved_pending_action_count,
        "executable_pending_action_count": sum(
            row.get("experiment_notional_usd") is not None for row in pending_actions
        ),
        "blocked_pending_action_count": unresolved_pending_action_count + sum(
            row.get("experiment_notional_usd") is None for row in pending_actions
        ),
        "status_counts": status_counts,
        "pending_actions": pending_actions,
        "surfaces": surface_rows,
        "production_impact": {
            "shared_policy_changed": True,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "production_signal_path_changed": False,
            "alters_candidate_selection": False,
            "alters_paper_notional": False,
            "alters_paper_pnl": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
    }


def apply_execution_sizing_contract(
    snapshot: dict[str, Any],
    *,
    surface_name: str,
) -> dict[str, Any]:
    """Attach one normalized, fail-closed execution contract to a snapshot."""
    envelope, envelope_source = _declared_envelope(snapshot)
    canonical_envelope, missing_envelope_fields = _canonical_envelope(envelope)
    envelope_declared = envelope is not None
    envelope_complete = envelope_declared and not missing_envelope_fields

    forward_gate = snapshot.get("forward_paper_gate")
    forward_gate_declared = isinstance(forward_gate, dict)
    forward_gate_passed = bool((forward_gate or {}).get("passed", False))
    trade_enabled = bool(snapshot.get("trade_enabled", False))
    paper_enabled = bool(snapshot.get("paper_enabled", False))
    pending_rows = _pending_rows(snapshot)
    declared_pending_count = _nonnegative_int(
        snapshot.get("pending_count"),
        default=len(pending_rows),
    )

    blockers = []
    if not paper_enabled:
        blockers.append("paper_snapshot_disabled")
    if not envelope_declared:
        blockers.append("execution_envelope_undeclared")
    elif not envelope_complete:
        blockers.append("execution_envelope_incomplete")
    if not forward_gate_declared:
        blockers.append("forward_paper_gate_undeclared")
    elif not forward_gate_passed:
        blockers.append("forward_paper_gate_blocked")
    if not trade_enabled:
        blockers.append("trade_adapter_disabled")
    if declared_pending_count > len(pending_rows):
        blockers.append("pending_action_rows_unavailable")

    annotated_rows = 0
    executable_rows = 0
    missing_paper_notional_rows = 0
    root_paper_notionals = set(_root_paper_notionals(snapshot))
    row_fallback_notional = (
        next(iter(root_paper_notionals)) if len(root_paper_notionals) == 1 else None
    )
    paper_notional_values = set(root_paper_notionals)
    for row in _candidate_and_pending_rows(snapshot):
        paper_notional = freeze_paper_notional(
            row,
            fallback_notional_usd=row_fallback_notional,
            fallback_source="snapshot_unique_paper_notional",
        )
        row_blockers = list(blockers)
        if paper_notional is None:
            row_blockers.append("paper_notional_missing")
            missing_paper_notional_rows += 1
        else:
            paper_notional_values.add(paper_notional)

        experiment_notional = None
        if not row_blockers and paper_notional is not None:
            cap = _positive_float(canonical_envelope.get("max_position_notional_usd"))
            experiment_notional = round(min(paper_notional, cap), 2) if cap else paper_notional
            executable_rows += 1
        row["experiment_notional_usd"] = experiment_notional
        row["execution_sizing_status"] = "ready" if experiment_notional else "blocked"
        row["execution_sizing_blockers"] = row_blockers
        annotated_rows += 1

    status = "ready" if not blockers else "blocked"
    contract = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "surface_name": surface_name,
        "status": status,
        "read_only": True,
        "trade_enabled": trade_enabled,
        "alters_orders": False,
        "paper_notional_role": "evidence_only_not_an_order_size",
        "paper_notional_values_usd": sorted(paper_notional_values),
        "paper_notional_frozen_on_pending": _pending_notionals_frozen(snapshot),
        "execution_envelope": {
            "declared": envelope_declared,
            "complete": envelope_complete,
            "source": envelope_source,
            "missing_fields": missing_envelope_fields,
            "canonical": canonical_envelope,
        },
        "forward_gate": {
            "declared": forward_gate_declared,
            "passed": forward_gate_passed,
            "status": (forward_gate or {}).get("status") if forward_gate_declared else None,
        },
        "blockers": blockers,
        "annotated_candidate_pending_rows": annotated_rows,
        "executable_candidate_pending_rows": executable_rows,
        "missing_paper_notional_rows": missing_paper_notional_rows,
        "declared_pending_count": declared_pending_count,
        "observed_pending_row_count": len(pending_rows),
        "unresolved_pending_action_count": max(
            0, declared_pending_count - len(pending_rows)
        ),
        "experiment_notional_usd": None,
    }
    snapshot["execution_sizing_contract"] = contract
    return contract


def _declared_envelope(
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    raw = snapshot.get("execution_envelope")
    if isinstance(raw, dict):
        return deepcopy(raw), "snapshot.execution_envelope"
    trade_plan = snapshot.get("trade_plan")
    if isinstance(trade_plan, dict) and any(
        key in trade_plan for key in ("event_notional_usd", "max_portfolio_pct", "max_positions")
    ):
        envelope = {
            "max_position_notional_usd": trade_plan.get("event_notional_usd"),
            "max_capital_pct": trade_plan.get("max_portfolio_pct"),
            "max_concurrent_positions": trade_plan.get("max_positions"),
            "order_semantics": "next_session_open",
        }
        return envelope, "snapshot.trade_plan"
    return None, None


def _canonical_envelope(
    envelope: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    if envelope is None:
        return {}, list(ENVELOPE_FIELD_ALIASES)
    canonical = {}
    missing = []
    for canonical_field, aliases in ENVELOPE_FIELD_ALIASES.items():
        value = _first_present(envelope, aliases)
        canonical[canonical_field] = value
        if not _valid_envelope_field(canonical_field, value):
            missing.append(canonical_field)
    return canonical, missing


def _valid_envelope_field(field: str, value: Any) -> bool:
    if field in {"max_position_notional_usd", "min_dollar_volume"}:
        return _positive_float(value) is not None
    if field in {"max_capital_pct", "kill_switch_drawdown_pct"}:
        parsed = _positive_float(value)
        return parsed is not None and parsed <= 1.0
    if field == "max_concurrent_positions":
        parsed = _positive_float(value)
        return parsed is not None and parsed.is_integer()
    if field in {"slippage", "max_displacement"}:
        if isinstance(value, (int, float)):
            return math.isfinite(float(value)) and float(value) >= 0
        return isinstance(value, str) and bool(value.strip())
    if field in {"order_semantics", "failure_policy"}:
        return isinstance(value, str) and bool(value.strip())
    return value is not None


def _first_present(source: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in source and source[field] is not None:
            return source[field]
    return None


def _candidate_and_pending_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ("candidate", "candidates", "new_pending_entries", "pending_entries"):
        value = snapshot.get(key)
        if isinstance(value, dict):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    unique = []
    seen = set()
    for row in rows:
        identity = id(row)
        if identity not in seen:
            unique.append(row)
            seen.add(identity)
    return unique


def _root_paper_notionals(snapshot: dict[str, Any]) -> list[float]:
    values = []
    for source in (snapshot, snapshot.get("parameters") or {}):
        if not isinstance(source, dict):
            continue
        for field in ("paper_notional_usd", "event_notional_usd", "fallback_paper_notional_usd"):
            parsed = _positive_float(source.get(field))
            if parsed is not None:
                values.append(round(parsed, 2))
    return values


def _pending_notionals_frozen(snapshot: dict[str, Any]) -> bool:
    pending = _pending_rows(snapshot)
    return all(
        bool(row.get("paper_notional_frozen"))
        and _positive_float(row.get("paper_notional_usd")) is not None
        for row in pending
    )


def _surface_summary(
    surface_name: str,
    snapshot: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    envelope = contract.get("execution_envelope") or {}
    return {
        "surface": surface_name,
        "sleeve": snapshot.get("sleeve"),
        "status": contract.get("status"),
        "paper_enabled": bool(snapshot.get("paper_enabled", False)),
        "trade_enabled": bool(snapshot.get("trade_enabled", False)),
        "candidate_count": int(snapshot.get("candidate_count") or 0),
        "pending_count": int(snapshot.get("pending_count") or 0),
        "pending_row_count": int(contract.get("observed_pending_row_count") or 0),
        "unresolved_pending_action_count": int(
            contract.get("unresolved_pending_action_count") or 0
        ),
        "paper_notional_values_usd": contract.get("paper_notional_values_usd") or [],
        "paper_notional_frozen_on_pending": bool(
            contract.get("paper_notional_frozen_on_pending")
        ),
        "execution_envelope_declared": bool(envelope.get("declared")),
        "execution_envelope_complete": bool(envelope.get("complete")),
        "blockers": list(contract.get("blockers") or []),
    }


def _pending_action_summaries(
    surface_name: str,
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    out = []
    for row in _pending_rows(snapshot):
        out.append(
            {
                "surface": surface_name,
                "sleeve": snapshot.get("sleeve"),
                "ticker": row.get("ticker"),
                "status": row.get("status") or row.get("paper_status"),
                "signal_date": row.get("signal_date")
                or row.get("date")
                or row.get("source_event_date"),
                "entry_timing": row.get("entry_semantics")
                or row.get("entry_timing")
                or row.get("intended_entry_timing"),
                "paper_notional_usd": _positive_float(row.get("paper_notional_usd")),
                "paper_notional_role": "evidence_only_not_an_order_size",
                "experiment_notional_usd": row.get("experiment_notional_usd"),
                "execution_sizing_status": row.get("execution_sizing_status"),
                "execution_sizing_blockers": list(
                    row.get("execution_sizing_blockers") or []
                ),
            }
        )
    return out


def _pending_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for key in ("pending_entries", "new_pending_entries"):
        for row in snapshot.get(key) or []:
            if not isinstance(row, dict):
                continue
            logical_identity = (
                row.get("ticker"),
                row.get("signal_date") or row.get("date") or row.get("source_event_date"),
                row.get("sleeve") or row.get("source"),
                row.get("status") or row.get("paper_status"),
            )
            identity = row.get("decision_id") or (
                logical_identity if any(logical_identity) else id(row)
            )
            if identity in seen:
                continue
            rows.append(row)
            seen.add(identity)
    return rows


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)
