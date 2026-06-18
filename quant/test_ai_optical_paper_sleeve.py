from __future__ import annotations

from datetime import date, timedelta

from quant.ai_optical_paper_sleeve import (
    MARKET_CONFIRMATION_RULE_VERSION,
    REPLACEMENT_VALUE_RULE_VERSION,
    RULE_VERSION,
    UNIVERSE_STATE_FEED_RULE_VERSION,
    build_ai_optical_candidate_universe_from_universe_state,
    build_ai_optical_paper_sleeve_snapshot,
    build_ai_optical_replacement_value_report,
    empty_ai_optical_paper_state,
)


def _rows(start_price: float, step: float, *, days: int = 65) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = start_price + step * idx
        rows.append(
            {
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": round(close * 0.99, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.98, 4),
                "close": round(close, 4),
                "volume": 1_000_000,
            }
        )
    return rows


def _signal(ticker: str = "CIEN") -> dict:
    return {
        "ticker": ticker,
        "strategy": "trend_long",
        "entry_price": 50.0,
        "stop_price": 45.0,
        "target_price": 60.0,
        "confidence_score": 0.93,
        "trade_quality_score": 0.88,
        "risk_reward_ratio": 2.0,
        "exec_lag_adj_net_rr": 1.5,
    }


def _drop_date(rows: list[dict], as_of: str) -> list[dict]:
    return [row for row in rows if row["date"] != as_of]


def test_universe_state_feed_selects_governed_optical_without_noise():
    universe_state = {
        "as_of": "2026-05-22",
        "artifact_path": "data/daily/universe/universe_state_20260522.json",
        "observation_universe": ["AAOI", "COHR", "CRDO", "SNDK", "BAD", "CORE"],
        "records": {
            "AAOI": {
                "ticker": "AAOI",
                "status": "research",
                "theme": "ai_optical_connectivity",
                "theme_segment": "optical_connectivity",
                "history_class": "full_history",
                "liquidity_tier": "watch",
            },
            "COHR": {
                "ticker": "COHR",
                "status": "pilot",
                "theme": "ai_optical_connectivity",
                "theme_segment": "optical_connectivity",
                "history_class": "full_history",
                "liquidity_tier": "ok",
            },
            "CRDO": {
                "ticker": "CRDO",
                "status": "research",
                "theme": "ai_optical_connectivity",
                "theme_segment": "optical_connectivity",
                "history_class": "full_history",
                "liquidity_tier": "ok",
            },
            "SNDK": {
                "ticker": "SNDK",
                "status": "research",
                "theme": "ai_compute_memory",
                "theme_segment": "compute_memory_semis",
                "history_class": "full_history",
                "liquidity_tier": "ok",
            },
            "BAD": {
                "ticker": "BAD",
                "status": "quarantine",
                "theme": "ai_optical_connectivity",
                "theme_segment": "optical_connectivity",
                "history_class": "full_history",
                "liquidity_tier": "watch",
            },
        },
    }

    feed = build_ai_optical_candidate_universe_from_universe_state(
        universe_state,
        current_core_universe={"CORE", "CRDO"},
    )

    assert feed["status"] == "universe_state_ai_optical_feed"
    assert feed["rule_version"] == UNIVERSE_STATE_FEED_RULE_VERSION
    assert feed["tickers"] == ["AAOI", "COHR"]
    assert feed["records"]["AAOI"]["feed_rule_version"] == UNIVERSE_STATE_FEED_RULE_VERSION
    assert feed["excluded_count"] == 4


