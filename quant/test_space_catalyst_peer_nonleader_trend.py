from space_catalyst_sleeve import (
    SPACE_CATALYST_BENCHMARK_BREADTH_PEER_NONLEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR,
    SPACE_CATALYST_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR,
    SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR,
    SPACE_CATALYST_IWM_RELATIVE_LEADER_RISK_SCALAR,
    SPACE_CATALYST_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_FINANCING_PROFILE_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_IWM_LEADER_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_NEAR_PERFECT_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_SAME_THEME_WINNER_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_TREND_RISK_SCALAR,
    SPACE_CATALYST_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR,
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


DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE = {
    **SOURCE_DIVERSITY_PROFILE,
    "event_fields": [
        "customer_win",
        "government_space_contract",
    ],
}


DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE = {
    "closed_event_count": 1,
    "avg_5d_cash_relative_pnl": 10.0,
    "avg_10d_cash_relative_pnl": 100.0,
    "avg_10d_same_theme_replacement_value": 600.0,
    "rows": [
        {
            "semantic_bucket": "defense_budget_theme",
            "event_fields": ["government_space_contract"],
            "cash_relative_pnl": 100.0,
            "same_theme_replacement_value": 600.0,
        }
    ],
}


DEFENSE_BUDGET_NONWINNER_PROFILE = {
    **DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
    "rows": [
        {
            "semantic_bucket": "defense_budget_theme",
            "event_fields": ["government_space_contract"],
            "cash_relative_pnl": -1.0,
            "same_theme_replacement_value": 600.0,
        }
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


def test_space_source_diversity_dual_catalyst_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
    )
    breakout_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "breakout_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
    )

    assert risk == (
        SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_TREND_RISK_SCALAR
    )
    assert breakout_risk == SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR


def test_space_source_diversity_dual_catalyst_iwm_leader_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        iwm_relative_momentum_state={"state": "smallcap_leader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
    )
    laggard_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        iwm_relative_momentum_state={"state": "smallcap_laggard"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
    )

    assert round(risk, 6) == round(
        laggard_risk
        * SPACE_CATALYST_IWM_RELATIVE_LEADER_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_IWM_LEADER_TREND_RISK_SCALAR,
        6,
    )


def test_space_source_diversity_dual_catalyst_same_theme_winner_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
    )
    nonwinner_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=DEFENSE_BUDGET_NONWINNER_PROFILE,
    )
    breakout_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "breakout_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
    )

    assert round(risk, 6) == round(
        nonwinner_risk
        * SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_SAME_THEME_WINNER_TREND_RISK_SCALAR,
        6,
    )
    assert round(breakout_risk, 6) == round(
        SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_POSITIVE_RISK_SCALAR
        * SPACE_CATALYST_FORWARD_REPLACEMENT_SAME_THEME_STRENGTH_RISK_SCALAR,
        6,
    )


def test_space_source_diversity_dual_catalyst_near_perfect_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.97,
    )
    lower_quality_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.9,
    )

    assert round(risk, 6) == round(
        lower_quality_risk
        * SPACE_CATALYST_NEAR_PERFECT_TQS_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_NEAR_PERFECT_TREND_RISK_SCALAR,
        6,
    )


def test_space_source_diversity_dual_catalyst_financing_profile_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        event_guard_profile="satellite_launch_and_financing_sensitive",
    )
    clean_profile_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        event_guard_profile="operating_contracts",
    )
    breakout_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "breakout_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        event_guard_profile="satellite_launch_and_financing_sensitive",
    )

    assert round(risk, 6) == round(
        clean_profile_risk
        * SPACE_CATALYST_FINANCING_DILUTION_PROFILE_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_FINANCING_PROFILE_TREND_RISK_SCALAR,
        6,
    )
    assert round(breakout_risk, 6) == round(
        SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR
        * SPACE_CATALYST_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
        6,
    )


def test_space_source_diversity_dual_catalyst_benchmark_breadth_trend_adds_scalar():
    risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=BENCHMARK_BREADTH_PROFILE,
    )
    dual_only_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
    )
    breakout_risk = space_catalyst_forward_risk_scalar(
        "LUNR",
        "breakout_long",
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=BENCHMARK_BREADTH_PROFILE,
    )

    assert round(risk, 6) == round(
        dual_only_risk
        * SPACE_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR
        * SPACE_CATALYST_SOURCE_DIVERSITY_DUAL_CATALYST_BENCHMARK_BREADTH_TREND_RISK_SCALAR,
        6,
    )
    assert breakout_risk == SPACE_CATALYST_SOURCE_DIVERSITY_RISK_SCALAR


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


def test_observation_slot_surfaces_source_diversity_dual_catalyst_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-16",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-16"),
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
        space_source_diversity_profiles={
            "LUNR": DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE
        },
        space_forward_replacement_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.8,
    )
    assert plan["space_source_diversity_dual_catalyst_trend_bucket"] is True
    assert plan["space_source_diversity_dual_catalyst_trend_event_fields"] == [
        "customer_win",
        "government_space_contract",
    ]
    assert plan["space_source_diversity_dual_catalyst_trend_risk_scalar"] == 1.025
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False


