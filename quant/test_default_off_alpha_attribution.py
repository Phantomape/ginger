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
    )

    assert report["read_only"] is True
    assert report["trade_enabled"] is False
    assert report["production_impact"]["alters_orders"] is False
    assert "broad_market_leadership" in report["eligible_for_separate_activation_review"]
    assert report["blocked_surface_count"] >= 2
    surface_names = {row["name"] for row in report["surfaces"]}
    assert "volatility_contraction_qqq_confirmed" in surface_names
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
    )

    assert "DEFAULT-OFF ALPHA ATTRIBUTION" in report
    assert "Read-only: True" in report
    assert "Trade enabled: False" in report
    assert "closed_pilot_outcomes" in report
    assert "CORE_MISFIT_PAPER" in report
    assert "VOLATILITY CONTRACTION QQQ-CONFIRMED PAPER SLEEVE" in report