def test_prep_runs_signal_chain_and_preserves_core_dropped_signals(monkeypatch):
    """prep_and_build runs the core signal chain over the sleeve's own universe,
    but must restore risk_engine.last_dropped_signals so the core run's
    enrichment audit (logged separately by run.py) is left untouched."""
    import pandas as pd

    # Resolve the same module objects the prep imports internally (mirror its
    # bare-first / quant-fallback order) so monkeypatching hits what it calls.
    try:
        import ai_optical_paper_sleeve as aos
        import signal_engine
        import risk_engine
        import production_parity
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant import ai_optical_paper_sleeve as aos
        from quant import signal_engine, risk_engine, production_parity

    sentinel = [{"ticker": "CORE", "reason": "core_enrichment_drop"}]
    risk_engine.last_dropped_signals.clear()
    risk_engine.last_dropped_signals.extend(sentinel)

    captured: dict = {}

    def fake_generate_signals(features, **kwargs):
        captured["generated_for"] = sorted(features)
        return [_signal("AAOI")]

    def fake_enrich(signals, context, **kwargs):
        # real enrich_signals clobbers last_dropped_signals in place
        risk_engine.last_dropped_signals.clear()
        risk_engine.last_dropped_signals.append({"ticker": "AAOI", "reason": "sleeve_drop"})
        return signals

    def fake_filter(signals, **kwargs):
        return signals, {}

    def fake_build(**kwargs):
        captured["candidate_signals"] = kwargs.get("candidate_signals")
        return {"sleeve": "ai_optical", "candidate_count": len(kwargs.get("candidate_signals") or [])}

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate_signals)
    monkeypatch.setattr(risk_engine, "enrich_signals", fake_enrich)
    monkeypatch.setattr(production_parity, "filter_entry_signal_candidates", fake_filter)
    monkeypatch.setattr(aos, "build_ai_optical_paper_sleeve_snapshot", fake_build)

    frame = pd.DataFrame(
        {"Open": [9.9, 10.1], "High": [10.2, 10.4], "Low": [9.8, 10.0],
         "Close": [10.0, 10.3], "Volume": [1_000_000, 1_100_000]}
    )
    universe_state = {
        "as_of": "2026-05-22",
        "observation_universe": ["AAOI"],
        "records": {
            "AAOI": {
                "ticker": "AAOI", "status": "research",
                "theme": "ai_optical_connectivity", "theme_segment": "optical_connectivity",
                "history_class": "full_history", "liquidity_tier": "ok",
            }
        },
    }

    try:
        snapshot = aos.prep_and_build_ai_optical_paper_sleeve_snapshot(
            as_of="2026-05-22",
            universe_governance_state=universe_state,
            universe_state_artifact_path="data/daily/universe/universe_state_20260522.json",
            core_universe={"CORE"},
            ohlcv_dict={"AAOI": frame, "IWM": frame, "SPY": frame},
            features_by_ticker={"AAOI": {"close": 10.3, "atr": 0.5}},
            enabled_strategies=["trend_long"],
            atr_target_mult=2.0,
            open_positions={},
            current_prices={},
            open_prices={},
        )

        # signal chain ran over the sleeve universe and fed the builder
        assert captured["generated_for"] == ["AAOI"]
        assert captured["candidate_signals"] == [_signal("AAOI")]
        assert snapshot["candidate_count"] == 1
        # core run's dropped-signal accounting was restored after sleeve enrichment
        assert risk_engine.last_dropped_signals == sentinel
    finally:
        risk_engine.last_dropped_signals.clear()


