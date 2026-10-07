"""Retired V1 paper histories must not become active reports or recommendations."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import default_off_alpha_attribution as attribution
import report_generator
import sleeve_health
from quant import pilot_tracker


RETIREMENT_MARKERS = (
    {"retired": True},
    {"build_status": "retired_default_off_paper_disabled"},
)

REPORT_SURFACES = (
    ("ai_optical_paper_sleeve", "AI OPTICAL IWM-CONFIRMED PAPER SLEEVE"),
    ("alpha_score_market_regime_paper_sleeve", "ALPHA-SCORE MARKET-REGIME PAPER SLEEVE"),
    ("accepted_source_consensus_paper_sleeve", "ACCEPTED-SOURCE CONSENSUS PAPER SLEEVE"),
    ("free_data_cross_source_consensus_paper_sleeve", "ACCEPTED FREE-DATA CROSS-SOURCE CONSENSUS PAPER SLEEVE"),
    ("accepted_helper_source_priority_allocator_paper_sleeve", "ACCEPTED HELPER SOURCE-PRIORITY ALLOCATOR PAPER SLEEVE"),
    ("industry_relative_laggard_repair_paper_sleeve", "INDUSTRY-RELATIVE LAGGARD REPAIR PAPER SLEEVE"),
    ("state_surface_sleeve", "STATE-SURFACE SATELLITE PAPER SLEEVE"),
    ("space_catalyst_shadow", "SPACE CATALYST SHADOW UNIVERSE"),
    ("space_catalyst_observation_slot", "SPACE CATALYST PRODUCTION OBSERVATION SLOT"),
    ("space_catalyst_event_ledger", "SPACE CATALYST EVENT LEDGER"),
)


def _historical_surface():
    row = {
        "ticker": "OLD",
        "signal_date": "2026-09-08",
        "entry_date": "2026-09-09",
        "entry_price": 100.0,
        "last_price": 101.0,
        "notional": 4000.0,
        "hold_days": 10,
        "observed_trading_days": 1,
    }
    return {
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 1,
        "pending_count": 1,
        "open_position_count": 1,
        "active_event_count": 1,
        "pending_entries": [deepcopy(row)],
        "open_positions": [deepcopy(row)],
        "realized_pnl_to_date": 100.0,
        "unrealized_pnl": 40.0,
        "forward_paper_gate": {
            "passed": True,
            "status": "passed",
            "metrics": {"closed_trades": 80, "realized_pnl": 100.0},
        },
    }


@pytest.mark.parametrize("surface_name,heading", REPORT_SURFACES)
@pytest.mark.parametrize("marker", RETIREMENT_MARKERS)
def test_retired_history_is_hidden_without_hiding_disabled_unretired_surface(
    surface_name, heading, marker
):
    history = _historical_surface()
    baseline = report_generator.generate_daily_report([], **{surface_name: history})
    assert heading in baseline
    history.update(marker)
    before = deepcopy(history)

    report = report_generator.generate_daily_report([], **{surface_name: history})

    assert heading not in report
    assert history == before


@pytest.mark.parametrize("retire_addon", [False, True])
def test_retired_satellite_addon_does_not_hide_event_bundle(retire_addon):
    bundle = _historical_surface()
    bundle["state_surface_addon"] = {"eligible_candidate_count": 1, "candidate_count": 1}
    satellite = _historical_surface()
    if retire_addon:
        bundle["state_surface_addon"]["retired"] = True
    else:
        satellite["retired"] = True
    before = deepcopy(bundle)

    report = report_generator.generate_daily_report(
        [], event_sleeve_bundle=bundle, state_surface_sleeve=satellite,
        volume_breadth_breakout_paper_sleeve=_historical_surface(),
        fundamental_growth_rs_paper_sleeve=_historical_surface(),
    )

    assert "DEFAULT-OFF EVENT OVERLAY BUNDLE" in report
    assert "VOLUME-BREADTH BREAKOUT PAPER SLEEVE" in report
    assert "FUNDAMENTAL GROWTH + RS PAPER SLEEVE" in report
    assert "State-surface add-on:" not in report
    assert bundle == before


@pytest.mark.parametrize("marker", RETIREMENT_MARKERS)
def test_retired_passed_gates_do_not_count_as_activation_candidates(marker):
    retired_kwargs = {
        name: {**_historical_surface(), **marker}
        for name, _ in REPORT_SURFACES if not name.startswith("space_catalyst")
    }
    retained_kwargs = {
        "volume_breadth_breakout_paper_sleeve": _historical_surface(),
        "fundamental_growth_rs_paper_sleeve": _historical_surface(),
    }
    baseline = attribution.build_default_off_alpha_attribution_report(
        as_of="2026-09-11", **retained_kwargs,
        **{name: _historical_surface() for name in retired_kwargs},
    )
    before = deepcopy(retired_kwargs)
    report = attribution.build_default_off_alpha_attribution_report(
        as_of="2026-09-11", **retained_kwargs, **retired_kwargs,
    )

    assert report["surface_count"] == baseline["surface_count"] - len(retired_kwargs)
    assert report["status_counts"]["eligible_for_review"] == 2
    assert set(report["eligible_for_separate_activation_review"]) == {
        "volume_breadth_breakout", "fundamental_growth_rs",
    }
    retained_names = set(report["eligible_for_separate_activation_review"])
    assert [row for row in report["surfaces"] if row["name"] in retained_names] == [
        row for row in baseline["surfaces"] if row["name"] in retained_names
    ]
    assert retired_kwargs == before


def test_active_pilot_recommendations_skip_allocator_without_reading_its_history(
    monkeypatch, tmp_path
):
    history = {
        "updated_at": "2026-09-11T00:00:00Z",
        "closed_positions": [],
        "open_positions": [],
        "pending_entries": _historical_surface()["pending_entries"],
    }
    reads = []

    def load_state(sleeve):
        reads.append(sleeve)
        return deepcopy(history)

    monkeypatch.setattr(pilot_tracker, "_load_state", load_state)
    monkeypatch.setattr(pilot_tracker, "_load_latest_broker_position_snapshot", lambda: {})
    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "load_cache", lambda: {})
    monkeypatch.setattr(pilot_tracker, "OUT_DIR", tmp_path / "output")

    result = pilot_tracker.generate(write=False)

    assert set(reads) == {"distribution_day_absorption_leadership", "fundamental_growth_rs"}
    assert {row["pilot"] for row in result["recommendations"]} == {
        "distribution_absorption", "fundamental_growth_rs",
    }
    assert all(
        row["actionable"][0]["status"] == "ENTER_NEXT_OPEN"
        for row in result["recommendations"]
    )
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("surface_name", (
    "space_catalyst_shadow", "space_catalyst_observation_slot", "space_catalyst_event_ledger",
))
@pytest.mark.parametrize("marker", RETIREMENT_MARKERS)
def test_retired_space_history_is_not_a_stalled_or_failed_surface(
    surface_name, marker, tmp_path
):
    root = tmp_path / "paper_sleeves"
    for sleeve in ("space_catalyst", "volume_breadth_breakout"):
        directory = root / sleeve
        directory.mkdir(parents=True)
        (directory / "snapshots.jsonl").write_text(
            json.dumps({"asof_date": "2026-06-01"}) + "\n", encoding="utf-8",
        )
    history_path = root / "space_catalyst" / "snapshots.jsonl"
    before = history_path.read_bytes()

    report = sleeve_health.build_sleeve_health_report(
        "2026-09-11", {surface_name: {**_historical_surface(), **marker}},
        sleeves_root=root, persist=False,
    )

    assert report["build_status"][surface_name] == "retired_default_off_paper_disabled"
    assert report["disk_status"]["space_catalyst"]["retired"] is True
    assert report["stalled_sleeves"] == ["volume_breadth_breakout"]
    assert report["failing_builds"] == []
    assert history_path.read_bytes() == before
