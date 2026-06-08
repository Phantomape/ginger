from __future__ import annotations

from quant.default_off_alpha_attribution import (
    build_default_off_alpha_attribution_report,
)
from quant.report_generator import generate_daily_report


def test_default_off_alpha_attribution_rolls_up_blockers_without_orders():
    report = build_default_off_alpha_attribution_report(
        as_of="2026-05-24",
        pilot_attribution={
            "decision_snapshots": 3,
            "outcome_records": 0,
            "direct_pilot_pnl": 0.0,
            "replacement_value": None,
        },
        ai_infra_aggressive_attribution={
            "selected": [],
            "sliced": [],
            "promotion_readiness": {
                "eligible_for_limited_production_review": False,
                "blocked_reasons": ["closed_pilot_outcomes"],
                "requirements": {
                    "closed_pilot_outcomes": {"passed": False, "value": 0},
                },
            },
        },
        state_surface_sleeve={
            "candidate_count": 2,
            "open_position_count": 1,
            "trade_enabled": False,
            "realized_pnl_to_date": 125.0,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["min_closed_trades"],
                "metrics": {"closed_trades": 4},
            },
        },
        broad_market_paper_sleeve={
            "candidate_count": 1,
            "trade_enabled": False,
            "forward_paper_gate": {
                "passed": True,
                "status": "eligible_for_review",
                "reasons": [],
                "metrics": {"closed_trades": 61},
            },
        },
        volatility_contraction_paper_sleeve={
            "candidate_count": 1,
            "trade_enabled": False,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["needs_closed_forward_outcomes"],
                "metrics": {"closed_trades": 0},
            },
        },
        rolling_corr_peer_shock_paper_sleeve={
            "candidate_count": 1,
            "raw_candidate_count": 3,
            "pending_count": 1,
            "trade_enabled": False,
            "rule_version": "rolling_corr_peer_shock_core_flow_shared_adapter_v1",
            "source_rule_version": "rolling_corr_peer_shock_core_flow_positive_candidate_source_v1",
            "peer_shock_context": {
                "core_flow_confirmation_required": True,
                "raw_corr_pairs": 3,
            },
            "production_impact": {"uses_free_ohlcv_only": True},
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["not_enough_closed_forward_paper_trades"],
            },
        },
        industry_stable_core_flow_paper_sleeve={
            "candidate_count": 1,
            "raw_candidate_count": 4,
            "pending_count": 1,
            "trade_enabled": False,
            "rule_version": "industry_stable_core_flow_shared_default_off_adapter_v1",
            "source_rule_version": "industry_stable_core_flow_confirmed_candidate_source_v1",
            "industry_stable_core_flow_context": {
                "stable_industry_group_rows": 2,
                "core_flow_confirmed_dates": 1,
                "same_ticker_core_overlap_excluded": True,
            },
            "production_impact": {"uses_free_ohlcv_only": True},
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["not_enough_closed_forward_paper_trades"],
            },
        },
    )

    assert report["read_only"] is True
    assert report["trade_enabled"] is False
    assert report["production_impact"]["alters_orders"] is False
    assert "broad_market_leadership" in report["eligible_for_separate_activation_review"]
    assert report["blocked_surface_count"] >= 2
    surface_names = {row["name"] for row in report["surfaces"]}
    assert "volatility_contraction_qqq_confirmed" in surface_names
    assert "rolling_corr_peer_shock" in surface_names
    rolling_surface = next(
        row for row in report["surfaces"] if row["name"] == "rolling_corr_peer_shock"
    )
    stable_surface = next(
        row for row in report["surfaces"] if row["name"] == "industry_stable_core_flow"
    )
    assert rolling_surface["trade_enabled"] is False
    assert rolling_surface["extra_metrics"]["same_day_core_flow_required"] is True
    assert rolling_surface["extra_metrics"]["uses_free_ohlcv_only"] is True
    assert stable_surface["trade_enabled"] is False
    assert stable_surface["extra_metrics"]["core_flow_confirmed_dates"] == 1
    assert stable_surface["extra_metrics"]["uses_free_ohlcv_only"] is True
    top_reasons = {row["reason"] for row in report["top_blockers"]}
    assert "closed_pilot_outcomes" in top_reasons
    assert "min_closed_trades" in top_reasons


