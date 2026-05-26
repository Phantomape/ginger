from quant.experiments.exp_20260526_007_vcp_rank_notional_profile import (
    _apply_rank_notional_profile,
    _profile_gate,
    _select_profile_paper_trades,
    rank_notional_scalar,
)


def _candidate(ticker: str, date: str = "2025-01-02", **extra):
    return {"ticker": ticker, "date": date, **extra}


def test_rank_notional_scalar_defaults_safely():
    assert rank_notional_scalar(1, [1.0, 1.25]) == 1.0
    assert rank_notional_scalar(2, [1.0, 1.25]) == 1.25
    assert rank_notional_scalar(3, [1.0, 1.25]) == 1.0
    assert rank_notional_scalar(None, [1.0, 1.25]) == 1.0


def test_apply_rank_notional_profile_scales_notional_and_pnl():
    trade = {
        "ticker": "RANK2",
        "pnl": 100.0,
        "pnl_pct_net": 0.01,
        "paper_notional_usd": 10000.0,
        "vcp_candidate_rank_on_signal_date": 2,
    }

    scaled = _apply_rank_notional_profile(
        trade,
        profile=[1.0, 1.25],
        variant="rank2_125",
    )

    assert scaled["paper_notional_usd"] == 12500.0
    assert scaled["pnl"] == 125.0
    assert scaled["base_equal_notional_pnl"] == 100.0
    assert scaled["rank_notional_scalar"] == 1.25
    assert scaled["pnl_pct_net"] == 0.01
    assert scaled["trade_enabled"] is False
    assert scaled["alters_orders"] is False


def test_select_profile_keeps_top2_and_applies_rank_scalars(monkeypatch):
    def fake_trade(_snapshot, row):
        return {
            **row,
            "pnl": 100.0,
            "paper_notional_usd": 10000.0,
            "pnl_pct_net": 0.01,
        }

    monkeypatch.setattr(
        "quant.experiments.exp_20260526_007_vcp_rank_notional_profile.base._paper_trade_from_candidate",
        fake_trade,
    )
    selected, filtered = _select_profile_paper_trades(
        {},
        [
            _candidate("AAA", vcp_candidate_rank_on_signal_date=1),
            _candidate("BBB", vcp_candidate_rank_on_signal_date=2),
            _candidate("CCC", vcp_candidate_rank_on_signal_date=3),
        ],
        profile=[1.0, 1.25],
        variant="rank2_125",
    )

    assert [(row["ticker"], row["paper_notional_usd"], row["pnl"]) for row in selected] == [
        ("AAA", 10000.0, 100.0),
        ("BBB", 12500.0, 125.0),
    ]
    assert [(row["ticker"], row["filter_reason"]) for row in filtered] == [
        ("CCC", "daily_top2_limit")
    ]


def test_profile_gate_requires_exp037_outperformance_without_regression():
    gate = _profile_gate(
        aggregate={
            "expected_value_score_delta_sum": 2.30,
            "total_pnl_delta_sum": 39000.0,
        },
        target_summary={
            "total_trade_count": 117,
            "max_single_positive_pnl_share": 0.20,
            "positive_pnl_hhi": 0.10,
        },
        target_windows=["late_strong", "mid_weak", "old_thin"],
        exp037_comparison={
            "beats_exp037_ev_by_min_5pct": True,
            "windows_ev_regressed_vs_exp037": [],
            "windows_pnl_regressed_vs_exp037": [],
            "max_drawdown_worse_vs_exp037": 0.001,
        },
    )

    assert gate["passed"] is True


def test_profile_gate_rejects_positive_core_result_that_lags_exp037():
    gate = _profile_gate(
        aggregate={
            "expected_value_score_delta_sum": 2.10,
            "total_pnl_delta_sum": 35000.0,
        },
        target_summary={
            "total_trade_count": 117,
            "max_single_positive_pnl_share": 0.20,
            "positive_pnl_hhi": 0.10,
        },
        target_windows=["late_strong", "mid_weak", "old_thin"],
        exp037_comparison={
            "beats_exp037_ev_by_min_5pct": False,
            "windows_ev_regressed_vs_exp037": ["old_thin"],
            "windows_pnl_regressed_vs_exp037": [],
            "max_drawdown_worse_vs_exp037": 0.001,
        },
    )

    assert gate["passed"] is False
    assert "did_not_beat_exp037_aggregate_ev_by_5pct" in gate["failed_reasons"]
    assert "window_ev_regression_vs_exp037" in gate["failed_reasons"]
