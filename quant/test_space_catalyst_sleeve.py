import json
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from space_catalyst_sleeve import (  # noqa: E402
    SPACE_CATALYST_FORWARD_HYPOTHESIS,
    SPACE_CATALYST_LLM_EVENT_FIELDS,
    build_space_catalyst_shadow_snapshot,
    empty_space_catalyst_shadow_snapshot,
    space_catalyst_records_as_of,
)
from report_generator import generate_daily_report  # noqa: E402


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_events(path, events):
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def test_space_catalyst_records_include_research_and_optional_quarantine(tmp_path):
    registry_path = tmp_path / "registry.json"
    events_path = tmp_path / "events.jsonl"
    _write_json(
        registry_path,
        {
            "schema_version": 1,
            "protocol_version": "universe_protocol_v1.0",
            "tickers": {},
        },
    )
    _write_events(
        events_path,
        [
            {
                "event_id": "space-rklb",
                "effective_as_of": "2026-05-10",
                "ticker": "RKLB",
                "to_status": "research",
                "record_patch": {
                    "ticker": "RKLB",
                    "status": "research",
                    "theme": "space_launch_systems",
                    "pilot_sleeve": "SPACE_CATALYST_SHADOW",
                    "theme_segment": "launch_lunar",
                    "first_trade_allowed_as_of": None,
                    "max_capital_scalar": 0,
                    "max_risk_scalar": 0,
                },
            },
            {
                "event_id": "space-spce",
                "effective_as_of": "2026-05-10",
                "ticker": "SPCE",
                "to_status": "quarantine",
                "record_patch": {
                    "ticker": "SPCE",
                    "status": "quarantine",
                    "theme": "space_tourism_meme",
                    "pilot_sleeve": "SPACE_CATALYST_SHADOW",
                    "theme_segment": "quarantine_meme",
                    "first_trade_allowed_as_of": None,
                    "max_capital_scalar": 0,
                    "max_risk_scalar": 0,
                },
            },
        ],
    )

    all_records = space_catalyst_records_as_of(
        "2026-05-10",
        registry_path=registry_path,
        events_path=events_path,
    )
    non_quarantine = space_catalyst_records_as_of(
        "2026-05-10",
        registry_path=registry_path,
        events_path=events_path,
        include_quarantine=False,
    )

    assert sorted(all_records) == ["RKLB", "SPCE"]
    assert sorted(non_quarantine) == ["RKLB"]


def test_space_catalyst_shadow_snapshot_is_observe_only(tmp_path):
    registry_path = tmp_path / "registry.json"
    events_path = tmp_path / "events.jsonl"
    _write_json(
        registry_path,
        {
            "schema_version": 1,
            "protocol_version": "universe_protocol_v1.0",
            "tickers": {},
        },
    )
    _write_events(
        events_path,
        [
            {
                "event_id": "space-asts",
                "effective_as_of": "2026-05-10",
                "ticker": "ASTS",
                "to_status": "research",
                "record_patch": {
                    "ticker": "ASTS",
                    "status": "research",
                    "theme": "space_satellite_connectivity",
                    "pilot_sleeve": "SPACE_CATALYST_SHADOW",
                    "theme_segment": "satellite_connectivity",
                    "first_trade_allowed_as_of": None,
                    "max_capital_scalar": 0,
                    "max_risk_scalar": 0,
                },
            }
        ],
    )

    snapshot = build_space_catalyst_shadow_snapshot(
        "2026-05-10",
        registry_path=registry_path,
        events_path=events_path,
    )

    assert snapshot["mode"] == "observe_only"
    assert snapshot["trade_enabled_tickers"] == []
    assert snapshot["candidate_count"] == 1
    assert snapshot["tickers_by_segment"] == {"satellite_connectivity": ["ASTS"]}
    assert "spacex_ipo_proxy" in snapshot["llm_event_fields"]
    assert tuple(snapshot["llm_event_fields"]) == SPACE_CATALYST_LLM_EVENT_FIELDS
    assert snapshot["forward_hypothesis"] == SPACE_CATALYST_FORWARD_HYPOTHESIS
    assert snapshot["forward_hypothesis"]["risk_budget_scalar"] == 0.75
    assert snapshot["forward_hypothesis"]["live_slots"] == 0


def test_empty_space_catalyst_shadow_snapshot_keeps_governance_fields():
    snapshot = empty_space_catalyst_shadow_snapshot("2026-05-11", "unit_test")

    assert snapshot["mode"] == "observe_only"
    assert snapshot["candidate_count"] == 0
    assert snapshot["trade_enabled_tickers"] == []
    assert snapshot["reason"] == "unit_test"
    assert tuple(snapshot["llm_event_fields"]) == SPACE_CATALYST_LLM_EVENT_FIELDS
    assert snapshot["forward_hypothesis"] == SPACE_CATALYST_FORWARD_HYPOTHESIS


def test_report_generator_renders_space_catalyst_without_orders():
    report = generate_daily_report(
        signals=[],
        space_catalyst_shadow={
            "mode": "observe_only",
            "candidate_count": 2,
            "trade_enabled_tickers": [],
            "tickers_by_segment": {
                "launch_lunar": ["RKLB"],
                "satellite_connectivity": ["ASTS"],
            },
            "llm_event_fields": ["launch_success", "dilution_risk"],
            "forward_hypothesis": {
                "candidate_pool": "official_catalyst_operating_growth",
                "risk_budget_scalar": 0.75,
            },
            "promotion_gates": {"minimum_closed_decisions": 10},
        },
    )

    assert "SPACE CATALYST SHADOW UNIVERSE" in report
    assert "Trade-enabled: 0" in report
    assert "launch_lunar: RKLB" in report
    assert "official_catalyst_operating_growth @ 0.75x risk" in report
