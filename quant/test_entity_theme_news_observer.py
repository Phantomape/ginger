import json
from pathlib import Path
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from entity_theme_news_observer import (  # noqa: E402
    ENTITY_THEME_SOURCE_SPECS,
    build_entity_theme_news_outcome_ledger,
    get_entity_theme_observer_sources,
    persist_entity_theme_news_observer,
    persist_entity_theme_news_outcome_ledger,
)


def test_entity_theme_observer_source_manifest_is_observer_only():
    sources = get_entity_theme_observer_sources()

    assert len(sources) == len(ENTITY_THEME_SOURCE_SPECS)
    assert all(source["source_type"] == "google_news_entity_theme" for source in sources)
    assert all(source["metadata"]["observer_only"] is True for source in sources)
    assert all(source["metadata"]["candidate_tickers"] for source in sources)
    assert all("stock" not in source["url"].lower().split("q=", 1)[1].split("&", 1)[0] for source in sources)


def test_persist_entity_theme_news_observer_writes_separate_artifacts(tmp_path):
    calls = []

    def fake_parse(url, source_type, metadata):
        calls.append((url, source_type, metadata))
        return (
            [
                {
                    "source": source_type,
                    "title": f"{metadata['query_id']} headline",
                    "summary": "observer row",
                    "url": f"https://example.test/{metadata['query_id']}",
                    "published_at": "2026-07-03T13:00:00+00:00",
                    "tickers": [],
                    "raw_source": url,
                    "source_metadata": metadata,
                }
            ],
            {
                "url": url,
                "source_type": source_type,
                "metadata": metadata,
                "request_headers_used": {},
                "status": 200,
                "bozo": False,
                "bozo_exception": None,
                "entry_count": 1,
                "parsed_item_count": 1,
                "error": None,
            },
        )

    summary = persist_entity_theme_news_observer(
        "20260703",
        data_dir=tmp_path,
        parse_func=fake_parse,
    )

    assert len(calls) == len(ENTITY_THEME_SOURCE_SPECS)
    assert summary["status"] == "ok"
    assert summary["observer_only"] is True
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["alters_orders"] is False
    assert summary["source_count"] == len(ENTITY_THEME_SOURCE_SPECS)
    assert summary["raw_item_count"] == len(ENTITY_THEME_SOURCE_SPECS)
    assert summary["unique_item_count"] == len(ENTITY_THEME_SOURCE_SPECS)

    items_path = Path(summary["items_path"])
    source_stats_path = Path(summary["source_stats_path"])
    source_manifest_path = Path(summary["source_manifest_path"])
    assert items_path.exists()
    assert source_stats_path.exists()
    assert source_manifest_path.exists()

    items = json.loads(items_path.read_text(encoding="utf-8"))
    assert all(item["observer_only"] is True for item in items)
    assert all(item["observer_name"] == "entity_theme_news_observer" for item in items)
    assert all(item["entity_theme_query_id"] for item in items)
    assert all(item["candidate_tickers"] for item in items)
    assert not any("clean_trade_news" in str(path) for path in (items_path, source_stats_path))

    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    assert manifest["observer_only"] is True
    assert manifest["strategy_behavior_changed"] is False
    assert manifest["trade_enabled"] is False


def test_persist_entity_theme_news_observer_records_source_errors(tmp_path):
    def failing_parse(url, source_type, metadata):
        raise RuntimeError(f"rss unavailable for {metadata['query_id']}")

    summary = persist_entity_theme_news_observer(
        "20260703",
        data_dir=tmp_path,
        parse_func=failing_parse,
    )

    assert summary["status"] == "ok"
    assert summary["source_error_count"] == len(ENTITY_THEME_SOURCE_SPECS)
    assert summary["raw_item_count"] == 0
    assert summary["unique_item_count"] == 0
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False

    source_stats = json.loads(Path(summary["source_stats_path"]).read_text(encoding="utf-8"))
    assert len(source_stats) == len(ENTITY_THEME_SOURCE_SPECS)
    assert all("rss unavailable" in stat["error"] for stat in source_stats)


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


