from __future__ import annotations

from datetime import date, timedelta

import quant.broad_market_paper_sleeve as broad_market_sleeve
from quant.broad_market_paper_sleeve import (
    HIGH_VOLATILITY_RULE_VERSION,
    LOW_EXTENSION_RULE_VERSION,
    REPLACEMENT_VALUE_RULE_VERSION,
    TREND_PERSISTENCE_RULE_VERSION,
    UNIVERSE_STATE_FEED_RULE_VERSION,
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
    prep_and_build_broad_market_paper_sleeve_snapshot,
)


def _rows(
    start_price: float,
    step: float,
    *,
    volume_last: float = 1500.0,
    start: date = date(2026, 1, 1),
) -> list[dict]:
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


def _clean_feed(
    as_of: str,
    tickers: list[str],
    *,
    hash_char: str = "a",
) -> dict:
    hashes = {
        "membership_hash": hash_char * 64,
        "membership_snapshot_hash": chr(ord(hash_char) + 1) * 64,
        "membership_ledger_hash": chr(ord(hash_char) + 2) * 64,
    }
    return {
        "status": "loaded",
        "path": "test-clean-universe.json",
        "as_of": as_of,
        "tickers": tickers,
        "records": {ticker: {"ticker": ticker} for ticker in tickers},
        "membership_as_of": as_of,
        **hashes,
        "membership_ledger_status": "appended",
        "clean_cutoff": "2026-07-17",
        "forward_generation": "broad_market_clean_forward_v1",
        "membership": {
            "effective_as_of": as_of,
            "membership_hash": hashes["membership_hash"],
            "snapshot_hash": hashes["membership_snapshot_hash"],
            "ledger_hash": hashes["membership_ledger_hash"],
            "ledger_status": "appended",
            "clean_cutoff": "2026-07-17",
            "forward_generation": "broad_market_clean_forward_v1",
        },
    }


def _membership_projection(row: dict) -> dict:
    return {
        key: row.get(key)
        for key in (
            "cohort",
            "membership_as_of",
            "membership_hash",
            "membership_snapshot_hash",
            "membership_ledger_hash",
            "clean_cutoff",
            "forward_generation",
        )
    }


def _open_position(ticker: str, created_asof: str, **extra) -> dict:
    return {
        "decision_id": f"open-{ticker}",
        "ticker": ticker,
        "created_asof": created_asof,
        "entry_date": created_asof,
        "entry_price": 50.0,
        "notional": 10_000.0,
        "observed_trading_days": 0,
        **extra,
    }


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


def test_clean_forward_capacity_excludes_five_legacy_open_positions():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    as_of = spy_rows[60]["date"]
    feed = _clean_feed(as_of, ["WIN"])
    state = empty_broad_market_paper_state()
    state["open_positions"] = [
        _open_position(f"LEGACY{idx}", "2026-07-16") for idx in range(5)
    ]

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=feed,
        state=state,
        persist=False,
    )

    assert snapshot["open_position_count"] == 5
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert _membership_projection(snapshot["candidates"][0]) == _membership_projection(
        snapshot["new_pending_entries"][0]
    )
    capacity = snapshot["cohort_capacity"]
    assert capacity["mode"] == "clean_forward_generation"
    assert capacity["legacy_carry_active_count"] == 5
    assert capacity["same_generation_provenanced_active_count"] == 1
    assert capacity["remaining_capacity"] == 4
    assert capacity["legacy_carry_starvation_bypassed"] is True
    assert snapshot["trade_enabled"] is False


def test_clean_membership_provenance_survives_pending_to_next_session_fill():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    first_as_of = spy_rows[60]["date"]
    first = build_broad_market_paper_sleeve_snapshot(
        as_of=first_as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=_clean_feed(first_as_of, ["WIN"], hash_char="a"),
        state=empty_broad_market_paper_state(),
        persist=False,
    )
    pending_provenance = _membership_projection(first["pending_entries"][0])

    state = empty_broad_market_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second_as_of = spy_rows[61]["date"]
    second = build_broad_market_paper_sleeve_snapshot(
        as_of=second_as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=_clean_feed(second_as_of, ["WIN"], hash_char="d"),
        state=state,
        persist=False,
    )

    assert second["filled_count"] == 1
    filled = second["filled_entries"][0]
    assert _membership_projection(filled) == pending_provenance
    assert _membership_projection(filled["source_candidate"]) == pending_provenance
    assert filled["membership_hash"] != second["data_source"]["membership_hash"]
    assert filled["trade_enabled"] is False


