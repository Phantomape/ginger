#!/usr/bin/env python3
"""Authorized Massive full-market research-PIT staging warehouse.

This module is deliberately isolated from Ginger's production OHLCV warehouse.
It freezes exact API responses and normalized rows in one SQLite transaction,
uses unadjusted daily bars, and never persists credentials.  The resulting
surface is research-only until a separate promotion proves canonical PIT,
effective-dated identity, split semantics, and replay/daily parity.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
DEFAULT_KEY_FILE = REPO_ROOT / "secrets" / "massive.txt"
API_ORIGIN = "https://api.massive.com"
ALLOWED_API_HOST = "api.massive.com"
SCHEMA_VERSION = 4
DEFAULT_MIN_INTERVAL_SECONDS = 12.1  # Individual-key documented limit: 5/min.
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_REFERENCE_PAGES = 100
DEFAULT_MAX_SPLIT_PAGES = 10_000
DEFAULT_MAX_DIVIDEND_PAGES = 1_000
DEFAULT_SPLIT_SNAPSHOT_START = "2024-07-29"
DEFAULT_SPLIT_SNAPSHOT_END = "2026-07-24"
DEFAULT_DIVIDEND_SNAPSHOT_START = "2021-01-01"
DEFAULT_DIVIDEND_SNAPSHOT_END = "2026-05-31"
DIVIDEND_PRIOR_GAP_DAYS = 1_095
DIVIDEND_MIN_PREDECISION_BARS = 20
DIVIDEND_MIN_CLOSE = Decimal("3")
DIVIDEND_MIN_MEDIAN_DOLLAR_VOLUME = Decimal("1000000")
DIVIDEND_TOP_PER_DAY = 2
DIVIDEND_FIXED_WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}
EXPECTED_GROUPED_DAILY_CHECKPOINTS = 520
DEFAULT_MIN_REFERENCE_ASOF_ROWS = 1_000
DEFAULT_REFERENCE_ASOF_DATES = (
    "2024-10-02",
    "2024-11-01",
    "2024-12-02",
    "2025-01-02",
    "2025-02-03",
    "2025-03-03",
    "2025-04-01",
    "2025-05-01",
    "2025-06-02",
    "2025-07-01",
    "2025-08-01",
    "2025-09-02",
    "2025-10-01",
    "2025-11-03",
    "2025-12-01",
    "2026-01-02",
    "2026-02-02",
    "2026-03-02",
    "2026-04-01",
)
ALLOWED_SPLIT_TYPES = frozenset(
    {"forward_split", "reverse_split", "stock_dividend"}
)


class MassiveError(RuntimeError):
    """Fail-closed source, validation, or persistence error."""


@dataclasses.dataclass(frozen=True)
class FetchedPayload:
    url: str
    retrieved_at: str
    status_code: int
    raw_bytes: bytes = dataclasses.field(repr=False)
    sha256: str
    payload: Mapping[str, Any] = dataclasses.field(repr=False)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_api_key(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Load a credential without logging it; environment wins over file."""

    source_environ = os.environ if environ is None else environ
    value = str(source_environ.get("MASSIVE_API_KEY", "")).strip()
    if not value:
        key_path = Path(path) if path is not None else DEFAULT_KEY_FILE
        try:
            value = key_path.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise MassiveError(f"Massive credential file is unavailable: {key_path}") from exc
    if not value or "\n" in value or "\r" in value:
        raise MassiveError("Massive credential must be one non-empty line")
    return value


def _sanitize_api_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(str(url))
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or host != ALLOWED_API_HOST or parsed.username:
        label = host or "missing-host"
        raise MassiveError(f"Refusing non-allowlisted Massive API host: {label}")
    filtered = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in {"apikey", "api_key"}
    ]
    query = urllib.parse.urlencode(filtered, doseq=True)
    return urllib.parse.urlunsplit(("https", ALLOWED_API_HOST, parsed.path, query, ""))


class MassiveClient:
    """Small injectable HTTP client with bounded retry and credential hygiene."""

    def __init__(
        self,
        api_key: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        key = str(api_key).strip()
        if not key:
            raise MassiveError("Massive credential is empty")
        self._api_key = key
        self._opener = opener
        self._sleep = sleep
        self.max_attempts = max(1, int(max_attempts))
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.max_response_bytes = max(1024, int(max_response_bytes))
        self._last_attempt_monotonic: float | None = None

    def __repr__(self) -> str:
        return (
            "MassiveClient(api_key=<redacted>, "
            f"max_attempts={self.max_attempts}, "
            f"min_interval_seconds={self.min_interval_seconds})"
        )

    def _pace(self) -> None:
        now = time.monotonic()
        if self._last_attempt_monotonic is not None:
            remaining = self.min_interval_seconds - (now - self._last_attempt_monotonic)
            if remaining > 0:
                self._sleep(remaining)
        self._last_attempt_monotonic = time.monotonic()

    @staticmethod
    def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
        raw = None
        try:
            raw = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(raw) if raw is not None else float(2 ** max(0, attempt - 1))
        except (TypeError, ValueError):
            delay = float(2 ** max(0, attempt - 1))
        return min(60.0, max(0.0, delay))

    def get_json(self, url: str) -> FetchedPayload:
        safe_url = _sanitize_api_url(url)
        for attempt in range(1, self.max_attempts + 1):
            self._pace()
            request = urllib.request.Request(
                safe_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "application/json",
                    "User-Agent": "ginger-massive-research-pit/1.0",
                },
                method="GET",
            )
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read(self.max_response_bytes + 1)
                    status_code = int(getattr(response, "status", response.getcode()))
                    response_url = _sanitize_api_url(
                        getattr(response, "geturl", lambda: safe_url)()
                    )
                if len(raw) > self.max_response_bytes:
                    raise MassiveError("Massive response exceeded the configured size bound")
                if self._api_key.encode("utf-8") in raw:
                    raise MassiveError("Massive response contained credential material")
                try:
                    decoded = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise MassiveError("Massive response was not valid UTF-8 JSON") from exc
                if not isinstance(decoded, Mapping):
                    raise MassiveError("Massive response root must be a JSON object")
                return FetchedPayload(
                    url=response_url,
                    retrieved_at=_utc_now(),
                    status_code=status_code,
                    raw_bytes=raw,
                    sha256=_sha256_bytes(raw),
                    payload=dict(decoded),
                )
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code <= 599
                if retryable and attempt < self.max_attempts:
                    self._sleep(self._retry_delay(exc, attempt))
                    continue
                raise MassiveError(
                    f"Massive request failed with HTTP {exc.code} for {safe_url}"
                ) from None
            except urllib.error.URLError:
                if attempt < self.max_attempts:
                    self._sleep(min(60.0, float(2 ** max(0, attempt - 1))))
                    continue
                raise MassiveError(f"Massive request failed for {safe_url}") from None
        raise MassiveError(f"Massive request attempts exhausted for {safe_url}")


