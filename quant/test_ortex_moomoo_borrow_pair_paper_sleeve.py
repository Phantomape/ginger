from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import date, timedelta

import pytest

from quant import ortex_moomoo_borrow_pair_paper_sleeve as sleeve


def _sessions(count: int = 70) -> list[str]:
    current = date(2025, 1, 2)
    result = []
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _bars(sessions: list[str]) -> dict[str, list[dict]]:
    result = {}
    for ticker_index, ticker in enumerate((*sleeve.FIXED_TICKERS, "SPY")):
        close = 80.0 + ticker_index
        rows = []
        for index, day in enumerate(sessions):
            common = ((index % 7) - 3) * 0.001
            own = ((index + ticker_index) % 3 - 1) * 0.00008
            close *= 1.0 + common + own + 0.0005
            rows.append(
                {
                    "date": day,
                    "open": close * (1.0 - 0.0002),
                    "close": close,
                }
            )
        result[ticker] = rows
    return result


def _source_rows(source_date: str, usable_date: str):
    # Top four agree.  AAPL is highest combined stress; AMZN is the lowest
    # stress same-cluster peer and therefore the deterministic long.
    descending = list(sleeve.FIXED_TICKERS)
    ortex = []
    moomoo = []
    for index, ticker in enumerate(descending):
        score = -0.02 if index == len(descending) - 1 else 20 - index
        short_score = 20 - index
        ortex.append(
            {
                "ticker": ticker,
                "provider_date": source_date,
                "usable_trade_date": usable_date,
                "cost_to_borrow_new_pct": score,
            }
        )
        moomoo.append(
            {
                "ticker": ticker,
                "activity_date": source_date,
                "usable_trade_date": None,
                "short_volume_ratio": short_score / 100.0,
            }
        )
    return ortex, moomoo


def _fixture():
    sessions = _sessions()
    bars = _bars(sessions)
    source_index = 30
    source_date = sessions[source_index]
    usable_date = sessions[source_index + 1]
    ortex, moomoo = _source_rows(source_date, usable_date)
    return sessions, bars, source_index, source_date, usable_date, ortex, moomoo


def test_exact_join_rank_and_peer_selection_with_strict_next_session():
    sessions, bars, _, source_date, usable_date, ortex, moomoo = _fixture()
    joined, audit = sleeve.build_joined_ranked_source_days(ortex, moomoo, sessions)

    assert list(joined) == [source_date]
    day = joined[source_date]
    assert day["usable_trade_date"] == usable_date
    assert [row["ticker"] for row in day["candidates"]] == ["AAPL", "MSFT", "META", "GOOG"]
    assert day["candidates"][0]["combined_stress_rank_score"] == 40
    assert audit["joined_source_rows"] == 20
    assert audit["exact_date_join_only"] == 1
    assert audit["no_carry_forward"] == 1

    replay = sleeve.replay_ortex_moomoo_borrow_pair_sleeve(
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        windows={"fixture": {"start": sessions[0], "end": sessions[-1]}},
    )
    trade = replay["windows"]["fixture"]["trades"][0]
    assert trade["short_ticker"] == "AAPL"
    assert trade["long_ticker"] == "AMZN"
    assert trade["entry_date"] == usable_date
    assert trade["strict_prior_20d_correlation"] >= 0.20


def test_off_calendar_and_nonexact_source_dates_are_dropped_without_carry_forward():
    sessions, _, _, source_date, usable_date, ortex, moomoo = _fixture()
    holiday = "2025-01-01"
    holiday_ortex, _ = _source_rows(holiday, sessions[0])
    joined, audit = sleeve.build_joined_ranked_source_days(
        [*ortex, *holiday_ortex], moomoo, sessions
    )
    assert list(joined) == [source_date]
    # Holiday has no same-day Moomoo row, so it is absent rather than carried.
    assert audit["joined_source_dates"] == 1

    shifted = [{**row, "activity_date": usable_date} for row in moomoo]
    joined_shifted, _ = sleeve.build_joined_ranked_source_days(ortex, shifted, sessions)
    assert joined_shifted == {}