def test_clean_active_at_cap_blocks_candidates_and_uses_clean_only_evidence():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    as_of = spy_rows[60]["date"]
    feed = _clean_feed(as_of, ["WIN"])
    provenance = _membership_projection({**feed, "cohort": "clean_forward"})
    state = empty_broad_market_paper_state()
    state["open_positions"] = [
        _open_position(f"CLEAN{idx}", as_of, **provenance) for idx in range(5)
    ]
    state["closed_positions"] = [
        {**_open_position("CLEAN-CLOSED", as_of, **provenance), "pnl": 125.0},
        {**_open_position("LEGACY-CLOSED", "2026-07-16"), "pnl": 10_000.0},
    ]

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=feed,
        state=state,
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 0
    capacity = snapshot["cohort_capacity"]
    assert capacity["same_generation_provenanced_active_count"] == 5
    assert capacity["remaining_capacity"] == 0
    assert capacity["starved"] is True
    assert capacity["starvation_reason"] == "clean_cohort_at_capacity"
    assert snapshot["forward_paper_gate"]["metrics"]["closed_trades"] == 1
    assert snapshot["forward_paper_gate"]["cohort_scope"] == "clean_forward_generation"
    assert snapshot["replacement_value_report"]["closed_count"] == 1
    assert snapshot["replacement_value_report"]["closed_pnl"] == 125.0
    assert snapshot["cohort_evidence"]["excluded_non_current_clean_closed_count"] == 1


def test_stale_fill_day_feed_keeps_stored_clean_evidence_isolated():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    signal_as_of = spy_rows[60]["date"]
    fill_as_of = spy_rows[61]["date"]
    win_rows[61]["volume"] = 2_000.0
    signal_feed = _clean_feed(signal_as_of, ["WIN"])
    provenance = _membership_projection(
        {**signal_feed, "cohort": "clean_forward"}
    )
    invalid_provenance = {**provenance, "membership_hash": "not-a-sha256"}
    state = empty_broad_market_paper_state()
    state["closed_positions"] = [
        {
            **_open_position("CLEAN-CLOSED", signal_as_of, **provenance),
            "pnl": 125.0,
        },
        {
            **_open_position("INVALID-CLEAN", signal_as_of, **invalid_provenance),
            "pnl": 9_000.0,
        },
        {**_open_position("LEGACY-CLOSED", "2026-07-16"), "pnl": 10_000.0},
    ]

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=fill_as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=signal_feed,
        state=state,
        persist=False,
    )

    assert snapshot["cohort_capacity"]["mode"] == "legacy_global"
    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 0
    assert snapshot["cohort_capacity"]["admission_blocked_without_current_context"] is True
    assert (
        snapshot["cohort_capacity"]["admission_blocked_reason"]
        == "missing_current_clean_membership_context"
    )
    assert snapshot["cohort_evidence"]["clean_context_active"] is False
    assert snapshot["cohort_evidence"]["stored_clean_rows_present"] is True
    assert snapshot["forward_paper_gate"]["cohort_scope"] == "clean_forward_generation"
    assert snapshot["forward_paper_gate"]["metrics"]["closed_trades"] == 1
    assert snapshot["forward_paper_gate"]["metrics"]["realized_pnl"] == 125.0
    assert snapshot["replacement_value_report"]["closed_count"] == 1
    assert snapshot["replacement_value_report"]["closed_pnl"] == 125.0
    assert snapshot["cohort_evidence"]["excluded_non_current_clean_closed_count"] == 2


def test_post_cutoff_unattributed_active_row_consumes_clean_capacity():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    as_of = spy_rows[60]["date"]
    feed = _clean_feed(as_of, ["WIN"])
    provenance = _membership_projection({**feed, "cohort": "clean_forward"})
    state = empty_broad_market_paper_state()
    state["open_positions"] = [
        *[
            _open_position(f"CLEAN{idx}", as_of, **provenance)
            for idx in range(4)
        ],
        _open_position("UNTAGGED", as_of),
    ]

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=feed,
        state=state,
        persist=False,
    )

    assert snapshot["new_pending_count"] == 0
    assert snapshot["cohort_capacity"]["post_cutoff_unattributed_active_count"] == 1
    assert snapshot["cohort_capacity"]["capacity_consuming_active_count"] == 5


