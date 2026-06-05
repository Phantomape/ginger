"""exp-20260519-030: broad-market OHLCV warehouse v1.

This is a measurement-repair builder for core-expansion research. It creates a
SQLite OHLCV warehouse from the local SEC ticker reference, seeds any rows that
already exist in local snapshots, and can resume Yahoo Finance downloads in
batches. It does not change core, pilot, ranking, sizing, or live orders.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf
import yfinance.shared as yf_shared


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260519-030"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
WAREHOUSE_PATH = OUT_DIR / "warehouse_main.sqlite"
MANIFEST_PATH = OUT_DIR / "broad_market_ohlcv_warehouse_manifest.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_broad_market_ohlcv_warehouse.md"
)
LOG_PATH = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_PATH = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEC_REFERENCE_PATH = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"

WINDOWS: dict[str, dict[str, str]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

LOCAL_SEED_SNAPSHOTS = [
    "data/experiments/exp-20260519-029/ohlcv/exp-20260519-029_late_strong_current_universe_ohlcv.json",
    "data/experiments/exp-20260501-008/ohlcv_aug_20251023_20260421.json",
    "data/ohlcv/ohlcv_snapshot_20251023_20260501_with_pilot.json",
    "data/ohlcv/ohlcv_snapshot_20251023_20260421_with_pilot_refreshed.json",
    "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
]
REFERENCE_OHLCV_TICKERS = {
    "SPY",
    "QQQ",
    "IWM",
    "TLT",
    "IEF",
    "XLE",
    "XLU",
    "XLP",
    "XLV",
    "SNXX",
}

MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_CLOSE = 5.0
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000.0

SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,11}$")
EXCLUDE_TITLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "title_warrant": re.compile(r"\bWARRANTS?\b", re.I),
    "title_unit": re.compile(r"\bUNITS?\b", re.I),
    "title_right": re.compile(r"\bRIGHTS?\b", re.I),
    "title_preferred": re.compile(r"\b(PREFERRED|PREFERENCE|PFD)\b", re.I),
    "title_debt": re.compile(r"\b(NOTES?|BONDS?|DEBENTURES?)\b|SENIOR NOTE|SUBORDINATED", re.I),
}
TAG_PATTERNS: dict[str, re.Pattern[str]] = {
    "etf_or_fund": re.compile(r"\b(ETF|FUND|ISHARES|VANGUARD|SPDR|INVESCO|PROSHARES|DIREXION|GLOBAL X)\b", re.I),
    "trust_like": re.compile(r"\bTRUST\b", re.I),
    "adr_like": re.compile(r"\b(ADR|ADS|AMERICAN DEPOSITARY|DEPOSITARY RECEIPT)\b", re.I),
    "spac_like": re.compile(r"\b(ACQUISITION|BLANK CHECK|SPAC)\b", re.I),
}
SPAC_DERIVATIVE_CONTEXT_RE = re.compile(
    r"\b(ACQUISITION|BLANK CHECK|SPAC|CAPITAL|HOLDINGS|CORP|INC)\b",
    re.I,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("/", "\\")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _finite_float(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _parse_date(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _canonical_fetch_bounds() -> tuple[str, str]:
    starts: list[str] = []
    ends: list[str] = []
    for spec in WINDOWS.values():
        path = REPO_ROOT / spec["snapshot"]
        if not path.exists():
            continue
        snapshot = _load_json(path)
        metadata = snapshot.get("metadata") or {}
        if metadata.get("download_start") and metadata.get("download_end"):
            starts.append(str(metadata["download_start"]))
            ends.append(str(metadata["download_end"]))
    if starts and ends:
        return min(starts), max(ends)
    return "2024-09-18", "2026-04-26"


def _expected_dates_by_window() -> dict[str, set[str]]:
    expected: dict[str, set[str]] = {}
    for label, spec in WINDOWS.items():
        path = REPO_ROOT / spec["snapshot"]
        if not path.exists():
            expected[label] = set()
            continue
        snapshot = _load_json(path)
        rows_by_ticker = snapshot.get("ohlcv") or {}
        rows = rows_by_ticker.get("SPY") or next(iter(rows_by_ticker.values()), [])
        expected[label] = {
            str(row.get("Date"))
            for row in rows or []
            if row.get("Date") and spec["start"] <= str(row.get("Date")) <= spec["end"]
        }
    return expected


def _classify_security(ticker: str, title: str) -> dict[str, Any]:
    reasons: list[str] = []
    tags: list[str] = []

    def add_reason(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    if not SYMBOL_RE.match(ticker):
        add_reason("bad_symbol_format")
    if ticker.count("-") > 1:
        add_reason("multi_dash_symbol")
    for name, pattern in EXCLUDE_TITLE_PATTERNS.items():
        if pattern.search(title):
            add_reason(name)
    for name, pattern in TAG_PATTERNS.items():
        if pattern.search(title):
            tags.append(name)

    if "spac_like" in tags:
        add_reason("title_spac_like")
    if re.search(r"-(WT|WS|W)$", ticker) or (len(ticker) >= 5 and ticker.endswith(("WW", "WS", "WT"))):
        add_reason("ticker_warrant_marker")
    if re.search(r"-(RI|RT|R)$", ticker) or (
        len(ticker) >= 5 and ticker.endswith("R") and "spac_like" in tags
    ):
        add_reason("ticker_right_marker")
    if re.search(r"-(UN|U)$", ticker) or (
        len(ticker) >= 5 and ticker.endswith("U") and "spac_like" in tags
    ):
        add_reason("ticker_unit_marker")
    if re.search(r"-P[A-Z0-9]?$", ticker):
        add_reason("ticker_preferred_marker")
    if (
        len(ticker) >= 5
        and ticker.endswith("W")
        and SPAC_DERIVATIVE_CONTEXT_RE.search(title)
    ):
        add_reason("ticker_spac_warrant_suffix")
    if len(ticker) >= 5 and ticker.endswith(("F", "Y")):
        add_reason("ticker_otc_foreign_or_adr_suffix")
    if len(ticker) >= 5 and ticker.endswith(("Q", "Z")):
        add_reason("ticker_terminal_special_suffix")

    return {
        "hygiene_pass": not reasons,
        "exclusion_reasons": reasons,
        "tags": tags,
    }


def _load_sec_universe() -> list[dict[str, Any]]:
    payload = _load_json(SEC_REFERENCE_PATH)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in payload.values():
        ticker = str(raw.get("ticker") or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        title = str(raw.get("title") or "").strip()
        classification = _classify_security(ticker, title)
        rows.append(
            {
                "ticker": ticker,
                "yahoo_ticker": ticker,
                "cik": int(raw.get("cik_str") or 0),
                "title": title,
                **classification,
                "source": _repo_rel(SEC_REFERENCE_PATH),
            }
        )
    rows.sort(key=lambda row: row["ticker"])
    return rows


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ticker_universe (
            ticker TEXT PRIMARY KEY,
            yahoo_ticker TEXT NOT NULL,
            cik INTEGER,
            title TEXT,
            hygiene_pass INTEGER NOT NULL,
            exclusion_reasons_json TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            source TEXT NOT NULL,
            loaded_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (ticker, date)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv(date)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_status (
            ticker TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            first_date TEXT,
            last_date TEXT,
            error TEXT,
            provider TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS coverage_summary (
            ticker TEXT PRIMARY KEY,
            row_count INTEGER NOT NULL,
            first_date TEXT,
            last_date TEXT,
            full_liquid_window_count INTEGER NOT NULL,
            any_window_full_liquid INTEGER NOT NULL,
            all_windows_full_liquid INTEGER NOT NULL,
            windows_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_manifest (
            experiment_id TEXT PRIMARY KEY,
            generated_at TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        )
        """
    )
    return conn


