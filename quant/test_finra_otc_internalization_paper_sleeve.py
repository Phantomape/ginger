from __future__ import annotations

from datetime import date, timedelta

from quant.finra_otc_internalization_paper_sleeve import (
    RULE_VERSION,
    build_finra_otc_internalization_candidates,
    build_finra_otc_internalization_paper_sleeve_snapshot,
    empty_finra_otc_internalization_paper_state,
    normalise_otc_rows,
    otc_rows_by_ticker,
    replay_finra_otc_internalization_paper_trades,
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

BASELINE_WEEKS = ["2026-02-09", "2026-02-16", "2026-02-23", "2026-03-02"]
SIGNAL_WEEK = "2026-03-09"
# Published on the Saturday before the 2026-03-30 session: the candidate rule
# must map weekend publications to the first following session.
SIGNAL_PUBLISHED = "2026-03-28"


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


def _otc_rows(
    *,
    signal_published: str = SIGNAL_PUBLISHED,
    signal_week: str = SIGNAL_WEEK,
) -> list[dict]:
    """Weekly consolidated volume is 5 x 2M = 10M shares, so baseline weeks at
    1.0M OTC shares carry share 0.10."""
    rows: list[dict] = []
    for ticker, signal_qty in (
        # STRONG: share 0.05 -> retreat ratio 0.5 (deepest retreat, ranks first).
        ("STRONG", 500_000.0),
        # WEAKER: share 0.08 -> retreat ratio 0.8.
        ("WEAKER", 800_000.0),
        # LAGGARD: deepest retreat but fails the SPY-relative guard.
        ("LAGGARD", 200_000.0),
    ):
        for week in BASELINE_WEEKS:
            rows.append(
                {
                    "ticker": ticker,
                    "week_start_date": week,
                    "published_date": (
                        date.fromisoformat(week) + timedelta(days=21)
                    ).isoformat(),
                    "otc_share_quantity": 1_000_000.0,
                }
            )
        rows.append(
            {
                "ticker": ticker,
                "week_start_date": signal_week,
                "published_date": signal_published,
                "otc_share_quantity": signal_qty,
            }
        )
    return rows


def _asof() -> str:
    return DATES[ASOF_IDX].isoformat()


def test_candidates_rank_ascending_by_share_retreat_ratio_and_apply_guards():
    ohlcv = _ohlcv()
    candidates, rejects = build_finra_otc_internalization_candidates(
        rows_by_ticker=ohlcv,
        otc_by_ticker=otc_rows_by_ticker(_otc_rows()),
        tickers=["STRONG", "WEAKER", "LAGGARD"],
        as_of=_asof(),
        same_day_core_tickers=set(),
        config={},
    )
    tickers = [row["ticker"] for row in candidates]
    assert tickers == ["STRONG", "WEAKER"]
    assert rejects.get("ret20_excess_spy_below_threshold") == 1  # LAGGARD
    top = candidates[0]
    assert top["rule_version"] == RULE_VERSION
    assert top["trade_enabled"] is False
    assert top["alters_orders"] is False
    assert abs(top["otc_share"] - 0.05) < 1e-9
    assert abs(top["baseline_share"] - 0.10) < 1e-9
    assert abs(top["share_retreat_ratio"] - 0.5) < 1e-9
    # ASCENDING rank: the deeper retreat (lower ratio) comes first.
    assert top["share_retreat_ratio"] < candidates[1]["share_retreat_ratio"]


def test_publication_is_pit_no_candidate_before_published_date():
    ohlcv = _ohlcv()
    # 2026-03-27 (Friday): signal week not yet published (published 03-28).
    candidates, rejects = build_finra_otc_internalization_candidates(
        rows_by_ticker=ohlcv,
        otc_by_ticker=otc_rows_by_ticker(_otc_rows()),
        tickers=["STRONG", "WEAKER", "LAGGARD"],
        as_of=DATES[ASOF_IDX - 1].isoformat(),
        same_day_core_tickers=set(),
        config={},
    )
    assert candidates == []
    assert rejects.get("no_new_publication_asof") == 3


def test_insufficient_prior_published_weeks_rejected():
    ohlcv = _ohlcv()
    rows = [
        row
        for row in _otc_rows()
        if row["ticker"] == "STRONG"
        and row["week_start_date"] in (SIGNAL_WEEK, BASELINE_WEEKS[-1])
    ]
    candidates, rejects = build_finra_otc_internalization_candidates(
        rows_by_ticker=ohlcv,
        otc_by_ticker=otc_rows_by_ticker(rows),
        tickers=["STRONG"],
        as_of=_asof(),
        same_day_core_tickers=set(),
        config={},
    )
    assert candidates == []
    assert rejects.get("insufficient_prior_published_weeks") == 1


def test_flat_share_not_admitted():
    ohlcv = _ohlcv()
    rows = _otc_rows()
    for row in rows:
        if row["ticker"] == "STRONG" and row["week_start_date"] == SIGNAL_WEEK:
            row["otc_share_quantity"] = 1_000_000.0  # ratio exactly 1.0
    candidates, rejects = build_finra_otc_internalization_candidates(
        rows_by_ticker=ohlcv,
        otc_by_ticker=otc_rows_by_ticker(rows),
        tickers=["STRONG"],
        as_of=_asof(),
        same_day_core_tickers=set(),
        config={},
    )
    assert candidates == []
    assert rejects.get("otc_share_not_retreating") == 1


def test_rising_share_not_admitted():
    # The inverse of the rejected ATS rise sleeve: a RISING internalization
    # share must NOT be admitted by this sleeve.
    ohlcv = _ohlcv()
    rows = _otc_rows()
    for row in rows:
        if row["ticker"] == "STRONG" and row["week_start_date"] == SIGNAL_WEEK:
            row["otc_share_quantity"] = 2_000_000.0  # ratio 2.0
    candidates, rejects = build_finra_otc_internalization_candidates(
        rows_by_ticker=ohlcv,
        otc_by_ticker=otc_rows_by_ticker(rows),
        tickers=["STRONG"],
        as_of=_asof(),
        same_day_core_tickers=set(),
        config={},
    )
    assert candidates == []
    assert rejects.get("otc_share_not_retreating") == 1


def test_snapshot_admits_top1_pending_without_orders_and_is_same_day_idempotent():
    ohlcv = _ohlcv()
    as_of = _asof()
    first = build_finra_otc_internalization_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["STRONG", "WEAKER", "LAGGARD"],
        otc_rows=_otc_rows(),
        state=empty_finra_otc_internalization_paper_state(),
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
    second = build_finra_otc_internalization_paper_sleeve_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["STRONG", "WEAKER", "LAGGARD"],
        otc_rows=_otc_rows(),
        state=carried,
        persist=False,
        config={"allow_network_fetch": False},
    )
    assert second["new_pending_count"] == 0
    assert second["pending_count"] == 1


