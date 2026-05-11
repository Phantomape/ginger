import json
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from pilot_sleeve import (  # noqa: E402
    AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
    CONSUMER_PLATFORM_SLEEVE_NAME,
    SPACE_CATALYST_SHADOW_SLEEVE_NAME,
    apply_pilot_sizing_policy,
    build_counterfactual_snapshots,
    mark_pilot_signals,
    pilot_sleeve_name_for_record,
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


def test_select_pilot_entry_candidates_prioritizes_trade_quality():
    records = {"INTC": {}, "LITE": {}}
    signals = [
        {
            "ticker": "INTC",
            "trade_quality_score": 0.25,
            "confidence_score": 0.95,
            "risk_reward_ratio": 3.0,
            "sizing": {"shares_to_buy": 1},
        },
        {
            "ticker": "LITE",
            "trade_quality_score": 0.80,
            "confidence_score": 0.70,
            "risk_reward_ratio": 1.5,
            "sizing": {"shares_to_buy": 1},
        },
    ]

    selected, audit = select_pilot_entry_candidates(signals, records)

    assert [s["ticker"] for s in selected] == ["LITE"]
    assert (
        audit["selection_policy"]
        == "trade_quality_score_then_confidence_then_risk_reward_with_segment_cap"
    )
    assert [s["ticker"] for s in audit["pilot_slot_sliced_signals"]] == ["INTC"]


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


def test_ai_infra_bull_booster_opens_second_segment_slot():
    records = {
        "INTC": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "compute_memory_semis",
        },
        "LITE": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "optical_connectivity",
        },
    }
    signals = [
        {
            "ticker": "INTC",
            "trade_quality_score": 0.9,
            "sizing": {"shares_to_buy": 1, "position_pct_of_portfolio": 0.08},
        },
        {
            "ticker": "LITE",
            "trade_quality_score": 0.8,
            "sizing": {"shares_to_buy": 1, "position_pct_of_portfolio": 0.08},
        },
    ]

    selected, audit = select_pilot_entry_candidates(
        signals,
        records,
        market_context={
            "market_regime": "BULL",
            "qqq_10d_return": 0.06,
            "spy_10d_return": 0.03,
        },
    )

    assert [s["ticker"] for s in selected] == ["INTC", "LITE"]
    sleeve_audit = audit["by_sleeve"][AI_INFRA_AGGRESSIVE_SLEEVE_NAME]
    assert sleeve_audit["bull_booster_active"] is True
    assert sleeve_audit["max_concurrent_positions"] == 2


def test_ai_infra_segment_cap_blocks_second_same_segment_candidate():
    records = {
        "INTC": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "compute_memory_semis",
        },
        "WDC": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "compute_memory_semis",
        },
    }
    signals = [
        {
            "ticker": "INTC",
            "trade_quality_score": 0.9,
            "sizing": {"shares_to_buy": 1, "position_pct_of_portfolio": 0.08},
        },
        {
            "ticker": "WDC",
            "trade_quality_score": 0.8,
            "sizing": {"shares_to_buy": 1, "position_pct_of_portfolio": 0.08},
        },
    ]

    selected, audit = select_pilot_entry_candidates(
        signals,
        records,
        market_context={
            "market_regime": "BULL",
            "qqq_10d_return": 0.06,
            "spy_10d_return": 0.03,
        },
    )

    assert [s["ticker"] for s in selected] == ["INTC"]
    sliced = audit["by_sleeve"][AI_INFRA_AGGRESSIVE_SLEEVE_NAME][
        "pilot_slot_sliced_signals"
    ]
    assert sliced[0]["ticker"] == "WDC"
    assert sliced[0]["pilot_sleeve"]["slot_decision"] == "sleeve_segment_limit"


def test_ai_infra_sleeve_risk_cap_blocks_extra_candidate():
    records = {
        "INTC": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "compute_memory_semis",
        },
        "LITE": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "optical_connectivity",
        },
    }
    signals = [
        {
            "ticker": "INTC",
            "trade_quality_score": 0.9,
            "sizing": {
                "shares_to_buy": 1,
                "risk_pct": 0.09,
                "position_pct_of_portfolio": 0.04,
            },
        },
        {
            "ticker": "LITE",
            "trade_quality_score": 0.8,
            "sizing": {
                "shares_to_buy": 1,
                "risk_pct": 0.02,
                "position_pct_of_portfolio": 0.04,
            },
        },
    ]

    selected, audit = select_pilot_entry_candidates(
        signals,
        records,
        market_context={
            "market_regime": "BULL",
            "qqq_10d_return": 0.06,
            "spy_10d_return": 0.03,
        },
    )

    assert [s["ticker"] for s in selected] == ["INTC"]
    sleeve_audit = audit["by_sleeve"][AI_INFRA_AGGRESSIVE_SLEEVE_NAME]
    assert sleeve_audit["selected_risk_pct"] == 0.09
    sliced = sleeve_audit["pilot_slot_sliced_signals"]
    assert sliced[0]["ticker"] == "LITE"
    assert sliced[0]["pilot_sleeve"]["slot_decision"] == "sleeve_risk_limit"