def test_snapshot_adds_candidate_only_when_iwm_leads_spy():
    spy_rows = _rows(100.0, 0.05)
    iwm_rows = _rows(100.0, 0.25)
    cien_rows = _rows(50.0, 0.15)
    as_of = spy_rows[60]["date"]

    snapshot = build_ai_optical_paper_sleeve_snapshot(
        as_of=as_of,
        candidate_signals=[_signal()],
        ohlcv_by_ticker={"SPY": spy_rows, "IWM": iwm_rows, "CIEN": cien_rows},
        candidate_universe={
            "status": "provided",
            "tickers": ["CIEN"],
            "records": {
                "CIEN": {
                    "ticker": "CIEN",
                    "status": "research",
                    "theme": "ai_optical_connectivity",
                    "theme_segment": "optical_connectivity",
                    "history_class": "full_history",
                    "liquidity_tier": "ok",
                }
            },
        },
        state=empty_ai_optical_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["pending_count"] == 1
    assert snapshot["market_confirmation"]["passed"] is True
    assert snapshot["candidates"][0]["rule_version"] == RULE_VERSION
    assert snapshot["candidates"][0]["market_confirmation_rule_version"] == MARKET_CONFIRMATION_RULE_VERSION
    assert snapshot["candidates"][0]["intended_notional"] == 10_000.0
    assert snapshot["production_impact"]["alters_orders"] is False


def test_snapshot_rejects_candidate_when_iwm_lags_spy():
    spy_rows = _rows(100.0, 0.25)
    iwm_rows = _rows(100.0, 0.05)
    cien_rows = _rows(50.0, 0.15)
    as_of = spy_rows[60]["date"]

    snapshot = build_ai_optical_paper_sleeve_snapshot(
        as_of=as_of,
        candidate_signals=[_signal()],
        ohlcv_by_ticker={"SPY": spy_rows, "IWM": iwm_rows, "CIEN": cien_rows},
        candidate_universe=["CIEN"],
        state=empty_ai_optical_paper_state(),
        persist=False,
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["rejected_candidate_count"] == 1
    assert snapshot["market_confirmation"]["passed"] is False
    assert "iwm_spy_confirmation_failed" in snapshot["rejected_candidates"][0]["reasons"]
    assert snapshot["production_impact"]["trade_enabled"] is False


def test_snapshot_fills_next_session_and_closes_target_without_orders():
    spy_rows = _rows(100.0, 0.05, days=67)
    iwm_rows = _rows(100.0, 0.25, days=67)
    cien_rows = _rows(50.0, 0.15, days=67)
    first = build_ai_optical_paper_sleeve_snapshot(
        as_of=spy_rows[60]["date"],
        candidate_signals=[_signal()],
        ohlcv_by_ticker={"SPY": spy_rows, "IWM": iwm_rows, "CIEN": cien_rows},
        candidate_universe=["CIEN"],
        state=empty_ai_optical_paper_state(),
        persist=False,
    )

    state = empty_ai_optical_paper_state()
    state["pending_entries"] = first["pending_entries"]
    second = build_ai_optical_paper_sleeve_snapshot(
        as_of=spy_rows[61]["date"],
        candidate_signals=[],
        ohlcv_by_ticker={"SPY": spy_rows, "IWM": iwm_rows, "CIEN": cien_rows},
        candidate_universe=["CIEN"],
        state=state,
        open_prices={"CIEN": 50.25},
        current_prices={"CIEN": 50.75},
        persist=False,
    )
    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["trade_enabled"] is False

    close_state = empty_ai_optical_paper_state()
    close_state["open_positions"] = second["open_positions"]
    third = build_ai_optical_paper_sleeve_snapshot(
        as_of=spy_rows[62]["date"],
        candidate_signals=[],
        ohlcv_by_ticker={"SPY": spy_rows, "IWM": iwm_rows, "CIEN": cien_rows},
        candidate_universe=["CIEN"],
        state=close_state,
        current_prices={"CIEN": 61.0},
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["closed_positions_today"][0]["exit_reason"] == "target_close_reached"
    assert third["realized_pnl_to_date"] > 0
    assert third["replacement_value_report"]["rule_version"] == REPLACEMENT_VALUE_RULE_VERSION


def test_snapshot_does_not_use_stale_prices_when_asof_ohlcv_is_missing():
    spy_rows = _rows(100.0, 0.05, days=67)
    iwm_rows = _rows(100.0, 0.25, days=67)
    cien_rows = _rows(50.0, 0.15, days=67)
    as_of = spy_rows[61]["date"]
    previous = spy_rows[60]["date"]
    state = empty_ai_optical_paper_state()
    state["pending_entries"] = [
        {
            "decision_id": "pending-cien",
            "ticker": "CIEN",
            "created_asof": previous,
            "status": "pending_next_session_open",
            "intended_notional": 10_000.0,
            "candidate": _signal(),
        }
    ]
    state["open_positions"] = [
        {
            "decision_id": "open-cien",
            "ticker": "CIEN",
            "entry_date": previous,
            "entry_price": 50.0,
            "notional": 10_000.0,
            "observed_trading_days": 19,
            "target_price": 60.0,
            "stop_price": 45.0,
        }
    ]

    snapshot = build_ai_optical_paper_sleeve_snapshot(
        as_of=as_of,
        candidate_signals=[_signal()],
        ohlcv_by_ticker={
            "SPY": _drop_date(spy_rows, as_of),
            "IWM": _drop_date(iwm_rows, as_of),
            "CIEN": _drop_date(cien_rows, as_of),
        },
        candidate_universe=["CIEN"],
        state=state,
        open_prices={"CIEN": cien_rows[60]["open"]},
        current_prices={"CIEN": 61.0},
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["new_pending_count"] == 0
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 1
    assert snapshot["open_positions"][0]["observed_trading_days"] == 19


def test_replacement_value_report_tracks_cash_slot_ledger():
    report = build_ai_optical_replacement_value_report(
        candidates=[{"ticker": "CIEN"}],
        pending_entries=[{"ticker": "CIEN"}],
        open_positions=[{"ticker": "AAOI", "unrealized_pnl": 125.5}],
        closed_positions=[
            {"ticker": "CIEN", "pnl": 200.0},
            {"ticker": "LOSS", "pnl": -50.0},
        ],
        skipped_entries=[{"ticker": "SKIP"}],
    )

    assert report["read_only"] is True
    assert report["closed_count"] == 2
    assert report["closed_pnl"] == 150.0
    assert report["positive_closed_pnl"] == 200.0
    assert report["by_ticker"]["CIEN"]["positive_pnl_share"] == 1.0
    assert report["alters_orders"] is False
