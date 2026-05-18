from __future__ import annotations

from copy import deepcopy

from backtest_readonly_diagnostics import build_diagnostics
from evaluator_gates import evaluate_metrics
from experiments.exp_20260518_004_tail_aware_state_surface_attribution import (
    _paper_diagnostics,
    _tail_metrics_from_values,
)
from portfolio_heat_engine import build_portfolio_heat_report, heat_score
from regime_engine import classify_market_regime


def test_backtest_readonly_diagnostics_does_not_mutate_result():
    result = {
        "period": "unit",
        "trades": [
            {
                "ticker": "AAA",
                "strategy": "trend_long",
                "entry_date": "2026-01-01",
                "exit_date": "2026-01-10",
                "entry_price": 100.0,
                "exit_price": 110.0,
                "stop_price": 95.0,
                "shares": 10,
                "pnl": 100.0,
            },
            {
                "ticker": "BBB",
                "strategy": "breakout_long",
                "entry_date": "2026-01-02",
                "exit_date": "2026-01-11",
                "entry_price": 100.0,
                "exit_price": 96.0,
                "stop_price": 95.0,
                "shares": 10,
                "pnl": -40.0,
            },
        ],
    }
    before = deepcopy(result)

    diagnostics = build_diagnostics(result)

    assert result == before
    assert diagnostics["read_only"] is True
    assert diagnostics["tail_gate_report"]["passed"] is False
    assert "insufficient_sample" in diagnostics["tail_gate_report"]["hard_failures"]


def test_evaluator_gate_flags_synthetic_top5_concentration():
    metrics = {
        "total_trades": 20,
        "expected_value_usd": 10.0,
        "avg_r_multiple": 0.2,
        "sharpe_ratio": 1.0,
        "max_drawdown_pct": 0.03,
        "r_skewness": 0.1,
        "r_excess_kurtosis": 1.0,
        "r_tail_ratio": 1.2,
        "r_top_5_contribution_pct": 0.75,
        "r_hhi_concentration": 0.10,
    }

    report = evaluate_metrics(metrics)

    assert report["passed"] is False
    assert "r_top5_concentration" in report["hard_failures"]


def test_regime_engine_missing_fields_falls_back_low_confidence():
    report = classify_market_regime({})

    assert report["regime"] == "baseline"
    assert report["confidence"] == 0.0


def test_portfolio_heat_report_is_deterministic_and_read_only():
    positions = [
        {"ticker": "NVDA", "position_value_usd": 40_000, "sleeve": "core"},
        {"ticker": "AMD", "position_value_usd": 30_000, "sleeve": "core"},
        {"ticker": "GLD", "position_value_usd": 30_000, "sleeve": "paper"},
    ]

    first = build_portfolio_heat_report(positions, portfolio_value=100_000)
    second = build_portfolio_heat_report(positions, portfolio_value=100_000)

    assert first == second
    assert first["read_only"] is True
    assert heat_score(first) == heat_score(second)
    assert first["concentration_hhi"]["theme_value_hhi"] is not None


def test_exp003_paper_tail_metrics_use_pnl_without_true_r_multiple():
    trades = [
        {"ticker": "AAA", "entry_date": "2026-01-01", "exit_date": "2026-01-02", "pnl": 100, "net_return_pct": 0.10},
        {"ticker": "BBB", "entry_date": "2026-01-01", "exit_date": "2026-01-02", "pnl": 80, "net_return_pct": 0.08},
        {"ticker": "CCC", "entry_date": "2026-01-01", "exit_date": "2026-01-02", "pnl": -20, "net_return_pct": -0.02},
        {"ticker": "DDD", "entry_date": "2026-01-01", "exit_date": "2026-01-02", "pnl": 40, "net_return_pct": 0.04},
        {"ticker": "EEE", "entry_date": "2026-01-01", "exit_date": "2026-01-02", "pnl": 20, "net_return_pct": 0.02},
    ]

    direct = _tail_metrics_from_values([trade["pnl"] for trade in trades], "pnl")
    diagnostics = _paper_diagnostics(trades)

    assert direct["pnl_top_5_contribution_pct"] == 1.0
    assert diagnostics["metrics_for_gates"]["total_trades"] == 5
    assert diagnostics["metrics_for_gates"]["pnl_hhi_concentration"] is not None
    assert "true R-multiple is unavailable" in diagnostics["notes"][0]
