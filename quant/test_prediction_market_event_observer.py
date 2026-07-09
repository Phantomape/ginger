import json
from pathlib import Path
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from prediction_market_event_observer import (  # noqa: E402
    PREDICTION_MARKET_SOURCE_SPECS,
    build_prediction_market_event_outcome_ledger,
    extract_yes_probability,
    get_prediction_market_observer_sources,
    persist_prediction_market_event_observer,
    persist_prediction_market_event_outcome_ledger,
    prediction_market_source_relevance,
)


def test_prediction_market_observer_source_manifest_is_observer_only():
    sources = get_prediction_market_observer_sources()

    assert len(sources) == len(PREDICTION_MARKET_SOURCE_SPECS)
    assert all(
        source["source_type"] == "polymarket_prediction_market_event"
        for source in sources
    )
    assert all(source["metadata"]["observer_only"] is True for source in sources)
    assert all(source["metadata"]["provider"] == "polymarket" for source in sources)
    assert all(source["metadata"]["candidate_tickers"] for source in sources)
    assert all(source["metadata"]["relevance_groups"] for source in sources)
    assert all(source["metadata"]["min_relevance_groups"] >= 2 for source in sources)
    assert all("clean_trade_news" not in source["url"] for source in sources)


def test_extract_yes_probability_handles_polymarket_outcome_prices():
    assert extract_yes_probability(
        {"outcomes": '["Yes","No"]', "outcomePrices": '["0.31","0.69"]'}
    ) == 0.31
    assert extract_yes_probability(
        {"outcomes": ["No", "Yes"], "outcomePrices": [0.72, 0.28]}
    ) == 0.28
    assert extract_yes_probability({"bestBid": "0.30", "bestAsk": "0.34"}) == 0.32


def test_persist_prediction_market_event_observer_writes_separate_artifacts(tmp_path):
    calls = []

    def fake_fetch(url, params, timeout_seconds=10.0):
        calls.append((url, params, timeout_seconds))
        slug = params["search"].lower().replace(" ", "-")[:80]
        return {
            "events": [
                {
                    "id": f"event-{len(calls)}",
                    "slug": slug,
                    "title": params["search"],
                    "markets": [
                        {
                            "id": f"market-{len(calls)}",
                            "question": f"Will {params['search']} occur?",
                            "outcomes": '["Yes","No"]',
                            "outcomePrices": '["0.31","0.69"]',
                            "volume": "100000",
                            "liquidity": "25000",
                            "active": True,
                            "closed": False,
                        }
                    ],
                }
            ]
        }

    summary = persist_prediction_market_event_observer(
        "20260703",
        data_dir=tmp_path,
        fetch_func=fake_fetch,
    )

    assert len(calls) == len(PREDICTION_MARKET_SOURCE_SPECS)
    assert summary["status"] == "ok"
    assert summary["observer_only"] is True
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False
    assert summary["source_count"] == len(PREDICTION_MARKET_SOURCE_SPECS)
    assert summary["raw_item_count"] == len(PREDICTION_MARKET_SOURCE_SPECS)
    assert summary["unique_item_count"] == len(PREDICTION_MARKET_SOURCE_SPECS)

    items_path = Path(summary["items_path"])
    source_stats_path = Path(summary["source_stats_path"])
    source_manifest_path = Path(summary["source_manifest_path"])
    assert items_path.exists()
    assert source_stats_path.exists()
    assert source_manifest_path.exists()

    items = json.loads(items_path.read_text(encoding="utf-8"))
    assert all(item["observer_only"] is True for item in items)
    assert all(item["observer_name"] == "prediction_market_event_observer" for item in items)
    assert all(item["provider"] == "polymarket" for item in items)
    assert all(item["prediction_market_query_id"] for item in items)
    assert all(item["candidate_tickers"] for item in items)
    assert all(item["yes_probability"] == 0.31 for item in items)
    assert all(item["relevance_matched_group_count"] >= 2 for item in items)
    assert all(item["relevance_hit_terms"] for item in items)
    assert not any("clean_trade_news" in str(path) for path in (items_path, source_stats_path))

    spacex = [
        item
        for item in items
        if item["prediction_market_query_id"] == "spacex_ipo_probability"
    ][0]
    assert "RKLB" in spacex["candidate_tickers"]

    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    assert manifest["observer_only"] is True
    assert manifest["strategy_behavior_changed"] is False
    assert manifest["trade_enabled"] is False
    assert manifest["provider"] == "polymarket"