def test_report_generator_renders_default_off_alpha_attribution():
    attribution = build_default_off_alpha_attribution_report(
        as_of="2026-05-24",
        ai_infra_aggressive_attribution={
            "selected": [],
            "sliced": [],
            "promotion_readiness": {
                "eligible_for_limited_production_review": False,
                "blocked_reasons": ["closed_pilot_outcomes"],
            },
        },
        core_misfit_paper_sleeve={
            "candidate_count": 1,
            "trade_enabled": False,
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["positive_inverse_pnl"],
            },
        },
        volatility_contraction_paper_sleeve={
            "candidate_count": 1,
            "trade_enabled": False,
            "paper_enabled": True,
            "candidate_universe": {"status": "daily_data_universe", "ticker_count": 12},
            "market_confirmation": {
                "status": "ok",
                "qqq_minus_spy_return_20d": 0.012,
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["needs_closed_forward_outcomes"],
            },
            "candidates": [{"ticker": "NVDA", "intended_notional": 10000.0}],
        },
        rolling_corr_peer_shock_paper_sleeve={
            "candidate_count": 1,
            "raw_candidate_count": 2,
            "pending_count": 1,
            "trade_enabled": False,
            "paper_enabled": True,
            "peer_shock_context": {
                "core_flow_confirmation_required": True,
                "raw_corr_pairs": 2,
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["not_enough_closed_forward_paper_trades"],
            },
            "candidates": [
                {
                    "ticker": "LAG",
                    "peer_ticker": "PEER",
                    "rolling_corr_60d": 0.75,
                    "candidate_score": 1.23,
                    "peer_relative_vs_spy": 0.05,
                    "date": "2026-05-24",
                    "paper_notional_usd": 4000.0,
                }
            ],
        },
        industry_stable_core_flow_paper_sleeve={
            "candidate_count": 1,
            "raw_candidate_count": 2,
            "pending_count": 1,
            "trade_enabled": False,
            "paper_enabled": True,
            "industry_stable_core_flow_context": {
                "stable_industry_group_rows": 1,
                "core_flow_confirmed_dates": 1,
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["not_enough_closed_forward_paper_trades"],
            },
            "candidates": [
                {
                    "ticker": "LEAD",
                    "candidate_group_key": "technology/software",
                    "candidate_ret20_lead_vs_group": 0.04,
                    "candidate_signal_relative_vs_spy": 0.02,
                    "candidate_score": 1.91,
                    "date": "2026-05-24",
                    "paper_notional_usd": 4000.0,
                }
            ],
        },
    )

    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        default_off_alpha_attribution=attribution,
        volatility_contraction_paper_sleeve={
            "candidate_count": 1,
            "trade_enabled": False,
            "paper_enabled": True,
            "candidate_universe": {"status": "daily_data_universe", "ticker_count": 12},
            "market_confirmation": {
                "status": "ok",
                "qqq_minus_spy_return_20d": 0.012,
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["needs_closed_forward_outcomes"],
            },
            "candidates": [{"ticker": "NVDA", "intended_notional": 10000.0}],
        },
        rolling_corr_peer_shock_paper_sleeve={
            "candidate_count": 1,
            "raw_candidate_count": 2,
            "pending_count": 1,
            "trade_enabled": False,
            "paper_enabled": True,
            "peer_shock_context": {
                "core_flow_confirmation_required": True,
                "raw_corr_pairs": 2,
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["not_enough_closed_forward_paper_trades"],
            },
            "candidates": [
                {
                    "ticker": "LAG",
                    "peer_ticker": "PEER",
                    "rolling_corr_60d": 0.75,
                    "candidate_score": 1.23,
                    "peer_relative_vs_spy": 0.05,
                    "date": "2026-05-24",
                    "paper_notional_usd": 4000.0,
                }
            ],
        },
        industry_stable_core_flow_paper_sleeve={
            "candidate_count": 1,
            "raw_candidate_count": 2,
            "pending_count": 1,
            "trade_enabled": False,
            "paper_enabled": True,
            "industry_stable_core_flow_context": {
                "stable_industry_group_rows": 1,
                "core_flow_confirmed_dates": 1,
            },
            "forward_paper_gate": {
                "passed": False,
                "status": "blocked",
                "reasons": ["not_enough_closed_forward_paper_trades"],
            },
            "candidates": [
                {
                    "ticker": "LEAD",
                    "candidate_group_key": "technology/software",
                    "candidate_ret20_lead_vs_group": 0.04,
                    "candidate_signal_relative_vs_spy": 0.02,
                    "candidate_score": 1.91,
                    "date": "2026-05-24",
                    "paper_notional_usd": 4000.0,
                }
            ],
        },
    )

    assert "DEFAULT-OFF ALPHA ATTRIBUTION" in report
    assert "Read-only: True" in report
    assert "Trade enabled: False" in report
    assert "closed_pilot_outcomes" in report
    assert "CORE_MISFIT_PAPER" in report
    assert "VOLATILITY CONTRACTION QQQ-CONFIRMED PAPER SLEEVE" in report
    assert "ROLLING-CORR PEER-SHOCK PAPER SLEEVE" in report
    assert "Core flow required: True" in report
    assert "peer=PEER" in report
    assert "INDUSTRY STABLE CORE-FLOW PAPER SLEEVE" in report
    assert "Core-flow dates: 1" in report
    assert "group=technology/software" in report
