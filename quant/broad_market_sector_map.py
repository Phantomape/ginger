"""Broad-market candidate sector map (read-only lookup).

Default-off measurement surface accepted in exp-20260525-038. The
`risk_engine.SECTOR_MAP` static map only covers the hand-curated core
universe (~80 tickers) and returns "Unknown" for almost every ticker in the
broad-market candidate warehouse (1336 tickers). This module exposes a
larger sector map sourced from yfinance and persisted to a JSON cache so
the lookup itself is offline-deterministic.

This module is read-only with respect to trading state. It does not change
candidate eligibility, ranking, sizing, exits, LLM/news, or live orders.

The cache lives at `data/reference/broad_market_sector_map.json`. Rebuild
the cache by calling `build_cache(tickers)` from
`quant/build_broad_market_sector_cache.py`.

No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_PATH = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"

RULE_VERSION = "yfinance_gics_proxy_sector_v1"
SOURCE_LABEL = "yfinance.Ticker.info.sector"

OK_STATUS = "ok"
MISSING_TICKER_STATUS = "missing_ticker"
MISSING_INFO_STATUS = "missing_info"
FETCH_ERROR_STATUS = "fetch_error"


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def load_cache(path: Path | str = DEFAULT_CACHE_PATH) -> dict[str, Any]:
    """Load the persisted sector cache. Returns an empty shell if absent."""
    p = Path(path)
    if not p.exists():
        return {
            "schema_version": 1,
            "rule_version": RULE_VERSION,
            "source": SOURCE_LABEL,
            "generated_at": None,
            "entries": {},
        }
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Cache at {p} is not a JSON object")
    data.setdefault("schema_version", 1)
    data.setdefault("rule_version", RULE_VERSION)
    data.setdefault("source", SOURCE_LABEL)
    data.setdefault("entries", {})
    return data


def save_cache(payload: dict[str, Any], path: Path | str = DEFAULT_CACHE_PATH) -> None:
    """Persist the cache atomically (write to tmp then rename)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    payload["generated_at"] = _utc_now_iso()
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(p)


