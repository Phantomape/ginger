"""Tests for the yfinance no-price negative cache (delisted-symbol OHLCV skip)."""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

import yf_no_price_cache as npc


def _fresh_cache(tmp_path):
    npc.CACHE_PATH = tmp_path / "yf_no_price_cache.json"
    npc._state = None
    return npc


def test_records_delisted_no_timezone_lines(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    log = logging.getLogger("yfinance")

    # Single-download form.
    log.error("$NUAN: possibly delisted; no timezone found")
    assert cache.is_blocked("nuan")  # normalization is case-insensitive


def test_records_bulk_bracket_form(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # Bulk/shared download logs the ticker list form.
    logging.getLogger("yfinance").error("['PXD']: possibly delisted; no timezone found")
    assert cache.is_blocked("PXD")


def test_ignores_no_price_data_line(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # A live ticker can emit this on an empty short/holiday window. It must NOT be
    # cached -- only the "no timezone found" variant is a reliable delisting signal.
    logging.getLogger("yfinance").error("AAPL: possibly delisted; no price data found")
    assert not cache.is_blocked("AAPL")


def test_ignores_rate_limit_line(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    logging.getLogger("yfinance").error("Too Many Requests. Rate limited. Try after a while.")
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