def test_entity_theme_outcome_ledger_settles_candidate_vs_cash_spy_qqq():
    items = [
        {
            "entity_theme_query_id": "frontier_ai_private_capex",
            "primary_entity": "frontier_ai_labs",
            "theme": "ai_capex_private_lab",
            "relation_type": "private_ai_lab_to_public_ai_infrastructure",
            "title": "OpenAI data center chip investment",
            "url": "https://example.test/openai-capex",
            "candidate_tickers": ["NVDA"],
            "published_at": "2026-07-01T22:00:00+00:00",
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

    rows, summary = build_entity_theme_news_outcome_ledger(
        items,
        ohlcv,
        as_of_date="2026-07-06",
        horizons=(3,),
        notional_usd=4000.0,
    )

    assert summary["settled_count"] == 1
    assert summary["unsettled_count"] == 0
    assert rows[0]["outcome_status"] == "settled"
    assert rows[0]["entity_theme_query_id"] == "frontier_ai_private_capex"
    assert rows[0]["entry_date"] == "2026-07-02"
    assert rows[0]["exit_date"] == "2026-07-06"
    assert rows[0]["pnl_usd"] == 400.0
    assert rows[0]["replacement_value_vs_cash_usd"] == 400.0
    assert rows[0]["replacement_value_vs_spy_usd"] == 280.0
    assert rows[0]["replacement_value_vs_qqq_usd"] == 280.0
    assert rows[0]["trade_enabled"] is False


def test_entity_theme_outcome_ledger_keeps_immature_rows_unsettled():
    items = [
        {
            "entity_theme_query_id": "private_space_launch_contracts",
            "candidate_tickers": ["RKLB"],
            "published_at": "2026-07-01T22:00:00+00:00",
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

    rows, summary = build_entity_theme_news_outcome_ledger(
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


def test_entity_theme_outcome_ledger_separates_future_entry_from_missing_price():
    items = [
        {
            "entity_theme_query_id": "future_session_theme",
            "candidate_tickers": ["FUTR"],
            "published_at": "2026-07-04T22:00:00+00:00",
        },
        {
            "entity_theme_query_id": "missing_ticker_theme",
            "candidate_tickers": ["MISS"],
            "published_at": "2026-07-01T22:00:00+00:00",
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

    rows, summary = build_entity_theme_news_outcome_ledger(
        items,
        ohlcv,
        as_of_date="2026-07-04",
        horizons=(2,),
        notional_usd=4000.0,
    )

    by_query = {row["entity_theme_query_id"]: row for row in rows}
    assert summary["settled_count"] == 0
    assert summary["status_counts"] == {
        "future_entry_session_not_reached": 1,
        "unsettled_no_entry_bar": 1,
    }
    assert (
        by_query["future_session_theme"]["outcome_status"]
        == "future_entry_session_not_reached"
    )
    assert (
        by_query["future_session_theme"]["outcome_status_detail"]
        == "market_calendar_has_no_session_after_observed_date"
    )
    assert by_query["missing_ticker_theme"]["outcome_status"] == "unsettled_no_entry_bar"
    assert (
        by_query["missing_ticker_theme"]["outcome_status_detail"]
        == "market_calendar_has_next_session_but_ticker_missing_bar"
    )


def test_persist_entity_theme_news_outcome_ledger_reads_accumulated_daily_items(
    tmp_path,
):
    base = tmp_path / "non_ohlcv" / "entity_theme_news_observer" / "daily"
    base.mkdir(parents=True)
    (base / "entity_theme_news_observer_20260701.json").write_text(
        json.dumps(
            [
                {
                    "entity_theme_query_id": "frontier_ai_private_capex",
                    "candidate_tickers": ["NVDA"],
                    "published_at": "2026-07-01T22:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    (base / "entity_theme_news_observer_20260703.json").write_text(
        json.dumps(
            [
                {
                    "entity_theme_query_id": "private_space_launch_contracts",
                    "candidate_tickers": ["RKLB"],
                    "published_at": "2026-07-03T22:00:00+00:00",
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

    summary = persist_entity_theme_news_outcome_ledger(
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
