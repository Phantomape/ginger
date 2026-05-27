"""Focused unit tests for broad_market_sector_map.

Covers the read-only lookup contract, coverage reporting, and round-trip
persistence. The actual yfinance fetch in `build_cache` is exercised in the
build script; here we feed a synthetic cache through `load_cache` /
`save_cache` to keep the tests offline.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from broad_market_sector_map import (  # noqa: E402
    DEFAULT_CACHE_PATH,
    FETCH_ERROR_STATUS,
    MISSING_INFO_STATUS,
    MISSING_TICKER_STATUS,
    OK_STATUS,
    RULE_VERSION,
    SOURCE_LABEL,
    coverage_report,
    load_cache,
    lookup_sector,
    save_cache,
    upsert_entry,
)


def _make_cache():
    return {
        "schema_version": 1,
        "rule_version": RULE_VERSION,
        "source": SOURCE_LABEL,
        "generated_at": "2026-05-25T00:00:00Z",
        "entries": {
            "AAPL": {
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "status": OK_STATUS,
                "fetched_at": "2026-05-25T00:00:00Z",
            },
            "JPM": {
                "sector": "Financial Services",
                "industry": "Banks - Diversified",
                "status": OK_STATUS,
                "fetched_at": "2026-05-25T00:00:00Z",
            },
            "BADTICK": {
                "sector": None,
                "industry": None,
                "status": MISSING_INFO_STATUS,
                "fetched_at": "2026-05-25T00:00:00Z",
            },
            "BOOM": {
                "sector": None,
                "industry": None,
                "status": FETCH_ERROR_STATUS,
                "fetched_at": "2026-05-25T00:00:00Z",
            },
        },
    }


def test_lookup_sector_ok():
    cache = _make_cache()
    row = lookup_sector("AAPL", cache=cache)
    assert row["ticker"] == "AAPL"
    assert row["sector"] == "Technology"
    assert row["industry"] == "Consumer Electronics"
    assert row["status"] == OK_STATUS
    assert row["rule_version"] == RULE_VERSION
    assert row["source"] == SOURCE_LABEL
    assert row["fetched_at"] == "2026-05-25T00:00:00Z"


def test_lookup_sector_case_and_whitespace_normalization():
    cache = _make_cache()
    row = lookup_sector("  aapl ", cache=cache)
    assert row["ticker"] == "AAPL"
    assert row["sector"] == "Technology"


def test_lookup_sector_unknown_ticker_returns_missing_ticker_status():
    cache = _make_cache()
    row = lookup_sector("NOPE", cache=cache)
    assert row["status"] == MISSING_TICKER_STATUS
    assert row["sector"] is None
    assert row["industry"] is None
    assert row["rule_version"] == RULE_VERSION


def test_lookup_sector_empty_ticker():
    row = lookup_sector("", cache=_make_cache())
    assert row["status"] == MISSING_TICKER_STATUS
    assert row["sector"] is None


def test_lookup_sector_missing_info_status_round_trip():
    row = lookup_sector("BADTICK", cache=_make_cache())
    assert row["status"] == MISSING_INFO_STATUS
    assert row["sector"] is None
    assert row["industry"] is None


def test_lookup_sector_fetch_error_status_round_trip():
    row = lookup_sector("BOOM", cache=_make_cache())
    assert row["status"] == FETCH_ERROR_STATUS
    assert row["sector"] is None


def test_coverage_report_counts_and_shares():
    cache = _make_cache()
    report = coverage_report(["AAPL", "JPM", "BADTICK", "BOOM", "NOPE"], cache=cache)
    assert report["tickers_requested"] == 5
    assert report["status_counts"][OK_STATUS] == 2
    assert report["status_counts"][MISSING_INFO_STATUS] == 1
    assert report["status_counts"][FETCH_ERROR_STATUS] == 1
    assert report["status_counts"][MISSING_TICKER_STATUS] == 1
    assert report["ok_share"] == round(2 / 5, 6)
    assert report["sector_unique_count"] == 2
    assert "NOPE" in report["unresolved_sample"]


def test_coverage_report_excludes_blanks():
    cache = _make_cache()
    report = coverage_report(["AAPL", "", None, "AAPL"], cache=cache)
    # Duplicates are de-duped via the set in coverage_report; AAPL counted once
    assert report["tickers_requested"] == 1
    assert report["status_counts"][OK_STATUS] == 1


def test_save_cache_then_load_round_trip(tmp_path):
    payload = _make_cache()
    cache_path = tmp_path / "subdir" / "cache.json"
    save_cache(payload, cache_path)
    assert cache_path.exists()
    reloaded = load_cache(cache_path)
    assert reloaded["entries"]["AAPL"]["sector"] == "Technology"
    assert reloaded["rule_version"] == RULE_VERSION
    # generated_at is refreshed by save_cache; ensure it's a valid ISO string
    assert isinstance(reloaded["generated_at"], str)
    assert reloaded["generated_at"].endswith("Z")


def test_load_cache_returns_empty_shell_when_missing(tmp_path):
    cache_path = tmp_path / "does_not_exist.json"
    payload = load_cache(cache_path)
    assert payload["entries"] == {}
    assert payload["rule_version"] == RULE_VERSION
    assert payload["source"] == SOURCE_LABEL


def test_upsert_entry_in_place_overwrites():
    payload = _make_cache()
    upsert_entry(
        payload,
        ticker="aapl",
        sector="Information Technology",
        industry="Hardware",
        status=OK_STATUS,
    )
    assert payload["entries"]["AAPL"]["sector"] == "Information Technology"
    assert payload["entries"]["AAPL"]["industry"] == "Hardware"
    assert "fetched_at" in payload["entries"]["AAPL"]


def test_upsert_entry_ignores_blank_ticker():
    payload = _make_cache()
    before = dict(payload["entries"])
    upsert_entry(payload, ticker="", sector="X", industry=None, status=OK_STATUS)
    assert payload["entries"] == before


def test_default_cache_path_points_inside_repo():
    # Sanity that we point at the canonical reference location and not, say,
    # a checked-in fixture or a tmp dir.
    assert DEFAULT_CACHE_PATH.parent.name == "reference"
    assert DEFAULT_CACHE_PATH.suffix == ".json"
