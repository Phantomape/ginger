from __future__ import annotations

from core_misfit_paper_sleeve import (
    DEFAULT_TARGET_STRATEGIES,
    RULE_VERSION,
    SLEEVE_NAME,
    build_core_misfit_paper_candidates,
    build_core_misfit_paper_sleeve_snapshot,
    empty_core_misfit_paper_state,
)
from report_generator import generate_daily_report


def _signal(ticker="TSM", strategy="trend_long", shares=10):
    return {
        "ticker": ticker,
        "strategy": strategy,
        "entry_price": 100.0,
        "stop_price": 95.0,
        "target_price": 115.0,
        "confidence_score": 0.9,
        "trade_quality_score": 0.95,
        "target_mult_used": 4.5,
        "sizing": {
            "shares_to_buy": shares,
            "entry_price": 100.0,
            "position_value_usd": shares * 100.0,
        },
    }


def test_core_misfit_candidates_are_default_off_and_filtered():
    candidates = build_core_misfit_paper_candidates(
        candidate_signals=[
            _signal("TSM"),
            _signal("AAPL"),
            _signal("TSM", strategy="earnings_event_long"),
        ],
        entry_execution_plan={"slot_sliced_signals": [_signal("V")]},
        as_of="2026-05-18",
    )

    assert {row["ticker"] for row in candidates} == {"TSM", "V"}
    assert {row["source_kind"] for row in candidates} == {
        "selected_core_signal",
        "slot_sliced_core_signal",
    }
    assert all(row["trade_enabled"] is False for row in candidates)
    assert all(row["alters_orders"] is False for row in candidates)
    assert all(row["rule_version"] == RULE_VERSION for row in candidates)


def test_core_misfit_default_scope_is_trend_long_only_but_configurable():
    assert DEFAULT_TARGET_STRATEGIES == ("trend_long",)

    default_candidates = build_core_misfit_paper_candidates(
        candidate_signals=[
            _signal("TSM", strategy="trend_long"),
            _signal("ISRG", strategy="breakout_long"),
        ],
        entry_execution_plan={
            "slot_sliced_signals": [
                _signal("V", strategy="trend_long"),
                _signal("DDOG", strategy="breakout_long"),
            ]
        },
        as_of="2026-05-18",
    )

    assert {row["ticker"] for row in default_candidates} == {"TSM", "V"}
    assert {row["strategy"] for row in default_candidates} == {"trend_long"}

    override_candidates = build_core_misfit_paper_candidates(
        candidate_signals=[
            _signal("TSM", strategy="trend_long"),
            _signal("ISRG", strategy="breakout_long"),
        ],
        entry_execution_plan={
            "slot_sliced_signals": [
                _signal("V", strategy="trend_long"),
                _signal("DDOG", strategy="breakout_long"),
            ]
        },
        as_of="2026-05-18",
        config={"target_strategies": ("trend_long", "breakout_long")},
    )

    assert {row["ticker"] for row in override_candidates} == {
        "TSM",
        "ISRG",
        "V",
        "DDOG",
    }
    assert {row["strategy"] for row in override_candidates} == {
        "trend_long",
        "breakout_long",
    }


def test_core_misfit_sleeve_tracks_no_trade_and_inverse_paper_outcomes():
    state = empty_core_misfit_paper_state()
    first = build_core_misfit_paper_sleeve_snapshot(
        as_of="2026-05-18",
        candidate_signals=[_signal("TSM")],
        entry_execution_plan={},
        open_prices={"TSM": 100.0},
        current_prices={"TSM": 100.0},
        state=state,
        persist=False,
    )

    assert first["sleeve"] == SLEEVE_NAME
    assert first["enabled"] is False
    assert first["trade_enabled"] is False
    assert first["candidate_count"] == 1
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["production_impact"]["alters_orders"] is False

    second_state = empty_core_misfit_paper_state()
    second_state["pending_entries"] = first["pending_entries"]
    second = build_core_misfit_paper_sleeve_snapshot(
        as_of="2026-05-19",
        candidate_signals=[],
        entry_execution_plan={},
        open_prices={"TSM": 100.0},
        current_prices={"TSM": 99.0},
        state=second_state,
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["closed_count_today"] == 0

    third_state = empty_core_misfit_paper_state()
    third_state["open_positions"] = second["open_positions"]
    third = build_core_misfit_paper_sleeve_snapshot(
        as_of="2026-05-20",
        candidate_signals=[],
        entry_execution_plan={},
        open_prices={},
        current_prices={"TSM": 95.0},
        state=third_state,
        persist=False,
    )

    assert third["closed_count_today"] == 1
    outcome = third["closed_outcomes_today"][0]
    assert outcome["horizon_days"] == 1
    assert outcome["fast_long_pnl"] < 0
    assert outcome["no_trade_avoided_value_pnl"] > 0
    assert outcome["inverse_short_pnl"] > 0
    assert third["realized_no_trade_value_to_date"] > 0
    assert third["realized_inverse_pnl_to_date"] > 0


def test_report_generator_renders_core_misfit_paper_without_orders():
    snapshot = build_core_misfit_paper_sleeve_snapshot(
        as_of="2026-05-18",
        candidate_signals=[_signal("DDOG")],
        entry_execution_plan={},
        open_prices={"DDOG": 100.0},
        current_prices={"DDOG": 100.0},
        state=empty_core_misfit_paper_state(),
        persist=False,
    )

    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        core_misfit_paper_sleeve=snapshot,
    )

    assert "CORE MISFIT PAPER SLEEVE" in report
    assert "Trade enabled: False" in report
    assert "Live short: False" in report
    assert "paper only" in report
