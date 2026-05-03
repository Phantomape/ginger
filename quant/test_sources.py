import os
import sys
import json
from types import SimpleNamespace


sys.path.insert(0, os.path.dirname(__file__))

from sources import get_all_sources  # noqa: E402
from parser import normalize_entry, parse_feed_with_diagnostics  # noqa: E402
from sec_ticker_map import load_company_ticker_map, parse_sec_title  # noqa: E402


def test_get_all_sources_adds_extra_ticker_google_feeds():
    sources = get_all_sources(extra_tickers=["INTC", "LITE", "BE"])
    urls = [source["url"] for source in sources]

    assert any("q=INTC+stock" in url for url in urls)
    assert any("q=LITE+stock" in url for url in urls)
    assert any("q=BE+stock" in url for url in urls)


def test_get_all_sources_does_not_duplicate_existing_google_feed():
    sources = get_all_sources(extra_tickers=["AMD"])
    amd_sources = [
        source for source in sources
        if source.get("metadata", {}).get("keywords") == ["AMD"]
    ]

    assert len(amd_sources) == 1


def test_parse_feed_with_diagnostics_uses_sec_headers(monkeypatch):
    captured = {}

    def fake_parse(url, request_headers=None):
        captured["url"] = url
        captured["request_headers"] = request_headers
        return SimpleNamespace(entries=[], bozo=False, status=200)

    monkeypatch.setattr("parser.feedparser.parse", fake_parse)

    items, diagnostics = parse_feed_with_diagnostics(
        "https://www.sec.gov/feed",
        "sec",
        {"filing_type": "8-K", "user_agent": "ginger-test/1.0"},
    )

    assert items == []
    assert captured["request_headers"]["User-Agent"] == "ginger-test/1.0"
    assert diagnostics["source_type"] == "sec"
    assert diagnostics["status"] == 200
    assert diagnostics["entry_count"] == 0
    assert diagnostics["parsed_item_count"] == 0


def test_parse_feed_with_diagnostics_omits_headers_for_google(monkeypatch):
    captured = {}

    def fake_parse(url, request_headers=None):
        captured["request_headers"] = request_headers
        return SimpleNamespace(entries=[], bozo=False, status=200)

    monkeypatch.setattr("parser.feedparser.parse", fake_parse)

    _, diagnostics = parse_feed_with_diagnostics(
        "https://news.google.com/rss",
        "google_news",
        {"keywords": ["AMD"]},
    )

    assert captured["request_headers"] is None
    assert diagnostics["request_headers_used"] == {}


def test_parse_sec_title_extracts_company_and_cik():
    parsed = parse_sec_title("10-Q - ROPER TECHNOLOGIES INC (0000882835) (Filer)")

    assert parsed["filing_form"] == "10-Q"
    assert parsed["company_name"] == "ROPER TECHNOLOGIES INC"
    assert parsed["cik"] == "0000882835"
    assert parsed["filer_role"] == "Filer"


def test_load_company_ticker_map_supports_sec_json_shape(tmp_path):
    cache = tmp_path / "company_tickers.json"
    cache.write_text(
        json.dumps({"0": {"cik_str": 882835, "ticker": "ROP", "title": "ROPER TECHNOLOGIES INC"}}),
        encoding="utf-8",
    )

    mapping = load_company_ticker_map(cache)

    assert mapping["0000882835"]["ticker"] == "ROP"


def test_normalize_entry_maps_sec_cik_to_ticker(tmp_path):
    cache = tmp_path / "company_tickers.json"
    cache.write_text(
        json.dumps({"0": {"cik_str": 882835, "ticker": "ROP", "title": "ROPER TECHNOLOGIES INC"}}),
        encoding="utf-8",
    )
    entry = {
        "title": "10-Q - ROPER TECHNOLOGIES INC (0000882835) (Filer)",
        "link": "https://www.sec.gov/Archives/edgar/data/882835/example-index.htm",
        "summary": "<b>Filed:</b> 2026-05-01 <br />Item 2.02: Results of Operations",
        "updated": "2026-05-01T17:29:40-04:00",
    }

    item = normalize_entry(
        entry,
        "https://www.sec.gov/feed",
        "sec",
        {"filing_type": "10-Q", "sec_company_tickers_path": str(cache)},
    )

    assert item["tickers"] == ["ROP"]
    assert item["sec_cik"] == "0000882835"
    assert item["sec_company_name"] == "ROPER TECHNOLOGIES INC"
    assert item["source_metadata"]["sec_ticker"] == "ROP"
    assert "sec_company_tickers_path" not in item["source_metadata"]


def test_normalize_entry_uses_cik_mapping_not_sec_title_text_tickers(tmp_path):
    cache = tmp_path / "company_tickers.json"
    cache.write_text(
        json.dumps({"0": {"cik_str": 1015739, "ticker": "AWRE", "title": "AWARE INC /MA/"}}),
        encoding="utf-8",
    )
    entry = {
        "title": "10-Q - AWARE INC /MA/ (0001015739) (Filer)",
        "link": "https://www.sec.gov/Archives/edgar/data/1015739/example-index.htm",
        "summary": "<b>Filed:</b> 2026-05-01",
        "updated": "2026-05-01T17:29:40-04:00",
    }

    item = normalize_entry(
        entry,
        "https://www.sec.gov/feed",
        "sec",
        {"filing_type": "10-Q", "sec_company_tickers_path": str(cache)},
    )

    assert item["tickers"] == ["AWRE"]
