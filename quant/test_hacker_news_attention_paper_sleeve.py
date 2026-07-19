from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from quant.constants import ROUND_TRIP_COST_PCT
from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET
from quant.hacker_news_attention_paper_sleeve import (
    DOMAIN_TO_TICKER,
    HOLD_SESSIONS,
    ISSUER_OWNED_DOMAINS,
    PAPER_NOTIONAL_USD,
    HackerNewsAttentionContractError,
    build_hacker_news_attention_historical_trades,
    build_hacker_news_attention_snapshot,
    match_hacker_news_owned_domain,
    normalise_hacker_news_story_rows,
    select_hacker_news_attention_weekly_decisions,
)


def _story(object_id: str, created_at: str, url: str) -> dict[str, object]:
    return {"objectID": object_id, "created_at": created_at, "url": url}


def _week_stories(
    *,
    ticker: str,
    monday: str,
    count: int,
    prefix: str,
) -> list[dict[str, object]]:
    domain = ISSUER_OWNED_DOMAINS[ticker][0]
    start = date.fromisoformat(monday)
    return [
        _story(
            f"{prefix}-{index}",
            datetime.combine(
                start + timedelta(days=index % 6),
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            .replace(hour=12)
            .isoformat()
            .replace("+00:00", "Z"),
            f"https://{domain}/story/{prefix}/{index}",
        )
        for index in range(count)
    ]


def _business_bars(start: str, count: int, *, slope: float = 0.4):
    day = date.fromisoformat(start)
    rows = []
    index = 0
    while len(rows) < count:
        if day.weekday() < 5:
            close = 100.0 + index * slope
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": close - 0.2,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                }
            )
            index += 1
        day += timedelta(days=1)
    return rows


