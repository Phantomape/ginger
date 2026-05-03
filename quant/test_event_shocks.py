from __future__ import annotations

import json
from pathlib import Path

from event_shocks import build_event_snapshot
from parser import normalize_entry


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_normalize_entry_keeps_sec_metadata():
    entry = {
        "title": "ACME files 8-K Item 2.02 after raising outlook",
        "link": "https://example.com/sec/8k",
        "summary": "ACME files 8-K Item 2.02 and raises guidance.",
        "published": "2026-05-02T12:00:00Z",
    }
    item = normalize_entry(
        entry,
        "https://www.sec.gov/feed",
        "sec",
        {"filing_type": "8-K"},
    )
    assert item["filing_type"] == "8-K"
    assert item["source_metadata"]["filing_type"] == "8-K"


def test_build_event_snapshot_classifies_earnings_and_sec(tmp_path: Path):
    _write_json(
        tmp_path / "earnings_snapshot_20260502.json",
        {
            "date": "20260502",
            "earnings": {
                "ACME": {
                    "days_to_earnings": 0,
                    "eps_estimate": 1.2,
                    "eps_actual_last": 1.4,
                    "avg_historical_surprise_pct": 12.5,
                    "historical_surprise_pct": [8.0, 10.0, 15.0],
                }
            },
        },
    )
    _write_json(
        tmp_path / "news_20260502.json",
        [
            {
                "source": "google_news",
                "title": "ACME beats revenue and raises guidance as gross margin expands",
                "summary": "Strong free cash flow offset inventory pressure.",
                "url": "https://example.com/acme",
                "published_at": "2026-05-02T10:00:00Z",
                "tickers": ["ACME"],
                "raw_source": "https://news.google.com",
            },
            {
                "source": "sec",
                "title": "ACME files 8-K Item 2.02 Results of Operations",
                "summary": "Item 2.02 earnings release.",
                "url": "https://www.sec.gov/acme-8k",
                "published_at": "2026-05-02T11:00:00Z",
                "tickers": ["ACME"],
                "raw_source": "https://www.sec.gov/feed",
                "filing_type": "8-K",
                "source_metadata": {"filing_type": "8-K"},
            },
        ],
    )

    payload = build_event_snapshot(
        "20260502",
        data_dir=tmp_path,
        universe=["ACME"],
        persist=False,
    )
    assert payload["coverage"]["tickers_with_dte0_event"] == 1
    assert payload["coverage"]["sec_items_mapped_to_ticker"] == 1
    events = payload["events_by_ticker"]["ACME"]
    earnings_event = next(event for event in events if event["event_type"] == "earnings")
    assert earnings_event["surprise_direction"] == "mixed"
    assert earnings_event["surprise_strength"] == "high"
    assert "guidance_raise" in earnings_event["headline_buckets"]
    assert "revenue_up" in earnings_event["headline_buckets"]
    assert "margin_up" in earnings_event["headline_buckets"]
    assert "inventory_warning" in earnings_event["headline_buckets"]
    assert earnings_event["field_availability"]["sue_proxy"] == "derived"
    sec_event = next(event for event in events if event["event_type"] == "8k")
    assert sec_event["event_subtype"] == "8k_item_2_02"
    assert sec_event["field_availability"]["sec_filing_type"] == "derived"


def test_build_event_snapshot_records_unmapped_sec_items(tmp_path: Path):
    _write_json(tmp_path / "earnings_snapshot_20260502.json", {"date": "20260502", "earnings": {}})
    _write_json(
        tmp_path / "news_20260502.json",
        [
            {
                "source": "sec",
                "title": "Unknown issuer files 10-Q",
                "summary": "",
                "url": "https://www.sec.gov/unknown-10q",
                "published_at": "2026-05-02T11:00:00Z",
                "tickers": [],
                "raw_source": "https://www.sec.gov/feed",
                "filing_type": "10-Q",
            }
        ],
    )

    payload = build_event_snapshot("20260502", data_dir=tmp_path, universe=["ACME"], persist=False)
    assert payload["coverage"]["sec_items_total"] == 1
    assert payload["coverage"]["sec_items_mapped_to_ticker"] == 0
    assert payload["coverage"]["sec_items_unmapped"] == 1
    assert payload["unmapped_sec_items"][0]["sec_cik"] is None
