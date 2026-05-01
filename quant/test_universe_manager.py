import json
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from candidate_competition_logger import (  # noqa: E402
    append_decision_snapshot,
    risk_adjusted_replacement_value,
)
from universe_manager import (  # noqa: E402
    eligible_tickers_as_of,
    replay_events_as_of,
    validate_registry,
)


def test_replay_events_ignores_future_status_changes():
    events = [
        {
            "event_id": "1",
            "effective_as_of": "2026-05-01",
            "ticker": "LITE",
            "to_status": "research",
            "record_patch": {
                "ticker": "LITE",
                "status": "research",
                "eligible_as_of": "2026-05-01",
            },
        },
        {
            "event_id": "2",
            "effective_as_of": "2026-05-10",
            "ticker": "LITE",
            "to_status": "pilot",
            "record_patch": {
                "ticker": "LITE",
                "status": "pilot",
                "eligible_as_of": "2026-05-01",
                "first_trade_allowed_as_of": "2026-05-11",
            },
        },
    ]

    before = replay_events_as_of(events, "2026-05-05")
    after = replay_events_as_of(events, "2026-05-12")

    assert before["LITE"]["status"] == "research"
    assert after["LITE"]["status"] == "pilot"


def test_eligible_tickers_respects_first_trade_allowed_date(tmp_path):
    events_path = tmp_path / "events.jsonl"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps({"schema_version": 1, "tickers": {}}),
        encoding="utf-8",
    )
    event = {
        "event_id": "1",
        "effective_as_of": "2026-05-01",
        "ticker": "INTC",
        "to_status": "pilot",
        "record_patch": {
            "ticker": "INTC",
            "status": "pilot",
            "eligible_as_of": "2026-05-01",
            "first_trade_allowed_as_of": "2026-05-06",
        },
    }
    events_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    assert eligible_tickers_as_of(
        "2026-05-05",
        events_path=events_path,
        registry_path=registry_path,
    ) == []
    assert eligible_tickers_as_of(
        "2026-05-06",
        events_path=events_path,
        registry_path=registry_path,
    ) == ["INTC"]


def test_registry_validation_requires_trade_date_for_pilot():
    registry = {
        "schema_version": 1,
        "tickers": {
            "BE": {
                "ticker": "BE",
                "status": "pilot",
                "theme": "ai_power_energy",
                "discovered_as_of": "2026-05-01",
                "eligible_as_of": "2026-05-01",
                "first_trade_allowed_as_of": None,
                "status_effective_as_of": "2026-05-01",
                "decision_as_of": "2026-05-01",
                "data_available_as_of": "2026-05-01",
                "rule_version": "universe_protocol_v1.0",
                "source": "test",
                "history_class": "full_history",
                "liquidity_tier": "ok",
                "max_capital_scalar": 0.5,
                "max_risk_scalar": 0.2,
                "requires_event_guard": True,
                "event_guard_profile": "earnings_sensitive",
                "created_by": "test",
                "last_reviewed_at": "2026-05-01",
            }
        },
    }

    issues = validate_registry(registry)

    assert any("first_trade_allowed_as_of" in issue for issue in issues)


def test_decision_snapshot_requires_counterfactual_before_logging(tmp_path):
    path = tmp_path / "decisions.jsonl"
    snapshot = {
        "decision_id": "pilot-1",
        "timestamp": "2026-05-01T09:25:00-07:00",
        "sleeve": "AI_INFRA_PILOT",
        "pilot_ticker": "LITE",
        "action": "BUY",
        "protocol_version": "universe_protocol_v1.0",
        "ranking_snapshot": [
            {"ticker": "LITE", "score": 0.76, "status": "pilot"},
            {"ticker": "AMD", "score": 0.71, "status": "core"},
        ],
        "counterfactuals": [
            {
                "type": "primary_displaced_candidate",
                "ticker": "AMD",
                "shadow_weight": 0.7,
            },
            {"type": "cash_baseline", "ticker": "CASH", "shadow_weight": 0.3},
        ],
        "risk_snapshot": {
            "pilot_expected_vol": 0.034,
            "replacement_expected_vol": 0.028,
        },
    }

    digest = append_decision_snapshot(snapshot, path)

    assert len(digest) == 16
    assert path.read_text(encoding="utf-8").count("decision_snapshot") == 1


def test_risk_adjusted_replacement_value_compares_risk_units():
    value = risk_adjusted_replacement_value(
        pilot_pnl=1200,
        replacement_pnl=800,
        pilot_risk=300,
        replacement_risk=400,
    )

    assert value == 2.0