def connect_database(path: str | Path = DEFAULT_DATABASE) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_responses (
            request_key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            sanitized_url TEXT NOT NULL,
            retrieved_at_utc TEXT NOT NULL,
            http_status INTEGER NOT NULL,
            response_sha256 TEXT NOT NULL,
            raw_gzip BLOB NOT NULL,
            row_count INTEGER NOT NULL,
            adjusted INTEGER,
            UNIQUE(kind, sanitized_url)
        );

        CREATE TABLE IF NOT EXISTS daily_bars (
            ticker TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            vwap REAL,
            transactions INTEGER,
            source_timestamp_ms INTEGER NOT NULL,
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            PRIMARY KEY (ticker, trade_date)
        );

        CREATE TABLE IF NOT EXISTS instrument_master (
            snapshot_key TEXT NOT NULL,
            identity_key TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT,
            locale TEXT,
            primary_exchange TEXT,
            instrument_type TEXT,
            active INTEGER NOT NULL,
            currency_name TEXT,
            list_date TEXT,
            delisted_utc TEXT,
            last_updated_utc TEXT,
            cik TEXT,
            composite_figi TEXT,
            share_class_figi TEXT,
            raw_json TEXT NOT NULL,
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            PRIMARY KEY (snapshot_key, identity_key)
        );

        CREATE TABLE IF NOT EXISTS reference_asof_pages (
            snapshot_key TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            page_number INTEGER NOT NULL CHECK (page_number > 0),
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            sanitized_url TEXT NOT NULL,
            response_sha256 TEXT NOT NULL,
            next_url TEXT,
            row_count INTEGER NOT NULL CHECK (row_count >= 0),
            retrieved_at_utc TEXT NOT NULL,
            PRIMARY KEY (snapshot_key, page_number),
            UNIQUE (snapshot_key, request_key),
            UNIQUE (snapshot_key, sanitized_url),
            CHECK (
                snapshot_key = 'reference-asof:' || as_of_date ||
                    ':active=true:type=CS'
            )
        );

        CREATE UNIQUE INDEX IF NOT EXISTS
            instrument_master_reference_asof_ticker_unique
        ON instrument_master(snapshot_key, ticker)
        WHERE snapshot_key GLOB 'reference-asof:*:active=true:type=CS';

        CREATE TABLE IF NOT EXISTS stock_splits (
            snapshot_key TEXT NOT NULL,
            split_key TEXT NOT NULL,
            event_identity_key TEXT NOT NULL,
            provider_id TEXT,
            ticker TEXT NOT NULL,
            execution_date TEXT NOT NULL,
            adjustment_type TEXT NOT NULL,
            split_from REAL NOT NULL,
            split_to REAL NOT NULL,
            raw_json TEXT NOT NULL,
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            PRIMARY KEY (snapshot_key, split_key),
            UNIQUE (snapshot_key, event_identity_key),
            CHECK (split_from > 0),
            CHECK (split_to > 0),
            CHECK (adjustment_type IN (
                'forward_split', 'reverse_split', 'stock_dividend'
            ))
        );

        CREATE TABLE IF NOT EXISTS stock_split_pages (
            snapshot_key TEXT NOT NULL,
            page_number INTEGER NOT NULL CHECK (page_number > 0),
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            sanitized_url TEXT NOT NULL,
            response_sha256 TEXT NOT NULL,
            next_url TEXT,
            row_count INTEGER NOT NULL CHECK (row_count >= 0),
            retrieved_at_utc TEXT NOT NULL,
            PRIMARY KEY (snapshot_key, page_number),
            UNIQUE (snapshot_key, request_key),
            UNIQUE (snapshot_key, sanitized_url)
        );

        CREATE TABLE IF NOT EXISTS stock_dividends (
            snapshot_key TEXT NOT NULL,
            row_identity_key TEXT NOT NULL,
            provider_id TEXT,
            ticker TEXT,
            declaration_date TEXT,
            ex_dividend_date TEXT,
            cash_amount TEXT CHECK (
                cash_amount IS NULL OR typeof(cash_amount) = 'text'
            ),
            currency TEXT,
            raw_json TEXT NOT NULL,
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            PRIMARY KEY (snapshot_key, row_identity_key)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS stock_dividends_provider_id_unique
        ON stock_dividends(snapshot_key, provider_id)
        WHERE provider_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS stock_dividends_decision_lookup
        ON stock_dividends(snapshot_key, declaration_date, ticker);

        CREATE INDEX IF NOT EXISTS stock_dividends_request_page_lookup
        ON stock_dividends(snapshot_key, request_key, provider_id);

        CREATE TABLE IF NOT EXISTS stock_dividend_pages (
            snapshot_key TEXT NOT NULL,
            page_number INTEGER NOT NULL CHECK (page_number > 0),
            request_key TEXT NOT NULL REFERENCES raw_responses(request_key),
            sanitized_url TEXT NOT NULL,
            response_sha256 TEXT NOT NULL,
            next_url TEXT,
            row_count INTEGER NOT NULL CHECK (row_count >= 0),
            retrieved_at_utc TEXT NOT NULL,
            PRIMARY KEY (snapshot_key, page_number),
            UNIQUE (snapshot_key, request_key),
            UNIQUE (snapshot_key, sanitized_url)
        );

        CREATE TABLE IF NOT EXISTS fetch_checkpoint (
            checkpoint_key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            cursor TEXT,
            status TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            content_sha256 TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_manifests (
            manifest_sha256 TEXT PRIMARY KEY,
            generated_at_utc TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        """
    )
    metadata = {
        "schema_version": str(SCHEMA_VERSION),
        "source": "massive_full_market_ohlcv",
        "pit_tier": "research_pit",
        "adjusted": "false",
        "credential_persisted": "false",
        "production_warehouse": "untouched",
        "split_factor_contract": "product(split_from/split_to)",
        "historical_adjustment_factor_used": "false",
        "dividend_decision_clock": "declaration_date",
        "dividend_cash_amount_storage": "canonical_decimal_text",
        "dividend_surface_tier": "research_pit",
    }
    conn.executemany(
        "INSERT INTO source_metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        sorted(metadata.items()),
    )
    conn.commit()


def _validate_session_date(value: str) -> str:
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise MassiveError(f"Invalid ISO session date: {value!r}") from exc


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise MassiveError(f"Invalid numeric field: {field}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise MassiveError(f"Invalid numeric field: {field}") from exc
    if not math.isfinite(result):
        raise MassiveError(f"Non-finite numeric field: {field}")
    return result


def _normalise_bar(row: Mapping[str, Any], session_date: str) -> tuple[Any, ...]:
    # Massive uses case to distinguish some preferred/structured symbols
    # (for example BCPC versus BCpC). Preserve the provider identity exactly;
    # upper-casing here would create a false same-day key collision.
    ticker = str(row.get("T", "")).strip()
    if not ticker or len(ticker) > 64:
        raise MassiveError("Grouped daily row has invalid ticker")
    open_ = _finite_number(row.get("o"), "open")
    high = _finite_number(row.get("h"), "high")
    low = _finite_number(row.get("l"), "low")
    close = _finite_number(row.get("c"), "close")
    volume = _finite_number(row.get("v"), "volume")
    if min(open_, high, low, close) <= 0 or volume < 0:
        raise MassiveError("Grouped daily row violates positive-price/volume contract")
    if high < max(open_, low, close) or low > min(open_, high, close):
        raise MassiveError("Grouped daily row violates OHLC invariants")
    try:
        timestamp_ms = int(row.get("t"))
    except (TypeError, ValueError) as exc:
        raise MassiveError("Grouped daily row has invalid timestamp") from exc
    timestamp_date = dt.datetime.fromtimestamp(
        timestamp_ms / 1000.0, tz=dt.timezone.utc
    ).date().isoformat()
    if timestamp_date != session_date:
        raise MassiveError("Grouped daily timestamp does not match requested date")
    vwap = row.get("vw")
    vwap_value = None if vwap is None else _finite_number(vwap, "vwap")
    transactions = row.get("n")
    if transactions is not None:
        try:
            transactions = int(transactions)
        except (TypeError, ValueError) as exc:
            raise MassiveError("Grouped daily row has invalid transaction count") from exc
        if transactions < 0:
            raise MassiveError("Grouped daily row has negative transaction count")
    return (
        ticker,
        session_date,
        open_,
        high,
        low,
        close,
        volume,
        vwap_value,
        transactions,
        timestamp_ms,
    )


def _request_key(kind: str, url: str) -> str:
    return f"{kind}:{hashlib.sha256(url.encode('utf-8')).hexdigest()}"


def _existing_raw_hash(conn: sqlite3.Connection, request_key: str) -> str | None:
    row = conn.execute(
        "SELECT response_sha256 FROM raw_responses WHERE request_key=?",
        (request_key,),
    ).fetchone()
    return None if row is None else str(row[0])


def _insert_raw_response(
    conn: sqlite3.Connection,
    *,
    request_key: str,
    kind: str,
    fetched: FetchedPayload,
    row_count: int,
    adjusted: bool | None,
) -> None:
    existing = _existing_raw_hash(conn, request_key)
    if existing is not None:
        if existing != fetched.sha256:
            raise MassiveError("Frozen request key returned conflicting response bytes")
        return
    conn.execute(
        "INSERT INTO raw_responses("
        "request_key,kind,sanitized_url,retrieved_at_utc,http_status,"
        "response_sha256,raw_gzip,row_count,adjusted) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            request_key,
            kind,
            fetched.url,
            fetched.retrieved_at,
            fetched.status_code,
            fetched.sha256,
            sqlite3.Binary(gzip.compress(fetched.raw_bytes, mtime=0)),
            int(row_count),
            None if adjusted is None else int(adjusted),
        ),
    )


def _upsert_checkpoint(
    conn: sqlite3.Connection,
    *,
    checkpoint_key: str,
    kind: str,
    cursor: str | None,
    status: str,
    row_count: int,
    content_sha256: str,
    updated_at: str,
) -> None:
    conn.execute(
        "INSERT INTO fetch_checkpoint("
        "checkpoint_key,kind,cursor,status,row_count,content_sha256,updated_at_utc"
        ") VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(checkpoint_key) DO UPDATE SET "
        "kind=excluded.kind,cursor=excluded.cursor,status=excluded.status,"
        "row_count=excluded.row_count,content_sha256=excluded.content_sha256,"
        "updated_at_utc=excluded.updated_at_utc",
        (
            checkpoint_key,
            kind,
            cursor,
            status,
            int(row_count),
            content_sha256,
            updated_at,
        ),
    )


def ingest_grouped_day(
    conn: sqlite3.Connection,
    client: MassiveClient,
    session_date: str,
    *,
    failpoint: Callable[..., None] | None = None,
) -> dict[str, Any]:
    session_date = _validate_session_date(session_date)
    url = (
        f"{API_ORIGIN}/v2/aggs/grouped/locale/us/market/stocks/{session_date}"
        "?adjusted=false"
    )
    fetched = client.get_json(url)
    payload = fetched.payload
    if payload.get("status") not in {"OK", "DELAYED"}:
        raise MassiveError("Grouped daily response status was not usable")
    if payload.get("adjusted") is not False:
        raise MassiveError("Grouped daily response was not explicitly unadjusted")
    raw_rows = payload.get("results") or []
    if not isinstance(raw_rows, list):
        raise MassiveError("Grouped daily results must be a list")
    normalised: dict[str, tuple[Any, ...]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise MassiveError("Grouped daily result must be an object")
        row = _normalise_bar(raw_row, session_date)
        ticker = str(row[0])
        if ticker in normalised and normalised[ticker] != row:
            raise MassiveError("Duplicate grouped daily ticker has conflicting values")
        if ticker in normalised:
            raise MassiveError("Duplicate grouped daily ticker")
        normalised[ticker] = row
    request_key = f"grouped:{session_date}:adjusted=false"
    with conn:
        existing_hash = _existing_raw_hash(conn, request_key)
        if existing_hash is not None and existing_hash != fetched.sha256:
            raise MassiveError("Frozen grouped day returned conflicting response bytes")
        _insert_raw_response(
            conn,
            request_key=request_key,
            kind="grouped_daily",
            fetched=fetched,
            row_count=len(normalised),
            adjusted=False,
        )
        if failpoint is not None:
            failpoint(stage="after_raw_insert", request_key=request_key)
        for row in normalised.values():
            existing = conn.execute(
                "SELECT open,high,low,close,volume,vwap,transactions,source_timestamp_ms "
                "FROM daily_bars WHERE ticker=? AND trade_date=?",
                (row[0], row[1]),
            ).fetchone()
            values = row[2:]
            if existing is not None:
                if tuple(existing) != tuple(values):
                    raise MassiveError("Existing daily bar conflicts with fetched values")
                continue
            conn.execute(
                "INSERT INTO daily_bars("
                "ticker,trade_date,open,high,low,close,volume,vwap,transactions,"
                "source_timestamp_ms,request_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (*row, request_key),
            )
        _upsert_checkpoint(
            conn,
            checkpoint_key=f"grouped:{session_date}",
            kind="grouped_daily",
            cursor=None,
            status="complete",
            row_count=len(normalised),
            content_sha256=fetched.sha256,
            updated_at=fetched.retrieved_at,
        )
    return {
        "date": session_date,
        "adjusted": False,
        "row_count": len(normalised),
        "response_sha256": fetched.sha256,
        "retrieved_at": fetched.retrieved_at,
    }


def _normalise_reference_row(
    row: Mapping[str, Any], *, active: bool
) -> tuple[Any, ...]:
    ticker = str(row.get("ticker", "")).strip()
    if not ticker or len(ticker) > 64:
        raise MassiveError("Reference row has invalid ticker")
    row_active = row.get("active", active)
    if not isinstance(row_active, bool):
        raise MassiveError("Reference row active status must be boolean")
    if row_active is not active:
        raise MassiveError("Reference row active status conflicts with request")
    raw_json = _canonical_json_bytes(dict(row)).decode("utf-8")
    share_class_figi = None if row.get("share_class_figi") is None else str(row.get("share_class_figi"))
    composite_figi = None if row.get("composite_figi") is None else str(row.get("composite_figi"))
    cik = None if row.get("cik") is None else str(row.get("cik"))
    provider_identity = share_class_figi or composite_figi or (f"cik:{cik}" if cik else "")
    # One FIGI can span multiple symbol/listing lifecycles.  The staging key
    # therefore binds provider identity to the exact ticker and effective
    # listing boundary instead of collapsing historical symbol changes.
    identity_material = "|".join(
        (
            provider_identity,
            ticker,
            str(row.get("primary_exchange") or ""),
            str(row.get("list_date") or ""),
            str(row.get("delisted_utc") or ""),
        )
    )
    identity_key = f"listing:{hashlib.sha256(identity_material.encode('utf-8')).hexdigest()}"
    return (
        identity_key,
        ticker,
        None if row.get("name") is None else str(row.get("name")),
        None if row.get("market") is None else str(row.get("market")),
        None if row.get("locale") is None else str(row.get("locale")),
        None
        if row.get("primary_exchange") is None
        else str(row.get("primary_exchange")),
        None if row.get("type") is None else str(row.get("type")),
        int(bool(active)),
        None if row.get("currency_name") is None else str(row.get("currency_name")),
        None if row.get("list_date") is None else str(row.get("list_date")),
        None if row.get("delisted_utc") is None else str(row.get("delisted_utc")),
        None
        if row.get("last_updated_utc") is None
        else str(row.get("last_updated_utc")),
        cik,
        composite_figi,
        share_class_figi,
        raw_json,
    )


def _merge_reference_duplicate(
    first: tuple[Any, ...], second: tuple[Any, ...]
) -> tuple[Any, ...]:
    """Collapse vendor duplicate rows only when stable identity is identical.

    Massive can emit the same inactive identity twice with different
    ``last_updated_utc`` values.  True ticker reuse remains distinct because
    the key is FIGI/fallback identity, not ticker.
    """

    if first[0] != second[0]:
        raise MassiveError("Reference duplicate identity keys do not match")
    # Layout: identity,ticker,name,market,locale,exchange,type,active,currency,
    # list_date,delisted,last_updated,cik,composite,share,raw_json.
    stable_positions = tuple(index for index in range(len(first)) if index not in {11, 15})
    if tuple(first[index] for index in stable_positions) != tuple(
        second[index] for index in stable_positions
    ):
        field_names = (
            "identity_key",
            "ticker",
            "name",
            "market",
            "locale",
            "primary_exchange",
            "instrument_type",
            "active",
            "currency_name",
            "list_date",
            "delisted_utc",
            "last_updated_utc",
            "cik",
            "composite_figi",
            "share_class_figi",
            "raw_json",
        )
        differing = [
            field_names[index]
            for index in stable_positions
            if first[index] != second[index]
        ]
        raise MassiveError(
            f"Reference identity {first[1]!r} conflicts in fields: {','.join(differing)}"
        )
    return max((first, second), key=lambda value: str(value[11] or ""))


def _parse_reference_last_updated(value: Any) -> dt.datetime | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MassiveError("Reference vendor revision has invalid last_updated_utc") from exc
    if parsed.tzinfo is None:
        raise MassiveError(
            "Reference vendor revision last_updated_utc lacks timezone"
        )
    return parsed.astimezone(dt.timezone.utc)


def _reference_decision_cutoff_utc(as_of: str) -> dt.datetime:
    as_of_date = dt.date.fromisoformat(_validate_session_date(as_of))
    decision_close = dt.datetime.combine(
        as_of_date,
        dt.time(hour=16),
        tzinfo=ZoneInfo("America/New_York"),
    )
    return decision_close.astimezone(dt.timezone.utc)


def _utc_iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _collapse_reference_asof_vendor_revisions(
    revisions: list[tuple[Mapping[str, Any], tuple[Any, ...]]],
    *,
    as_of: str,
) -> tuple[Any, ...]:
    """Collapse only revisions proven to describe one stable FIGI listing.

    Descriptive vendor fields may be revised after the requested snapshot.
    They are retained for provenance, but the readiness contract explicitly
    excludes them from candidate decisions.  Identity disagreements remain a
    hard error rather than being resolved by recency.
    """

    if len(revisions) < 2:
        raise MassiveError("Reference vendor revision collapse requires duplicates")
    cutoff_utc = _reference_decision_cutoff_utc(as_of)
    timestamped: list[
        tuple[dt.datetime, bytes, tuple[Any, ...]]
    ] = []
    for raw_row, normalized_row in revisions:
        updated_at = _parse_reference_last_updated(normalized_row[11])
        if updated_at is None:
            raise MassiveError(
                "Reference duplicate revision lacks decision-time last_updated_utc"
            )
        timestamped.append(
            (updated_at, _canonical_json_bytes(dict(raw_row)), normalized_row)
        )
    eligible = [candidate for candidate in timestamped if candidate[0] <= cutoff_utc]
    if not eligible:
        raise MassiveError(
            "Reference duplicate revisions have no row eligible by decision cutoff"
        )

    # Future revisions are provenance-only.  They are intentionally excluded
    # before identity comparisons so current/future descriptive changes cannot
    # invalidate or alter a historical ticker that has an eligible revision.
    normalized = [candidate[2] for candidate in eligible]
    ticker = str(normalized[0][1])
    if any(str(row[1]) != ticker for row in normalized[1:]):
        raise MassiveError("Reference vendor revisions do not share a ticker")

    # These fields define the same listing boundary and trading surface.  A
    # missing-vs-present difference is material here and therefore conflicts.
    stable_positions = (1, 3, 4, 5, 6, 7, 8, 9, 10)
    for position in stable_positions:
        if any(row[position] != normalized[0][position] for row in normalized[1:]):
            raise MassiveError(
                f"Reference as-of ticker {ticker!r} has conflicting listing identity"
            )

    # FIGI fields may be filled in by another eligible vendor revision, but two
    # non-empty values may never be silently reconciled.  CIK/name/update time
    # are descriptive rather than decision identity and may legitimately vary.
    for position, label in (
        (13, "composite_figi"),
        (14, "share_class_figi"),
    ):
        nonempty = {str(row[position]).strip() for row in normalized if row[position]}
        if len(nonempty) > 1:
            raise MassiveError(
                f"Reference as-of ticker {ticker!r} has conflicting {label}"
            )
    if any(not (row[13] or row[14]) for row in normalized):
        raise MassiveError(
            f"Reference as-of ticker {ticker!r} lacks stable FIGI revision identity"
        )
    figi_tokens = [
        {
            (label, str(row[position]).strip())
            for position, label in (
                (13, "composite_figi"),
                (14, "share_class_figi"),
            )
            if row[position]
        }
        for row in normalized
    ]
    if not set.intersection(*figi_tokens):
        raise MassiveError(
            f"Reference as-of ticker {ticker!r} has no common stable FIGI"
        )
    selected = max(eligible, key=lambda candidate: (candidate[0], candidate[1]))
    return selected[2]


def _normalise_reference_asof_page(
    raw_rows: list[Any],
    *,
    as_of: str,
) -> tuple[dict[str, tuple[Any, ...]], dict[str, int]]:
    """Normalize one raw page and cautiously collapse vendor revisions."""

    cutoff_utc = _reference_decision_cutoff_utc(as_of)
    grouped: dict[str, list[tuple[Mapping[str, Any], tuple[Any, ...]]]] = {}
    revision_timestamps: dict[int, dt.datetime | None] = {}
    eligible_revision_count = 0
    future_revision_count = 0
    undated_revision_count = 0
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise MassiveError("Reference as-of result must be an object")
        if raw_row.get("type") != "CS":
            raise MassiveError("Reference as-of row type conflicts with type=CS")
        normalized = _normalise_reference_row(raw_row, active=True)
        updated_at = _parse_reference_last_updated(normalized[11])
        revision_timestamps[id(raw_row)] = updated_at
        if updated_at is None:
            undated_revision_count += 1
        elif updated_at <= cutoff_utc:
            eligible_revision_count += 1
        else:
            future_revision_count += 1
        grouped.setdefault(str(normalized[1]), []).append((raw_row, normalized))

    rows: dict[str, tuple[Any, ...]] = {}
    revision_group_count = 0
    selected_eligible_row_count = 0
    selected_future_or_undated_single_row_count = 0
    for ticker, revisions in grouped.items():
        if len(revisions) == 1:
            rows[ticker] = revisions[0][1]
            selected_timestamp = revision_timestamps[id(revisions[0][0])]
            if selected_timestamp is not None and selected_timestamp <= cutoff_utc:
                selected_eligible_row_count += 1
            else:
                selected_future_or_undated_single_row_count += 1
            continue
        revision_group_count += 1
        rows[ticker] = _collapse_reference_asof_vendor_revisions(
            revisions, as_of=as_of
        )
        selected_eligible_row_count += 1
    return rows, {
        "raw_result_count": len(raw_rows),
        "eligible_revision_count": eligible_revision_count,
        "future_revision_count": future_revision_count,
        "undated_revision_count": undated_revision_count,
        "selected_unique_row_count": len(rows),
        "selected_eligible_row_count": selected_eligible_row_count,
        "selected_future_or_undated_single_row_count": (
            selected_future_or_undated_single_row_count
        ),
        "normalized_unique_row_count": len(rows),
        "vendor_revision_collapse_count": len(raw_rows) - len(rows),
        "vendor_revision_group_count": revision_group_count,
        "vendor_revision_future_only_group_count": 0,
    }


def sync_reference(
    conn: sqlite3.Connection,
    client: MassiveClient,
    *,
    active: bool,
) -> dict[str, Any]:
    active_text = "true" if active else "false"
    initial_url = (
        f"{API_ORIGIN}/v3/reference/tickers?market=stocks&active={active_text}"
        "&limit=1000&sort=ticker&order=asc"
    )
    snapshot_key = f"reference:{active_text}"
    checkpoint = conn.execute(
        "SELECT cursor,status,row_count FROM fetch_checkpoint WHERE checkpoint_key=?",
        (f"reference:{active_text}",),
    ).fetchone()
    if checkpoint and checkpoint[1] == "complete":
        pages = int(
            conn.execute(
                "SELECT COUNT(*) FROM raw_responses WHERE kind=?",
                (f"reference_{active_text}",),
            ).fetchone()[0]
        )
        return {
            "active": active,
            "row_count": int(checkpoint[2]),
            "pages": pages,
            "status": "complete",
            "resumed_without_network": True,
        }
    url = str(checkpoint[0]) if checkpoint and checkpoint[0] else initial_url
    total_rows = int(checkpoint[2]) if checkpoint else 0
    pages = int(
        conn.execute(
            "SELECT COUNT(*) FROM raw_responses WHERE kind=?",
            (f"reference_{active_text}",),
        ).fetchone()[0]
    )
    seen_urls: set[str] = set()
    while url:
        safe_url = _sanitize_api_url(url)
        if safe_url in seen_urls:
            raise MassiveError("Reference pagination cursor repeated")
        seen_urls.add(safe_url)
        fetched = client.get_json(safe_url)
        payload = fetched.payload
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Reference response status was not usable")
        raw_rows = payload.get("results") or []
        if not isinstance(raw_rows, list):
            raise MassiveError("Reference results must be a list")
        rows: dict[str, tuple[Any, ...]] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                raise MassiveError("Reference result must be an object")
            row = _normalise_reference_row(raw_row, active=active)
            identity_key = str(row[0])
            if identity_key in rows:
                rows[identity_key] = _merge_reference_duplicate(rows[identity_key], row)
            else:
                rows[identity_key] = row
        next_url_value = payload.get("next_url")
        next_url = None if not next_url_value else _sanitize_api_url(str(next_url_value))
        request_key = _request_key(f"reference:{active_text}", safe_url)
        status = "complete" if next_url is None else "in_progress"
        with conn:
            _insert_raw_response(
                conn,
                request_key=request_key,
                kind=f"reference_{active_text}",
                fetched=fetched,
                row_count=len(rows),
                adjusted=None,
            )
            for row in rows.values():
                existing = conn.execute(
                    "SELECT ticker,name,market,locale,primary_exchange,instrument_type,active,"
                    "currency_name,list_date,delisted_utc,last_updated_utc,cik,"
                    "composite_figi,share_class_figi,raw_json "
                    "FROM instrument_master WHERE snapshot_key=? AND identity_key=?",
                    (snapshot_key, row[0]),
                ).fetchone()
                if existing is not None:
                    if tuple(existing) != tuple(row[1:]):
                        raise MassiveError("Frozen reference ticker conflicts with prior values")
                    continue
                conn.execute(
                    "INSERT INTO instrument_master("
                    "snapshot_key,identity_key,ticker,name,market,locale,primary_exchange,"
                    "instrument_type,active,currency_name,list_date,delisted_utc,"
                    "last_updated_utc,cik,composite_figi,share_class_figi,raw_json,"
                    "request_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (snapshot_key, *row, request_key),
                )
            _upsert_checkpoint(
                conn,
                checkpoint_key=f"reference:{active_text}",
                kind="reference",
                cursor=next_url,
                status=status,
                row_count=total_rows + len(rows),
                content_sha256=fetched.sha256,
                updated_at=fetched.retrieved_at,
            )
        total_rows += len(rows)
        pages += 1
        url = next_url or ""
    return {
        "active": active,
        "row_count": total_rows,
        "pages": pages,
        "status": "complete",
    }


def reference_asof_snapshot_key(as_of: str) -> str:
    """Return the complete policy-bound key for one dated identity snapshot."""

    as_of_date = _validate_session_date(as_of)
    return f"reference-asof:{as_of_date}:active=true:type=CS"


def _reference_asof_initial_url(as_of: str) -> str:
    as_of_date = _validate_session_date(as_of)
    return (
        f"{API_ORIGIN}/v3/reference/tickers?date={as_of_date}"
        "&active=true&type=CS&limit=1000&sort=ticker&order=asc"
    )


def _sanitize_reference_asof_url(
    url: str,
    *,
    as_of: str,
    require_explicit_contract: bool,
) -> str:
    """Validate a dated reference URL without rejecting opaque cursors.

    Massive continuation URLs may contain only an opaque cursor.  The initial
    request must explicitly bind ``date``, ``active=true``, and ``type=CS``;
    continuation pages may omit those fields, but may never override one.
    """

    as_of_date = _validate_session_date(as_of)
    safe_url = _sanitize_api_url(url)
    parsed = urllib.parse.urlsplit(safe_url)
    if parsed.path.rstrip("/") != "/v3/reference/tickers":
        raise MassiveError("Refusing unexpected Massive reference endpoint path")
    values: dict[str, list[str]] = {}
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in {"date", "active", "type"} and key not in {
            "date",
            "active",
            "type",
        }:
            raise MassiveError(
                f"Reference pagination used non-canonical query field: {key}"
            )
        values.setdefault(key, []).append(value)
    expected = {
        "date": as_of_date,
        "active": "true",
        "type": "CS",
    }
    for key, expected_value in expected.items():
        observed = values.get(key, [])
        if len(observed) > 1:
            raise MassiveError(f"Reference pagination repeats query field: {key}")
        if require_explicit_contract and not observed:
            raise MassiveError(f"Reference initial URL is missing query field: {key}")
        if observed and observed[0] != expected_value:
            raise MassiveError(f"Reference pagination changed query field: {key}")
    return safe_url


def _reference_asof_pages_digest(pages: Iterable[tuple[Any, ...]]) -> str:
    digest = hashlib.sha256()
    for page in pages:
        digest.update(_canonical_json_bytes(list(page)))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_reference_asof_snapshot_state(
    conn: sqlite3.Connection,
    *,
    as_of: str,
) -> dict[str, Any]:
    """Verify a dated identity snapshot from page chain through normalized rows."""

    as_of_date = _validate_session_date(as_of)
    snapshot_key = reference_asof_snapshot_key(as_of_date)
    checkpoint = conn.execute(
        "SELECT kind,cursor,status,row_count,content_sha256,updated_at_utc "
        "FROM fetch_checkpoint WHERE checkpoint_key=?",
        (snapshot_key,),
    ).fetchone()
    pages = conn.execute(
        "SELECT as_of_date,page_number,request_key,sanitized_url,response_sha256,"
        "next_url,row_count,retrieved_at_utc FROM reference_asof_pages "
        "WHERE snapshot_key=? ORDER BY page_number",
        (snapshot_key,),
    ).fetchall()
    if checkpoint is None:
        if pages:
            raise MassiveError("Reference as-of pages exist without a checkpoint")
        return {
            "snapshot_key": snapshot_key,
            "as_of": as_of_date,
            "status": "missing",
            "cursor": None,
            "row_count": 0,
            "pages": 0,
            "all_pages_sha256": _reference_asof_pages_digest(()),
            "page_records": [],
            "page_urls": [],
            "raw_result_count": 0,
            "eligible_revision_count": 0,
            "future_revision_count": 0,
            "undated_revision_count": 0,
            "selected_unique_row_count": 0,
            "selected_eligible_row_count": 0,
            "selected_future_or_undated_single_row_count": 0,
            "vendor_revision_collapse_count": 0,
            "vendor_revision_group_count": 0,
            "vendor_revision_future_only_group_count": 0,
        }
    if not pages:
        raise MassiveError("Reference as-of checkpoint exists without page records")

    expected_url = _sanitize_reference_asof_url(
        _reference_asof_initial_url(as_of_date),
        as_of=as_of_date,
        require_explicit_contract=True,
    )
    digest_records: list[tuple[Any, ...]] = []
    raw_result_count = 0
    eligible_revision_count = 0
    future_revision_count = 0
    undated_revision_count = 0
    selected_unique_row_count = 0
    selected_eligible_row_count = 0
    selected_future_or_undated_single_row_count = 0
    vendor_revision_collapse_count = 0
    vendor_revision_group_count = 0
    vendor_revision_future_only_group_count = 0
    for expected_number, page in enumerate(pages, start=1):
        (
            stored_as_of,
            page_number,
            request_key,
            sanitized_url,
            response_sha256,
            next_url,
            page_row_count,
            _retrieved_at,
        ) = page
        if str(stored_as_of) != as_of_date:
            raise MassiveError("Reference page as_of does not match its snapshot")
        if int(page_number) != expected_number:
            raise MassiveError("Reference as-of page sequence is not contiguous")
        safe_page_url = _sanitize_reference_asof_url(
            str(sanitized_url),
            as_of=as_of_date,
            require_explicit_contract=expected_number == 1,
        )
        if safe_page_url != expected_url:
            raise MassiveError("Reference as-of page cursor chain is inconsistent")
        expected_request_key = _request_key(snapshot_key, safe_page_url)
        if str(request_key) != expected_request_key:
            raise MassiveError("Reference as-of request key is not snapshot-bound")
        raw_row = conn.execute(
            "SELECT kind,sanitized_url,response_sha256,raw_gzip,row_count "
            "FROM raw_responses WHERE request_key=?",
            (request_key,),
        ).fetchone()
        if raw_row is None:
            raise MassiveError("Reference as-of page is missing its frozen raw response")
        raw_kind, raw_url, raw_hash, raw_gzip, raw_row_count = raw_row
        if str(raw_kind) != snapshot_key or str(raw_url) != safe_page_url:
            raise MassiveError("Reference as-of raw response identity is inconsistent")
        if str(raw_hash) != str(response_sha256) or int(raw_row_count) != int(
            page_row_count
        ):
            raise MassiveError("Reference as-of page metadata conflicts with raw response")
        try:
            raw = gzip.decompress(bytes(raw_gzip))
        except (OSError, EOFError) as exc:
            raise MassiveError("Reference as-of raw response is not valid gzip") from exc
        if _sha256_bytes(raw) != str(response_sha256):
            raise MassiveError("Reference as-of raw response hash verification failed")
        try:
            raw_payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MassiveError(
                "Reference as-of frozen raw response is not valid JSON"
            ) from exc
        if not isinstance(raw_payload, Mapping):
            raise MassiveError("Reference as-of frozen raw root is not an object")
        if raw_payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Reference as-of frozen raw status is not usable")
        raw_results = raw_payload.get("results")
        if not isinstance(raw_results, list):
            raise MassiveError("Reference as-of frozen raw results are not a list")
        normalized_raw_rows, page_stats = _normalise_reference_asof_page(
            raw_results, as_of=as_of_date
        )
        if len(normalized_raw_rows) != int(page_row_count):
            raise MassiveError("Reference as-of normalized raw row count is inconsistent")
        raw_result_count += int(page_stats["raw_result_count"])
        eligible_revision_count += int(page_stats["eligible_revision_count"])
        future_revision_count += int(page_stats["future_revision_count"])
        undated_revision_count += int(page_stats["undated_revision_count"])
        selected_unique_row_count += int(page_stats["selected_unique_row_count"])
        selected_eligible_row_count += int(
            page_stats["selected_eligible_row_count"]
        )
        selected_future_or_undated_single_row_count += int(
            page_stats["selected_future_or_undated_single_row_count"]
        )
        vendor_revision_collapse_count += int(
            page_stats["vendor_revision_collapse_count"]
        )
        vendor_revision_group_count += int(
            page_stats["vendor_revision_group_count"]
        )
        vendor_revision_future_only_group_count += int(
            page_stats["vendor_revision_future_only_group_count"]
        )
        stored_identity_rows = conn.execute(
            "SELECT identity_key,ticker,name,market,locale,primary_exchange,"
            "instrument_type,active,currency_name,list_date,delisted_utc,"
            "last_updated_utc,cik,composite_figi,share_class_figi,raw_json "
            "FROM instrument_master WHERE snapshot_key=? AND request_key=? "
            "ORDER BY ticker",
            (snapshot_key, request_key),
        ).fetchall()
        expected_identity_rows = sorted(normalized_raw_rows.values(), key=lambda row: row[1])
        if [tuple(row) for row in stored_identity_rows] != expected_identity_rows:
            raise MassiveError(
                "Reference as-of normalized rows are not bound to frozen raw page"
            )
        payload_next_value = raw_payload.get("next_url")
        payload_next = (
            None
            if not payload_next_value
            else _sanitize_reference_asof_url(
                str(payload_next_value),
                as_of=as_of_date,
                require_explicit_contract=False,
            )
        )
        safe_next = (
            None
            if next_url is None
            else _sanitize_reference_asof_url(
                str(next_url),
                as_of=as_of_date,
                require_explicit_contract=False,
            )
        )
        if safe_next != payload_next:
            raise MassiveError("Reference as-of page cursor is not bound to raw payload")
        digest_records.append(
            (
                int(page_number),
                str(request_key),
                str(response_sha256),
                safe_next,
                int(page_row_count),
            )
        )
        expected_url = safe_next or ""

    checkpoint_kind, cursor, status, checkpoint_rows, checkpoint_digest, updated_at = (
        checkpoint
    )
    if str(checkpoint_kind) != snapshot_key:
        raise MassiveError("Reference as-of checkpoint kind is not snapshot-bound")
    safe_cursor = (
        None
        if cursor is None
        else _sanitize_reference_asof_url(
            str(cursor),
            as_of=as_of_date,
            require_explicit_contract=False,
        )
    )
    last_next = digest_records[-1][3]
    if safe_cursor != last_next:
        raise MassiveError("Reference as-of checkpoint cursor does not match page chain")
    if status == "complete" and safe_cursor is not None:
        raise MassiveError("Complete reference as-of checkpoint still has a cursor")
    if status == "in_progress" and safe_cursor is None:
        raise MassiveError("In-progress reference as-of checkpoint has no cursor")
    if status not in {"complete", "in_progress"}:
        raise MassiveError("Reference as-of checkpoint has unsupported status")

    row_stats = conn.execute(
        "SELECT COUNT(*),COUNT(DISTINCT ticker),"
        "SUM(CASE WHEN active!=1 THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN instrument_type!='CS' OR instrument_type IS NULL THEN 1 ELSE 0 END) "
        "FROM instrument_master WHERE snapshot_key=?",
        (snapshot_key,),
    ).fetchone()
    identity_rows = int(row_stats[0] or 0)
    distinct_tickers = int(row_stats[1] or 0)
    if identity_rows != distinct_tickers:
        raise MassiveError("Reference as-of snapshot has duplicate ticker identities")
    if int(row_stats[2] or 0) or int(row_stats[3] or 0):
        raise MassiveError("Reference as-of snapshot contains rows outside active CS")
    summed_rows = sum(int(page[6]) for page in pages)
    if identity_rows != summed_rows or identity_rows != int(checkpoint_rows):
        raise MassiveError("Reference as-of checkpoint row count is inconsistent")
    if identity_rows != selected_unique_row_count:
        raise MassiveError("Reference as-of selected-row accounting is inconsistent")
    if raw_result_count != (
        eligible_revision_count + future_revision_count + undated_revision_count
    ):
        raise MassiveError("Reference as-of revision-time accounting is inconsistent")
    all_pages_sha256 = _reference_asof_pages_digest(digest_records)
    if str(checkpoint_digest) != all_pages_sha256:
        raise MassiveError("Reference as-of all-page digest is inconsistent")
    return {
        "snapshot_key": snapshot_key,
        "as_of": as_of_date,
        "status": str(status),
        "cursor": safe_cursor,
        "row_count": identity_rows,
        "pages": len(pages),
        "all_pages_sha256": all_pages_sha256,
        "updated_at": str(updated_at),
        "page_records": digest_records,
        "page_urls": [str(page[3]) for page in pages],
        "raw_result_count": raw_result_count,
        "eligible_revision_count": eligible_revision_count,
        "future_revision_count": future_revision_count,
        "undated_revision_count": undated_revision_count,
        "selected_unique_row_count": selected_unique_row_count,
        "selected_eligible_row_count": selected_eligible_row_count,
        "selected_future_or_undated_single_row_count": (
            selected_future_or_undated_single_row_count
        ),
        "vendor_revision_collapse_count": vendor_revision_collapse_count,
        "vendor_revision_group_count": vendor_revision_group_count,
        "vendor_revision_future_only_group_count": (
            vendor_revision_future_only_group_count
        ),
    }


def sync_reference_asof(
    conn: sqlite3.Connection,
    client: MassiveClient,
    as_of: str,
    *,
    max_pages: int = DEFAULT_MAX_REFERENCE_PAGES,
    failpoint: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Freeze the official active common-stock identity set for one date."""

    as_of_date = _validate_session_date(as_of)
    snapshot_key = reference_asof_snapshot_key(as_of_date)
    page_limit = int(max_pages)
    if page_limit < 1:
        raise MassiveError("Reference as-of max_pages must be positive")
    state = _verify_reference_asof_snapshot_state(conn, as_of=as_of_date)
    if state["status"] == "complete":
        return {
            "snapshot_key": snapshot_key,
            "as_of": as_of_date,
            "active": True,
            "type": "CS",
            "row_count": int(state["row_count"]),
            "pages": int(state["pages"]),
            "all_pages_sha256": state["all_pages_sha256"],
            "raw_result_count": int(state["raw_result_count"]),
            "eligible_revision_count": int(state["eligible_revision_count"]),
            "future_revision_count": int(state["future_revision_count"]),
            "undated_revision_count": int(state["undated_revision_count"]),
            "selected_unique_row_count": int(state["selected_unique_row_count"]),
            "vendor_revision_collapse_count": int(
                state["vendor_revision_collapse_count"]
            ),
            "vendor_revision_group_count": int(
                state["vendor_revision_group_count"]
            ),
            "vendor_revision_future_only_group_count": int(
                state["vendor_revision_future_only_group_count"]
            ),
            "status": "complete",
            "resumed_without_network": True,
        }
    if int(state["pages"]) >= page_limit:
        raise MassiveError("Reference as-of pagination exceeded configured page bound")

    url = str(state["cursor"] or _reference_asof_initial_url(as_of_date))
    total_rows = int(state["row_count"])
    page_number = int(state["pages"]) + 1
    digest_records = list(state["page_records"])
    seen_urls = set(state.get("page_urls", []))
    while url:
        if page_number > page_limit:
            raise MassiveError("Reference as-of pagination exceeded configured page bound")
        safe_url = _sanitize_reference_asof_url(
            url,
            as_of=as_of_date,
            require_explicit_contract=page_number == 1,
        )
        if safe_url in seen_urls:
            raise MassiveError("Reference as-of pagination cursor repeated")
        seen_urls.add(safe_url)
        fetched = client.get_json(safe_url)
        response_url = _sanitize_reference_asof_url(
            fetched.url,
            as_of=as_of_date,
            require_explicit_contract=page_number == 1,
        )
        if response_url != safe_url:
            raise MassiveError("Reference as-of response URL changed the request identity")
        payload = fetched.payload
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Reference as-of response status was not usable")
        raw_rows = payload.get("results")
        if not isinstance(raw_rows, list):
            raise MassiveError("Reference as-of results must be a list")

        rows, _page_stats = _normalise_reference_asof_page(
            raw_rows, as_of=as_of_date
        )

        next_url_value = payload.get("next_url")
        next_url = (
            None
            if not next_url_value
            else _sanitize_reference_asof_url(
                str(next_url_value),
                as_of=as_of_date,
                require_explicit_contract=False,
            )
        )
        if next_url is not None and next_url in seen_urls:
            raise MassiveError("Reference as-of pagination cursor repeated")
        request_key = _request_key(snapshot_key, safe_url)
        status = "complete" if next_url is None else "in_progress"
        digest_record = (
            page_number,
            request_key,
            fetched.sha256,
            next_url,
            len(rows),
        )
        all_pages_sha256 = _reference_asof_pages_digest(
            [*digest_records, digest_record]
        )

        with conn:
            _insert_raw_response(
                conn,
                request_key=request_key,
                kind=snapshot_key,
                fetched=fetched,
                row_count=len(rows),
                adjusted=None,
            )
            if failpoint is not None:
                failpoint(
                    stage="after_reference_asof_raw_insert",
                    snapshot_key=snapshot_key,
                    page_number=page_number,
                )
            for row in rows.values():
                existing = conn.execute(
                    "SELECT identity_key FROM instrument_master "
                    "WHERE snapshot_key=? AND ticker=?",
                    (snapshot_key, row[1]),
                ).fetchone()
                if existing is not None:
                    raise MassiveError(
                        "Reference as-of pagination repeated or conflicted on ticker"
                    )
                conn.execute(
                    "INSERT INTO instrument_master("
                    "snapshot_key,identity_key,ticker,name,market,locale,primary_exchange,"
                    "instrument_type,active,currency_name,list_date,delisted_utc,"
                    "last_updated_utc,cik,composite_figi,share_class_figi,raw_json,"
                    "request_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (snapshot_key, *row, request_key),
                )
            conn.execute(
                "INSERT INTO reference_asof_pages("
                "snapshot_key,as_of_date,page_number,request_key,sanitized_url,"
                "response_sha256,next_url,row_count,retrieved_at_utc) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    snapshot_key,
                    as_of_date,
                    page_number,
                    request_key,
                    fetched.url,
                    fetched.sha256,
                    next_url,
                    len(rows),
                    fetched.retrieved_at,
                ),
            )
            _upsert_checkpoint(
                conn,
                checkpoint_key=snapshot_key,
                kind=snapshot_key,
                cursor=next_url,
                status=status,
                row_count=total_rows + len(rows),
                content_sha256=all_pages_sha256,
                updated_at=fetched.retrieved_at,
            )

        digest_records.append(digest_record)
        total_rows += len(rows)
        page_number += 1
        url = next_url or ""

    verified = _verify_reference_asof_snapshot_state(conn, as_of=as_of_date)
    if verified["status"] != "complete":
        raise MassiveError("Reference as-of sync ended without complete checkpoint")
    return {
        "snapshot_key": snapshot_key,
        "as_of": as_of_date,
        "active": True,
        "type": "CS",
        "row_count": int(verified["row_count"]),
        "pages": int(verified["pages"]),
        "all_pages_sha256": verified["all_pages_sha256"],
        "raw_result_count": int(verified["raw_result_count"]),
        "eligible_revision_count": int(verified["eligible_revision_count"]),
        "future_revision_count": int(verified["future_revision_count"]),
        "undated_revision_count": int(verified["undated_revision_count"]),
        "selected_unique_row_count": int(verified["selected_unique_row_count"]),
        "vendor_revision_collapse_count": int(
            verified["vendor_revision_collapse_count"]
        ),
        "vendor_revision_group_count": int(
            verified["vendor_revision_group_count"]
        ),
        "vendor_revision_future_only_group_count": int(
            verified["vendor_revision_future_only_group_count"]
        ),
        "status": "complete",
        "resumed_without_network": False,
    }


def _normalise_reference_asof_dates(values: Iterable[str]) -> list[str]:
    dates: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _validate_session_date(str(value).strip())
        if normalized in seen:
            raise MassiveError(f"Duplicate reference as-of date: {normalized}")
        seen.add(normalized)
        dates.append(normalized)
    if not dates:
        raise MassiveError("At least one reference as-of date is required")
    return dates


def sync_reference_asof_dates(
    conn: sqlite3.Connection,
    client: MassiveClient,
    dates: Iterable[str],
    *,
    max_pages: int = DEFAULT_MAX_REFERENCE_PAGES,
) -> dict[str, Any]:
    """Synchronize a fixed, caller-declared set of as-of dates in order."""

    expected_dates = _normalise_reference_asof_dates(dates)
    snapshots = [
        sync_reference_asof(conn, client, value, max_pages=max_pages)
        for value in expected_dates
    ]
    return {
        "status": "complete",
        "expected_dates": expected_dates,
        "complete_dates": [str(part["as_of"]) for part in snapshots],
        "date_count": len(snapshots),
        "row_count": sum(int(part["row_count"]) for part in snapshots),
        "raw_result_count": sum(
            int(part["raw_result_count"]) for part in snapshots
        ),
        "eligible_revision_count": sum(
            int(part["eligible_revision_count"]) for part in snapshots
        ),
        "future_revision_count": sum(
            int(part["future_revision_count"]) for part in snapshots
        ),
        "undated_revision_count": sum(
            int(part["undated_revision_count"]) for part in snapshots
        ),
        "selected_unique_row_count": sum(
            int(part["selected_unique_row_count"]) for part in snapshots
        ),
        "vendor_revision_collapse_count": sum(
            int(part["vendor_revision_collapse_count"]) for part in snapshots
        ),
        "vendor_revision_group_count": sum(
            int(part["vendor_revision_group_count"]) for part in snapshots
        ),
        "vendor_revision_future_only_group_count": sum(
            int(part["vendor_revision_future_only_group_count"])
            for part in snapshots
        ),
        "pages": sum(int(part["pages"]) for part in snapshots),
        "snapshots": snapshots,
    }


def split_snapshot_key(start: str, end: str) -> str:
    """Return the explicit, range-bound identity for one split snapshot."""

    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    if start_date > end_date:
        raise MassiveError("Split snapshot start must not be after end")
    return f"stock_splits:{start_date}:{end_date}"


def _split_initial_url(start: str, end: str) -> str:
    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    return (
        f"{API_ORIGIN}/stocks/v1/splits?execution_date.gte={start_date}"
        f"&execution_date.lte={end_date}&limit=5000&sort=execution_date.asc"
    )


def _sanitize_split_url(url: str) -> str:
    safe_url = _sanitize_api_url(url)
    if urllib.parse.urlsplit(safe_url).path.rstrip("/") != "/stocks/v1/splits":
        raise MassiveError("Refusing unexpected Massive split endpoint path")
    return safe_url


def _normalise_split_row(
    row: Mapping[str, Any], *, start: str, end: str
) -> tuple[Any, ...]:
    """Validate one official split row without consuming cumulative factors."""

    ticker_value = row.get("ticker")
    if not isinstance(ticker_value, str):
        raise MassiveError("Split row is missing required ticker")
    ticker = ticker_value.strip()
    if not ticker or len(ticker) > 64:
        raise MassiveError("Split row has invalid ticker")

    execution_value = row.get("execution_date")
    if not isinstance(execution_value, str) or not execution_value.strip():
        raise MassiveError("Split row is missing required execution_date")
    execution_date = _validate_session_date(execution_value.strip())
    if execution_date < start or execution_date > end:
        raise MassiveError("Split execution_date is outside the explicit snapshot")

    adjustment_value = row.get("adjustment_type")
    if not isinstance(adjustment_value, str):
        raise MassiveError("Split row is missing required adjustment_type")
    adjustment_type = adjustment_value.strip()
    if adjustment_type not in ALLOWED_SPLIT_TYPES:
        raise MassiveError("Split row has unsupported type")

    if "split_from" not in row or row.get("split_from") is None:
        raise MassiveError("Split row is missing required split_from")
    if "split_to" not in row or row.get("split_to") is None:
        raise MassiveError("Split row is missing required split_to")
    split_from = _finite_number(row.get("split_from"), "split_from")
    split_to = _finite_number(row.get("split_to"), "split_to")
    if split_from <= 0 or split_to <= 0:
        raise MassiveError("Split ratios must be positive")

    provider_id: str | None = None
    if row.get("id") is not None:
        if not isinstance(row.get("id"), str) or not str(row.get("id")).strip():
            raise MassiveError("Split row has invalid optional id")
        provider_id = str(row.get("id")).strip()

    # One issuer can have multiple distinct same-day effects of the same type
    # (observed in the official stock-dividend feed).  Bind the natural event
    # identity to the complete normalized economic effect.  Provider-ID reuse
    # remains an independent conflict key through ``split_key``.
    event_identity_material = _canonical_json_bytes(
        [ticker, execution_date, adjustment_type, split_from, split_to]
    )
    event_identity_key = "event:" + _sha256_bytes(event_identity_material)
    if provider_id is None:
        split_key = event_identity_key
    else:
        split_key = "id:" + _sha256_bytes(provider_id.encode("utf-8"))
    raw_json = _canonical_json_bytes(dict(row)).decode("utf-8")
    return (
        split_key,
        event_identity_key,
        provider_id,
        ticker,
        execution_date,
        adjustment_type,
        split_from,
        split_to,
        raw_json,
    )


def _split_pages_digest(pages: Iterable[tuple[Any, ...]]) -> str:
    """Hash the ordered, complete page chain stored for a split snapshot."""

    digest = hashlib.sha256()
    for page in pages:
        digest.update(_canonical_json_bytes(list(page)))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_split_snapshot_state(
    conn: sqlite3.Connection,
    *,
    start: str,
    end: str,
) -> dict[str, Any]:
    """Verify checkpoint, cursor chain, every exact raw hash, and row count."""

    snapshot_key = split_snapshot_key(start, end)
    checkpoint = conn.execute(
        "SELECT cursor,status,row_count,content_sha256,updated_at_utc "
        "FROM fetch_checkpoint WHERE checkpoint_key=?",
        (snapshot_key,),
    ).fetchone()
    pages = conn.execute(
        "SELECT page_number,request_key,sanitized_url,response_sha256,next_url,"
        "row_count,retrieved_at_utc FROM stock_split_pages "
        "WHERE snapshot_key=? ORDER BY page_number",
        (snapshot_key,),
    ).fetchall()
    if checkpoint is None:
        if pages:
            raise MassiveError("Split pages exist without a checkpoint")
        return {
            "snapshot_key": snapshot_key,
            "status": "missing",
            "cursor": None,
            "row_count": 0,
            "pages": 0,
            "all_pages_sha256": _split_pages_digest(()),
            "page_records": [],
        }
    if not pages:
        raise MassiveError("Split checkpoint exists without page records")

    expected_url = _sanitize_split_url(_split_initial_url(start, end))
    digest_records: list[tuple[Any, ...]] = []
    for expected_number, page in enumerate(pages, start=1):
        (
            page_number,
            request_key,
            sanitized_url,
            response_sha256,
            next_url,
            page_row_count,
            retrieved_at,
        ) = page
        if int(page_number) != expected_number:
            raise MassiveError("Split page sequence is not contiguous")
        if str(sanitized_url) != expected_url:
            raise MassiveError("Split page cursor chain is inconsistent")
        raw_row = conn.execute(
            "SELECT kind,sanitized_url,response_sha256,raw_gzip,row_count "
            "FROM raw_responses WHERE request_key=?",
            (request_key,),
        ).fetchone()
        if raw_row is None:
            raise MassiveError("Split page is missing its frozen raw response")
        raw_kind, raw_url, raw_hash, raw_gzip, raw_row_count = raw_row
        if raw_kind != "stock_splits" or raw_url != sanitized_url:
            raise MassiveError("Split raw response identity is inconsistent")
        if raw_hash != response_sha256 or int(raw_row_count) != int(page_row_count):
            raise MassiveError("Split page metadata conflicts with its raw response")
        try:
            raw = gzip.decompress(bytes(raw_gzip))
        except (OSError, EOFError) as exc:
            raise MassiveError("Split raw response is not valid gzip") from exc
        if _sha256_bytes(raw) != response_sha256:
            raise MassiveError("Split raw response hash verification failed")
        safe_next = None if next_url is None else _sanitize_split_url(str(next_url))
        digest_records.append(
            (
                int(page_number),
                str(request_key),
                str(response_sha256),
                safe_next,
                int(page_row_count),
            )
        )
        expected_url = safe_next or ""

    cursor, status, checkpoint_rows, checkpoint_digest, updated_at = checkpoint
    safe_cursor = None if cursor is None else _sanitize_split_url(str(cursor))
    last_next = digest_records[-1][3]
    if safe_cursor != last_next:
        raise MassiveError("Split checkpoint cursor does not match the page chain")
    if status == "complete" and (safe_cursor is not None or last_next is not None):
        raise MassiveError("Complete split checkpoint still has a pagination cursor")
    if status == "in_progress" and safe_cursor is None:
        raise MassiveError("In-progress split checkpoint has no pagination cursor")
    if status not in {"complete", "in_progress"}:
        raise MassiveError("Split checkpoint has an unsupported status")

    event_rows = int(
        conn.execute(
            "SELECT COUNT(*) FROM stock_splits WHERE snapshot_key=?",
            (snapshot_key,),
        ).fetchone()[0]
    )
    summed_rows = sum(int(page[5]) for page in pages)
    if event_rows != summed_rows or event_rows != int(checkpoint_rows):
        raise MassiveError("Split checkpoint row count is inconsistent")
    all_pages_sha256 = _split_pages_digest(digest_records)
    if str(checkpoint_digest) != all_pages_sha256:
        raise MassiveError("Split all-page checkpoint digest is inconsistent")
    return {
        "snapshot_key": snapshot_key,
        "status": str(status),
        "cursor": safe_cursor,
        "row_count": event_rows,
        "pages": len(pages),
        "all_pages_sha256": all_pages_sha256,
        "updated_at": str(updated_at),
        "page_records": digest_records,
        "page_urls": [str(page[2]) for page in pages],
    }


def sync_splits(
    conn: sqlite3.Connection,
    client: MassiveClient,
    *,
    start: str = DEFAULT_SPLIT_SNAPSHOT_START,
    end: str = DEFAULT_SPLIT_SNAPSHOT_END,
    max_pages: int = DEFAULT_MAX_SPLIT_PAGES,
    failpoint: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Freeze and normalize the official paginated split event snapshot."""

    start = _validate_session_date(start)
    end = _validate_session_date(end)
    snapshot_key = split_snapshot_key(start, end)
    page_limit = int(max_pages)
    if page_limit < 1:
        raise MassiveError("Split max_pages must be positive")

    state = _verify_split_snapshot_state(conn, start=start, end=end)
    if state["status"] == "complete":
        return {
            "snapshot_key": snapshot_key,
            "start": start,
            "end": end,
            "row_count": int(state["row_count"]),
            "pages": int(state["pages"]),
            "all_pages_sha256": state["all_pages_sha256"],
            "status": "complete",
            "resumed_without_network": True,
        }
    if int(state["pages"]) >= page_limit:
        raise MassiveError("Split pagination exceeded the configured page bound")

    url = str(state["cursor"] or _split_initial_url(start, end))
    total_rows = int(state["row_count"])
    page_number = int(state["pages"]) + 1
    digest_records = list(state["page_records"])
    seen_urls = set(state.get("page_urls", []))
    while url:
        if page_number > page_limit:
            raise MassiveError("Split pagination exceeded the configured page bound")
        safe_url = _sanitize_split_url(url)
        if safe_url in seen_urls:
            raise MassiveError("Split pagination cursor repeated")
        seen_urls.add(safe_url)
        fetched = client.get_json(safe_url)
        payload = fetched.payload
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Split response status was not usable")
        raw_rows = payload.get("results")
        if not isinstance(raw_rows, list):
            raise MassiveError("Split results must be a list")

        rows: dict[str, tuple[Any, ...]] = {}
        split_keys: set[str] = set()
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                raise MassiveError("Split result must be an object")
            row = _normalise_split_row(raw_row, start=start, end=end)
            event_identity_key = str(row[1])
            if event_identity_key in rows:
                if rows[event_identity_key] != row:
                    raise MassiveError("Split page contains conflicting events")
                raise MassiveError("Split page contains a duplicate event")
            if str(row[0]) in split_keys:
                raise MassiveError("Split page reuses a provider event id")
            rows[event_identity_key] = row
            split_keys.add(str(row[0]))

        next_url_value = payload.get("next_url")
        next_url = (
            None
            if not next_url_value
            else _sanitize_split_url(str(next_url_value))
        )
        if next_url is not None and next_url in seen_urls:
            raise MassiveError("Split pagination cursor repeated")
        request_key = _request_key(f"stock_splits:{snapshot_key}", safe_url)
        status = "complete" if next_url is None else "in_progress"
        digest_record = (
            page_number,
            request_key,
            fetched.sha256,
            next_url,
            len(rows),
        )
        all_pages_sha256 = _split_pages_digest([*digest_records, digest_record])

        with conn:
            _insert_raw_response(
                conn,
                request_key=request_key,
                kind="stock_splits",
                fetched=fetched,
                row_count=len(rows),
                adjusted=None,
            )
            if failpoint is not None:
                failpoint(
                    stage="after_split_raw_insert",
                    snapshot_key=snapshot_key,
                    page_number=page_number,
                )
            for row in rows.values():
                existing = conn.execute(
                    "SELECT split_key,event_identity_key,provider_id,ticker,execution_date,"
                    "adjustment_type,split_from,split_to,raw_json FROM stock_splits "
                    "WHERE snapshot_key=? AND (split_key=? OR event_identity_key=?)",
                    (snapshot_key, row[0], row[1]),
                ).fetchall()
                if existing:
                    expected = tuple(row)
                    if len(existing) == 1 and tuple(existing[0]) == expected:
                        raise MassiveError("Split pagination repeated an existing event")
                    raise MassiveError("Split event conflicts with frozen values")
                conn.execute(
                    "INSERT INTO stock_splits("
                    "snapshot_key,split_key,event_identity_key,provider_id,ticker,"
                    "execution_date,adjustment_type,split_from,split_to,raw_json,request_key"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (snapshot_key, *row, request_key),
                )
            conn.execute(
                "INSERT INTO stock_split_pages("
                "snapshot_key,page_number,request_key,sanitized_url,response_sha256,"
                "next_url,row_count,retrieved_at_utc) VALUES(?,?,?,?,?,?,?,?)",
                (
                    snapshot_key,
                    page_number,
                    request_key,
                    fetched.url,
                    fetched.sha256,
                    next_url,
                    len(rows),
                    fetched.retrieved_at,
                ),
            )
            _upsert_checkpoint(
                conn,
                checkpoint_key=snapshot_key,
                kind="stock_splits",
                cursor=next_url,
                status=status,
                row_count=total_rows + len(rows),
                content_sha256=all_pages_sha256,
                updated_at=fetched.retrieved_at,
            )

        digest_records.append(digest_record)
        total_rows += len(rows)
        page_number += 1
        url = next_url or ""

    verified = _verify_split_snapshot_state(conn, start=start, end=end)
    if verified["status"] != "complete":
        raise MassiveError("Split sync ended without a complete checkpoint")
    return {
        "snapshot_key": snapshot_key,
        "start": start,
        "end": end,
        "row_count": int(verified["row_count"]),
        "pages": int(verified["pages"]),
        "all_pages_sha256": verified["all_pages_sha256"],
        "status": "complete",
        "resumed_without_network": False,
    }


def dividend_snapshot_key(start: str, end: str) -> str:
    """Return the explicit declaration-date range identity for one snapshot."""

    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    if start_date > end_date:
        raise MassiveError("Dividend snapshot start must not be after end")
    return f"stock_dividends:{start_date}:{end_date}"


def _dividend_initial_url(start: str, end: str) -> str:
    # The current /stocks/v1/dividends contract does not expose a
    # declaration_date query parameter.  Freeze the complete provider page
    # chain and apply the explicit decision range only in the safe projection.
    _validate_session_date(start)
    _validate_session_date(end)
    # The endpoint documents ticker/ascending as its default order.  The live
    # contract rejects an explicit declaration-date sort, so bind only the
    # maximum page size and follow the opaque cursor chain verbatim.
    return f"{API_ORIGIN}/stocks/v1/dividends?limit=5000"


def _sanitize_dividend_url(
    url: str,
    *,
    start: str,
    end: str,
    require_explicit_contract: bool = False,
) -> str:
    """Allow only the declared dividend endpoint and immutable query contract."""

    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    original = urllib.parse.urlsplit(str(url))
    if original.netloc.casefold() != ALLOWED_API_HOST:
        raise MassiveError("Refusing non-canonical Massive dividend API origin")
    safe_url = _sanitize_api_url(url)
    parsed = urllib.parse.urlsplit(safe_url)
    if parsed.path.rstrip("/") != "/stocks/v1/dividends":
        raise MassiveError("Refusing unexpected Massive dividend endpoint path")

    expected = {"limit": "5000"}
    observed: dict[str, str] = {}
    allowed = {*expected, "cursor"}
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key not in allowed:
            raise MassiveError(f"Dividend URL contains unexpected query field: {key}")
        if key in observed:
            raise MassiveError(f"Dividend pagination repeats query field: {key}")
        if not value:
            raise MassiveError(f"Dividend URL has empty query field: {key}")
        observed[key] = value
    for key, expected_value in expected.items():
        if require_explicit_contract and key not in observed:
            raise MassiveError(f"Dividend initial URL is missing query field: {key}")
        if key in observed and observed[key] != expected_value:
            raise MassiveError(f"Dividend pagination changed query field: {key}")
    if require_explicit_contract and "cursor" in observed:
        raise MassiveError("Dividend initial URL must not contain a cursor")
    if not require_explicit_contract and "cursor" not in observed:
        raise MassiveError("Dividend continuation URL is missing its cursor")
    return safe_url


def _canonical_decimal_text(value: Any, field: str = "decimal") -> str:
    """Encode a finite JSON decimal losslessly as one canonical TEXT value."""

    if value is None or isinstance(value, bool):
        raise MassiveError(f"Invalid decimal field: {field}")
    try:
        if isinstance(value, Decimal):
            number = value
        elif isinstance(value, int):
            number = Decimal(value)
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise MassiveError(f"Non-finite decimal field: {field}")
            number = Decimal(str(value))
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                raise MassiveError(f"Invalid decimal field: {field}")
            number = Decimal(text)
        else:
            raise MassiveError(f"Invalid decimal field: {field}")
    except InvalidOperation as exc:
        raise MassiveError(f"Invalid decimal field: {field}") from exc
    if not number.is_finite():
        raise MassiveError(f"Non-finite decimal field: {field}")
    if number == 0:
        return "0"
    canonical = format(number, "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    return canonical


def _decimal_json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _canonical_decimal_text(value)
    if isinstance(value, Mapping):
        return {str(key): _decimal_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decimal_json_safe(item) for item in value]
    return value


def _decode_decimal_json(raw: bytes, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MassiveError(f"{label} frozen raw response is not valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise MassiveError(f"{label} frozen raw root is not an object")
    return dict(payload)


def _normalise_dividend_row(
    row: Mapping[str, Any], *, start: str, end: str
) -> tuple[Any, ...]:
    """Normalize only decision-safe fields while retaining the full raw object."""

    provider_value = row.get("id")
    provider_id = (
        provider_value.strip()
        if isinstance(provider_value, str) and provider_value.strip()
        else None
    )
    if provider_id is not None and len(provider_id) > 512:
        raise MassiveError("Dividend row has invalid provider id")

    ticker_value = row.get("ticker")
    ticker = (
        ticker_value.strip()
        if isinstance(ticker_value, str) and ticker_value.strip()
        else None
    )
    if ticker is not None and len(ticker) > 64:
        raise MassiveError("Dividend row has invalid ticker")

    declaration_value = row.get("declaration_date")
    declaration_date = None
    if isinstance(declaration_value, str) and declaration_value.strip():
        declaration_date = _validate_session_date(declaration_value.strip())
    elif declaration_value is not None:
        raise MassiveError("Dividend row has invalid declaration_date")
    # The endpoint cannot filter declaration dates.  Rows outside the local
    # decision range remain hash-bound provenance and are excluded by
    # decision_safe_dividend_rows below.

    ex_value = row.get("ex_dividend_date")
    ex_dividend_date = None
    if isinstance(ex_value, str) and ex_value.strip():
        ex_dividend_date = _validate_session_date(ex_value.strip())
    elif ex_value is not None:
        raise MassiveError("Dividend row has invalid ex_dividend_date")

    cash_amount = None
    if row.get("cash_amount") is not None:
        cash_amount = _canonical_decimal_text(row.get("cash_amount"), "cash_amount")

    currency_value = row.get("currency")
    currency = (
        currency_value.strip()
        if isinstance(currency_value, str) and currency_value.strip()
        else None
    )
    if currency is not None and len(currency) > 16:
        raise MassiveError("Dividend row has invalid currency")

    raw_json = _canonical_json_bytes(_decimal_json_safe(dict(row))).decode("utf-8")
    row_identity_key = (
        "id:" + _sha256_bytes(provider_id.encode("utf-8"))
        if provider_id is not None
        else "raw:" + _sha256_bytes(raw_json.encode("utf-8"))
    )
    return (
        row_identity_key,
        provider_id,
        ticker,
        declaration_date,
        ex_dividend_date,
        cash_amount,
        currency,
        raw_json,
    )


def _normalise_dividend_page(
    raw_rows: Iterable[Any], *, start: str, end: str, identity_scope: str = "page"
) -> dict[str, tuple[Any, ...]]:
    rows: dict[str, tuple[Any, ...]] = {}
    provider_ids: set[str] = set()
    for row_number, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, Mapping):
            raise MassiveError("Dividend result must be an object")
        row = _normalise_dividend_row(raw_row, start=start, end=end)
        if row[1] is None:
            fallback_material = _canonical_json_bytes(
                [identity_scope, row_number, row[-1]]
            )
            row = (
                "raw:" + _sha256_bytes(fallback_material),
                *row[1:],
            )
        row_identity_key = str(row[0])
        provider_id = row[1]
        if row_identity_key in rows:
            if rows[row_identity_key] != row:
                raise MassiveError("Dividend page has a provider-ID conflict")
            raise MassiveError("Dividend page repeats a row identity")
        if provider_id is not None and str(provider_id) in provider_ids:
            raise MassiveError("Dividend page has a provider-ID conflict")
        rows[row_identity_key] = row
        if provider_id is not None:
            provider_ids.add(str(provider_id))
    return rows


def _dividend_pages_digest(pages: Iterable[tuple[Any, ...]]) -> str:
    digest = hashlib.sha256()
    for page in pages:
        digest.update(_canonical_json_bytes(list(page)))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_dividend_snapshot_state(
    conn: sqlite3.Connection,
    *,
    start: str = DEFAULT_DIVIDEND_SNAPSHOT_START,
    end: str = DEFAULT_DIVIDEND_SNAPSHOT_END,
) -> dict[str, Any]:
    """Replay every raw dividend page and prove all stored rows and metadata."""

    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    snapshot_key = dividend_snapshot_key(start_date, end_date)
    checkpoint = conn.execute(
        "SELECT kind,cursor,status,row_count,content_sha256,updated_at_utc "
        "FROM fetch_checkpoint WHERE checkpoint_key=?",
        (snapshot_key,),
    ).fetchone()
    pages = conn.execute(
        "SELECT page_number,request_key,sanitized_url,response_sha256,next_url,"
        "row_count,retrieved_at_utc FROM stock_dividend_pages "
        "WHERE snapshot_key=? ORDER BY page_number",
        (snapshot_key,),
    ).fetchall()
    stored_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM stock_dividends WHERE snapshot_key=?",
            (snapshot_key,),
        ).fetchone()[0]
    )
    if checkpoint is None:
        if pages or stored_count:
            raise MassiveError("Dividend rows or pages exist without a checkpoint")
        return {
            "snapshot_key": snapshot_key,
            "start": start_date,
            "end": end_date,
            "status": "missing",
            "cursor": None,
            "row_count": 0,
            "pages": 0,
            "all_pages_sha256": _dividend_pages_digest(()),
            "page_records": [],
            "page_urls": [],
        }
    if not pages:
        raise MassiveError("Dividend checkpoint exists without page records")

    expected_url = _sanitize_dividend_url(
        _dividend_initial_url(start_date, end_date),
        start=start_date,
        end=end_date,
        require_explicit_contract=True,
    )
    digest_records: list[tuple[Any, ...]] = []
    replayed_row_identities: set[str] = set()
    replayed_row_count = 0
    for expected_number, page in enumerate(pages, start=1):
        (
            page_number,
            request_key,
            sanitized_url,
            response_sha256,
            next_url,
            page_row_count,
            _retrieved_at,
        ) = page
        if int(page_number) != expected_number:
            raise MassiveError("Dividend page sequence is not contiguous")
        safe_page_url = _sanitize_dividend_url(
            str(sanitized_url),
            start=start_date,
            end=end_date,
            require_explicit_contract=expected_number == 1,
        )
        if safe_page_url != expected_url:
            raise MassiveError("Dividend page cursor chain is inconsistent")
        expected_request_key = _request_key(snapshot_key, safe_page_url)
        if str(request_key) != expected_request_key:
            raise MassiveError("Dividend request key is not snapshot-bound")
        raw_row = conn.execute(
            "SELECT kind,sanitized_url,response_sha256,raw_gzip,row_count "
            "FROM raw_responses WHERE request_key=?",
            (request_key,),
        ).fetchone()
        if raw_row is None:
            raise MassiveError("Dividend page is missing its frozen raw response")
        raw_kind, raw_url, raw_hash, raw_gzip, raw_row_count = raw_row
        if str(raw_kind) != snapshot_key or str(raw_url) != safe_page_url:
            raise MassiveError("Dividend raw response identity is inconsistent")
        if str(raw_hash) != str(response_sha256) or int(raw_row_count) != int(
            page_row_count
        ):
            raise MassiveError("Dividend page metadata conflicts with raw response")
        try:
            raw = gzip.decompress(bytes(raw_gzip))
        except (OSError, EOFError) as exc:
            raise MassiveError("Dividend raw response is not valid gzip") from exc
        if _sha256_bytes(raw) != str(response_sha256):
            raise MassiveError("Dividend raw response hash verification failed")
        raw_payload = _decode_decimal_json(raw, label="Dividend")
        if raw_payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Dividend frozen raw status is not usable")
        raw_results = raw_payload.get("results")
        if not isinstance(raw_results, list):
            raise MassiveError("Dividend frozen raw results are not a list")
        normalized_rows = _normalise_dividend_page(
            raw_results,
            start=start_date,
            end=end_date,
            identity_scope=safe_page_url,
        )
        if len(normalized_rows) != int(page_row_count):
            raise MassiveError("Dividend normalized page row count is inconsistent")
        repeated = replayed_row_identities.intersection(normalized_rows)
        if repeated:
            raise MassiveError("Dividend raw page chain repeats a row identity")
        replayed_row_identities.update(normalized_rows)
        replayed_row_count += len(normalized_rows)

        stored_rows = conn.execute(
            "SELECT row_identity_key,provider_id,ticker,declaration_date,ex_dividend_date,"
            "cash_amount,currency,raw_json FROM stock_dividends "
            "WHERE snapshot_key=? AND request_key=? ORDER BY row_identity_key",
            (snapshot_key, request_key),
        ).fetchall()
        expected_rows = sorted(normalized_rows.values(), key=lambda item: item[0])
        if [tuple(row) for row in stored_rows] != expected_rows:
            raise MassiveError(
                "Dividend normalized rows are not bound to their frozen raw page"
            )

        payload_next_value = raw_payload.get("next_url")
        payload_next = (
            None
            if not payload_next_value
            else _sanitize_dividend_url(
                str(payload_next_value),
                start=start_date,
                end=end_date,
                require_explicit_contract=False,
            )
        )
        safe_next = (
            None
            if next_url is None
            else _sanitize_dividend_url(
                str(next_url),
                start=start_date,
                end=end_date,
                require_explicit_contract=False,
            )
        )
        if safe_next != payload_next:
            raise MassiveError("Dividend page cursor is not bound to raw payload")
        digest_records.append(
            (
                int(page_number),
                str(request_key),
                str(response_sha256),
                safe_next,
                int(page_row_count),
            )
        )
        expected_url = safe_next or ""

    checkpoint_kind, cursor, status, checkpoint_rows, checkpoint_digest, updated_at = (
        checkpoint
    )
    if str(checkpoint_kind) != snapshot_key:
        raise MassiveError("Dividend checkpoint kind is not snapshot-bound")
    safe_cursor = (
        None
        if cursor is None
        else _sanitize_dividend_url(
            str(cursor),
            start=start_date,
            end=end_date,
            require_explicit_contract=False,
        )
    )
    last_next = digest_records[-1][3]
    if safe_cursor != last_next:
        raise MassiveError("Dividend checkpoint cursor does not match page chain")
    if status == "complete" and safe_cursor is not None:
        raise MassiveError("Complete dividend checkpoint still has a cursor")
    if status == "in_progress" and safe_cursor is None:
        raise MassiveError("In-progress dividend checkpoint has no cursor")
    if status not in {"complete", "in_progress"}:
        raise MassiveError("Dividend checkpoint has unsupported status")
    summed_rows = sum(int(page[5]) for page in pages)
    if not (
        stored_count
        == replayed_row_count
        == summed_rows
        == int(checkpoint_rows)
    ):
        raise MassiveError("Dividend checkpoint row count is inconsistent")
    all_pages_sha256 = _dividend_pages_digest(digest_records)
    if str(checkpoint_digest) != all_pages_sha256:
        raise MassiveError("Dividend all-page checkpoint digest is inconsistent")
    return {
        "snapshot_key": snapshot_key,
        "start": start_date,
        "end": end_date,
        "status": str(status),
        "cursor": safe_cursor,
        "row_count": stored_count,
        "pages": len(pages),
        "all_pages_sha256": all_pages_sha256,
        "updated_at": str(updated_at),
        "page_records": digest_records,
        "page_urls": [str(page[2]) for page in pages],
    }


def sync_dividends(
    conn: sqlite3.Connection,
    client: MassiveClient,
    *,
    start: str = DEFAULT_DIVIDEND_SNAPSHOT_START,
    end: str = DEFAULT_DIVIDEND_SNAPSHOT_END,
    max_pages: int = DEFAULT_MAX_DIVIDEND_PAGES,
    failpoint: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Freeze every official dividend row for one declaration-date range."""

    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    snapshot_key = dividend_snapshot_key(start_date, end_date)
    page_limit = int(max_pages)
    if page_limit < 1:
        raise MassiveError("Dividend max_pages must be positive")
    state = _verify_dividend_snapshot_state(
        conn, start=start_date, end=end_date
    )
    if state["status"] == "complete":
        return {
            "snapshot_key": snapshot_key,
            "start": start_date,
            "end": end_date,
            "row_count": int(state["row_count"]),
            "pages": int(state["pages"]),
            "all_pages_sha256": state["all_pages_sha256"],
            "status": "complete",
            "resumed_without_network": True,
        }
    if int(state["pages"]) >= page_limit:
        raise MassiveError("Dividend pagination exceeded the configured page bound")

    url = str(state["cursor"] or _dividend_initial_url(start_date, end_date))
    total_rows = int(state["row_count"])
    page_number = int(state["pages"]) + 1
    digest_records = list(state["page_records"])
    seen_urls = set(state.get("page_urls", []))
    while url:
        if page_number > page_limit:
            raise MassiveError("Dividend pagination exceeded the configured page bound")
        safe_url = _sanitize_dividend_url(
            url,
            start=start_date,
            end=end_date,
            require_explicit_contract=page_number == 1,
        )
        if safe_url in seen_urls:
            raise MassiveError("Dividend pagination cursor repeated")
        seen_urls.add(safe_url)
        fetched = client.get_json(safe_url)
        response_url = _sanitize_dividend_url(
            fetched.url,
            start=start_date,
            end=end_date,
            require_explicit_contract=page_number == 1,
        )
        if response_url != safe_url:
            raise MassiveError("Dividend response URL changed the request identity")
        payload = _decode_decimal_json(fetched.raw_bytes, label="Dividend")
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise MassiveError("Dividend response status was not usable")
        raw_rows = payload.get("results")
        if not isinstance(raw_rows, list):
            raise MassiveError("Dividend results must be a list")
        rows = _normalise_dividend_page(
            raw_rows,
            start=start_date,
            end=end_date,
            identity_scope=safe_url,
        )

        next_url_value = payload.get("next_url")
        next_url = (
            None
            if not next_url_value
            else _sanitize_dividend_url(
                str(next_url_value),
                start=start_date,
                end=end_date,
                require_explicit_contract=False,
            )
        )
        if next_url is not None and next_url in seen_urls:
            raise MassiveError("Dividend pagination cursor repeated")
        request_key = _request_key(snapshot_key, safe_url)
        status = "complete" if next_url is None else "in_progress"
        digest_record = (
            page_number,
            request_key,
            fetched.sha256,
            next_url,
            len(rows),
        )
        all_pages_sha256 = _dividend_pages_digest(
            [*digest_records, digest_record]
        )

        with conn:
            _insert_raw_response(
                conn,
                request_key=request_key,
                kind=snapshot_key,
                fetched=fetched,
                row_count=len(rows),
                adjusted=None,
            )
            if failpoint is not None:
                failpoint(
                    stage="after_dividend_raw_insert",
                    snapshot_key=snapshot_key,
                    page_number=page_number,
                )
            for row in rows.values():
                existing = conn.execute(
                    "SELECT row_identity_key,provider_id,ticker,declaration_date,"
                    "ex_dividend_date,"
                    "cash_amount,currency,raw_json FROM stock_dividends "
                    "WHERE snapshot_key=? AND (row_identity_key=? OR "
                    "(? IS NOT NULL AND provider_id=?))",
                    (snapshot_key, row[0], row[1], row[1]),
                ).fetchone()
                if existing is not None:
                    if tuple(existing) == tuple(row):
                        raise MassiveError(
                            "Dividend pagination repeats a provider ID"
                        )
                    raise MassiveError("Dividend provider-ID conflict")
                conn.execute(
                    "INSERT INTO stock_dividends("
                    "snapshot_key,row_identity_key,provider_id,ticker,declaration_date,"
                    "ex_dividend_date,cash_amount,currency,raw_json,request_key"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (snapshot_key, *row, request_key),
                )
            if failpoint is not None:
                failpoint(
                    stage="after_dividend_rows_insert",
                    snapshot_key=snapshot_key,
                    page_number=page_number,
                )
            conn.execute(
                "INSERT INTO stock_dividend_pages("
                "snapshot_key,page_number,request_key,sanitized_url,response_sha256,"
                "next_url,row_count,retrieved_at_utc) VALUES(?,?,?,?,?,?,?,?)",
                (
                    snapshot_key,
                    page_number,
                    request_key,
                    fetched.url,
                    fetched.sha256,
                    next_url,
                    len(rows),
                    fetched.retrieved_at,
                ),
            )
            _upsert_checkpoint(
                conn,
                checkpoint_key=snapshot_key,
                kind=snapshot_key,
                cursor=next_url,
                status=status,
                row_count=total_rows + len(rows),
                content_sha256=all_pages_sha256,
                updated_at=fetched.retrieved_at,
            )

        digest_records.append(digest_record)
        total_rows += len(rows)
        page_number += 1
        url = next_url or ""

    verified = _verify_dividend_snapshot_state(
        conn, start=start_date, end=end_date
    )
    if verified["status"] != "complete":
        raise MassiveError("Dividend sync ended without a complete checkpoint")
    return {
        "snapshot_key": snapshot_key,
        "start": start_date,
        "end": end_date,
        "row_count": int(verified["row_count"]),
        "pages": int(verified["pages"]),
        "all_pages_sha256": verified["all_pages_sha256"],
        "status": "complete",
        "resumed_without_network": False,
    }


def decision_safe_dividend_rows(
    conn: sqlite3.Connection,
    *,
    start: str = DEFAULT_DIVIDEND_SNAPSHOT_START,
    end: str = DEFAULT_DIVIDEND_SNAPSHOT_END,
) -> list[dict[str, str | None]]:
    """Return the complete verified projection permitted for decision research."""

    state = _verify_dividend_snapshot_state(conn, start=start, end=end)
    if state["status"] != "complete":
        raise MassiveError("Decision-safe dividends require a complete snapshot")
    return _decision_safe_dividend_rows_from_verified_state(
        conn, state=state, start=start, end=end
    )


def _decision_safe_dividend_rows_from_verified_state(
    conn: sqlite3.Connection,
    *,
    state: Mapping[str, Any],
    start: str,
    end: str,
) -> list[dict[str, str | None]]:
    """Project a snapshot whose strong verifier already passed in this call."""

    if state.get("status") != "complete":
        raise MassiveError("Decision-safe dividends require a complete snapshot")
    rows = conn.execute(
        "SELECT provider_id,ticker,declaration_date,ex_dividend_date,"
        "cash_amount,currency FROM stock_dividends WHERE snapshot_key=? "
        "AND declaration_date>=? AND declaration_date<=? "
        "ORDER BY declaration_date,ticker,provider_id",
        (
            state["snapshot_key"],
            _validate_session_date(start),
            _validate_session_date(end),
        ),
    ).fetchall()
    keys = (
        "provider_id",
        "ticker",
        "declaration_date",
        "ex_dividend_date",
        "cash_amount",
        "currency",
    )
    return [
        dict(
            zip(
                keys,
                (None if value is None else str(value) for value in row),
            )
        )
        for row in rows
    ]


def dividend_decision_safe_projection(
    conn: sqlite3.Connection,
    *,
    start: str = DEFAULT_DIVIDEND_SNAPSHOT_START,
    end: str = DEFAULT_DIVIDEND_SNAPSHOT_END,
) -> list[dict[str, str | None]]:
    """Compatibility name for the deliberately narrow decision-safe projection."""

    return decision_safe_dividend_rows(conn, start=start, end=end)


def historical_price_factor(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    price_date: str,
    as_of: str,
    snapshot_start: str = DEFAULT_SPLIT_SNAPSHOT_START,
    snapshot_end: str = DEFAULT_SPLIT_SNAPSHOT_END,
) -> float:
    """Return the event-local price factor known by an explicit cutoff.

    Only ``split_from / split_to`` is multiplied, and only for the strict
    boundary ``price_date < execution_date <= as_of``.  The provider's
    today-cumulative ``historical_adjustment_factor`` is intentionally absent
    from the normalized schema and from this calculation.
    """

    if not isinstance(ticker, str) or not ticker.strip() or ticker != ticker.strip():
        raise MassiveError("Historical factor requires an exact non-empty ticker")
    start = _validate_session_date(snapshot_start)
    end = _validate_session_date(snapshot_end)
    price_date = _validate_session_date(price_date)
    as_of = _validate_session_date(as_of)
    if not (start <= price_date <= as_of <= end):
        raise MassiveError("Historical factor dates exceed the explicit split snapshot")
    state = _verify_split_snapshot_state(conn, start=start, end=end)
    if state["status"] != "complete":
        raise MassiveError("Historical factor requires a complete split snapshot")

    snapshot_key = split_snapshot_key(start, end)
    factor = 1.0
    for split_from, split_to in conn.execute(
        "SELECT split_from,split_to FROM stock_splits "
        "WHERE snapshot_key=? AND ticker=? AND execution_date>? "
        "AND execution_date<=? ORDER BY execution_date,split_key",
        (snapshot_key, ticker, price_date, as_of),
    ):
        factor *= float(split_from) / float(split_to)
        if not math.isfinite(factor) or factor <= 0:
            raise MassiveError("Historical split factor became invalid")
    return factor


def compute_historical_price_factor(
    conn: sqlite3.Connection,
    ticker: str,
    *,
    price_date: str,
    as_of: str,
    snapshot_start: str = DEFAULT_SPLIT_SNAPSHOT_START,
    snapshot_end: str = DEFAULT_SPLIT_SNAPSHOT_END,
) -> float:
    """Compatibility spelling for :func:`historical_price_factor`."""

    return historical_price_factor(
        conn,
        ticker,
        price_date=price_date,
        as_of=as_of,
        snapshot_start=snapshot_start,
        snapshot_end=snapshot_end,
    )


def audit_reference_asof_readiness(
    conn: sqlite3.Connection,
    *,
    expected_dates: Iterable[str] = DEFAULT_REFERENCE_ASOF_DATES,
    min_rows_per_date: int = DEFAULT_MIN_REFERENCE_ASOF_ROWS,
) -> dict[str, Any]:
    """Fail closed on dated identity coverage without reading price outcomes."""

    dates = _normalise_reference_asof_dates(expected_dates)
    minimum_required = int(min_rows_per_date)
    if minimum_required < 1:
        raise MassiveError("Reference as-of audit minimum rows must be positive")

    complete_dates: list[str] = []
    missing_dates: list[str] = []
    incomplete_dates: list[str] = []
    invalid_dates: dict[str, str] = {}
    row_counts_by_date: dict[str, int] = {}
    page_counts_by_date: dict[str, int] = {}
    all_pages_sha256_by_date: dict[str, str | None] = {}
    raw_result_counts_by_date: dict[str, int] = {}
    eligible_revision_count_by_date: dict[str, int] = {}
    future_revision_count_by_date: dict[str, int] = {}
    undated_revision_count_by_date: dict[str, int] = {}
    selected_unique_row_count_by_date: dict[str, int] = {}
    vendor_revision_collapse_count_by_date: dict[str, int] = {}
    vendor_revision_group_count_by_date: dict[str, int] = {}
    vendor_revision_future_only_group_count_by_date: dict[str, int] = {}
    decision_cutoff_utc_by_date = {
        value: _utc_iso(_reference_decision_cutoff_utc(value)) for value in dates
    }
    future_only_duplicate_invalid_dates: list[str] = []
    for as_of_date in dates:
        try:
            state = _verify_reference_asof_snapshot_state(conn, as_of=as_of_date)
        except MassiveError as exc:
            invalid_dates[as_of_date] = str(exc)
            if "no row eligible by decision cutoff" in str(exc):
                future_only_duplicate_invalid_dates.append(as_of_date)
            row_counts_by_date[as_of_date] = 0
            page_counts_by_date[as_of_date] = 0
            all_pages_sha256_by_date[as_of_date] = None
            raw_result_counts_by_date[as_of_date] = 0
            eligible_revision_count_by_date[as_of_date] = 0
            future_revision_count_by_date[as_of_date] = 0
            undated_revision_count_by_date[as_of_date] = 0
            selected_unique_row_count_by_date[as_of_date] = 0
            vendor_revision_collapse_count_by_date[as_of_date] = 0
            vendor_revision_group_count_by_date[as_of_date] = 0
            vendor_revision_future_only_group_count_by_date[as_of_date] = 0
            continue
        row_counts_by_date[as_of_date] = int(state["row_count"])
        page_counts_by_date[as_of_date] = int(state["pages"])
        all_pages_sha256_by_date[as_of_date] = str(
            state["all_pages_sha256"]
        )
        raw_result_counts_by_date[as_of_date] = int(state["raw_result_count"])
        eligible_revision_count_by_date[as_of_date] = int(
            state["eligible_revision_count"]
        )
        future_revision_count_by_date[as_of_date] = int(
            state["future_revision_count"]
        )
        undated_revision_count_by_date[as_of_date] = int(
            state["undated_revision_count"]
        )
        selected_unique_row_count_by_date[as_of_date] = int(
            state["selected_unique_row_count"]
        )
        vendor_revision_collapse_count_by_date[as_of_date] = int(
            state["vendor_revision_collapse_count"]
        )
        vendor_revision_group_count_by_date[as_of_date] = int(
            state["vendor_revision_group_count"]
        )
        vendor_revision_future_only_group_count_by_date[as_of_date] = int(
            state["vendor_revision_future_only_group_count"]
        )
        if state["status"] == "complete":
            complete_dates.append(as_of_date)
        elif state["status"] == "missing":
            missing_dates.append(as_of_date)
        else:
            incomplete_dates.append(as_of_date)

    snapshot_keys = [reference_asof_snapshot_key(value) for value in dates]
    placeholders = ",".join("?" for _ in snapshot_keys)
    duplicate_asof_ticker_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT snapshot_key,ticker FROM instrument_master "
            f"WHERE snapshot_key IN ({placeholders}) "
            "GROUP BY snapshot_key,ticker HAVING COUNT(*)!=1)",
            tuple(snapshot_keys),
        ).fetchone()[0]
    )
    current_reference_row_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM instrument_master "
            "WHERE snapshot_key IN ('reference:true','reference:false')"
        ).fetchone()[0]
    )
    insufficient_row_dates = [
        value
        for value in complete_dates
        if row_counts_by_date[value] < minimum_required
    ]
    minimum_observed = min(row_counts_by_date.values()) if dates else 0
    complete_row_counts = [row_counts_by_date[value] for value in complete_dates]
    minimum_complete = min(complete_row_counts) if complete_row_counts else 0
    raw_page_hash_integrity = bool(
        len(complete_dates) == len(dates)
        and not missing_dates
        and not incomplete_dates
        and not invalid_dates
    )
    park_reasons: list[str] = []
    if missing_dates:
        park_reasons.append("reference_asof_dates_missing")
    if incomplete_dates:
        park_reasons.append("reference_asof_dates_incomplete")
    if invalid_dates:
        park_reasons.append("reference_asof_raw_page_hash_integrity_failed")
    if insufficient_row_dates:
        park_reasons.append("reference_asof_minimum_rows_not_met")
    if duplicate_asof_ticker_count:
        park_reasons.append("reference_asof_duplicate_ticker_identity")
    ready = bool(
        raw_page_hash_integrity
        and not insufficient_row_dates
        and duplicate_asof_ticker_count == 0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "status": "ready" if ready else "parked",
        "parked": not ready,
        "park_reasons": park_reasons,
        "expected_dates": dates,
        "complete_dates": complete_dates,
        "missing_dates": missing_dates,
        "incomplete_dates": incomplete_dates,
        "invalid_dates": invalid_dates,
        "insufficient_row_dates": insufficient_row_dates,
        "expected_date_count": len(dates),
        "complete_date_count": len(complete_dates),
        "minimum_rows_per_date_required": minimum_required,
        "minimum_rows_per_date_observed": minimum_observed,
        "minimum_rows_per_complete_date": minimum_complete,
        "row_counts_by_date": row_counts_by_date,
        "page_counts_by_date": page_counts_by_date,
        "all_pages_sha256_by_date": all_pages_sha256_by_date,
        "decision_cutoff_utc_by_date": decision_cutoff_utc_by_date,
        "raw_result_counts_by_date": raw_result_counts_by_date,
        "eligible_revision_count": sum(eligible_revision_count_by_date.values()),
        "eligible_revision_count_by_date": eligible_revision_count_by_date,
        "future_revision_count": sum(future_revision_count_by_date.values()),
        "future_revision_count_by_date": future_revision_count_by_date,
        "undated_revision_count": sum(undated_revision_count_by_date.values()),
        "undated_revision_count_by_date": undated_revision_count_by_date,
        "selected_unique_row_count": sum(
            selected_unique_row_count_by_date.values()
        ),
        "selected_unique_row_count_by_date": selected_unique_row_count_by_date,
        "vendor_revision_collapse_count": sum(
            vendor_revision_collapse_count_by_date.values()
        ),
        "vendor_revision_collapse_count_by_date": (
            vendor_revision_collapse_count_by_date
        ),
        "vendor_revision_group_count": sum(
            vendor_revision_group_count_by_date.values()
        ),
        "vendor_revision_group_count_by_date": vendor_revision_group_count_by_date,
        "vendor_revision_future_only_group_count": sum(
            vendor_revision_future_only_group_count_by_date.values()
        ),
        "vendor_revision_future_only_group_count_by_date": (
            vendor_revision_future_only_group_count_by_date
        ),
        "future_only_duplicate_invalid_dates": future_only_duplicate_invalid_dates,
        "duplicate_asof_ticker_count": duplicate_asof_ticker_count,
        "raw_page_hash_integrity": raw_page_hash_integrity,
        "expected_snapshot_keys": snapshot_keys,
        "identity_availability_clock": "reference_snapshot_date",
        "provider_list_date_required": False,
        "candidate_decision_membership_fields": [
            "as_of",
            "ticker",
            "type",
            "active",
        ],
        "measurement_identity_fields": [
            "composite_figi",
            "share_class_figi",
        ],
        "descriptive_fields_excluded_from_decision": [
            "name",
            "cik",
            "last_updated_utc",
            "market",
            "locale",
            "primary_exchange",
            "currency_name",
            "list_date",
            "delisted_utc",
            "raw_json",
        ],
        "vendor_revision_selection_contract": (
            "isolate last_updated_utc at/before as_of 16:00 America/New_York; "
            "validate identity and select latest only within eligible revisions; "
            "future-only duplicate groups fail closed"
        ),
        "cross_page_duplicate_policy": "fail_closed",
        "cross_page_vendor_revision_collapse_supported": False,
        "figi_candidate_ranking_filter_allowed": False,
        "figi_cross_surface_join_allowed": False,
        "future_descriptive_metadata_decision_input": False,
        "dated_endpoint_future_version_anomaly_observed": bool(
            sum(future_revision_count_by_date.values())
        ),
        "as_published_vintage_verified": False,
        "known_future_leakage": False,
        "known_future_leakage_scope": "candidate_decision_membership_fields_only",
        "pit_caveats": [
            "dated endpoint contains post-decision descriptive vendor revisions",
            "as-published reference vintage is unverified",
            "FIGIs are measurement identity only, not candidate decision inputs",
            "cross-page duplicate revisions fail closed rather than collapse",
        ],
        "current_reference_row_count": current_reference_row_count,
        "current_reference_consumed": False,
        "price_or_return_values_read": False,
        "pit_tier": "research_pit",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "paper_enabled": False,
        "live_enabled": False,
        "trade_enabled": False,
        "production_impact": "none",
    }


