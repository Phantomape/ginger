"""Default-off external event sleeve bundle attribution.

This module aggregates the existing default-off Form 4, SEC negative-reaction,
and SEC governance/procedural paper sleeves into one production-visible bundle.
It is an attribution surface only: it does not emit orders, change core
ranking, size positions, or consume A/B slots.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


SLEEVE_NAME = "DEFAULT_OFF_EVENT_OVERLAY_BUNDLE_PAPER"
STATE_SCHEMA_VERSION = 2

SOURCE_ORDER = (
    ("form4_meaningful_purchase", "Form 4 meaningful purchase"),
    ("sec_negative_reaction", "SEC negative reaction"),
    ("sec_governance_procedural", "SEC governance/procedural"),
)

SOURCE_PRIORITY = {
    "sec_governance_procedural": 0,
    "sec_negative_reaction": 1,
    "form4_meaningful_purchase": 2,
}

STATE_SURFACE_ADDON_RULE_VERSION = (
    "non_generic_positive_state_surface_front_rank_broad_breadth_governance_source_v4"
)
STATE_SURFACE_GENERIC_SURFACE = "balanced_state_leadership"
STATE_SURFACE_ROTATION_TILT_SURFACE = "rotation_breakout_leadership"
STATE_SURFACE_BROAD_BREADTH_BUCKET = "broad_breadth"
EVENT_SOURCE_QUALITY_SOURCE = "sec_governance_procedural"
TRADE_PLAN_RULE_VERSION = "event_bundle_forward_gated_trade_plan_v1"

DEFAULT_SOURCE_RULE_VERSIONS = {
    "form4_meaningful_purchase": "form4_meaningful_purchase_ge_500k_v1",
    "sec_negative_reaction": "sec_negative_language_negative_reaction_v1",
    "sec_governance_procedural": "sec_governance_procedural_mild_reaction_v1",
}

REQUIRED_CANDIDATE_FIELDS = (
    "source",
    "rule_version",
    "ticker",
    "usable_trade_date",
    "entry_date",
    "event_notional_usd",
    "hold_days",
    "dedupe_key",
    "counterfactuals",
    "alters_orders",
)

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "event_notional_usd": 10_000.0,
    "per_source_max_positions": 1,
    "hold_days": 10,
    "source_names": [source for source, _ in SOURCE_ORDER],
    "micro_live_notional_usd": 2_500.0,
    "micro_live_max_portfolio_pct": 0.025,
    "micro_live_max_positions": 1,
    "trade_adapter_requires_forward_gate": True,
    "forward_gate_min_closed_trades": 15,
    "forward_gate_min_sources": 2,
    "forward_gate_min_win_rate": 0.55,
    "forward_gate_max_drawdown_pct": 0.08,
    "forward_gate_max_source_pnl_share": 0.70,
    "kill_consecutive_closed_losses": 3,
    "kill_recent_source_trades": 5,
    "kill_recent_source_min_win_rate": 0.40,
    "kill_drawdown_notional_fraction": 0.50,
    "state_surface_addon_paper_enabled": True,
    "state_surface_addon_scalar": 2.0,
    "state_surface_rotation_tilt_surface": STATE_SURFACE_ROTATION_TILT_SURFACE,
    "state_surface_rotation_tilt_scalar": 3.0,
    "state_surface_front_rank_rotation_tilt_enabled": True,
    "state_surface_front_rank_rotation_max_rank_pct": 0.20,
    "state_surface_front_rank_rotation_tilt_scalar": 4.0,
    "state_surface_broad_breadth_tilt_enabled": True,
    "state_surface_broad_breadth_bucket": STATE_SURFACE_BROAD_BREADTH_BUCKET,
    "state_surface_broad_breadth_tilt_scalar": 1.25,
    "state_surface_addon_generic_surface": STATE_SURFACE_GENERIC_SURFACE,
    "event_source_quality_tilt_enabled": True,
    "event_source_quality_source": EVENT_SOURCE_QUALITY_SOURCE,
    "event_source_quality_tilt_scalar": 2.0,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_event_sleeve_bundle_snapshot(
    *,
    as_of: str,
    form4_event_queue: dict[str, Any] | None = None,
    sec_negative_event_queue: dict[str, Any] | None = None,
    sec_governance_event_queue: dict[str, Any] | None = None,
    state_surface_queue: dict[str, Any] | None = None,
    form4_event_sleeve: dict[str, Any] | None = None,
    sec_negative_event_sleeve: dict[str, Any] | None = None,
    sec_governance_event_sleeve: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False

    raw_sources = {
        "form4_meaningful_purchase": form4_event_sleeve,
        "sec_negative_reaction": sec_negative_event_sleeve,
        "sec_governance_procedural": sec_governance_event_sleeve,
    }
    raw_queues = {
        "form4_meaningful_purchase": form4_event_queue,
        "sec_negative_reaction": sec_negative_event_queue,
        "sec_governance_procedural": sec_governance_event_queue,
    }
    source_summaries = {}
    open_positions = []
    closed_positions = []
    closed_positions_today = []
    new_pending_entries = []
    skipped_entries_today = []

    for source, label in SOURCE_ORDER:
        snapshot = raw_sources.get(source)
        summary = _summarize_source(source, label, snapshot)
        source_summaries[source] = summary
        open_positions.extend(_tag_rows(source, snapshot, "open_positions"))
        closed_positions.extend(_tag_rows(source, snapshot, "closed_positions"))
        closed_positions_today.extend(
            _tag_rows(source, snapshot, "closed_positions_today")
        )
        new_pending_entries.extend(_tag_rows(source, snapshot, "new_pending_entries"))
        skipped_entries_today.extend(_tag_rows(source, snapshot, "skipped_entries_today"))

    raw_candidates = _normalise_bundle_candidates(
        queues=raw_queues,
        sleeves=raw_sources,
        config=cfg,
    )
    accepted_candidates, deduped_candidates = _dedupe_candidates(raw_candidates)
    accepted_candidates = apply_state_surface_addon_to_event_candidates(
        accepted_candidates,
        state_surface_queue=state_surface_queue,
        config=cfg,
    )
    deduped_candidates = apply_state_surface_addon_to_event_candidates(
        deduped_candidates,
        state_surface_queue=state_surface_queue,
        config=cfg,
    )
    state_surface_addon = _state_surface_addon_summary(
        accepted_candidates,
        state_surface_queue=state_surface_queue,
        config=cfg,
    )
    schema_audit = _candidate_schema_audit(accepted_candidates)
    totals = _aggregate_totals(source_summaries)
    all_closed = closed_positions or closed_positions_today
    forward_gate = evaluate_forward_paper_gate(
        closed_positions=all_closed,
        open_positions=open_positions,
        source_summaries=source_summaries,
        schema_audit=schema_audit,
        config=cfg,
    )
    kill_switch = evaluate_event_bundle_kill_switch(
        closed_positions=all_closed,
        open_positions=open_positions,
        schema_audit=schema_audit,
        config=cfg,
    )
    bundle_snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": (
            "default_off_until_forward_gate_passes_and_live_adapter_is_explicitly_enabled"
        ),
        "source_count": len(SOURCE_ORDER),
        "sources_with_open_positions": sum(
            1 for row in source_summaries.values() if row["open_position_count"] > 0
        ),
        "sources_with_closed_positions": sum(
            1 for row in source_summaries.values() if row["closed_position_count"] > 0
        ),
        "candidate_count": totals["candidate_count"],
        "raw_candidate_count": len(raw_candidates),
        "deduped_candidate_count": len(accepted_candidates),
        "duplicate_candidate_count": len(deduped_candidates),
        "new_pending_count": totals["new_pending_count"],
        "filled_count": totals["filled_count"],
        "closed_count_today": totals["closed_count_today"],
        "skipped_count_today": totals["skipped_count_today"],
        "pending_count": totals["pending_count"],
        "open_position_count": totals["open_position_count"],
        "closed_position_count": totals["closed_position_count"],
        "realized_pnl_to_date": totals["realized_pnl_to_date"],
        "unrealized_pnl": totals["unrealized_pnl"],
        "source_summaries": source_summaries,
        "state_surface_addon": state_surface_addon,
        "candidate_schema": {
            "required_fields": list(REQUIRED_CANDIDATE_FIELDS),
            "audit": schema_audit,
        },
        "candidates": accepted_candidates,
        "deduped_candidates": deduped_candidates,
        "dedupe_policy": {
            "same_source_key": "source+ticker+usable_trade_date+rule_version",
            "cross_source_key": "ticker+usable_trade_date",
            "source_priority": {
                source: priority
                for source, priority in sorted(
                    SOURCE_PRIORITY.items(),
                    key=lambda item: item[1],
                )
            },
        },
        "open_positions": open_positions,
        "closed_positions": all_closed,
        "closed_positions_today": closed_positions_today,
        "new_pending_entries": new_pending_entries,
        "skipped_entries_today": skipped_entries_today,
        "forward_paper_gate": forward_gate,
        "kill_switch": kill_switch,
        "micro_live_plan": {
            "status": "blocked" if not forward_gate["passed"] else "eligible_for_manual_enablement",
            "trade_enabled": False,
            "max_positions": int(cfg["micro_live_max_positions"]),
            "event_notional_usd": float(cfg["micro_live_notional_usd"]),
            "max_portfolio_pct": float(cfg["micro_live_max_portfolio_pct"]),
            "requires_explicit_config_change": True,
        },
        "parameters": dict(cfg),
        "production_impact": _production_impact(),
        "next_action": (
            "accumulate_closed_forward_paper_outcomes_before_trade_enabled_adapter"
        ),
    }
    bundle_snapshot["trade_plan"] = build_event_sleeve_bundle_trade_plan(
        bundle_snapshot,
        config=cfg,
    )
    return bundle_snapshot


def empty_event_sleeve_bundle_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "deduped_candidate_count": 0,
        "duplicate_candidate_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "source_summaries": {},
        "state_surface_addon": _empty_state_surface_addon_summary(reason),
        "candidate_schema": {
            "required_fields": list(REQUIRED_CANDIDATE_FIELDS),
            "audit": {
                "valid": False,
                "missing_required_field_count": 1,
                "rows_with_missing_required_fields": [
                    {
                        "row_index": None,
                        "ticker": None,
                        "source": None,
                        "missing_fields": ["source_snapshot"],
                    }
                ],
            },
        },
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "kill_switch": {"triggered": True, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def evaluate_forward_paper_gate(
    *,
    closed_positions: list[dict[str, Any]],
    open_positions: list[dict[str, Any]] | None = None,
    source_summaries: dict[str, dict[str, Any]] | None = None,
    schema_audit: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    closed = [row for row in closed_positions or [] if isinstance(row, dict)]
    realized_pnl = round(sum(_money(row.get("pnl")) for row in closed), 2)
    closed_count = len(closed)
    wins = sum(1 for row in closed if _money(row.get("pnl")) > 0)
    win_rate = round(wins / closed_count, 4) if closed_count else None
    source_pnl = _pnl_by_source(closed, source_summaries or {})
    represented_sources = sorted(
        source
        for source, pnl in source_pnl.items()
        if _source_closed_count(closed, source, source_summaries or {}) > 0
    )
    source_pnl_share = _max_positive_source_pnl_share(source_pnl)
    drawdown = _closed_pnl_drawdown(closed, cfg)
    schema_valid = bool((schema_audit or {}).get("valid", False))

    checks = {
        "min_closed_trades": closed_count >= int(cfg["forward_gate_min_closed_trades"]),
        "min_sources": len(represented_sources) >= int(cfg["forward_gate_min_sources"]),
        "positive_net_pnl": realized_pnl > 0,
        "min_win_rate": win_rate is not None
        and win_rate >= float(cfg["forward_gate_min_win_rate"]),
        "max_drawdown": drawdown["max_drawdown_pct"] is not None
        and drawdown["max_drawdown_pct"] <= float(cfg["forward_gate_max_drawdown_pct"]),
        "max_source_concentration": source_pnl_share is not None
        and source_pnl_share <= float(cfg["forward_gate_max_source_pnl_share"]),
        "schema_valid": schema_valid,
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": closed_count,
            "represented_sources": represented_sources,
            "realized_pnl": realized_pnl,
            "win_rate": win_rate,
            "source_pnl": source_pnl,
            "max_positive_source_pnl_share": source_pnl_share,
            **drawdown,
        },
        "thresholds": {
            "min_closed_trades": int(cfg["forward_gate_min_closed_trades"]),
            "min_sources": int(cfg["forward_gate_min_sources"]),
            "min_win_rate": float(cfg["forward_gate_min_win_rate"]),
            "max_drawdown_pct": float(cfg["forward_gate_max_drawdown_pct"]),
            "max_source_pnl_share": float(cfg["forward_gate_max_source_pnl_share"]),
        },
        "open_position_count": len(open_positions or []),
        "trade_enabled_after_gate": False,
    }


def evaluate_event_bundle_kill_switch(
    *,
    closed_positions: list[dict[str, Any]],
    open_positions: list[dict[str, Any]] | None = None,
    schema_audit: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    closed = sorted(
        [row for row in closed_positions or [] if isinstance(row, dict)],
        key=lambda row: (
            str(row.get("exit_date") or row.get("entry_date") or ""),
            str(row.get("ticker") or ""),
        ),
    )
    open_rows = [row for row in open_positions or [] if isinstance(row, dict)]
    consecutive_losses = _trailing_consecutive_losses(closed)
    recent_source_failures = _recent_source_failures(closed, cfg)
    realized = sum(_money(row.get("pnl")) for row in closed)
    unrealized = sum(_money(row.get("net_pnl_if_closed_now") or row.get("unrealized_pnl")) for row in open_rows)
    combined_pnl = round(realized + unrealized, 2)
    drawdown_trigger_usd = round(
        float(cfg["event_notional_usd"])
        * float(cfg["kill_drawdown_notional_fraction"]),
        2,
    )
    schema_valid = bool((schema_audit or {}).get("valid", False))
    reasons = []
    if consecutive_losses >= int(cfg["kill_consecutive_closed_losses"]):
        reasons.append("consecutive_closed_losses")
    if combined_pnl < -drawdown_trigger_usd:
        reasons.append("bundle_pnl_drawdown")
    if recent_source_failures:
        reasons.append("recent_source_win_rate_breach")
    if not schema_valid:
        reasons.append("schema_invalid")
    return {
        "triggered": bool(reasons),
        "status": "halt" if reasons else "clear",
        "reasons": reasons,
        "metrics": {
            "closed_trades": len(closed),
            "trailing_consecutive_losses": consecutive_losses,
            "combined_realized_unrealized_pnl": combined_pnl,
            "drawdown_trigger_usd": drawdown_trigger_usd,
            "recent_source_failures": recent_source_failures,
        },
        "thresholds": {
            "consecutive_closed_losses": int(cfg["kill_consecutive_closed_losses"]),
            "drawdown_notional_fraction": float(cfg["kill_drawdown_notional_fraction"]),
            "recent_source_trades": int(cfg["kill_recent_source_trades"]),
            "recent_source_min_win_rate": float(cfg["kill_recent_source_min_win_rate"]),
        },
    }


def build_event_sleeve_bundle_trade_plan(
    snapshot: dict[str, Any] | None,
    *,
    config: dict[str, Any] | None = None,
    portfolio_value: float | None = None,
) -> dict[str, Any]:
    """Build the shared executable plan for the default-off event bundle.

    The helper is intentionally inert unless the caller explicitly enables
    trading and the forward paper gate is already passed.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    bundle = snapshot if isinstance(snapshot, dict) else {}
    schema_audit = (bundle.get("candidate_schema") or {}).get("audit") or {}
    forward_gate = bundle.get("forward_paper_gate") or {}
    kill_switch = bundle.get("kill_switch") or {}

    block_reasons = []
    if not bool(cfg.get("trade_enabled", False)):
        block_reasons.append("trade_adapter_disabled")
    if bool(cfg.get("trade_adapter_requires_forward_gate", True)) and not bool(
        forward_gate.get("passed", False)
    ):
        block_reasons.append("forward_paper_gate_blocked")
    if bool(kill_switch.get("triggered", False)):
        block_reasons.append("kill_switch_triggered")
    if not bool(schema_audit.get("valid", False)):
        block_reasons.append("candidate_schema_invalid")
    if not bool(bundle.get("paper_enabled", False)):
        block_reasons.append("paper_snapshot_disabled")

    actions: list[dict[str, Any]] = []
    if not block_reasons:
        candidates = _trade_plan_candidate_rows(bundle.get("candidates") or [])
        max_positions = max(0, int(cfg.get("micro_live_max_positions") or 0))
        actions = [
            _event_trade_action_from_candidate(
                row,
                config=cfg,
                portfolio_value=portfolio_value,
            )
            for row in candidates[:max_positions]
        ]

    if actions:
        status = "ready"
    elif block_reasons:
        status = "blocked"
    else:
        status = "no_candidates"

    return {
        "rule_version": TRADE_PLAN_RULE_VERSION,
        "status": status,
        "trade_enabled": bool(actions),
        "alters_orders": bool(actions),
        "block_reasons": block_reasons,
        "actions": actions,
        "action_count": len(actions),
        "max_positions": int(cfg.get("micro_live_max_positions") or 0),
        "event_notional_usd": float(cfg.get("micro_live_notional_usd") or 0.0),
        "max_portfolio_pct": float(cfg.get("micro_live_max_portfolio_pct") or 0.0),
        "requires_forward_gate": bool(
            cfg.get("trade_adapter_requires_forward_gate", True)
        ),
        "forward_paper_gate": {
            "passed": bool(forward_gate.get("passed", False)),
            "status": forward_gate.get("status"),
            "reasons": list(forward_gate.get("reasons") or []),
        },
        "kill_switch": {
            "triggered": bool(kill_switch.get("triggered", False)),
            "status": kill_switch.get("status"),
            "reasons": list(kill_switch.get("reasons") or []),
        },
        "candidate_schema": {
            "valid": bool(schema_audit.get("valid", False)),
            "missing_required_field_count": int(
                schema_audit.get("missing_required_field_count") or 0
            ),
        },
        "production_impact": {
            "shared_policy_changed": True,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "parity_test_added": True,
            "replay_only": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": bool(actions),
            "alters_orders": bool(actions),
            "scope": "default_off_event_overlay_bundle_trade_adapter",
        },
    }


