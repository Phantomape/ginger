import json
import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from space_catalyst_sleeve import (  # noqa: E402
    SPACE_CATALYST_FORWARD_HYPOTHESIS,
    SPACE_CATALYST_LLM_EVENT_FIELDS,
    build_space_catalyst_event_ledger_snapshot,
    build_space_catalyst_observation_slot,
    build_space_catalyst_shadow_snapshot,
    empty_space_catalyst_observation_slot,
    empty_space_catalyst_shadow_snapshot,
    persist_space_catalyst_observation_slot,
    persist_space_catalyst_event_ledger,
    space_catalyst_basket_momentum_state,
    space_catalyst_forward_target_atr_mult,
    space_catalyst_forward_risk_scalar,
    space_catalyst_observation_tickers,
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
    assert snapshot["forward_hypothesis"]["experiment_id"] == "exp-20260512-004"
    assert snapshot["forward_hypothesis"]["risk_budget_scalar"] == 0.75
    assert (
        snapshot["forward_hypothesis"]["data_vendor_breakout_risk_scalar"]
        == 0.1
    )
    assert (
        snapshot["forward_hypothesis"]["launch_connectivity_trend_risk_scalar"]
        == 1.25
    )
    assert snapshot["forward_hypothesis"]["official_trend_target_atr_mult"] == 5.0
    assert (
        snapshot["forward_hypothesis"][
            "launch_connectivity_trend_target_atr_mult"
        ]
        == 7.0
    )
    assert snapshot["forward_hypothesis"]["space_basket_momentum_field"] == (
        "momentum_20d_pct"
    )
    assert (
        snapshot["forward_hypothesis"]["space_basket_positive_risk_scalar"]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"]["space_perfect_tqs_risk_scalar"]
        == 1.5
    )
    assert snapshot["forward_hypothesis"]["space_perfect_tqs_score_floor"] == 1.0
    assert snapshot["forward_hypothesis"]["live_slots"] == 0


def test_empty_space_catalyst_shadow_snapshot_keeps_governance_fields():
    snapshot = empty_space_catalyst_shadow_snapshot("2026-05-11", "unit_test")

    assert snapshot["mode"] == "observe_only"
    assert snapshot["candidate_count"] == 0
    assert snapshot["trade_enabled_tickers"] == []
    assert snapshot["reason"] == "unit_test"
    assert tuple(snapshot["llm_event_fields"]) == SPACE_CATALYST_LLM_EVENT_FIELDS
    assert snapshot["forward_hypothesis"] == SPACE_CATALYST_FORWARD_HYPOTHESIS


def test_space_catalyst_forward_risk_scalar_subbucket_overrides():
    assert space_catalyst_forward_risk_scalar("PL", "breakout_long") == 0.1
    assert space_catalyst_forward_risk_scalar("BKSY", "breakout_long") == 0.1
    assert space_catalyst_forward_risk_scalar("PL", "trend_long") == 1.0
    assert space_catalyst_forward_risk_scalar("RKLB", "trend_long") == 1.25
    assert space_catalyst_forward_risk_scalar("ASTS", "trend_long") == 1.25
    assert space_catalyst_forward_risk_scalar("RKLB", "breakout_long") == 1.0
    assert space_catalyst_forward_risk_scalar(
        "RKLB",
        "trend_long",
        basket_momentum_state={"state": "positive"},
    ) == 1.375
    assert space_catalyst_forward_risk_scalar(
        "RKLB",
        "trend_long",
        basket_momentum_state={"state": "positive"},
        trade_quality_score=1.0,
    ) == 2.0625
    assert round(
        space_catalyst_forward_risk_scalar(
            "PL",
            "breakout_long",
            basket_momentum_state={"state": "positive"},
            trade_quality_score=1.0,
        ),
        6,
    ) == 0.165
    assert round(
        space_catalyst_forward_risk_scalar(
            "PL",
            "breakout_long",
            basket_momentum_state={"state": "positive"},
            trade_quality_score=0.99,
        ),
        6,
    ) == 0.11


def test_space_catalyst_basket_momentum_state_uses_official_pool():
    state = space_catalyst_basket_momentum_state(
        {
            "ASTS": {"momentum_20d_pct": 0.2},
            "BKSY": {"momentum_20d_pct": 0.1},
            "LUNR": {"momentum_20d_pct": -0.05},
            "PL": {"momentum_20d_pct": 0.15},
            "RDW": {"momentum_20d_pct": 0.05},
            "RKLB": {"momentum_20d_pct": 0.15},
        }
    )

    assert state["state"] == "positive"
    assert state["average"] == 0.1
    assert state["available_count"] == 6
    assert state["missing_tickers"] == []


def test_space_catalyst_forward_target_atr_mult_official_trends_only():
    assert space_catalyst_forward_target_atr_mult("RKLB", "trend_long", 4.5) == 7.0
    assert space_catalyst_forward_target_atr_mult("ASTS", "trend_long", 4.5) == 7.0
    assert space_catalyst_forward_target_atr_mult("RDW", "trend_long", 4.5) == 5.0
    assert space_catalyst_forward_target_atr_mult("RKLB", "breakout_long", 4.5) == 4.5
    assert space_catalyst_forward_target_atr_mult("IRDM", "trend_long", 4.5) == 4.5


def test_space_catalyst_observation_tickers_use_official_forward_pool():
    assert space_catalyst_observation_tickers({}) == [
        "ASTS",
        "BKSY",
        "LUNR",
        "PL",
        "RDW",
        "RKLB",
    ]


def test_empty_space_catalyst_observation_slot_is_blocked_by_default():
    snapshot = empty_space_catalyst_observation_slot("2026-05-11", "unit_test")

    assert snapshot["enabled"] is True
    assert snapshot["trade_enabled"] is False
    assert snapshot["live_slots"] == 0
    assert snapshot["slot_count"] == 1
    assert snapshot["reason"] == "unit_test"
    assert snapshot["production_impact"]["alters_orders"] is False


def test_space_catalyst_observation_slot_blocks_trade_plan_and_applies_policy():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RKLB",
                "strategy": "trend_long",
                "entry_price": 100.0,
                "stop_price": 92.5,
                "target_price": 117.5,
                "target_mult_used": 3.5,
                "risk_reward_ratio": 2.33,
                "net_risk_reward_ratio": 1.9,
                "exec_lag_adj_net_rr": 1.6,
                "confidence_score": 0.9,
                "trade_quality_score": 0.82,
                "sizing": {
                    "shares_to_buy": 10,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            },
            {
                "ticker": "IRDM",
                "strategy": "trend_long",
                "entry_price": 25.0,
                "stop_price": 23.0,
                "target_price": 32.0,
                "confidence_score": 0.95,
                "trade_quality_score": 0.9,
            },
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.1},
            "BKSY": {"momentum_20d_pct": 0.1},
            "LUNR": {"momentum_20d_pct": 0.1},
            "PL": {"momentum_20d_pct": 0.1},
            "RDW": {"momentum_20d_pct": 0.1},
            "RKLB": {"atr": 5.0, "momentum_20d_pct": 0.1},
            "IRDM": {"atr": 1.0},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {"launch_lunar": ["RKLB"]},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        core_signals=[{"ticker": "AMD", "strategy": "trend_long"}],
        entry_execution_plan={"available_slots": 1, "slot_sliced_signals": []},
        portfolio_heat={"portfolio_heat_pct": 0.03, "can_add_new_positions": True},
        entry_filter_audit={
            "signals_before_entry_filters": 1,
            "signals_after_entry_filters": 1,
        },
        raw_signal_count=1,
        enriched_signal_count=1,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["candidate_count"] == 1
    assert snapshot["selected_count"] == 1
    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "RKLB"
    assert plan["forward_target_price"] == 135.0
    assert plan["target_atr_mult"] == 7.0
    assert plan["space_basket_momentum_state"] == "positive"
    assert plan["space_basket_momentum_20d_pct"] == 0.1
    assert plan["space_perfect_tqs_bucket"] is False
    assert plan["space_perfect_tqs_risk_scalar"] == 1.0
    assert plan["effective_risk_scalar"] == 1.03125
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 1031.25
    assert plan["blocked_reason"] == "live_slots_zero_forward_gate_pending"
    assert plan["same_day_core_alternative_count"] == 1
    assert snapshot["production_impact"]["alters_orders"] is False


