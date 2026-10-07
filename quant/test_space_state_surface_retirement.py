from copy import deepcopy
from datetime import date, timedelta
import json

import event_sleeve_bundle as bundle
import space_catalyst_sleeve as space
import state_surface_sleeve as satellite


def test_satellite_retirement_cancels_pending_and_settles_existing_once(tmp_path):
    state = satellite.empty_state_surface_sleeve_state()
    pending = {"decision_id": "pending", "ticker": "BBB", "created_asof": "2026-09-09", "original": {"rank": 2}}
    state["pending_entries"] = [pending]
    state["open_positions"] = [{"decision_id": "open", "ticker": "AAA", "entry_date": "2026-09-09", "entry_price": 10.0, "notional": 1000.0, "shares": 100.0, "observed_trading_days": 0, "last_seen_date": "2026-09-09"}]
    original = deepcopy(state)
    path = tmp_path / "state.json"
    snapshots = tmp_path / "snapshots.jsonl"
    kwargs = dict(state_surface_queue={"candidate_count": 1, "candidates": [{"decision_id": "new", "ticker": "CCC"}]}, as_of="2026-09-10", open_prices={"BBB": 10.0}, current_prices={"AAA": 11.0}, config={"hold_days": 1}, state_path=path, snapshot_log_path=snapshots)
    first = satellite.build_state_surface_sleeve_snapshot(state=state, **kwargs)
    saved = satellite.load_state_surface_sleeve_state(path)
    assert state == original
    assert first["retired"] is True
    assert first["build_status"] == "retired_default_off_paper_disabled"
    assert first["next_action"] == "settle_existing_positions_only"
    assert first["new_pending_count"] == first["filled_count"] == first["candidate_count"] == 0
    assert first["closed_count_today"] == 1
    enabled = satellite.build_state_surface_sleeve_snapshot(
        state=original, **{**kwargs, "config": {"hold_days": 1, "paper_enabled": True}, "persist": False}
    )
    assert first["closed_positions_today"] == enabled["closed_positions_today"]
    assert saved["pending_entries"] == []
    skipped = saved["skipped_entries"][0]
    assert all(skipped[key] == value for key, value in pending.items())
    assert skipped["skip_reason"] == "retired_default_off_paper_disabled"
    assert skipped["skipped_asof"] == "2026-09-10"
    second = satellite.build_state_surface_sleeve_snapshot(**kwargs)
    rerun = satellite.load_state_surface_sleeve_state(path)
    assert second["closed_count_today"] == second["skipped_count_today"] == 0
    assert rerun["closed_positions"] == saved["closed_positions"]
    assert rerun["skipped_entries"] == saved["skipped_entries"]


