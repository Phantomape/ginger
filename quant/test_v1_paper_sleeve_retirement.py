"""Owner-authorized retirement: synthetic lifecycle checks, no market replay."""

from copy import deepcopy
from importlib import import_module

import pytest


SPECS = [
    ("ai_optical", "build_ai_optical_paper_sleeve_snapshot", "empty_ai_optical_paper_state", "load_ai_optical_paper_state", "_build_ai_optical_candidates"),
    ("alpha_score_market_regime", "build_alpha_score_market_regime_paper_sleeve_snapshot", "empty_alpha_score_market_regime_paper_state", "load_alpha_score_market_regime_paper_state", "build_alpha_score_market_regime_candidates"),
    ("accepted_source_consensus", "build_accepted_source_consensus_paper_sleeve_snapshot", "empty_accepted_source_consensus_paper_state", "load_accepted_source_consensus_paper_state", "build_alpha_score_market_regime_candidates"),
    ("free_data_cross_source_consensus", "build_free_data_cross_source_consensus_paper_sleeve_snapshot", "empty_free_data_cross_source_consensus_paper_state", "load_free_data_cross_source_consensus_paper_state", "_consensus_candidates"),
    ("accepted_helper_source_priority_allocator", "build_accepted_helper_source_priority_allocator_snapshot", "empty_accepted_helper_source_priority_allocator_state", "load_accepted_helper_source_priority_allocator_state", "source_rows_from_snapshots"),
    ("industry_relative_laggard_repair", "build_industry_relative_laggard_repair_paper_sleeve_snapshot", "empty_industry_relative_laggard_repair_paper_state", "load_industry_relative_laggard_repair_paper_state", "build_industry_relative_laggard_repair_candidate_rows"),
]


def _forbidden(*args, **kwargs):
    raise AssertionError("retired strategy must not generate candidates or fill pending")


def _prices():
    rows = [
        {"date": day, "open": 100.0, "high": 106.0, "low": 99.0, "close": 105.0, "volume": 1_000_000}
        for day in ("2026-09-08", "2026-09-09", "2026-09-10")
    ]
    return {ticker: deepcopy(rows) for ticker in ("SPY", "IWM", "DUE", "KEEP", "NEW")}


