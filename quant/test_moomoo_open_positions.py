"""Tests for the moomoo-backed open_positions generator (pure transforms)."""

from __future__ import annotations

import moomoo_open_positions as M


def test_strip_market():
    assert M._strip_market("US.NVDA") == "NVDA"
    assert M._strip_market("AAPL") == "AAPL"
    assert M._strip_market("hk.00700") == "00700"
    assert M._strip_market(None) == ""


def test_reconstruct_entry_dates_open_add_close_reopen():
    fills = [
        {"ticker": "US.AAPL", "side": "BUY", "qty": 10, "date": "2025-01-01"},
        {"ticker": "US.AAPL", "side": "BUY", "qty": 5, "date": "2025-02-01"},   # add: keep lot date
        {"ticker": "US.AAPL", "side": "SELL", "qty": 15, "date": "2025-03-01"}, # close
        {"ticker": "US.AAPL", "side": "BUY", "qty": 8, "date": "2025-04-01"},   # reopen
        {"ticker": "US.MSFT", "side": "BUY", "qty": 3, "date": "2025-01-15"},
        {"ticker": "US.TSLA", "side": "BUY", "qty": 4, "date": "2025-01-10"},
        {"ticker": "US.TSLA", "side": "SELL", "qty": 4, "date": "2025-01-20"},  # fully closed
    ]
    out = M.reconstruct_entry_dates(fills)
    assert out["AAPL"] == "2025-04-01"   # latest open lot, not the original add
    assert out["MSFT"] == "2025-01-15"
    assert "TSLA" not in out             # flat -> excluded


def test_load_tag_map_forms(tmp_path):
    import json
    p = tmp_path / "tags.json"
    p.write_text(json.dumps({"tags": {
        "US.NVDA": {"type": "sleeve", "sleeve": "distribution"},
        "AAPL": "core",
    }}), encoding="utf-8")
    tm = M.load_tag_map(p)
    assert tm["NVDA"] == {"type": "sleeve", "sleeve": "distribution"}
    assert tm["AAPL"] == {"type": "core"}


def _positions():
    return [
        {"code": "US.COHR", "qty": 19, "average_cost": 377.418, "nominal_price": 389.0,
         "position_side": "LONG", "market_val": 7391.0, "unrealized_pl": 218.0, "position_id": 1},
        {"code": "US.NVDA", "qty": 31, "average_cost": 70.296, "nominal_price": 210.69,
         "position_side": "LONG", "market_val": 6531.39, "unrealized_pl": 4350.0, "position_id": 2},
        {"code": "US.META", "qty": 9, "average_cost": 701.256, "nominal_price": 577.0,
         "position_side": "LONG", "market_val": 5193.0, "unrealized_pl": -1117.0, "position_id": 3},
        {"code": "US.RKLZ", "qty": 500, "average_cost": 2.94, "nominal_price": 2.67,
         "position_side": "LONG", "market_val": 1335.0, "unrealized_pl": -135.0, "position_id": 4},
        {"code": "US.ZERO", "qty": 0, "average_cost": 10.0, "nominal_price": 9.0,
         "position_side": "LONG"},  # closed -> skipped
    ]


def _tag_map():
    return {
        "COHR": {"type": "core", "sleeve": "core_strategy", "opened_by_strategy": "pilot_breakout_long"},
        "NVDA": {"type": "sleeve", "sleeve": "distribution_day_absorption_leadership"},
        "META": {"type": "legacy"},
        # RKLZ intentionally untagged
    }


def test_build_payload_sections_and_slot_policy():
    account = {"total_assets": 75305.59, "cash": 9429.23, "market_val": 65876.35}
    payload, untagged = M.build_payload(
        _positions(), account,
        entry_dates={"NVDA": "2026-04-29"}, atr_by_ticker={},
        tag_map=_tag_map(), prior_payload=None, as_of="2026-06-20",
    )
    core = {r["ticker"] for r in payload["core_positions"]}
    pos = {r["ticker"] for r in payload["positions"]}
    obs = {r["ticker"] for r in payload["observations"]}
    assert core == {"COHR"}
    assert pos == {"NVDA", "RKLZ"}        # RKLZ untagged -> default sleeve section
    assert obs == {"META"}
    assert "ZERO" not in (core | pos | obs)  # zero-qty skipped
    assert untagged == ["RKLZ"]
    assert payload["untagged_tickers"] == ["RKLZ"]

    cohr = payload["core_positions"][0]
    assert cohr["slot_policy"] == "consumes_core_slot"
    assert cohr["opened_by_strategy"] == "pilot_breakout_long"
    nvda = next(r for r in payload["positions"] if r["ticker"] == "NVDA")
    assert nvda["slot_policy"] == "no_core_slot"
    assert nvda["sleeve"] == "distribution_day_absorption_leadership"
    assert nvda["entry_date"] == "2026-04-29"

    # account-level USD fields come straight from moomoo
    assert payload["portfolio_value_usd"] == 75305.59
    assert payload["cash_usd"] == 9429.23
    assert payload["currency"] == "USD"
    assert payload["account"].endswith("futusg")


def test_build_payload_auto_target_stop_and_overrides():
    pos = [{"code": "US.NVDA", "qty": 31, "average_cost": 100.0, "nominal_price": 200.0,
            "position_side": "LONG"}]
    # auto: target = profit target above avg_cost; stop = ATR stop below current price
    payload, _ = M.build_payload(
        pos, {}, entry_dates={}, atr_by_ticker={"NVDA": 5.0},
        tag_map={"NVDA": {"type": "sleeve", "sleeve": "x"}}, prior_payload=None,
    )
    row = payload["positions"][0]
    assert row["target_price"] > 100.0          # profit target above cost
    assert row["stop_price"] < 200.0            # ATR stop below current price
    assert row["stop_price"] is not None

    # tag override wins over auto
    payload2, _ = M.build_payload(
        pos, {}, entry_dates={}, atr_by_ticker={"NVDA": 5.0},
        tag_map={"NVDA": {"type": "sleeve", "sleeve": "x",
                          "target_price": 333.0, "stop_price": 150.0}},
        prior_payload=None,
    )
    r2 = payload2["positions"][0]
    assert r2["target_price"] == 333.0
    assert r2["stop_price"] == 150.0


def test_build_payload_prior_fallback_for_entry_and_notes():
    pos = [{"code": "US.APP", "qty": 8, "average_cost": 174.7, "nominal_price": 350.0,
            "position_side": "LONG"}]
    prior = {"observations": [{"ticker": "APP", "entry_date": "2025-02-13",
                              "risk_notes": "legacy hold", "opened_by_strategy": "legacy"}]}
    payload, _ = M.build_payload(
        pos, {}, entry_dates={}, atr_by_ticker={},  # no fresh entry date
        tag_map={"APP": {"type": "legacy"}}, prior_payload=prior,
    )
    row = payload["observations"][0]
    assert row["entry_date"] == "2025-02-13"     # preserved from prior file
    assert row["risk_notes"] == "legacy hold"


def test_compute_target_stop_guards():
    assert M.compute_target_stop(None, 10.0, 1.0) == (None, None)
    assert M.compute_target_stop(0, 10.0, 1.0) == (None, None)
    target, stop = M.compute_target_stop(100.0, 120.0, 4.0)
    assert target > 100.0 and stop is not None
