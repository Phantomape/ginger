"""Persistent negative cache for tickers yfinance reports as delisted (no price data).

The broad refresh universe (``pead_broad_universe_tickers`` + sector cache) carries a
long tail of names that have been acquired or delisted -- NUAN (Microsoft, 2022), PXD
(ExxonMobil, 2024), MRO (ConocoPhillips, 2024) -- plus the odd bad symbol (``GARTNER``;
the real ticker is ``IT``). None of these ever accumulate warehouse rows, so the
incremental refresh plans them at ``last_date is None`` -> full max-lookback fetch on
*every* run, forever. Each is a wasted HTTP round-trip that returns nothing and logs
``<ticker>: no OHLCV data returned``.

This is the price-data analogue of :mod:`yf_negative_cache` (which handles missing
*fundamentals*). It records the symbols and skips re-fetching them for a TTL, then
re-probes so a re-listing eventually self-heals -- the cache never permanently
blacklists a name.

Two signals are recorded (exp-20260717-001 added the second):

1. ``possibly delisted; no timezone found`` -- a valid security *always* has a
   timezone, and that check fires before any date window is even considered, so this
   signal cannot be produced by a live ticker that merely had an empty short/holiday
   fetch window.
2. ``possibly delisted; no price data found`` -- but **only** when the request window
   embedded in the message itself spans >= ``MIN_NO_PRICE_WINDOW_DAYS``. A live ticker
   can emit this line for a 1-2 day weekend/holiday gap (which is why the bare line was
   originally excluded), but zero rows across a month-long window cannot come from a
   calendar gap. Observed cost of the gap: SATS/IAC/BK (dead since 2025-06), CTRA/CUK/
   TPH (2026-04), BOK/SFG (2025-05) were re-fetched at full lookback on every daily run
   and burned retry quota against a rate-limited vendor (run log 2026-07-15).

Rate-limit errors carry a different message entirely, so transient 429s never poison
the cache. A wrongly-cached live ticker self-heals two ways: the TTL re-probe, and
``clear()`` on the first successful fetch.

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

CACHE_PATH = REPO_ROOT / "data" / "reference" / "yf_no_price_cache.json"

# How long a "delisted / no timezone" observation suppresses re-querying before we
# re-probe. Long enough to skip a dead symbol for many runs, short enough that a
# re-listing self-heals within ~2 weeks.
DEFAULT_TTL_DAYS = 14

_lock = threading.RLock()
_state: dict[str, str] | None = None  # {"TICKER": "<iso8601 last observed>"}

# yfinance logs a genuinely unknown / delisted symbol (in both single and bulk
# downloads) as, e.g.:
#   "$NUAN: possibly delisted; no timezone found"
#   "['NUAN']: possibly delisted; no timezone found"   (bulk/shared form)
_DELISTED_NO_TZ_RE = re.compile(
    r"([A-Z][A-Z0-9.\-]{0,9})['\]]{0,2}:\s*possibly delisted;\s*no timezone found"
)

# The "no price data found" shape carries the requested window in the message, single
# and bulk forms alike (bulk lists every failed symbol in one bracket):
#   "$SATS: possibly delisted; no price data found  (1d 2025-06-10 22:30:23 -> 2026-07-15 22:30:23)"
#   "['SATS', 'IAC', 'BK']: possibly delisted; no price data found  (1d 2026-06-15 ... -> 2026-07-15 ...)"
# Optionally suffixed with '(Yahoo error = "...")'. Recorded only when the window spans
# >= MIN_NO_PRICE_WINDOW_DAYS -- see module docstring.
_DELISTED_NO_PRICE_RE = re.compile(
    r"(?P<tickers>[A-Z][A-Z0-9.\-]{0,9}(?:['\],\s]+[A-Z][A-Z0-9.\-]{0,9})*)"
    r"['\]]*:\s*possibly delisted;\s*no price data found\s*"
    r"\(\s*\S+\s+(?P<start>\d{4}-\d{2}-\d{2})[^)]*?->\s*(?P<end>\d{4}-\d{2}-\d{2})"
)

# Minimum request-window span (calendar days) before a zero-row "no price data found"
# response is treated as delisted. US markets never close for more than a few
# consecutive days, so a live ticker cannot produce an empty month; month-long halts
# are rare and self-heal via TTL + clear-on-real-data.
MIN_NO_PRICE_WINDOW_DAYS = 25

_TICKER_SPLIT_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


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
            logger.debug("yf no-price cache load failed (%s); starting empty", exc)
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
        logger.debug("yf no-price cache save failed (%s); keeping in-memory only", exc)


def _age_days(iso: str) -> float | None:
    try:
        seen = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return (_now() - seen).total_seconds() / 86400.0


def is_blocked(ticker, ttl_days: float = DEFAULT_TTL_DAYS) -> bool:
    """Return True if ``ticker`` was recently observed as delisted (no timezone)."""
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
    """Note that yfinance reported ``ticker`` as delisted / no timezone."""
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
            "yfinance reports %s as delisted (no timezone); suppressing OHLCV "
            "requests for up to %d days",
            sym,
            DEFAULT_TTL_DAYS,
        )


def clear(ticker) -> None:
    """Drop a ticker from the cache once it returns real OHLCV again (self-heal)."""
    sym = _normalize(ticker)
    if not sym:
        return
    with _lock:
        state = _load()
        if sym in state:
            del state[sym]
            _save(state)


def _no_price_window_days(match: re.Match) -> float | None:
    try:
        start = datetime.strptime(match.group("start"), "%Y-%m-%d")
        end = datetime.strptime(match.group("end"), "%Y-%m-%d")
    except ValueError:
        return None
    return (end - start).total_seconds() / 86400.0


class _DelistedNoTzFilter(logging.Filter):
    """Records (does not drop) yfinance delisted-symbol log lines.

    Matches 'no timezone found' unconditionally and 'no price data found' only for
    long request windows (see module docstring).
    """

    def filter(self, log_record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            msg = log_record.getMessage()
        except Exception:
            return True
        match = _DELISTED_NO_TZ_RE.search(msg)
        if match:
            try:
                record(match.group(1))
            except Exception:
                pass
            return True
        match = _DELISTED_NO_PRICE_RE.search(msg)
        if match:
            try:
                window = _no_price_window_days(match)
                if window is not None and window >= MIN_NO_PRICE_WINDOW_DAYS:
                    for sym in _TICKER_SPLIT_RE.findall(match.group("tickers")):
                        record(sym)
            except Exception:
                pass
        return True  # never suppress; next run skips the request so the line stops


_filter_installed = False


def install_yf_log_filter() -> None:
    """Attach the recorder to the ``yfinance`` logger (idempotent)."""
    global _filter_installed
    yf_logger = logging.getLogger("yfinance")
    yf_logger.disabled = False
    if yf_logger.level == logging.NOTSET or yf_logger.level > logging.ERROR:
        yf_logger.setLevel(logging.ERROR)
    if _filter_installed and any(
        isinstance(existing, _DelistedNoTzFilter) for existing in yf_logger.filters
    ):
        return
    with _lock:
        if any(
            isinstance(existing, _DelistedNoTzFilter)
            for existing in yf_logger.filters
        ):
            _filter_installed = True
            return
        yf_logger.addFilter(_DelistedNoTzFilter())
        _filter_installed = True