def _trade_plan_candidate_rows(candidates: list[Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in candidates
        if isinstance(row, dict)
        and str(row.get("candidate_status") or "") in {"candidate", "pending"}
        and bool(row.get("ticker"))
    ]
    return sorted(
        rows,
        key=lambda row: (
            row.get("usable_trade_date") or "",
            row.get("source_priority", 99),
            row.get("ticker") or "",
        ),
    )


def _event_trade_action_from_candidate(
    candidate: dict[str, Any],
    *,
    config: dict[str, Any],
    portfolio_value: float | None,
) -> dict[str, Any]:
    micro_notional = float(config.get("micro_live_notional_usd") or 0.0)
    max_portfolio_pct = float(config.get("micro_live_max_portfolio_pct") or 0.0)
    paper_notional = _float_or_none(candidate.get("paper_event_notional_usd"))
    base_notional = _float_or_none(candidate.get("event_notional_usd"))
    notional = micro_notional or paper_notional or base_notional or 0.0
    if paper_notional is not None:
        notional = min(notional, paper_notional)
    if portfolio_value is not None and max_portfolio_pct > 0:
        notional = min(notional, float(portfolio_value) * max_portfolio_pct)
    notional = round(max(0.0, notional), 2)

    state_surface_addon = deepcopy(candidate.get("state_surface_addon") or {})
    if state_surface_addon:
        state_surface_addon["trade_enabled"] = True
        state_surface_addon["alters_orders"] = True

    return {
        "sleeve": SLEEVE_NAME,
        "rule_version": TRADE_PLAN_RULE_VERSION,
        "action": "BUY",
        "ticker": str(candidate.get("ticker") or "").upper(),
        "source": candidate.get("source"),
        "source_label": candidate.get("source_label"),
        "source_rule_version": candidate.get("rule_version"),
        "decision_id": candidate.get("decision_id"),
        "usable_trade_date": candidate.get("usable_trade_date"),
        "entry_date": candidate.get("entry_date"),
        "entry_timing": "next_session_open",
        "notional_usd": notional,
        "max_portfolio_pct": max_portfolio_pct,
        "hold_days": _int(candidate.get("hold_days")),
        "paper_event_notional_usd": paper_notional,
        "base_event_notional_usd": base_notional,
        "paper_notional_scalar": _float_or_none(candidate.get("paper_notional_scalar")),
        "state_surface_addon": state_surface_addon,
        "counterfactuals": deepcopy(candidate.get("counterfactuals") or {}),
        "trade_enabled": True,
        "alters_orders": True,
    }


def _normalise_bundle_candidates(
    *,
    queues: dict[str, dict[str, Any] | None],
    sleeves: dict[str, dict[str, Any] | None],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, label in SOURCE_ORDER:
        queue = queues.get(source)
        if isinstance(queue, dict) and queue.get("candidates"):
            rule_version = str(
                queue.get("rule_version")
                or DEFAULT_SOURCE_RULE_VERSIONS.get(source)
                or "unknown_rule"
            )
            for raw in queue.get("candidates") or []:
                if isinstance(raw, dict):
                    rows.append(
                        _normalise_candidate_row(
                            source=source,
                            source_label=label,
                            raw=raw,
                            rule_version=rule_version,
                            status="candidate",
                            config=config,
                        )
                    )
            continue

        sleeve = sleeves.get(source)
        if not isinstance(sleeve, dict):
            continue
        rule_version = str(DEFAULT_SOURCE_RULE_VERSIONS.get(source) or "unknown_rule")
        for bucket, status in (
            ("new_pending_entries", "pending"),
            ("pending_entries", "pending"),
            ("open_positions", "open"),
            ("closed_positions", "closed"),
            ("closed_positions_today", "closed_today"),
            ("skipped_entries_today", "skipped"),
        ):
            for raw in sleeve.get(bucket) or []:
                if isinstance(raw, dict):
                    rows.append(
                        _normalise_candidate_row(
                            source=source,
                            source_label=label,
                            raw=raw,
                            rule_version=rule_version,
                            status=status,
                            config=config,
                        )
                    )
    return rows


def _normalise_candidate_row(
    *,
    source: str,
    source_label: str,
    raw: dict[str, Any],
    rule_version: str,
    status: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    candidate = raw.get("candidate") or raw.get("source_candidate") or raw
    ticker = str(raw.get("ticker") or candidate.get("ticker") or "").upper()
    usable_trade_date = _date10(
        candidate.get("usable_trade_date")
        or raw.get("source_event_date")
        or raw.get("usable_trade_date")
        or raw.get("entry_date")
    )
    entry_date = _date10(
        raw.get("entry_date") or candidate.get("entry_date") or usable_trade_date
    )
    event_notional = _float_or_none(
        raw.get("notional")
        or raw.get("event_notional_usd")
        or candidate.get("event_notional_usd")
        or config.get("event_notional_usd")
    )
    hold_days = _int(raw.get("hold_days") or candidate.get("hold_days") or config.get("hold_days"))
    decision_id = str(raw.get("decision_id") or candidate.get("decision_id") or "")
    source_unique_key = "|".join(
        [
            source,
            ticker,
            usable_trade_date or "unknown_date",
            rule_version,
        ]
    )
    cross_source_key = "|".join([ticker, usable_trade_date or "unknown_date"])
    return {
        "source": source,
        "source_label": source_label,
        "source_priority": SOURCE_PRIORITY[source],
        "rule_version": rule_version,
        "ticker": ticker,
        "usable_trade_date": usable_trade_date,
        "entry_date": entry_date,
        "event_notional_usd": event_notional,
        "hold_days": hold_days,
        "dedupe_key": source_unique_key,
        "cross_source_dedupe_key": cross_source_key,
        "decision_id": decision_id or source_unique_key,
        "candidate_status": status,
        "counterfactuals": deepcopy(
            candidate.get("counterfactuals")
            or candidate.get("counterfactual")
            or raw.get("counterfactuals")
            or raw.get("counterfactual")
            or {}
        ),
        "trade_enabled": False,
        "alters_orders": False,
        "pnl": _float_or_none(raw.get("pnl")),
        "net_return_pct": _float_or_none(raw.get("net_return_pct")),
        "source_payload": deepcopy(candidate),
    }


def _dedupe_candidates(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted_by_source_key: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []

    for row in sorted(
        candidates,
        key=lambda item: (
            item.get("dedupe_key") or "",
            item.get("source_priority", 99),
            item.get("decision_id") or "",
        ),
    ):
        key = str(row.get("dedupe_key") or "")
        if key in accepted_by_source_key:
            duplicates.append(
                _deduped_row(row, "duplicate_same_source_ticker_date_rule", accepted_by_source_key[key])
            )
            continue
        accepted_by_source_key[key] = row

    accepted: list[dict[str, Any]] = []
    by_cross_key: dict[str, dict[str, Any]] = {}
    for row in sorted(
        accepted_by_source_key.values(),
        key=lambda item: (
            item.get("cross_source_dedupe_key") or "",
            item.get("source_priority", 99),
            item.get("source") or "",
        ),
    ):
        key = str(row.get("cross_source_dedupe_key") or "")
        existing = by_cross_key.get(key)
        if existing is None:
            by_cross_key[key] = row
            accepted.append(row)
            continue
        if int(row.get("source_priority", 99)) < int(existing.get("source_priority", 99)):
            accepted.remove(existing)
            duplicates.append(
                _deduped_row(
                    existing,
                    "lower_priority_same_ticker_date",
                    row,
                )
            )
            by_cross_key[key] = row
            accepted.append(row)
        else:
            duplicates.append(
                _deduped_row(
                    row,
                    "lower_priority_same_ticker_date",
                    existing,
                )
            )
    accepted.sort(
        key=lambda row: (
            row.get("usable_trade_date") or "",
            row.get("source_priority", 99),
            row.get("ticker") or "",
        )
    )
    duplicates.sort(
        key=lambda row: (
            row.get("usable_trade_date") or "",
            row.get("source_priority", 99),
            row.get("ticker") or "",
        )
    )
    return accepted, duplicates


def _deduped_row(
    row: dict[str, Any],
    reason: str,
    kept: dict[str, Any],
) -> dict[str, Any]:
    out = deepcopy(row)
    out["dedupe_reason"] = reason
    out["kept_source"] = kept.get("source")
    out["kept_dedupe_key"] = kept.get("dedupe_key")
    return out


def apply_state_surface_addon_to_event_candidates(
    candidates: list[dict[str, Any]],
    *,
    state_surface_queue: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    state_by_ticker = _state_surface_candidates_by_ticker(state_surface_queue)
    return [
        _with_state_surface_addon(row, state_by_ticker.get(str(row.get("ticker") or "").upper()), cfg)
        for row in candidates
    ]


def _state_surface_candidates_by_ticker(
    state_surface_queue: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(state_surface_queue, dict):
        return {}
    rows = (
        state_surface_queue.get("scored_candidates")
        or state_surface_queue.get("candidates")
        or []
    )
    scored_count = _int(
        state_surface_queue.get("scored_candidate_count")
        or len(rows)
        or state_surface_queue.get("candidate_count")
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            candidate = deepcopy(row)
            if candidate.get("state_rank_pct") in (None, "") and scored_count:
                rank = _int(candidate.get("rank"))
                if rank > 0:
                    candidate["state_rank_pct"] = round(rank / scored_count, 6)
            out[ticker] = candidate
    return out


def _with_state_surface_addon(
    candidate: dict[str, Any],
    state_row: dict[str, Any] | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    out = deepcopy(candidate)
    base_notional = _float_or_none(out.get("event_notional_usd")) or float(config["event_notional_usd"])
    scalar = 1.0
    reason = "state_surface_ticker_not_scored"
    eligible = False
    surface = None
    score = None
    decision_date = None
    state_rank = None
    state_rank_pct = None
    breadth_bucket = None
    rotation_tilt = False
    front_rank_rotation_tilt = False
    broad_breadth_tilt = False
    broad_breadth_scalar = 1.0
    source_quality_tilt = False
    source_quality_source = str(
        config.get("event_source_quality_source") or EVENT_SOURCE_QUALITY_SOURCE
    )
    source_quality_scalar = 1.0

    if not bool(config.get("state_surface_addon_paper_enabled", True)):
        reason = "state_surface_addon_disabled"
    elif isinstance(state_row, dict):
        surface = state_row.get("surface") or state_row.get("state_surface")
        score = _float_or_none(state_row.get("score") or state_row.get("state_score"))
        decision_date = state_row.get("decision_date") or state_row.get("date")
        state_rank = _int(state_row.get("rank")) or None
        state_rank_pct = _float_or_none(
            state_row.get("state_rank_pct") or state_row.get("rank_pct")
        )
        breadth_bucket = (
            state_row.get("breadth_bucket")
            or state_row.get("state_breadth_bucket")
            or (state_row.get("state") or {}).get("breadth_bucket")
        )
        generic_surface = str(
            config.get("state_surface_addon_generic_surface") or STATE_SURFACE_GENERIC_SURFACE
        )
        if score is None:
            reason = "missing_state_surface_score"
        elif score <= 0:
            reason = "nonpositive_state_surface_score"
        elif str(surface or "") == generic_surface:
            reason = "generic_state_surface"
        else:
            eligible = True
            rotation_surface = str(
                config.get("state_surface_rotation_tilt_surface")
                or STATE_SURFACE_ROTATION_TILT_SURFACE
            )
            rotation_tilt = str(surface or "") == rotation_surface
            if rotation_tilt:
                front_rank_enabled = bool(
                    config.get("state_surface_front_rank_rotation_tilt_enabled", True)
                )
                front_rank_max_pct = _float_or_none(
                    config.get("state_surface_front_rank_rotation_max_rank_pct")
                )
                if (
                    front_rank_enabled
                    and state_rank_pct is not None
                    and front_rank_max_pct is not None
                    and state_rank_pct <= front_rank_max_pct
                ):
                    scalar = float(config["state_surface_front_rank_rotation_tilt_scalar"])
                    reason = "eligible_front_rank_rotation_breakout_positive_state_surface"
                    front_rank_rotation_tilt = True
                else:
                    scalar = float(config["state_surface_rotation_tilt_scalar"])
                    reason = "eligible_rotation_breakout_positive_state_surface"
            else:
                scalar = float(config["state_surface_addon_scalar"])
                reason = "eligible_non_generic_positive_state_surface"
            broad_bucket = str(
                config.get("state_surface_broad_breadth_bucket")
                or STATE_SURFACE_BROAD_BREADTH_BUCKET
            )
            if (
                bool(config.get("state_surface_broad_breadth_tilt_enabled", True))
                and str(breadth_bucket or "") == broad_bucket
            ):
                broad_breadth_scalar = float(
                    config["state_surface_broad_breadth_tilt_scalar"]
                )
                scalar *= broad_breadth_scalar
                broad_breadth_tilt = True
                reason = f"{reason}_broad_breadth_support"

    state_surface_scalar = scalar
    state_adjusted_notional = base_notional * state_surface_scalar
    if (
        bool(config.get("event_source_quality_tilt_enabled", True))
        and str(out.get("source") or "") == source_quality_source
    ):
        source_quality_scalar = float(config["event_source_quality_tilt_scalar"])
        scalar *= source_quality_scalar
        source_quality_tilt = True
        reason = f"{reason}_sec_governance_source_quality"

    adjusted_notional = base_notional * scalar
    out["state_surface_addon"] = {
        "rule_version": STATE_SURFACE_ADDON_RULE_VERSION,
        "paper_enabled": bool(config.get("state_surface_addon_paper_enabled", True)),
        "trade_enabled": False,
        "eligible": eligible,
        "reason": reason,
        "scalar": round(scalar, 4),
        "state_surface_scalar": round(state_surface_scalar, 4),
        "source_quality_tilt": source_quality_tilt,
        "source_quality_source": source_quality_source,
        "source_quality_scalar": round(source_quality_scalar, 4),
        "base_event_notional_usd": round(base_notional, 2),
        "state_adjusted_event_notional_usd": round(state_adjusted_notional, 2),
        "adjusted_event_notional_usd": round(adjusted_notional, 2),
        "incremental_notional_usd": round(adjusted_notional - base_notional, 2),
        "state_surface_incremental_notional_usd": round(
            state_adjusted_notional - base_notional,
            2,
        ),
        "source_quality_incremental_notional_usd": round(
            adjusted_notional - state_adjusted_notional,
            2,
        ),
        "state_score": score,
        "state_surface": surface,
        "state_decision_date": decision_date,
        "state_rank": state_rank,
        "state_rank_pct": round(state_rank_pct, 6) if state_rank_pct is not None else None,
        "breadth_bucket": breadth_bucket,
        "rotation_tilt": rotation_tilt,
        "front_rank_rotation_tilt": front_rank_rotation_tilt,
        "broad_breadth_tilt": broad_breadth_tilt,
        "broad_breadth_scalar": round(broad_breadth_scalar, 4),
        "alters_orders": False,
    }
    out["paper_event_notional_usd"] = round(adjusted_notional, 2)
    out["paper_notional_scalar"] = round(scalar, 4)
    return out


def _state_surface_addon_summary(
    candidates: list[dict[str, Any]],
    *,
    state_surface_queue: dict[str, Any] | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    rows = [row.get("state_surface_addon") or {} for row in candidates]
    eligible = [row for row in rows if row.get("eligible")]
    rotation_eligible = [row for row in eligible if row.get("rotation_tilt")]
    front_rank_rotation_eligible = [
        row for row in rotation_eligible if row.get("front_rank_rotation_tilt")
    ]
    broad_breadth_eligible = [row for row in eligible if row.get("broad_breadth_tilt")]
    source_quality_eligible = [row for row in rows if row.get("source_quality_tilt")]
    adjusted = [row for row in rows if _money(row.get("incremental_notional_usd")) != 0.0]
    incremental = sum(_money(row.get("incremental_notional_usd")) for row in adjusted)
    rotation_incremental = sum(
        _money(row.get("state_surface_incremental_notional_usd"))
        for row in rotation_eligible
    )
    front_rank_rotation_incremental = sum(
        _money(row.get("state_surface_incremental_notional_usd"))
        for row in front_rank_rotation_eligible
    )
    broad_breadth_incremental = sum(
        _money(row.get("state_adjusted_event_notional_usd"))
        - (
            _money(row.get("base_event_notional_usd"))
            * (
                _money(row.get("state_surface_scalar"))
                / max(_money(row.get("broad_breadth_scalar")) or 1.0, 1e-9)
            )
        )
        for row in broad_breadth_eligible
    )
    source_quality_incremental = sum(
        _money(row.get("source_quality_incremental_notional_usd"))
        for row in source_quality_eligible
    )
    scored_count = 0
    if isinstance(state_surface_queue, dict):
        scored_count = _int(
            state_surface_queue.get("scored_candidate_count")
            or len(state_surface_queue.get("scored_candidates") or [])
            or state_surface_queue.get("candidate_count")
        )
    return {
        "rule_version": STATE_SURFACE_ADDON_RULE_VERSION,
        "paper_enabled": bool(config.get("state_surface_addon_paper_enabled", True)),
        "trade_enabled": False,
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(eligible),
        "rotation_tilt_candidate_count": len(rotation_eligible),
        "front_rank_rotation_tilt_candidate_count": len(front_rank_rotation_eligible),
        "broad_breadth_tilt_candidate_count": len(broad_breadth_eligible),
        "source_quality_tilt_candidate_count": len(source_quality_eligible),
        "eligible_fraction": round(len(eligible) / len(candidates), 4) if candidates else None,
        "scored_candidate_count": scored_count,
        "incremental_notional_usd": round(incremental, 2),
        "rotation_tilt_incremental_notional_usd": round(rotation_incremental, 2),
        "front_rank_rotation_tilt_incremental_notional_usd": round(
            front_rank_rotation_incremental,
            2,
        ),
        "broad_breadth_tilt_incremental_notional_usd": round(
            broad_breadth_incremental,
            2,
        ),
        "source_quality_tilt_incremental_notional_usd": round(
            source_quality_incremental,
            2,
        ),
        "eligible_surfaces": sorted(
            {
                str(row.get("state_surface"))
                for row in eligible
                if row.get("state_surface")
            }
        ),
        "parameters": {
            "eligible_scalar": float(config["state_surface_addon_scalar"]),
            "rotation_tilt_surface": str(
                config.get("state_surface_rotation_tilt_surface")
                or STATE_SURFACE_ROTATION_TILT_SURFACE
            ),
            "rotation_tilt_scalar": float(
                config["state_surface_rotation_tilt_scalar"]
            ),
            "front_rank_rotation_tilt_enabled": bool(
                config.get("state_surface_front_rank_rotation_tilt_enabled", True)
            ),
            "front_rank_rotation_max_rank_pct": float(
                config["state_surface_front_rank_rotation_max_rank_pct"]
            ),
            "front_rank_rotation_tilt_scalar": float(
                config["state_surface_front_rank_rotation_tilt_scalar"]
            ),
            "broad_breadth_tilt_enabled": bool(
                config.get("state_surface_broad_breadth_tilt_enabled", True)
            ),
            "broad_breadth_bucket": str(
                config.get("state_surface_broad_breadth_bucket")
                or STATE_SURFACE_BROAD_BREADTH_BUCKET
            ),
            "broad_breadth_tilt_scalar": float(
                config["state_surface_broad_breadth_tilt_scalar"]
            ),
            "source_quality_tilt_enabled": bool(
                config.get("event_source_quality_tilt_enabled", True)
            ),
            "source_quality_source": str(
                config.get("event_source_quality_source") or EVENT_SOURCE_QUALITY_SOURCE
            ),
            "source_quality_tilt_scalar": float(
                config["event_source_quality_tilt_scalar"]
            ),
            "generic_surface_not_eligible": str(
                config.get("state_surface_addon_generic_surface") or STATE_SURFACE_GENERIC_SURFACE
            ),
            "eligibility_rule": (
                "score > 0 and state_surface != generic_surface; "
                "rotation_breakout_leadership uses rotation_tilt_scalar; "
                "front-rank rotation rows use front_rank_rotation_tilt_scalar; "
                "broad_breadth rows multiply the active scalar; "
                "sec_governance_procedural rows multiply the final paper notional"
            ),
        },
        "production_impact": {
            "alters_orders": False,
            "alters_sizing": False,
            "trade_enabled": False,
            "scope": "default_off_event_bundle_paper_addon_attribution",
        },
    }


def _empty_state_surface_addon_summary(reason: str) -> dict[str, Any]:
    return {
        "rule_version": STATE_SURFACE_ADDON_RULE_VERSION,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "eligible_candidate_count": 0,
        "rotation_tilt_candidate_count": 0,
        "front_rank_rotation_tilt_candidate_count": 0,
        "broad_breadth_tilt_candidate_count": 0,
        "source_quality_tilt_candidate_count": 0,
        "eligible_fraction": None,
        "scored_candidate_count": 0,
        "incremental_notional_usd": 0.0,
        "rotation_tilt_incremental_notional_usd": 0.0,
        "front_rank_rotation_tilt_incremental_notional_usd": 0.0,
        "broad_breadth_tilt_incremental_notional_usd": 0.0,
        "source_quality_tilt_incremental_notional_usd": 0.0,
        "eligible_surfaces": [],
        "status": "blocked",
        "reason": reason,
        "production_impact": {
            "alters_orders": False,
            "alters_sizing": False,
            "trade_enabled": False,
        },
    }


def _candidate_schema_audit(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for idx, row in enumerate(candidates):
        missing = [
            field
            for field in REQUIRED_CANDIDATE_FIELDS
            if row.get(field) in (None, "", [])
        ]
        if missing:
            rows.append(
                {
                    "row_index": idx,
                    "ticker": row.get("ticker"),
                    "source": row.get("source"),
                    "missing_fields": missing,
                }
            )
    return {
        "valid": not rows,
        "candidate_count": len(candidates),
        "missing_required_field_count": sum(len(row["missing_fields"]) for row in rows),
        "rows_with_missing_required_fields": rows,
    }


def _summarize_source(
    source: str,
    label: str,
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {
            "source": source,
            "label": label,
            "available": False,
            "paper_enabled": False,
            "trade_enabled": False,
            "candidate_count": 0,
            "new_pending_count": 0,
            "filled_count": 0,
            "closed_count_today": 0,
            "skipped_count_today": 0,
            "pending_count": 0,
            "open_position_count": 0,
            "closed_position_count": 0,
            "realized_pnl_to_date": 0.0,
            "unrealized_pnl": 0.0,
            "status": "missing_snapshot",
        }
    return {
        "source": source,
        "label": label,
        "available": True,
        "paper_enabled": bool(snapshot.get("paper_enabled", False)),
        "trade_enabled": False,
        "candidate_count": _int(snapshot.get("candidate_count")),
        "new_pending_count": _int(snapshot.get("new_pending_count")),
        "filled_count": _int(snapshot.get("filled_count")),
        "closed_count_today": _int(snapshot.get("closed_count_today")),
        "skipped_count_today": _int(snapshot.get("skipped_count_today")),
        "pending_count": _int(snapshot.get("pending_count")),
        "open_position_count": _int(snapshot.get("open_position_count")),
        "closed_position_count": _int(snapshot.get("closed_position_count")),
        "realized_pnl_to_date": _money(snapshot.get("realized_pnl_to_date")),
        "unrealized_pnl": _money(snapshot.get("unrealized_pnl")),
        "status": snapshot.get("error") or "loaded",
    }


def _aggregate_totals(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    int_keys = (
        "candidate_count",
        "new_pending_count",
        "filled_count",
        "closed_count_today",
        "skipped_count_today",
        "pending_count",
        "open_position_count",
        "closed_position_count",
    )
    totals = {key: sum(row[key] for row in summaries.values()) for key in int_keys}
    totals["realized_pnl_to_date"] = round(
        sum(row["realized_pnl_to_date"] for row in summaries.values()),
        2,
    )
    totals["unrealized_pnl"] = round(
        sum(row["unrealized_pnl"] for row in summaries.values()),
        2,
    )
    return totals


def _tag_rows(
    source: str,
    snapshot: dict[str, Any] | None,
    key: str,
) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    rows = []
    for row in snapshot.get(key) or []:
        if isinstance(row, dict):
            tagged = deepcopy(row)
            tagged.setdefault("source", source)
            rows.append(tagged)
    return rows


def _pnl_by_source(
    closed_positions: list[dict[str, Any]],
    source_summaries: dict[str, dict[str, Any]],
) -> dict[str, float]:
    out = {source: 0.0 for source, _ in SOURCE_ORDER}
    counted = False
    for row in closed_positions:
        source = str(row.get("source") or "")
        if source in out:
            out[source] += _money(row.get("pnl"))
            counted = True
    if not counted:
        for source, summary in source_summaries.items():
            out[source] = _money(summary.get("realized_pnl_to_date"))
    return {source: round(value, 2) for source, value in out.items()}


def _source_closed_count(
    closed_positions: list[dict[str, Any]],
    source: str,
    source_summaries: dict[str, dict[str, Any]],
) -> int:
    direct = sum(1 for row in closed_positions if row.get("source") == source)
    if direct:
        return direct
    return _int((source_summaries.get(source) or {}).get("closed_position_count"))


def _max_positive_source_pnl_share(source_pnl: dict[str, float]) -> float | None:
    positive = [value for value in source_pnl.values() if value > 0]
    total_positive = sum(positive)
    if total_positive <= 0:
        return None
    return round(max(positive) / total_positive, 4)


def _closed_pnl_drawdown(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    rows = sorted(
        closed_positions,
        key=lambda row: (
            str(row.get("exit_date") or row.get("entry_date") or ""),
            str(row.get("ticker") or ""),
        ),
    )
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for row in rows:
        equity += _money(row.get("pnl"))
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    denominator = float(config["event_notional_usd"]) * len(SOURCE_ORDER)
    return {
        "max_drawdown_usd": round(max_dd, 2),
        "drawdown_denominator_usd": round(denominator, 2),
        "max_drawdown_pct": round(max_dd / denominator, 4) if denominator else None,
    }


def _trailing_consecutive_losses(closed_positions: list[dict[str, Any]]) -> int:
    count = 0
    for row in reversed(closed_positions):
        if _money(row.get("pnl")) < 0:
            count += 1
        else:
            break
    return count


def _recent_source_failures(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    failures = []
    sample_size = int(config["kill_recent_source_trades"])
    min_win_rate = float(config["kill_recent_source_min_win_rate"])
    by_source: dict[str, list[dict[str, Any]]] = {source: [] for source, _ in SOURCE_ORDER}
    for row in closed_positions:
        source = row.get("source")
        if source in by_source:
            by_source[source].append(row)
    for source, rows in by_source.items():
        recent = rows[-sample_size:]
        if len(recent) < sample_size:
            continue
        wins = sum(1 for row in recent if _money(row.get("pnl")) > 0)
        win_rate = wins / len(recent)
        if win_rate < min_win_rate:
            failures.append(
                {
                    "source": source,
                    "sample_size": len(recent),
                    "win_rate": round(win_rate, 4),
                    "threshold": min_win_rate,
                }
            )
    return failures


def _date10(value: Any) -> str | None:
    text = str(value or "")[:10]
    return text or None


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _money(value: Any) -> float:
    try:
        return round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "scope": "default_off_event_overlay_bundle_paper_attribution",
    }