def test_prediction_market_relevance_rejects_single_generic_term():
    sources = get_prediction_market_observer_sources()
    ai_export_metadata = [
        source["metadata"]
        for source in sources
        if source["metadata"]["query_id"] == "ai_export_controls_probability"
    ][0]

    irrelevant = {
        "title": "China x India military clash by December 31?",
        "question": "Will China x India military clash happen by December 31?",
    }
    relevant = {
        "title": "Nvidia AI chip export controls to China by year-end?",
        "question": "Will the US restrict Nvidia AI chip exports to China?",
    }

    assert prediction_market_source_relevance(irrelevant, ai_export_metadata)[
        "matched"
    ] is False
    assert prediction_market_source_relevance(relevant, ai_export_metadata)[
        "matched"
    ] is True


def test_prediction_market_relevance_uses_token_boundaries_for_short_terms():
    metadata = {
        "relevance_groups": [["ai"], ["energy"]],
        "min_relevance_groups": 2,
    }

    assert prediction_market_source_relevance(
        {
            "title": "Russia-Ukraine ceasefire before GTA VI?",
            "question": "Will energy markets react?",
        },
        metadata,
    )["matched"] is False
    assert prediction_market_source_relevance(
        {
            "title": "AI energy shortage for data centers?",
            "question": "Will AI data center energy shortages persist?",
        },
        metadata,
    )["matched"] is True


def test_prediction_market_relevance_rejects_known_off_theme_markets():
    sources = get_prediction_market_observer_sources()
    hyperscaler_metadata = [
        source["metadata"]
        for source in sources
        if source["metadata"]["query_id"] == "hyperscaler_power_shortage_probability"
    ][0]
    frontier_ai_metadata = [
        source["metadata"]
        for source in sources
        if source["metadata"]["query_id"] == "frontier_ai_private_capex_probability"
    ][0]

    assert prediction_market_source_relevance(
        {
            "title": "What will happen before GTA VI?",
            "question": "Russia-Ukraine Ceasefire before GTA VI?",
        },
        hyperscaler_metadata,
    )["matched"] is False
    assert prediction_market_source_relevance(
        {
            "title": "Xi Jinping out before 2027?",
            "question": "Xi Jinping out before 2027?",
        },
        hyperscaler_metadata,
    )["matched"] is False
    assert prediction_market_source_relevance(
        {
            "title": "Will OpenAI launch a consumer hardware product by 2026?",
            "question": "Will OpenAI launch a new consumer hardware product?",
        },
        frontier_ai_metadata,
    )["matched"] is False


def test_persist_prediction_market_event_observer_records_relevance_rejects(tmp_path):
    def fake_fetch(url, params, timeout_seconds=10.0):
        if "AI chips export controls" in params["search"]:
            return {
                "events": [
                    {
                        "id": "irrelevant-event",
                        "slug": "china-india-military-clash",
                        "title": "China x India military clash by December 31?",
                        "markets": [
                            {
                                "id": "irrelevant-market",
                                "question": "Will China x India clash by December 31?",
                                "outcomes": '["Yes","No"]',
                                "outcomePrices": '["0.44","0.56"]',
                            }
                        ],
                    },
                    {
                        "id": "relevant-event",
                        "slug": "nvidia-ai-chip-export-controls",
                        "title": "Nvidia AI chip export controls to China by year-end?",
                        "markets": [
                            {
                                "id": "relevant-market",
                                "question": "Will US restrict Nvidia AI chip exports to China?",
                                "outcomes": '["Yes","No"]',
                                "outcomePrices": '["0.31","0.69"]',
                            }
                        ],
                    },
                ]
            }
        slug = params["search"].lower().replace(" ", "-")[:80]
        return {
            "events": [
                {
                    "id": f"event-{slug}",
                    "slug": slug,
                    "title": params["search"],
                    "markets": [
                        {
                            "id": f"market-{slug}",
                            "question": f"Will {params['search']} occur?",
                            "outcomes": '["Yes","No"]',
                            "outcomePrices": '["0.31","0.69"]',
                        }
                    ],
                }
            ]
        }

    summary = persist_prediction_market_event_observer(
        "20260703",
        data_dir=tmp_path,
        fetch_func=fake_fetch,
    )
    items = json.loads(Path(summary["items_path"]).read_text(encoding="utf-8"))
    source_stats = json.loads(Path(summary["source_stats_path"]).read_text(encoding="utf-8"))

    assert summary["relevance_rejected_count"] == 1
    assert not any(item["provider_event_id"] == "irrelevant-event" for item in items)
    assert any(item["provider_event_id"] == "relevant-event" for item in items)
    ai_stat = [
        stat
        for stat in source_stats
        if stat["metadata"]["query_id"] == "ai_export_controls_probability"
    ][0]
    assert ai_stat["market_candidate_count"] == 2
    assert ai_stat["relevance_rejected_count"] == 1
    assert ai_stat["parsed_item_count"] == 1