def test_satellite_retired_queue_does_not_score(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("retired queue must not score")
    monkeypatch.setattr(satellite, "_score_candidates_for_date", unexpected)
    result = satellite.build_state_surface_queue(as_of="2026-09-10", ohlcv_by_ticker={})
    assert result["retired"] is True
    assert result["candidates"] == []


def test_space_retirement_never_evaluates_new_plan_or_seed(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("retired path must not evaluate strategy or seeds")
    monkeypatch.setattr(space, "space_catalyst_forward_risk_scalar", unexpected)
    monkeypatch.setattr(space, "load_space_catalyst_event_seeds", unexpected)
    result = space.build_space_catalyst_observation_slot(as_of="2026-09-10", candidate_signals=[{"ticker": "LUNR"}])
    empty = space.empty_space_catalyst_observation_slot("2026-09-10", "retired_default_off_paper_disabled")
    for snapshot in (result, empty):
        assert snapshot["retired"] is True
        assert snapshot["enabled"] is False
        assert not snapshot["forward_hypothesis"]
        assert snapshot["blocked_trade_plans"] == []


def _space_rows():
    start = date(2026, 8, 3)
    dates = [start + timedelta(days=idx) for idx in range(50)]
    dates = [day.isoformat() for day in dates if day.weekday() < 5][:23]
    bars = [{"date": day, "close": 100.0 + idx} for idx, day in enumerate(dates)]
    return dates, {"LUNR": bars, "SPY": bars, "QQQ": bars, "ARKX": bars, "UFO": bars}


def test_space_settlement_only_registered_pairs_preserves_mature_horizons(tmp_path, monkeypatch):
    dates, prices = _space_rows()
    initial = space.build_space_catalyst_event_ledger_snapshot(as_of=dates[11], events=[{"event_id": "old", "event_date": dates[0], "tickers": ["LUNR"], "semantic_bucket": "contract", "event_fields": ["customer_win"]}], ohlcv_by_ticker=prices, space_catalyst_shadow={"forward_hypothesis": {"included_tickers": ["LUNR"]}})
    old = initial["event_rows"][0]
    assert old["closed_decision"] is True
    assert old["horizons"]["20d"]["status"] == "pending"
    old["logged_at"] = "2026-09-10T20:00:00Z"
    late = {**old, "event_id": "unregistered", "ticker": "NEW", "logged_at": "2026-09-12T00:00:00Z"}
    missing_clock = {**old, "event_id": "no_clock", "ticker": "UNKNOWN", "logged_at": None}
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in [old, late, missing_clock]), encoding="utf-8")
    before = ledger.read_bytes()
    def unexpected(*args, **kwargs):
        raise AssertionError("retired settlement must not read seed file")
    monkeypatch.setattr(space, "load_space_catalyst_event_seeds", unexpected)
    assert "NEW" not in space.retired_space_catalyst_event_tickers(ledger_path=ledger)
    assert "UNKNOWN" not in space.retired_space_catalyst_event_tickers(ledger_path=ledger)
    partial = space.build_retired_space_catalyst_event_ledger_snapshot(as_of=dates[11], ohlcv_by_ticker=prices, ledger_path=ledger)
    assert partial["pending_decision_count"] == 1
    summary_path = tmp_path / "summary.json"
    space.persist_space_catalyst_event_ledger(partial, ledger_path=ledger, summary_path=summary_path)
    standard = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert len(standard["pending_entries"]) == 1
    result = space.build_retired_space_catalyst_event_ledger_snapshot(as_of=dates[-1], ohlcv_by_ticker=prices, ledger_path=ledger)
    assert ledger.read_bytes() == before
    assert result["retired"] is True
    assert result["event_row_count"] == 1
    settled = result["event_rows"][0]
    assert settled["event_id"] == "old"
    assert settled["horizons"]["10d"] == old["horizons"]["10d"]
    assert settled["horizons"]["20d"]["status"] == "mature"
    assert settled["outcome_status"] == "mature"
    assert result["promotion_gate"]["passed"] is False
    first = space.persist_space_catalyst_event_ledger(result, ledger_path=ledger, summary_path=summary_path)
    assert ledger.read_bytes().startswith(before)
    assert first["persistence"]["appended_count"] == 1
    standard = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert standard["pending_entries"] == []
    assert space.retired_space_catalyst_event_tickers(ledger_path=ledger) == []
    second = space.build_retired_space_catalyst_event_ledger_snapshot(as_of="2026-09-12", ohlcv_by_ticker=prices, ledger_path=ledger)
    assert second["event_rows"][0]["horizons"] == settled["horizons"]
    repeated = space.persist_space_catalyst_event_ledger(second, ledger_path=ledger, summary_path=summary_path)
    assert repeated["persistence"]["appended_count"] == 0


def test_event_bundle_only_retires_state_surface_addon():
    candidate = {"ticker": "LUNR", "event_notional_usd": 10000.0, "source": "form4"}
    queue = {"scored_candidates": [{"ticker": "LUNR", "score": 1.0, "surface": "rotation_breakout_leadership", "state_rank_pct": 0.1}]}
    current = bundle.apply_state_surface_addon_to_event_candidates([candidate], state_surface_queue=queue)
    historical = bundle.apply_state_surface_addon_to_event_candidates([candidate], state_surface_queue=queue, config={"state_surface_addon_paper_enabled": True})
    assert current[0]["paper_event_notional_usd"] == 10000.0
    assert historical[0]["paper_event_notional_usd"] > 10000.0
    summary = bundle._state_surface_addon_summary(current, state_surface_queue=queue, config=bundle.DEFAULT_CONFIG)
    assert summary["retired"] is True
    assert bundle.DEFAULT_CONFIG["paper_enabled"] is True
    assert bundle.DEFAULT_CONFIG["event_source_quality_tilt_enabled"] is True
