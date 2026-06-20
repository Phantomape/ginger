from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
# exp-20260612-017: the warehouse is production infrastructure, not experiment
# output. Canonical home is data/warehouse/; the legacy exp-20260519-030 path
# is honored read-side for checkouts that have not picked up the relocation.
_CANONICAL_WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
LEGACY_WAREHOUSE_PATH = (
    REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
)
DEFAULT_WAREHOUSE_PATH = (
    _CANONICAL_WAREHOUSE_PATH
    if _CANONICAL_WAREHOUSE_PATH.exists() or not LEGACY_WAREHOUSE_PATH.exists()
    else LEGACY_WAREHOUSE_PATH
)


def hot_path_for(cold_path: str | Path = DEFAULT_WAREHOUSE_PATH) -> Path:
    """Sibling hot-tier DB for a given cold warehouse path.

    Hot/cold split (LFS churn fix): the multi-hundred-MB cold warehouse is
    git-LFS tracked, so every daily run that upserts into it re-uploads the
    whole blob as a fresh LFS object. We instead route daily/refresh writes to
    a small sibling ``*_hot.sqlite`` that grows slowly, overlay it on the cold
    base at read time, and fold it back into cold with ``merge-hot`` once a
    window (~half a year) has accumulated. The cold blob then stays byte-stable
    between merges and stops churning LFS.
    """
    p = Path(cold_path)
    return p.with_name(f"{p.stem}_hot{p.suffix}")


DEFAULT_HOT_WAREHOUSE_PATH = hot_path_for(DEFAULT_WAREHOUSE_PATH)
DEFAULT_REFERENCE_TICKERS = {
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
    # MSCI USA single-factor ETFs — reference/context only (never traded), used
    # for return-based factor attribution of the core stack (exp-20260620-021).
    "MTUM",
    "QUAL",
    "VLUE",
    "USMV",
    "SIZE",
}
DEFAULT_SNAPSHOT_RELS = [
    "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
]
SNAPSHOT_VERSION_TABLE = "ohlcv_snapshot_versions"


def default_snapshot_paths() -> list[Path]:
    return [REPO_ROOT / rel for rel in DEFAULT_SNAPSHOT_RELS]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def snapshot_source_key(value: str | Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        candidate = REPO_ROOT / path
        if candidate.exists():
            path = candidate
    return _repo_rel(path).replace("\\", "/")


def _date_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw)[:10]
    return text if len(text) == 10 else None