def test_observation_slot_surfaces_source_diversity_dual_catalyst_iwm_leader_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-16",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-16"),
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
        features_by_ticker={
            "LUNR": {"atr": 2.0, "momentum_20d_pct": 0.0},
            "IWM": {"momentum_20d_pct": 0.04},
            "SPY": {"momentum_20d_pct": 0.01},
        },
        space_event_source_profiles={},
        space_government_contract_profiles={},
        space_multi_event_depth_profiles={},
        space_single_event_defense_profiles={},
        space_attention_overlay_profiles={},
        space_source_diversity_profiles={
            "LUNR": DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE
        },
        space_forward_replacement_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        iwm_relative_momentum_state={"state": "smallcap_leader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.8,
    )
    assert plan["space_iwm_relative_state"] == "smallcap_leader"
    assert plan["space_source_diversity_dual_catalyst_trend_bucket"] is True
    assert (
        plan["space_source_diversity_dual_catalyst_iwm_leader_trend_bucket"]
        is True
    )
    assert (
        plan[
            "space_source_diversity_dual_catalyst_iwm_leader_trend_risk_scalar"
        ]
        == 1.0125
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False


def test_observation_slot_surfaces_dual_catalyst_same_theme_winner_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-16",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-16"),
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
        space_source_diversity_profiles={
            "LUNR": DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE
        },
        space_forward_replacement_profiles={
            "LUNR": DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE
        },
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE,
        trade_quality_score=0.8,
    )
    assert plan["space_source_diversity_dual_catalyst_trend_bucket"] is True
    assert (
        plan[
            "space_source_diversity_dual_catalyst_same_theme_winner_trend_bucket"
        ]
        is True
    )
    assert (
        plan[
            "space_source_diversity_dual_catalyst_same_theme_winner_trend_risk_scalar"
        ]
        == 1.0125
    )
    assert (
        plan["space_source_diversity_dual_catalyst_same_theme_winner_profile"]
        == DEFENSE_BUDGET_SAME_THEME_WINNER_PROFILE
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False


def test_observation_slot_surfaces_dual_catalyst_near_perfect_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-16",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-16"),
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
        space_source_diversity_profiles={
            "LUNR": DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE
        },
        space_forward_replacement_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        trade_quality_score=0.97,
    )
    assert plan["space_source_diversity_dual_catalyst_trend_bucket"] is True
    assert (
        plan["space_source_diversity_dual_catalyst_near_perfect_trend_bucket"]
        is True
    )
    assert (
        plan[
            "space_source_diversity_dual_catalyst_near_perfect_trend_risk_scalar"
        ]
        == 1.0125
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False


def test_observation_slot_surfaces_dual_catalyst_financing_profile_bucket():
    shadow = empty_space_catalyst_shadow_snapshot("2026-05-16")
    shadow["tickers_by_event_guard_profile"] = {
        "satellite_launch_and_financing_sensitive": ["LUNR"]
    }
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-16",
        space_catalyst_shadow=shadow,
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
        space_source_diversity_profiles={
            "LUNR": DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE
        },
        space_forward_replacement_profiles={},
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        event_guard_profile="satellite_launch_and_financing_sensitive",
        trade_quality_score=0.8,
    )
    assert plan["event_guard_profile"] == "satellite_launch_and_financing_sensitive"
    assert plan["space_source_diversity_dual_catalyst_trend_bucket"] is True
    assert (
        plan["space_source_diversity_dual_catalyst_financing_profile_trend_bucket"]
        is True
    )
    assert (
        plan[
            "space_source_diversity_dual_catalyst_financing_profile_trend_risk_scalar"
        ]
        == 1.0125
    )
    assert (
        plan["space_source_diversity_dual_catalyst_financing_profile"]
        == "satellite_launch_and_financing_sensitive"
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False


def test_observation_slot_surfaces_dual_catalyst_benchmark_breadth_bucket():
    snapshot = build_space_catalyst_observation_slot(
        as_of="2026-05-16",
        space_catalyst_shadow=empty_space_catalyst_shadow_snapshot("2026-05-16"),
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
        space_source_diversity_profiles={
            "LUNR": DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE
        },
        space_forward_replacement_profiles={"LUNR": BENCHMARK_BREADTH_PROFILE},
    )

    plan = snapshot["blocked_trade_plans"][0]
    expected_sleeve_scalar = space_catalyst_forward_risk_scalar(
        "LUNR",
        "trend_long",
        peer_momentum_state={"state": "nonleader"},
        source_diversity_profile=DUAL_CATALYST_SOURCE_DIVERSITY_PROFILE,
        forward_replacement_profile=BENCHMARK_BREADTH_PROFILE,
        trade_quality_score=0.8,
    )
    assert plan["space_benchmark_breadth_trend_bucket"] is True
    assert (
        plan[
            "space_source_diversity_dual_catalyst_benchmark_breadth_trend_bucket"
        ]
        is True
    )
    assert (
        plan[
            "space_source_diversity_dual_catalyst_benchmark_breadth_trend_risk_scalar"
        ]
        == 1.0125
    )
    assert (
        plan["space_source_diversity_dual_catalyst_benchmark_breadth_profile"]
        == BENCHMARK_BREADTH_PROFILE
    )
    assert plan["effective_risk_scalar"] == round(0.75 * expected_sleeve_scalar, 6)
    assert plan["trade_enabled"] is False
