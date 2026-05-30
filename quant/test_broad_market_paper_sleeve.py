from __future__ import annotations

from datetime import date, timedelta

from quant.broad_market_paper_sleeve import (
    CORRELATION_CROWDING_RULE_VERSION,
    HIGH_VOLATILITY_RULE_VERSION,
    LOW_EXTENSION_RULE_VERSION,
    REPLACEMENT_VALUE_RULE_VERSION,
    TREND_PERSISTENCE_RULE_VERSION,
    UNIVERSE_STATE_FEED_RULE_VERSION,
    _pearson_corr_safe,
    _trailing_close_returns,
    broad_market_candidate_notional_payload,
    broad_market_high_volatility_multiplier,
    broad_market_low_extension_multiplier,
    broad_market_rank_notional_multiplier,
    broad_market_trend_persistence_multiplier,
    build_broad_market_candidate_universe_from_universe_state,
    build_broad_market_replacement_value_report,
    build_broad_market_paper_candidates,
    build_broad_market_paper_sleeve_snapshot,
    build_broad_market_feature,
    candidate_passes_profile,
    empty_broad_market_paper_state,
    max_corr_to_active_positions,
    select_broad_market_features_corr_crowding,
)


def _rows(start_price: float, step: float, *, volume_last: float = 1500.0) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(62):
        close = start_price + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": close * 0.99,
                "high": close,
                "low": close * 0.98,
                "close": close,
                "volume": volume_last if idx == 60 else 1000.0,
            }
        )
    return rows


def _drop_date(rows: list[dict], as_of: str) -> list[dict]:
    return [row for row in rows if row["date"] != as_of]


def test_broad_market_feature_and_price_floor_gate():
    spy_rows = _rows(100.0, 0.02)
    high_price_rows = _rows(50.0, 0.35)
    low_price_rows = _rows(20.0, 0.18)
    spy_index = {row["date"]: idx for idx, row in enumerate(spy_rows)}

    high_feature = build_broad_market_feature(
        ticker="WIN",
        rows=high_price_rows,
        idx=60,
        spy_rows=spy_rows,
        spy_index=spy_index,
    )
    low_feature = build_broad_market_feature(
        ticker="LOW",
        rows=low_price_rows,
        idx=60,
        spy_rows=spy_rows,
        spy_index=spy_index,
    )

    assert high_feature is not None
    assert high_feature["close"] >= 40.0
    assert high_feature["ret5"] > 0.02
    assert high_feature["realized_volatility_20"] >= 0.0
    assert high_feature["positive_day_ratio_20"] == 1.0
    assert candidate_passes_profile(high_feature)
    assert low_feature is not None
    assert low_feature["close"] < 40.0
    assert not candidate_passes_profile(low_feature)


