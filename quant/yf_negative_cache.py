"""Persistent negative cache for tickers yfinance reports as delisted / no-fundamentals.

yfinance re-issues (and 404s) on *every* daily run for symbols that have no company
fundamentals -- theme/benchmark ETFs (ARKX, UFO, SPCX ...) and genuinely delisted
stocks. Those wasted HTTP round-trips slow the pipeline and bury the logs in repeated
``No fundamentals data found for symbol`` / ``symbol may be delisted`` errors.

The well-known, never-changing ETFs live in :mod:`earnings_assets`. This module handles
the *open-ended* case -- a stock that delists later -- without hand-maintaining a list:

  * A logging filter installed on the ``yfinance`` logger observes yfinance's own
    "no fundamentals / delisted" lines and records the offending ticker here.
  * Earnings entry points (:func:`data_layer.get_earnings_data`,
    :func:`fetch_broad_earnings_snapshot._fetch_one_ticker`) skip a ticker that is
    cached, avoiding the wasted request entirely.
  * Entries expire after :data:`DEFAULT_TTL_DAYS`, so a symbol that becomes valid again
    (re-listing, late-arriving fundamentals) is eventually re-probed -- the cache never
    permanently blacklists a name.

Persistence is best-effort: the cache is a pure latency/noise optimization, so a failed
write (the repo's known WinError-5 atomic-rename flakiness under concurrent agents) is
swallowed and retried on the next observation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone

from operator_input_paths import REPO_ROOT

logger = logging.getLogger(__name__)

CACHE_PATH = REPO_ROOT / "data" / "reference" / "yf_no_fundamentals_cache.json"

# How long a "no fundamentals" observation suppresses re-querying before we re-probe.
# Long enough to skip a symbol for many runs, short enough to self-heal within ~2 weeks.
DEFAULT_TTL_DAYS = 14

_lock = threading.RLock()
_state: dict[str, str] | None = None  # {"TICKER": "<iso8601 last observed>"}

# yfinance logs missing-fundamentals / delisting as, e.g.:
#   "MUU: No earnings dates found, symbol may be delisted"
#   'HTTP Error 404: ... "No fundamentals data found for symbol: MUU" ...'
# Only the 404 *fundamentals-not-found* line is matched -- it is the single reliable,
# stable signal (a security either has company fundamentals or does not). The bare
# "No earnings dates found, symbol may be delisted" line is deliberately NOT matched:
# yfinance emits it for perfectly valid equities whenever the earnings_dates request
# merely fails transiently (rate-limit 429, network blip), which would poison mega-caps
# like AAPL/AMD for the full TTL. A genuinely delisted / fundamentals-less symbol always
# also produces the 404 line, so coverage is preserved without the false positives.
_FUNDAMENTALS_MISSING_RE = (
    re.compile(r"No fundamentals data found for symbol:\s*([A-Z][A-Z0-9.\-]{0,9})"),
)


def _normalize(ticker) -> str:
    return str(ticker or "").strip().upper()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict[str, str]:
    global _state
    if _state is not None:
        return _state
    with _lock:
        if _state is not None:
            return _state
        data: dict[str, str] = {}
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                data = {
                    _normalize(k): str(v)
                    for k, v in raw.items()
                    if _normalize(k) and isinstance(v, str)
                }
        except FileNotFoundError:
            pass
        except Exception as exc:  # corrupt cache -> start clean, never fatal
            logger.debug("yf negative cache load failed (%s); starting empty", exc)
        _state = data
        return _state


def _save(state: dict[str, str]) -> None:
    """Persist best-effort; swallow the repo's known atomic-rename flakiness."""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        tmp = f"{CACHE_PATH}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
        try:
            os.replace(tmp, CACHE_PATH)
        except OSError:
            # Atomic rename denied (concurrent agent / AV). Fall back to a direct
            # overwrite so the cache still advances; leftover tmp is harmless.
            with open(CACHE_PATH, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, sort_keys=True)
            try:
                os.remove(tmp)
            except OSError:
                pass
    except Exception as exc:
        logger.debug("yf negative cache save failed (%s); keeping in-memory only", exc)


def _age_days(iso: str) -> float | None:
    try:
        seen = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return (_now() - seen).total_seconds() / 86400.0


def is_blocked(ticker, ttl_days: float = DEFAULT_TTL_DAYS) -> bool:
    """Return True if ``ticker`` was recently observed as having no fundamentals."""
    sym = _normalize(ticker)
    if not sym:
        return False
    state = _load()
    iso = state.get(sym)
    if iso is None:
        return False
    age = _age_days(iso)
    if age is None or age >= ttl_days:
        return False
    return True


def record(ticker) -> None:
    """Note that yfinance reported ``ticker`` as delisted / missing fundamentals."""
    sym = _normalize(ticker)
    if not sym:
        return
    with _lock:
        state = _load()
        existed = sym in state
        state[sym] = _now().isoformat()
        _save(state)
    if not existed:
        logger.info(
            "yfinance reports no fundamentals for %s; suppressing earnings requests "
            "for up to %d days",
            sym,
            DEFAULT_TTL_DAYS,
        )


def clear(ticker) -> None:
    """Drop a ticker from the cache once it returns real data (self-heal)."""
    sym = _normalize(ticker)
    if not sym:
        return
    with _lock:
        state = _load()
        if sym in state:
            del state[sym]
            _save(state)


class _FundamentalsMissingFilter(logging.Filter):
    """Records (does not drop) yfinance 'no fundamentals / delisted' log lines."""

    def filter(self, log_record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            msg = log_record.getMessage()
        except Exception:
            return True
        for rx in _FUNDAMENTALS_MISSING_RE:
            match = rx.search(msg)
            if match:
                try:
                    record(match.group(1))
                except Exception:
                    pass
                break
        return True  # never suppress; next run skips the request so the line stops


_filter_installed = False


def install_yf_log_filter() -> None:
    """Attach the recorder to the ``yfinance`` logger (idempotent)."""
    global _filter_installed
    yf_logger = logging.getLogger("yfinance")
    if _filter_installed and any(
        isinstance(existing, _FundamentalsMissingFilter)
        for existing in yf_logger.filters
    ):
        return
    with _lock:
        if any(
            isinstance(existing, _FundamentalsMissingFilter)
            for existing in yf_logger.filters
        ):
            _filter_installed = True
            return
        yf_logger.addFilter(_FundamentalsMissingFilter())
        _filter_installed = True
