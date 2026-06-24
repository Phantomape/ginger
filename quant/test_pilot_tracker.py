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


def test_cross_pilot_overlap_includes_verdict_and_status_context() -> None:
    recs = [
        {
            "pilot": "allocator_top1",
            "label": "Source-priority allocator (TOP-1 only)",
            "sleeve": "accepted_helper_source_priority_allocator",
            "pilot_verdict": "COLLECTING",
            "pilot_verdict_note": "0/20 closed trades; keep tracking",
            "new_entries_blocked": False,
            "actionable": [
                {
                    "ticker": "DDOG",
                    "status": "HOLD",
                    "entry_date": "2026-06-18",
                    "days_held": 3,
                    "days_remaining": 7,
                    "stop_status": "no_price",
                    "unrealized_pct": None,
                    "pilot_notional_usd": 10000.0,
                }
            ],
        },
        {
            "pilot": "fundamental_growth_rs",
            "label": "Fundamental growth + RS",
            "sleeve": "fundamental_growth_rs",
            "pilot_verdict": "KILL",
            "pilot_verdict_note": "book drawdown 24.3% breaches 15% ceiling -> stop pilot",
            "new_entries_blocked": True,
            "actionable": [
                {
                    "ticker": "DDOG",
                    "status": "HOLD",
                    "entry_date": "2026-06-17",
                    "days_held": 7,
                    "days_remaining": 3,
                    "stop_status": "OK",
                    "unrealized_pct": -0.0418,
                    "pilot_notional_usd": 10000.0,
                }
            ],
        },
    ]

    overlaps = pilot_tracker._cross_pilot_overlap(recs)

    assert len(overlaps) == 1
    overlap = overlaps[0]
    assert overlap["ticker"] == "DDOG"
    assert overlap["total_exposure_usd"] == 20000.0
    assert overlap["pilot_verdicts"] == {
        "allocator_top1": "COLLECTING",
        "fundamental_growth_rs": "KILL",
    }
    assert overlap["pilot_statuses"] == {
        "allocator_top1": ["HOLD"],
        "fundamental_growth_rs": ["HOLD"],
    }
    assert overlap["new_entries_blocked_by_pilot"] == {
        "allocator_top1": False,
        "fundamental_growth_rs": True,
    }
    assert [
        row["pilot_key"] for row in overlap["participant_context"]
    ] == ["allocator_top1", "fundamental_growth_rs"]