def _resolved_warehouse_path() -> Path:
    candidates = [
        WAREHOUSE_PATH,
        WAREHOUSE_PATH.with_name(f"{WAREHOUSE_PATH.stem}_main.sqlite"),
        WAREHOUSE_PATH.with_name(f"{WAREHOUSE_PATH.stem}_run.sqlite"),
    ]
    for path in candidates:
        journal = Path(f"{path}-journal")
        if path.exists() and path.stat().st_size == 0:
            continue
        if journal.exists():
            continue
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return WAREHOUSE_PATH.with_name(f"{WAREHOUSE_PATH.stem}_{stamp}.sqlite")


def _upsert_universe(conn: sqlite3.Connection, rows: list[dict[str, Any]], generated_at: str) -> None:
    conn.executemany(
        """
        INSERT INTO ticker_universe (
            ticker, yahoo_ticker, cik, title, hygiene_pass,
            exclusion_reasons_json, tags_json, source, loaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            yahoo_ticker=excluded.yahoo_ticker,
            cik=excluded.cik,
            title=excluded.title,
            hygiene_pass=excluded.hygiene_pass,
            exclusion_reasons_json=excluded.exclusion_reasons_json,
            tags_json=excluded.tags_json,
            source=excluded.source,
            loaded_at=excluded.loaded_at
        """,
        [
            (
                row["ticker"],
                row["yahoo_ticker"],
                row["cik"],
                row["title"],
                1 if row["hygiene_pass"] else 0,
                json.dumps(row["exclusion_reasons"], sort_keys=True),
                json.dumps(row["tags"], sort_keys=True),
                row["source"],
                generated_at,
            )
            for row in rows
        ],
    )
    conn.commit()


def _clean_snapshot_rows(rows: Any, start: str, end: str) -> list[tuple[str, str, float, float, float, float, float]]:
    cleaned: dict[str, tuple[str, str, float, float, float, float, float]] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date = str(row.get("Date") or "")[:10]
        if not date or date < start or date > end:
            continue
        open_ = _finite_float(row.get("Open"))
        high = _finite_float(row.get("High"))
        low = _finite_float(row.get("Low"))
        close = _finite_float(row.get("Close"))
        volume = _finite_float(row.get("Volume"))
        if open_ is None or high is None or low is None or close is None:
            continue
        cleaned[date] = ("", date, open_, high, low, close, volume or 0.0)
    return [cleaned[date] for date in sorted(cleaned)]