def test_persist_prediction_market_event_observer_records_source_errors(tmp_path):
    def failing_fetch(url, params, timeout_seconds=10.0):
        raise RuntimeError(f"prediction market unavailable for {params['search']}")

    summary = persist_prediction_market_event_observer(
        "20260703",
        data_dir=tmp_path,
        fetch_func=failing_fetch,
    )

    assert summary["status"] == "ok"
    assert summary["source_error_count"] == len(PREDICTION_MARKET_SOURCE_SPECS)
    assert summary["raw_item_count"] == 0
    assert summary["unique_item_count"] == 0
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False

    source_stats = json.loads(Path(summary["source_stats_path"]).read_text(encoding="utf-8"))
    assert len(source_stats) == len(PREDICTION_MARKET_SOURCE_SPECS)
    assert all("prediction market unavailable" in stat["error"] for stat in source_stats)


def _bars(ticker, prices):
    return [
        {
            "Date": day,
            "Open": open_price,
            "Close": close_price,
            "ticker": ticker,
        }
        for day, open_price, close_price in prices
    ]


def test_prediction_market_outcome_ledger_settles_candidate_vs_cash_spy_qqq():
    items = [
        {
            "prediction_market_query_id": "ai_export_controls_probability",
            "provider": "polymarket",
            "provider_event_id": "event-1",
            "provider_market_id": "market-1",
            "title": "Nvidia AI chip export controls to China",
            "question": "Will US restrict Nvidia exports?",
            "theme": "ai_chip_export_controls",
            "relation_type": "regulatory_policy_to_public_semiconductor_exposure",
            "candidate_tickers": ["NVDA"],
            "yes_probability": 0.31,
            "observed_at": "2026-07-01T22:00:00+00:00",
        }
    ]
    ohlcv = {
        "NVDA": _bars(
            "NVDA",
            [
                ("2026-07-01", 100.0, 100.0),
                ("2026-07-02", 100.0, 103.0),
                ("2026-07-03", 103.0, 106.0),
                ("2026-07-06", 106.0, 110.0),
            ],
        ),
        "SPY": _bars(
            "SPY",
            [
                ("2026-07-02", 500.0, 505.0),
                ("2026-07-03", 505.0, 510.0),
                ("2026-07-06", 510.0, 515.0),
            ],
        ),
        "QQQ": _bars(
            "QQQ",
            [
                ("2026-07-02", 400.0, 404.0),
                ("2026-07-03", 404.0, 408.0),
                ("2026-07-06", 408.0, 412.0),
            ],
        ),
    }

    rows, summary = build_prediction_market_event_outcome_ledger(
        items,
        ohlcv,
        as_of_date="2026-07-06",
        horizons=(3,),
        notional_usd=4000.0,
    )

    assert summary["settled_count"] == 1
    assert summary["unsettled_count"] == 0
    assert rows[0]["outcome_status"] == "settled"
    assert rows[0]["entry_date"] == "2026-07-02"
    assert rows[0]["exit_date"] == "2026-07-06"
    assert rows[0]["pnl_usd"] == 400.0
    assert rows[0]["replacement_value_vs_cash_usd"] == 400.0
    assert rows[0]["replacement_value_vs_spy_usd"] == 280.0
    assert rows[0]["replacement_value_vs_qqq_usd"] == 280.0
    assert rows[0]["trade_enabled"] is False


def test_prediction_market_outcome_ledger_keeps_immature_rows_unsettled():
    items = [
        {
            "prediction_market_query_id": "spacex_ipo_probability",
            "provider": "polymarket",
            "provider_event_id": "event-2",
            "provider_market_id": "market-2",
            "candidate_tickers": ["RKLB"],
            "yes_probability": 0.42,
            "observed_at": "2026-07-01T22:00:00+00:00",
        }
    ]
    ohlcv = {
        "RKLB": _bars(
            "RKLB",
            [
                ("2026-07-02", 10.0, 10.5),
                ("2026-07-03", 10.5, 11.0),
            ],
        ),
        "SPY": _bars("SPY", [("2026-07-02", 500.0, 505.0)]),
        "QQQ": _bars("QQQ", [("2026-07-02", 400.0, 404.0)]),
    }

    rows, summary = build_prediction_market_event_outcome_ledger(
        items,
        ohlcv,
        as_of_date="2026-07-03",
        horizons=(3,),
        notional_usd=4000.0,
    )

    assert summary["settled_count"] == 0
    assert summary["unsettled_count"] == 1
    assert rows[0]["outcome_status"] == "unsettled_horizon"
    assert rows[0]["entry_date"] == "2026-07-02"
    assert "replacement_value_vs_cash_usd" not in rows[0]