def test_pending_fills_next_session_and_closes_after_hold_days():
    ohlcv = _ohlcv()
    snapshot = build_finra_otc_internalization_paper_sleeve_snapshot(
        as_of=_asof(),
        ohlcv_by_ticker=ohlcv,
        candidate_universe=["STRONG"],
        otc_rows=_otc_rows(),
        state=empty_finra_otc_internalization_paper_state(),
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
        step = build_finra_otc_internalization_paper_sleeve_snapshot(
            as_of=day,
            ohlcv_by_ticker=ohlcv,
            candidate_universe=["STRONG"],
            otc_rows=[],
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
    result = replay_finra_otc_internalization_paper_trades(
        ohlcv_by_ticker=ohlcv,
        otc_rows=_otc_rows(),
        start=DATES[30].isoformat(),
        end=DATES[-1].isoformat(),
        config={},
    )
    trades = result["trades"]
    assert len(trades) == 1
    trade = trades[0]
    assert trade["ticker"] == "STRONG"
    assert trade["signal_date"] == _asof()
    assert trade["entry_date"] == DATES[ASOF_IDX + 1].isoformat()
    assert trade["exit_date"] == DATES[ASOF_IDX + 11].isoformat()
    assert trade["trade_enabled"] is False
    # Rising tape: net PnL after slippage and round-trip cost should be positive.
    assert trade["pnl"] > 0


def test_replay_skips_exit_outside_window():
    ohlcv = _ohlcv()
    late_published = DATES[-3].isoformat()
    result = replay_finra_otc_internalization_paper_trades(
        ohlcv_by_ticker=ohlcv,
        otc_rows=_otc_rows(signal_published=late_published),
        start=DATES[30].isoformat(),
        end=DATES[-1].isoformat(),
        config={},
    )
    assert result["trades"] == []
    reasons = {row["unsettled_reason"] for row in result["unsettled"]}
    assert "exit_outside_window" in reasons or "no_next_open_inside_window" in reasons


def test_same_day_core_overlap_blocked():
    ohlcv = _ohlcv()
    candidates, rejects = build_finra_otc_internalization_candidates(
        rows_by_ticker=ohlcv,
        otc_by_ticker=otc_rows_by_ticker(_otc_rows()),
        tickers=["STRONG", "WEAKER"],
        as_of=_asof(),
        same_day_core_tickers={"STRONG"},
        config={},
    )
    assert [row["ticker"] for row in candidates] == ["WEAKER"]
    assert rejects.get("same_ticker_core_overlap") == 1


def test_normalise_otc_rows_dedupes_and_requires_fields():
    rows = normalise_otc_rows(
        [
            {
                "ticker": "strong",
                "week_start_date": "2026-03-09",
                "published_date": "2026-03-30",
                "otc_share_quantity": 1_000.0,
            },
            {  # duplicate (ticker, week) is dropped, first observation kept
                "ticker": "STRONG",
                "week_start_date": "2026-03-09",
                "published_date": "2026-03-31",
                "otc_share_quantity": 2_000.0,
            },
            {  # missing published_date is dropped
                "ticker": "STRONG",
                "week_start_date": "2026-03-16",
                "otc_share_quantity": 1_000.0,
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "STRONG"
    assert rows[0]["published_date"] == "2026-03-30"