def test_replay_cost_borrow_hold_cash_gross_and_daily_equity_contract():
    sessions, bars, source_index, _, _, ortex, moomoo = _fixture()
    result = sleeve.replay_ortex_moomoo_borrow_pair_sleeve(
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        windows={"fixture": {"start": sessions[0], "end": sessions[-1]}},
    )["windows"]["fixture"]
    assert result["signals_generated"] == 4
    assert result["signals_survived"] == 1
    assert math.isclose(result["survival_rate"], 0.25)
    trade = result["trades"][0]
    assert trade["exit_date"] == sessions[source_index + 1 + sleeve.HOLD_SESSIONS]
    assert trade["holding_sessions"] == sleeve.HOLD_SESSIONS
    assert math.isclose(trade["trade_cost_usd"], 9.0)
    expected_borrow = (
        1_000.0
        * trade["signal_ctb_new_pct"]
        / 100.0
        * trade["borrow_calendar_days_inclusive"]
        / 360.0
    )
    assert math.isclose(trade["borrow_cost_usd"], expected_borrow, abs_tol=1e-8)
    assert trade["entry_date"]
    assert "target_price" in trade
    assert result["summary"]["trade_count"] == 1
    assert math.isclose(result["summary"]["total_trade_cost_usd"], 9.0)
    assert result["audit"]["cash_nonnegative"] == 1
    assert result["audit"]["gross_lte_nav"] == 1
    assert all(row["cash_usd"] >= 0 for row in result["daily_equity"])
    assert all(row["gross_exposure_usd"] <= row["equity_usd"] for row in result["daily_equity"])
    assert all(
        row["gross_exposure_usd"] == row["marked_gross_market_value_usd"]
        for row in result["daily_equity"]
    )
    assert result["summary"]["min_cash_usd"] >= 0
    assert len(result["daily_equity"]) == len(result["daily_returns"])
    assert all("daily_pnl_usd" in row and "daily_return" in row for row in result["daily_equity"])


def test_correlation_uses_source_close_but_ignores_entry_and_future_mutations():
    sessions, bars, _, source_date, _, _, _ = _fixture()
    before = sleeve._strict_prior_corr("AAPL", "AMZN", source_date, sleeve._normalise_prices(bars))
    future_mutated = deepcopy(bars)
    for ticker in ("AAPL", "AMZN"):
        for row in future_mutated[ticker]:
            if row["date"] > source_date:
                row["close"] *= 10.0 if ticker == "AAPL" else 0.1
    after_future = sleeve._strict_prior_corr(
        "AAPL", "AMZN", source_date, sleeve._normalise_prices(future_mutated)
    )
    assert before == after_future

    source_mutated = deepcopy(bars)
    for ticker in ("AAPL", "AMZN"):
        for row in source_mutated[ticker]:
            if row["date"] == source_date:
                row["close"] *= 10.0 if ticker == "AAPL" else 0.1
    after_source = sleeve._strict_prior_corr(
        "AAPL", "AMZN", source_date, sleeve._normalise_prices(source_mutated)
    )
    assert not math.isclose(before, after_source)


def test_highest_ranked_short_failure_does_not_fallback_to_lower_rank():
    sessions, bars, _, _, usable_date, ortex, moomoo = _fixture()
    bars["AAPL"] = [row for row in bars["AAPL"] if row["date"] != usable_date]
    result = sleeve.replay_ortex_moomoo_borrow_pair_sleeve(
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        windows={"fixture": {"start": sessions[0], "end": sessions[-1]}},
    )["windows"]["fixture"]
    assert result["signals_generated"] == 4
    assert result["signals_survived"] == 0
    assert result["trades"] == []
    assert result["audit"]["missing_atomic_price_skips"] == 1


def test_marked_gross_not_allocated_notional_is_the_nav_guard():
    sessions, bars, source_index, _, _, ortex, moomoo = _fixture()
    entry_date = sessions[source_index + 1]
    for row in bars["AAPL"]:
        if row["date"] == entry_date:
            row["close"] = row["open"] * 20.0
    with pytest.raises(AssertionError, match="marked gross exceeded NAV"):
        sleeve.replay_ortex_moomoo_borrow_pair_sleeve(
            ortex_rows=ortex,
            moomoo_rows=moomoo,
            ohlcv_by_ticker=bars,
            windows={"fixture": {"start": sessions[0], "end": sessions[-1]}},
        )