def _upsert_ohlcv(
    conn: sqlite3.Connection,
    ticker: str,
    rows: list[tuple[str, str, float, float, float, float, float]],
    *,
    source: str,
    updated_at: str,
) -> int:
    if not rows:
        return 0
    payload = [
        (ticker, date, open_, high, low, close, volume, source, updated_at)
        for _, date, open_, high, low, close, volume in rows
    ]
    conn.executemany(
        """
        INSERT INTO ohlcv (ticker, date, open, high, low, close, volume, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, date) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            source=excluded.source,
            updated_at=excluded.updated_at
        """,
        payload,
    )
    return len(payload)


def _upsert_fetch_status(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    status: str,
    row_count: int,
    first_date: str | None,
    last_date: str | None,
    error: str | None,
    provider: str,
    fetched_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO fetch_status (ticker, status, row_count, first_date, last_date, error, provider, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            status=excluded.status,
            row_count=excluded.row_count,
            first_date=excluded.first_date,
            last_date=excluded.last_date,
            error=excluded.error,
            provider=excluded.provider,
            fetched_at=excluded.fetched_at
        """,
        (ticker, status, row_count, first_date, last_date, error, provider, fetched_at),
    )


def seed_local_snapshots(
    conn: sqlite3.Connection,
    target_tickers: set[str],
    *,
    start: str,
    end: str,
    generated_at: str,
) -> dict[str, Any]:
    seeded_tickers: set[str] = set()
    rows_inserted = 0
    source_counts: dict[str, int] = {}
    for rel_path in LOCAL_SEED_SNAPSHOTS:
        path = REPO_ROOT / rel_path
        if not path.exists():
            continue
        snapshot = _load_json(path)
        for ticker, raw_rows in (snapshot.get("ohlcv") or {}).items():
            ticker = str(ticker).upper()
            if ticker not in target_tickers and ticker not in REFERENCE_OHLCV_TICKERS:
                continue
            rows = _clean_snapshot_rows(raw_rows, start, end)
            inserted = _upsert_ohlcv(conn, ticker, rows, source=rel_path, updated_at=generated_at)
            if inserted:
                seeded_tickers.add(ticker)
                rows_inserted += inserted
                source_counts[rel_path] = source_counts.get(rel_path, 0) + inserted
        conn.commit()

    for ticker in seeded_tickers:
        first_last = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM ohlcv WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        _upsert_fetch_status(
            conn,
            ticker,
            status="seeded_local",
            row_count=int(first_last[0] or 0),
            first_date=first_last[1],
            last_date=first_last[2],
            error=None,
            provider="local_snapshot_seed",
            fetched_at=generated_at,
        )
    conn.commit()
    return {
        "seeded_ticker_count": len(seeded_tickers),
        "seeded_row_upserts": rows_inserted,
        "seed_sources": source_counts,
    }


def _existing_loaded_tickers(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute("SELECT ticker FROM ohlcv GROUP BY ticker HAVING COUNT(*) > 0").fetchall()
    }


def _status_tickers(conn: sqlite3.Connection, statuses: set[str]) -> set[str]:
    if not statuses:
        return set()
    placeholders = ",".join("?" for _ in statuses)
    return {
        str(row[0])
        for row in conn.execute(
            f"SELECT ticker FROM fetch_status WHERE status IN ({placeholders})",
            tuple(sorted(statuses)),
        ).fetchall()
    }


def _frame_for_ticker(data: pd.DataFrame, ticker: str, batch_size: int) -> pd.DataFrame | None:
    if data is None or data.empty:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        top = list(data.columns.get_level_values(0))
        if ticker in top:
            frame = data[ticker].copy()
            return frame.dropna(how="all")
        return None
    if batch_size == 1 and "Open" in data.columns:
        return data.copy().dropna(how="all")
    return None


def _rows_from_yfinance_frame(frame: pd.DataFrame, start: str, end: str) -> list[tuple[str, str, float, float, float, float, float]]:
    rows: dict[str, tuple[str, str, float, float, float, float, float]] = {}
    if frame is None or frame.empty:
        return []
    for index, row in frame.iterrows():
        date = pd.Timestamp(index).date().isoformat()
        if date < start or date > end:
            continue
        raw_close = _finite_float(row.get("Close"))
        adj_close = _finite_float(row.get("Adj Close"))
        open_ = _finite_float(row.get("Open"))
        high = _finite_float(row.get("High"))
        low = _finite_float(row.get("Low"))
        volume = _finite_float(row.get("Volume"))
        if raw_close is None or open_ is None or high is None or low is None:
            continue
        close = adj_close if adj_close is not None else raw_close
        ratio = close / raw_close if raw_close else 1.0
        rows[date] = ("", date, open_ * ratio, high * ratio, low * ratio, close, volume or 0.0)
    return [rows[date] for date in sorted(rows)]


def fetch_yfinance_batches(
    conn: sqlite3.Connection,
    tickers: list[str],
    *,
    start: str,
    end: str,
    batch_size: int,
    generated_at: str,
    stop_on_rate_limit_count: int,
    sleep_between_batches: float,
    threads: bool,
) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    rows_inserted = 0
    batch_errors: list[dict[str, Any]] = []
    rate_limited_total = 0
    stopped_early_reason: str | None = None
    end_exclusive = (_parse_date(end) + timedelta(days=1)).date().isoformat()
    for offset in range(0, len(tickers), batch_size):
        batch = tickers[offset : offset + batch_size]
        getattr(yf_shared, "_ERRORS", {}).clear()
        try:
            data = yf.download(
                tickers=batch,
                start=start,
                end=end_exclusive,
                group_by="ticker",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=threads,
            )
        except Exception as exc:  # pragma: no cover - provider/network behavior
            message = str(exc)
            is_rate_limit = "Too Many Requests" in message or "RateLimit" in message
            batch_errors.append({"tickers": batch, "error": message})
            for ticker in batch:
                _upsert_fetch_status(
                    conn,
                    ticker,
                    status="rate_limited" if is_rate_limit else "failed",
                    row_count=0,
                    first_date=None,
                    last_date=None,
                    error=message,
                    provider="yfinance",
                    fetched_at=generated_at,
                )
                status_counts["rate_limited" if is_rate_limit else "failed"] += 1
                if is_rate_limit:
                    rate_limited_total += 1
            conn.commit()
            if stop_on_rate_limit_count > 0 and rate_limited_total >= stop_on_rate_limit_count:
                stopped_early_reason = f"rate_limit_guard_{rate_limited_total}_tickers"
                break
            continue

        for ticker in batch:
            frame = _frame_for_ticker(data, ticker, len(batch))
            rows = _rows_from_yfinance_frame(frame, start, end) if frame is not None else []
            if rows:
                inserted = _upsert_ohlcv(conn, ticker, rows, source="yfinance", updated_at=generated_at)
                dates = [row[1] for row in rows]
                _upsert_fetch_status(
                    conn,
                    ticker,
                    status="downloaded",
                    row_count=len(rows),
                    first_date=min(dates),
                    last_date=max(dates),
                    error=None,
                    provider="yfinance",
                    fetched_at=generated_at,
                )
                rows_inserted += inserted
                status_counts["downloaded"] += 1
            else:
                errors = getattr(yf_shared, "_ERRORS", {}) or {}
                error = errors.get(ticker) or errors.get(ticker.upper())
                status = "no_rows"
                if error and ("Too Many Requests" in str(error) or "RateLimit" in str(error)):
                    status = "rate_limited"
                    rate_limited_total += 1
                _upsert_fetch_status(
                    conn,
                    ticker,
                    status=status,
                    row_count=0,
                    first_date=None,
                    last_date=None,
                    error=str(error) if error else None,
                    provider="yfinance",
                    fetched_at=generated_at,
                )
                status_counts[status] += 1
        conn.commit()
        if stop_on_rate_limit_count > 0 and rate_limited_total >= stop_on_rate_limit_count:
            stopped_early_reason = f"rate_limit_guard_{rate_limited_total}_tickers"
            break
        if sleep_between_batches > 0 and offset + batch_size < len(tickers):
            time.sleep(sleep_between_batches)

    return {
        "requested_ticker_count": len(tickers),
        "rows_upserted": rows_inserted,
        "status_counts": dict(status_counts),
        "batch_errors": batch_errors[:20],
        "rate_limited_ticker_count": rate_limited_total,
        "stopped_early_reason": stopped_early_reason,
    }


def compute_coverage_summary(
    conn: sqlite3.Connection,
    tickers: list[str],
    *,
    expected_dates: dict[str, set[str]],
    generated_at: str,
) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    full_liquid_distribution: Counter[int] = Counter()
    for ticker in tickers:
        rows = conn.execute(
            "SELECT date, close, volume FROM ohlcv WHERE ticker = ? ORDER BY date",
            (ticker,),
        ).fetchall()
        dates = {str(row[0]) for row in rows}
        windows: dict[str, dict[str, Any]] = {}
        full_liquid_count = 0
        for label, spec in WINDOWS.items():
            expected = expected_dates.get(label) or set()
            window_rows = [
                row
                for row in rows
                if spec["start"] <= str(row[0]) <= spec["end"]
            ]
            covered = len(dates & expected)
            coverage_fraction = covered / len(expected) if expected else 0.0
            closes = [float(row[1]) for row in window_rows if _finite_float(row[1]) is not None]
            dollar_volumes = [
                float(row[1]) * float(row[2])
                for row in window_rows
                if _finite_float(row[1]) is not None and _finite_float(row[2]) is not None
            ]
            median_close = float(pd.Series(closes).median()) if closes else None
            median_dollar_volume = float(pd.Series(dollar_volumes).median()) if dollar_volumes else None
            full = coverage_fraction >= MIN_COVERAGE_FRACTION
            liquid = (
                full
                and (median_close or 0.0) >= MIN_MEDIAN_CLOSE
                and (median_dollar_volume or 0.0) >= MIN_MEDIAN_DOLLAR_VOLUME
            )
            if liquid:
                full_liquid_count += 1
            windows[label] = {
                "coverage_fraction": round(coverage_fraction, 4),
                "covered_expected_trading_dates": covered,
                "expected_trading_dates": len(expected),
                "row_count": len(window_rows),
                "median_close": round(median_close, 4) if median_close is not None else None,
                "median_dollar_volume": round(median_dollar_volume, 2)
                if median_dollar_volume is not None
                else None,
                "full_coverage": full,
                "full_liquid": liquid,
            }

        row_count = len(rows)
        first_date = min(dates) if dates else None
        last_date = max(dates) if dates else None
        any_window = full_liquid_count > 0
        all_windows = full_liquid_count == len(WINDOWS)
        conn.execute(
            """
            INSERT INTO coverage_summary (
                ticker, row_count, first_date, last_date,
                full_liquid_window_count, any_window_full_liquid,
                all_windows_full_liquid, windows_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                row_count=excluded.row_count,
                first_date=excluded.first_date,
                last_date=excluded.last_date,
                full_liquid_window_count=excluded.full_liquid_window_count,
                any_window_full_liquid=excluded.any_window_full_liquid,
                all_windows_full_liquid=excluded.all_windows_full_liquid,
                windows_json=excluded.windows_json,
                updated_at=excluded.updated_at
            """,
            (
                ticker,
                row_count,
                first_date,
                last_date,
                full_liquid_count,
                1 if any_window else 0,
                1 if all_windows else 0,
                json.dumps(windows, sort_keys=True),
                generated_at,
            ),
        )
        status = "all_windows_full_liquid" if all_windows else "any_window_full_liquid" if any_window else "not_research_ready"
        status_counts[status] += 1
        full_liquid_distribution[full_liquid_count] += 1
    conn.commit()
    return {
        "coverage_status_counts": dict(status_counts),
        "full_liquid_window_distribution": {str(k): v for k, v in sorted(full_liquid_distribution.items())},
    }


def _sqlite_counts(conn: sqlite3.Connection) -> dict[str, int]:
    keys = ["ticker_universe", "ohlcv", "fetch_status", "coverage_summary"]
    return {
        key: int(conn.execute(f"SELECT COUNT(*) FROM {key}").fetchone()[0])
        for key in keys
    }


def _top_research_candidates(conn: sqlite3.Connection, limit: int = 25) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT c.ticker, u.title, c.row_count, c.full_liquid_window_count,
               c.first_date, c.last_date, c.windows_json
        FROM coverage_summary c
        JOIN ticker_universe u ON u.ticker = c.ticker
        WHERE c.any_window_full_liquid = 1
        ORDER BY c.full_liquid_window_count DESC, c.row_count DESC, c.ticker ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for ticker, title, row_count, full_windows, first_date, last_date, windows_json in rows:
        out.append(
            {
                "ticker": ticker,
                "title": title,
                "row_count": row_count,
                "full_liquid_window_count": full_windows,
                "first_date": first_date,
                "last_date": last_date,
                "windows": json.loads(windows_json),
            }
        )
    return out


def _artifact_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market OHLCV Warehouse v1",
        "",
        "## Summary",
        "",
        f"- Status: `{manifest['status']}`",
        f"- SQLite warehouse: `{manifest['warehouse_path']}`",
        f"- SEC reference tickers: `{manifest['universe']['raw_sec_ticker_count']}`",
        f"- Hygiene-pass tickers: `{manifest['universe']['hygiene_pass_count']}`",
        f"- OHLCV rows stored: `{manifest['sqlite_counts']['ohlcv']}`",
        f"- Tickers with OHLCV rows: `{manifest['loaded_ticker_count']}`",
        f"- Hygiene-pass tickers with OHLCV rows: `{manifest['loaded_hygiene_ticker_count']}`",
        f"- Remaining hygiene tickers without rows: `{manifest['remaining_hygiene_without_rows']}`",
        f"- Pending hygiene tickers not yet attempted: `{manifest['pending_fetch_ticker_count']}`",
        f"- Hygiene no-row provider gaps: `{manifest['hygiene_no_rows_count']}`",
        f"- Hygiene rate-limited tickers: `{manifest['hygiene_rate_limited_count']}`",
        f"- Fetch status counts: `{json.dumps(manifest['fetch_status_counts_total'], sort_keys=True)}`",
        f"- Download requested in latest run: `{manifest['download']['requested_ticker_count']}`",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(manifest["coverage"], indent=2, sort_keys=True),
        "```",
        "",
        "## Notes",
        "",
        "- This is a replay data warehouse, not a core-universe promotion.",
        "- Canonical snapshots and live production policy are unchanged.",
        "- Resume future runs with the same script and SQLite path.",
        "",
    ]
    return "\n".join(lines)


def _ticket(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": manifest["status"],
        "artifact": _repo_rel(ARTIFACT_PATH),
        "json": _repo_rel(MANIFEST_PATH),
        "warehouse": manifest["warehouse_path"],
        "summary": "Broad-market OHLCV SQLite warehouse v1 for core-expansion discovery and ticker elevator research.",
        "next_step": manifest["next_step"],
    }


def _experiment_log_record(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": manifest["generated_at"],
        "status": "accepted" if manifest["status"] != "failed" else "rejected",
        "hypothesis": (
            "A broad OHLCV warehouse is the measurement blocker for systematic core-expansion discovery; "
            "core can stay small while a large research universe feeds an evidence-based ticker elevator."
        ),
        "change_summary": "Create a resumable SQLite OHLCV warehouse from local SEC ticker reference plus local snapshots/Yahoo batch downloads.",
        "change_type": "measurement_repair",
        "component": "quant/experiments/exp_20260519_030_broad_market_ohlcv_warehouse.py",
        "changed_variable": "broad_market_ohlcv_warehouse_v1",
        "parameters": {
            "warehouse_path": manifest["warehouse_path"],
            "source_reference": manifest["universe"]["source_reference"],
            "fetch_range": manifest["fetch_range"],
            "batch_size": manifest["parameters"]["batch_size"],
            "max_tickers": manifest["parameters"]["max_tickers"],
            "max_fetch_tickers": manifest["parameters"]["max_fetch_tickers"],
            "offset": manifest["parameters"]["offset"],
            "resume": manifest["parameters"]["resume"],
            "sleep_between_batches": manifest["parameters"]["sleep_between_batches"],
            "threads": manifest["parameters"]["threads"],
        },
        "date_range": manifest["windows"],
        "before_metrics": {
            "warehouse_exists_before": manifest["before"]["warehouse_exists_before"],
            "sqlite_counts_before": manifest["before"]["sqlite_counts_before"],
        },
        "after_metrics": {
            "sqlite_counts": manifest["sqlite_counts"],
            "loaded_ticker_count": manifest["loaded_ticker_count"],
            "loaded_hygiene_ticker_count": manifest["loaded_hygiene_ticker_count"],
            "remaining_hygiene_without_rows": manifest["remaining_hygiene_without_rows"],
            "pending_fetch_ticker_count": manifest["pending_fetch_ticker_count"],
            "hygiene_no_rows_count": manifest["hygiene_no_rows_count"],
            "hygiene_rate_limited_count": manifest["hygiene_rate_limited_count"],
            "coverage": manifest["coverage"],
        },
        "delta_metrics": manifest["delta_metrics"],
        "expected_value_score_delta": None,
        "production_impact": manifest["production_impact"],
        "decision": "accepted_measurement_repair",
        "rejection_reason": None,
        "next_retry_requires": [
            "Do not blindly retry no-row provider gaps; only use --retry-no-rows when the provider universe changes.",
            "Run broad-market shadow replay against the warehouse-derived liquid research universe.",
        ],
        "related_files": [
            "quant/experiments/exp_20260519_030_broad_market_ohlcv_warehouse.py",
            manifest["warehouse_path"],
            _repo_rel(MANIFEST_PATH),
            _repo_rel(ARTIFACT_PATH),
        ],
        "notes": "Data warehouse only; no live orders, core universe, ranking, sizing, or strategy policy changed.",
    }


def _write_experiment_log_record(record: dict[str, Any], *, replace: bool) -> bool:
    if EXPERIMENT_LOG_PATH.exists():
        if replace:
            lines: list[str] = []
            replaced = False
            for line in EXPERIMENT_LOG_PATH.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    lines.append(line)
                    continue
                if payload.get("experiment_id") == EXPERIMENT_ID:
                    if not replaced:
                        lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
                        replaced = True
                    continue
                lines.append(line)
            if not replaced:
                lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
            EXPERIMENT_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        for line in EXPERIMENT_LOG_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("experiment_id") == EXPERIMENT_ID:
                return False
    with EXPERIMENT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def build_warehouse(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = _utc_now()
    fetch_start, fetch_end = _canonical_fetch_bounds()
    warehouse_path = _resolved_warehouse_path()
    warehouse_exists_before = warehouse_path.exists()
    conn = _connect(warehouse_path)
    before_counts = _sqlite_counts(conn)

    sec_rows = _load_sec_universe()
    _upsert_universe(conn, sec_rows, generated_at)
    hygiene_rows = [row for row in sec_rows if row["hygiene_pass"]]
    hygiene_tickers = [row["ticker"] for row in hygiene_rows]

    seed_stats = {"seeded_ticker_count": 0, "seeded_row_upserts": 0, "seed_sources": {}}
    if args.seed_local:
        seed_stats = seed_local_snapshots(
            conn,
            set(hygiene_tickers),
            start=fetch_start,
            end=fetch_end,
            generated_at=generated_at,
        )

    fetch_pool = hygiene_tickers[args.offset :]
    if args.max_tickers is not None:
        fetch_pool = fetch_pool[: max(args.max_tickers, 0)]
    reset_no_rows_count = 0
    if args.reset_no_rows_status:
        reset_no_rows_count = int(
            conn.execute(
                """
                DELETE FROM fetch_status
                WHERE status = 'no_rows'
                  AND ticker NOT IN (SELECT DISTINCT ticker FROM ohlcv)
                """
            ).rowcount
            or 0
        )
        conn.commit()

    if args.resume:
        loaded = _existing_loaded_tickers(conn)
        terminal_statuses: set[str] = {"failed"}
        if not args.retry_no_rows:
            terminal_statuses.add("no_rows")
        if not args.retry_rate_limited:
            terminal_statuses.add("rate_limited")
        terminal = _status_tickers(conn, terminal_statuses)
        fetch_pool = [ticker for ticker in fetch_pool if ticker not in loaded and ticker not in terminal]
    if args.max_fetch_tickers is not None:
        fetch_pool = fetch_pool[: max(args.max_fetch_tickers, 0)]

    download_stats = {
        "requested_ticker_count": 0,
        "rows_upserted": 0,
        "status_counts": {},
        "batch_errors": [],
        "rate_limited_ticker_count": 0,
        "stopped_early_reason": None,
    }
    if not args.universe_only and fetch_pool:
        download_stats = fetch_yfinance_batches(
            conn,
            fetch_pool,
            start=fetch_start,
            end=fetch_end,
            batch_size=args.batch_size,
            generated_at=generated_at,
            stop_on_rate_limit_count=args.stop_on_rate_limit_count,
            sleep_between_batches=args.sleep_between_batches,
            threads=args.threads,
        )

    expected_dates = _expected_dates_by_window()
    coverage_tickers = hygiene_tickers
    if args.coverage_tickers_with_rows_only:
        coverage_tickers = sorted(set(_existing_loaded_tickers(conn)) & set(hygiene_tickers))
        conn.execute(
            """
            DELETE FROM coverage_summary
            WHERE ticker NOT IN (
                SELECT DISTINCT o.ticker
                FROM ohlcv o
                JOIN ticker_universe u ON u.ticker = o.ticker
                WHERE u.hygiene_pass = 1
            )
            """
        )
    else:
        conn.execute(
            """
            DELETE FROM coverage_summary
            WHERE ticker NOT IN (
                SELECT ticker FROM ticker_universe WHERE hygiene_pass = 1
            )
            """
        )
    conn.commit()
    coverage = compute_coverage_summary(
        conn,
        coverage_tickers,
        expected_dates=expected_dates,
        generated_at=generated_at,
    )

    after_counts = _sqlite_counts(conn)
    loaded_ticker_count = int(
        conn.execute("SELECT COUNT(*) FROM (SELECT ticker FROM ohlcv GROUP BY ticker)").fetchone()[0]
    )
    loaded_hygiene_ticker_count = int(
        conn.execute(
            """
            SELECT COUNT(DISTINCT o.ticker)
            FROM ohlcv o
            JOIN ticker_universe u ON u.ticker = o.ticker
            WHERE u.hygiene_pass = 1
            """
        ).fetchone()[0]
    )
    remaining_hygiene_without_rows = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM ticker_universe u
            WHERE u.hygiene_pass = 1
              AND NOT EXISTS (
                  SELECT 1 FROM ohlcv o WHERE o.ticker = u.ticker
              )
            """
        ).fetchone()[0]
    )
    pending_fetch_ticker_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM ticker_universe u
            WHERE u.hygiene_pass = 1
              AND NOT EXISTS (
                  SELECT 1 FROM ohlcv o WHERE o.ticker = u.ticker
              )
              AND NOT EXISTS (
                  SELECT 1 FROM fetch_status f WHERE f.ticker = u.ticker
              )
            """
        ).fetchone()[0]
    )
    hygiene_no_rows_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM fetch_status f
            JOIN ticker_universe u ON u.ticker = f.ticker
            WHERE u.hygiene_pass = 1
              AND f.status = 'no_rows'
            """
        ).fetchone()[0]
    )
    hygiene_rate_limited_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM fetch_status f
            JOIN ticker_universe u ON u.ticker = f.ticker
            WHERE u.hygiene_pass = 1
              AND f.status = 'rate_limited'
            """
        ).fetchone()[0]
    )
    hygiene_failed_count = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM fetch_status f
            JOIN ticker_universe u ON u.ticker = f.ticker
            WHERE u.hygiene_pass = 1
              AND f.status = 'failed'
            """
        ).fetchone()[0]
    )
    failure_counts = dict(
        conn.execute("SELECT status, COUNT(*) FROM fetch_status GROUP BY status").fetchall()
    )
    exclusion_counts = Counter(
        reason
        for row in sec_rows
        for reason in row["exclusion_reasons"]
    )
    tag_counts = Counter(tag for row in sec_rows for tag in row["tags"])

    manifest: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": (
            "partial_warehouse_built"
            if pending_fetch_ticker_count > 0 or hygiene_rate_limited_count > 0 or hygiene_failed_count > 0
            else "warehouse_built_with_provider_gaps"
            if remaining_hygiene_without_rows > 0
            else "warehouse_built"
        ),
        "warehouse_path": _repo_rel(warehouse_path),
        "manifest_path": _repo_rel(MANIFEST_PATH),
        "fetch_range": {"start": fetch_start, "end": fetch_end},
        "windows": WINDOWS,
        "parameters": {
            "batch_size": args.batch_size,
            "max_tickers": args.max_tickers,
            "max_fetch_tickers": args.max_fetch_tickers,
            "offset": args.offset,
            "resume": args.resume,
            "seed_local": args.seed_local,
            "universe_only": args.universe_only,
            "coverage_tickers_with_rows_only": args.coverage_tickers_with_rows_only,
            "retry_no_rows": args.retry_no_rows,
            "retry_rate_limited": args.retry_rate_limited,
            "reset_no_rows_status": args.reset_no_rows_status,
            "stop_on_rate_limit_count": args.stop_on_rate_limit_count,
            "sleep_between_batches": args.sleep_between_batches,
            "threads": args.threads,
        },
        "before": {
            "warehouse_exists_before": warehouse_exists_before,
            "sqlite_counts_before": before_counts,
        },
        "universe": {
            "source_reference": _repo_rel(SEC_REFERENCE_PATH),
            "raw_sec_ticker_count": len(sec_rows),
            "hygiene_pass_count": len(hygiene_tickers),
            "excluded_count": len(sec_rows) - len(hygiene_tickers),
            "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
            "tag_counts": dict(sorted(tag_counts.items())),
        },
        "seed_local": seed_stats,
        "reset_no_rows_status_count": reset_no_rows_count,
        "download": download_stats,
        "fetch_status_counts_total": failure_counts,
        "coverage": coverage,
        "sqlite_counts": after_counts,
        "loaded_ticker_count": loaded_ticker_count,
        "loaded_hygiene_ticker_count": loaded_hygiene_ticker_count,
        "remaining_hygiene_without_rows": remaining_hygiene_without_rows,
        "pending_fetch_ticker_count": pending_fetch_ticker_count,
        "hygiene_no_rows_count": hygiene_no_rows_count,
        "hygiene_rate_limited_count": hygiene_rate_limited_count,
        "hygiene_failed_count": hygiene_failed_count,
        "delta_metrics": {
            key: after_counts[key] - before_counts.get(key, 0)
            for key in after_counts
        },
        "top_research_candidates": _top_research_candidates(conn),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "next_step": (
            "Derive a liquid research universe from loaded hygiene tickers and run broad-market shadow replay. "
            "Only retry provider gaps with explicit --retry-no-rows or --retry-rate-limited when new provider evidence exists."
        ),
    }
    conn.execute(
        """
        INSERT INTO run_manifest (experiment_id, generated_at, manifest_json)
        VALUES (?, ?, ?)
        ON CONFLICT(experiment_id) DO UPDATE SET
            generated_at=excluded.generated_at,
            manifest_json=excluded.manifest_json
        """,
        (EXPERIMENT_ID, generated_at, json.dumps(manifest, sort_keys=True)),
    )
    conn.commit()
    conn.close()
    return manifest


