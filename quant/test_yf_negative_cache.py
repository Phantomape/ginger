"""Tests for the yfinance no-fundamentals negative cache (delisted-symbol skip)."""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

import yf_negative_cache as nc


def _fresh_cache(tmp_path):
    nc.CACHE_PATH = tmp_path / "yf_no_fundamentals_cache.json"
    nc._state = None
    return nc


def test_records_fundamentals_missing_lines(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    log = logging.getLogger("yfinance")

    # Only the reliable 404 fundamentals-not-found line records the symbol.
    log.error('{"description":"No fundamentals data found for symbol: ZZZZ"}')

    assert cache.is_blocked("zzzz")  # normalization is case-insensitive


def test_ignores_transient_price_data_lines(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # Rate-limit / transient price-data lines must NOT blacklist a valid ticker.
    logging.getLogger("yfinance").error("AAPL: possibly delisted; no price data found")
    assert not cache.is_blocked("AAPL")


def test_ignores_bare_no_earnings_dates_line(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # yfinance emits this for valid equities on a transient earnings_dates failure
    # (rate-limit / network blip). It must NOT poison the ticker; only the 404
    # fundamentals-not-found line is a reliable delisting signal.
    logging.getLogger("yfinance").error(
        "AAPL: No earnings dates found, symbol may be delisted"
    )
    assert not cache.is_blocked("AAPL")


def test_ttl_expiry_re_probes(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.record("DEAD")
    assert cache.is_blocked("DEAD", ttl_days=14)

    # Backdate the observation beyond the TTL -> ticker becomes eligible again.
    stale = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    cache._state["DEAD"] = stale
    assert not cache.is_blocked("DEAD", ttl_days=14)


def test_clear_self_heals(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.record("BACK")
    assert cache.is_blocked("BACK")
    cache.clear("BACK")
    assert not cache.is_blocked("BACK")


def test_persists_across_reload(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.record("GONE")
    # Drop the in-memory state to force a fresh load from disk.
    cache._state = None
    assert cache.is_blocked("GONE")