def _float_value(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _normalise_snapshot_row(
    row: dict[str, Any],
) -> tuple[str, float, float, float, float, float] | None:
    day = _date_text(row.get("Date") or row.get("date"))
    open_ = _float_value(row.get("Open") if "Open" in row else row.get("open"))
    high = _float_value(row.get("High") if "High" in row else row.get("high"))
    low = _float_value(row.get("Low") if "Low" in row else row.get("low"))
    close = _float_value(row.get("Close") if "Close" in row else row.get("close"))
    volume = _float_value(row.get("Volume") if "Volume" in row else row.get("volume"))
    if day is None or open_ is None or high is None or low is None or close is None:
        return None
    return day, open_, high, low, close, volume or 0.0


def _normalise_frame_row(
    day: Any,
    row: Any,
) -> tuple[str, float, float, float, float, float] | None:
    day_text = _date_text(day)
    if day_text is None:
        return None
    open_ = _float_value(row.get("Open") if "Open" in row else row.get("open"))
    high = _float_value(row.get("High") if "High" in row else row.get("high"))
    low = _float_value(row.get("Low") if "Low" in row else row.get("low"))
    close = _float_value(row.get("Close") if "Close" in row else row.get("close"))
    volume = _float_value(row.get("Volume") if "Volume" in row else row.get("volume"))
    if day_text is None or open_ is None or high is None or low is None or close is None:
        return None
    return day_text, open_, high, low, close, volume or 0.0


# Concurrent agent runs + the broad-universe refresh writer all hit the same
# warehouse_main.sqlite. With the default 5s lock timeout a read that collides
# with a writer raises "database is locked" instantly, which aborted the whole
# broad-market sleeve block intermittently. A generous busy timeout makes a
# blocked connection wait out the (short) writer transaction instead of failing.
_WAREHOUSE_BUSY_TIMEOUT_S = 60.0


def _connect(path: Path, *, journal_mode_off: bool = False) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=_WAREHOUSE_BUSY_TIMEOUT_S)
    if journal_mode_off:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
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
        f"""
        CREATE TABLE IF NOT EXISTS {SNAPSHOT_VERSION_TABLE} (
            snapshot_source TEXT NOT NULL,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (snapshot_source, ticker, date)
        )
        """
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_ohlcv_snapshot_versions_ticker_date
        ON {SNAPSHOT_VERSION_TABLE}(ticker, date)
        """
    )
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
    conn.commit()
    return conn


# Columns of the ``ohlcv`` table, in storage order. The overlay view emits the
# same shape so readers can swap ``FROM ohlcv`` -> ``FROM ohlcv_overlay`` with
# no other change.
_OHLCV_COLUMNS = "ticker, date, open, high, low, close, volume, source, updated_at"


def connect_overlay_reader(
    cold_path: str | Path = DEFAULT_WAREHOUSE_PATH,
) -> sqlite3.Connection:
    """Open a read connection over the cold warehouse with the hot tier overlaid.

    Exposes a temp view ``ohlcv_overlay`` with the same columns as ``ohlcv``.
    Hot rows win on ``(ticker, date)`` conflicts (the hot tier carries the most
    recent / corrected bars). When no hot sibling exists the view is a plain
    pass-through over ``ohlcv``, so behaviour is identical to the pre-split
    warehouse. Callers query ``ohlcv_overlay`` and close the connection as usual;
    the attach + temp view are connection-scoped.
    """
    cold = Path(cold_path)
    conn = sqlite3.connect(cold, timeout=_WAREHOUSE_BUSY_TIMEOUT_S)
    hot = hot_path_for(cold)
    attached = False
    if hot.exists():
        try:
            conn.execute("ATTACH DATABASE ? AS hot", (str(hot),))
            # Confirm the hot DB actually carries the ohlcv table before relying
            # on it; a partially-initialised file falls back to cold-only.
            conn.execute("SELECT 1 FROM hot.ohlcv LIMIT 1")
            attached = True
        except sqlite3.Error:
            try:
                conn.execute("DETACH DATABASE hot")
            except sqlite3.Error:
                pass
            attached = False
    if attached:
        conn.execute(
            f"""
            CREATE TEMP VIEW ohlcv_overlay AS
            SELECT {_OHLCV_COLUMNS} FROM hot.ohlcv
            UNION ALL
            SELECT {_OHLCV_COLUMNS} FROM main.ohlcv AS c
            WHERE NOT EXISTS (
                SELECT 1 FROM hot.ohlcv AS h
                WHERE h.ticker = c.ticker AND h.date = c.date
            )
            """
        )
    else:
        conn.execute(
            f"CREATE TEMP VIEW ohlcv_overlay AS SELECT {_OHLCV_COLUMNS} FROM ohlcv"
        )
    return conn


def _upsert_fetch_status(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    status: str,
    provider: str,
    fetched_at: str,
    error: str | None = None,
) -> None:
    row_count, first_date, last_date = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM ohlcv WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    conn.execute(
        """
        INSERT INTO fetch_status (
            ticker, status, row_count, first_date, last_date, error, provider, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET
            status = excluded.status,
            row_count = excluded.row_count,
            first_date = excluded.first_date,
            last_date = excluded.last_date,
            error = excluded.error,
            provider = excluded.provider,
            fetched_at = excluded.fetched_at
        """,
        (
            ticker,
            status,
            int(row_count or 0),
            first_date,
            last_date,
            error,
            provider,
            fetched_at,
        ),
    )


def _same_ohlcv(
    existing: tuple[Any, Any, Any, Any, Any],
    values: tuple[float, float, float, float, float],
) -> bool:
    return all(abs(float(a) - float(b)) <= 1e-12 for a, b in zip(existing, values))


def _insert_fetch_status_if_missing(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    fetched_at: str,
) -> bool:
    row_count, first_date, last_date = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM ohlcv WHERE ticker = ?",
        (ticker,),
    ).fetchone()
    status = (
        "seeded_local_reference"
        if ticker in DEFAULT_REFERENCE_TICKERS
        else "seeded_local"
    )
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO fetch_status (
            ticker, status, row_count, first_date, last_date, error, provider, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ticker,
            status,
            int(row_count or 0),
            first_date,
            last_date,
            None,
            "local_snapshot_seed",
            fetched_at,
        ),
    )
    return bool(cur.rowcount)


def upsert_ohlcv_frames(
    db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    frames_by_ticker: dict[str, pd.DataFrame | None] | Iterable[tuple[str, pd.DataFrame | None]] = (),
    *,
    source: str = "run.py:yfinance",
    provider: str = "yfinance",
    fetched_at: str | None = None,
    update_existing: bool = False,
    commit_every: int = 1000,
) -> dict[str, Any]:
    """Upsert downloaded OHLCV frames into the SQLite warehouse.

    Production daily runs should normally leave ``update_existing`` false so
    deterministic research rows are not silently rewritten by vendor adjustment
    drift. Dedicated refresh/rebuild jobs can opt in to updating existing rows.
    """
    if isinstance(frames_by_ticker, dict):
        items = list(frames_by_ticker.items())
    else:
        items = list(frames_by_ticker)

    db = Path(db_path)
    now = fetched_at or _utc_now()
    commit_every = max(1, int(commit_every))
    inserted = 0
    updated = 0
    unchanged = 0
    skipped_existing = 0
    skipped_rows = 0
    empty_tickers: list[str] = []
    touched_tickers: set[str] = set()
    processed_tickers: set[str] = set()
    pending_writes = 0

    conn = _connect(db)
    try:
        for raw_ticker, frame in items:
            ticker = str(raw_ticker).upper().strip()
            if not ticker:
                continue
            if frame is None or getattr(frame, "empty", True):
                empty_tickers.append(ticker)
                _upsert_fetch_status(
                    conn,
                    ticker,
                    status="empty",
                    provider=provider,
                    fetched_at=now,
                    error="no_ohlcv_rows",
                )
                pending_writes += 1
                if pending_writes >= commit_every:
                    conn.commit()
                    pending_writes = 0
                continue

            processed_tickers.add(ticker)
            for day, row in frame.iterrows():
                normalised = _normalise_frame_row(day, row)
                if normalised is None:
                    skipped_rows += 1
                    continue
                day_text, open_, high, low, close, volume = normalised
                values = (open_, high, low, close, volume)
                existing = conn.execute(
                    """
                    SELECT open, high, low, close, volume
                    FROM ohlcv
                    WHERE ticker = ? AND date = ?
                    """,
                    (ticker, day_text),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO ohlcv (
                            ticker, date, open, high, low, close, volume,
                            source, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ticker,
                            day_text,
                            open_,
                            high,
                            low,
                            close,
                            volume,
                            source,
                            now,
                        ),
                    )
                    inserted += 1
                    touched_tickers.add(ticker)
                    pending_writes += 1
                elif update_existing and not _same_ohlcv(existing, values):
                    conn.execute(
                        """
                        UPDATE ohlcv
                        SET open = ?, high = ?, low = ?, close = ?,
                            volume = ?, source = ?, updated_at = ?
                        WHERE ticker = ? AND date = ?
                        """,
                        (
                            open_,
                            high,
                            low,
                            close,
                            volume,
                            source,
                            now,
                            ticker,
                            day_text,
                        ),
                    )
                    updated += 1
                    touched_tickers.add(ticker)
                    pending_writes += 1
                else:
                    unchanged += 1
                    if not update_existing:
                        skipped_existing += 1

                if pending_writes >= commit_every:
                    conn.commit()
                    pending_writes = 0

            _upsert_fetch_status(
                conn,
                ticker,
                status="ok",
                provider=provider,
                fetched_at=now,
            )
            pending_writes += 1
            if pending_writes >= commit_every:
                conn.commit()
                pending_writes = 0

        if pending_writes:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "db_path": str(db),
        "source": source,
        "provider": provider,
        "fetched_at": now,
        "ticker_count": len({str(t).upper().strip() for t, _frame in items if str(t).strip()}),
        "processed_ticker_count": len(processed_tickers),
        "empty_ticker_count": len(set(empty_tickers)),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "skipped_existing": skipped_existing,
        "skipped_rows": skipped_rows,
        "touched_ticker_count": len(touched_tickers),
        "processed_tickers": sorted(processed_tickers),
        "touched_tickers": sorted(touched_tickers),
        "empty_tickers": sorted(set(empty_tickers)),
        "update_existing": update_existing,
    }


def seed_warehouse_from_snapshots(
    db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    snapshot_paths: Iterable[str | Path] | None = None,
    *,
    update_existing: bool = True,
    journal_mode_off: bool = False,
    commit_every: int = 1000,
) -> dict[str, Any]:
    """Seed/update warehouse OHLCV rows from deterministic snapshot JSON files.

    This is intended to keep the broad ticker SQLite warehouse usable as the
    superset OHLCV source while preserving the exact fixed-window snapshot
    values for the canonical replay subset.
    """
    db = Path(db_path)
    paths = [Path(p) for p in (snapshot_paths or default_snapshot_paths())]
    paths = [p if p.is_absolute() else REPO_ROOT / p for p in paths]
    now = _utc_now()
    inserted = 0
    updated = 0
    unchanged = 0
    skipped = 0
    commit_every = max(1, int(commit_every))
    pending_writes = 0
    touched_tickers: set[str] = set()
    source_counts: dict[str, dict[str, int]] = {}

    conn = _connect(db, journal_mode_off=journal_mode_off)
    try:
        for path in paths:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows_by_ticker = payload.get("ohlcv") or {}
            rel = _repo_rel(path)
            source_counts.setdefault(
                rel,
                {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0},
            )
            for raw_ticker, raw_rows in rows_by_ticker.items():
                ticker = str(raw_ticker).upper().strip()
                if not ticker:
                    continue
                for raw_row in raw_rows or []:
                    if not isinstance(raw_row, dict):
                        skipped += 1
                        source_counts[rel]["skipped"] += 1
                        continue
                    normalised = _normalise_snapshot_row(raw_row)
                    if normalised is None:
                        skipped += 1
                        source_counts[rel]["skipped"] += 1
                        continue
                    day, open_, high, low, close, volume = normalised
                    values = (open_, high, low, close, volume)
                    existing = conn.execute(
                        """
                        SELECT open, high, low, close, volume
                        FROM ohlcv
                        WHERE ticker = ? AND date = ?
                        """,
                        (ticker, day),
                    ).fetchone()
                    if existing is None:
                        conn.execute(
                            """
                            INSERT INTO ohlcv (
                                ticker, date, open, high, low, close, volume,
                                source, updated_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (ticker, day, open_, high, low, close, volume, rel, now),
                        )
                        inserted += 1
                        pending_writes += 1
                        source_counts[rel]["inserted"] += 1
                        touched_tickers.add(ticker)
                    elif update_existing and not _same_ohlcv(existing, values):
                        conn.execute(
                            """
                            UPDATE ohlcv
                            SET open = ?, high = ?, low = ?, close = ?,
                                volume = ?, source = ?, updated_at = ?
                            WHERE ticker = ? AND date = ?
                            """,
                            (open_, high, low, close, volume, rel, now, ticker, day),
                        )
                        updated += 1
                        pending_writes += 1
                        source_counts[rel]["updated"] += 1
                        touched_tickers.add(ticker)
                    else:
                        unchanged += 1
                        source_counts[rel]["unchanged"] += 1
                    if pending_writes >= commit_every:
                        conn.commit()
                        pending_writes = 0
            if pending_writes:
                conn.commit()
                pending_writes = 0

        fetch_status_inserted = 0
        for ticker in sorted(touched_tickers):
            if _insert_fetch_status_if_missing(conn, ticker, fetched_at=now):
                fetch_status_inserted += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "db_path": str(db),
        "snapshot_count": len(paths),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "skipped": skipped,
        "touched_ticker_count": len(touched_tickers),
        "touched_tickers": sorted(touched_tickers),
        "fetch_status_inserted": fetch_status_inserted,
        "source_counts": source_counts,
        "updated_at": now,
    }


