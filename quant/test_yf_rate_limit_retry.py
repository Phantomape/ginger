"""Tests for the rate-limit-aware yfinance retry wrapper (exp-20260708-008)."""

from __future__ import annotations

import pandas as pd
import pytest

import yfinance
import yfinance.shared as yf_shared

import yfinance_bootstrap as yb


RATE_LIMIT_MSG = "YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.setattr(yf_shared, "_ERRORS", {}, raising=False)
    monkeypatch.setattr(yb, "_sleep_budget_used_s", 0.0)
    monkeypatch.delenv("GINGER_YF_RATE_LIMIT_SLEEP_BUDGET_S", raising=False)
    # No real sleeping in tests; record requested delays instead.
    sleeps: list[float] = []
    monkeypatch.setattr(yb.time, "sleep", sleeps.append)
    yield sleeps


def test_is_rate_limit_error_matches_signatures():
    assert yb.is_rate_limit_error(RATE_LIMIT_MSG)
    assert yb.is_rate_limit_error(Exception("Too Many Requests. Rate limited."))
    assert not yb.is_rate_limit_error("HTTP Error 404: Not Found")


def test_download_retries_until_rate_limit_clears(monkeypatch, _clean_state):
    frames = [pd.DataFrame(), pd.DataFrame(), pd.DataFrame({"Close": [1.0, 2.0]})]
    calls = {"n": 0}

    def fake_download(*args, **kwargs):
        index = calls["n"]
        calls["n"] += 1
        yf_shared._ERRORS = {"SPY": RATE_LIMIT_MSG} if index < 2 else {}
        return frames[index]

    monkeypatch.setattr(yfinance, "download", fake_download)
    result = yb.download_with_rate_limit_retry("SPY", progress=False)

    assert calls["n"] == 3
    assert list(result["Close"]) == [1.0, 2.0]
    assert _clean_state == [15.0, 30.0]  # exponential backoff actually slept


def test_download_gives_up_after_max_attempts(monkeypatch, _clean_state):
    calls = {"n": 0}

    def always_limited(*args, **kwargs):
        calls["n"] += 1
        yf_shared._ERRORS = {"SPY": RATE_LIMIT_MSG}
        return pd.DataFrame()

    monkeypatch.setattr(yfinance, "download", always_limited)
    result = yb.download_with_rate_limit_retry("SPY", max_attempts=3)

    assert calls["n"] == 3
    assert result.empty  # same degraded shape callers already handle


def test_download_does_not_retry_non_rate_limit_errors(monkeypatch, _clean_state):
    calls = {"n": 0}

    def delisted(*args, **kwargs):
        calls["n"] += 1
        yf_shared._ERRORS = {"NUAN": "YFTzMissingError('possibly delisted')"}
        return pd.DataFrame()

    monkeypatch.setattr(yfinance, "download", delisted)
    result = yb.download_with_rate_limit_retry("NUAN")

    assert calls["n"] == 1  # single attempt, no sleeping
    assert _clean_state == []
    assert result.empty


def test_download_respects_process_sleep_budget(monkeypatch, _clean_state):
    monkeypatch.setenv("GINGER_YF_RATE_LIMIT_SLEEP_BUDGET_S", "0")
    calls = {"n": 0}

    def always_limited(*args, **kwargs):
        calls["n"] += 1
        yf_shared._ERRORS = {"SPY": RATE_LIMIT_MSG}
        return pd.DataFrame()

    monkeypatch.setattr(yfinance, "download", always_limited)
    yb.download_with_rate_limit_retry("SPY")

    assert calls["n"] == 1  # budget exhausted -> no retries
    assert _clean_state == []


def test_download_reraises_direct_rate_limit_exception(monkeypatch, _clean_state):
    def raises(*args, **kwargs):
        raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")

    monkeypatch.setattr(yfinance, "download", raises)
    with pytest.raises(RuntimeError):
        yb.download_with_rate_limit_retry("SPY", max_attempts=2)
    assert _clean_state == [15.0]  # retried once, then re-raised


def test_call_with_rate_limit_retry_recovers(_clean_state):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(RATE_LIMIT_MSG)
        return "ok"

    assert yb.call_with_rate_limit_retry(flaky, what="fast_info") == "ok"
    assert calls["n"] == 3
    assert _clean_state == [15.0, 30.0]


def test_call_with_rate_limit_retry_passes_through_other_errors(_clean_state):
    def broken():
        raise ValueError("schema drift")

    with pytest.raises(ValueError):
        yb.call_with_rate_limit_retry(broken)
    assert _clean_state == []


def test_daily_call_sites_use_the_wrapper():
    # Wiring proof: the daily pipeline's download paths must not call
    # yf.download directly anymore (rate-limited fetches would silently
    # degrade to "no data" again).
    from pathlib import Path

    quant_dir = Path(__file__).resolve().parent
    for module in ("regime.py", "data_layer.py", "trend_signals.py", "crypto_sleeve.py"):
        source = (quant_dir / module).read_text(encoding="utf-8")
        assert "yf.download(" not in source, f"{module} still calls yf.download directly"
        assert "download_with_rate_limit_retry(" in source, f"{module} not wired to retry wrapper"