@pytest.mark.parametrize("spec", SPECS, ids=[spec[0] for spec in SPECS])
def test_retirement_cancels_pending_preserves_and_settles_existing_positions(spec, monkeypatch, tmp_path):
    name, builder_name, empty_name, loader_name, candidate_name = spec
    module = import_module(f"quant.{name}_paper_sleeve")
    state = getattr(module, empty_name)()
    original_pending = {
        "decision_id": "pending", "ticker": "NEW", "created_asof": "2026-09-09",
        "signal_date": "2026-09-09", "notional": 1000.0, "notional_usd": 1000.0,
        "paper_notional_usd": 1000.0, "status": "pending_next_open", "source_note": "retain me",
        "reason": "original_pending_reason",
    }
    state["pending_entries"] = [deepcopy(original_pending)]
    for ticker, observed in (("DUE", module.DEFAULT_CONFIG["hold_days"] - 1), ("KEEP", 0)):
        state["open_positions"].append({
            "decision_id": ticker, "ticker": ticker, "entry_date": "2026-09-08",
            "entry_price": 100.0, "notional": 1000.0, "notional_usd": 1000.0,
            "paper_notional_usd": 1000.0, "observed_trading_days": observed,
            "last_observed_date": "2026-09-09", "last_price_asof": "2026-09-09",
            "status": "open", "paper_status": "open",
        })
    prior_closed = {"decision_id": "prior", "ticker": "OLD", "entry_date": "2026-09-01", "exit_date": "2026-09-02", "pnl": 17.0}
    state["closed_positions"] = [deepcopy(prior_closed)]
    monkeypatch.setattr(module, candidate_name, _forbidden)
    if name == "accepted_helper_source_priority_allocator":
        monkeypatch.setattr(module.leader, "_fill_pending_entries", _forbidden)
    else:
        monkeypatch.setattr(module, "_fill_pending_entries", _forbidden)
    kwargs = {"as_of": "2026-09-10", "ohlcv_by_ticker": _prices(), "state": state,
              "state_path": tmp_path / "state.json", "snapshot_log_path": tmp_path / "snapshots.jsonl"}
    if name == "accepted_helper_source_priority_allocator":
        kwargs["source_snapshots"] = None
    snapshot = getattr(module, builder_name)(**kwargs)
    saved = getattr(module, loader_name)(kwargs["state_path"])
    assert snapshot["retired"] is True
    assert snapshot["build_status"] == "retired_default_off_paper_disabled"
    assert snapshot["next_action"] == "settle_existing_positions_only"
    assert snapshot["paper_enabled"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["forward_paper_gate"]["passed"] is False
    assert snapshot["candidate_count"] == snapshot["new_pending_count"] == 0
    assert snapshot.get("filled_count", 0) == 0
    assert saved["pending_entries"] == []
    assert [row["ticker"] for row in saved["open_positions"]] == ["KEEP"]
    assert all(saved["closed_positions"][0][key] == value for key, value in prior_closed.items())
    assert saved["closed_positions"][1]["decision_id"] == "DUE"
    skip_key = "skipped_days" if name == "accepted_helper_source_priority_allocator" else "skipped_entries"
    cancelled = saved[skip_key][0]
    assert cancelled["source_note"] == "retain me"
    assert cancelled["paper_notional_usd"] == original_pending["paper_notional_usd"]
    assert cancelled["decision_id"] == "pending"
    assert cancelled["skipped_asof"] == "2026-09-10"
    assert cancelled["status"] == "skipped_retired"
    assert cancelled["prior_status"] == original_pending["status"]
    assert cancelled["prior_reason"] == original_pending["reason"]
    before = deepcopy(saved)
    kwargs["state"] = saved
    repeated = getattr(module, builder_name)(**kwargs)
    again = getattr(module, loader_name)(kwargs["state_path"])
    for key in ("pending_entries", "open_positions", "closed_positions", skip_key):
        assert again[key] == before[key]
    assert repeated["closed_count_today"] == 0


def test_ai_retired_prep_fetches_only_existing_position_and_benchmark(monkeypatch):
    from quant import ai_optical_paper_sleeve as module
    import signal_engine

    state = module.empty_ai_optical_paper_state()
    state["open_positions"] = [{"ticker": "OLD_OPTICAL"}]
    monkeypatch.setattr(module, "load_ai_optical_paper_state", lambda *args: state)
    monkeypatch.setattr(signal_engine, "generate_signals", _forbidden)
    seen = []
    captured = {}

    def fetch(ticker):
        seen.append(ticker)
        return _prices()["SPY"]

    def build(**kwargs):
        captured.update(kwargs)
        return {"retired": True}

    monkeypatch.setattr(module, "build_ai_optical_paper_sleeve_snapshot", build)
    result = module.prep_and_build_ai_optical_paper_sleeve_snapshot(
        as_of="2026-09-10", cached_ohlcv_fn=fetch,
        universe_governance_state={"observation_universe": ["NEW_OPTICAL"]},
    )
    assert result["retired"] is True
    assert set(seen) == {"OLD_OPTICAL", "SPY"}
    assert captured["candidate_signals"] == []


@pytest.mark.parametrize("spec", SPECS, ids=[spec[0] for spec in SPECS])
def test_retired_empty_snapshot_keeps_failure_reason_and_blocks_promotion(spec):
    module = import_module(f"quant.{spec[0]}_paper_sleeve")
    empty = next(value for name, value in vars(module).items()
                 if name.startswith("empty_") and name.endswith("snapshot"))
    snapshot = empty("2026-09-10", "price_refresh_failed")
    assert snapshot["retired"] is True
    assert snapshot["build_status"] == "retired_default_off_paper_disabled"
    assert snapshot["error"] == "price_refresh_failed"
    assert snapshot["forward_paper_gate"]["passed"] is False