def seed_warehouse_snapshot_versions(
    db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    snapshot_paths: Iterable[str | Path] | None = None,
    *,
    replace_source: bool = False,
    journal_mode_off: bool = False,
    commit_every: int = 1000,
) -> dict[str, Any]:
    """Persist fixed-window OHLCV snapshots under a source-version key.

    Unlike the broad ``ohlcv`` table, this table preserves one row per
    ``(snapshot_source, ticker, date)`` so overlapping fixed-window snapshots
    can coexist without adjusted-price drift or universe changes.
    """
    db = Path(db_path)
    paths = [Path(p) for p in (snapshot_paths or default_snapshot_paths())]
    paths = [p if p.is_absolute() else REPO_ROOT / p for p in paths]
    now = _utc_now()
    commit_every = max(1, int(commit_every))
    inserted = 0
    updated = 0
    unchanged = 0
    skipped = 0
    deleted = 0
    pending_writes = 0
    source_counts: dict[str, dict[str, int]] = {}
    touched_tickers: set[str] = set()

    conn = _connect(db, journal_mode_off=journal_mode_off)
    try:
        for path in paths:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows_by_ticker = payload.get("ohlcv") or {}
            source = snapshot_source_key(path)
            source_counts.setdefault(
                source,
                {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0, "deleted": 0},
            )
            if replace_source:
                cur = conn.execute(
                    f"DELETE FROM {SNAPSHOT_VERSION_TABLE} WHERE snapshot_source = ?",
                    (source,),
                )
                deleted += int(cur.rowcount or 0)
                source_counts[source]["deleted"] += int(cur.rowcount or 0)

            for raw_ticker, raw_rows in rows_by_ticker.items():
                ticker = str(raw_ticker).upper().strip()
                if not ticker:
                    continue
                for raw_row in raw_rows or []:
                    if not isinstance(raw_row, dict):
                        skipped += 1
                        source_counts[source]["skipped"] += 1
                        continue
                    normalised = _normalise_snapshot_row(raw_row)
                    if normalised is None:
                        skipped += 1
                        source_counts[source]["skipped"] += 1
                        continue
                    day, open_, high, low, close, volume = normalised
                    values = (open_, high, low, close, volume)
                    existing = conn.execute(
                        f"""
                        SELECT open, high, low, close, volume
                        FROM {SNAPSHOT_VERSION_TABLE}
                        WHERE snapshot_source = ? AND ticker = ? AND date = ?
                        """,
                        (source, ticker, day),
                    ).fetchone()
                    if existing is None:
                        conn.execute(
                            f"""
                            INSERT INTO {SNAPSHOT_VERSION_TABLE} (
                                snapshot_source, ticker, date, open, high, low,
                                close, volume, updated_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (source, ticker, day, open_, high, low, close, volume, now),
                        )
                        inserted += 1
                        source_counts[source]["inserted"] += 1
                        touched_tickers.add(ticker)
                        pending_writes += 1
                    elif not _same_ohlcv(existing, values):
                        conn.execute(
                            f"""
                            UPDATE {SNAPSHOT_VERSION_TABLE}
                            SET open = ?, high = ?, low = ?, close = ?,
                                volume = ?, updated_at = ?
                            WHERE snapshot_source = ? AND ticker = ? AND date = ?
                            """,
                            (
                                open_,
                                high,
                                low,
                                close,
                                volume,
                                now,
                                source,
                                ticker,
                                day,
                            ),
                        )
                        updated += 1
                        source_counts[source]["updated"] += 1
                        touched_tickers.add(ticker)
                        pending_writes += 1
                    else:
                        unchanged += 1
                        source_counts[source]["unchanged"] += 1

                    if pending_writes >= commit_every:
                        conn.commit()
                        pending_writes = 0
            if pending_writes:
                conn.commit()
                pending_writes = 0
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "db_path": str(db),
        "snapshot_count": len(paths),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": deleted,
        "skipped": skipped,
        "touched_ticker_count": len(touched_tickers),
        "touched_tickers": sorted(touched_tickers),
        "source_counts": source_counts,
        "updated_at": now,
    }


def _snapshot_overlay(
    snapshot_paths: Iterable[str | Path] | None = None,
) -> tuple[
    dict[tuple[str, str], tuple[float, float, float, float, float, str]],
    dict[str, int],
]:
    overlay: dict[tuple[str, str], tuple[float, float, float, float, float, str]] = {}
    source_counts: dict[str, int] = {}
    paths = [Path(p) for p in (snapshot_paths or default_snapshot_paths())]
    paths = [p if p.is_absolute() else REPO_ROOT / p for p in paths]
    for path in paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rel = _repo_rel(path)
        source_count = 0
        for raw_ticker, raw_rows in (payload.get("ohlcv") or {}).items():
            ticker = str(raw_ticker).upper().strip()
            if not ticker:
                continue
            for raw_row in raw_rows or []:
                if not isinstance(raw_row, dict):
                    continue
                normalised = _normalise_snapshot_row(raw_row)
                if normalised is None:
                    continue
                day, open_, high, low, close, volume = normalised
                overlay[(ticker, day)] = (open_, high, low, close, volume, rel)
                source_count += 1
        source_counts[rel] = source_count
    return overlay, source_counts


def _copy_table_rows(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    table: str,
    *,
    batch_size: int = 5000,
) -> int:
    cols = [row[1] for row in src.execute(f"PRAGMA table_info({table})").fetchall()]
    if not cols:
        return 0
    col_sql = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    inserted = 0
    batch: list[tuple[Any, ...]] = []
    for row in src.execute(f"SELECT {col_sql} FROM {table}"):
        batch.append(tuple(row))
        if len(batch) >= batch_size:
            dst.executemany(
                f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
                batch,
            )
            inserted += len(batch)
            batch = []
    if batch:
        dst.executemany(
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
            batch,
        )
        inserted += len(batch)
    dst.commit()
    return inserted


def rebuild_warehouse_with_snapshots(
    src_db_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    dst_db_path: str | Path | None = None,
    snapshot_paths: Iterable[str | Path] | None = None,
    *,
    overwrite: bool = False,
    batch_size: int = 20000,
) -> dict[str, Any]:
    """Build a compact warehouse copy with snapshot rows applied.

    This avoids in-place random updates on the large LFS SQLite file. The
    caller can integrity-check the rebuilt file before replacing the source.
    """
    src_path = Path(src_db_path)
    dst_path = Path(dst_db_path) if dst_db_path is not None else src_path.with_suffix(".rebuilt.sqlite")
    if dst_path.exists():
        if not overwrite:
            raise FileExistsError(dst_path)
        dst_path.unlink()
    journal_path = Path(f"{dst_path}-journal")
    if journal_path.exists():
        journal_path.unlink()

    overlay, source_counts = _snapshot_overlay(snapshot_paths)
    original_overlay_count = len(overlay)
    now = _utc_now()
    copied_rows: dict[str, int] = {}
    inserted_ohlcv = 0
    overlay_updates = 0
    unchanged_ohlcv = 0

    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dst = sqlite3.connect(dst_path)
    try:
        dst.execute("PRAGMA journal_mode=OFF")
        dst.execute("PRAGMA synchronous=OFF")
        dst.execute("PRAGMA temp_store=MEMORY")

        table_defs = src.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        for _name, sql in table_defs:
            if sql:
                dst.execute(sql)
        dst.commit()

        for table, _sql in table_defs:
            if table == "ohlcv":
                continue
            copied_rows[table] = _copy_table_rows(src, dst, table, batch_size=batch_size)

        batch: list[tuple[Any, ...]] = []
        for ticker, day, open_, high, low, close, volume, source, updated_at in src.execute(
            """
            SELECT ticker, date, open, high, low, close, volume, source, updated_at
            FROM ohlcv
            ORDER BY ticker, date
            """
        ):
            key = (str(ticker), str(day))
            overlay_row = overlay.pop(key, None)
            if overlay_row is not None:
                new_open, new_high, new_low, new_close, new_volume, new_source = overlay_row
                existing_values = (open_, high, low, close, volume)
                new_values = (new_open, new_high, new_low, new_close, new_volume)
                if _same_ohlcv(existing_values, new_values):
                    unchanged_ohlcv += 1
                    row = (
                        ticker,
                        day,
                        open_,
                        high,
                        low,
                        close,
                        volume,
                        source,
                        updated_at,
                    )
                else:
                    overlay_updates += 1
                    row = (
                        ticker,
                        day,
                        new_open,
                        new_high,
                        new_low,
                        new_close,
                        new_volume,
                        new_source,
                        now,
                    )
            else:
                unchanged_ohlcv += 1
                row = (ticker, day, open_, high, low, close, volume, source, updated_at)
            batch.append(row)
            if len(batch) >= batch_size:
                dst.executemany(
                    """
                    INSERT INTO ohlcv (
                        ticker, date, open, high, low, close, volume, source, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                inserted_ohlcv += len(batch)
                batch = []
        if batch:
            dst.executemany(
                """
                INSERT INTO ohlcv (
                    ticker, date, open, high, low, close, volume, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            inserted_ohlcv += len(batch)
        dst.commit()

        reference_inserts = 0
        if overlay:
            batch = []
            for (ticker, day), (open_, high, low, close, volume, source) in sorted(overlay.items()):
                batch.append((ticker, day, open_, high, low, close, volume, source, now))
                if len(batch) >= batch_size:
                    dst.executemany(
                        """
                        INSERT INTO ohlcv (
                            ticker, date, open, high, low, close, volume, source, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    reference_inserts += len(batch)
                    batch = []
            if batch:
                dst.executemany(
                    """
                    INSERT INTO ohlcv (
                        ticker, date, open, high, low, close, volume, source, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                reference_inserts += len(batch)
        copied_rows["ohlcv"] = inserted_ohlcv + reference_inserts

        fetch_status_inserted = 0
        touched_reference_tickers = {ticker for ticker, _day in overlay}
        for ticker in sorted(touched_reference_tickers):
            if _insert_fetch_status_if_missing(dst, ticker, fetched_at=now):
                fetch_status_inserted += 1

        index_defs = src.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'index'
              AND sql IS NOT NULL
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        for _name, sql in index_defs:
            if sql:
                dst.execute(sql)
        dst.commit()
    finally:
        src.close()
        dst.close()

    return {
        "src_db_path": str(src_path),
        "dst_db_path": str(dst_path),
        "snapshot_overlay_rows": original_overlay_count,
        "overlay_updates": overlay_updates,
        "reference_inserts": reference_inserts,
        "unchanged_ohlcv": unchanged_ohlcv,
        "fetch_status_inserted": fetch_status_inserted,
        "copied_rows": copied_rows,
        "source_counts": source_counts,
        "rebuilt_at": now,
    }


def load_warehouse_ohlcv_frames(
    db_path: str | Path,
    tickers: Iterable[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    """Load OHLCV frames from the SQLite warehouse in backtester shape."""
    db = Path(db_path)
    ticker_list = sorted({str(t).upper().strip() for t in tickers if str(t).strip()})
    if not ticker_list:
        return {}
    start_text = str(pd.Timestamp(start).date())
    end_text = str(pd.Timestamp(end).date())
    placeholders = ",".join("?" for _ in ticker_list)
    sql = f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM ohlcv_overlay
        WHERE ticker IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY ticker, date
    """
    params = [*ticker_list, start_text, end_text]
    by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in ticker_list}
    conn = connect_overlay_reader(db)
    try:
        for ticker, day, open_, high, low, close, volume in conn.execute(sql, params):
            by_ticker[str(ticker)].append(
                {
                    "Date": day,
                    "Open": float(open_),
                    "High": float(high),
                    "Low": float(low),
                    "Close": float(close),
                    "Volume": float(volume),
                }
            )
    finally:
        conn.close()

    frames: dict[str, pd.DataFrame] = {}
    for ticker, rows in by_ticker.items():
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        frames[ticker] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return frames


def load_warehouse_snapshot_ohlcv_frames(
    db_path: str | Path,
    snapshot_source: str | Path,
    tickers: Iterable[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    """Load a fixed-window snapshot version from the SQLite warehouse."""
    db = Path(db_path)
    source = snapshot_source_key(snapshot_source)
    ticker_list = sorted({str(t).upper().strip() for t in tickers if str(t).strip()})
    if not ticker_list:
        return {}
    start_text = str(pd.Timestamp(start).date())
    end_text = str(pd.Timestamp(end).date())
    placeholders = ",".join("?" for _ in ticker_list)
    sql = f"""
        SELECT ticker, date, open, high, low, close, volume
        FROM {SNAPSHOT_VERSION_TABLE}
        WHERE snapshot_source = ?
          AND ticker IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY ticker, date
    """
    params = [source, *ticker_list, start_text, end_text]
    by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in ticker_list}
    with sqlite3.connect(db, timeout=_WAREHOUSE_BUSY_TIMEOUT_S) as conn:
        for ticker, day, open_, high, low, close, volume in conn.execute(sql, params):
            by_ticker[str(ticker)].append(
                {
                    "Date": day,
                    "Open": float(open_),
                    "High": float(high),
                    "Low": float(low),
                    "Close": float(close),
                    "Volume": float(volume),
                }
            )

    frames: dict[str, pd.DataFrame] = {}
    for ticker, rows in by_ticker.items():
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        frame["Date"] = pd.to_datetime(frame["Date"])
        frame = frame.set_index("Date").sort_index()
        frame.index.name = None
        frames[ticker] = frame[["Open", "High", "Low", "Close", "Volume"]]
    return frames


def hot_status(
    cold_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    hot_path: str | Path | None = None,
) -> dict[str, Any]:
    """Summarise the hot tier: row/ticker counts and date span pending merge."""
    cold = Path(cold_path)
    hot = Path(hot_path) if hot_path else hot_path_for(cold)
    out: dict[str, Any] = {
        "cold_path": str(cold),
        "hot_path": str(hot),
        "hot_exists": hot.exists(),
    }
    if not hot.exists():
        out["status"] = "no_hot"
        return out
    conn = sqlite3.connect(hot, timeout=_WAREHOUSE_BUSY_TIMEOUT_S)
    try:
        rows, tickers, first_date, last_date = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(date), MAX(date) FROM ohlcv"
        ).fetchone()
    except sqlite3.Error as exc:
        out["status"] = "unreadable"
        out["error"] = str(exc)
        return out
    finally:
        conn.close()
    out["status"] = "ok"
    out["row_count"] = int(rows or 0)
    out["ticker_count"] = int(tickers or 0)
    out["first_date"] = str(first_date)[:10] if first_date else None
    out["last_date"] = str(last_date)[:10] if last_date else None
    out["hot_size_bytes"] = hot.stat().st_size
    return out


def merge_hot_into_cold(
    cold_path: str | Path = DEFAULT_WAREHOUSE_PATH,
    hot_path: str | Path | None = None,
    *,
    reset_hot: bool = True,
    vacuum: bool = True,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Fold accumulated hot-tier rows into the cold warehouse.

    Run this once a window (~half a year) has accumulated in the hot DB. Hot
    rows carry dates after the cold base's max, so ``INSERT OR IGNORE`` inserts
    the new bars and never rewrites cold's deterministic research rows (matching
    the warehouse-wide ``update_existing=False`` contract). ``fetch_status`` for
    merged tickers is recomputed from the merged cold table. With ``reset_hot``
    the hot DB is then emptied and VACUUMed so the committed blob shrinks back to
    ~empty for the next window.
    """
    cold = Path(cold_path)
    hot = Path(hot_path) if hot_path else hot_path_for(cold)
    now = fetched_at or _utc_now()
    summary: dict[str, Any] = {
        "cold_path": str(cold),
        "hot_path": str(hot),
        "fetched_at": now,
        "reset_hot": reset_hot,
        "vacuum": vacuum,
    }
    if not hot.exists():
        summary["status"] = "no_hot"
        summary["inserted"] = 0
        return summary

    conn = _connect(cold)
    try:
        conn.execute("ATTACH DATABASE ? AS hot", (str(hot),))
        cold_before = conn.execute("SELECT COUNT(*) FROM main.ohlcv").fetchone()[0]
        hot_rows = conn.execute("SELECT COUNT(*) FROM hot.ohlcv").fetchone()[0]
        merged_tickers = conn.execute(
            "SELECT COUNT(DISTINCT ticker) FROM hot.ohlcv"
        ).fetchone()[0]
        conn.execute(
            f"""
            INSERT OR IGNORE INTO main.ohlcv ({_OHLCV_COLUMNS})
            SELECT {_OHLCV_COLUMNS} FROM hot.ohlcv
            """
        )
        # Recompute fetch_status for merged tickers from the merged cold rows so
        # row_count / first_date / last_date reflect the full cold history, not
        # the hot-only slice.
        conn.execute(
            """
            INSERT INTO main.fetch_status (
                ticker, status, row_count, first_date, last_date,
                error, provider, fetched_at
            )
            SELECT o.ticker, 'ok', COUNT(*), MIN(o.date), MAX(o.date),
                   NULL, 'warehouse_merge', ?
            FROM main.ohlcv o
            WHERE o.ticker IN (SELECT DISTINCT ticker FROM hot.ohlcv)
            GROUP BY o.ticker
            ON CONFLICT(ticker) DO UPDATE SET
                status = excluded.status,
                row_count = excluded.row_count,
                first_date = excluded.first_date,
                last_date = excluded.last_date,
                error = excluded.error,
                provider = excluded.provider,
                fetched_at = excluded.fetched_at
            """,
            (now,),
        )
        conn.commit()
        cold_after = conn.execute("SELECT COUNT(*) FROM main.ohlcv").fetchone()[0]
        if reset_hot:
            conn.execute("DELETE FROM hot.ohlcv")
            conn.execute("DELETE FROM hot.fetch_status")
            conn.commit()
        conn.execute("DETACH DATABASE hot")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    inserted = int(cold_after - cold_before)
    summary["status"] = "merged"
    summary["hot_row_count"] = int(hot_rows or 0)
    summary["merged_ticker_count"] = int(merged_tickers or 0)
    summary["inserted"] = inserted
    summary["skipped_existing"] = int((hot_rows or 0) - inserted)
    summary["cold_row_count"] = int(cold_after)

    if reset_hot and vacuum and hot.exists():
        # VACUUM cannot run inside a transaction or with an attached DB, so do it
        # on a fresh standalone connection after the merge has detached hot.
        hc = sqlite3.connect(hot, timeout=_WAREHOUSE_BUSY_TIMEOUT_S)
        try:
            hc.execute("VACUUM")
        finally:
            hc.close()
        summary["hot_size_bytes_after"] = hot.stat().st_size
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="OHLCV warehouse helpers.")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed-snapshots", help="Seed/update warehouse rows from snapshots.")
    seed.add_argument("--db-path", default=str(DEFAULT_WAREHOUSE_PATH))
    seed.add_argument("--snapshot", action="append", default=None)
    seed.add_argument("--no-update-existing", action="store_true")
    seed.add_argument("--journal-mode-off", action="store_true")
    seed.add_argument("--commit-every", type=int, default=1000)
    seed_versions = sub.add_parser(
        "seed-snapshot-versions",
        help="Persist deterministic snapshots under source-version keys.",
    )
    seed_versions.add_argument("--db-path", default=str(DEFAULT_WAREHOUSE_PATH))
    seed_versions.add_argument("--snapshot", action="append", default=None)
    seed_versions.add_argument("--replace-source", action="store_true")
    seed_versions.add_argument("--journal-mode-off", action="store_true")
    seed_versions.add_argument("--commit-every", type=int, default=1000)
    rebuild = sub.add_parser(
        "rebuild-with-snapshots",
        help="Build a new warehouse DB with deterministic snapshot rows applied.",
    )
    rebuild.add_argument("--src-db-path", default=str(DEFAULT_WAREHOUSE_PATH))
    rebuild.add_argument("--dst-db-path", required=True)
    rebuild.add_argument("--snapshot", action="append", default=None)
    rebuild.add_argument("--force", action="store_true")
    rebuild.add_argument("--batch-size", type=int, default=20000)
    merge = sub.add_parser(
        "merge-hot",
        help="Fold the accumulated hot tier back into the cold warehouse.",
    )
    merge.add_argument("--db-path", default=str(DEFAULT_WAREHOUSE_PATH))
    merge.add_argument("--hot-path", default=None, help="Defaults to <db>_hot.sqlite.")
    merge.add_argument(
        "--keep-hot",
        action="store_true",
        help="Do not empty/VACUUM the hot DB after merging.",
    )
    merge.add_argument("--no-vacuum", action="store_true")
    hot_stat = sub.add_parser(
        "hot-status",
        help="Show hot-tier row/ticker counts and date span pending merge.",
    )
    hot_stat.add_argument("--db-path", default=str(DEFAULT_WAREHOUSE_PATH))
    hot_stat.add_argument("--hot-path", default=None)
    args = parser.parse_args()

    if args.command == "seed-snapshots":
        summary = seed_warehouse_from_snapshots(
            args.db_path,
            args.snapshot,
            update_existing=not args.no_update_existing,
            journal_mode_off=args.journal_mode_off,
            commit_every=args.commit_every,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "seed-snapshot-versions":
        summary = seed_warehouse_snapshot_versions(
            args.db_path,
            args.snapshot,
            replace_source=args.replace_source,
            journal_mode_off=args.journal_mode_off,
            commit_every=args.commit_every,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "rebuild-with-snapshots":
        summary = rebuild_warehouse_with_snapshots(
            args.src_db_path,
            args.dst_db_path,
            args.snapshot,
            overwrite=args.force,
            batch_size=args.batch_size,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "merge-hot":
        summary = merge_hot_into_cold(
            args.db_path,
            args.hot_path,
            reset_hot=not args.keep_hot,
            vacuum=not args.no_vacuum,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "hot-status":
        summary = hot_status(args.db_path, args.hot_path)
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
