from datetime import date

import numpy as np

from quant import current_paper_sleeve_panel as panel
from quant.current_paper_core_allocator import SURFACE_SPECS, WINDOWS


def test_every_registered_surface_has_one_version_aware_plan() -> None:
    names = [str(spec["surface"]) for spec in SURFACE_SPECS]
    plans = [panel._plan_for(spec) for spec in SURFACE_SPECS]
    assert len(names) == 41
    assert len(set(names)) == 41
    assert len(plans) == 41
    assert all(plan.provenance for plan in plans)
    assert sum(plan.mode == "unsupported" for plan in plans) == 1
    assert sum(plan.mode == "research_incomplete" for plan in plans) == 1


def test_final_nested_state_and_vcp_paths_are_recovered() -> None:
    calendars = {
        window: [date.fromisoformat(bounds[0]), date.fromisoformat(bounds[1])]
        for window, bounds in {
            "old_thin": ("2024-10-02", "2025-04-22"),
            "mid_weak": ("2025-04-23", "2025-10-22"),
            "late_strong": ("2025-10-23", "2026-04-21"),
        }.items()
    }
    state = panel._load_direct(panel.CUSTOM_PLANS["state_surface_sleeve"], calendars)
    vcp = panel._load_direct(
        panel.CUSTOM_PLANS["volatility_contraction_paper_sleeve"], calendars
    )
    assert {window: len(state[window]) for window in WINDOWS} == {
        "old_thin": 3,
        "mid_weak": 12,
        "late_strong": 9,
    }
    assert {window: len(vcp[window]) for window in WINDOWS} == {
        "old_thin": 25,
        "mid_weak": 88,
        "late_strong": 4,
    }


def test_complete_zero_trigger_window_is_not_confused_with_missing_data() -> None:
    calendars = {window: [date(2025, 1, 2), date(2025, 1, 3)] for window in WINDOWS}
    trades = {window: [] for window in WINDOWS}
    returns, diagnostics, contributions = panel._reconstruct_returns(
        trades, calendars, {}
    )
    assert contributions == []
    assert all(np.array_equal(returns[window], np.zeros(2)) for window in WINDOWS)
    assert all(diagnostics[window]["true_zero_trigger_window"] for window in WINDOWS)


def test_broad_market_replay_matches_frozen_accepted_identity() -> None:
    trades = panel._replay_broad_market()
    assert {window: len(trades[window]) for window in WINDOWS} == {
        "old_thin": 30,
        "mid_weak": 30,
        "late_strong": 30,
    }
    assert {
        window: round(sum(float(row["pnl"]) for row in trades[window]), 2)
        for window in WINDOWS
    } == {
        "old_thin": 4059.90,
        "mid_weak": 14607.88,
        "late_strong": 10307.76,
    }


def test_non_capital_and_incomplete_surfaces_are_never_zero_return_proxies() -> None:
    misfit = panel.CUSTOM_PLANS["core_misfit_paper_sleeve"]
    options = panel.CUSTOM_PLANS[
        "core_drawdown_flow_put_stabilization_paper_sleeve"
    ]
    assert misfit.mode == "unsupported"
    assert "mutually opposite" in str(misfit.note)
    assert options.mode == "research_incomplete"
    assert options.pit_tier == "research_pit"

