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

The recorded signal is deliberately narrow: yfinance's ``possibly delisted; no timezone
found`` line only. A valid security *always* has a timezone, and that check fires before
any date window is even considered, so this signal cannot be produced by a live ticker
that merely had an empty short/holiday fetch window. The broader ``no price data found``
line is NOT matched -- a live ticker can emit it for a 1-2 day weekend gap, which would
wrongly suppress its price (and price feeds trading decisions). Rate-limit errors carry
a different message entirely, so transient 429s never poison the cache.

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
# Only the "no timezone found" variant is matched -- see module docstring for why the
# broader "no price data found" line is deliberately excluded.
_DELISTED_NO_TZ_RE = re.compile(
    r"([A-Z][A-Z0-9.\-]{0,9})['\]]{0,2}:\s*possibly delisted;\s*no timezone found"
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


class _DelistedNoTzFilter(logging.Filter):
    """Records (does not drop) yfinance 'possibly delisted; no timezone' log lines."""

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
        return True  # never suppress; next run skips the request so the line stops


_filter_installed = False


def install_yf_log_filter() -> None:
    """Attach the recorder to the ``yfinance`` logger (idempotent)."""
    global _filter_installed
    if _filter_installed:
        return
    with _lock:
        if _filter_installed:
            return
        logging.getLogger("yfinance").addFilter(_DelistedNoTzFilter())
        _filter_installed = True