def test_daily_snapshot_is_fresh_only_default_off_and_persistent_idempotent(tmp_path):
    sessions, bars, _, source_date, _, ortex, moomoo = _fixture()
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshots.jsonl"
    pair_path = tmp_path / "pairs.jsonl"
    first = sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=source_date,
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
        persist=True,
    )
    second = sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=source_date,
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
        persist=True,
    )
    assert first["status"] == "ready"
    assert first["candidate_count"] == 4
    assert first["selected_pair"]["short_ticker"] == "AAPL"
    assert len(first["new_pending_entries"]) == 1
    assert first["trade_enabled"] is False
    assert first["production_impact"]["alters_orders"] is False
    assert first["audit"]["old_source_rows_consumed"] == 0
    assert second["status"] == "idempotent"
    assert len(snapshot_path.read_text().splitlines()) == 1
    assert len(pair_path.read_text().splitlines()) == 1
    persisted = json.loads(state_path.read_text())
    assert len(persisted["pending_pairs"]) == 1

    later = sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=sessions[sessions.index(source_date) + 2],
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        state=sleeve.empty_ortex_moomoo_borrow_pair_state(),
        persist=False,
    )
    assert later["status"] == "no_fresh_exact_join"
    assert later["candidate_count"] == 0
    assert later["new_pending_entries"] == []


def test_daily_pending_fills_atomically_then_exits_on_entry_plus_five(tmp_path):
    sessions, bars, source_index, source_date, usable_date, ortex, moomoo = _fixture()
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshots.jsonl"
    pair_path = tmp_path / "pairs.jsonl"
    sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=source_date,
        ortex_rows=ortex,
        moomoo_rows=moomoo,
        ohlcv_by_ticker=bars,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
        persist=True,
    )
    entered = sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=usable_date,
        ortex_rows=[],
        moomoo_rows=[],
        ohlcv_by_ticker=bars,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
        persist=True,
    )
    assert len(entered["entered_pairs"]) == 1
    exit_date = sessions[source_index + 1 + sleeve.HOLD_SESSIONS]
    exited = sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=exit_date,
        ortex_rows=[],
        moomoo_rows=[],
        ohlcv_by_ticker=bars,
        state_path=state_path,
        snapshot_ledger_path=snapshot_path,
        pair_ledger_path=pair_path,
        persist=True,
    )
    assert len(exited["exited_pairs"]) == 1
    assert exited["exited_pairs"][0]["exit_date"] == exit_date
    assert exited["state_summary"]["open_pair_count"] == 0


def test_daily_entry_reuses_marked_gross_nav_guard():
    sessions, bars, source_index, _, _, _, _ = _fixture()
    prior_day = sessions[source_index]
    as_of = sessions[source_index + 1]
    aapl_prior = next(row for row in bars["AAPL"] if row["date"] == prior_day)
    amzn_prior = next(row for row in bars["AMZN"] if row["date"] == prior_day)
    aapl_now = next(row for row in bars["AAPL"] if row["date"] == as_of)
    aapl_now["open"] *= 20.0
    state = sleeve.empty_ortex_moomoo_borrow_pair_state()
    state["cash_usd"] = 7_995.5
    state["open_pairs"] = [
        {
            "pair_id": "existing",
            "entry_date": prior_day,
            "long_ticker": "AMZN",
            "short_ticker": "AAPL",
            "long_entry_open": amzn_prior["open"],
            "short_entry_open": aapl_prior["open"],
            "long_shares": 1_000.0 / amzn_prior["open"],
            "short_shares": 1_000.0 / aapl_prior["open"],
            "signal_ctb_new_pct": 1.0,
            "entry_trade_cost_usd": 4.5,
        }
    ]
    state["pending_pairs"] = [
        {
            "pair_id": "pending",
            "entry_date": as_of,
            "long_ticker": "MU",
            "short_ticker": "AMD",
            "signal_ctb_new_pct": 1.0,
            "trade_enabled": False,
        }
    ]
    snapshot = sleeve.build_ortex_moomoo_borrow_pair_paper_snapshot(
        as_of=as_of,
        ortex_rows=[],
        moomoo_rows=[],
        ohlcv_by_ticker=bars,
        state=state,
        persist=False,
    )
    assert snapshot["entered_pairs"] == []
    assert snapshot["audit"]["marked_gross_nav_entry_skips"] == 1
    assert snapshot["audit"]["marked_gross_nav_guard"] is True
