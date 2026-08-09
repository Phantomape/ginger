from __future__ import annotations

from datetime import date, timedelta

from quant.moomoo_capital_flow_paper_sleeve import (
    RULE_VERSION,
    build_moomoo_capital_flow_candidates,
    build_moomoo_capital_flow_paper_sleeve_snapshot,
    empty_moomoo_capital_flow_paper_state,
    flow_rows_by_ticker,
    normalise_flow_rows,
    refresh_moomoo_capital_flow_archive,
    replay_moomoo_capital_flow_paper_trades,
)


def _weekdays(start: date, count: int) -> list[date]:
    out: list[date] = []
    cursor = start
    while len(out) < count:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


DATES = _weekdays(date(2026, 1, 5), 80)
ASOF_IDX = 60  # 2026-03-30, a regular US session (Monday)


def _rows(*, base: float, step: float, volume: float = 2_000_000.0) -> list[dict]:
    rows = []
    for idx, day in enumerate(DATES):
        close = base + step * idx
        rows.append(
            {
                "date": day.isoformat(),
                "open": round(close * 0.995, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": volume,
            }
        )
    return rows


def _ohlcv() -> dict[str, list[dict]]:
    return {
        "SPY": _rows(base=100.0, step=0.05),
        # Both outpace SPY on ret20; ADV comfortably above $50M.
        "STRONG": _rows(base=80.0, step=0.20),
        "WEAKER": _rows(base=60.0, step=0.15),
        "LAGGARD": _rows(base=50.0, step=0.01),
    }


def _flow_rows(as_of: str) -> list[dict]:
    return [
        # STRONG: bigger main inflow relative to ADV -> should rank first.
        {"ticker": "STRONG", "flow_date": as_of, "main_in_flow": 30_000_000.0,
         "in_flow": 35_000_000.0},
        {"ticker": "WEAKER", "flow_date": as_of, "main_in_flow": 5_000_000.0,
         "in_flow": 6_000_000.0},
        # LAGGARD has inflow but fails the SPY-relative guard.
        {"ticker": "LAGGARD", "flow_date": as_of, "main_in_flow": 40_000_000.0},
    ]


def _asof() -> str:
    return DATES[ASOF_IDX].isoformat()


def test_candidates_rank_by_main_flow_ratio_and_apply_guards():
    ohlcv = _ohlcv()
    as_of = _asof()
    candidates, rejects = build_moomoo_capital_flow_candidates(
        rows_by_ticker=ohlcv,
        flow_by_ticker=flow_rows_by_ticker(_flow_rows(as_of)),
        tickers=["STRONG", "WEAKER", "LAGGARD"],
        as_of=as_of,
        same_day_core_tickers=set(),
        config={
            "relative_strength_days": 20,
            "dollar_volume_days": 20,
            "min_close": 10.0,
            "min_avg_dollar_volume_20": 50_000_000.0,
            "min_main_in_flow": 0.0,
            "min_ret20_excess_spy": 0.0,
            "block_same_day_core_overlap": True,
            "paper_notional_usd": 4_000.0,
        },
    )
    tickers = [row["ticker"] for row in candidates]
    assert tickers == ["STRONG", "WEAKER"]
    assert rejects.get("ret20_excess_spy_below_threshold") == 1  # LAGGARD
    top = candidates[0]
    assert top["rule_version"] == RULE_VERSION
    assert top["trade_enabled"] is False
    assert top["alters_orders"] is False
    assert top["main_flow_ratio"] > candidates[1]["main_flow_ratio"]


def test_missing_or_negative_flow_is_rejected():
    ohlcv = _ohlcv()
    as_of = _asof()
    flows = [
        {"ticker": "STRONG", "flow_date": as_of, "main_in_flow": -1_000_000.0},
    ]
    candidates, rejects = build_moomoo_capital_flow_candidates(
        rows_by_ticker=ohlcv,
        flow_by_ticker=flow_rows_by_ticker(flows),
        tickers=["STRONG", "WEAKER"],
        as_of=as_of,
        same_day_core_tickers=set(),
        config={},
    )
    assert candidates == []
    assert rejects.get("main_in_flow_not_positive") == 1  # STRONG negative
    assert rejects.get("missing_flow_row_asof") == 1  # WEAKER absent


def test_snapshot_admits_top1_pending_without_orders_and_is_same_day_idempotent():
    ohlcv = _ohlcv()
    as_of = _asof()
    state = empty_moomoo_capital_flow_paper_state()

    first = build_moomoo_capital_flow_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["STRONG", "WEAKER", "LAGGARD"],
        flow_rows=_flow_rows(as_of),
        state=state,
        persist=False,
        config={"allow_network_fetch": False},
    )
    assert first["trade_enabled"] is False
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["new_pending_entries"][0]["ticker"] == "STRONG"
    assert first["production_impact"]["alters_orders"] is False

    # Same-day re-run with the carried state must not grant a second slot
    # (exp-20260701-004 idempotency rule).
    carried = {
        "pending_entries": first["pending_entries"],
        "open_positions": first["open_positions"],
        "closed_positions": [],
        "skipped_entries": [],
    }
    second = build_moomoo_capital_flow_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["STRONG", "WEAKER", "LAGGARD"],
        flow_rows=_flow_rows(as_of),
        state=carried,
        persist=False,
        config={"allow_network_fetch": False},
    )
    assert second["new_pending_count"] == 0
    assert second["pending_count"] == 1


