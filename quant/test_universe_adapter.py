import json
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from universe_adapter import universe_segments_as_of  # noqa: E402


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_read_only_adapter_keeps_pilot_out_of_core_trade_universe(tmp_path):
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
    events = [
        {
            "event_id": "1",
            "effective_as_of": "2026-05-01",
            "ticker": "LITE",
            "to_status": "pilot",
            "record_patch": {
                "ticker": "LITE",
                "status": "pilot",
                "eligible_as_of": "2026-05-01",
                "first_trade_allowed_as_of": "2026-05-06",
            },
        },
        {
            "event_id": "2",
            "effective_as_of": "2026-05-01",
            "ticker": "OLD",
            "to_status": "core",
            "record_patch": {
                "ticker": "OLD",
                "status": "core",
                "eligible_as_of": "2026-05-01",
                "first_trade_allowed_as_of": "2026-05-01",
            },
        },
    ]
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    state = universe_segments_as_of(
        "2026-05-06",
        core_universe=["AMD", "LITE"],
        registry_path=registry_path,
        events_path=events_path,
    )

    assert state["mode"] == "read_only"
    assert "LITE" in state["segments"]["pilot"]
    assert "LITE" in state["observation_universe"]
    assert "LITE" not in state["core_trade_universe"]
    assert state["core_trade_universe"] == ["AMD", "OLD"]
    assert state["production_impact"]["alters_orders"] is False


def test_adapter_reports_hashes_and_event_counts(tmp_path):
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
    events_path.write_text("", encoding="utf-8")

    state = universe_segments_as_of(
        "2026-05-01",
        core_universe=["AMD"],
        registry_path=registry_path,
        events_path=events_path,
    )

    assert state["registry_hash"]
    assert state["event_ledger_hash"]
    assert state["event_count"] == 0
    assert state["core_trade_universe"] == ["AMD"]
