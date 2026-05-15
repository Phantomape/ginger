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
    space_catalyst_attention_overlay_profiles,
    space_catalyst_forward_replacement_positive_profiles,
    space_catalyst_forward_target_atr_mult,
    space_catalyst_forward_risk_scalar,
    space_catalyst_government_contract_profiles,
    space_catalyst_iwm_relative_momentum_state,
    space_catalyst_multi_event_depth_profiles,
    space_catalyst_official_customer_source_profiles,
    space_catalyst_observation_feature_tickers,
    space_catalyst_observation_tickers,
    space_catalyst_peer_momentum_state,
    space_catalyst_records_as_of,
    space_catalyst_single_event_defense_profiles,
    space_catalyst_source_diversity_profiles,
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
                    "liquidity_tier": "watch",
                    "event_guard_profile": "satellite_launch_and_financing_sensitive",
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
    assert snapshot["tickers_by_liquidity_tier"] == {"watch": ["ASTS"]}
    assert snapshot["tickers_by_event_guard_profile"] == {
        "satellite_launch_and_financing_sensitive": ["ASTS"]
    }
    assert "spacex_ipo_proxy" in snapshot["llm_event_fields"]
    assert tuple(snapshot["llm_event_fields"]) == SPACE_CATALYST_LLM_EVENT_FIELDS
    assert snapshot["forward_hypothesis"] == SPACE_CATALYST_FORWARD_HYPOTHESIS
    assert snapshot["forward_hypothesis"]["experiment_id"] == "exp-20260513-113"
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
    assert (
        snapshot["forward_hypothesis"][
            "space_near_perfect_tqs_trend_risk_scalar"
        ]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"]["space_near_perfect_tqs_score_floor"]
        == 0.95
    )
    assert (
        snapshot["forward_hypothesis"]["space_near_perfect_tqs_score_ceiling"]
        == 1.0
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_peer_nonleader_breakout_experiment_id"
        ]
        == "exp-20260512-013"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_peer_nonleader_breakout_risk_scalar"
        ]
        == 0.0
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_iwm_relative_momentum_experiment_id"
        ]
        == "exp-20260512-031"
    )
    assert (
        snapshot["forward_hypothesis"]["space_iwm_relative_momentum_ticker"]
        == "IWM"
    )
    assert (
        snapshot["forward_hypothesis"]["space_iwm_relative_momentum_reference"]
        == "SPY"
    )
    assert (
        snapshot["forward_hypothesis"]["space_iwm_relative_leader_risk_scalar"]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_iwm_peer_leader_trend_experiment_id"
        ]
        == "exp-20260513-020"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_iwm_peer_leader_trend_risk_scalar"
        ]
        == 1.15
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_launch_lunar_theme_segment_experiment_id"
        ]
        == "exp-20260512-032"
    )
    assert (
        snapshot["forward_hypothesis"]["space_launch_lunar_theme_segment"]
        == "launch_lunar"
    )
    assert (
        snapshot["forward_hypothesis"]["space_launch_lunar_theme_risk_scalar"]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"]["space_liquidity_tier_experiment_id"]
        == "exp-20260512-037"
    )
    assert snapshot["forward_hypothesis"]["space_liquidity_tier"] == "ok"
    assert (
        snapshot["forward_hypothesis"]["space_liquidity_tier_risk_scalar"]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"]["space_watch_liquidity_tier_experiment_id"]
        == "exp-20260512-112"
    )
    assert snapshot["forward_hypothesis"]["space_watch_liquidity_tier"] == "watch"
    assert (
        snapshot["forward_hypothesis"]["space_watch_liquidity_tier_risk_scalar"]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_official_customer_source_experiment_id"
        ]
        == "exp-20260512-038"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_official_customer_source_event_field"
        ]
        == "customer_win"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_official_customer_source_risk_scalar"
        ]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_customer_source_peer_leader_experiment_id"
        ]
        == "exp-20260513-014"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_customer_source_peer_leader_risk_scalar"
        ]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_government_contract_peer_leader_experiment_id"
        ]
        == "exp-20260513-015"
    )
    assert (
        snapshot["forward_hypothesis"]["space_government_contract_event_field"]
        == "government_space_contract"
    )
    assert snapshot["forward_hypothesis"][
        "space_government_contract_source_types"
    ] == ["official_or_primary_release", "official_government_release"]
    assert (
        snapshot["forward_hypothesis"][
            "space_government_contract_peer_leader_risk_scalar"
        ]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_company_release_customer_source_experiment_id"
        ]
        == "exp-20260512-110"
    )
    assert snapshot["forward_hypothesis"][
        "space_company_release_customer_source_types"
    ] == ["company_release"]
    assert (
        snapshot["forward_hypothesis"][
            "space_company_release_customer_source_risk_scalar"
        ]
        == 1.1
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_financing_dilution_profile_experiment_id"
        ]
        == "exp-20260512-041"
    )
    assert snapshot["forward_hypothesis"][
        "space_financing_dilution_profile_terms"
    ] == ["financing", "dilution"]
    assert (
        snapshot["forward_hypothesis"][
            "space_financing_dilution_profile_risk_scalar"
        ]
        == 1.075
    )
    assert (
        snapshot["forward_hypothesis"]["space_multi_event_depth_experiment_id"]
        == "exp-20260513-012"
    )
    assert snapshot["forward_hypothesis"]["space_multi_event_depth_min_count"] == 2
    assert (
        snapshot["forward_hypothesis"]["space_multi_event_depth_risk_scalar"]
        == 1.075
    )
    assert (
        snapshot["forward_hypothesis"]["space_single_event_defense_risk_scalar"]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"]["space_attention_overlay_experiment_id"]
        == "exp-20260513-032"
    )
    assert snapshot["forward_hypothesis"][
        "space_attention_overlay_event_fields"
    ] == ["spacex_ipo_proxy", "uap_attention_spike"]
    assert (
        snapshot["forward_hypothesis"]["space_attention_overlay_risk_scalar"]
        == 1.25
    )
    assert (
        snapshot["forward_hypothesis"]["space_source_diversity_experiment_id"]
        == "exp-20260513-038"
    )
    assert (
        snapshot["forward_hypothesis"]["space_source_diversity_min_source_types"]
        == 2
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_min_semantic_buckets"
        ]
        == 2
    )
    assert (
        snapshot["forward_hypothesis"]["space_source_diversity_risk_scalar"]
        == 1.075
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_peer_leader_experiment_id"
        ]
        == "exp-20260513-039"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_peer_leader_risk_scalar"
        ]
        == 1.15
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_iwm_leader_experiment_id"
        ]
        == "exp-20260513-108"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_iwm_leader_risk_scalar"
        ]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_peer_iwm_leader_experiment_id"
        ]
        == "exp-20260513-110"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_peer_iwm_leader_risk_scalar"
        ]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_trend_experiment_id"
        ]
        == "exp-20260514-028"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_trend_risk_scalar"
        ]
        == 1.025
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_peer_nonleader_trend_experiment_id"
        ]
        == "exp-20260515-024"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_source_diversity_peer_nonleader_trend_risk_scalar"
        ]
        == 1.025
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_positive_experiment_id"
        ]
        == "exp-20260513-113"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_positive_horizon"
        ]
        == "10d"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_positive_risk_scalar"
        ]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_same_theme_strength_risk_scalar"
        ]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_trend_strength_risk_scalar"
        ]
        == 1.05
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_iwm_leader_trend_experiment_id"
        ]
        == "exp-20260514-024"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_iwm_leader_trend_risk_scalar"
        ]
        == 1.025
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_company_source_trend_experiment_id"
        ]
        == "exp-20260514-026"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_forward_replacement_company_source_trend_risk_scalar"
        ]
        == 1.025
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_benchmark_breadth_trend_experiment_id"
        ]
        == "exp-20260514-041"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_benchmark_breadth_trend_risk_scalar"
        ]
        == 1.025
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_defense_budget_delayed_benchmark_trend_experiment_id"
        ]
        == "exp-20260514-051"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_defense_budget_delayed_benchmark_trend_risk_scalar"
        ]
        == 1.025
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_benchmark_breadth_iwm_leader_trend_experiment_id"
        ]
        == "exp-20260514-053"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_benchmark_breadth_iwm_leader_trend_risk_scalar"
        ]
        == 1.0125
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_defense_budget_same_theme_winner_trend_experiment_id"
        ]
        == "exp-20260515-021"
    )
    assert (
        snapshot["forward_hypothesis"][
            "space_defense_budget_same_theme_winner_trend_risk_scalar"
        ]
        == 1.05
    )
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
        trade_quality_score=0.956,
    ) == 1.375
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            basket_momentum_state={"state": "positive"},
            trade_quality_score=0.956,
        ),
        6,
    ) == 1.5125
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
    assert (
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "breakout_long",
            peer_momentum_state={"state": "nonleader"},
        )
        == 0.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "breakout_long",
            peer_momentum_state={"state": "leader"},
        )
        == 1.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "PL",
            "breakout_long",
            basket_momentum_state={"state": "positive"},
            peer_momentum_state={"state": "nonleader"},
            trade_quality_score=1.0,
        )
        == 0.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            iwm_relative_momentum_state={"state": "smallcap_leader"},
        )
        == 1.1
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            iwm_relative_momentum_state={"state": "smallcap_leader"},
            peer_momentum_state={"state": "leader"},
        )
        == 1.265
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            iwm_relative_momentum_state={"state": "smallcap_laggard"},
        )
        == 1.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            theme_segment="launch_lunar",
        )
        == 1.1
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "ASTS",
            "trend_long",
            theme_segment="satellite_connectivity",
        )
        == 1.25
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            liquidity_tier="ok",
        )
        == 1.375
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            liquidity_tier="watch",
        )
        == 1.1
    )
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            liquidity_tier="ok",
            official_customer_source_profile={"event_ids": ["rklb_customer_win"]},
        ),
        6,
    ) == 1.5125
    assert round(
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            official_customer_source_profile={"event_ids": ["lunr_customer"]},
            peer_momentum_state={"state": "leader"},
        ),
        6,
    ) == 1.21
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            official_customer_source_profile={"event_ids": ["lunr_customer"]},
            peer_momentum_state={"state": "nonleader"},
        )
        == 1.1
    )
    assert round(
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            government_contract_profile={
                "event_ids": ["lunr_nasa_clps"],
                "event_fields": ["government_space_contract"],
                "source_types": ["official_or_primary_release"],
            },
            peer_momentum_state={"state": "leader"},
        ),
        6,
    ) == 1.05
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            government_contract_profile={
                "event_ids": ["lunr_nasa_clps"],
                "event_fields": ["government_space_contract"],
                "source_types": ["official_or_primary_release"],
            },
            peer_momentum_state={"state": "nonleader"},
        )
        == 1.0
    )
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            official_customer_source_profile={
                "event_ids": ["rklb_record_backlog_launch_deal_20260507"],
                "event_fields": ["customer_win"],
                "source_types": ["company_release"],
            },
        ),
        6,
    ) == 1.5125
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            event_guard_profile="launch_contract_and_dilution_sensitive",
        ),
        6,
    ) == 1.34375
    assert (
        space_catalyst_forward_risk_scalar(
            "RDW",
            "trend_long",
            event_guard_profile="contract_concentration_and_dilution_sensitive",
        )
        == 1.075
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "PL",
            "trend_long",
            event_guard_profile="data_contract_and_revenue_quality_sensitive",
        )
        == 1.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            multi_event_depth_profile={
                "event_count": 2,
                "event_ids": ["lunr_contract", "golden_dome"],
            },
        )
        == 1.075
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            multi_event_depth_profile={
                "event_count": 1,
                "event_ids": ["lunr_contract"],
            },
        )
        == 1.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            source_diversity_profile={
                "event_count": 2,
                "event_ids": ["lunr_contract", "golden_dome"],
                "event_fields": ["customer_win", "government_space_contract"],
                "semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "source_types": [
                    "official_government_release",
                    "official_or_primary_release",
                ],
            },
        )
        == 1.101875
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "breakout_long",
            source_diversity_profile={
                "event_count": 2,
                "event_ids": ["lunr_contract", "golden_dome"],
                "event_fields": ["customer_win", "government_space_contract"],
                "semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "source_types": [
                    "official_government_release",
                    "official_or_primary_release",
                ],
            },
        )
        == 1.075
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "LUNR",
                "trend_long",
                peer_momentum_state={"state": "leader"},
                source_diversity_profile={
                    "event_count": 2,
                    "event_ids": ["lunr_contract", "golden_dome"],
                    "event_fields": ["customer_win", "government_space_contract"],
                    "semantic_buckets": [
                        "defense_budget_theme",
                        "fundamental_contract_regulatory",
                    ],
                    "source_types": [
                        "official_government_release",
                        "official_or_primary_release",
                    ],
                },
            ),
            6,
        )
        == 1.267156
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "LUNR",
                "trend_long",
                iwm_relative_momentum_state={"state": "smallcap_leader"},
                source_diversity_profile={
                    "event_count": 2,
                    "event_ids": ["lunr_contract", "golden_dome"],
                    "event_fields": ["customer_win", "government_space_contract"],
                    "semantic_buckets": [
                        "defense_budget_theme",
                        "fundamental_contract_regulatory",
                    ],
                    "source_types": [
                        "official_government_release",
                        "official_or_primary_release",
                    ],
                },
            ),
            6,
        )
        == 1.272666
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "LUNR",
                "trend_long",
                iwm_relative_momentum_state={"state": "smallcap_leader"},
                peer_momentum_state={"state": "leader"},
                source_diversity_profile={
                    "event_count": 2,
                    "event_ids": ["lunr_contract", "golden_dome"],
                    "event_fields": ["customer_win", "government_space_contract"],
                    "semantic_buckets": [
                        "defense_budget_theme",
                        "fundamental_contract_regulatory",
                    ],
                    "source_types": [
                        "official_government_release",
                        "official_or_primary_release",
                    ],
                },
            ),
            6,
        )
        == 1.767255
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "LUNR",
                "trend_long",
                forward_replacement_profile={
                    "closed_event_count": 2,
                    "avg_10d_cash_relative_pnl": 100.0,
                    "avg_10d_same_theme_replacement_value": 50.0,
                },
            ),
            6,
        )
        == 1.05
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "LUNR",
                "trend_long",
                forward_replacement_profile={
                    "closed_event_count": 1,
                    "avg_10d_cash_relative_pnl": 100.0,
                    "avg_10d_same_theme_replacement_value": -50.0,
                    "avg_10d_spy_relative_value": 25.0,
                    "avg_10d_qqq_relative_value": 20.0,
                    "avg_10d_ufo_relative_value": 15.0,
                    "avg_10d_arkx_relative_value": 10.0,
                },
            ),
            6,
        )
        == 1.025
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "RKLB",
                "trend_long",
                forward_replacement_profile={
                    "closed_event_count": 1,
                    "avg_10d_cash_relative_pnl": 4200.0,
                    "avg_10d_same_theme_replacement_value": 500.0,
                },
            ),
            6,
        )
        == 1.447031
    )
    assert (
        round(
            space_catalyst_forward_risk_scalar(
                "RKLB",
                "trend_long",
                iwm_relative_momentum_state={"state": "smallcap_leader"},
                forward_replacement_profile={
                    "closed_event_count": 1,
                    "avg_10d_cash_relative_pnl": 4200.0,
                    "avg_10d_same_theme_replacement_value": 500.0,
                },
            ),
            6,
        )
        == 1.631528
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "LUNR",
            "trend_long",
            source_diversity_profile={
                "event_count": 2,
                "event_ids": ["lunr_contract", "lunr_followup"],
                "event_fields": ["customer_win"],
                "semantic_buckets": ["fundamental_contract_regulatory"],
                "source_types": [
                    "official_government_release",
                    "official_or_primary_release",
                ],
            },
        )
        == 1.0
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "RDW",
            "trend_long",
            single_event_defense_profile={
                "event_count": 1,
                "event_ids": ["golden_dome"],
                "event_fields": ["government_space_contract"],
                "semantic_buckets": ["defense_budget_theme"],
                "source_types": ["official_government_release"],
            },
        )
        == 1.05
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "RDW",
            "trend_long",
            single_event_defense_profile={
                "event_count": 1,
                "event_ids": ["golden_dome"],
                "event_fields": ["customer_win", "government_space_contract"],
                "semantic_buckets": ["defense_budget_theme"],
                "source_types": ["official_government_release"],
            },
        )
        == 1.0
    )
    assert round(
        space_catalyst_forward_risk_scalar(
            "RDW",
            "trend_long",
            event_guard_profile="contract_concentration_and_dilution_sensitive",
            single_event_defense_profile={
                "event_count": 1,
                "event_ids": ["golden_dome"],
                "event_fields": ["government_space_contract"],
                "semantic_buckets": ["defense_budget_theme"],
                "source_types": ["official_government_release"],
            },
        ),
        6,
    ) == 1.12875
    assert (
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            attention_overlay_profile={
                "attention_event_count": 1,
                "attention_event_ids": ["spacex_ipo_proxy"],
                "attention_event_fields": ["spacex_ipo_proxy"],
                "attention_semantic_buckets": ["attention_only"],
                "attention_source_types": ["market_attention_proxy"],
                "non_attention_event_count": 1,
                "non_attention_event_ids": ["rklb_customer"],
                "non_attention_event_fields": ["customer_win"],
                "non_attention_semantic_buckets": [
                    "fundamental_contract_regulatory"
                ],
                "non_attention_source_types": ["company_release"],
            },
        )
        == 1.5625
    )
    assert (
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            attention_overlay_profile={
                "attention_event_count": 1,
                "attention_event_ids": ["spacex_ipo_proxy"],
                "attention_event_fields": ["spacex_ipo_proxy"],
                "attention_semantic_buckets": ["attention_only"],
                "attention_source_types": ["market_attention_proxy"],
                "non_attention_event_count": 0,
                "non_attention_event_ids": [],
                "non_attention_event_fields": [],
                "non_attention_semantic_buckets": [],
                "non_attention_source_types": [],
            },
        )
        == 1.25
    )
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            basket_momentum_state={"state": "positive"},
            iwm_relative_momentum_state={"state": "smallcap_leader"},
            trade_quality_score=0.956,
        ),
        6,
    ) == 1.66375
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            basket_momentum_state={"state": "positive"},
            iwm_relative_momentum_state={"state": "smallcap_leader"},
            theme_segment="launch_lunar",
            trade_quality_score=0.956,
        ),
        6,
    ) == 1.830125
    assert round(
        space_catalyst_forward_risk_scalar(
            "RKLB",
            "trend_long",
            basket_momentum_state={"state": "positive"},
            iwm_relative_momentum_state={"state": "smallcap_leader"},
            theme_segment="launch_lunar",
            liquidity_tier="ok",
            trade_quality_score=0.956,
        ),
        6,
    ) == 2.013138


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


