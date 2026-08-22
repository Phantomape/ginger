"""Incremental daily refresher for the broad moomoo daily short-volume archive.

exp-20260813-001 (measurement repair, frozen-input fault recovery): the broad
archive built by exp-20260623-008 was a one-time collection whose last
activity_date froze at 2026-06-22, while the forward replacement-value
enricher kept consuming it and stamping ``entry_short_volume_status=ok`` on
rows entered weeks later. This module restores forward accrual by fetching
only activity dates newer than each ticker's last archived row.

Contract (AGENTS.md section 6):
- The incremental cutoff is anchored to the DATA calendar (the archive's own
  per-ticker max ``activity_date``), never the process wall clock.
- Rows are append-only. Existing rows are never rewritten, so the original
  ``collected_at`` retrieval vintage of every historical row is preserved;
  new rows carry the current fetch's ``collected_at``. Vintage classification
  downstream (collected before vs after a decision) depends on this.
- Failure is explicit: OpenD unreachable or a fetch error returns a summary
  whose ``status`` is not ``ok``. The consumer-side tag (rule v2 in
  ``forward_replacement_value.py``) fails closed on a stale archive, so a
  failed refresh can never silently re-freeze the surface into ``ok`` tags.

The archive stays activity-only sell-pressure context (never FINRA
short-interest positioning) and never creates, ranks, sizes, or exits a
position.
"""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_paths import DATA_ROOT, atomic_write_text

ARCHIVE_RELDIR = Path("non_ohlcv") / "moomoo_daily_short_volume_broad"
ROWS_RELPATH = ARCHIVE_RELDIR / "rows.jsonl"
MANIFEST_RELPATH = ARCHIVE_RELDIR / "manifest.json"

# Parity with the exp-20260623-008 backfill and exp-20260622-009 schema.
SCHEMA_VERSION = "moomoo_daily_short_volume_activity_v1"
SOURCE_NAME = "moomoo_get_daily_short_volume"
REFRESH_EXPERIMENT_ID = "exp-20260813-001"
START_DATE = "2024-06-01"

PAGE_NUM = 50            # max rows per page (API range 1-50)
REQUEST_SLEEP_SEC = 1.1  # stay under the 30 req / 30 s quote quota
MAX_PAGES_INCREMENTAL = 6    # ~300 sessions of catch-up per ticker
MAX_PAGES_NEW_TICKER = 60    # full backfill bound for a ticker new to the archive

ACTIVITY_ONLY_WARNING = (
    "Moomoo daily short volume is an activity field, not FINRA short-interest "
    "positioning. Any candidate-pool helper must use it as activity-only "
    "sell-pressure context and map each activity_date to the next tradable session."
)
USABLE_TRADE_DATE_POLICY = (
    "Future helper must map this activity_date to the next valid trading "
    "session unless vendor publication timing proves same-session "
    "post-close availability."
)


def _f(value: Any) -> float | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # drop NaN


def _rows_path(archive_root: Path | None = None) -> Path:
    root = Path(archive_root) if archive_root else DATA_ROOT
    return root / ROWS_RELPATH


def _manifest_path(archive_root: Path | None = None) -> Path:
    root = Path(archive_root) if archive_root else DATA_ROOT
    return root / MANIFEST_RELPATH