def test_frozen_map_and_exact_host_boundary_reject_lookalikes():
    assert len(ISSUER_OWNED_DOMAINS) == 38
    assert len(DOMAIN_TO_TICKER) == 43
    assert match_hacker_news_owned_domain("https://apple.com/x") == (
        "AAPL",
        "apple.com",
    )
    assert match_hacker_news_owned_domain("https://developer.apple.com/x") == (
        "AAPL",
        "apple.com",
    )
    assert match_hacker_news_owned_domain("https://notapple.com/x") is None
    assert match_hacker_news_owned_domain("https://apple.com.evil.example/x") is None
    assert match_hacker_news_owned_domain("https://apple.com@evil.example/x") is None
    assert match_hacker_news_owned_domain("https://github.com.evil.example/x") is None

    rows = normalise_hacker_news_story_rows(
        [
            _story("1", "2025-02-03T12:00:00Z", "https://developer.apple.com/x"),
            _story("1", "2025-02-03T12:00:00Z", "https://developer.apple.com/x"),
            _story("2", "2025-02-03T12:00:00Z", "https://notapple.com/x"),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["host"] == "developer.apple.com"


def test_duplicate_object_id_conflict_fails_closed():
    with pytest.raises(HackerNewsAttentionContractError, match="conflicting duplicate"):
        normalise_hacker_news_story_rows(
            [
                _story("same", "2025-02-03T12:00:00Z", "https://apple.com/a"),
                _story("same", "2025-02-03T12:00:00Z", "https://google.com/b"),
            ]
        )


def test_complete_week_prior_four_mean_and_strict_acceleration_are_pit():
    stories: list[dict[str, object]] = []
    prior_mondays = ["2025-01-06", "2025-01-13", "2025-01-20", "2025-01-27"]
    for index, (monday, count) in enumerate(zip(prior_mondays, [1, 2, 1, 0])):
        stories.extend(
            _week_stories(
                ticker="AAPL", monday=monday, count=count, prefix=f"a-prior-{index}"
            )
        )
    for index, monday in enumerate(prior_mondays):
        stories.extend(
            _week_stories(
                ticker="GOOG", monday=monday, count=3, prefix=f"g-prior-{index}"
            )
        )
    stories.extend(
        _week_stories(ticker="AAPL", monday="2025-02-03", count=2, prefix="a-now")
    )
    stories.extend(
        _week_stories(ticker="GOOG", monday="2025-02-03", count=3, prefix="g-now")
    )
    stories.extend(
        _week_stories(ticker="MSFT", monday="2025-02-03", count=1, prefix="m-now")
    )

    # Sunday is not yet a completed UTC week, even if rows from earlier in the
    # week have arrived.
    assert (
        select_hacker_news_attention_weekly_decisions(
            stories,
            as_of="2025-02-09",
            archive_start="2025-01-06",
        )
        == []
    )
    decisions = select_hacker_news_attention_weekly_decisions(
        stories,
        as_of="2025-02-10",
        archive_start="2025-01-06",
    )
    assert [row["ticker"] for row in decisions] == ["AAPL"]
    assert decisions[0]["week_end"] == "2025-02-09"
    assert decisions[0]["prior_four_week_counts"] == [1, 2, 1, 0]
    assert decisions[0]["prior_four_week_mean"] == 1.0
    assert decisions[0]["current_story_count"] == 2
    assert decisions[0]["attention_acceleration"] == 1.0
    # GOOG equals its prior mean and MSFT fails current_count >= 2.


def test_top_three_ranking_historical_snapshot_parity_and_h10_timing():
    stories: list[dict[str, object]] = []
    for ticker, count in (("AAPL", 5), ("MSFT", 4), ("GOOG", 3), ("AMZN", 2)):
        stories.extend(
            _week_stories(
                ticker=ticker,
                monday="2025-02-03",
                count=count,
                prefix=f"{ticker.lower()}-now",
            )
        )
    bars = _business_bars("2025-01-01", 70)
    market = {
        "SPY": bars,
        "AAPL": bars,
        "MSFT": bars,
        "GOOG": bars,
        "AMZN": bars,
    }
    replay = build_hacker_news_attention_historical_trades(
        story_rows=stories,
        ohlcv_by_ticker=market,
        start="2025-02-01",
        end="2025-03-10",
        archive_start="2025-01-06",
    )
    assert [row["ticker"] for row in replay["window_decisions"]] == [
        "AAPL",
        "MSFT",
        "GOOG",
    ]
    assert replay["trade_enabled"] is False
    assert len(replay["trades"]) == 3
    for trade in replay["trades"]:
        assert trade["entry_date"] == "2025-02-10"
        assert trade["exit_date"] == "2025-02-21"
        assert trade["hold_sessions_realized"] == HOLD_SESSIONS
        assert trade["target_price"] > trade["entry_price"]
        assert trade["paper_notional_usd"] == PAPER_NOTIONAL_USD
        assert trade["round_trip_cost_pct"] == ROUND_TRIP_COST_PCT
        assert trade["entry_slippage_bps"] == SLIPPAGE_BPS_ENTRY
        assert trade["exit_slippage_bps"] == SLIPPAGE_BPS_TARGET
        assert trade["trade_enabled"] is False
        assert trade["alters_orders"] is False

    snapshot = build_hacker_news_attention_snapshot(
        story_rows=stories,
        ohlcv_by_ticker=market,
        as_of="2025-03-10",
        start="2025-02-01",
        archive_start="2025-01-06",
        persist=False,
    )
    assert snapshot["trade_enabled"] is False
    assert snapshot["alters_orders"] is False
    assert snapshot["execution_envelope"]["max_concurrent_positions"] == 6
    assert snapshot["execution_envelope"]["one_active_position_per_ticker"] is True
    assert [
        row["decision_id"] for row in snapshot["replay"]["window_decisions"]
    ] == [row["decision_id"] for row in replay["window_decisions"]]
    assert [
        (row["decision_id"], row["entry_date"], row["exit_date"])
        for row in snapshot["replay"]["trades"]
    ] == [
        (row["decision_id"], row["entry_date"], row["exit_date"])
        for row in replay["trades"]
    ]


def test_one_active_position_per_ticker_rejects_overlapping_week():
    stories: list[dict[str, object]] = []
    stories.extend(
        _week_stories(ticker="AAPL", monday="2025-02-03", count=2, prefix="first")
    )
    stories.extend(
        _week_stories(ticker="AAPL", monday="2025-02-10", count=3, prefix="second")
    )
    bars = _business_bars("2025-01-01", 70)
    replay = build_hacker_news_attention_historical_trades(
        story_rows=stories,
        ohlcv_by_ticker={"SPY": bars, "AAPL": bars},
        start="2025-02-01",
        end="2025-03-10",
        archive_start="2025-01-06",
    )
    assert len(replay["window_decisions"]) == 2
    assert len(replay["trade_candidates"]) == 1
    assert replay["reject_totals"] == {"same_ticker_active": 1}
    assert replay["trade_candidates"][0]["entry_date"]
    assert replay["trade_candidates"][0]["target_price"]


def test_optional_snapshot_persistence_uses_injected_paths(tmp_path):
    stories = _week_stories(
        ticker="AAPL", monday="2025-02-03", count=2, prefix="persist"
    )
    bars = _business_bars("2025-01-01", 45)
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshots.jsonl"
    snapshot = build_hacker_news_attention_snapshot(
        story_rows=stories,
        ohlcv_by_ticker={"SPY": bars, "AAPL": bars},
        as_of="2025-02-14",
        start="2025-02-01",
        archive_start="2025-01-06",
        persist=True,
        state_path=state_path,
        snapshot_log_path=snapshot_path,
    )
    assert state_path.exists()
    assert snapshot_path.exists()
    assert snapshot["trade_enabled"] is False
    assert snapshot["replay"]["trade_candidates"][0]["entry_date"]
    assert snapshot["replay"]["trade_candidates"][0]["target_price"]