def test_space_catalyst_official_customer_source_profiles_filters_attention_only():
    profiles = space_catalyst_official_customer_source_profiles(
        [
            {
                "event_id": "rklb_customer",
                "event_date": "2026-05-01",
                "tickers": ["RKLB"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "company_release",
            },
            {
                "event_id": "uap_attention",
                "event_date": "2026-05-01",
                "tickers": ["RKLB"],
                "event_fields": ["uap_attention_spike"],
                "semantic_bucket": "attention_only",
                "source_type": "official_attention_release",
            },
        ],
        included_tickers=["RKLB", "ASTS"],
    )

    assert profiles == {
        "RKLB": {
            "event_ids": ["rklb_customer"],
            "event_fields": ["customer_win"],
            "semantic_buckets": ["fundamental_contract_regulatory"],
            "source_types": ["company_release"],
        }
    }


def test_space_catalyst_government_contract_profiles_use_official_sources():
    profiles = space_catalyst_government_contract_profiles(
        [
            {
                "event_id": "lunr_nasa_contract",
                "event_date": "2026-05-01",
                "tickers": ["LUNR"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_or_primary_release",
            },
            {
                "event_id": "golden_dome",
                "event_date": "2026-05-02",
                "tickers": ["LUNR", "RDW"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "defense_budget_theme",
                "source_type": "official_government_release",
            },
            {
                "event_id": "company_contract",
                "event_date": "2026-05-03",
                "tickers": ["LUNR"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "company_release",
            },
            {
                "event_id": "attention_only",
                "event_date": "2026-05-04",
                "tickers": ["RDW"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "attention_only",
                "source_type": "official_government_release",
            },
        ],
        included_tickers=["LUNR", "RDW"],
    )

    assert profiles == {
        "LUNR": {
            "event_count": 2,
            "event_ids": ["golden_dome", "lunr_nasa_contract"],
            "event_fields": ["government_space_contract"],
            "semantic_buckets": [
                "defense_budget_theme",
                "fundamental_contract_regulatory",
            ],
            "source_types": [
                "official_government_release",
                "official_or_primary_release",
            ],
        },
        "RDW": {
            "event_count": 1,
            "event_ids": ["golden_dome"],
            "event_fields": ["government_space_contract"],
            "semantic_buckets": ["defense_budget_theme"],
            "source_types": ["official_government_release"],
        },
    }


def test_space_catalyst_multi_event_depth_profiles_filters_attention_and_singletons():
    profiles = space_catalyst_multi_event_depth_profiles(
        [
            {
                "event_id": "lunr_contract",
                "event_date": "2026-05-01",
                "tickers": ["LUNR"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_or_primary_release",
            },
            {
                "event_id": "lunr_golden_dome",
                "event_date": "2026-05-02",
                "tickers": ["LUNR", "RDW"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "defense_budget_theme",
                "source_type": "official_government_release",
            },
            {
                "event_id": "lunr_attention",
                "event_date": "2026-05-03",
                "tickers": ["LUNR"],
                "event_fields": ["uap_attention_spike"],
                "semantic_bucket": "attention_only",
                "source_type": "official_attention_release",
            },
        ],
        included_tickers=["LUNR", "RDW"],
    )

    assert profiles == {
        "LUNR": {
            "event_count": 2,
            "event_ids": ["lunr_contract", "lunr_golden_dome"],
            "event_fields": ["customer_win", "government_space_contract"],
            "semantic_buckets": [
                "defense_budget_theme",
                "fundamental_contract_regulatory",
            ],
            "source_types": [
                "official_government_release",
                "official_or_primary_release",
            ],
        }
    }


def test_space_catalyst_source_diversity_profiles_require_source_and_bucket_diversity():
    profiles = space_catalyst_source_diversity_profiles(
        [
            {
                "event_id": "lunr_contract",
                "event_date": "2026-05-01",
                "tickers": ["LUNR"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_or_primary_release",
            },
            {
                "event_id": "lunr_golden_dome",
                "event_date": "2026-05-02",
                "tickers": ["LUNR", "RDW"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "defense_budget_theme",
                "source_type": "official_government_release",
            },
            {
                "event_id": "rdw_followup",
                "event_date": "2026-05-03",
                "tickers": ["RDW"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "defense_budget_theme",
                "source_type": "official_or_primary_release",
            },
            {
                "event_id": "rklb_attention",
                "event_date": "2026-05-04",
                "tickers": ["RKLB"],
                "event_fields": ["spacex_ipo_proxy"],
                "semantic_bucket": "attention_only",
                "source_type": "market_attention_proxy",
            },
        ],
        included_tickers=["LUNR", "RDW", "RKLB"],
    )

    assert profiles == {
        "LUNR": {
            "event_count": 2,
            "event_ids": ["lunr_contract", "lunr_golden_dome"],
            "event_fields": ["customer_win", "government_space_contract"],
            "semantic_buckets": [
                "defense_budget_theme",
                "fundamental_contract_regulatory",
            ],
            "source_types": [
                "official_government_release",
                "official_or_primary_release",
            ],
        }
    }


def test_space_catalyst_forward_replacement_positive_profiles_use_closed_ledger_rows():
    profiles = space_catalyst_forward_replacement_positive_profiles(
        [
            {
                "asof_date": "2026-05-12",
                "event_id": "lunr_contract",
                "ticker": "LUNR",
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_or_primary_release",
                "event_fields": ["customer_win"],
                "closed_decision": True,
                "horizons": {
                    "5d": {
                        "status": "mature",
                        "cash_relative_pnl": -25.0,
                        "same_theme_replacement_value": 20.0,
                    },
                    "10d": {
                        "status": "mature",
                        "cash_relative_pnl": 200.0,
                        "same_theme_replacement_value": 100.0,
                    }
                },
            },
            {
                "asof_date": "2026-05-12",
                "event_id": "lunr_defense",
                "ticker": "LUNR",
                "semantic_bucket": "defense_budget_theme",
                "source_type": "official_government_release",
                "event_fields": ["government_space_contract"],
                "closed_decision": True,
                "horizons": {
                    "5d": {
                        "status": "mature",
                        "cash_relative_pnl": 50.0,
                        "same_theme_replacement_value": 40.0,
                    },
                    "10d": {
                        "status": "mature",
                        "cash_relative_pnl": -50.0,
                        "same_theme_replacement_value": 60.0,
                    }
                },
            },
            {
                "asof_date": "2026-05-12",
                "event_id": "asts_authorization",
                "ticker": "ASTS",
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_government_release",
                "event_fields": ["customer_win"],
                "closed_decision": True,
                "horizons": {
                    "10d": {
                        "status": "mature",
                        "cash_relative_pnl": 300.0,
                        "same_theme_replacement_value": -10.0,
                    }
                },
            },
            {
                "asof_date": "2026-05-12",
                "event_id": "rklb_attention",
                "ticker": "RKLB",
                "semantic_bucket": "attention_only",
                "source_type": "market_attention_proxy",
                "event_fields": ["spacex_ipo_proxy"],
                "closed_decision": True,
                "horizons": {
                    "10d": {
                        "status": "mature",
                        "cash_relative_pnl": 500.0,
                        "same_theme_replacement_value": 100.0,
                    }
                },
            },
        ],
        included_tickers=["LUNR", "ASTS", "RKLB"],
    )

    assert sorted(profiles) == ["LUNR"]
    assert profiles["LUNR"]["closed_event_count"] == 2
    assert profiles["LUNR"]["avg_5d_cash_relative_pnl"] == 12.5
    assert profiles["LUNR"]["avg_5d_same_theme_replacement_value"] == 30.0
    assert profiles["LUNR"]["avg_10d_cash_relative_pnl"] == 75.0
    assert profiles["LUNR"]["avg_10d_same_theme_replacement_value"] == 80.0
    assert profiles["LUNR"]["weak_5d_cash_count"] == 1
    assert profiles["LUNR"]["positive_cash_count"] == 1
    assert profiles["LUNR"]["positive_same_theme_count"] == 2

    benchmark_profiles = space_catalyst_forward_replacement_positive_profiles(
        [
            {
                "asof_date": "2026-05-12",
                "event_id": "asts_authorization",
                "ticker": "ASTS",
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_government_release",
                "event_fields": ["customer_win"],
                "closed_decision": True,
                "horizons": {
                    "10d": {
                        "status": "mature",
                        "cash_relative_pnl": 300.0,
                        "same_theme_replacement_value": -10.0,
                        "spy_relative_value": 120.0,
                        "qqq_relative_value": 90.0,
                        "ufo_relative_value": 80.0,
                        "arkx_relative_value": 70.0,
                    }
                },
            },
        ],
        included_tickers=["ASTS"],
    )

    assert sorted(benchmark_profiles) == ["ASTS"]
    assert benchmark_profiles["ASTS"]["avg_10d_same_theme_replacement_value"] == -10.0
    assert benchmark_profiles["ASTS"]["avg_10d_spy_relative_value"] == 120.0
    assert benchmark_profiles["ASTS"]["positive_same_theme_count"] == 0
    assert benchmark_profiles["ASTS"]["positive_arkx_count"] == 1


def test_space_catalyst_single_event_defense_profiles_isolates_defense_only():
    profiles = space_catalyst_single_event_defense_profiles(
        [
            {
                "event_id": "lunr_customer",
                "event_date": "2026-05-01",
                "tickers": ["LUNR"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_or_primary_release",
            },
            {
                "event_id": "golden_dome",
                "event_date": "2026-05-02",
                "tickers": ["LUNR", "RDW", "PL"],
                "event_fields": ["government_space_contract"],
                "semantic_bucket": "defense_budget_theme",
                "source_type": "official_government_release",
            },
            {
                "event_id": "rdw_customer",
                "event_date": "2026-05-03",
                "tickers": ["RDW"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "company_release",
            },
            {
                "event_id": "pl_attention",
                "event_date": "2026-05-04",
                "tickers": ["PL"],
                "event_fields": ["uap_attention_spike"],
                "semantic_bucket": "attention_only",
                "source_type": "official_attention_release",
            },
        ],
        included_tickers=["LUNR", "RDW", "PL"],
    )

    assert profiles == {
        "PL": {
            "event_count": 1,
            "event_ids": ["golden_dome"],
            "event_fields": ["government_space_contract"],
            "semantic_buckets": ["defense_budget_theme"],
            "source_types": ["official_government_release"],
        }
    }


def test_space_catalyst_attention_overlay_profiles_require_official_support():
    profiles = space_catalyst_attention_overlay_profiles(
        [
            {
                "event_id": "rklb_customer",
                "event_date": "2026-05-01",
                "tickers": ["RKLB"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "company_release",
            },
            {
                "event_id": "spacex_proxy",
                "event_date": "2026-05-02",
                "tickers": ["RKLB", "UFO"],
                "event_fields": ["spacex_ipo_proxy"],
                "semantic_bucket": "attention_only",
                "source_type": "market_attention_proxy",
            },
            {
                "event_id": "asts_contract",
                "event_date": "2026-05-03",
                "tickers": ["ASTS"],
                "event_fields": ["customer_win"],
                "semantic_bucket": "fundamental_contract_regulatory",
                "source_type": "official_regulatory_release",
            },
            {
                "event_id": "pl_attention",
                "event_date": "2026-05-04",
                "tickers": ["PL"],
                "event_fields": ["uap_attention_spike"],
                "semantic_bucket": "attention_only",
                "source_type": "official_attention_release",
            },
        ],
        included_tickers=["RKLB", "ASTS", "PL"],
    )

    assert profiles == {
        "RKLB": {
            "event_count": 2,
            "attention_event_count": 1,
            "attention_event_ids": ["spacex_proxy"],
            "attention_event_fields": ["spacex_ipo_proxy"],
            "attention_semantic_buckets": ["attention_only"],
            "attention_source_types": ["market_attention_proxy"],
            "non_attention_event_count": 1,
            "non_attention_event_ids": ["rklb_customer"],
            "non_attention_event_fields": ["customer_win"],
            "non_attention_semantic_buckets": [
                "fundamental_contract_regulatory"
            ],
            "non_attention_source_types": ["company_release"],
        }
    }


def test_space_catalyst_peer_momentum_state_compares_to_official_average():
    basket = space_catalyst_basket_momentum_state(
        {
            "ASTS": {"momentum_20d_pct": 0.15},
            "BKSY": {"momentum_20d_pct": 0.05},
            "LUNR": {"momentum_20d_pct": 0.1},
            "PL": {"momentum_20d_pct": 0.1},
            "RDW": {"momentum_20d_pct": 0.1},
            "RKLB": {"momentum_20d_pct": 0.1},
        }
    )

    leader = space_catalyst_peer_momentum_state("ASTS", basket)
    nonleader = space_catalyst_peer_momentum_state("BKSY", basket)

    assert leader["state"] == "leader"
    assert leader["excess_momentum_20d_pct"] == 0.05
    assert nonleader["state"] == "nonleader"
    assert nonleader["excess_momentum_20d_pct"] == -0.05


def test_space_catalyst_iwm_relative_momentum_state_compares_iwm_to_spy():
    state = space_catalyst_iwm_relative_momentum_state(
        {
            "IWM": {"momentum_20d_pct": 0.08},
            "SPY": {"momentum_20d_pct": 0.03},
        }
    )
    missing = space_catalyst_iwm_relative_momentum_state(
        {"IWM": {"momentum_20d_pct": 0.08}}
    )

    assert state["state"] == "smallcap_leader"
    assert state["iwm_excess_vs_spy_20d_pct"] == 0.05
    assert missing["state"] == "missing"


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
    assert space_catalyst_observation_feature_tickers({}) == [
        "ASTS",
        "BKSY",
        "IWM",
        "LUNR",
        "PL",
        "RDW",
        "RKLB",
        "SPY",
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
                "trade_quality_score": 0.956,
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
            "IWM": {"momentum_20d_pct": 0.08},
            "SPY": {"momentum_20d_pct": 0.03},
            "IRDM": {"atr": 1.0},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {"launch_lunar": ["RKLB"]},
            "tickers_by_liquidity_tier": {"ok": ["RKLB"]},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={
            "RKLB": {
                "event_ids": ["rklb_record_backlog_launch_deal_20260507"],
                "event_fields": ["customer_win"],
                "semantic_buckets": ["fundamental_contract_regulatory"],
                "source_types": ["company_release"],
            }
        },
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={
            "RKLB": {
                "event_count": 2,
                "event_ids": [
                    "golden_dome_sbi_awards_20260424",
                    "rklb_record_backlog_launch_deal_20260507",
                ],
                "event_fields": [
                    "customer_win",
                    "government_space_contract",
                ],
                "semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "source_types": [
                    "company_release",
                    "official_government_release",
                ],
            }
        },
        space_attention_overlay_profiles={
            "RKLB": {
                "event_count": 3,
                "attention_event_count": 1,
                "attention_event_ids": ["spacex_ipo_proxy"],
                "attention_event_fields": ["spacex_ipo_proxy"],
                "attention_semantic_buckets": ["attention_only"],
                "attention_source_types": ["market_attention_proxy"],
                "non_attention_event_count": 2,
                "non_attention_event_ids": [
                    "golden_dome_sbi_awards_20260424",
                    "rklb_record_backlog_launch_deal_20260507",
                ],
                "non_attention_event_fields": [
                    "customer_win",
                    "government_space_contract",
                ],
                "non_attention_semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "non_attention_source_types": [
                    "company_release",
                    "official_government_release",
                ],
            }
        },
        space_source_diversity_profiles={
            "RKLB": {
                "event_count": 2,
                "event_ids": [
                    "golden_dome_sbi_awards_20260424",
                    "rklb_record_backlog_launch_deal_20260507",
                ],
                "event_fields": [
                    "customer_win",
                    "government_space_contract",
                ],
                "semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "source_types": [
                    "company_release",
                    "official_government_release",
                ],
            }
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
    assert plan["space_near_perfect_tqs_trend_bucket"] is True
    assert plan["space_near_perfect_tqs_trend_risk_scalar"] == 1.1
    assert plan["space_peer_momentum_state"] == "nonleader"
    assert plan["space_peer_nonleader_breakout_bucket"] is False
    assert plan["space_peer_nonleader_breakout_risk_scalar"] == 1.0
    assert plan["space_iwm_relative_state"] == "smallcap_leader"
    assert plan["space_iwm_excess_vs_spy_20d_pct"] == 0.05
    assert plan["space_iwm_relative_momentum_risk_scalar"] == 1.1
    assert plan["space_iwm_peer_leader_trend_bucket"] is False
    assert plan["space_iwm_peer_leader_trend_risk_scalar"] == 1.0
    assert plan["space_launch_lunar_theme_segment_bucket"] is True
    assert plan["space_launch_lunar_theme_segment_risk_scalar"] == 1.1
    assert plan["liquidity_tier"] == "ok"
    assert plan["space_liquidity_tier_bucket"] is True
    assert plan["space_liquidity_tier_risk_scalar"] == 1.1
    assert plan["space_watch_liquidity_tier_bucket"] is False
    assert plan["space_watch_liquidity_tier_risk_scalar"] == 1.0
    assert plan["space_official_customer_source_bucket"] is True
    assert plan["space_official_customer_source_risk_scalar"] == 1.1
    assert plan["space_customer_source_peer_leader_bucket"] is False
    assert plan["space_customer_source_peer_leader_risk_scalar"] == 1.0
    assert plan["space_company_release_customer_source_bucket"] is True
    assert plan["space_company_release_customer_source_risk_scalar"] == 1.1
    assert plan["space_multi_event_depth_bucket"] is True
    assert plan["space_multi_event_depth_risk_scalar"] == 1.075
    assert plan["space_attention_overlay_bucket"] is True
    assert plan["space_attention_overlay_risk_scalar"] == 1.25
    assert plan["space_source_diversity_bucket"] is True
    assert plan["space_source_diversity_risk_scalar"] == 1.075
    assert plan["space_source_diversity_peer_leader_bucket"] is False
    assert plan["space_source_diversity_peer_leader_risk_scalar"] == 1.0
    assert plan["space_source_diversity_iwm_leader_bucket"] is True
    assert plan["space_source_diversity_iwm_leader_risk_scalar"] == 1.05
    assert plan["space_source_diversity_peer_iwm_leader_bucket"] is False
    assert plan["space_source_diversity_peer_iwm_leader_risk_scalar"] == 1.0
    assert plan["space_source_diversity_trend_bucket"] is True
    assert plan["space_source_diversity_trend_risk_scalar"] == 1.025
    assert plan["space_source_diversity_peer_nonleader_trend_bucket"] is True
    assert plan["space_source_diversity_peer_nonleader_trend_risk_scalar"] == 1.025
    assert plan["space_event_source_profile"]["event_fields"] == ["customer_win"]
    assert plan["space_multi_event_depth_profile"]["event_count"] == 2
    assert plan["space_attention_overlay_profile"]["attention_event_ids"] == [
        "spacex_ipo_proxy"
    ]
    assert plan["space_source_diversity_profile"]["event_count"] == 2
    assert plan["effective_risk_scalar"] == 2.91128
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 2911.28
    assert plan["blocked_reason"] == "live_slots_zero_forward_gate_pending"
    assert plan["same_day_core_alternative_count"] == 1
    assert snapshot["production_impact"]["alters_orders"] is False


def test_space_catalyst_observation_slot_marks_iwm_peer_leader_trend():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.0},
            "BKSY": {"momentum_20d_pct": 0.0},
            "LUNR": {"atr": 1.0, "momentum_20d_pct": 0.6},
            "PL": {"momentum_20d_pct": 0.0},
            "RDW": {"momentum_20d_pct": 0.0},
            "RKLB": {"momentum_20d_pct": 0.0},
            "IWM": {"momentum_20d_pct": 0.2},
            "SPY": {"momentum_20d_pct": 0.05},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_source_diversity_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "LUNR"
    assert plan["space_iwm_relative_state"] == "smallcap_leader"
    assert plan["space_peer_momentum_state"] == "leader"
    assert plan["space_iwm_peer_leader_trend_bucket"] is True
    assert plan["space_iwm_peer_leader_trend_risk_scalar"] == 1.15
    assert plan["effective_risk_scalar"] == 1.043625
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 1043.62


def test_space_catalyst_observation_slot_marks_source_diversity_peer_leader():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.0},
            "BKSY": {"momentum_20d_pct": 0.0},
            "LUNR": {"atr": 1.0, "momentum_20d_pct": 0.6},
            "PL": {"momentum_20d_pct": 0.0},
            "RDW": {"momentum_20d_pct": 0.0},
            "RKLB": {"momentum_20d_pct": 0.0},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_source_diversity_profiles={
            "LUNR": {
                "event_count": 2,
                "event_ids": ["lunr_nasa_clps", "golden_dome"],
                "event_fields": ["customer_win", "government_space_contract"],
                "semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "source_types": [
                    "official_government_release",
                    "official_or_primary_release",
                ],
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "LUNR"
    assert plan["space_peer_momentum_state"] == "leader"
    assert plan["space_source_diversity_bucket"] is True
    assert plan["space_source_diversity_risk_scalar"] == 1.075
    assert plan["space_source_diversity_peer_leader_bucket"] is True
    assert plan["space_source_diversity_peer_leader_risk_scalar"] == 1.15
    assert plan["space_source_diversity_iwm_leader_bucket"] is False
    assert plan["space_source_diversity_iwm_leader_risk_scalar"] == 1.0
    assert plan["space_source_diversity_peer_iwm_leader_bucket"] is False
    assert plan["space_source_diversity_peer_iwm_leader_risk_scalar"] == 1.0
    assert plan["space_source_diversity_trend_bucket"] is True
    assert plan["space_source_diversity_trend_risk_scalar"] == 1.025
    assert plan["space_source_diversity_peer_nonleader_trend_bucket"] is False
    assert plan["space_source_diversity_peer_nonleader_trend_risk_scalar"] == 1.0
    assert plan["effective_risk_scalar"] == 1.045404
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 1045.4


def test_space_catalyst_observation_slot_marks_source_diversity_peer_iwm_leader():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.0},
            "BKSY": {"momentum_20d_pct": 0.0},
            "LUNR": {"atr": 1.0, "momentum_20d_pct": 0.6},
            "PL": {"momentum_20d_pct": 0.0},
            "RDW": {"momentum_20d_pct": 0.0},
            "RKLB": {"momentum_20d_pct": 0.0},
            "IWM": {"momentum_20d_pct": 0.08},
            "SPY": {"momentum_20d_pct": 0.03},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_source_diversity_profiles={
            "LUNR": {
                "event_count": 2,
                "event_ids": ["lunr_nasa_clps", "golden_dome"],
                "event_fields": ["customer_win", "government_space_contract"],
                "semantic_buckets": [
                    "defense_budget_theme",
                    "fundamental_contract_regulatory",
                ],
                "source_types": [
                    "official_government_release",
                    "official_or_primary_release",
                ],
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "LUNR"
    assert plan["space_peer_momentum_state"] == "leader"
    assert plan["space_iwm_relative_state"] == "smallcap_leader"
    assert plan["space_source_diversity_bucket"] is True
    assert plan["space_source_diversity_peer_leader_bucket"] is True
    assert plan["space_source_diversity_iwm_leader_bucket"] is True
    assert plan["space_source_diversity_peer_iwm_leader_bucket"] is True
    assert plan["space_source_diversity_peer_iwm_leader_risk_scalar"] == 1.05
    assert plan["space_source_diversity_trend_bucket"] is True
    assert plan["space_source_diversity_trend_risk_scalar"] == 1.025
    assert plan["space_source_diversity_peer_nonleader_trend_bucket"] is False
    assert plan["space_source_diversity_peer_nonleader_trend_risk_scalar"] == 1.0
    assert plan["effective_risk_scalar"] == 1.457986
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 1457.99


def test_space_catalyst_observation_slot_marks_forward_replacement_positive():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"LUNR": {"atr": 1.0}},
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "LUNR": {
                "closed_event_count": 1,
                "avg_10d_cash_relative_pnl": 200.0,
                "avg_10d_same_theme_replacement_value": 100.0,
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_forward_replacement_positive_bucket"] is True
    assert plan["space_forward_replacement_positive_risk_scalar"] == 1.05
    assert plan["effective_risk_scalar"] == 0.7875
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 787.5


def test_space_catalyst_observation_slot_marks_benchmark_breadth_trend():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"LUNR": {"atr": 1.0}},
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "LUNR": {
                "closed_event_count": 1,
                "avg_10d_cash_relative_pnl": 200.0,
                "avg_10d_same_theme_replacement_value": -50.0,
                "avg_10d_spy_relative_value": 40.0,
                "avg_10d_qqq_relative_value": 30.0,
                "avg_10d_ufo_relative_value": 20.0,
                "avg_10d_arkx_relative_value": 10.0,
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_forward_replacement_positive_bucket"] is False
    assert plan["space_benchmark_breadth_trend_bucket"] is True
    assert plan["space_benchmark_breadth_trend_risk_scalar"] == 1.025
    assert plan["space_benchmark_breadth_profile"]["avg_10d_spy_relative_value"] == 40.0
    assert plan["effective_risk_scalar"] == 0.76875
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 768.75


def test_space_catalyst_observation_slot_marks_defense_budget_delayed_benchmark_trend():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"LUNR": {"atr": 1.0}},
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "LUNR": {
                "closed_event_count": 1,
                "avg_5d_cash_relative_pnl": -25.0,
                "avg_10d_cash_relative_pnl": 200.0,
                "avg_10d_same_theme_replacement_value": -50.0,
                "avg_10d_spy_relative_value": 40.0,
                "avg_10d_qqq_relative_value": 30.0,
                "avg_10d_ufo_relative_value": 20.0,
                "avg_10d_arkx_relative_value": 10.0,
                "rows": [
                    {
                        "semantic_bucket": "defense_budget_theme",
                        "event_fields": ["government_space_contract"],
                        "5d_cash_relative_pnl": -25.0,
                        "cash_relative_pnl": 200.0,
                        "spy_relative_value": 40.0,
                        "qqq_relative_value": 30.0,
                        "ufo_relative_value": 20.0,
                        "arkx_relative_value": 10.0,
                    }
                ],
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_benchmark_breadth_trend_bucket"] is True
    assert plan["space_defense_budget_delayed_benchmark_trend_bucket"] is True
    assert plan["space_defense_budget_delayed_benchmark_trend_risk_scalar"] == 1.025
    assert (
        plan["space_defense_budget_delayed_benchmark_profile"][
            "avg_5d_cash_relative_pnl"
        ]
        == -25.0
    )
    assert plan["effective_risk_scalar"] == 0.787969
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 787.97


def test_space_catalyst_observation_slot_marks_forward_replacement_trend_strength():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RDW",
                "strategy": "trend_long",
                "entry_price": 10.0,
                "stop_price": 9.0,
                "target_price": 13.5,
                "target_mult_used": 3.5,
                "confidence_score": 0.88,
                "trade_quality_score": 0.8,
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"RDW": {"atr": 1.0}},
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "RDW": {
                "closed_event_count": 1,
                "avg_10d_cash_relative_pnl": 1200.0,
                "avg_10d_same_theme_replacement_value": 600.0,
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_forward_replacement_positive_bucket"] is True
    assert plan["space_forward_replacement_same_theme_strength_bucket"] is True
    assert plan["space_forward_replacement_trend_strength_bucket"] is True
    assert plan["space_forward_replacement_trend_strength_risk_scalar"] == 1.05
    assert plan["effective_risk_scalar"] == 0.868219
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 868.22


def test_space_catalyst_observation_slot_marks_forward_replacement_iwm_leader_trend():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RDW",
                "strategy": "trend_long",
                "entry_price": 10.0,
                "stop_price": 9.0,
                "target_price": 13.5,
                "target_mult_used": 3.5,
                "confidence_score": 0.88,
                "trade_quality_score": 0.8,
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "IWM": {"momentum_20d_pct": 0.08},
            "SPY": {"momentum_20d_pct": 0.02},
            "RDW": {"atr": 1.0},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "RDW": {
                "closed_event_count": 1,
                "avg_10d_cash_relative_pnl": 1200.0,
                "avg_10d_same_theme_replacement_value": 600.0,
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_iwm_relative_state"] == "smallcap_leader"
    assert plan["space_forward_replacement_positive_bucket"] is True
    assert plan["space_forward_replacement_same_theme_strength_bucket"] is True
    assert plan["space_forward_replacement_trend_strength_bucket"] is True
    assert plan["space_forward_replacement_iwm_leader_trend_bucket"] is True
    assert plan["space_forward_replacement_iwm_leader_trend_risk_scalar"] == 1.025
    assert plan["effective_risk_scalar"] == 0.978917
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 978.92


def test_space_catalyst_observation_slot_marks_forward_replacement_company_source_trend():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RKLB",
                "strategy": "trend_long",
                "entry_price": 10.0,
                "stop_price": 9.0,
                "target_price": 13.5,
                "target_mult_used": 3.5,
                "confidence_score": 0.88,
                "trade_quality_score": 0.8,
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"RKLB": {"atr": 1.0}},
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={
            "RKLB": {
                "event_ids": ["rklb_record_backlog_launch_deal"],
                "event_fields": ["customer_win"],
                "semantic_buckets": ["fundamental_contract_regulatory"],
                "source_types": ["company_release"],
            }
        },
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "RKLB": {
                "closed_event_count": 1,
                "avg_5d_cash_relative_pnl": -250.0,
                "avg_10d_cash_relative_pnl": 1200.0,
                "avg_10d_same_theme_replacement_value": 600.0,
            }
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_company_release_customer_source_bucket"] is True
    assert plan["space_forward_replacement_positive_bucket"] is True
    assert plan["space_forward_replacement_same_theme_strength_bucket"] is True
    assert plan["space_forward_replacement_trend_strength_bucket"] is True
    assert plan["space_forward_replacement_company_source_trend_bucket"] is True
    assert plan["space_forward_replacement_company_source_trend_risk_scalar"] == 1.025
    assert plan["space_delayed_absorption_trend_bucket"] is True
    assert plan["space_delayed_absorption_trend_risk_scalar"] == 1.025
    assert plan["effective_risk_scalar"] == 1.379661
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 1379.66


def test_space_catalyst_forward_replacement_trend_strength_is_trend_only():
    profile = {
        "closed_event_count": 1,
        "avg_5d_cash_relative_pnl": -150.0,
        "avg_10d_cash_relative_pnl": 1200.0,
        "avg_10d_same_theme_replacement_value": 600.0,
    }

    trend_scalar = space_catalyst_forward_risk_scalar(
        "RDW",
        "trend_long",
        forward_replacement_profile=profile,
    )
    breakout_scalar = space_catalyst_forward_risk_scalar(
        "RDW",
        "breakout_long",
        forward_replacement_profile=profile,
    )

    assert round(trend_scalar, 6) == 1.186566
    assert round(breakout_scalar, 6) == 1.1025

    company_source_profile = {
        "event_ids": ["rklb_record_backlog_launch_deal"],
        "event_fields": ["customer_win"],
        "semantic_buckets": ["fundamental_contract_regulatory"],
        "source_types": ["company_release"],
    }
    company_source_trend_scalar = space_catalyst_forward_risk_scalar(
        "RKLB",
        "trend_long",
        official_customer_source_profile=company_source_profile,
        forward_replacement_profile=profile,
    )
    company_source_breakout_scalar = space_catalyst_forward_risk_scalar(
        "RKLB",
        "breakout_long",
        official_customer_source_profile=company_source_profile,
        forward_replacement_profile=profile,
    )

    assert round(company_source_trend_scalar, 6) == 1.839548
    assert round(company_source_breakout_scalar, 6) == 1.334025


def test_space_catalyst_defense_budget_delayed_benchmark_is_trend_only():
    profile = {
        "closed_event_count": 1,
        "avg_5d_cash_relative_pnl": -25.0,
        "avg_10d_cash_relative_pnl": 200.0,
        "avg_10d_same_theme_replacement_value": -50.0,
        "avg_10d_spy_relative_value": 40.0,
        "avg_10d_qqq_relative_value": 30.0,
        "avg_10d_ufo_relative_value": 20.0,
        "avg_10d_arkx_relative_value": 10.0,
        "rows": [
            {
                "semantic_bucket": "defense_budget_theme",
                "event_fields": ["government_space_contract"],
                "5d_cash_relative_pnl": -25.0,
                "cash_relative_pnl": 200.0,
                "spy_relative_value": 40.0,
                "qqq_relative_value": 30.0,
                "ufo_relative_value": 20.0,
                "arkx_relative_value": 10.0,
            }
        ],
    }

    trend_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        forward_replacement_profile=profile,
    )
    breakout_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "breakout_long",
        forward_replacement_profile=profile,
    )

    assert round(trend_scalar, 6) == 1.050625
    assert round(breakout_scalar, 6) == 1.0


def test_space_catalyst_observation_slot_marks_government_contract_peer_leader():
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
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.0},
            "BKSY": {"momentum_20d_pct": 0.0},
            "LUNR": {"atr": 1.0, "momentum_20d_pct": 0.6},
            "PL": {"momentum_20d_pct": 0.0},
            "RDW": {"momentum_20d_pct": 0.0},
            "RKLB": {"momentum_20d_pct": 0.0},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={
            "LUNR": {
                "event_count": 1,
                "event_ids": ["lunr_nasa_contract"],
                "event_fields": ["government_space_contract"],
                "semantic_buckets": ["fundamental_contract_regulatory"],
                "source_types": ["official_or_primary_release"],
            }
        },
        space_multi_event_depth_profiles={},
        space_source_diversity_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "LUNR"
    assert plan["space_peer_momentum_state"] == "leader"
    assert plan["space_government_contract_profile_bucket"] is True
    assert plan["space_government_contract_peer_leader_bucket"] is True
    assert plan["space_government_contract_peer_leader_risk_scalar"] == 1.05
    assert plan["space_iwm_peer_leader_trend_bucket"] is False
    assert plan["space_iwm_peer_leader_trend_risk_scalar"] == 1.0
    assert plan["space_government_contract_profile"]["event_ids"] == [
        "lunr_nasa_contract"
    ]
    assert plan["effective_risk_scalar"] == 0.86625
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 866.25


def test_space_catalyst_observation_slot_marks_financing_dilution_profile():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RDW",
                "strategy": "trend_long",
                "entry_price": 20.0,
                "stop_price": 18.0,
                "target_price": 27.0,
                "target_mult_used": 3.5,
                "confidence_score": 0.88,
                "trade_quality_score": 0.9,
                "sizing": {
                    "shares_to_buy": 50,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.1},
            "BKSY": {"momentum_20d_pct": 0.1},
            "LUNR": {"momentum_20d_pct": 0.1},
            "PL": {"momentum_20d_pct": 0.1},
            "RDW": {"atr": 1.0, "momentum_20d_pct": 0.1},
            "RKLB": {"momentum_20d_pct": 0.1},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {"space_data_defense": ["RDW"]},
            "tickers_by_event_guard_profile": {
                "contract_concentration_and_dilution_sensitive": ["RDW"]
            },
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_source_diversity_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "RDW"
    assert plan["event_guard_profile"] == (
        "contract_concentration_and_dilution_sensitive"
    )
    assert plan["space_financing_dilution_profile_bucket"] is True
    assert plan["space_financing_dilution_profile_risk_scalar"] == 1.075
    assert plan["space_iwm_peer_leader_trend_bucket"] is False
    assert plan["space_iwm_peer_leader_trend_risk_scalar"] == 1.0
    assert plan["effective_risk_scalar"] == 0.886875
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 886.88


def test_space_catalyst_observation_slot_marks_single_event_defense_profile():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RDW",
                "strategy": "trend_long",
                "entry_price": 20.0,
                "stop_price": 18.0,
                "target_price": 27.0,
                "target_mult_used": 3.5,
                "confidence_score": 0.88,
                "trade_quality_score": 0.9,
                "sizing": {
                    "shares_to_buy": 50,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.1},
            "BKSY": {"momentum_20d_pct": 0.1},
            "LUNR": {"momentum_20d_pct": 0.1},
            "PL": {"momentum_20d_pct": 0.1},
            "RDW": {"atr": 1.0, "momentum_20d_pct": 0.1},
            "RKLB": {"momentum_20d_pct": 0.1},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {"space_data_defense": ["RDW"]},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={
            "RDW": {
                "event_count": 1,
                "event_ids": ["golden_dome"],
                "event_fields": ["government_space_contract"],
                "semantic_buckets": ["defense_budget_theme"],
                "source_types": ["official_government_release"],
            }
        },
        space_source_diversity_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "RDW"
    assert plan["space_single_event_defense_bucket"] is True
    assert plan["space_single_event_defense_risk_scalar"] == 1.05
    assert plan["space_single_event_defense_profile"]["event_ids"] == [
        "golden_dome"
    ]
    assert plan["effective_risk_scalar"] == 0.86625
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 866.25


def test_space_catalyst_observation_slot_marks_watch_liquidity_tier():
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
                "confidence_score": 0.86,
                "trade_quality_score": 0.8,
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.1},
            "BKSY": {"momentum_20d_pct": 0.1},
            "LUNR": {"atr": 1.0, "momentum_20d_pct": 0.1},
            "PL": {"momentum_20d_pct": 0.1},
            "RDW": {"momentum_20d_pct": 0.1},
            "RKLB": {"momentum_20d_pct": 0.1},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {"launch_lunar": ["LUNR"]},
            "tickers_by_liquidity_tier": {"watch": ["LUNR"]},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "LUNR"
    assert plan["liquidity_tier"] == "watch"
    assert plan["space_liquidity_tier_bucket"] is False
    assert plan["space_liquidity_tier_risk_scalar"] == 1.0
    assert plan["space_watch_liquidity_tier_bucket"] is True
    assert plan["space_watch_liquidity_tier_risk_scalar"] == 1.1
    assert plan["space_iwm_peer_leader_trend_bucket"] is False
    assert plan["space_iwm_peer_leader_trend_risk_scalar"] == 1.0
    assert plan["effective_risk_scalar"] == 0.99825
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 998.25


def test_space_catalyst_observation_slot_zeroes_peer_nonleader_breakout():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-11",
        candidate_signals=[
            {
                "ticker": "RKLB",
                "strategy": "breakout_long",
                "entry_price": 100.0,
                "stop_price": 92.5,
                "target_price": 117.5,
                "target_mult_used": 3.5,
                "risk_reward_ratio": 2.33,
                "confidence_score": 0.9,
                "trade_quality_score": 0.9,
                "sizing": {
                    "shares_to_buy": 10,
                    "position_value_usd": 1000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={
            "ASTS": {"momentum_20d_pct": 0.12},
            "BKSY": {"momentum_20d_pct": 0.12},
            "LUNR": {"momentum_20d_pct": 0.12},
            "PL": {"momentum_20d_pct": 0.12},
            "RDW": {"momentum_20d_pct": 0.12},
            "RKLB": {"atr": 5.0, "momentum_20d_pct": 0.0},
        },
        space_catalyst_shadow={
            "tickers_by_segment": {"launch_lunar": ["RKLB"]},
            "tickers_by_liquidity_tier": {"ok": ["RKLB"]},
            "forward_hypothesis": SPACE_CATALYST_FORWARD_HYPOTHESIS,
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["ticker"] == "RKLB"
    assert plan["space_peer_momentum_state"] == "nonleader"
    assert plan["space_peer_nonleader_breakout_bucket"] is True
    assert plan["space_peer_nonleader_breakout_risk_scalar"] == 0.0
    assert plan["space_launch_lunar_theme_segment_bucket"] is True
    assert plan["space_launch_lunar_theme_segment_risk_scalar"] == 1.1
    assert plan["space_liquidity_tier_bucket"] is True
    assert plan["space_liquidity_tier_risk_scalar"] == 1.1
    assert plan["space_watch_liquidity_tier_bucket"] is False
    assert plan["space_watch_liquidity_tier_risk_scalar"] == 1.0
    assert plan["effective_risk_scalar"] == 0.0
    assert plan["paper_sizing"]["scaled_position_value_usd"] == 0.0


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
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_source_diversity_profiles={},
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
                "space_near_perfect_tqs_trend_risk_scalar": 1.1,
                "space_peer_nonleader_breakout_risk_scalar": 0.0,
                "space_iwm_relative_leader_risk_scalar": 1.1,
                "space_iwm_peer_leader_trend_risk_scalar": 1.15,
                "space_launch_lunar_theme_risk_scalar": 1.1,
                "space_liquidity_tier": "ok",
                "space_liquidity_tier_risk_scalar": 1.1,
                "space_watch_liquidity_tier": "watch",
                "space_watch_liquidity_tier_risk_scalar": 1.1,
                "space_official_customer_source_event_field": "customer_win",
                "space_official_customer_source_risk_scalar": 1.1,
                "space_customer_source_peer_leader_risk_scalar": 1.1,
                "space_government_contract_peer_leader_risk_scalar": 1.05,
                "space_company_release_customer_source_risk_scalar": 1.1,
                "space_financing_dilution_profile_risk_scalar": 1.075,
                "space_multi_event_depth_min_count": 2,
                "space_multi_event_depth_risk_scalar": 1.075,
                "space_single_event_defense_risk_scalar": 1.05,
                "space_attention_overlay_risk_scalar": 1.25,
                "space_source_diversity_risk_scalar": 1.075,
                "space_source_diversity_peer_leader_risk_scalar": 1.15,
                "space_source_diversity_iwm_leader_risk_scalar": 1.05,
                "space_source_diversity_peer_iwm_leader_risk_scalar": 1.05,
                "space_source_diversity_trend_risk_scalar": 1.025,
                "space_source_diversity_peer_nonleader_trend_risk_scalar": 1.025,
                "space_forward_replacement_positive_horizon": "10d",
                "space_forward_replacement_positive_risk_scalar": 1.05,
                "space_forward_replacement_same_theme_strength_min_value": 500.0,
                "space_forward_replacement_same_theme_strength_risk_scalar": 1.05,
                "space_forward_replacement_trend_strength_risk_scalar": 1.05,
                "space_forward_replacement_iwm_leader_trend_risk_scalar": 1.025,
                "space_forward_replacement_company_source_trend_risk_scalar": 1.025,
                "space_delayed_absorption_trend_risk_scalar": 1.025,
                "space_benchmark_breadth_trend_risk_scalar": 1.025,
                "space_benchmark_breadth_iwm_leader_trend_risk_scalar": 1.0125,
                "space_defense_budget_same_theme_winner_trend_risk_scalar": 1.05,
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
                    "space_peer_momentum_state": "leader",
                    "space_iwm_relative_state": "smallcap_leader",
                    "theme_segment": "launch_lunar",
                    "liquidity_tier": "ok",
                    "space_official_customer_source_bucket": True,
                    "space_customer_source_peer_leader_bucket": True,
                    "space_government_contract_peer_leader_bucket": True,
                    "space_iwm_peer_leader_trend_bucket": True,
                    "space_company_release_customer_source_bucket": True,
                    "space_financing_dilution_profile_bucket": True,
                    "space_multi_event_depth_bucket": True,
                    "space_single_event_defense_bucket": True,
                    "space_attention_overlay_bucket": True,
                    "space_source_diversity_bucket": True,
                    "space_source_diversity_peer_leader_bucket": True,
                    "space_source_diversity_iwm_leader_bucket": True,
                    "space_source_diversity_peer_iwm_leader_bucket": True,
                    "space_source_diversity_trend_bucket": True,
                    "space_source_diversity_peer_nonleader_trend_bucket": True,
                    "space_forward_replacement_positive_bucket": True,
                    "space_forward_replacement_same_theme_strength_bucket": True,
                    "space_forward_replacement_trend_strength_bucket": True,
                    "space_forward_replacement_iwm_leader_trend_bucket": True,
                    "space_forward_replacement_company_source_trend_bucket": True,
                    "space_delayed_absorption_trend_bucket": True,
                    "space_benchmark_breadth_trend_bucket": True,
                    "space_benchmark_breadth_iwm_leader_trend_bucket": True,
                    "space_defense_budget_same_theme_winner_trend_bucket": True,
                    "space_perfect_tqs_bucket": False,
                    "space_near_perfect_tqs_trend_bucket": False,
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
        "perfect Space TQS @ 1.5x; "
        "near-perfect Space trend TQS @ 1.1x; "
        "peer-nonleader Space breakout @ 0.0x; "
        "IWM>SPY Space risk @ 1.1x; "
        "IWM+peer-leader Space trend @ 1.15x; "
        "launch/lunar theme risk @ 1.1x; "
        "liquidity tier ok @ 1.1x; "
        "liquidity tier watch @ 1.1x; "
        "official customer source customer_win @ 1.1x; "
        "customer-source peer leader @ 1.1x; "
        "government-contract peer leader @ 1.05x; "
        "company-release customer source @ 1.1x; "
        "financing/dilution profile @ 1.075x; "
        "multi-event catalyst depth >=2 @ 1.075x; "
        "single-event defense-only @ 1.05x; "
        "attention overlay with official catalyst @ 1.25x; "
        "official source diversity @ 1.075x; "
        "source-diversity peer leader @ 1.15x; "
        "source-diversity IWM-leader @ 1.05x; "
        "source-diversity peer+IWM leader @ 1.05x; "
        "source-diversity trend @ 1.025x; "
        "source-diversity peer-nonleader trend @ 1.025x; "
        "forward replacement-positive 10d @ 1.05x; "
        "forward same-theme replacement-strength >=500.0 @ 1.05x; "
        "forward replacement-strength trend @ 1.05x; "
        "forward replacement-strength IWM trend @ 1.025x; "
        "forward replacement-strength company-source trend @ 1.025x; "
        "delayed-absorption trend @ 1.025x; "
        "benchmark-breadth trend @ 1.025x; "
        "benchmark-breadth IWM-leader trend @ 1.0125x; "
        "defense-budget same-theme winner trend @ 1.05x)"
    ) in report
    assert "SPACE CATALYST EVENT LEDGER" in report
    assert "SPACE CATALYST PRODUCTION OBSERVATION SLOT" in report
    assert "Live slots: 0" in report
    assert "RKLB: trend_long entry $100.00 target $125.00" in report
    assert (
        "risk=1.03125x basket=positive peer=leader iwm=smallcap_leader "
        "theme=launch_lunar liquidity=ok customer_source=True "
        "source_peer_leader=True government_contract_peer_leader=True "
        "iwm_peer_leader_trend=True "
        "company_release_source=True "
        "financing_dilution_profile=True "
        "multi_event_depth=True single_event_defense=True "
        "attention_overlay=True source_diversity=True "
        "source_diversity_peer_leader=True "
        "source_diversity_iwm_leader=True "
        "source_diversity_peer_iwm_leader=True "
        "source_diversity_trend=True "
        "source_diversity_peer_nonleader_trend=True "
        "forward_replacement_positive=True "
        "forward_replacement_same_theme_strength=True "
        "forward_replacement_trend_strength=True "
        "forward_replacement_iwm_leader_trend=True "
        "forward_replacement_company_source_trend=True "
        "delayed_absorption_trend=True "
        "benchmark_breadth_trend=True"
        " benchmark_breadth_iwm_leader_trend=True"
        " defense_budget_same_theme_winner_trend=True"
    ) in report
    assert "Closed 10d: 0" in report
    assert "LUNR: fundamental_contract_regulatory" in report
