from __future__ import annotations

from quant import pilot_tracker


def test_scorecard_kills_drawdown_breach_before_min_closed() -> None:
    state = {
        "updated_at": "2026-06-23T00:00:00+00:00",
        "closed_positions": [
            {
                "ticker": "AAA",
                "exit_date": "2026-06-01",
                "return_pct_net": 0.10,
                "replacement_value_vs_spy_usd": 400.0,
            },
            {
                "ticker": "BBB",
                "exit_date": "2026-06-02",
                "return_pct_net": -0.30,
                "replacement_value_vs_spy_usd": -1200.0,
            },
        ],
        "open_positions": [],
        "pending_entries": [],
    }

    card = pilot_tracker._scorecard(
        {
            "key": "test_pilot",
            "label": "Test pilot",
            "sleeve": "test_sleeve",
        },
        state,
    )

    assert card["closed_trades"] < pilot_tracker.GRADUATE_MIN_CLOSED
    assert card["book_max_drawdown_pct"] > pilot_tracker.GRADUATE_MAX_BOOK_DD_PCT
    assert card["drawdown_ceiling_breached"] is True
    assert card["verdict"] == "KILL"
    assert "breaches" in card["verdict_note"]


def test_scorecard_collects_when_under_sample_and_within_drawdown() -> None:
    state = {
        "updated_at": "2026-06-23T00:00:00+00:00",
        "closed_positions": [
            {
                "ticker": "AAA",
                "exit_date": "2026-06-01",
                "return_pct_net": 0.02,
                "replacement_value_vs_spy_usd": 100.0,
            },
            {
                "ticker": "BBB",
                "exit_date": "2026-06-02",
                "return_pct_net": -0.01,
                "replacement_value_vs_spy_usd": -50.0,
            },
        ],
        "open_positions": [],
        "pending_entries": [],
    }

    card = pilot_tracker._scorecard(
        {
            "key": "test_pilot",
            "label": "Test pilot",
            "sleeve": "test_sleeve",
        },
        state,
    )

    assert card["closed_trades"] < pilot_tracker.GRADUATE_MIN_CLOSED
    assert card["drawdown_ceiling_breached"] is False
    assert card["verdict"] == "COLLECTING"


def test_recommendations_block_new_entries_when_scorecard_kills_pilot() -> None:
    pilot = {
        "key": "test_pilot",
        "label": "Test pilot",
        "sleeve": "test_sleeve",
        "max_concurrent": None,
    }
    state = {
        "updated_at": "2026-06-23T00:00:00+00:00",
        "closed_positions": [
            {
                "ticker": "AAA",
                "exit_date": "2026-06-01",
                "return_pct_net": 0.10,
                "replacement_value_vs_spy_usd": 400.0,
            },
            {
                "ticker": "BBB",
                "exit_date": "2026-06-02",
                "return_pct_net": -0.30,
                "replacement_value_vs_spy_usd": -1200.0,
            },
        ],
        "open_positions": [
            {
                "ticker": "HOLD",
                "entry_date": "2026-06-20",
                "entry_price": 100.0,
                "last_price": 101.0,
                "hold_days": 10,
                "observed_trading_days": 2,
            },
        ],
        "pending_entries": [
            {
                "ticker": "BUYME",
                "entry_date": None,
            },
        ],
    }

    card = pilot_tracker._scorecard(pilot, state)
    rec = pilot_tracker._recommendations(pilot, state, card)

    assert card["verdict"] == "KILL"
    assert rec["new_entries_blocked"] is True
    assert {row["status"] for row in rec["actionable"]} == {"HOLD"}
    assert rec["skipped"][0]["ticker"] == "BUYME"
    assert rec["skipped"][0]["status"] == "SKIP_pilot_kill_verdict"
