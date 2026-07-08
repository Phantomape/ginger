import logging
import os
import tempfile
import threading
import time

import yfinance.cache as yf_cache

log = logging.getLogger(__name__)


PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "GIT_HTTP_PROXY",
    "GIT_HTTPS_PROXY",
)


def configure_yfinance_runtime():
    """Normalize yfinance runtime settings across all entrypoints."""
    for key in PROXY_ENV_VARS:
        value = os.environ.get(key)
        if value and "127.0.0.1:9" in value:
            os.environ.pop(key, None)

    cache_dir = os.path.join(tempfile.gettempdir(), "ginger_yfinance_cache")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        yf_cache.set_cache_location(cache_dir)
    except Exception:
        pass

    # Observe yfinance's own "no fundamentals / delisted" log lines so we can stop
    # re-requesting those symbols on subsequent runs (self-healing negative cache).
    try:
        from yf_negative_cache import install_yf_log_filter

        install_yf_log_filter()
    except Exception:
        pass

    # Same idea for OHLCV: record symbols yfinance reports as delisted (no timezone)
    # so dead names (NUAN, PXD, MRO, ...) are not re-fetched every run.
    try:
        from yf_no_price_cache import install_yf_log_filter as install_no_price_filter

        install_no_price_filter()
    except Exception:
        pass

    return cache_dir


# ── Rate-limit-aware retry (exp-20260708-008) ────────────────────────────────
#
# yf.download swallows per-ticker YFRateLimitError internally: it logs
# "ERROR yfinance: ['SPY']: YFRateLimitError(...)" and returns an empty slice,
# so callers cannot catch the exception — the only reliable per-call signal is
# yfinance.shared._ERRORS (reset at the start of every download call). Yahoo
# rate limits usually clear within a minute; retrying with backoff recovers the
# fetch instead of silently degrading regime/OHLCV/trend inputs to "no data".

_RATE_LIMIT_SIGNATURES = ("YFRateLimitError", "Too Many Requests", "Rate limited")

# Rate limiting is vendor-global, so one process fetching ~1300 names must not
# stack per-ticker retries into an unbounded stall: all sleeps share one
# process-wide budget. When it is exhausted, calls degrade to today's
# single-attempt behavior.
_DEFAULT_SLEEP_BUDGET_S = 600.0
_sleep_budget_lock = threading.Lock()
_sleep_budget_used_s = 0.0


def _sleep_budget_total_s() -> float:
    try:
        return float(os.environ.get("GINGER_YF_RATE_LIMIT_SLEEP_BUDGET_S", ""))
    except ValueError:
        return _DEFAULT_SLEEP_BUDGET_S


def _consume_sleep_budget(wanted_s: float) -> float:
    """Reserve up to ``wanted_s`` from the shared budget; returns the grant."""
    global _sleep_budget_used_s
    with _sleep_budget_lock:
        remaining = _sleep_budget_total_s() - _sleep_budget_used_s
        grant = max(0.0, min(float(wanted_s), remaining))
        _sleep_budget_used_s += grant
        return grant


def is_rate_limit_error(error) -> bool:
    """True when an exception/message carries a Yahoo rate-limit signature."""
    text = repr(error) if isinstance(error, BaseException) else str(error)
    return any(signature in text for signature in _RATE_LIMIT_SIGNATURES)


def rate_limited_tickers() -> list[str]:
    """Tickers the LAST yf.download call dropped due to rate limiting."""
    try:
        import yfinance.shared as yf_shared

        errors = dict(getattr(yf_shared, "_ERRORS", None) or {})
    except Exception:
        return []
    return sorted(
        str(ticker)
        for ticker, message in errors.items()
        if is_rate_limit_error(message)
    )


def download_with_rate_limit_retry(
    *args,
    max_attempts: int = 4,
    base_delay_s: float = 15.0,
    retry_logger=None,
    **kwargs,
):
    """``yf.download`` that retries while Yahoo is rate limiting.

    Returns whatever the last attempt returned (possibly an empty frame), so
    existing "empty -> None" caller behavior is unchanged when the limit
    outlives the retries or the sleep budget.
    """
    import yfinance as yf

    logger = retry_logger or log
    delay = float(base_delay_s)
    for attempt in range(1, max_attempts + 1):
        data = None
        raised_exc = None
        try:
            data = yf.download(*args, **kwargs)
            limited = rate_limited_tickers()
        except Exception as exc:
            # Direct-raise path (e.g. single ticker with raise_errors=True).
            if not is_rate_limit_error(exc):
                raise
            raised_exc = exc
            limited = ["<raised>"]
        if not limited:
            return data
        if attempt == max_attempts:
            logger.error(
                "yfinance still rate limited after %d attempts (%s); giving up",
                max_attempts,
                ", ".join(limited[:8]),
            )
            if raised_exc is not None:
                raise raised_exc
            return data
        grant = _consume_sleep_budget(delay)
        if grant <= 0.0:
            logger.error(
                "yfinance rate limited (%s) but process retry sleep budget is "
                "exhausted; giving up",
                ", ".join(limited[:8]),
            )
            if raised_exc is not None:
                raise raised_exc
            return data
        logger.warning(
            "yfinance rate limited (%s); retry %d/%d in %.0fs",
            ", ".join(limited[:8]) + ("..." if len(limited) > 8 else ""),
            attempt,
            max_attempts - 1,
            grant,
        )
        time.sleep(grant)
        delay *= 2


def call_with_rate_limit_retry(
    fn,
    *,
    what: str = "yfinance call",
    max_attempts: int = 4,
    base_delay_s: float = 15.0,
    retry_logger=None,
):
    """Run ``fn()`` retrying on raised Yahoo rate-limit errors.

    For yf.Ticker property/method paths (.info, .history, .earnings_dates,
    .fast_info), which raise YFRateLimitError directly instead of logging it.
    """
    logger = retry_logger or log
    delay = float(base_delay_s)
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_rate_limit_error(exc) or attempt == max_attempts:
                raise
            grant = _consume_sleep_budget(delay)
            if grant <= 0.0:
                logger.error(
                    "%s rate limited but process retry sleep budget is "
                    "exhausted; giving up",
                    what,
                )
                raise
            logger.warning(
                "%s rate limited; retry %d/%d in %.0fs",
                what,
                attempt,
                max_attempts - 1,
                grant,
            )
            time.sleep(grant)
            delay *= 2