def test_prediction_market_outcome_ledger_separates_future_entry_from_missing_price():
    items = [
        {
            "prediction_market_query_id": "future_session_probability",
            "provider": "polymarket",
            "provider_event_id": "event-future",
            "provider_market_id": "market-future",
            "candidate_tickers": ["FUTR"],
            "yes_probability": 0.42,
            "observed_at": "2026-07-04T22:00:00+00:00",
        },
        {
            "prediction_market_query_id": "missing_ticker_probability",
            "provider": "polymarket",
            "provider_event_id": "event-missing",
            "provider_market_id": "market-missing",
            "candidate_tickers": ["MISS"],
            "yes_probability": 0.35,
            "observed_at": "2026-07-01T22:00:00+00:00",
        },
    ]
    ohlcv = {
        "FUTR": _bars("FUTR", [("2026-07-02", 20.0, 21.0)]),
        "MISS": _bars("MISS", [("2026-07-01", 10.0, 10.0)]),
        "SPY": _bars(
            "SPY",
            [
                ("2026-07-01", 500.0, 500.0),
                ("2026-07-02", 500.0, 505.0),
            ],
        ),
        "QQQ": _bars(
            "QQQ",
            [
                ("2026-07-01", 400.0, 400.0),
                ("2026-07-02", 400.0, 404.0),
            ],
        ),
    }

    rows, summary = build_prediction_market_event_outcome_ledger(
        items,
        ohlcv,
        as_of_date="2026-07-04",
        horizons=(2,),
        notional_usd=4000.0,
    )

    by_query = {row["prediction_market_query_id"]: row for row in rows}
    assert summary["settled_count"] == 0
    assert summary["status_counts"] == {
        "future_entry_session_not_reached": 1,
        "unsettled_no_entry_bar": 1,
    }
    assert (
        by_query["future_session_probability"]["outcome_status"]
        == "future_entry_session_not_reached"
    )
    assert (
        by_query["future_session_probability"]["outcome_status_detail"]
        == "market_calendar_has_no_session_after_observed_date"
    )
    assert (
        by_query["missing_ticker_probability"]["outcome_status"]
        == "unsettled_no_entry_bar"
    )
    assert (
        by_query["missing_ticker_probability"]["outcome_status_detail"]
        == "market_calendar_has_next_session_but_ticker_missing_bar"
    )


def test_persist_prediction_market_event_outcome_ledger_reads_accumulated_daily_items(
    tmp_path,
):
    base = tmp_path / "non_ohlcv" / "prediction_market_event_observer" / "daily"
    base.mkdir(parents=True)
    (base / "prediction_market_event_observer_20260701.json").write_text(
        json.dumps(
            [
                {
                    "prediction_market_query_id": "ai_export_controls_probability",
                    "provider": "polymarket",
                    "provider_event_id": "event-1",
                    "provider_market_id": "market-1",
                    "candidate_tickers": ["NVDA"],
                    "yes_probability": 0.31,
                    "observed_at": "2026-07-01T22:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    (base / "prediction_market_event_observer_20260703.json").write_text(
        json.dumps(
            [
                {
                    "prediction_market_query_id": "spacex_ipo_probability",
                    "provider": "polymarket",
                    "provider_event_id": "event-2",
                    "provider_market_id": "market-2",
                    "candidate_tickers": ["RKLB"],
                    "yes_probability": 0.42,
                    "observed_at": "2026-07-03T22:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    ohlcv = {
        "NVDA": _bars(
            "NVDA",
            [
                ("2026-07-02", 100.0, 103.0),
                ("2026-07-03", 103.0, 106.0),
            ],
        ),
        "RKLB": _bars(
            "RKLB",
            [
                ("2026-07-06", 10.0, 10.5),
                ("2026-07-07", 10.5, 10.8),
            ],
        ),
        "SPY": _bars(
            "SPY",
            [
                ("2026-07-02", 500.0, 505.0),
                ("2026-07-03", 505.0, 510.0),
                ("2026-07-06", 510.0, 515.0),
                ("2026-07-07", 515.0, 520.0),
            ],
        ),
        "QQQ": _bars(
            "QQQ",
            [
                ("2026-07-02", 400.0, 404.0),
                ("2026-07-03", 404.0, 408.0),
                ("2026-07-06", 408.0, 412.0),
                ("2026-07-07", 412.0, 416.0),
            ],
        ),
    }

    summary = persist_prediction_market_event_outcome_ledger(
        "20260707",
        data_dir=tmp_path,
        ohlcv_by_ticker=ohlcv,
        horizons=(2,),
        notional_usd=4000.0,
    )

    assert summary["status"] == "ok"
    assert summary["daily_item_file_count"] == 2
    assert summary["source_item_count"] == 2
    assert summary["candidate_outcome_row_count"] == 2
    assert summary["settled_count"] == 2
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False

    ledger_path = Path(summary["ledger_path"])
    latest_path = Path(summary["latest_summary_path"])
    assert ledger_path.exists()
    assert latest_path.exists()
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {row["candidate_ticker"] for row in rows} == {"NVDA", "RKLB"}
    assert all(row["outcome_status"] == "settled" for row in rows)