def test_space_catalyst_observation_slot_persistence_dedupes_daily_plan(tmp_path):
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "LUNR",
                "strategy": "trend_long",
                "entry_price": 10.0,
                "stop_price": 9.0,
                "target_price": 13.5,
                "target_mult_used": 3.5,
                "confidence_score": 0.88,
                "trade_quality_score": 0.8,
            }
        ],
        features_by_ticker={"LUNR": {"atr": 1.0}},
        space_catalyst_shadow={
            "tickers_by_segment": {"launch_lunar": ["LUNR"]},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
    )
    ledger_path = tmp_path / "observation.jsonl"
    summary_path = tmp_path / "observation_summary.json"

    first = persist_space_catalyst_observation_slot(
        snapshot,
        ledger_path=ledger_path,
        summary_path=summary_path,
    )
    second = persist_space_catalyst_observation_slot(
        snapshot,
        ledger_path=ledger_path,
        summary_path=summary_path,
    )

    assert first["persistence"]["appended_count"] == 1
    assert second["persistence"]["appended_count"] == 0
    assert second["persistence"]["ledger_row_count"] == 1


def test_space_catalyst_event_ledger_tracks_closed_10d_outcome(tmp_path):
    seed_path = tmp_path / "space_events.jsonl"
    _write_events(
        seed_path,
        [
            {
                "event_id": "unit_lunr_contract",
                "event_date": "2026-05-01",
                "tickers": ["LUNR"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "event_fields": ["government_space_contract"],
                "description": "unit event",
            }
        ],
    )
    dates = [
        "2026-05-01",
        "2026-05-04",
        "2026-05-05",
        "2026-05-06",
        "2026-05-07",
        "2026-05-08",
        "2026-05-11",
        "2026-05-12",
        "2026-05-13",
        "2026-05-14",
        "2026-05-15",
        "2026-05-18",
    ]
    lunr = [
        {"Date": date, "Close": close}
        for date, close in zip(dates, [10, 11, 12, 12, 12, 12, 12, 12, 12, 12, 12, 13])
    ]
    spy = [{"Date": date, "Close": close} for date, close in zip(dates, range(100, 112))]

    snapshot = build_space_catalyst_event_ledger_snapshot(
        as_of="2026-05-18",
        source_path=seed_path,
        ohlcv_by_ticker={"LUNR": lunr, "SPY": spy},
        space_catalyst_shadow={
            "tickers_by_segment": {"launch_lunar": ["LUNR"]},
            "forward_hypothesis": {"included_tickers": ["LUNR"]},
        },
        core_signals=[{"ticker": "AMD", "strategy": "trend_long"}],
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["active_event_count"] == 1
    assert snapshot["event_row_count"] == 1
    assert snapshot["closed_decision_count"] == 1
    row = snapshot["event_rows"][0]
    assert row["entry_date"] == "2026-05-04"
    assert row["closed_decision"] is True
    assert row["horizons"]["10d"]["event_return"] == round(13 / 11 - 1, 6)
    assert row["same_day_core_alternative_count"] == 1
    assert snapshot["promotion_gate"]["passed"] is False


def test_space_catalyst_event_ledger_persistence_dedupes_daily_rows(tmp_path):
    snapshot = build_space_catalyst_event_ledger_snapshot(
        as_of="2026-05-04",
        events=[
            {
                "event_id": "unit_space_attention",
                "event_date": "2026-05-01",
                "tickers": ["UFO"],
                "semantic_bucket": "attention_only",
                "event_fields": ["uap_attention_spike"],
            }
        ],
        ohlcv_by_ticker={
            "UFO": [
                {"Date": "2026-05-01", "Close": 20},
                {"Date": "2026-05-04", "Close": 21},
            ]
        },
    )
    ledger_path = tmp_path / "ledger.jsonl"
    summary_path = tmp_path / "summary.json"

    first = persist_space_catalyst_event_ledger(
        snapshot,
        ledger_path=ledger_path,
        summary_path=summary_path,
    )
    second = persist_space_catalyst_event_ledger(
        snapshot,
        ledger_path=ledger_path,
        summary_path=summary_path,
    )

    assert first["persistence"]["appended_count"] == 1
    assert second["persistence"]["appended_count"] == 0
    assert second["persistence"]["ledger_row_count"] == 1


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
                "data_vendor_breakout_risk_scalar": 0.1,
                "launch_connectivity_trend_risk_scalar": 1.25,
                "launch_connectivity_trend_target_atr_mult": 7.0,
                "official_trend_target_atr_mult": 5.0,
                "space_basket_positive_risk_scalar": 1.1,
                "space_perfect_tqs_risk_scalar": 1.5,
            },
            "promotion_gates": {"minimum_closed_decisions": 10},
        },
        space_catalyst_observation_slot={
            "mode": "production_observe_only",
            "trade_enabled": False,
            "live_slots": 0,
            "candidate_count": 1,
            "selected_count": 1,
            "persistence": {"ledger_row_count": 1, "appended_count": 1},
            "blocked_trade_plans": [
                {
                    "ticker": "RKLB",
                    "strategy": "trend_long",
                    "entry_price": 100.0,
                    "forward_target_price": 125.0,
                    "trade_quality_score": 0.82,
                    "effective_risk_scalar": 1.03125,
                    "space_basket_momentum_state": "positive",
                    "space_perfect_tqs_bucket": False,
                    "blocked_reason": "live_slots_zero_forward_gate_pending",
                }
            ],
        },
        space_catalyst_event_ledger={
            "mode": "observe_only",
            "active_event_count": 1,
            "event_row_count": 1,
            "closed_decision_count": 0,
            "promotion_gate": {"passed": False, "reason": "insufficient_closed"},
            "aggregate": {
                "by_semantic_bucket_count": {
                    "fundamental_contract_regulatory": 1,
                }
            },
            "event_rows": [
                {
                    "ticker": "LUNR",
                    "semantic_bucket": "fundamental_contract_regulatory",
                    "event_date": "2026-05-01",
                    "closed_decision": False,
                    "horizons": {"10d": {"status": "pending"}},
                }
            ],
            "persistence": {"ledger_row_count": 1, "appended_count": 1},
        },
    )

    assert "SPACE CATALYST SHADOW UNIVERSE" in report
    assert "Trade-enabled: 0" in report
    assert "launch_lunar: RKLB" in report
    assert (
        "official_catalyst_operating_growth @ 0.75x risk "
        "(default off; data-vendor breakout @ 0.1x; "
        "launch/connectivity trend @ 1.25x; "
        "launch/connectivity trend target @ 7.0 ATR; "
        "official trend target @ 5.0 ATR; "
        "Space basket positive 20d momentum @ 1.1x; "
        "perfect Space TQS @ 1.5x)"
    ) in report
    assert "SPACE CATALYST EVENT LEDGER" in report
    assert "SPACE CATALYST PRODUCTION OBSERVATION SLOT" in report
    assert "Live slots: 0" in report
    assert "RKLB: trend_long entry $100.00 target $125.00" in report
    assert "risk=1.03125x basket=positive" in report
    assert "Closed 10d: 0" in report
    assert "LUNR: fundamental_contract_regulatory" in report
