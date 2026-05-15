from space_catalyst_sleeve import (
    SPACE_CATALYST_BENCHMARK_BREADTH_IWM_LEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_BENCHMARK_BREADTH_PEER_NONLEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR,
    SPACE_CATALYST_BENCHMARK_SAME_THEME_STRENGTH_TREND_RISK_SCALAR,
    SPACE_CATALYST_DEFENSE_BUDGET_SAME_THEME_WINNER_TREND_RISK_SCALAR,
    SPACE_CATALYST_FORWARD_REPLACEMENT_IWM_LEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR,
    SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR,
    SPACE_CATALYST_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR,
    SPACE_CATALYST_IWM_RELATIVE_LEADER_RISK_SCALAR,
    SPACE_CATALYST_IWM_PEER_LEADER_TREND_RISK_SCALAR,
    build_space_catalyst_observation_slot,
    empty_space_catalyst_shadow_snapshot,
    space_catalyst_forward_risk_scalar,
)


BENCHMARK_SAME_THEME_PROFILE = {
    "closed_event_count": 1,
    "avg_10d_cash_relative_pnl": 1000.0,
    "avg_10d_same_theme_replacement_value": 1000.0,
    "avg_10d_spy_relative_value": 900.0,
    "avg_10d_qqq_relative_value": 800.0,
    "avg_10d_ufo_relative_value": 700.0,
    "avg_10d_arkx_relative_value": 600.0,
}


DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE = {
    **BENCHMARK_SAME_THEME_PROFILE,
    "rows": [
        {
            "semantic_bucket": "defense_budget_theme",
            "event_fields": ["government_space_contract"],
            "cash_relative_pnl": 1000.0,
            "same_theme_replacement_value": 1000.0,
            "spy_relative_value": 900.0,
            "qqq_relative_value": 800.0,
            "ufo_relative_value": 700.0,
            "arkx_relative_value": 600.0,
        }
    ],
}


def test_space_benchmark_same_theme_strength_adds_extra_trend_risk_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "BKSY",
        "trend_long",
        peer_momentum_state={"state": "leader"},
        forward_replacement_profile=BENCHMARK_SAME_THEME_PROFILE,
    )

    assert risk == (
        SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_SAME_THEME_STRENGTH_TREND_RISK_SCALAR
    )


def test_space_defense_budget_same_theme_winner_adds_extra_trend_risk_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "BKSY",
        "trend_long",
        peer_momentum_state={"state": "leader"},
        forward_replacement_profile=DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
    )

    assert risk == (
        SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_SAME_THEME_STRENGTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_DEFENSE_BUDGET_SAME_THEME_WINNER_TREND_RISK_SCALAR
    )


def test_space_benchmark_iwm_leader_adds_conservative_extra_trend_risk_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "BKSY",
        "trend_long",
        peer_momentum_state={"state": "leader"},
        iwm_relative_momentum_state={"state": "smallcap_leader"},
        forward_replacement_profile=BENCHMARK_SAME_THEME_PROFILE,
    )

    assert risk == (
        SPACE_CATALYST_IWM_RELATIVE_LEADER_RISK_SCALAR
        * SPACE_CATALYST_IWM_PEER_LEADER_TREND_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_IWM_LEADER_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_SAME_THEME_STRENGTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_IWM_LEADER_TREND_RISK_SCALAR
    )


def test_observation_slot_surfaces_benchmark_same_theme_strength_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-14",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-14"),
        candidate_signals=[
            {
                "ticker": "BKSY",
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
        features_by_ticker={"BKSY": {"atr": 2.0, "momentum_20d_pct": 0.0}},
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "BKSY": BENCHMARK_SAME_THEME_PROFILE,
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "BKSY",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        forward_replacement_profile=BENCHMARK_SAME_THEME_PROFILE,
    )
    assert plan["space_benchmark_breadth_trend_bucket"] is True
    assert plan["space_benchmark_breadth_same_theme_strength_trend_bucket"] is True
    assert plan["space_benchmark_breadth_same_theme_strength_trend_risk_scalar"] == 1.025
    assert plan["space_benchmark_breadth_same_theme_strength_profile"] == (
        BENCHMARK_SAME_THEME_PROFILE
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False
    assert expected_sleeve_scalar == (
        SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_TREND_STRENGTH_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_SAME_THEME_STRENGTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_BENCHMARK_BREADTH_PEER_NONLEADER_TREND_RISK_SCALAR
    )


def test_observation_slot_surfaces_defense_budget_same_theme_winner_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-15",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-15"),
        candidate_signals=[
            {
                "ticker": "BKSY",
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
        features_by_ticker={"BKSY": {"atr": 2.0, "momentum_20d_pct": 0.0}},
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "BKSY": DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "BKSY",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        forward_replacement_profile=DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
    )
    assert plan["space_defense_budget_same_theme_winner_trend_bucket"] is True
    assert plan["space_defense_budget_same_theme_winner_trend_risk_scalar"] == (
        SPACE_CATALYST_DEFENSE_BUDGET_SAME_THEME_WINNER_TREND_RISK_SCALAR
    )
    assert plan["space_defense_budget_same_theme_winner_profile"] == (
        DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False


def test_observation_slot_surfaces_benchmark_iwm_leader_trend_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-14",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-14"),
        candidate_signals=[
            {
                "ticker": "BKSY",
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
        features_by_ticker={
            "BKSY": {"atr": 2.0, "momentum_20d_pct": 0.0},
            "IWM": {"momentum_20d_pct": 0.12},
            "SPY": {"momentum_20d_pct": 0.04},
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={},
        space_forward_replacement_profiles={
            "BKSY": BENCHMARK_SAME_THEME_PROFILE,
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "BKSY",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        iwm_relative_momentum_state={"state": "smallcap_leader"},
        forward_replacement_profile=BENCHMARK_SAME_THEME_PROFILE,
    )
    assert plan["space_iwm_relative_state"] == "smallcap_leader"
    assert plan["space_benchmark_breadth_trend_bucket"] is True
    assert plan["space_benchmark_breadth_iwm_leader_trend_bucket"] is True
    assert plan["space_benchmark_breadth_iwm_leader_trend_risk_scalar"] == 1.0125
    assert plan["space_benchmark_breadth_iwm_leader_profile"] == (
        BENCHMARK_SAME_THEME_PROFILE
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False
