import json
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from pilot_sleeve import (  # noqa: E402
    apply_pilot_sizing_policy,
    build_counterfactual_snapshots,
    mark_pilot_signals,
    pilot_records_as_of,
    select_pilot_entry_candidates,
)


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_events(path, events):
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )


def test_pilot_records_require_trade_allowed_date(tmp_path):
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
                "event_id": "1",
                "effective_as_of": "2026-05-01",
                "ticker": "INTC",
                "to_status": "pilot",
                "record_patch": {
                    "ticker": "INTC",
                    "status": "pilot",
                    "theme": "ai_semiconductor_turnaround",
                    "eligible_as_of": "2026-05-01",
                    "first_trade_allowed_as_of": "2026-05-06",
                    "max_risk_scalar": 0.35,
                },
            }
        ],
    )

    assert pilot_records_as_of(
        "2026-05-05",
        registry_path=registry_path,
        events_path=events_path,
    ) == {}
    assert "INTC" in pilot_records_as_of(
        "2026-05-06",
        registry_path=registry_path,
        events_path=events_path,
    )


def test_mark_and_scale_pilot_signal_uses_registry_scalars():
    records = {
        "LITE": {
            "ticker": "LITE",
            "status": "pilot",
            "theme": "ai_optical_connectivity",
            "history_class": "full_history",
            "liquidity_tier": "ok",
            "requires_event_guard": True,
            "event_guard_profile": "earnings_sensitive",
            "max_capital_scalar": 0.5,
            "max_risk_scalar": 0.35,
            "competes_for_core_slots": False,
            "rule_version": "universe_protocol_v1.0",
        }
    }
    signal = {
        "ticker": "LITE",
        "strategy": "trend_long",
        "sizing": {
            "shares_to_buy": 10,
            "risk_pct": 0.01,
            "risk_amount_usd": 1000.0,
            "position_value_usd": 20000.0,
            "position_pct_of_portfolio": 0.2,
        },
    }

    marked = mark_pilot_signals([signal], records, metadata={"registry_hash": "abc"})
    scaled = apply_pilot_sizing_policy(marked, records)

    assert scaled[0]["pilot_trade_enabled"] is True
    assert scaled[0]["pilot_sleeve"]["theme"] == "ai_optical_connectivity"
    assert scaled[0]["sizing"]["shares_to_buy"] == 3
    assert scaled[0]["sizing"]["pilot_sleeve_scalar_applied"] == 0.35
    assert scaled[0]["sizing"]["risk_amount_usd"] == 300.0


def test_select_pilot_entry_candidates_limits_concurrent_slots():
    records = {"INTC": {}, "LITE": {}}
    signals = [
        {"ticker": "INTC", "sizing": {"shares_to_buy": 1}},
        {"ticker": "LITE", "sizing": {"shares_to_buy": 1}},
    ]

    selected, audit = select_pilot_entry_candidates(signals, records)

    assert [s["ticker"] for s in selected] == ["INTC"]
    assert audit["signals_after_pilot_slotting"] == 1
    assert [s["ticker"] for s in audit["pilot_slot_sliced_signals"]] == ["LITE"]


def test_select_pilot_entry_candidates_blocks_when_existing_pilot_is_open():
    records = {"INTC": {}}
    open_positions = {"positions": [{"ticker": "INTC", "shares": 5}]}
    signals = [{"ticker": "INTC", "sizing": {"shares_to_buy": 1}}]

    selected, audit = select_pilot_entry_candidates(
        signals,
        records,
        open_positions=open_positions,
    )

    assert selected == []
    assert audit["available_pilot_slots"] == 0
    assert audit["active_pilot_positions"] == ["INTC"]


def test_counterfactual_snapshot_uses_core_displaced_candidate():
    snapshots = build_counterfactual_snapshots(
        [
            {
                "ticker": "BE",
                "strategy": "trend_long",
                "trade_quality_score": 0.9,
                "sizing": {"shares_to_buy": 2},
            }
        ],
        core_signals=[
            {
                "ticker": "AMD",
                "strategy": "breakout_long",
                "trade_quality_score": 0.8,
                "sizing": {"shares_to_buy": 3},
            }
        ],
        as_of="2026-05-01",
        metadata={"protocol_version": "universe_protocol_v1.0"},
    )

    assert snapshots[0]["pilot_ticker"] == "BE"
    assert snapshots[0]["counterfactuals"][0]["ticker"] == "AMD"
    assert snapshots[0]["counterfactuals"][1]["ticker"] == "CASH"
