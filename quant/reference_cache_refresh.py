"""Throttled daily refreshers for unowned reference caches.

exp-20260612-009: ``data/reference/broad_market_sector_map.json`` and
``data/reference/sec_company_tickers.json`` are read by the daily pipeline but
nothing on the daily path refreshes them, so they go stale (the sector map
anchors the broad-universe feed). This module keeps them fresh from the daily
run with conservative throttles and env opt-outs.

- Sector map: rolling batch. Each call refreshes only the oldest/missing slice
  (capped per day) so a ~1200-name universe is re-queried over several days
  rather than in one yfinance storm.
- SEC company tickers: weekly. A single small HTTP GET, refreshed when the
  cache is older than the TTL.

Companyfacts is intentionally out of scope here - exp-20260613-023 already
wired its broad-universe refresh on the daily path.

Data-only: no signals, orders, ranking, sizing, or exits.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import broad_market_sector_map
    import sec_ticker_map
    from data_paths import atomic_write_json, data_artifact_path
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant import broad_market_sector_map, sec_ticker_map
    from quant.data_paths import atomic_write_json, data_artifact_path


RULE_VERSION = "reference_cache_rolling_refresh_v1"
DEFAULT_STATE_PATH = (
    Path(broad_market_sector_map.REPO_ROOT) / "data" / "state" / "reference_cache_refresh.json"
    if hasattr(broad_market_sector_map, "REPO_ROOT")
    else Path("data/state/reference_cache_refresh.json")
)

SECTOR_STALE_DAYS = 21
SECTOR_MAX_REFRESH_PER_DAY = 120
SEC_TICKERS_TTL_DAYS = 7


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _age_days(iso_text: Any, *, now: datetime) -> float:
    if not iso_text:
        return float("inf")
    try:
        stamp = datetime.fromisoformat(str(iso_text).replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (now - stamp).total_seconds() / 86400.0


def _load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def stale_sector_tickers(
    *,
    tickers: Iterable[str],
    cache_entries: dict[str, Any],
    now: datetime,
    stale_days: int = SECTOR_STALE_DAYS,
    max_refresh: int = SECTOR_MAX_REFRESH_PER_DAY,
) -> list[str]:
    """Oldest-first slice of universe tickers missing or older than ``stale_days``."""
    scored: list[tuple[float, str]] = []
    for raw in tickers:
        ticker = str(raw or "").upper().strip()
        if not ticker or "." in ticker or "-" in ticker:
            continue
        meta = cache_entries.get(ticker)
        age = _age_days(meta.get("fetched_at"), now=now) if isinstance(meta, dict) else float("inf")
        if age > stale_days:
            scored.append((age, ticker))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [ticker for _age, ticker in scored[: max(0, int(max_refresh))]]


def refresh_sector_cache_rolling(
    *,
    tickers: Iterable[str],
    now: datetime | None = None,
    stale_days: int = SECTOR_STALE_DAYS,
    max_refresh: int = SECTOR_MAX_REFRESH_PER_DAY,
    load_fn: Callable[..., dict[str, Any]] = broad_market_sector_map.load_cache,
    build_fn: Callable[..., dict[str, Any]] = broad_market_sector_map.build_cache,
    cache_path: Path | str = broad_market_sector_map.DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """Refresh the oldest stale slice of the sector cache for the universe."""
    now = now or _utc_now()
    cache = load_fn(cache_path)
    entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    slice_tickers = stale_sector_tickers(
        tickers=tickers,
        cache_entries=entries,
        now=now,
        stale_days=stale_days,
        max_refresh=max_refresh,
    )
    if not slice_tickers:
        return {"status": "fresh", "refreshed_count": 0, "stale_total": 0}
    build_fn(slice_tickers, path=cache_path, skip_existing=False)
    return {
        "status": "refreshed",
        "refreshed_count": len(slice_tickers),
        "sample": slice_tickers[:5],
    }


def refresh_sec_company_tickers_if_due(
    *,
    now: datetime | None = None,
    ttl_days: int = SEC_TICKERS_TTL_DAYS,
    refresh_fn: Callable[..., Any] = sec_ticker_map.refresh_company_tickers,
    cache_path: Path | str | None = None,
) -> dict[str, Any]:
    """Refresh the SEC company-ticker map when its file is older than the TTL."""
    now = now or _utc_now()
    path = Path(cache_path) if cache_path else Path(data_artifact_path("sec_company_tickers"))
    if path.exists():
        age = (now.timestamp() - path.stat().st_mtime) / 86400.0
        if age <= ttl_days:
            return {"status": "fresh", "age_days": round(age, 1), "refreshed": False}
    refresh_fn(path)
    return {"status": "refreshed", "refreshed": True, "path": str(path)}


def refresh_reference_caches(
    *,
    universe: Iterable[str],
    now: datetime | None = None,
    env_get: Callable[[str, str | None], str | None] = os.environ.get,
    state_path: Path | str = DEFAULT_STATE_PATH,
    sector_refresh_fn: Callable[..., dict[str, Any]] = refresh_sector_cache_rolling,
    tickers_refresh_fn: Callable[..., dict[str, Any]] = refresh_sec_company_tickers_if_due,
) -> dict[str, Any]:
    """Orchestrate the throttled reference-cache refreshers with env opt-outs."""
    now = now or _utc_now()

    def _disabled(name: str) -> bool:
        return str(env_get(name, "") or "").lower() in {"1", "true", "yes", "on"}

    summary: dict[str, Any] = {
        "rule_version": RULE_VERSION,
        "generated_at": now.replace(microsecond=0).isoformat(),
        "sector_cache": {"status": "skipped"},
        "sec_company_tickers": {"status": "skipped"},
    }
    if _disabled("REFERENCE_CACHE_REFRESH_DISABLED"):
        summary["status"] = "disabled"
        return summary

    if not _disabled("SECTOR_CACHE_REFRESH_DISABLED"):
        try:
            summary["sector_cache"] = sector_refresh_fn(tickers=universe, now=now)
        except Exception as error:  # pragma: no cover - network failure path
            summary["sector_cache"] = {"status": "failed", "error": str(error)}

    if not _disabled("SEC_TICKER_REFRESH_DISABLED"):
        try:
            summary["sec_company_tickers"] = tickers_refresh_fn(now=now)
        except Exception as error:  # pragma: no cover - network failure path
            summary["sec_company_tickers"] = {"status": "failed", "error": str(error)}

    try:
        atomic_write_json(summary, Path(state_path))
    except OSError:  # pragma: no cover
        pass
    summary["status"] = "completed"
    return summary