def audit_asof_identity_readiness(
    conn: sqlite3.Connection,
    *,
    expected_dates: Iterable[str] = DEFAULT_REFERENCE_ASOF_DATES,
    min_rows_per_date: int = DEFAULT_MIN_REFERENCE_ASOF_ROWS,
) -> dict[str, Any]:
    """Compatibility spelling for the dated reference readiness audit."""

    return audit_reference_asof_readiness(
        conn,
        expected_dates=expected_dates,
        min_rows_per_date=min_rows_per_date,
    )


def audit_normalization_readiness(
    conn: sqlite3.Connection,
    *,
    snapshot_start: str = DEFAULT_SPLIT_SNAPSHOT_START,
    snapshot_end: str = DEFAULT_SPLIT_SNAPSHOT_END,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Audit split and identity metadata without reading OHLC or returns."""

    start = _validate_session_date(snapshot_start)
    end = _validate_session_date(snapshot_end)
    as_of_date = _validate_session_date(as_of or end)
    if not (start <= as_of_date <= end):
        raise MassiveError("Normalization audit as_of is outside the split snapshot")
    snapshot_key = split_snapshot_key(start, end)
    park_reasons: list[str] = []
    split_error: str | None = None
    try:
        split_state = _verify_split_snapshot_state(conn, start=start, end=end)
        split_ready = split_state["status"] == "complete"
        if split_state["status"] == "missing":
            park_reasons.append("split_snapshot_missing")
        elif not split_ready:
            park_reasons.append("split_snapshot_incomplete")
    except MassiveError as exc:
        split_ready = False
        split_error = str(exc)
        split_state = {
            "snapshot_key": snapshot_key,
            "status": "invalid",
            "row_count": 0,
            "pages": 0,
            "all_pages_sha256": None,
        }
        park_reasons.append("split_snapshot_integrity_failed")

    identity_groups = conn.execute(
        "SELECT snapshot_key,COUNT(*),"
        "SUM(CASE WHEN list_date IS NULL OR TRIM(list_date)='' THEN 1 ELSE 0 END) "
        "FROM instrument_master GROUP BY snapshot_key ORDER BY snapshot_key"
    ).fetchall()
    identity_row_count = sum(int(row[1]) for row in identity_groups)
    missing_list_date_count = sum(int(row[2] or 0) for row in identity_groups)
    grouped_daily_complete_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM fetch_checkpoint "
            "WHERE kind='grouped_daily' AND status='complete'"
        ).fetchone()[0]
    )
    grouped_daily_ready = grouped_daily_complete_count >= EXPECTED_GROUPED_DAILY_CHECKPOINTS
    multiple_identity_ticker_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT ticker FROM instrument_master GROUP BY ticker "
            "HAVING COUNT(DISTINCT identity_key)>1)"
        ).fetchone()[0]
    )
    active_inactive_overlap_ticker_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT ticker FROM instrument_master GROUP BY ticker "
            "HAVING SUM(CASE WHEN active=1 THEN 1 ELSE 0 END)>0 "
            "AND SUM(CASE WHEN active=0 THEN 1 ELSE 0 END)>0)"
        ).fetchone()[0]
    )
    missing_both_figis_row_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM instrument_master WHERE "
            "(composite_figi IS NULL OR TRIM(composite_figi)='') AND "
            "(share_class_figi IS NULL OR TRIM(share_class_figi)='')"
        ).fetchone()[0]
    )
    current_only_keys = {
        str(row[0])
        for row in identity_groups
        if str(row[0]) in {"reference:true", "reference:false"}
    }
    required_asof_key = reference_asof_snapshot_key(as_of_date)
    required_asof_keys = {required_asof_key}
    available_keys = {str(row[0]) for row in identity_groups}
    identity_integrity_error: str | None = None
    try:
        identity_state = _verify_reference_asof_snapshot_state(
            conn, as_of=as_of_date
        )
        identity_asof_ready = bool(
            identity_state["status"] == "complete"
            and int(identity_state["row_count"]) > 0
        )
    except MassiveError as exc:
        identity_state = {
            "status": "invalid",
            "row_count": 0,
            "pages": 0,
            "all_pages_sha256": None,
        }
        identity_asof_ready = False
        identity_integrity_error = str(exc)
    if identity_row_count == 0:
        park_reasons.append("identity_reference_missing")
    elif not identity_asof_ready:
        if current_only_keys:
            park_reasons.append("identity_current_only_snapshot")
        if identity_state["status"] == "missing":
            park_reasons.append("identity_asof_snapshot_missing")
        elif identity_state["status"] == "in_progress":
            park_reasons.append("identity_asof_snapshot_incomplete")
        else:
            park_reasons.append("identity_asof_snapshot_integrity_failed")

    replay_ready = bool(split_ready and identity_asof_ready)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "status": "ready" if replay_ready else "parked",
        "parked": not replay_ready,
        "park_reasons": park_reasons,
        "snapshot_key": snapshot_key,
        "snapshot_start": start,
        "snapshot_end": end,
        "as_of": as_of_date,
        "split_ready": split_ready,
        "identity_asof_ready": identity_asof_ready,
        "identity_asof_integrity_error": identity_integrity_error,
        "identity_asof_row_count": int(identity_state.get("row_count", 0)),
        "identity_asof_page_count": int(identity_state.get("pages", 0)),
        "identity_asof_all_pages_sha256": identity_state.get("all_pages_sha256"),
        "identity_asof_raw_result_count": int(
            identity_state.get("raw_result_count", 0)
        ),
        "identity_asof_eligible_revision_count": int(
            identity_state.get("eligible_revision_count", 0)
        ),
        "identity_asof_future_revision_count": int(
            identity_state.get("future_revision_count", 0)
        ),
        "identity_asof_undated_revision_count": int(
            identity_state.get("undated_revision_count", 0)
        ),
        "identity_asof_selected_unique_row_count": int(
            identity_state.get("selected_unique_row_count", 0)
        ),
        "identity_asof_vendor_revision_collapse_count": int(
            identity_state.get("vendor_revision_collapse_count", 0)
        ),
        "identity_asof_vendor_revision_group_count": int(
            identity_state.get("vendor_revision_group_count", 0)
        ),
        "identity_asof_vendor_revision_future_only_group_count": int(
            identity_state.get("vendor_revision_future_only_group_count", 0)
        ),
        "identity_availability_clock": "reference_snapshot_date",
        "decision_cutoff_utc": _utc_iso(
            _reference_decision_cutoff_utc(as_of_date)
        ),
        "provider_list_date_required": False,
        "candidate_decision_membership_fields": [
            "as_of",
            "ticker",
            "type",
            "active",
        ],
        "measurement_identity_fields": [
            "composite_figi",
            "share_class_figi",
        ],
        "figi_candidate_ranking_filter_allowed": False,
        "figi_cross_surface_join_allowed": False,
        "future_descriptive_metadata_decision_input": False,
        "dated_endpoint_future_version_anomaly_observed": bool(
            identity_state.get("future_revision_count", 0)
        ),
        "as_published_vintage_verified": False,
        "known_future_leakage": False,
        "known_future_leakage_scope": "candidate_decision_membership_fields_only",
        "cross_page_duplicate_policy": "fail_closed",
        "pit_caveats": [
            "dated endpoint contains post-decision descriptive vendor revisions",
            "as-published reference vintage is unverified",
            "FIGIs are measurement identity only, not candidate decision inputs",
            "cross-page duplicate revisions fail closed rather than collapse",
        ],
        "current_reference_consumed": False,
        "replay_ready": replay_ready,
        "split_row_count": int(split_state.get("row_count", 0)),
        "split_page_count": int(split_state.get("pages", 0)),
        "split_all_pages_sha256": split_state.get("all_pages_sha256"),
        "split_integrity_error": split_error,
        "identity_row_count": identity_row_count,
        "identity_missing_list_date_count": missing_list_date_count,
        "identity_multiple_identity_ticker_count": multiple_identity_ticker_count,
        "identity_active_inactive_overlap_ticker_count": active_inactive_overlap_ticker_count,
        "identity_missing_both_figis_row_count": missing_both_figis_row_count,
        "identity_snapshot_keys": sorted(available_keys),
        "required_identity_snapshot_keys": sorted(required_asof_keys),
        "grouped_daily_complete_checkpoint_count": grouped_daily_complete_count,
        "grouped_daily_expected_checkpoint_count": EXPECTED_GROUPED_DAILY_CHECKPOINTS,
        "grouped_daily_ready": grouped_daily_ready,
        "price_or_return_values_read": False,
        "factor_contract": "product(split_from/split_to)",
        "historical_adjustment_factor_used": False,
        "pit_tier": "research_pit",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "paper_enabled": False,
        "live_enabled": False,
        "trade_enabled": False,
        "production_impact": "none",
    }


def _complete_reference_asof_states(
    conn: sqlite3.Connection,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    prefix = "reference-asof:"
    suffix = ":active=true:type=CS"
    states: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    keys = conn.execute(
        "SELECT checkpoint_key FROM fetch_checkpoint "
        "WHERE status='complete' AND checkpoint_key GLOB "
        "'reference-asof:*:active=true:type=CS' ORDER BY checkpoint_key"
    ).fetchall()
    for (key_value,) in keys:
        key = str(key_value)
        if not key.startswith(prefix) or not key.endswith(suffix):
            continue
        as_of = key[len(prefix) : -len(suffix)]
        try:
            as_of = _validate_session_date(as_of)
            state = _verify_reference_asof_snapshot_state(conn, as_of=as_of)
            if state["status"] == "complete" and int(state["row_count"]) > 0:
                states[as_of] = state
        except MassiveError as exc:
            errors[as_of] = str(exc)
    return states, errors


def audit_dividend_readiness(
    conn: sqlite3.Connection,
    *,
    start: str = DEFAULT_DIVIDEND_SNAPSHOT_START,
    end: str = DEFAULT_DIVIDEND_SNAPSHOT_END,
    min_touches_per_window: int = 5,
) -> dict[str, Any]:
    """Build an outcome-blind dividend-restart readiness handoff.

    Price access is constrained in SQL to ``trade_date <= declaration_date``.
    The audit never computes or reads a forward return, outcome, or post-event
    bar and cannot enable paper or live behavior.
    """

    start_date = _validate_session_date(start)
    end_date = _validate_session_date(end)
    touch_floor = max(1, int(min_touches_per_window))
    snapshot_key = dividend_snapshot_key(start_date, end_date)
    blockers: list[str] = []
    integrity_error: str | None = None
    try:
        dividend_state = _verify_dividend_snapshot_state(
            conn, start=start_date, end=end_date
        )
        dividend_complete = dividend_state["status"] == "complete"
        if not dividend_complete:
            blockers.append("dividend_snapshot_not_complete")
    except MassiveError as exc:
        integrity_error = str(exc)
        dividend_complete = False
        dividend_state = {
            "snapshot_key": snapshot_key,
            "status": "invalid",
            "row_count": 0,
            "pages": 0,
            "all_pages_sha256": None,
        }
        blockers.append("dividend_snapshot_integrity_failed")

    safe_rows: list[dict[str, str | None]] = []
    if dividend_complete:
        safe_rows = _decision_safe_dividend_rows_from_verified_state(
            conn,
            state=dividend_state,
            start=start_date,
            end=end_date,
        )

    identity_states, identity_errors = _complete_reference_asof_states(conn)
    identity_dates = sorted(identity_states)
    if not identity_dates:
        blockers.append("complete_prior_reference_asof_snapshot_missing")
    if identity_errors:
        blockers.append("reference_asof_snapshot_integrity_failed")

    exclusion_counts: dict[str, int] = {}

    def exclude(reason: str) -> None:
        exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1

    positive_groups: dict[tuple[str, str], list[dict[str, str | None]]] = {}
    for row in safe_rows:
        ticker = row.get("ticker")
        declaration = row.get("declaration_date")
        amount = row.get("cash_amount")
        currency = row.get("currency")
        if not ticker or not declaration or amount is None or not currency:
            exclude("missing_decision_safe_field")
            continue
        try:
            positive = Decimal(amount) > 0
        except InvalidOperation:
            exclude("invalid_cash_amount")
            continue
        if not positive:
            exclude("nonpositive_cash_amount")
            continue
        if currency.casefold() != "usd":
            exclude("non_usd_currency")
            continue
        positive_groups.setdefault((ticker, declaration), []).append(row)

    positive_dates_by_ticker: dict[str, list[str]] = {}
    for ticker, declaration in positive_groups:
        positive_dates_by_ticker.setdefault(ticker, []).append(declaration)
    for ticker in positive_dates_by_ticker:
        positive_dates_by_ticker[ticker] = sorted(
            set(positive_dates_by_ticker[ticker])
        )

    candidates_by_date: dict[str, list[dict[str, Any]]] = {}
    predecision_price_values_read = False
    duplicate_effect_rows_collapsed = 0
    ticker_date_groups_collapsed = 0
    for (ticker, declaration), members in sorted(positive_groups.items()):
        decision_day = dt.date.fromisoformat(declaration)
        lookback_start = decision_day - dt.timedelta(days=DIVIDEND_PRIOR_GAP_DAYS)
        if dt.date.fromisoformat(start_date) > lookback_start:
            exclude("prior_gap_source_coverage_insufficient")
            continue
        prior_dates = [
            value
            for value in positive_dates_by_ticker[ticker]
            if value < declaration
        ]
        previous_declaration = prior_dates[-1] if prior_dates else None
        prior_gap_days = (
            None
            if previous_declaration is None
            else (decision_day - dt.date.fromisoformat(previous_declaration)).days
        )
        if prior_gap_days is not None and prior_gap_days < DIVIDEND_PRIOR_GAP_DAYS:
            exclude("prior_same_ticker_gap_below_1095_days")
            continue

        window_name = next(
            (
                name
                for name, (window_start, window_end) in DIVIDEND_FIXED_WINDOWS.items()
                if window_start <= declaration <= window_end
            ),
            None,
        )
        if window_name is None:
            continue

        prior_identity_dates = [value for value in identity_dates if value <= declaration]
        if not prior_identity_dates:
            exclude("prior_reference_asof_snapshot_missing")
            continue
        identity_as_of = prior_identity_dates[-1]
        identity_key = reference_asof_snapshot_key(identity_as_of)
        identity_member = conn.execute(
            "SELECT 1 FROM instrument_master WHERE snapshot_key=? AND ticker=? "
            "AND active=1 AND instrument_type='CS' LIMIT 1",
            (identity_key, ticker),
        ).fetchone()
        if identity_member is None:
            exclude("ticker_absent_from_prior_active_common_stock_snapshot")
            continue

        # This is the only price query in the audit.  Its upper bound is the
        # declaration date itself, so a later row cannot affect any result.
        bars = conn.execute(
            "SELECT trade_date,close,volume FROM daily_bars "
            "WHERE ticker=? AND trade_date<=? ORDER BY trade_date DESC LIMIT ?",
            (ticker, declaration, DIVIDEND_MIN_PREDECISION_BARS),
        ).fetchall()
        predecision_price_values_read = True
        if len(bars) < DIVIDEND_MIN_PREDECISION_BARS:
            exclude("fewer_than_20_predecision_bars")
            continue
        try:
            reference_close = Decimal(str(bars[0][1]))
            dollar_volumes = [
                Decimal(str(close_value)) * Decimal(str(volume_value))
                for _trade_date, close_value, volume_value in bars
            ]
            median_dollar_volume = median(dollar_volumes)
        except (InvalidOperation, TypeError, ValueError):
            exclude("invalid_predecision_price_or_volume")
            continue
        if reference_close < DIVIDEND_MIN_CLOSE:
            exclude("declaration_or_previous_close_below_3")
            continue
        if median_dollar_volume < DIVIDEND_MIN_MEDIAN_DOLLAR_VOLUME:
            exclude("trailing20_median_dollar_volume_below_1m")
            continue

        ordered_members = sorted(
            members,
            key=lambda item: (
                item.get("provider_id") is None,
                item.get("provider_id") or "",
                item.get("ex_dividend_date") or "",
                item.get("cash_amount") or "",
            ),
        )
        representative = ordered_members[0]
        effects: dict[tuple[Any, ...], int] = {}
        for member in ordered_members:
            effect = (
                member.get("ticker"),
                member.get("declaration_date"),
                member.get("ex_dividend_date"),
                member.get("cash_amount"),
                (member.get("currency") or "").casefold(),
            )
            effects[effect] = effects.get(effect, 0) + 1
        duplicate_effect_rows_collapsed += sum(
            max(0, count - 1) for count in effects.values()
        )
        ticker_date_groups_collapsed += max(0, len(ordered_members) - 1)
        candidate = {
            "ticker": ticker,
            "declaration_date": declaration,
            "ex_dividend_date": representative.get("ex_dividend_date"),
            "cash_amount": representative.get("cash_amount"),
            "currency": representative.get("currency"),
            "provider_ids": sorted(
                str(member["provider_id"])
                for member in ordered_members
                if member.get("provider_id") is not None
            ),
            "provider_row_count": len(ordered_members),
            "economic_effect_count": len(effects),
            "previous_positive_usd_declaration_date": previous_declaration,
            "prior_gap_days": prior_gap_days,
            "prior_gap_lookback_days": DIVIDEND_PRIOR_GAP_DAYS,
            "identity_snapshot_as_of": identity_as_of,
            "identity_snapshot_age_days": (
                decision_day - dt.date.fromisoformat(identity_as_of)
            ).days,
            "predecision_bar_count": len(bars),
            "reference_close_date": str(bars[0][0]),
            "reference_close": _canonical_decimal_text(
                reference_close, "reference_close"
            ),
            "trailing20_median_dollar_volume": _canonical_decimal_text(
                median_dollar_volume, "median_dollar_volume"
            ),
            "window": window_name,
        }
        candidates_by_date.setdefault(declaration, []).append(candidate)

    selected_by_window: dict[str, list[dict[str, Any]]] = {
        name: [] for name in DIVIDEND_FIXED_WINDOWS
    }
    eligible_before_top2_by_window = {
        name: 0 for name in DIVIDEND_FIXED_WINDOWS
    }
    for declaration, candidates in sorted(candidates_by_date.items()):
        ordered = sorted(
            candidates,
            key=lambda item: (
                -Decimal(item["trailing20_median_dollar_volume"]),
                item["ticker"],
            ),
        )
        for candidate in ordered:
            eligible_before_top2_by_window[candidate["window"]] += 1
        for rank, candidate in enumerate(ordered[:DIVIDEND_TOP_PER_DAY], start=1):
            selected = dict(candidate)
            selected["liquidity_rank_on_declaration_date"] = rank
            selected_by_window[candidate["window"]].append(selected)
        if len(ordered) > DIVIDEND_TOP_PER_DAY:
            exclusion_counts["outside_top2_daily_liquidity"] = (
                exclusion_counts.get("outside_top2_daily_liquidity", 0)
                + len(ordered)
                - DIVIDEND_TOP_PER_DAY
            )

    windows: dict[str, dict[str, Any]] = {}
    for name, (window_start, window_end) in DIVIDEND_FIXED_WINDOWS.items():
        selected = sorted(
            selected_by_window[name],
            key=lambda item: (item["declaration_date"], item["ticker"]),
        )
        windows[name] = {
            "start": window_start,
            "end": window_end,
            "eligible_before_top2_count": eligible_before_top2_by_window[name],
            "selected_touch_count": len(selected),
            "unique_ticker_date_count": len(
                {(row["ticker"], row["declaration_date"]) for row in selected}
            ),
            "touch_floor": touch_floor,
            "touch_floor_pass": len(selected) >= touch_floor,
            "selected": selected,
        }

    all_window_touch_floors_pass = all(
        value["touch_floor_pass"] for value in windows.values()
    )
    readiness_pass = bool(
        dividend_complete and identity_dates and all_window_touch_floors_pass
    )
    if not all_window_touch_floors_pass:
        blockers.append("fixed_window_touch_floor_not_met")
    blockers.extend(
        [
            "pending_outcome_blind_d0_d3",
            "pending_model_diverse_debate",
            "pending_separate_private_replay_scout",
        ]
    )

    selected_tickers = sorted(
        {
            row["ticker"]
            for window in windows.values()
            for row in window["selected"]
        }
    )
    hypothesis = (
        "A first positive USD cash distribution after at least 1095 days "
        "without a same-ticker positive USD declaration may signal a durable "
        "capital-distribution restart."
    )
    falsifier = (
        "Reject promotion if any fixed window has fewer than five decisions, "
        "or a later separately authorized replay fails to beat the same-date "
        "cash-feasible core candidate (cash when none is admitted)."
    )
    next_action = (
        "Run outcome-blind D0-D3 and model-diverse debate; only an approved "
        "panel may request a separate private_replay_scout."
    )
    synthesis_pass = {
        "baseline_universe": [
            "same-date cash-feasible active-common-stock cross-section"
        ],
        "opportunity_cost_winner": "cash/no new core entry",
        "evidence_surfaces_used": [
            "hash-bound Massive dividend declaration pages",
            "complete Massive reference-asof active common-stock snapshots",
            "Massive unadjusted daily bars no later than each declaration date",
        ],
        "evidence_surfaces_missing": [
            "canonical as-published dividend vintages",
            "outcome-blind D0-D3 review",
            "model-diverse debate",
            "separately authorized private replay",
        ],
        "hypothesis_candidates": [
            {
                "hypothesis": hypothesis,
                "baseline": "cash/no new core entry",
                "treatment": "top-two liquid dividend-restart candidates per declaration day",
                "horizon": "next regular-session open through H10 close, after cost",
                "replacement_comparator": (
                    "same-date cash-feasible core candidate or cash"
                ),
                "secondary_comparators": "SPY and QQQ over the same window",
                "falsifier": falsifier,
            }
        ],
        "selected_hypothesis": hypothesis,
        "economic_mechanism": (
            "A long interruption followed by a positive cash declaration can "
            "reveal restored cash-generation confidence and capital-return capacity."
        ),
        "falsifier": falsifier,
        "pit_tier": "research_pit",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "next_machine_action": next_action,
        "research_digest_status": "latest_digest_entries_terminal",
        "research_digest_ledger_append_required": False,
        "research_digest_note": (
            "latest_digest entries are already terminal; no new ledger append"
        ),
        "outcome_access": "none; no return or outcome field was read",
        "selected_tickers": selected_tickers,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "record_type": "massive_dividend_declaration_readiness",
        "status": "blocked",
        "blocked": True,
        "blocked_reasons": list(dict.fromkeys(blockers)),
        "readiness_checks_pass": readiness_pass,
        "snapshot_key": snapshot_key,
        "snapshot_start": start_date,
        "snapshot_end": end_date,
        "dividend_snapshot_status": dividend_state["status"],
        "dividend_row_count": int(dividend_state.get("row_count", 0)),
        "dividend_page_count": int(dividend_state.get("pages", 0)),
        "dividend_all_pages_sha256": dividend_state.get("all_pages_sha256"),
        "dividend_integrity_error": integrity_error,
        "decision_safe_projection_fields": [
            "provider_id",
            "ticker",
            "declaration_date",
            "ex_dividend_date",
            "cash_amount",
            "currency",
        ],
        "stored_provider_row_count": len(safe_rows),
        "positive_usd_ticker_date_group_count": len(positive_groups),
        "ticker_date_rows_collapsed": ticker_date_groups_collapsed,
        "exact_effect_duplicate_rows_collapsed": duplicate_effect_rows_collapsed,
        "one_ticker_date_decision": True,
        "prior_same_ticker_gap_days": DIVIDEND_PRIOR_GAP_DAYS,
        "minimum_predecision_bars": DIVIDEND_MIN_PREDECISION_BARS,
        "minimum_reference_close": "3",
        "minimum_trailing20_median_dollar_volume": "1000000",
        "top_candidates_per_declaration_day": DIVIDEND_TOP_PER_DAY,
        "predeclared_horizon": "next regular-session open through H10 close, after cost",
        "primary_replacement_comparator": (
            "same-date cash-feasible core candidate or cash"
        ),
        "secondary_comparators": "SPY and QQQ over the same window",
        "reference_asof_complete_dates": identity_dates,
        "reference_asof_integrity_errors": identity_errors,
        "identity_rule": (
            "latest verified complete active-CS reference-asof snapshot "
            "whose snapshot date is no later than declaration_date"
        ),
        "windows": windows,
        "all_fixed_window_touch_floors_pass": all_window_touch_floors_pass,
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "predecision_price_values_read": predecision_price_values_read,
        "post_decision_price_or_return_values_read": False,
        "outcome_fields_read": [],
        "price_read_contract": (
            "daily_bars WHERE ticker=? AND trade_date<=declaration_date, "
            "descending LIMIT 20; no later row or forward horizon is read"
        ),
        "forward_horizon_read": False,
        "pit_tier": "research_pit",
        "evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "paper_enabled": False,
        "live_enabled": False,
        "trade_enabled": False,
        "production_impact": "none",
        "next_machine_action": next_action,
        "synthesis_pass": synthesis_pass,
    }


def audit_dividends(
    conn: sqlite3.Connection,
    *,
    start: str = DEFAULT_DIVIDEND_SNAPSHOT_START,
    end: str = DEFAULT_DIVIDEND_SNAPSHOT_END,
    min_touches_per_window: int = 5,
) -> dict[str, Any]:
    return audit_dividend_readiness(
        conn,
        start=start,
        end=end,
        min_touches_per_window=min_touches_per_window,
    )


def _checkpoint_complete(conn: sqlite3.Connection, key: str) -> bool:
    row = conn.execute(
        "SELECT status FROM fetch_checkpoint WHERE checkpoint_key=?", (key,)
    ).fetchone()
    return bool(row and row[0] == "complete")


def iter_weekdays(start: str, end: str) -> Iterable[str]:
    current = dt.date.fromisoformat(_validate_session_date(start))
    final = dt.date.fromisoformat(_validate_session_date(end))
    if current > final:
        raise MassiveError("Backfill start must not be after end")
    while current <= final:
        if current.weekday() < 5:
            yield current.isoformat()
        current += dt.timedelta(days=1)


def backfill_grouped_days(
    conn: sqlite3.Connection,
    client: MassiveClient,
    *,
    start: str,
    end: str,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    attempted = fetched_count = skipped = rows = 0
    for session_date in iter_weekdays(start, end):
        attempted += 1
        if _checkpoint_complete(conn, f"grouped:{session_date}"):
            skipped += 1
            event = {"date": session_date, "status": "skipped_complete", "row_count": 0}
        else:
            result = ingest_grouped_day(conn, client, session_date)
            fetched_count += 1
            rows += int(result["row_count"])
            event = {"date": session_date, "status": "fetched", "row_count": result["row_count"]}
        if progress is not None:
            progress(event)
    return {
        "start": _validate_session_date(start),
        "end": _validate_session_date(end),
        "weekdays_considered": attempted,
        "dates_fetched": fetched_count,
        "dates_skipped": skipped,
        "rows_fetched": rows,
        "status": "complete",
    }


DEFAULT_CATCHUP_MAX_SESSIONS = 15


def missing_grouped_sessions(
    conn: sqlite3.Connection, latest_completed_session: str
) -> list[str]:
    """Weekday dates in (max(daily_bars.trade_date), latest_completed_session].

    Pure data-calendar arithmetic: the upper bound must be a completed US
    equity session supplied by the caller (never a process wall-clock date).
    An empty ``daily_bars`` table returns an empty list — incremental catch-up
    is not a bootstrap tool and the caller must fail closed on that case.
    """

    end = _validate_session_date(latest_completed_session)
    row = conn.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()
    bars_max = row[0] if row else None
    if bars_max is None:
        return []
    start = (dt.date.fromisoformat(str(bars_max)) + dt.timedelta(days=1)).isoformat()
    if start > end:
        return []
    return list(iter_weekdays(start, end))


def run_incremental_grouped_catchup(
    *,
    as_of: dt.datetime | None = None,
    db: str | Path = DEFAULT_DATABASE,
    api_key_file: str | Path | None = None,
    max_sessions: int = DEFAULT_CATCHUP_MAX_SESSIONS,
    conn: sqlite3.Connection | None = None,
    client: MassiveClient | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Bounded, idempotent grouped-daily catch-up to the latest completed session.

    exp-20260805-004: the dividend-restart forward settlement chain silently
    starved for 12 days because nothing advanced ``daily_bars`` in the daily
    run. This entrypoint is wired ahead of the observer/settlement consumers:

    - freshness is anchored to the US-equity data calendar
      (``latest_completed_us_equity_session``), never the process date;
    - already-fresh warehouses return without loading a credential or
      touching the network;
    - at most ``max_sessions`` missing sessions are fetched per run
      (oldest first, so repeated runs converge) and completed checkpoints
      are skipped, keeping reruns idempotent;
    - failures never raise: the summary carries a non-ok status with
      ``alert`` true, and the downstream settlement staleness check keeps
      the gap visible until it is actually closed.
    """

    try:
        from us_market_calendar import latest_completed_us_equity_session
    except ImportError:  # pragma: no cover - package-style imports for tooling
        from quant.us_market_calendar import latest_completed_us_equity_session

    if max_sessions < 1:
        raise MassiveError("max_sessions must be at least 1")
    moment = dt.datetime.now(dt.timezone.utc) if as_of is None else as_of
    latest_completed = latest_completed_us_equity_session(moment).isoformat()

    summary: dict[str, Any] = {
        "scope": "massive_ohlcv_incremental_grouped_catchup",
        "source_experiment": "exp-20260805-004",
        "latest_completed_session": latest_completed,
        "max_sessions": max_sessions,
        "dates_fetched": 0,
        "dates_skipped": 0,
        "rows_fetched": 0,
        "remaining_missing_weekdays": 0,
        "alert": False,
        "error": None,
    }

    own_conn = conn is None
    if own_conn:
        try:
            conn = connect_database(db)
        except (sqlite3.Error, OSError) as exc:
            summary.update(
                {
                    "status": "error",
                    "reason": "warehouse_unavailable",
                    "alert": True,
                    "error": str(exc),
                }
            )
            return summary
    assert conn is not None
    try:
        row = conn.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()
        bars_max_before = row[0] if row else None
        summary["bars_max_trade_date_before"] = bars_max_before
        if bars_max_before is None:
            # Required input absent: fail closed instead of silently treating
            # an empty warehouse as "nothing to do" (AGENTS.md section 6).
            summary.update(
                {
                    "status": "blocked_empty_daily_bars",
                    "reason": "daily_bars_empty_catchup_is_not_bootstrap",
                    "alert": True,
                    "bars_max_trade_date_after": None,
                }
            )
            return summary
        missing = missing_grouped_sessions(conn, latest_completed)
        if not missing:
            summary.update(
                {
                    "status": "fresh",
                    "reason": None,
                    "bars_max_trade_date_after": bars_max_before,
                }
            )
            return summary
        bounded = missing[:max_sessions]
        summary["remaining_missing_weekdays"] = len(missing) - len(bounded)
        try:
            if client is None:
                client = MassiveClient(load_api_key(api_key_file))
            result = backfill_grouped_days(
                conn,
                client,
                start=bounded[0],
                end=bounded[-1],
                progress=progress,
            )
        except MassiveError as exc:
            summary.update(
                {"status": "error", "reason": "catchup_fetch_failed", "alert": True, "error": str(exc)}
            )
        else:
            summary.update(
                {
                    "status": "complete",
                    "reason": None,
                    "dates_fetched": int(result["dates_fetched"]),
                    "dates_skipped": int(result["dates_skipped"]),
                    "rows_fetched": int(result["rows_fetched"]),
                }
            )
        row = conn.execute("SELECT MAX(trade_date) FROM daily_bars").fetchone()
        summary["bars_max_trade_date_after"] = row[0] if row else None
        return summary
    finally:
        if own_conn:
            conn.close()


def _logical_table_hash(
    conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()
) -> str:
    digest = hashlib.sha256()
    for row in conn.execute(query, params):
        digest.update(_canonical_json_bytes(list(row)))
        digest.update(b"\n")
    return digest.hexdigest()


def build_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build one internally consistent manifest while ingestion may continue.

    Individual ``SELECT`` statements are otherwise free to observe different
    WAL commits.  A SQLite backup gives the manifest a single point-in-time
    view without pausing the resumable writer for the duration of hashing.
    """

    snapshot = sqlite3.connect(":memory:")
    try:
        conn.backup(snapshot)
        return _build_summary_snapshot(snapshot)
    finally:
        snapshot.close()


def _build_summary_snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        "SELECT COUNT(*),COUNT(DISTINCT ticker),MIN(trade_date),MAX(trade_date) FROM daily_bars"
    ).fetchone()
    row_count, ticker_count, min_date, max_date = row
    reference = conn.execute(
        "SELECT COUNT(*),SUM(CASE WHEN active=1 THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN active=0 THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN delisted_utc IS NOT NULL THEN 1 ELSE 0 END) "
        "FROM instrument_master"
    ).fetchone()
    split_summary = conn.execute(
        "SELECT COUNT(*),COUNT(DISTINCT ticker),MIN(execution_date),MAX(execution_date),"
        "COUNT(DISTINCT snapshot_key) FROM stock_splits"
    ).fetchone()
    dividend_summary = conn.execute(
        "SELECT COUNT(*),COUNT(DISTINCT ticker),MIN(declaration_date),"
        "MAX(declaration_date),COUNT(DISTINCT snapshot_key),"
        "SUM(CASE WHEN provider_id IS NULL THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN ex_dividend_date IS NULL THEN 1 ELSE 0 END) "
        "FROM stock_dividends"
    ).fetchone()
    split_type_counts = {
        str(adjustment_type): int(count)
        for adjustment_type, count in conn.execute(
            "SELECT adjustment_type,COUNT(*) FROM stock_splits "
            "GROUP BY adjustment_type ORDER BY adjustment_type"
        )
    }
    raw_rows = conn.execute(
        "SELECT request_key,response_sha256,raw_gzip FROM raw_responses ORDER BY request_key"
    ).fetchall()
    raw_ok = True
    raw_digest = hashlib.sha256()
    for request_key, expected_hash, raw_gzip in raw_rows:
        try:
            raw = gzip.decompress(bytes(raw_gzip))
        except (OSError, EOFError):
            raw_ok = False
            raw = b""
        actual = _sha256_bytes(raw)
        raw_ok = raw_ok and actual == expected_hash
        raw_digest.update(_canonical_json_bytes([request_key, expected_hash]))
        raw_digest.update(b"\n")
    checkpoint = conn.execute(
        "SELECT COUNT(*),SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) "
        "FROM fetch_checkpoint"
    ).fetchone()
    samples = {
        ticker: bool(
            conn.execute(
                "SELECT 1 FROM instrument_master WHERE ticker=? LIMIT 1", (ticker,)
            ).fetchone()
        )
        for ticker in ("ANSS", "DFS", "HES")
    }
    normalization_readiness = audit_normalization_readiness(conn)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "source": "massive_full_market_ohlcv",
        "pit_tier": "research_pit",
        "evidence_grade": "lead",
        "known_future_leakage": False,
        "research_pit_basis": (
            "unadjusted date-native grouped daily rows; exact response bytes are "
            "retrieval-time hash-bound; immutable historical vendor vintages remain unverified"
        ),
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "trade_enabled": False,
        "adjusted": False,
        "credential_persisted": False,
        "production_impact": "none",
        "row_count": int(row_count or 0),
        "distinct_ticker_count": int(ticker_count or 0),
        "min_date": min_date,
        "max_date": max_date,
        "reference_row_count": int(reference[0] or 0),
        "active_reference_rows": int(reference[1] or 0),
        "inactive_reference_rows": int(reference[2] or 0),
        "delisted_reference_rows": int(reference[3] or 0),
        "later_disappeared_samples_present": samples,
        "stock_split_row_count": int(split_summary[0] or 0),
        "stock_split_ticker_count": int(split_summary[1] or 0),
        "stock_split_min_execution_date": split_summary[2],
        "stock_split_max_execution_date": split_summary[3],
        "stock_split_snapshot_count": int(split_summary[4] or 0),
        "stock_split_type_counts": split_type_counts,
        "stock_dividend_row_count": int(dividend_summary[0] or 0),
        "stock_dividend_ticker_count": int(dividend_summary[1] or 0),
        "stock_dividend_min_declaration_date": dividend_summary[2],
        "stock_dividend_max_declaration_date": dividend_summary[3],
        "stock_dividend_snapshot_count": int(dividend_summary[4] or 0),
        "stock_dividend_missing_provider_id_count": int(dividend_summary[5] or 0),
        "stock_dividend_missing_ex_date_count": int(dividend_summary[6] or 0),
        "split_factor_contract": "product(split_from/split_to)",
        "historical_adjustment_factor_used": False,
        "normalization_readiness": normalization_readiness,
        "raw_response_count": len(raw_rows),
        "raw_hash_verification_passed": bool(raw_ok),
        "raw_response_logical_sha256": raw_digest.hexdigest(),
        "daily_bars_logical_sha256": _logical_table_hash(
            conn,
            "SELECT ticker,trade_date,open,high,low,close,volume,vwap,transactions,"
            "source_timestamp_ms FROM daily_bars ORDER BY trade_date,ticker",
        ),
        "instrument_master_logical_sha256": _logical_table_hash(
            conn,
            "SELECT snapshot_key,identity_key,ticker,active,list_date,delisted_utc,"
            "composite_figi,share_class_figi,cik FROM instrument_master "
            "ORDER BY snapshot_key,identity_key",
        ),
        "stock_splits_logical_sha256": _logical_table_hash(
            conn,
            "SELECT snapshot_key,split_key,event_identity_key,provider_id,ticker,"
            "execution_date,adjustment_type,split_from,split_to,request_key "
            "FROM stock_splits ORDER BY snapshot_key,execution_date,ticker,split_key",
        ),
        "stock_split_pages_logical_sha256": _logical_table_hash(
            conn,
            "SELECT snapshot_key,page_number,request_key,sanitized_url,"
            "response_sha256,next_url,row_count FROM stock_split_pages "
            "ORDER BY snapshot_key,page_number",
        ),
        "stock_dividends_logical_sha256": _logical_table_hash(
            conn,
            "SELECT snapshot_key,row_identity_key,provider_id,ticker,"
            "declaration_date,ex_dividend_date,cash_amount,currency,request_key "
            "FROM stock_dividends ORDER BY snapshot_key,row_identity_key",
        ),
        "stock_dividend_pages_logical_sha256": _logical_table_hash(
            conn,
            "SELECT snapshot_key,page_number,request_key,sanitized_url,"
            "response_sha256,next_url,row_count FROM stock_dividend_pages "
            "ORDER BY snapshot_key,page_number",
        ),
        "checkpoint_count": int(checkpoint[0] or 0),
        "complete_checkpoint_count": int(checkpoint[1] or 0),
        "limitations": [
            "accessible history begins 2024-07-29",
            "immutable/as-published vendor vintages are unverified",
            "current reference snapshots are not effective-dated identity evidence",
            "replay remains parked until normalization_readiness.replay_ready is true",
            "current active/inactive facts are coverage metadata, not decision-time ranking inputs",
        ],
    }


def write_summary_atomic(path: str | Path, summary: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, destination)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _json_print(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _build_client(args: argparse.Namespace) -> MassiveClient:
    return MassiveClient(
        load_api_key(args.api_key_file),
        min_interval_seconds=args.min_interval_seconds,
        max_attempts=args.max_attempts,
        timeout_seconds=args.timeout_seconds,
    )


def _parse_reference_asof_dates_text(value: str) -> list[str]:
    text = str(value).strip()
    if not text:
        raise MassiveError("Reference as-of date input is empty")
    if text.startswith("["):
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MassiveError("Reference as-of dates file is not valid JSON") from exc
        if not isinstance(decoded, list) or not all(
            isinstance(item, str) for item in decoded
        ):
            raise MassiveError("Reference as-of JSON input must be a string list")
        return _normalise_reference_asof_dates(decoded)
    tokens: list[str] = []
    for line in text.splitlines():
        content = line.split("#", 1)[0]
        tokens.extend(item.strip() for item in content.split(",") if item.strip())
    return _normalise_reference_asof_dates(tokens)


def _reference_asof_dates_from_args(
    args: argparse.Namespace,
    *,
    default: Iterable[str] | None = None,
) -> list[str]:
    single = getattr(args, "date", None)
    csv_dates = getattr(args, "dates", None)
    dates_file = getattr(args, "dates_file", None)
    if single:
        return _normalise_reference_asof_dates([str(single)])
    if csv_dates:
        return _parse_reference_asof_dates_text(str(csv_dates))
    if dates_file:
        path = Path(str(dates_file))
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise MassiveError(
                f"Reference as-of dates file is unavailable: {path}"
            ) from exc
        return _parse_reference_asof_dates_text(content)
    if default is not None:
        return _normalise_reference_asof_dates(default)
    raise MassiveError("A reference as-of date input is required")


def _add_reference_date_arguments(
    parser: argparse.ArgumentParser,
    *,
    required: bool,
) -> None:
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument("--date", help="one fixed ISO as-of date")
    group.add_argument("--dates", help="comma-separated fixed ISO as-of dates")
    group.add_argument(
        "--dates-file",
        help="UTF-8 comma/newline or JSON string-list file of fixed dates",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DATABASE))
    parser.add_argument("--api-key-file", default=str(DEFAULT_KEY_FILE))
    parser.add_argument(
        "--min-interval-seconds", type=float, default=DEFAULT_MIN_INTERVAL_SECONDS
    )
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--date", required=True)

    reference = subparsers.add_parser("sync-reference")
    reference.add_argument("--active", choices=("true", "false", "all"), default="all")

    reference_asof = subparsers.add_parser("sync-reference-asof")
    _add_reference_date_arguments(reference_asof, required=True)
    reference_asof.add_argument(
        "--max-pages", type=int, default=DEFAULT_MAX_REFERENCE_PAGES
    )

    splits = subparsers.add_parser("sync-splits")
    splits.add_argument("--start", default=DEFAULT_SPLIT_SNAPSHOT_START)
    splits.add_argument("--end", default=DEFAULT_SPLIT_SNAPSHOT_END)
    splits.add_argument("--max-pages", type=int, default=DEFAULT_MAX_SPLIT_PAGES)

    dividends = subparsers.add_parser("sync-dividends")
    dividends.add_argument("--start", default=DEFAULT_DIVIDEND_SNAPSHOT_START)
    dividends.add_argument("--end", default=DEFAULT_DIVIDEND_SNAPSHOT_END)
    dividends.add_argument("--max-pages", type=int, default=DEFAULT_MAX_DIVIDEND_PAGES)

    backfill = subparsers.add_parser("backfill")
    backfill.add_argument("--start", required=True)
    backfill.add_argument("--end", required=True)
    backfill.add_argument("--progress-every", type=int, default=5)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--output")

    audit = subparsers.add_parser("audit-normalization")
    audit.add_argument("--start", default=DEFAULT_SPLIT_SNAPSHOT_START)
    audit.add_argument("--end", default=DEFAULT_SPLIT_SNAPSHOT_END)
    audit.add_argument("--as-of")
    audit.add_argument("--output")

    dividend_audit = subparsers.add_parser("audit-dividends")
    dividend_audit.add_argument("--start", default=DEFAULT_DIVIDEND_SNAPSHOT_START)
    dividend_audit.add_argument("--end", default=DEFAULT_DIVIDEND_SNAPSHOT_END)
    dividend_audit.add_argument("--min-touches-per-window", type=int, default=5)
    dividend_audit.add_argument("--output")

    identity_audit = subparsers.add_parser(
        "audit-reference-asof", aliases=("audit-asof-identity",)
    )
    _add_reference_date_arguments(identity_audit, required=False)
    identity_audit.add_argument(
        "--min-rows-per-date",
        type=int,
        default=DEFAULT_MIN_REFERENCE_ASOF_ROWS,
    )
    identity_audit.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conn = connect_database(args.db)
    try:
        if args.command == "preflight":
            result = ingest_grouped_day(conn, _build_client(args), args.date)
        elif args.command == "sync-reference":
            client = _build_client(args)
            modes = (True, False) if args.active == "all" else (args.active == "true",)
            parts = [sync_reference(conn, client, active=value) for value in modes]
            result = {
                "status": "complete",
                "parts": parts,
                "row_count": sum(int(part["row_count"]) for part in parts),
                "pages": sum(int(part["pages"]) for part in parts),
            }
        elif args.command == "sync-reference-asof":
            result = sync_reference_asof_dates(
                conn,
                _build_client(args),
                _reference_asof_dates_from_args(args),
                max_pages=args.max_pages,
            )
        elif args.command == "sync-splits":
            result = sync_splits(
                conn,
                _build_client(args),
                start=args.start,
                end=args.end,
                max_pages=args.max_pages,
            )
        elif args.command == "sync-dividends":
            result = sync_dividends(
                conn,
                _build_client(args),
                start=args.start,
                end=args.end,
                max_pages=args.max_pages,
            )
        elif args.command == "backfill":
            progress_every = max(1, int(args.progress_every))
            seen = 0

            def emit(event: dict[str, Any]) -> None:
                nonlocal seen
                seen += 1
                if seen % progress_every == 0:
                    _json_print({"progress": seen, **event})

            result = backfill_grouped_days(
                conn,
                _build_client(args),
                start=args.start,
                end=args.end,
                progress=emit,
            )
        elif args.command == "summary":
            result = build_summary(conn)
            if args.output:
                write_summary_atomic(args.output, result)
        elif args.command == "audit-normalization":
            result = audit_normalization_readiness(
                conn,
                snapshot_start=args.start,
                snapshot_end=args.end,
                as_of=args.as_of,
            )
            if args.output:
                write_summary_atomic(args.output, result)
        elif args.command == "audit-dividends":
            result = audit_dividend_readiness(
                conn,
                start=args.start,
                end=args.end,
                min_touches_per_window=args.min_touches_per_window,
            )
            if args.output:
                write_summary_atomic(args.output, result)
        elif args.command in {"audit-reference-asof", "audit-asof-identity"}:
            result = audit_reference_asof_readiness(
                conn,
                expected_dates=_reference_asof_dates_from_args(
                    args, default=DEFAULT_REFERENCE_ASOF_DATES
                ),
                min_rows_per_date=args.min_rows_per_date,
            )
            if args.output:
                write_summary_atomic(args.output, result)
        else:  # pragma: no cover
            raise MassiveError(f"Unsupported command: {args.command}")
        _json_print(result)
        if args.command in {
            "audit-normalization",
            "audit-reference-asof",
            "audit-asof-identity",
            "audit-dividends",
        } and result["status"] == "parked":
            return 3
        if args.command == "audit-dividends" and result["status"] == "blocked":
            return 3
        return 0
    except MassiveError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
