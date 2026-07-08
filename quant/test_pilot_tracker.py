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


def test_stop_hit_open_position_is_machine_readable_sell_action() -> None:
    pilot = {
        "key": "test_pilot",
        "label": "Test pilot",
        "sleeve": "test_sleeve",
        "max_concurrent": None,
    }
    state = {
        "updated_at": "2026-07-08T00:00:00+00:00",
        "closed_positions": [],
        "open_positions": [
            {
                "ticker": "STOP",
                "entry_date": "2026-07-01",
                "entry_price": 100.0,
                "last_price": 84.0,
                "hold_days": 10,
                "observed_trading_days": 2,
            },
        ],
        "pending_entries": [],
    }

    card = pilot_tracker._scorecard(pilot, state)
    rec = pilot_tracker._recommendations(pilot, state, card)

    assert card["verdict"] == "COLLECTING"
    assert len(rec["actionable"]) == 1
    row = rec["actionable"][0]
    assert row["ticker"] == "STOP"
    assert row["status"] == "EXIT_NOW"
    assert row["stop_status"] == "STOP_HIT"
    assert row["days_remaining"] == 8

    alerts = pilot_tracker._stop_alerts([rec])
    assert [alert["ticker"] for alert in alerts] == ["STOP"]


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


def _pos(ticker: str, notional: float = 10000.0) -> dict:
    return {
        "ticker": ticker,
        "status": "HOLD",
        "entry_date": "2026-06-22",
        "days_held": 5,
        "days_remaining": 5,
        "stop_status": "OK",
        "unrealized_pct": -0.12,
        "pilot_notional_usd": notional,
    }


def test_cross_pilot_concentration_flags_same_theme_across_pilots(monkeypatch) -> None:
    # The 2026-07 failure shape: three pilots, three DIFFERENT semiconductor
    # tickers, zero same-ticker overlap -- must still alert at the sector level.
    sector_by_ticker = {
        "CRDO": ("Technology", "Semiconductors"),
        "MU": ("Technology", "Semiconductors"),
        "WDC": ("Technology", "Computer Hardware"),
    }

    def fake_lookup(ticker, cache):
        sector, industry = sector_by_ticker[ticker]
        return {"ticker": ticker, "sector": sector, "industry": industry, "status": "ok"}

    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "load_cache", lambda *a, **k: {})
    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "lookup_sector", fake_lookup)

    recs = [
        {"pilot": "allocator_top1", "label": "A", "sleeve": "a",
         "actionable": [_pos("CRDO")]},
        {"pilot": "distribution_absorption", "label": "B", "sleeve": "b",
         "actionable": [_pos("MU")]},
        {"pilot": "fundamental_growth_rs", "label": "C", "sleeve": "c",
         "actionable": [_pos("WDC")]},
    ]

    assert pilot_tracker._cross_pilot_overlap(recs) == []

    conc = pilot_tracker._cross_pilot_concentration(recs)
    assert conc["alert_rule"] == {
        "min_positions": 3,
        "min_positions_for_exposure_share": 2,
        "min_exposure_share": 0.5,
        "operator": "or",
        "description": (
            "Alert when a known sector/industry has at least min_positions "
            "positions, or at least min_positions_for_exposure_share positions "
            "and exposure_share >= min_exposure_share."
        ),
    }
    assert conc["position_count"] == 3
    assert conc["total_actionable_exposure_usd"] == 30000.0
    tech = [g for g in conc["by_sector"] if g["sector"] == "Technology"][0]
    assert tech["positions"] == 3
    assert tech["exposure_share"] == 1.0
    assert tech["alert"] is True
    assert tech["tickers"] == ["CRDO", "MU", "WDC"]
    assert len(tech["pilots"]) == 3
    assert any(g.get("sector") == "Technology" for g in conc["alerts"])
    # Industry level: two semis positions carry 66.7% share -> share rule fires.
    semis = [g for g in conc["by_industry"] if g["industry"] == "Semiconductors"][0]
    assert semis["positions"] == 2
    assert semis["alert"] is True


def test_cross_pilot_concentration_rule_metadata_explains_three_position_alert(
    monkeypatch,
) -> None:
    themes = {
        "AMD": ("Technology", "Semiconductors"),
        "DDOG": ("Technology", "Software - Application"),
        "WDC": ("Technology", "Computer Hardware"),
        "AAL": ("Industrials", "Airlines"),
        "CAT": ("Industrials", "Farm & Heavy Construction Machinery"),
        "GE": ("Industrials", "Aerospace & Defense"),
        "MOH": ("Healthcare", "Healthcare Plans"),
    }

    def fake_lookup(ticker, cache):
        sector, industry = themes[ticker]
        return {"ticker": ticker, "sector": sector, "industry": industry, "status": "ok"}

    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "load_cache", lambda *a, **k: {})
    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "lookup_sector", fake_lookup)

    recs = [
        {"pilot": "allocator_top1", "label": "A", "sleeve": "a",
         "actionable": [_pos("WDC")]},
        {"pilot": "fundamental_growth_rs", "label": "B", "sleeve": "b",
         "actionable": [_pos("AMD"), _pos("DDOG")]},
        {"pilot": "distribution_absorption", "label": "C", "sleeve": "c",
         "actionable": [_pos("AAL"), _pos("CAT"), _pos("GE"), _pos("MOH")]},
    ]

    conc = pilot_tracker._cross_pilot_concentration(recs)
    tech = [g for g in conc["by_sector"] if g["sector"] == "Technology"][0]
    assert tech["positions"] == 3
    assert tech["exposure_share"] == 0.4286
    assert tech["alert"] is True
    assert conc["alert_rule"]["operator"] == "or"
    assert conc["alert_rule"]["min_positions_for_exposure_share"] == 2


def test_cross_pilot_concentration_no_alert_when_dispersed(monkeypatch) -> None:
    themes = {
        "AAA": ("Technology", "Software"),
        "BBB": ("Healthcare", "Biotech"),
        "CCC": ("Energy", "Oil"),
        "DDD": ("Financials", "Banks"),
    }

    def fake_lookup(ticker, cache):
        sector, industry = themes[ticker]
        return {"ticker": ticker, "sector": sector, "industry": industry, "status": "ok"}

    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "load_cache", lambda *a, **k: {})
    monkeypatch.setattr(pilot_tracker.broad_market_sector_map, "lookup_sector", fake_lookup)

    recs = [
        {"pilot": "p1", "label": "P1", "sleeve": "s1",
         "actionable": [_pos("AAA"), _pos("BBB")]},
        {"pilot": "p2", "label": "P2", "sleeve": "s2",
         "actionable": [_pos("CCC"), _pos("DDD")]},
    ]

    conc = pilot_tracker._cross_pilot_concentration(recs)
    assert conc["alerts"] == []