def persist_outputs(manifest: dict[str, Any], *, record_log: bool, replace_log: bool) -> dict[str, Any]:
    _write_json(MANIFEST_PATH, manifest)
    _write_json(LOG_PATH, manifest)
    _write_json(TICKET_PATH, _ticket(manifest))
    _write_text(ARTIFACT_PATH, _artifact_markdown(manifest))
    appended_log = False
    if record_log:
        appended_log = _write_experiment_log_record(_experiment_log_record(manifest), replace=replace_log)
    return {
        "manifest": _repo_rel(MANIFEST_PATH),
        "log": _repo_rel(LOG_PATH),
        "ticket": _repo_rel(TICKET_PATH),
        "artifact": _repo_rel(ARTIFACT_PATH),
        "warehouse": manifest["warehouse_path"],
        "experiment_log_appended": appended_log,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=80)
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--max-fetch-tickers", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--no-resume", dest="resume", action="store_false", default=True)
    parser.add_argument("--no-seed-local", dest="seed_local", action="store_false", default=True)
    parser.add_argument("--universe-only", action="store_true")
    parser.add_argument("--coverage-all-hygiene", dest="coverage_tickers_with_rows_only", action="store_false")
    parser.set_defaults(coverage_tickers_with_rows_only=True)
    parser.add_argument("--retry-no-rows", action="store_true")
    parser.add_argument("--retry-rate-limited", action="store_true")
    parser.add_argument("--reset-no-rows-status", action="store_true")
    parser.add_argument("--stop-on-rate-limit-count", type=int, default=25)
    parser.add_argument("--sleep-between-batches", type=float, default=2.5)
    parser.add_argument("--threads", action="store_true")
    parser.add_argument("--record-log", action="store_true")
    parser.add_argument("--replace-log", action="store_true")
    args = parser.parse_args()
    args.batch_size = max(1, args.batch_size)
    args.offset = max(0, args.offset)
    args.stop_on_rate_limit_count = max(0, args.stop_on_rate_limit_count)
    args.sleep_between_batches = max(0.0, args.sleep_between_batches)

    manifest = build_warehouse(args)
    outputs = persist_outputs(manifest, record_log=args.record_log, replace_log=args.replace_log)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": manifest["status"],
                "warehouse_path": manifest["warehouse_path"],
                "universe": manifest["universe"],
                "download": manifest["download"],
                "coverage": manifest["coverage"],
                "sqlite_counts": manifest["sqlite_counts"],
                "loaded_ticker_count": manifest["loaded_ticker_count"],
                "loaded_hygiene_ticker_count": manifest["loaded_hygiene_ticker_count"],
                "remaining_hygiene_without_rows": manifest["remaining_hygiene_without_rows"],
                "pending_fetch_ticker_count": manifest["pending_fetch_ticker_count"],
                "hygiene_no_rows_count": manifest["hygiene_no_rows_count"],
                "hygiene_rate_limited_count": manifest["hygiene_rate_limited_count"],
                "outputs": outputs,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