def test_independent_consumer_sleeve_does_not_consume_ai_slot():
    records = {
        "INTC": {
            "pilot_sleeve": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
            "theme_segment": "compute_memory_semis",
        },
        "HOOD": {
            "pilot_sleeve": CONSUMER_PLATFORM_SLEEVE_NAME,
            "theme_segment": "consumer_digital_platform",
        },
    }
    signals = [
        {
            "ticker": "INTC",
            "trade_quality_score": 0.9,
            "sizing": {"shares_to_buy": 1, "position_pct_of_portfolio": 0.08},
        },
        {
            "ticker": "HOOD",
            "trade_quality_score": 0.95,
            "sizing": {"shares_to_buy": 1, "position_pct_of_portfolio": 0.05},
        },
    ]

    selected, audit = select_pilot_entry_candidates(signals, records)

    assert sorted(s["ticker"] for s in selected) == ["HOOD", "INTC"]
    assert set(audit["by_sleeve"]) == {
        AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
        CONSUMER_PLATFORM_SLEEVE_NAME,
    }


def test_space_theme_defaults_to_shadow_sleeve_and_segment():
    record = {
        "ticker": "RKLB",
        "status": "research",
        "theme": "space_launch_systems",
        "max_capital_scalar": 0.0,
        "max_risk_scalar": 0.0,
    }
    signal = {"ticker": "RKLB", "sizing": {"shares_to_buy": 10}}

    marked = mark_pilot_signals([signal], {"RKLB": record})

    assert pilot_sleeve_name_for_record(record) == SPACE_CATALYST_SHADOW_SLEEVE_NAME
    assert marked[0]["pilot_sleeve"]["name"] == SPACE_CATALYST_SHADOW_SLEEVE_NAME
    assert marked[0]["pilot_sleeve"]["segment"] == "launch_lunar"


def test_space_catalyst_shadow_policy_has_no_live_slots_even_if_promoted():
    records = {
        "RKLB": {
            "pilot_sleeve": SPACE_CATALYST_SHADOW_SLEEVE_NAME,
            "theme": "space_launch_systems",
            "theme_segment": "launch_lunar",
        }
    }
    signals = [
        {
            "ticker": "RKLB",
            "trade_quality_score": 0.99,
            "sizing": {"shares_to_buy": 10, "position_pct_of_portfolio": 0.03},
        }
    ]

    selected, audit = select_pilot_entry_candidates(signals, records)

    assert selected == []
    sleeve_audit = audit["by_sleeve"][SPACE_CATALYST_SHADOW_SLEEVE_NAME]
    assert sleeve_audit["max_concurrent_positions"] == 0
    assert sleeve_audit["pilot_slot_sliced_signals"][0]["ticker"] == "RKLB"
    assert (
        sleeve_audit["pilot_slot_sliced_signals"][0]["pilot_sleeve"]["slot_decision"]
        == "sleeve_slot_limit"
    )


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


def test_counterfactual_snapshot_freezes_same_sleeve_sliced_candidate():
    snapshots = build_counterfactual_snapshots(
        [
            {
                "ticker": "LITE",
                "strategy": "trend_long",
                "trade_quality_score": 0.9,
                "pilot_sleeve": {
                    "name": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
                    "segment": "optical_connectivity",
                },
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
        pilot_alternative_signals=[
            {
                "ticker": "COHR",
                "strategy": "trend_long",
                "trade_quality_score": 0.85,
                "confidence_score": 0.7,
                "risk_reward_ratio": 2.1,
                "entry_price": 98.0,
                "stop_price": 91.0,
                "target_price": 112.0,
                "pilot_sleeve": {
                    "name": AI_INFRA_AGGRESSIVE_SLEEVE_NAME,
                    "segment": "optical_connectivity",
                    "slot_decision": "sleeve_segment_limit",
                },
                "sizing": {
                    "shares_to_buy": 4,
                    "risk_amount_usd": 28.0,
                },
            },
            {
                "ticker": "HOOD",
                "strategy": "trend_long",
                "trade_quality_score": 0.99,
                "pilot_sleeve": {
                    "name": CONSUMER_PLATFORM_SLEEVE_NAME,
                    "segment": "consumer_digital_platform",
                },
                "sizing": {"shares_to_buy": 5},
            },
        ],
        as_of="2026-05-01",
        metadata={"protocol_version": "universe_protocol_v1.0"},
    )

    counterfactuals = snapshots[0]["counterfactuals"]
    assert [item["shadow_weight"] for item in counterfactuals[:2]] == [0.5, 0.5]
    same_sleeve = [
        item
        for item in counterfactuals
        if item["type"] == "same_sleeve_alternative_candidate"
    ]
    assert len(same_sleeve) == 1
    assert same_sleeve[0]["ticker"] == "COHR"
    assert same_sleeve[0]["shadow_weight"] == 0.0
    assert same_sleeve[0]["evaluation_only"] is True
    assert same_sleeve[0]["slot_decision"] == "sleeve_segment_limit"
    assert "pilot_sliced" in {
        item["status"] for item in snapshots[0]["ranking_snapshot"]
    }