def load_archive_rows(archive_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return ``{source_code|activity_date: row}`` for the whole archive."""
    path = _rows_path(archive_root)
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = f"{row.get('source_code')}|{row.get('activity_date')}"
        rows[key] = row
    return rows


def archive_max_activity_date(archive_root: Path | None = None) -> str | None:
    """Global max activity_date of the archive (data-calendar freshness anchor)."""
    rows = load_archive_rows(archive_root)
    dates = [str(r.get("activity_date") or "") for r in rows.values()]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def _normalize_api_row(code: str, raw: dict[str, Any], collected_at: str) -> dict[str, Any] | None:
    activity_date = str(raw.get("timestamp_str") or "")[:10]
    if not activity_date:
        return None
    total_shares_short = _f(raw.get("total_shares_short"))
    volume = _f(raw.get("volume"))
    short_volume_ratio = None
    if total_shares_short is not None and volume and volume > 0:
        short_volume_ratio = round(total_shares_short / volume, 8)
    ticker = code.split(".", 1)[-1] if "." in code else code
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE_NAME,
        "source_code": code,
        "ticker": ticker,
        "activity_date": activity_date,
        "collected_at": collected_at,
        "archive_experiment_id": REFRESH_EXPERIMENT_ID,
        "pit_boundary": "activity_date_after_us_close",
        "positioning_warning": ACTIVITY_ONLY_WARNING,
        "usable_trade_date": None,
        "usable_trade_date_policy": USABLE_TRADE_DATE_POLICY,
        "total_shares_short": total_shares_short,
        "nasdaq_shares_short": _f(raw.get("nasdaq_shares_short")),
        "nyse_shares_short": _f(raw.get("nyse_shares_short")),
        "reported_short_percent": _f(raw.get("short_percent")),
        "short_volume_ratio": short_volume_ratio,
        "volume": volume,
        "close_price": _f(raw.get("close_price")),
        "last_close_price": _f(raw.get("last_close_price")),
        "daily_trade_avg_ratio": _f(raw.get("daily_trade_avg_ratio")),
    }


def _fetch_ticker_incremental(
    ctx, code: str, last_known_date: str | None, collected_at: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch pages (newest first) until we reach ``last_known_date`` / START_DATE."""
    from moomoo import RET_OK

    floor_date = last_known_date or START_DATE
    max_pages = MAX_PAGES_INCREMENTAL if last_known_date else MAX_PAGES_NEW_TICKER
    collected: list[dict[str, Any]] = []
    next_key = None
    pages = 0
    while pages < max_pages:
        kwargs: dict[str, Any] = {"num": PAGE_NUM}
        if next_key not in (None, "", "-1"):
            kwargs["next_key"] = next_key
        ret, us_df, _hk_df = ctx.get_daily_short_volume(code, **kwargs)
        if ret != RET_OK:
            return collected, str(us_df)
        if us_df is None or us_df.empty:
            break
        page_min = "9999-99-99"
        for rec in us_df.to_dict("records"):
            row = _normalize_api_row(code, rec, collected_at)
            if row is None:
                continue
            ad = row["activity_date"]
            page_min = min(page_min, ad)
            if ad <= floor_date or ad < START_DATE:
                continue
            collected.append(row)
        pages += 1
        nk = us_df.attrs.get("next_key", "") if hasattr(us_df, "attrs") else ""
        if page_min <= floor_date or not nk or nk == "-1":
            break
        next_key = nk
        time.sleep(REQUEST_SLEEP_SEC)
    return collected, None


def refresh_moomoo_daily_short_volume_archive(
    *,
    host: str = "127.0.0.1",
    port: int = 11111,
    universe: list[str] | None = None,
    archive_root: Path | None = None,
    quote_ctx=None,
) -> dict[str, Any]:
    """Append rows newer than each ticker's last archived ``activity_date``.

    Returns a summary dict whose ``status`` is ``ok`` (possibly with zero new
    rows on a repeat same-day run), ``opend_unavailable``, or ``error``. The
    archive file is only rewritten when new rows exist, atomically, and
    existing rows are never modified (append-only vintage contract).
    """
    refreshed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary: dict[str, Any] = {
        "status": "ok",
        "refreshed_at": refreshed_at,
        "source": SOURCE_NAME,
        "new_rows": 0,
        "tickers_with_new_rows": 0,
        "tickers_scanned": 0,
        "errors": {},
        "max_activity_date_before": None,
        "max_activity_date_after": None,
    }

    rows_by_key = load_archive_rows(archive_root)
    last_by_code: dict[str, str] = {}
    for row in rows_by_key.values():
        code = str(row.get("source_code") or "")
        ad = str(row.get("activity_date") or "")
        if code and ad and ad > last_by_code.get(code, ""):
            last_by_code[code] = ad
    summary["max_activity_date_before"] = (
        max(last_by_code.values()) if last_by_code else None
    )

    if universe is not None:
        codes = sorted({f"US.{t}" if "." not in t else t for t in universe})
    else:
        codes = sorted(last_by_code)
    if not codes:
        summary["status"] = "empty_archive_and_no_universe"
        return summary

    ctx = quote_ctx
    owns_ctx = False
    if ctx is None:
        # Bounded reachability preflight: the moomoo SDK's OpenQuoteContext
        # constructor does NOT fail fast on an unreachable OpenD -- it blocks
        # in an unbounded background reconnect loop (observed live during the
        # exp-20260813-001 boundary smoke test). A raw TCP probe with a short
        # timeout keeps the daily run from hanging when OpenD is down.
        try:
            probe = socket.create_connection((host, port), timeout=3)
            probe.close()
        except OSError as e:
            summary["status"] = "opend_unavailable"
            summary["error"] = f"tcp_probe_failed: {e}"
            summary["max_activity_date_after"] = summary["max_activity_date_before"]
            return summary
        try:
            from moomoo import OpenQuoteContext

            ctx = OpenQuoteContext(host=host, port=port)
            owns_ctx = True
        except Exception as e:  # noqa: BLE001
            summary["status"] = "opend_unavailable"
            summary["error"] = str(e)
            summary["max_activity_date_after"] = summary["max_activity_date_before"]
            return summary

    new_rows = 0
    tickers_with_new = 0
    try:
        for code in codes:
            summary["tickers_scanned"] += 1
            try:
                recs, err = _fetch_ticker_incremental(
                    ctx, code, last_by_code.get(code), refreshed_at
                )
            except Exception as fetch_exc:  # noqa: BLE001
                recs, err = [], f"fetch_exception: {fetch_exc}"
            if err:
                summary["errors"][code] = err
                continue
            added_for_code = 0
            for row in recs:
                key = f"{row['source_code']}|{row['activity_date']}"
                if key in rows_by_key:
                    continue  # append-only: never overwrite an existing vintage
                rows_by_key[key] = row
                added_for_code += 1
            if added_for_code:
                new_rows += added_for_code
                tickers_with_new += 1
            time.sleep(REQUEST_SLEEP_SEC)
    finally:
        if owns_ctx:
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass

    summary["new_rows"] = new_rows
    summary["tickers_with_new_rows"] = tickers_with_new
    all_dates = [
        str(r.get("activity_date") or "") for r in rows_by_key.values()
    ]
    all_dates = [d for d in all_dates if d]
    summary["max_activity_date_after"] = max(all_dates) if all_dates else None

    if summary["errors"] and not new_rows:
        summary["status"] = "error"

    if new_rows:
        ordered = sorted(
            rows_by_key.values(),
            key=lambda x: (str(x.get("source_code")), str(x.get("activity_date"))),
        )
        payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in ordered) + "\n"
        rows_path = _rows_path(archive_root)
        rows_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(payload, rows_path)

        manifest_path = _manifest_path(archive_root)
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {}
        manifest.update(
            {
                "schema_version": 1,
                "source": SOURCE_NAME,
                "rows": len(rows_by_key),
                "max_activity_date": summary["max_activity_date_after"],
                "daily_refresh": {
                    "experiment_id": REFRESH_EXPERIMENT_ID,
                    "refreshed_at": refreshed_at,
                    "new_rows": new_rows,
                    "tickers_with_new_rows": tickers_with_new,
                    "errors": summary["errors"],
                },
                "updated_at": refreshed_at,
            }
        )
        atomic_write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", manifest_path
        )

    return summary