def test_pending_fills_next_session_and_closes_after_hold_days():
    ohlcv = _ohlcv()
    as_of = _asof()
    snapshot = build_moomoo_capital_flow_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["STRONG"],
        flow_rows=_flow_rows(as_of),
        state=empty_moomoo_capital_flow_paper_state(),
        persist=False,
        config={"allow_network_fetch": False},
    )
    state = {
        "pending_entries": snapshot["pending_entries"],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }
    filled_snapshot = None
    for idx in range(ASOF_IDX + 1, len(DATES)):
        day = DATES[idx].isoformat()
        step = build_moomoo_capital_flow_paper_sleeve_snapshot(
            as_of=day,
            ohlcv_by_ticker=ohlcv,
            candidate_universe=["STRONG"],
            flow_rows=[],
            state=state,
            persist=False,
            config={"allow_network_fetch": False},
        )
        if step.get("error"):  # non-session day: ledger untouched
            continue
        state = {
            "pending_entries": step["pending_entries"],
            "open_positions": step["open_positions"],
            "closed_positions": state["closed_positions"] + step["closed_positions_today"],
            "skipped_entries": [],
        }
        if step["filled_count"]:
            filled_snapshot = step
        if state["closed_positions"]:
            break
    assert filled_snapshot is not None
    assert filled_snapshot["filled_count"] == 1
    closed = state["closed_positions"]
    assert len(closed) == 1
    position = closed[0]
    assert position["ticker"] == "STRONG"
    assert position["observed_trading_days"] == 10
    assert position["trade_enabled"] is False
    assert position["pnl"] is not None


def test_replay_matches_shared_candidate_rule_top1_selection():
    ohlcv = _ohlcv()
    as_of = _asof()
    result = replay_moomoo_capital_flow_paper_trades(
        ohlcv_by_ticker=ohlcv,
        flow_rows=_flow_rows(as_of),
        start=DATES[30].isoformat(),
        end=DATES[-1].isoformat(),
        config={},
    )
    trades = result["trades"]
    assert len(trades) == 1
    trade = trades[0]
    assert trade["ticker"] == "STRONG"
    assert trade["signal_date"] == as_of
    assert trade["entry_date"] == DATES[ASOF_IDX + 1].isoformat()
    assert trade["exit_date"] == DATES[ASOF_IDX + 11].isoformat()
    assert trade["trade_enabled"] is False
    # Rising tape: net PnL after slippage and round-trip cost should be positive.
    assert trade["pnl"] > 0


def test_replay_skips_exit_outside_window():
    ohlcv = _ohlcv()
    late_asof = DATES[-3].isoformat()
    result = replay_moomoo_capital_flow_paper_trades(
        ohlcv_by_ticker=ohlcv,
        flow_rows=_flow_rows(late_asof),
        start=DATES[30].isoformat(),
        end=DATES[-1].isoformat(),
        config={},
    )
    assert result["trades"] == []
    reasons = {row["unsettled_reason"] for row in result["unsettled"]}
    assert "exit_outside_window" in reasons or "no_next_open_inside_window" in reasons


def test_same_day_core_overlap_blocked():
    ohlcv = _ohlcv()
    as_of = _asof()
    candidates, rejects = build_moomoo_capital_flow_candidates(
        rows_by_ticker=ohlcv,
        flow_by_ticker=flow_rows_by_ticker(_flow_rows(as_of)),
        tickers=["STRONG", "WEAKER"],
        as_of=as_of,
        same_day_core_tickers={"STRONG"},
        config={},
    )
    assert [row["ticker"] for row in candidates] == ["WEAKER"]
    assert rejects.get("same_ticker_core_overlap") == 1


def test_normalise_flow_rows_maps_vendor_timestamp():
    rows = normalise_flow_rows(
        [
            {
                "ticker": "us.strong",
                "capital_flow_item_time": "2026-03-30 00:00:00",
                "main_in_flow": 1_000.0,
            }
        ]
    )
    assert rows and rows[0]["flow_date"] == "2026-03-30"
    assert rows[0]["ticker"] == "US.STRONG"


def test_refresh_attempts_each_new_session_instead_of_waiting_three_days():
    existing = [
        {
            "ticker": "STRONG",
            "flow_date": "2026-07-20",
            "main_in_flow": 1_000.0,
            "fetched_at": "2026-07-21T01:00:00+00:00",
        }
    ]
    calls: list[dict] = []

    def _fetch(**kwargs):
        calls.append(kwargs)
        return (
            [
                {
                    "ticker": "STRONG",
                    "flow_date": "2026-07-21",
                    "main_in_flow": 2_000.0,
                    "fetched_at": "2026-07-22T01:00:00+00:00",
                }
            ],
            [{"ticker": "STRONG", "row_count": 2}],
        )

    rows, status, _ = refresh_moomoo_capital_flow_archive(
        existing_rows=existing,
        tickers={"STRONG"},
        as_of="2026-07-21",
        fetch_fn=_fetch,
        save=False,
    )

    assert status == "local_archive_refreshed"
    assert calls == [{"tickers": {"STRONG"}, "start": "2026-07-20", "end": "2026-07-21"}]
    assert max(row["flow_date"] for row in rows) == "2026-07-21"
