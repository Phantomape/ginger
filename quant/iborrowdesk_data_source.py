"""iBorrowDesk (IBKR shortable-stock mirror) borrow-economics archive.

Free HTTPS source for per-ticker daily indicative borrow fee, rebate, and
lendable availability (https://iborrowdesk.com/api/ticker/<SYMBOL>). Each
response carries roughly one rolling year of daily rows, so the history
erodes daily: rows older than the rolling window are lost forever unless the
archive is materialized and refreshed. This module owns that archive.

Archive layout (append-only PIT semantics):

- ``data/non_ohlcv/iborrowdesk/history/<SYMBOL>.json``: merged per-ticker
  daily rows keyed by date. Existing dates are never rewritten; a refresh
  only adds dates the archive has not seen. Each row keeps ``archived_at``
  so consumers can audit when a row first became locally known.
- ``data/non_ohlcv/iborrowdesk/fetch_state.json``: per-ticker last-fetch
  bookkeeping used to rotate refresh shards and to resume after throttling.

Refresh policy: the API returns the full rolling year per call, so per-ticker
refresh cadence only needs to beat the erosion horizon, not the calendar day.
``refresh_archive`` therefore fetches at most ``max_fetches`` of the stalest
tickers per invocation and backs off hard on HTTP 429/5xx (GDELT lesson:
resumable cache + polite pacing, never hammer a throttling host).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from data_paths import atomic_write_json

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "iborrowdesk"
HISTORY_DIR = ARCHIVE_DIR / "history"
FETCH_STATE_PATH = ARCHIVE_DIR / "fetch_state.json"

API_URL = "https://iborrowdesk.com/api/ticker/{symbol}"
USER_AGENT = "ginger-research/1.0 (borrow-economics archive; contact: repo-local)"
SOURCE_LABEL = "iborrowdesk.com mirror of IBKR shortable-stock indicative feed"

DAILY_FIELDS = (
    "fee",
    "rebate",
    "available",
    "open_fee",
    "high_fee",
    "low_fee",
    "open_available",
    "high_available",
    "low_available",
)

SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_symbol(symbol: str) -> str:
    cleaned = str(symbol).upper().strip()
    if not cleaned or any(ch in cleaned for ch in "\\/:*?\"<>|"):
        raise ValueError(f"unusable iborrowdesk symbol: {symbol!r}")
    return cleaned


def history_path(symbol: str) -> Path:
    return HISTORY_DIR / f"{_safe_symbol(symbol)}.json"


def load_history(symbol: str) -> dict[str, Any]:
    path = history_path(symbol)
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "symbol": _safe_symbol(symbol),
            "source": SOURCE_LABEL,
            "rows": {},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def load_fetch_state() -> dict[str, Any]:
    if not FETCH_STATE_PATH.exists():
        return {"schema_version": SCHEMA_VERSION, "tickers": {}}
    return json.loads(FETCH_STATE_PATH.read_text(encoding="utf-8"))


def fetch_ticker_payload(
    symbol: str,
    *,
    timeout: float = 30.0,
    retries: int = 3,
    backoff_s: float = 20.0,
) -> dict[str, Any]:
    """Fetch the raw API payload for one symbol.

    Raises ``urllib.error.HTTPError``/``URLError`` after exhausting retries.
    A 429 or 5xx triggers a long polite backoff; a 404 (unknown symbol)
    raises immediately so callers can mark the ticker uncovered.
    """
    url = API_URL.format(symbol=_safe_symbol(symbol))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise
            last_error = error
            if error.code in (429, 500, 502, 503, 504):
                time.sleep(backoff_s * (attempt + 1))
            else:
                time.sleep(2.0)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(5.0)
    assert last_error is not None
    raise last_error


def merge_daily_rows(symbol: str, daily_rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Merge API daily rows into the per-ticker archive (append-only by date)."""
    history = load_history(symbol)
    rows: dict[str, Any] = history.get("rows") or {}
    added = 0
    stamp = _utc_now_iso()
    for row in daily_rows or []:
        date = str(row.get("date") or "")[:10]
        if len(date) != 10 or date in rows:
            continue
        entry: dict[str, Any] = {"archived_at": stamp}
        for field in DAILY_FIELDS:
            value = row.get(field)
            if isinstance(value, (int, float)):
                entry[field] = value
        rows[date] = entry
        added += 1
    if added:
        history["rows"] = dict(sorted(rows.items()))
        history["symbol"] = _safe_symbol(symbol)
        history["source"] = SOURCE_LABEL
        history["schema_version"] = SCHEMA_VERSION
        history["updated_at"] = stamp
        history["row_count"] = len(history["rows"])
        atomic_write_json(history, history_path(symbol))
    return {"added": added, "total": len(rows)}