def lookup_sector(
    ticker: str,
    cache: dict[str, Any] | None = None,
    *,
    path: Path | str = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """Look up sector / industry / coverage status for a ticker.

    The result schema is stable so that callers can attach it as a
    `sector_lookup` field to candidate / trade rows without further parsing.

    Returns a dict with keys: `ticker`, `sector`, `industry`, `status`,
    `rule_version`, `source`, `fetched_at`.
    """
    norm = str(ticker or "").upper().strip()
    if not norm:
        return {
            "ticker": "",
            "sector": None,
            "industry": None,
            "status": MISSING_TICKER_STATUS,
            "rule_version": RULE_VERSION,
            "source": SOURCE_LABEL,
            "fetched_at": None,
        }
    if cache is None:
        cache = load_cache(path)
    entry = (cache.get("entries") or {}).get(norm)
    if not entry:
        return {
            "ticker": norm,
            "sector": None,
            "industry": None,
            "status": MISSING_TICKER_STATUS,
            "rule_version": RULE_VERSION,
            "source": SOURCE_LABEL,
            "fetched_at": None,
        }
    return {
        "ticker": norm,
        "sector": entry.get("sector"),
        "industry": entry.get("industry"),
        "status": entry.get("status") or OK_STATUS,
        "rule_version": RULE_VERSION,
        "source": SOURCE_LABEL,
        "fetched_at": entry.get("fetched_at"),
    }


def coverage_report(
    tickers: Iterable[str],
    cache: dict[str, Any] | None = None,
    *,
    path: Path | str = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    """Compute coverage statistics for a list of tickers.

    Returns counts and shares for ok / missing_ticker / missing_info /
    fetch_error, the unique sectors observed, and a small sample of
    unresolved tickers for diagnostic use.
    """
    if cache is None:
        cache = load_cache(path)
    entries = cache.get("entries") or {}
    requested = [str(t or "").upper().strip() for t in tickers if str(t or "")]
    seen = set(requested)
    statuses: dict[str, int] = {
        OK_STATUS: 0,
        MISSING_TICKER_STATUS: 0,
        MISSING_INFO_STATUS: 0,
        FETCH_ERROR_STATUS: 0,
    }
    sectors: dict[str, int] = {}
    unresolved_sample: list[str] = []
    for ticker in seen:
        entry = entries.get(ticker)
        if not entry:
            statuses[MISSING_TICKER_STATUS] += 1
            if len(unresolved_sample) < 25:
                unresolved_sample.append(ticker)
            continue
        status = entry.get("status") or OK_STATUS
        statuses[status] = statuses.get(status, 0) + 1
        sector = entry.get("sector")
        if status == OK_STATUS and sector:
            sectors[sector] = sectors.get(sector, 0) + 1
        elif status != OK_STATUS and len(unresolved_sample) < 25:
            unresolved_sample.append(ticker)
    total = len(seen)
    return {
        "rule_version": RULE_VERSION,
        "source": SOURCE_LABEL,
        "tickers_requested": total,
        "tickers_unique": total,
        "status_counts": statuses,
        "status_shares": {
            key: round(value / total, 6) if total else None
            for key, value in statuses.items()
        },
        "ok_share": (
            round(statuses[OK_STATUS] / total, 6) if total else None
        ),
        "sector_unique_count": len(sectors),
        "sector_counts": dict(sorted(sectors.items(), key=lambda kv: -kv[1])),
        "unresolved_sample": sorted(unresolved_sample),
        "cache_generated_at": cache.get("generated_at"),
    }


def upsert_entry(
    payload: dict[str, Any],
    *,
    ticker: str,
    sector: str | None,
    industry: str | None,
    status: str,
) -> None:
    """Upsert a single ticker entry into the cache payload in-place."""
    norm = str(ticker or "").upper().strip()
    if not norm:
        return
    entries = payload.setdefault("entries", {})
    entries[norm] = {
        "sector": sector,
        "industry": industry,
        "status": status,
        "fetched_at": _utc_now_iso(),
    }


def build_cache(
    tickers: Iterable[str],
    *,
    path: Path | str = DEFAULT_CACHE_PATH,
    skip_existing: bool = True,
    save_every: int = 25,
    on_progress: Any = None,
) -> dict[str, Any]:
    """Build/extend the sector cache by querying yfinance for each ticker.

    Lazy-imports yfinance so callers that only need read access do not pay
    the import cost. Saves incrementally so a long fetch is resilient.

    `skip_existing` keeps already-cached entries; pass False to force a
    refresh. `save_every` controls how often we persist intermediate state.
    `on_progress(idx, total, ticker, result)` is called after each lookup.
    """
    import yfinance as yf  # noqa: E402

    payload = load_cache(path)
    seen_already = set((payload.get("entries") or {}).keys()) if skip_existing else set()
    work = []
    for raw in tickers:
        norm = str(raw or "").upper().strip()
        if not norm or norm in seen_already:
            continue
        work.append(norm)
    total = len(work)
    for idx, ticker in enumerate(work, start=1):
        sector: str | None = None
        industry: str | None = None
        status = OK_STATUS
        try:
            info = yf.Ticker(ticker).info
        except Exception as exc:  # noqa: BLE001
            status = FETCH_ERROR_STATUS
            info = {"_error": type(exc).__name__}
        if status == OK_STATUS:
            if not isinstance(info, dict) or not info:
                status = MISSING_INFO_STATUS
            else:
                sector_raw = info.get("sector")
                industry_raw = info.get("industry")
                if not sector_raw:
                    status = MISSING_INFO_STATUS
                else:
                    sector = str(sector_raw).strip() or None
                    industry = (
                        str(industry_raw).strip() if industry_raw else None
                    )
        upsert_entry(
            payload,
            ticker=ticker,
            sector=sector,
            industry=industry,
            status=status,
        )
        if on_progress is not None:
            try:
                on_progress(idx, total, ticker, payload["entries"][ticker])
            except Exception:  # noqa: BLE001
                pass
        if save_every and idx % save_every == 0:
            save_cache(payload, path)
    save_cache(payload, path)
    return payload
