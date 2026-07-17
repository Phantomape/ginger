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


def test_ignores_no_price_data_line_without_window(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # No parseable request window -> cannot rule out a short-gap false positive.
    logging.getLogger("yfinance").error("AAPL: possibly delisted; no price data found")
    assert not cache.is_blocked("AAPL")


def test_ignores_no_price_data_short_window(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # A live ticker can emit this over a weekend/holiday gap. Short windows must
    # never be cached (exp-20260717-001).
    logging.getLogger("yfinance").error(
        "$AAPL: possibly delisted; no price data found  "
        "(1d 2026-07-11 09:00:00.000000 -> 2026-07-13 09:00:00.000000)"
    )
    assert not cache.is_blocked("AAPL")


def test_records_no_price_data_long_window_single(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # Verbatim shape from data/logs/run_20260715.log (13-month window, dead ticker).
    logging.getLogger("yfinance").error(
        "$SATS: possibly delisted; no price data found  "
        "(1d 2025-06-10 22:30:23.776321 -> 2026-07-15 22:30:23.776321)"
    )
    assert cache.is_blocked("SATS")


def test_records_no_price_data_long_window_bulk_list(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # Bulk form lists every failed symbol in one bracket; all must be recorded.
    logging.getLogger("yfinance").error(
        "['SATS', 'IAC', 'BK']: possibly delisted; no price data found  "
        "(1d 2026-06-15 22:31:18.744847 -> 2026-07-15 22:31:18.744847)"
    )
    assert cache.is_blocked("SATS")
    assert cache.is_blocked("IAC")
    assert cache.is_blocked("BK")


def test_records_no_price_data_with_yahoo_error_suffix(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # CTRA/CUK/TPH shape: window plus '(Yahoo error = "...")' suffix.
    logging.getLogger("yfinance").error(
        "$CTRA: possibly delisted; no price data found  "
        "(1d 2026-04-16 22:31:19.664944 -> 2026-07-15 22:31:19.664944) "
        '(Yahoo error = "No data found, symbol may be delisted")'
    )
    assert cache.is_blocked("CTRA")


def test_no_price_rate_limit_message_not_poisoned(tmp_path):
    cache = _fresh_cache(tmp_path)
    cache.install_yf_log_filter()
    # Rate-limit failures carry a different message and must never be cached,
    # even in the bulk bracket form.
    logging.getLogger("yfinance").error(
        "['CTRA']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"
    )
    assert not cache.is_blocked("CTRA")


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