def refresh_archive(
    tickers: Iterable[str],
    *,
    max_fetches: int = 250,
    min_age_days: float = 5.0,
    sleep_s: float = 0.35,
    timeout: float = 30.0,
    max_consecutive_failures: int = 5,
) -> dict[str, Any]:
    """Refresh the stalest shard of the archive.

    Fetches at most ``max_fetches`` tickers whose last successful fetch is
    older than ``min_age_days`` (stalest first, never-fetched first of all).
    Aborts early after ``max_consecutive_failures`` consecutive errors so a
    throttling or dead host cannot stall the daily pipeline; whatever was
    fetched before the abort stays merged (resumable).
    """
    state = load_fetch_state()
    per_ticker: dict[str, Any] = state.get("tickers") or {}
    now = datetime.now(timezone.utc)

    def _age_days(symbol: str) -> float:
        meta = per_ticker.get(symbol) or {}
        stamp = meta.get("last_success_utc")
        if not stamp:
            return float("inf")
        try:
            then = datetime.fromisoformat(stamp)
        except ValueError:
            return float("inf")
        return (now - then).total_seconds() / 86400.0

    cleaned = sorted({_safe_symbol(t) for t in tickers if str(t).strip()})
    due = [t for t in cleaned if _age_days(t) >= min_age_days]
    due.sort(key=_age_days, reverse=True)
    shard = due[: max(0, int(max_fetches))]

    summary: dict[str, Any] = {
        "started_at": _utc_now_iso(),
        "universe_count": len(cleaned),
        "due_count": len(due),
        "attempted": 0,
        "succeeded": 0,
        "rows_added": 0,
        "not_found": [],
        "failed": [],
        "aborted_early": False,
    }
    consecutive_failures = 0
    for symbol in shard:
        if consecutive_failures >= max_consecutive_failures:
            summary["aborted_early"] = True
            break
        summary["attempted"] += 1
        try:
            payload = fetch_ticker_payload(symbol, timeout=timeout)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                summary["not_found"].append(symbol)
                per_ticker[symbol] = {
                    "last_attempt_utc": _utc_now_iso(),
                    "status": "not_found",
                }
                consecutive_failures = 0
            else:
                summary["failed"].append(f"{symbol}:http_{error.code}")
                per_ticker[symbol] = {
                    **(per_ticker.get(symbol) or {}),
                    "last_attempt_utc": _utc_now_iso(),
                    "status": f"http_{error.code}",
                }
                consecutive_failures += 1
            continue
        except Exception as error:  # noqa: BLE001 - archive must stay resumable
            summary["failed"].append(f"{symbol}:{type(error).__name__}")
            per_ticker[symbol] = {
                **(per_ticker.get(symbol) or {}),
                "last_attempt_utc": _utc_now_iso(),
                "status": type(error).__name__,
            }
            consecutive_failures += 1
            continue
        merged = merge_daily_rows(symbol, payload.get("daily") or [])
        summary["succeeded"] += 1
        summary["rows_added"] += merged["added"]
        per_ticker[symbol] = {
            "last_attempt_utc": _utc_now_iso(),
            "last_success_utc": _utc_now_iso(),
            "status": "ok",
            "archived_rows": merged["total"],
            "latest_fee": payload.get("latest_fee"),
            "latest_available": payload.get("latest_available"),
        }
        consecutive_failures = 0
        time.sleep(sleep_s)

    state["tickers"] = per_ticker
    state["schema_version"] = SCHEMA_VERSION
    state["last_refresh_summary"] = {
        key: value for key, value in summary.items() if key != "not_found"
    }
    atomic_write_json(state, FETCH_STATE_PATH)
    summary["finished_at"] = _utc_now_iso()
    return summary


def archived_symbols() -> list[str]:
    if not HISTORY_DIR.exists():
        return []
    return sorted(p.stem for p in HISTORY_DIR.glob("*.json"))