def test_candidate_builder_excludes_tradeable_and_title_noise():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    etf_rows = _rows(55.0, 0.30)
    ohlcv = {"SPY": spy_rows, "WIN": win_rows, "ETFZ": etf_rows, "CORE": win_rows}

    candidates = build_broad_market_paper_candidates(
        as_of=spy_rows[60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_tickers=["WIN", "ETFZ", "CORE"],
        ticker_metadata={"ETFZ": {"title": "Example Growth ETF"}},
        current_tradeable_universe={"CORE"},
    )

    assert [row["ticker"] for row in candidates] == ["WIN"]
    assert candidates[0]["trade_enabled"] is False
    assert candidates[0]["rank_notional_multiplier"] == 1.2
    assert candidates[0]["trend_persistence_support_applied"] is True
    assert candidates[0]["intended_notional"] == 10350.0
    assert candidates[0]["low_extension_support_applied"] is False


def test_low_extension_support_scales_paper_notional_only_when_ret5_is_low():
    low_extension_feature = {"ret5": 0.01}
    extended_feature = {"ret5": 0.03}

    assert broad_market_low_extension_multiplier(low_extension_feature) == 1.15
    assert broad_market_low_extension_multiplier(extended_feature) == 1.0

    payload = broad_market_candidate_notional_payload(1, low_extension_feature)
    assert payload["base_notional"] == 7500.0
    assert payload["rank_multiplier"] == 1.2
    assert payload["low_extension_multiplier"] == 1.15
    assert payload["low_extension_support_applied"] is True
    assert payload["notional"] == 10350.0


def test_high_volatility_support_scales_paper_notional_after_low_extension():
    high_volatility_feature = {"ret5": 0.03, "realized_volatility_20": 0.06}
    low_volatility_feature = {"ret5": 0.03, "realized_volatility_20": 0.04}

    assert broad_market_high_volatility_multiplier(high_volatility_feature) == 1.15
    assert broad_market_high_volatility_multiplier(low_volatility_feature) == 1.0

    payload = broad_market_candidate_notional_payload(1, high_volatility_feature)
    assert payload["base_notional"] == 7500.0
    assert payload["rank_multiplier"] == 1.2
    assert payload["low_extension_multiplier"] == 1.0
    assert payload["high_volatility_multiplier"] == 1.15
    assert payload["high_volatility_support_applied"] is True
    assert payload["notional"] == 10350.0

    stacked = broad_market_candidate_notional_payload(
        1,
        {"ret5": 0.01, "realized_volatility_20": 0.06},
    )
    assert stacked["low_extension_multiplier"] == 1.15
    assert stacked["high_volatility_multiplier"] == 1.15
    assert stacked["notional"] == 11902.5


def test_trend_persistence_support_scales_after_existing_paper_helpers():
    persistent_feature = {
        "ret5": 0.03,
        "realized_volatility_20": 0.06,
        "positive_day_ratio_20": 0.60,
    }
    choppy_feature = {
        "ret5": 0.03,
        "realized_volatility_20": 0.06,
        "positive_day_ratio_20": 0.50,
    }

    assert broad_market_trend_persistence_multiplier(persistent_feature) == 1.15
    assert broad_market_trend_persistence_multiplier(choppy_feature) == 1.0

    payload = broad_market_candidate_notional_payload(1, persistent_feature)
    assert payload["base_notional"] == 7500.0
    assert payload["rank_multiplier"] == 1.2
    assert payload["high_volatility_multiplier"] == 1.15
    assert payload["trend_persistence_multiplier"] == 1.15
    assert payload["trend_persistence_support_applied"] is True
    assert payload["notional"] == 11902.5


def test_rank_notional_profile_uses_last_multiplier_for_deeper_ranks():
    assert broad_market_rank_notional_multiplier(1) == 1.2
    assert broad_market_rank_notional_multiplier(2) == 1.0
    assert broad_market_rank_notional_multiplier(3) == 0.8
    assert broad_market_rank_notional_multiplier(4) == 0.8
    assert broad_market_rank_notional_multiplier(
        1,
        {"rank_notional_multipliers": [1.0]},
    ) == 1.0


def test_snapshot_adds_pending_and_fills_next_session_without_orders():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    ohlcv = {"SPY": spy_rows, "WIN": win_rows}

    first = build_broad_market_paper_sleeve_snapshot(
        as_of=spy_rows[60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN"],
        state=empty_broad_market_paper_state(),
        persist=False,
    )
    assert first["candidate_count"] == 1
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["production_impact"]["alters_orders"] is False
    assert first["candidates"][0]["low_extension_rule_version"] == LOW_EXTENSION_RULE_VERSION

    state = empty_broad_market_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second = build_broad_market_paper_sleeve_snapshot(
        as_of=spy_rows[61]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["WIN"],
        state=state,
        persist=False,
    )
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["trade_enabled"] is False
    assert second["replacement_value_report"]["rule_version"] == REPLACEMENT_VALUE_RULE_VERSION
    assert second["replacement_value_report"]["open_count"] == 1
    assert second["open_positions"][0]["source_candidate"]["high_volatility_rule_version"] == HIGH_VOLATILITY_RULE_VERSION
    assert second["open_positions"][0]["source_candidate"]["trend_persistence_rule_version"] == TREND_PERSISTENCE_RULE_VERSION


def test_snapshot_does_not_use_stale_prices_when_asof_ohlcv_is_missing():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    as_of = spy_rows[61]["date"]
    previous = spy_rows[60]["date"]
    state = empty_broad_market_paper_state()
    state["pending_entries"] = [
        {
            "decision_id": "pending-win",
            "ticker": "WIN",
            "created_asof": previous,
            "status": "pending_next_session_open",
            "intended_notional": 10_000.0,
        }
    ]
    state["open_positions"] = [
        {
            "decision_id": "open-win",
            "ticker": "WIN",
            "entry_date": previous,
            "entry_price": 50.0,
            "notional": 10_000.0,
            "observed_trading_days": 19,
        }
    ]

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={
            "SPY": _drop_date(spy_rows, as_of),
            "WIN": _drop_date(win_rows, as_of),
        },
        candidate_universe=["WIN"],
        state=state,
        open_prices={"WIN": win_rows[60]["open"]},
        current_prices={"WIN": win_rows[60]["close"]},
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["candidate_count"] == 0
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 1
    assert snapshot["open_positions"][0]["observed_trading_days"] == 19


def test_universe_state_feed_uses_observation_records_without_tradeable_names():
    universe_state = {
        "as_of": "2026-05-22",
        "artifact_path": "data/daily/universe/universe_state_20260522.json",
        "core_trade_universe": ["CORE"],
        "pilot_trade_universe": ["PILOT"],
        "governance_tradeable_universe": ["GOV"],
        "observation_universe": ["WIN", "CORE", "PILOT", "GOV", "ARKX", "QUAR"],
        "records": {
            "WIN": {
                "ticker": "WIN",
                "status": "research",
                "theme": "ai_optical_connectivity",
                "theme_segment": "optical_connectivity",
                "eligible_as_of": "2026-05-01",
            },
            "ARKX": {
                "ticker": "ARKX",
                "status": "research",
                "theme": "space_theme_etf",
                "theme_segment": "theme_beta_benchmark",
                "eligible_as_of": "2026-05-01",
            },
            "QUAR": {
                "ticker": "QUAR",
                "status": "quarantine",
                "eligible_as_of": "2026-05-01",
            },
        },
    }

    feed = build_broad_market_candidate_universe_from_universe_state(universe_state)

    assert feed["status"] == "universe_state_observation_feed"
    assert feed["rule_version"] == UNIVERSE_STATE_FEED_RULE_VERSION
    assert feed["tickers"] == ["WIN"]
    assert feed["records"]["WIN"]["feed_rule_version"] == UNIVERSE_STATE_FEED_RULE_VERSION
    assert feed["excluded_count"] == 5


def test_snapshot_accepts_universe_state_feed_when_static_feed_is_absent():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    ohlcv = {"SPY": spy_rows, "WIN": win_rows}
    feed = build_broad_market_candidate_universe_from_universe_state(
        {
            "as_of": spy_rows[60]["date"],
            "artifact_path": "data/daily/universe/universe_state_20260522.json",
            "observation_universe": ["WIN"],
            "records": {
                "WIN": {
                    "ticker": "WIN",
                    "status": "research",
                    "eligible_as_of": "2026-01-01",
                },
            },
        }
    )

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=spy_rows[60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_universe=feed,
        state=empty_broad_market_paper_state(),
        persist=False,
    )

    assert snapshot["data_source"]["status"] == "universe_state_observation_feed"
    assert snapshot["data_source"]["rule_version"] == UNIVERSE_STATE_FEED_RULE_VERSION
    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["production_impact"]["alters_orders"] is False


def test_broad_market_replacement_value_report_tracks_cash_slot_ledger():
    report = build_broad_market_replacement_value_report(
        candidates=[
            {
                "ticker": "WIN",
                "replacement_value_context": {
                    "displaced_resource": "paper_cash_slot"
                },
            }
        ],
        pending_entries=[{"ticker": "WIN"}],
        open_positions=[{"ticker": "OPEN", "unrealized_pnl": 125.5}],
        closed_positions=[
            {"ticker": "WIN", "pnl": 200.0},
            {"ticker": "LOSS", "pnl": -50.0},
        ],
        skipped_entries=[{"ticker": "SKIP"}],
    )

    assert report["read_only"] is True
    assert report["closed_count"] == 2
    assert report["closed_pnl"] == 150.0
    assert report["positive_closed_pnl"] == 200.0
    assert report["by_ticker"]["WIN"]["positive_pnl_share"] == 1.0
    assert report["alters_orders"] is False


def test_pearson_corr_safe_detects_correlation():
    perfectly_correlated = [0.01 * i for i in range(20)]
    assert abs(_pearson_corr_safe(perfectly_correlated, perfectly_correlated) - 1.0) < 1e-9

    anti_correlated = [0.01 * i for i in range(20)]
    neg = [-x for x in anti_correlated]
    assert abs(_pearson_corr_safe(anti_correlated, neg) + 1.0) < 1e-9

    assert _pearson_corr_safe([0.0] * 20, [0.0] * 20) is None  # zero variance

    assert _pearson_corr_safe([0.01] * 5, [0.01] * 5, min_pairs=10) is None  # too few


def test_trailing_close_returns_computes_log_relatives():
    rows = _rows(100.0, 1.0)
    returns = _trailing_close_returns(rows, 20, 5)
    assert len(returns) == 5
    for r in returns:
        assert r > 0  # all steps are positive since step > 0


def test_correlation_crowding_blocks_high_corr_candidate():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    clone_rows = _rows(50.0, 0.35)  # identical price path to WIN → corr ~1.0
    low_corr_rows = _rows(55.0, -0.10)  # declining → low correlation to WIN

    spy_index = {row["date"]: idx for idx, row in enumerate(spy_rows)}
    prices = {"SPY": spy_rows, "WIN": win_rows, "CLONE": clone_rows, "LOW": low_corr_rows}
    date_indexes = {t: {r["date"]: i for i, r in enumerate(rows)} for t, rows in prices.items()}
    day = spy_rows[60]["date"]

    win_feature = build_broad_market_feature(ticker="WIN", rows=win_rows, idx=60, spy_rows=spy_rows, spy_index=spy_index)
    clone_feature = build_broad_market_feature(ticker="CLONE", rows=clone_rows, idx=60, spy_rows=spy_rows, spy_index=spy_index)
    low_feature = build_broad_market_feature(ticker="LOW", rows=low_corr_rows, idx=60, spy_rows=spy_rows, spy_index=spy_index)

    features = [f for f in [win_feature, clone_feature, low_feature] if f is not None]
    assert len(features) >= 2

    # WIN is active; CLONE should be blocked (corr ≈ 1.0 with WIN)
    selected = select_broad_market_features_corr_crowding(
        features,
        capacity=3,
        config={"correlation_crowding_max_corr": 0.75, "correlation_crowding_lookback_days": 20,
                "daily_entry_slots": 3, "max_active_positions": 5},
        active_tickers=["WIN"],
        rows_by_ticker=prices,
        date_indexes=date_indexes,
        day=day,
    )
    selected_tickers = [f["ticker"] for f in selected]
    assert "CLONE" not in selected_tickers  # blocked: too correlated with WIN


def test_correlation_crowding_no_active_positions_selects_all():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    other_rows = _rows(45.0, 0.30)

    spy_index = {row["date"]: idx for idx, row in enumerate(spy_rows)}
    prices = {"SPY": spy_rows, "WIN": win_rows, "OTHER": other_rows}
    date_indexes = {t: {r["date"]: i for i, r in enumerate(rows)} for t, rows in prices.items()}
    day = spy_rows[60]["date"]

    win_feature = build_broad_market_feature(ticker="WIN", rows=win_rows, idx=60, spy_rows=spy_rows, spy_index=spy_index)
    other_feature = build_broad_market_feature(ticker="OTHER", rows=other_rows, idx=60, spy_rows=spy_rows, spy_index=spy_index)
    features = [f for f in [win_feature, other_feature] if f is not None]
    assert len(features) == 2

    # With no active positions, crowding should never block → same result as without crowding
    selected = select_broad_market_features_corr_crowding(
        features,
        capacity=3,
        config={"correlation_crowding_max_corr": 0.75, "correlation_crowding_lookback_days": 20,
                "daily_entry_slots": 3, "max_active_positions": 5},
        active_tickers=[],
        rows_by_ticker=prices,
        date_indexes=date_indexes,
        day=day,
    )
    assert len(selected) == 2


def test_correlation_crowding_rule_version_in_backtest_trade():
    spy_rows = _rows(100.0, 0.02)
    win_rows = _rows(50.0, 0.35)
    ohlcv = {"SPY": spy_rows, "WIN": win_rows}

    candidates = build_broad_market_paper_candidates(
        as_of=spy_rows[60]["date"],
        ohlcv_by_ticker=ohlcv,
        candidate_tickers=["WIN"],
        ticker_metadata={},
        current_tradeable_universe=set(),
    )

    assert len(candidates) == 1
    assert candidates[0]["correlation_crowding_rule_version"] == CORRELATION_CROWDING_RULE_VERSION
    assert candidates[0]["correlation_crowding_max_corr"] == 0.75