def test_no_clean_context_preserves_legacy_global_capacity_behavior():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    as_of = spy_rows[60]["date"]
    state = empty_broad_market_paper_state()
    state["open_positions"] = [
        _open_position(f"LEGACY{idx}", "2026-07-16") for idx in range(5)
    ]

    snapshot = build_broad_market_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
        candidate_universe=["WIN"],
        state=state,
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 0
    assert snapshot["pending_count"] == 0
    assert snapshot["cohort_capacity"]["mode"] == "legacy_global"
    assert snapshot["cohort_capacity"]["starvation_reason"] == "legacy_global_capacity_at_limit"
    assert snapshot["forward_paper_gate"]["cohort_scope"] == "legacy_global"


def test_incomplete_or_stale_clean_context_falls_back_to_legacy_capacity():
    start = date(2026, 5, 21)
    spy_rows = _rows(100.0, 0.02, start=start)
    win_rows = _rows(50.0, 0.35, start=start)
    as_of = spy_rows[60]["date"]
    variants = [
        {"membership_as_of": "2026-07-19"},
        {"as_of": None},
        {"membership_ledger_status": "dry_run_not_persisted"},
        {"forward_generation": "broad_market_clean_forward_v2"},
        {"membership_hash": "not-a-sha256"},
    ]

    for updates in variants:
        feed = _clean_feed(as_of, ["WIN"])
        feed.pop("membership")
        feed.update(updates)
        state = empty_broad_market_paper_state()
        state["open_positions"] = [
            _open_position(f"LEGACY{idx}", "2026-07-16") for idx in range(5)
        ]
        snapshot = build_broad_market_paper_sleeve_snapshot(
            as_of=as_of,
            ohlcv_by_ticker={"SPY": spy_rows, "WIN": win_rows},
            candidate_universe=feed,
            state=state,
            persist=False,
        )
        assert snapshot["new_pending_count"] == 0
        assert snapshot["cohort_capacity"]["mode"] == "legacy_global"


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


def test_prep_keeps_retired_pending_and_open_tickers_marked_to_asof(monkeypatch):
    spy_rows = _rows(100.0, 0.02)
    held_rows = _rows(50.0, 0.20)
    pending_rows = _rows(45.0, 0.18)
    as_of = spy_rows[61]["date"]
    previous = spy_rows[60]["date"]
    state = empty_broad_market_paper_state()
    state["open_positions"] = [
        {
            "decision_id": "open-held",
            "ticker": "HELD",
            "entry_date": previous,
            "entry_price": 50.0,
            "notional": 10_000.0,
            "observed_trading_days": 18,
            "last_seen_date": previous,
        }
    ]
    state["pending_entries"] = [
        {
            "decision_id": "pending-retired",
            "ticker": "PEND",
            "created_asof": previous,
            "status": "pending_next_session_open",
            "intended_notional": 10_000.0,
        }
    ]
    feed = {
        "status": "loaded",
        "path": "test-universe.json",
        "rule_version": "test-feed-v1",
        "tickers": [],
        "records": {},
        "membership_hash": "membership-123",
        "membership_as_of": as_of,
        "membership_snapshot_hash": "snapshot-123",
        "membership_ledger_hash": "ledger-123",
        "membership_ledger_status": "appended",
        "clean_cutoff": as_of,
        "forward_generation": "broad_market_clean_forward_v1",
    }
    monkeypatch.setattr(
        broad_market_sleeve,
        "load_broad_market_candidate_universe",
        lambda: feed,
    )
    full_rows = {"HELD": held_rows, "PEND": pending_rows}
    cache_calls: list[str] = []

    def cached(ticker: str):
        cache_calls.append(ticker)
        return full_rows[ticker]

    snapshot, loaded, ohlcv = prep_and_build_broad_market_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_dict={
            "SPY": spy_rows,
            "HELD": _drop_date(held_rows, as_of),
            "PEND": _drop_date(pending_rows, as_of),
        },
        cached_ohlcv_fn=cached,
        state=state,
        persist=False,
        refresh_disabled=True,
        feed_disabled=True,
    )

    assert loaded["tickers"] == []
    assert set(ohlcv) == {"SPY", "HELD", "PEND"}
    assert set(cache_calls) == {"HELD", "PEND"}
    assert snapshot["closed_count_today"] == 1
    assert snapshot["closed_positions_today"][0]["ticker"] == "HELD"
    assert snapshot["filled_count"] == 1
    assert snapshot["open_positions"][0]["ticker"] == "PEND"
    assert snapshot["data_source"]["membership_hash"] == "membership-123"
    assert snapshot["data_source"]["membership_as_of"] == as_of
    assert (
        snapshot["data_source"]["forward_generation"]
        == "broad_market_clean_forward_v1"
    )


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
