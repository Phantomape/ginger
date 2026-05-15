from space_catalyst_sleeve import (
    SPACE_CATALYST_BENCHMARK_BREADTH_PEER_NONLEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR,
    SPACE_CATALYST_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_TREND_RISK_SCALAR,
    build_space_catalyst_observation_slot,
    empty_space_catalyst_shadow_snapshot,
    space_catalyst_forward_risk_scalar,
)


BENCHMARK_BREADTH_PROFILE = {
    "closed_event_count": 1,
    "avg_10d_cash_relative_pnl": 100.0,
    "avg_10d_spy_relative_value": 100.0,
    "avg_10d_qqq_relative_value": 100.0,
    "avg_10d_ufo_relative_value": 100.0,
    "avg_10d_arkx_relative_value": 100.0,
}


SOURCE_DIVERSITY_PROFILE = {
    "event_count": 2,
    "source_types": [
        "official_or_primary_release",
        "official_government_release",
    ],
    "semantic_buckets": [
        "customer_win",
        "defense_budget_theme",
    ],
}


def test_space_benchmark_breadth_peer_nonleader_trend_adds_extra_risk_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        forward_replacement_profile=BENCHMARK_BREADTH_PROFILE,
    )
    leader_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "leader"},
        forward_replacement_profile=BENCHMARK_BREADTH_PROFILE,
    )

    assert risk == (
        SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_PEER_NONLEADER_TREND_RISK_SCALAR
    )
    assert leader_risk == SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR


def test_observation_slot_surfaces_benchmark_breadth_peer_nonleader_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-14",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-14"),
        candidate_signals=[
            {
                "ticker": "LUNR",
                "strategy": "trend_long",
                "action": "BUY",
                "entry_price": 50.0,
                "stop_price": 45.0,
                "target_price": 58.0,
                "target_mult_used": 3.5,
                "trade_quality_score": 0.8,
                "confidence_score": 0.8,
                "risk_reward_ratio": 2.0,
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 5000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"LUNR": {"atr": 2.0, "momentum_20d_pct": 0.0}},
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "LUNR": BENCHMARK_BREADTH_PROFILE,
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    assert plan["space_benchmark_breadth_trend_bucket"] is True
    assert plan["space_benchmark_breadth_peer_nonleader_trend_bucket"] is True
    assert plan["space_benchmark_breadth_peer_nonleader_trend_risk_scalar"] == 1.025
    assert plan["space_peer_momentum_state"] == "nonleader"
    assert plan["effective_risk_scalar"] == 0.787969
    assert plan["trade_enabled"] is False


def test_space_source_diversity_peer_nonleader_near_perfect_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.97,
    )
    lower_quality_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.9,
    )

    assert risk == (
        SPACE_CATALYST_NEAR_PERFECT_TQS_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_RISK_SCALAR
    )
    assert lower_quality_risk == (
        SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_RISK_SCALAR
    )


def test_observation_slot_surfaces_source_diversity_peer_nonleader_near_perfect_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-15",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-15"),
        candidate_signals=[
            {
                "ticker": "LUNR",
                "strategy": "trend_long",
                "action": "BUY",
                "entry_price": 50.0,
                "stop_price": 45.0,
                "target_price": 58.0,
                "target_mult_used": 3.5,
                "trade_quality_score": 0.97,
                "confidence_score": 0.8,
                "risk_reward_ratio": 2.0,
                "sizing": {
                    "shares_to_buy": 100,
                    "position_value_usd": 5000.0,
                    "base_risk_pct": 0.01,
                    "risk_pct": 0.01,
                },
            }
        ],
        features_by_ticker={"LUNR": {"atr": 2.0, "momentum_20d_pct": 0.0}},
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={"LUNR": SOURCE_DIVERSITY_PROFILE},
        space_forward_replacement_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.97,
    )
    assert plan["space_peer_momentum_state"] == "nonleader"
    assert plan["space_source_diversity_peer_nonleader_trend_bucket"] is True
    assert (
        plan["space_source_diversity_peer_nonleader_near_perfect_trend_bucket"]
        is True
    )
    assert plan[
        "space_source_diversity_peer_nonleader_near_perfect_trend_risk_scalar"
    ] == 1.025
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False
