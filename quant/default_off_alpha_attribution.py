"""Read-only attribution surface for default-off alpha sleeves.

This module summarizes promotion readiness and blockers across paper/pilot
surfaces. It is deliberately non-executable: no entry, ranking, sizing, exit,
or order logic should read this payload as a trade rule.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


RULE_VERSION = "default_off_alpha_attribution_report_v1"


PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "parity_test_added": True,
    "replay_only": False,
    "default_off_attribution_only": True,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round_money(value: Any) -> float | None:
    parsed = _as_float(value)
    return round(parsed, 2) if parsed is not None else None


def _gate_blockers(gate: dict[str, Any] | None) -> list[str]:
    if not isinstance(gate, dict) or not gate:
        return ["missing_forward_gate"]
    blockers: list[str] = []
    for reason in gate.get("reasons") or []:
        if reason:
            blockers.append(str(reason))
    checks = gate.get("checks") or {}
    if isinstance(checks, dict):
        blockers.extend(str(name) for name, passed in checks.items() if passed is False)
    if not blockers and gate.get("passed") is not True:
        status = str(gate.get("status") or "blocked")
        blockers.append(status)
    return sorted(set(blockers))


def _promotion_readiness_blockers(readiness: dict[str, Any] | None) -> list[str]:
    if not isinstance(readiness, dict) or not readiness:
        return ["missing_promotion_readiness"]
    blockers = [str(item) for item in readiness.get("blocked_reasons") or [] if item]
    requirements = readiness.get("requirements") or {}
    if isinstance(requirements, dict):
        for name, row in requirements.items():
            if isinstance(row, dict) and row.get("passed") is False:
                blockers.append(str(name))
    return sorted(set(blockers))


def _generic_counts(snapshot: dict[str, Any] | None) -> dict[str, int]:
    payload = snapshot or {}
    return {
        "candidates": _as_int(payload.get("candidate_count")),
        "pending": _as_int(payload.get("pending_count")),
        "open": _as_int(payload.get("open_position_count")),
        "closed_today": _as_int(payload.get("closed_count_today")),
        "closed_total": _as_int(
            payload.get("closed_position_count")
            or payload.get("closed_trade_count")
            or payload.get("closed_outcome_count")
        ),
    }


def _activity_count(counts: dict[str, int]) -> int:
    return sum(counts.get(key, 0) for key in counts)


def _surface_summary(
    *,
    name: str,
    label: str,
    snapshot: dict[str, Any] | None,
    gate_field: str = "forward_paper_gate",
    realized_field: str = "realized_pnl_to_date",
    unrealized_field: str = "unrealized_pnl",
    extra_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = snapshot or {}
    counts = _generic_counts(payload)
    gate = payload.get(gate_field) if isinstance(payload, dict) else None
    blockers = _gate_blockers(gate)
    active = _activity_count(counts) > 0 or bool(payload.get("error"))
    passed = bool(isinstance(gate, dict) and gate.get("passed") is True)
    status = "eligible_for_review" if passed else "blocked"
    if not active and not passed:
        status = "inactive"
    return {
        "name": name,
        "label": label,
        "available": bool(snapshot is not None),
        "status": status,
        "trade_enabled": bool(payload.get("trade_enabled")),
        "counts": counts,
        "realized_pnl": _round_money(payload.get(realized_field)),
        "unrealized_pnl": _round_money(payload.get(unrealized_field)),
        "gate": {
            "present": isinstance(gate, dict) and bool(gate),
            "passed": passed,
            "status": gate.get("status") if isinstance(gate, dict) else None,
            "blocked_reasons": blockers,
            "metrics": gate.get("metrics") if isinstance(gate, dict) else None,
        },
        "blockers": blockers if not passed else [],
        "production_impact": dict(PRODUCTION_IMPACT),
        "extra_metrics": extra_metrics or {},
    }


def _pilot_summary(
    *,
    pilot_attribution: dict[str, Any] | None,
    ai_infra_aggressive_attribution: dict[str, Any] | None,
) -> dict[str, Any]:
    attribution = pilot_attribution or {}
    ai_surface = ai_infra_aggressive_attribution or {}
    readiness = ai_surface.get("promotion_readiness") or {}
    blockers = _promotion_readiness_blockers(readiness)
    eligible = bool(readiness.get("eligible_for_limited_production_review"))
    selected = ai_surface.get("selected") or []
    sliced = ai_surface.get("sliced") or []
    return {
        "name": "ai_infra_aggressive",
        "label": "AI_INFRA_AGGRESSIVE pilot sleeve",
        "available": bool(ai_infra_aggressive_attribution is not None),
        "status": "eligible_for_review" if eligible else "blocked",
        "trade_enabled": False,
        "counts": {
            "selected": len(selected),
            "sliced": len(sliced),
            "decision_snapshots": _as_int(attribution.get("decision_snapshots")),
            "outcome_records": _as_int(attribution.get("outcome_records")),
            "complete_replacement_outcomes": _as_int(
                attribution.get("complete_replacement_outcomes")
            ),
            "pending_replacement_outcomes": _as_int(
                attribution.get("pending_replacement_outcomes")
            ),
        },
        "realized_pnl": _round_money(attribution.get("direct_pilot_pnl")),
        "unrealized_pnl": None,
        "gate": {
            "present": bool(readiness),
            "passed": eligible,
            "status": "eligible_for_review" if eligible else "blocked",
            "blocked_reasons": blockers,
            "metrics": {
                "replacement_value": _round_money(attribution.get("replacement_value")),
                "risk_adjusted_replacement_value_avg": attribution.get(
                    "risk_adjusted_replacement_value_avg"
                ),
            },
        },
        "blockers": blockers if not eligible else [],
        "production_impact": dict(PRODUCTION_IMPACT),
        "extra_metrics": {
            "bull_booster_active": ai_surface.get("bull_booster_active"),
            "max_concurrent_positions": ai_surface.get("max_concurrent_positions"),
        },
    }


def _core_misfit_summary(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    payload = snapshot or {}
    return _surface_summary(
        name="core_misfit_paper",
        label="CORE_MISFIT_PAPER",
        snapshot=snapshot,
        realized_field="realized_inverse_pnl_to_date",
        unrealized_field="unrealized_inverse_pnl",
        extra_metrics={
            "realized_no_trade_value_to_date": _round_money(
                payload.get("realized_no_trade_value_to_date")
            ),
            "realized_fast_long_pnl_to_date": _round_money(
                payload.get("realized_fast_long_pnl_to_date")
            ),
        },
    )


def build_default_off_alpha_attribution_report(
    *,
    as_of: str,
    pilot_attribution: dict[str, Any] | None = None,
    ai_infra_aggressive_attribution: dict[str, Any] | None = None,
    sec_financial_report_event_sleeve: dict[str, Any] | None = None,
    event_sleeve_bundle: dict[str, Any] | None = None,
    state_surface_sleeve: dict[str, Any] | None = None,
    low_deployment_etf_overlay: dict[str, Any] | None = None,
    core_misfit_paper_sleeve: dict[str, Any] | None = None,
    broad_market_paper_sleeve: dict[str, Any] | None = None,
    ai_optical_paper_sleeve: dict[str, Any] | None = None,
    volatility_contraction_paper_sleeve: dict[str, Any] | None = None,
    volume_breadth_breakout_paper_sleeve: dict[str, Any] | None = None,
    alpha_score_market_regime_paper_sleeve: dict[str, Any] | None = None,
    accepted_source_consensus_paper_sleeve: dict[str, Any] | None = None,
    free_data_cross_source_consensus_paper_sleeve: dict[str, Any] | None = None,
    fundamental_growth_rs_paper_sleeve: dict[str, Any] | None = None,
    finra_iwm_paper_sleeve: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a daily read-only activation/blocker dashboard."""

    surfaces = [
        _pilot_summary(
            pilot_attribution=pilot_attribution,
            ai_infra_aggressive_attribution=ai_infra_aggressive_attribution,
        ),
        _surface_summary(
            name="sec_financial_report_t1",
            label="SEC financial-report T+1 paper sleeve",
            snapshot=sec_financial_report_event_sleeve,
        ),
        _surface_summary(
            name="event_overlay_bundle",
            label="Default-off event overlay bundle",
            snapshot=event_sleeve_bundle,
            realized_field="realized_pnl_to_date",
            unrealized_field="unrealized_pnl",
        ),
        _surface_summary(
            name="state_surface_satellite",
            label="STATE_SURFACE_SATELLITE",
            snapshot=state_surface_sleeve,
        ),
        _surface_summary(
            name="low_deployment_etf_overlay",
            label="Low-deployment ETF overlay",
            snapshot=low_deployment_etf_overlay,
        ),
        _core_misfit_summary(core_misfit_paper_sleeve),
        _surface_summary(
            name="broad_market_leadership",
            label="BROAD_MARKET_LEADERSHIP_PAPER",
            snapshot=broad_market_paper_sleeve,
        ),
        _surface_summary(
            name="ai_optical_iwm_confirmed",
            label="AI_OPTICAL_IWM_CONFIRMED_PAPER",
            snapshot=ai_optical_paper_sleeve,
        ),
        _surface_summary(
            name="volatility_contraction_qqq_confirmed",
            label="VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER",
            snapshot=volatility_contraction_paper_sleeve,
        ),
        _surface_summary(
            name="volume_breadth_breakout",
            label="VOLUME_BREADTH_BREAKOUT_PAPER",
            snapshot=volume_breadth_breakout_paper_sleeve,
            extra_metrics={
                "breadth_intensity_supported": (
                    ((volume_breadth_breakout_paper_sleeve or {}).get("breadth_intensity_support") or {}).get("supported_candidate_count")
                ),
                "high_close_supported": (
                    ((volume_breadth_breakout_paper_sleeve or {}).get("high_close_support") or {}).get("supported_candidate_count")
                ),
                "cost_liquidity_supported": (
                    ((volume_breadth_breakout_paper_sleeve or {}).get("cost_liquidity_support") or {}).get("supported_candidate_count")
                ),
            },
        ),
        _surface_summary(
            name="alpha_score_market_regime",
            label="ALPHA_SCORE_MARKET_REGIME_PAPER",
            snapshot=alpha_score_market_regime_paper_sleeve,
            extra_metrics={
                "source_rule_version": (
                    (alpha_score_market_regime_paper_sleeve or {}).get("source_rule_version")
                ),
                "market_regime_rule_version": (
                    (alpha_score_market_regime_paper_sleeve or {}).get("market_regime_rule_version")
                ),
                "safe_notional_usd": (
                    (alpha_score_market_regime_paper_sleeve or {}).get("safe_paper_notional_usd")
                    or ((alpha_score_market_regime_paper_sleeve or {}).get("candidates") or [{}])[0].get("safe_paper_notional_usd")
                ),
                "ranked_count": (
                    ((alpha_score_market_regime_paper_sleeve or {}).get("ranking_surface") or {}).get("ranked_count")
                ),
                "top_decile_count": (
                    ((alpha_score_market_regime_paper_sleeve or {}).get("ranking_surface") or {}).get("top_decile_count")
                ),
                "source_consensus_supported": (
                    ((alpha_score_market_regime_paper_sleeve or {}).get("source_consensus_support") or {}).get("supported_candidate_count")
                ),
            },
        ),
        _surface_summary(
            name="accepted_source_consensus",
            label="ACCEPTED_SOURCE_CONSENSUS_PAPER",
            snapshot=accepted_source_consensus_paper_sleeve,
            extra_metrics={
                "source_rule_version": (
                    (accepted_source_consensus_paper_sleeve or {}).get("source_rule_version")
                ),
                "market_regime_rule_version": (
                    (accepted_source_consensus_paper_sleeve or {}).get("market_regime_rule_version")
                ),
                "paper_notional_usd": (
                    ((accepted_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("paper_notional_usd")
                ),
                "raw_alpha_score_candidate_count": (
                    (accepted_source_consensus_paper_sleeve or {}).get("raw_alpha_score_candidate_count")
                ),
                "source_consensus_supported": (
                    ((accepted_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("supported_candidate_count")
                ),
                "source_counts": (
                    ((accepted_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("source_counts")
                ),
            },
        ),
        _surface_summary(
            name="free_data_cross_source_consensus",
            label="ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER",
            snapshot=free_data_cross_source_consensus_paper_sleeve,
            extra_metrics={
                "consensus_rule_version": (
                    (free_data_cross_source_consensus_paper_sleeve or {}).get("consensus_rule_version")
                ),
                "paper_notional_usd": (
                    ((free_data_cross_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("paper_notional_usd")
                ),
                "min_source_count": (
                    ((free_data_cross_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("min_source_count")
                ),
                "source_consensus_supported": (
                    ((free_data_cross_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("supported_candidate_count")
                ),
                "source_counts": (
                    ((free_data_cross_source_consensus_paper_sleeve or {}).get("source_consensus") or {}).get("source_counts")
                ),
            },
        ),
        _surface_summary(
            name="fundamental_growth_rs",
            label="FUNDAMENTAL_GROWTH_RS_PAPER",
            snapshot=fundamental_growth_rs_paper_sleeve,
            extra_metrics={
                "source_rule_version": (
                    (fundamental_growth_rs_paper_sleeve or {}).get("source_rule_version")
                ),
                "governor_rule_version": (
                    (fundamental_growth_rs_paper_sleeve or {}).get("governor_rule_version")
                ),
                "gross_margin_quality_candidates": (
                    ((fundamental_growth_rs_paper_sleeve or {}).get("gross_margin_quality") or {}).get("candidate_count")
                ),
                "low_volume_supported": (
                    ((fundamental_growth_rs_paper_sleeve or {}).get("low_volume_participation") or {}).get("supported_candidate_count")
                ),
                "filing_recency_supported": (
                    ((fundamental_growth_rs_paper_sleeve or {}).get("filing_recency") or {}).get("supported_candidate_count")
                ),
                "low_liability_supported": (
                    ((fundamental_growth_rs_paper_sleeve or {}).get("low_liability") or {}).get("supported_candidate_count")
                ),
            },
        ),
        _surface_summary(
            name="finra_iwm_confirmed",
            label="FINRA_IWM_CONFIRMED_PAPER",
            snapshot=finra_iwm_paper_sleeve,
            extra_metrics={
                "source_rule_version": (
                    (finra_iwm_paper_sleeve or {}).get("source_rule_version")
                ),
                "market_confirmation_rule_version": (
                    (finra_iwm_paper_sleeve or {}).get("market_confirmation_rule_version")
                ),
                "cooldown_rejected": (
                    ((finra_iwm_paper_sleeve or {}).get("same_ticker_cooldown") or {}).get("rejected_count")
                ),
                "finra_rows": (
                    ((finra_iwm_paper_sleeve or {}).get("data_source") or {}).get("row_count")
                ),
            },
        ),
    ]

    status_counts = Counter(row["status"] for row in surfaces)
    blocker_counts: Counter[str] = Counter()
    blocker_surfaces: dict[str, set[str]] = {}
    for surface in surfaces:
        for blocker in surface.get("blockers") or []:
            blocker_counts[blocker] += 1
            blocker_surfaces.setdefault(blocker, set()).add(surface["name"])

    top_blockers = [
        {
            "reason": reason,
            "count": count,
            "surfaces": sorted(blocker_surfaces.get(reason, set())),
        }
        for reason, count in blocker_counts.most_common()
    ]
    eligible = [row["name"] for row in surfaces if row["status"] == "eligible_for_review"]

    return {
        "schema_version": 1,
        "rule_version": RULE_VERSION,
        "report_name": "default_off_alpha_attribution_report_surface",
        "as_of": str(as_of)[:10],
        "read_only": True,
        "trade_enabled": False,
        "production_impact": dict(PRODUCTION_IMPACT),
        "surface_count": len(surfaces),
        "status_counts": dict(sorted(status_counts.items())),
        "eligible_for_separate_activation_review": eligible,
        "blocked_surface_count": status_counts.get("blocked", 0),
        "top_blockers": top_blockers,
        "surfaces": surfaces,
        "notes": (
            "This report ranks measurement blockers only. It is not an approval "
            "to enable capital, slots, ranking, sizing, exits, or orders."
        ),
    }
