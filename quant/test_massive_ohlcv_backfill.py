from __future__ import annotations

import gzip
import hashlib
import io
import json
import sqlite3
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import pytest

from quant import massive_ohlcv_backfill as massive


SECRET = "unit-test-massive-key-never-persist"
DAY = "2025-01-02"


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _millis(day: str) -> int:
    value = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _bar(
    ticker: str = "AAPL",
    *,
    day: str = DAY,
    open_: float = 100.0,
    high: float = 103.0,
    low: float = 99.0,
    close: float = 102.0,
    volume: float = 1_000_000.0,
) -> dict[str, Any]:
    return {
        "T": ticker,
        "o": open_,
        "h": high,
        "l": low,
        "c": close,
        "v": volume,
        "vw": 101.25,
        "n": 1000,
        "t": _millis(day),
    }


def _grouped_payload(
    rows: Iterable[dict[str, Any]] | None = None,
    *,
    adjusted: bool = False,
) -> dict[str, Any]:
    values = list(rows if rows is not None else [_bar()])
    return {
        "adjusted": adjusted,
        "queryCount": len(values),
        "resultsCount": len(values),
        "status": "OK",
        "results": values,
    }


def _reference_row(
    ticker: str,
    *,
    active: bool,
    delisted_utc: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticker": ticker,
        "name": f"{ticker} Incorporated",
        "market": "stocks",
        "locale": "us",
        "primary_exchange": "XNAS",
        "type": "CS",
        "active": active,
        "currency_name": "usd",
        "last_updated_utc": "2026-07-27T00:00:00Z",
    }
    if delisted_utc is not None:
        row["delisted_utc"] = delisted_utc
    return row


def _split_row(
    ticker: str = "AAPL",
    *,
    execution_date: str = "2025-01-10",
    adjustment_type: str = "forward_split",
    split_from: float = 1.0,
    split_to: float = 4.0,
    provider_id: str | None = "split-1",
    historical_adjustment_factor: float = 123456.0,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticker": ticker,
        "execution_date": execution_date,
        "adjustment_type": adjustment_type,
        "split_from": split_from,
        "split_to": split_to,
        "historical_adjustment_factor": historical_adjustment_factor,
    }
    if provider_id is not None:
        row["id"] = provider_id
    return row


def _dividend_row(
    ticker: str = "AAPL",
    *,
    declaration_date: str = "2025-01-02",
    ex_dividend_date: str | None = "2025-01-15",
    cash_amount: Any = "1.25",
    currency: str = "USD",
    provider_id: str | None = "dividend-1",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticker": ticker,
        "declaration_date": declaration_date,
        "cash_amount": cash_amount,
        "currency": currency,
        "distribution_type": "CD",
        "frequency": 4,
        "split_adjusted_cash_amount": 999.0,
        "historical_adjustment_factor": 123.0,
    }
    if ex_dividend_date is not None:
        row["ex_dividend_date"] = ex_dividend_date
    if provider_id is not None:
        row["id"] = provider_id
    return row


class _Response:
    def __init__(
        self,
        raw: bytes,
        *,
        url: str,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._raw = raw
        self._url = url
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, *_args: object, **_kwargs: object) -> bytes:
        return self._raw

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url


class _QueueOpener:
    def __init__(self, responses: Iterable[bytes | dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, **kwargs: Any) -> _Response:
        url = getattr(request, "full_url", str(request))
        headers = dict(getattr(request, "header_items", lambda: [])())
        self.calls.append({"url": url, "headers": headers, **kwargs})
        if not self._responses:
            raise AssertionError(f"unexpected request: {url}")
        value = self._responses.pop(0)
        raw = value if isinstance(value, bytes) else _json_bytes(value)
        return _Response(raw, url=url)


class _RepeatingOpener(_QueueOpener):
    def __init__(self, response: bytes | dict[str, Any]) -> None:
        super().__init__(())
        self._response = response

    def __call__(self, request: Any, **kwargs: Any) -> _Response:
        url = getattr(request, "full_url", str(request))
        headers = dict(getattr(request, "header_items", lambda: [])())
        self.calls.append({"url": url, "headers": headers, **kwargs})
        raw = (
            self._response
            if isinstance(self._response, bytes)
            else _json_bytes(self._response)
        )
        return _Response(raw, url=url)


def _client(opener: Any, **kwargs: Any) -> Any:
    return massive.MassiveClient(
        SECRET,
        opener=opener,
        sleep=lambda _seconds: None,
        min_interval_seconds=0,
        **kwargs,
    )


def _user_tables(conn: sqlite3.Connection) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    names = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for (name,) in names:
        quoted = str(name).replace('"', '""')
        columns = conn.execute(f'PRAGMA table_info("{quoted}")').fetchall()
        result[str(name)] = {str(row[1]) for row in columns}
    return result


def _find_table(conn: sqlite3.Connection, required: set[str]) -> str:
    matches = [
        name
        for name, columns in _user_tables(conn).items()
        if required <= columns
    ]
    assert len(matches) == 1, (required, _user_tables(conn))
    return matches[0]


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {_quoted(table)}").fetchone()[0])


def _all_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {name: _count(conn, name) for name in _user_tables(conn)}


def _raw_record(conn: sqlite3.Connection) -> tuple[bytes, str]:
    raw_table = _find_table(conn, {"response_sha256", "raw_gzip"})
    columns = _user_tables(conn)[raw_table]
    blob_candidates = [
        name
        for name in columns
        if "raw" in name.casefold() or "body" in name.casefold()
    ]
    assert blob_candidates, columns
    for blob_column in sorted(blob_candidates):
        row = conn.execute(
            f"SELECT {_quoted(blob_column)}, response_sha256 "
            f"FROM {_quoted(raw_table)} LIMIT 1"
        ).fetchone()
        if row and isinstance(row[0], (bytes, bytearray, memoryview)):
            return bytes(row[0]), str(row[1])
    raise AssertionError(f"no raw response BLOB in {raw_table}: {columns}")


def _decode_stored_raw(value: bytes) -> bytes:
    return gzip.decompress(value) if value.startswith(b"\x1f\x8b") else value


def _assert_secret_absent_from_sqlite_family(db_path: Path) -> None:
    for path in db_path.parent.glob(f"{db_path.name}*"):
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes(), path


def test_load_api_key_uses_explicit_environment_then_gitignored_file(
    tmp_path: Path,
) -> None:
    secret_file = tmp_path / "massive.txt"
    secret_file.write_text("file-key\n", encoding="utf-8")

    assert massive.load_api_key(path=secret_file, environ={}) == "file-key"
    assert (
        massive.load_api_key(
            path=secret_file,
            environ={"MASSIVE_API_KEY": "environment-key"},
        )
        == "environment-key"
    )


def test_client_uses_auth_header_and_never_places_key_in_url_or_repr() -> None:
    raw = _json_bytes({"status": "OK", "results": []})
    opener = _QueueOpener([raw])

    fetched = _client(opener).get_json(
        "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/2025-01-02"
        "?adjusted=false"
    )

    assert fetched.raw_bytes == raw
    assert fetched.sha256 == hashlib.sha256(raw).hexdigest()
    assert fetched.payload == {"status": "OK", "results": []}
    assert SECRET not in opener.calls[0]["url"]
    assert SECRET not in fetched.url
    assert SECRET not in repr(fetched)
    assert any(
        SECRET in str(value) for value in opener.calls[0]["headers"].values()
    )


def test_pagination_rejects_non_allowlisted_host_before_second_request(
    tmp_path: Path,
) -> None:
    first = {
        "status": "OK",
        "results": [_reference_row("AAPL", active=True)],
        "next_url": "https://attacker.invalid/v3/reference/tickers?cursor=stolen",
    }
    opener = _QueueOpener([first])
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        with pytest.raises(Exception) as caught:
            massive.sync_reference(conn, _client(opener), active=True)
        assert len(opener.calls) == 1
        assert "attacker.invalid" in str(caught.value)
        assert SECRET not in str(caught.value)
    finally:
        conn.close()


def test_client_429_retry_after_is_capped_and_attempts_are_bounded() -> None:
    calls: list[str] = []
    sleeps: list[float] = []

    def always_rate_limited(request: Any, **_kwargs: Any) -> None:
        url = getattr(request, "full_url", str(request))
        calls.append(url)
        raise urllib.error.HTTPError(
            url,
            429,
            "rate limited",
            {"Retry-After": "999999"},
            io.BytesIO(b'{"error":"slow down"}'),
        )

    client = massive.MassiveClient(
        SECRET,
        opener=always_rate_limited,
        sleep=sleeps.append,
        max_attempts=3,
        min_interval_seconds=0,
    )
    with pytest.raises(Exception) as caught:
        client.get_json(
            "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/"
            "2025-01-02?adjusted=false"
        )

    assert len(calls) == 3
    assert len(sleeps) == 2
    assert all(0.0 <= value <= 60.0 for value in sleeps)
    assert SECRET not in str(caught.value)
    assert all(SECRET not in url for url in calls)


def test_grouped_day_persists_valid_unadjusted_bar_and_exact_raw(
    tmp_path: Path,
) -> None:
    raw = _json_bytes(_grouped_payload())
    opener = _QueueOpener([raw])
    db_path = tmp_path / "massive.sqlite"
    conn = massive.connect_database(db_path)
    try:
        result = massive.ingest_grouped_day(conn, _client(opener), DAY)

        assert result["date"] == DAY
        assert result["adjusted"] is False
        assert result["row_count"] == 1
        assert "adjusted=false" in opener.calls[0]["url"].casefold()
        bars_table = _find_table(
            conn,
            {"ticker", "trade_date", "open", "high", "low", "close", "volume"},
        )
        row = conn.execute(
            f"SELECT ticker, trade_date, open, high, low, close, volume "
            f"FROM {_quoted(bars_table)}"
        ).fetchone()
        assert row == ("AAPL", DAY, 100.0, 103.0, 99.0, 102.0, 1_000_000.0)

        stored, stored_hash = _raw_record(conn)
        assert _decode_stored_raw(stored) == raw
        assert stored_hash == hashlib.sha256(raw).hexdigest()
        _assert_secret_absent_from_sqlite_family(db_path)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "bad_bar",
    [
        _bar(high=101.0, close=102.0),
        _bar(low=101.0, open_=100.0),
        _bar(volume=-1.0),
        _bar(day="2025-01-03"),
        {**_bar(), "c": "NaN"},
    ],
    ids=["high_below_close", "low_above_open", "negative_volume", "wrong_day", "nan"],
)
def test_grouped_day_rejects_invalid_bar_without_partial_persistence(
    tmp_path: Path,
    bad_bar: dict[str, Any],
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception):
            massive.ingest_grouped_day(
                conn,
                _client(_QueueOpener([_grouped_payload([bad_bar])])),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_same_bar_key_with_different_values_is_a_conflict(tmp_path: Path) -> None:
    payload = _grouped_payload([_bar(close=102.0), _bar(close=101.0)])
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception, match="(?i)conflict|duplicate"):
            massive.ingest_grouped_day(
                conn,
                _client(_QueueOpener([payload])),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_grouped_day_is_idempotent_for_identical_response(tmp_path: Path) -> None:
    raw = _json_bytes(_grouped_payload())
    opener = _RepeatingOpener(raw)
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        first = massive.ingest_grouped_day(conn, _client(opener), DAY)
        counts_after_first = _all_counts(conn)
        second = massive.ingest_grouped_day(conn, _client(opener), DAY)

        assert _all_counts(conn) == counts_after_first
        assert first["row_count"] == second["row_count"] == 1
        bars_table = _find_table(
            conn,
            {"ticker", "trade_date", "open", "high", "low", "close", "volume"},
        )
        assert _count(conn, bars_table) == 1
    finally:
        conn.close()


def test_backfill_resume_skips_complete_checkpoint_without_network(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        first = massive.backfill_grouped_days(
            conn,
            _client(_QueueOpener([_grouped_payload()])),
            start=DAY,
            end=DAY,
        )
        no_calls = _QueueOpener([])
        resumed = massive.backfill_grouped_days(
            conn,
            _client(no_calls),
            start=DAY,
            end=DAY,
        )

        assert first["dates_fetched"] == 1
        assert first["dates_skipped"] == 0
        assert resumed["dates_fetched"] == 0
        assert resumed["dates_skipped"] == 1
        assert no_calls.calls == []
    finally:
        conn.close()


def test_refetch_with_different_frozen_bytes_rejects_and_preserves_first(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    first_raw = _json_bytes(_grouped_payload([_bar(close=102.0)]))
    changed_raw = _json_bytes(_grouped_payload([_bar(close=101.0)]))
    try:
        massive.ingest_grouped_day(conn, _client(_QueueOpener([first_raw])), DAY)
        before = _all_counts(conn)
        with pytest.raises(Exception, match="(?i)conflict"):
            massive.ingest_grouped_day(
                conn,
                _client(_QueueOpener([changed_raw])),
                DAY,
            )

        assert _all_counts(conn) == before
        stored, stored_hash = _raw_record(conn)
        assert _decode_stored_raw(stored) == first_raw
        assert stored_hash == hashlib.sha256(first_raw).hexdigest()
    finally:
        conn.close()


def test_raw_rows_and_checkpoint_roll_back_as_one_transaction(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    massive.ensure_schema(conn)
    before = _all_counts(conn)
    conn.execute(
        "CREATE TRIGGER fail_checkpoint_insert BEFORE INSERT ON fetch_checkpoint "
        "BEGIN SELECT RAISE(ABORT, 'injected checkpoint failure'); END"
    )
    conn.commit()
    try:
        with pytest.raises(sqlite3.DatabaseError, match="injected checkpoint failure"):
            massive.ingest_grouped_day(
                conn,
                _client(_QueueOpener([_grouped_payload()])),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_response_that_echoes_key_is_rejected_before_database_write(
    tmp_path: Path,
) -> None:
    payload = {**_grouped_payload(), "debug_api_key": SECRET}
    db_path = tmp_path / "massive.sqlite"
    conn = massive.connect_database(db_path)
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception) as caught:
            massive.ingest_grouped_day(
                conn,
                _client(_QueueOpener([payload])),
                DAY,
            )
        assert SECRET not in str(caught.value)
        assert _all_counts(conn) == before
    finally:
        conn.close()
    _assert_secret_absent_from_sqlite_family(db_path)


def test_reference_sync_keeps_active_and_inactive_delisted_rows(
    tmp_path: Path,
) -> None:
    active_page_1 = {
        "status": "OK",
        "results": [_reference_row("AAPL", active=True)],
        "next_url": "https://api.massive.com/v3/reference/tickers?active=true&cursor=two",
    }
    active_page_2 = {
        "status": "OK",
        "results": [_reference_row("MSFT", active=True)],
    }
    inactive_page = {
        "status": "OK",
        "results": [
            _reference_row(
                "ANSS",
                active=False,
                delisted_utc="2025-03-21T00:00:00Z",
            )
        ],
    }
    opener = _QueueOpener([active_page_1, active_page_2, inactive_page])
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        active = massive.sync_reference(conn, _client(opener), active=True)
        inactive = massive.sync_reference(conn, _client(opener), active=False)

        assert active["row_count"] == 2
        assert inactive["row_count"] == 1
        reference_table = _find_table(conn, {"ticker", "active", "delisted_utc"})
        rows = conn.execute(
            f"SELECT ticker, active, delisted_utc FROM {_quoted(reference_table)} "
            "ORDER BY ticker"
        ).fetchall()
        assert rows == [
            ("AAPL", 1, None),
            ("ANSS", 0, "2025-03-21T00:00:00Z"),
            ("MSFT", 1, None),
        ]
        assert len(opener.calls) == 3
        assert all(SECRET not in call["url"] for call in opener.calls)
        assert "active=true" in opener.calls[0]["url"].casefold()
        assert "active=false" in opener.calls[2]["url"].casefold()
    finally:
        conn.close()


def test_reference_duplicate_identity_keeps_latest_vendor_revision(
    tmp_path: Path,
) -> None:
    older = _reference_row("AC", active=False, delisted_utc="2025-09-05T00:00:00Z")
    older.update(
        {
            "share_class_figi": "BBG008NZ8QB1",
            "composite_figi": "BBG008NZ8QC0",
            "last_updated_utc": "2025-09-06T06:11:32Z",
        }
    )
    newer = {**older, "last_updated_utc": "2025-09-07T06:04:47Z"}
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        result = massive.sync_reference(
            conn,
            _client(_QueueOpener([{"status": "OK", "results": [older, newer]}])),
            active=False,
        )
        assert result["row_count"] == 1
        assert conn.execute(
            "SELECT ticker,last_updated_utc FROM instrument_master"
        ).fetchall() == [("AC", "2025-09-07T06:04:47Z")]
    finally:
        conn.close()


def test_reference_ticker_reuse_preserves_distinct_provider_identities(
    tmp_path: Path,
) -> None:
    first = _reference_row("REUSE", active=False, delisted_utc="2020-01-01T00:00:00Z")
    first["share_class_figi"] = "BBG000FIRST"
    second = _reference_row("REUSE", active=False, delisted_utc="2025-01-01T00:00:00Z")
    second["share_class_figi"] = "BBG000SECOND"
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        result = massive.sync_reference(
            conn,
            _client(_QueueOpener([{"status": "OK", "results": [first, second]}])),
            active=False,
        )
        assert result["row_count"] == 2
        assert conn.execute(
            "SELECT COUNT(*),COUNT(DISTINCT identity_key) FROM instrument_master "
            "WHERE ticker='REUSE'"
        ).fetchone() == (2, 2)
    finally:
        conn.close()


def test_completed_reference_sync_resumes_without_network(tmp_path: Path) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        first = massive.sync_reference(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_reference_row("AAPL", active=True)]}]
                )
            ),
            active=True,
        )
        no_network = _QueueOpener([])
        second = massive.sync_reference(conn, _client(no_network), active=True)
        assert first["row_count"] == second["row_count"] == 1
        assert second["resumed_without_network"] is True
        assert no_network.calls == []
    finally:
        conn.close()


def test_reference_asof_sync_accepts_cursor_only_pages_and_hash_binds_every_layer(
    tmp_path: Path,
) -> None:
    next_url = "https://api.massive.com/v3/reference/tickers?cursor=opaque-two"
    first_payload = {
        "status": "OK",
        "results": [_reference_row("AAPL", active=True)],
        "next_url": next_url,
    }
    second_payload = {
        "status": "OK",
        "results": [_reference_row("MSFT", active=True)],
    }
    raw_pages = [_json_bytes(first_payload), _json_bytes(second_payload)]
    opener = _QueueOpener(raw_pages)
    db_path = tmp_path / "massive.sqlite"
    conn = massive.connect_database(db_path)
    try:
        result = massive.sync_reference_asof(conn, _client(opener), DAY)
        snapshot_key = massive.reference_asof_snapshot_key(DAY)

        assert result["snapshot_key"] == snapshot_key
        assert result["as_of"] == DAY
        assert result["active"] is True
        assert result["type"] == "CS"
        assert result["row_count"] == 2
        assert result["pages"] == 2
        assert result["status"] == "complete"
        assert "date=2025-01-02" in opener.calls[0]["url"]
        assert "active=true" in opener.calls[0]["url"]
        assert "type=CS" in opener.calls[0]["url"]
        assert opener.calls[1]["url"] == next_url

        rows = conn.execute(
            "SELECT snapshot_key,ticker,active,instrument_type,list_date "
            "FROM instrument_master ORDER BY ticker"
        ).fetchall()
        assert rows == [
            (snapshot_key, "AAPL", 1, "CS", None),
            (snapshot_key, "MSFT", 1, "CS", None),
        ]
        checkpoint = conn.execute(
            "SELECT checkpoint_key,kind,status,row_count,content_sha256 "
            "FROM fetch_checkpoint"
        ).fetchone()
        assert checkpoint[:4] == (snapshot_key, snapshot_key, "complete", 2)
        stored_pages = conn.execute(
            "SELECT p.as_of_date,p.page_number,p.request_key,p.response_sha256,"
            "p.next_url,p.row_count,r.kind,r.raw_gzip "
            "FROM reference_asof_pages p JOIN raw_responses r USING(request_key) "
            "ORDER BY p.page_number"
        ).fetchall()
        assert len(stored_pages) == 2
        assert all(row[0] == DAY and row[6] == snapshot_key for row in stored_pages)
        for expected_raw, stored in zip(raw_pages, stored_pages):
            assert gzip.decompress(bytes(stored[7])) == expected_raw
            assert stored[3] == hashlib.sha256(expected_raw).hexdigest()
        digest_records = [
            (row[1], row[2], row[3], row[4], row[5]) for row in stored_pages
        ]
        assert result["all_pages_sha256"] == massive._reference_asof_pages_digest(
            digest_records
        )
        assert checkpoint[4] == result["all_pages_sha256"]

        counts = _all_counts(conn)
        no_network = _QueueOpener([])
        resumed = massive.sync_reference_asof(conn, _client(no_network), DAY)
        assert resumed["resumed_without_network"] is True
        assert resumed["all_pages_sha256"] == result["all_pages_sha256"]
        assert _all_counts(conn) == counts
        assert no_network.calls == []
        _assert_secret_absent_from_sqlite_family(db_path)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "drifted_next_url",
    [
        "https://api.massive.com/v3/reference/tickers?cursor=x&date=2025-01-03",
        "https://api.massive.com/v3/reference/tickers?cursor=x&active=false",
        "https://api.massive.com/v3/reference/tickers?cursor=x&type=ETF",
    ],
    ids=["date", "active", "type"],
)
def test_reference_asof_rejects_explicit_pagination_contract_drift_before_write(
    tmp_path: Path,
    drifted_next_url: str,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception, match="changed query field"):
            massive.sync_reference_asof(
                conn,
                _client(
                    _QueueOpener(
                        [
                            {
                                "status": "OK",
                                "results": [_reference_row("AAPL", active=True)],
                                "next_url": drifted_next_url,
                            }
                        ]
                    )
                ),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_reference_asof_rejects_two_identities_for_same_ticker_atomically(
    tmp_path: Path,
) -> None:
    first = _reference_row("DUP", active=True)
    first["share_class_figi"] = "BBG000FIRST"
    first["last_updated_utc"] = "2025-01-02T20:00:00Z"
    second = _reference_row("DUP", active=True)
    second["share_class_figi"] = "BBG000SECOND"
    second["last_updated_utc"] = "2025-01-02T20:30:00Z"
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(
            Exception, match="conflicting (listing identity|share_class_figi)"
        ):
            massive.sync_reference_asof(
                conn,
                _client(
                    _QueueOpener(
                        [{"status": "OK", "results": [first, second]}]
                    )
                ),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_reference_asof_collapses_real_fldd_vendor_revision_by_decision_cutoff(
    tmp_path: Path,
) -> None:
    older = _reference_row("FLDD", active=True)
    older.update(
        {
            "name": "FTAC EMERALD ACQ A",
            "composite_figi": "BBG0142PTRC8",
            "share_class_figi": "BBG0142PTS63",
            "last_updated_utc": "2024-12-24T15:12:00Z",
        }
    )
    newer = {
        **older,
        "name": "FTAC EMERALD ACQUISITION CORP CLASS A",
        "cik": "0001889123",
        "last_updated_utc": "2025-08-22T18:35:00Z",
    }
    raw = _json_bytes({"status": "OK", "results": [older, newer]})
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        result = massive.sync_reference_asof(
            conn, _client(_QueueOpener([raw])), DAY
        )
        stored = conn.execute(
            "SELECT ticker,name,cik,last_updated_utc,composite_figi,"
            "share_class_figi,raw_json FROM instrument_master"
        ).fetchone()
        assert stored == (
            "FLDD",
            "FTAC EMERALD ACQ A",
            None,
            "2024-12-24T15:12:00Z",
            "BBG0142PTRC8",
            "BBG0142PTS63",
            massive._canonical_json_bytes(older).decode("utf-8"),
        )
        assert result["raw_result_count"] == 2
        assert result["eligible_revision_count"] == 1
        assert result["future_revision_count"] == 1
        assert result["selected_unique_row_count"] == 1
        assert result["vendor_revision_collapse_count"] == 1
        assert result["vendor_revision_group_count"] == 1
        raw_record = conn.execute(
            "SELECT raw_gzip,row_count FROM raw_responses"
        ).fetchone()
        assert gzip.decompress(bytes(raw_record[0])) == raw
        assert raw_record[1] == 1

        audit = massive.audit_reference_asof_readiness(
            conn, expected_dates=[DAY], min_rows_per_date=1
        )
        assert audit["status"] == "ready"
        assert audit["decision_cutoff_utc_by_date"] == {
            DAY: "2025-01-02T21:00:00Z"
        }
        assert audit["raw_result_counts_by_date"] == {DAY: 2}
        assert audit["eligible_revision_count_by_date"] == {DAY: 1}
        assert audit["future_revision_count_by_date"] == {DAY: 1}
        assert audit["selected_unique_row_count_by_date"] == {DAY: 1}
        assert audit["vendor_revision_collapse_count_by_date"] == {DAY: 1}
        assert audit["dated_endpoint_future_version_anomaly_observed"] is True
        assert audit["candidate_decision_membership_fields"] == [
            "as_of",
            "ticker",
            "type",
            "active",
        ]
        assert audit["measurement_identity_fields"] == [
            "composite_figi",
            "share_class_figi",
        ]
        assert audit["figi_candidate_ranking_filter_allowed"] is False
        assert audit["figi_cross_surface_join_allowed"] is False
        assert audit["future_descriptive_metadata_decision_input"] is False
        assert audit["known_future_leakage"] is False
        assert audit["known_future_leakage_scope"] == (
            "candidate_decision_membership_fields_only"
        )
        assert audit["as_published_vintage_verified"] is False
        assert audit["evidence_grade"] == "lead"
        assert audit["result_ceiling"] == "observed_only"
        assert audit["paper_enabled"] is False
        assert audit["live_enabled"] is False
    finally:
        conn.close()


def test_reference_asof_future_conflicting_figi_injection_cannot_change_selection(
    tmp_path: Path,
) -> None:
    eligible = _reference_row("SAFE", active=True)
    eligible.update(
        {
            "name": "Historical safe identity",
            "composite_figi": "BBG00SAFE001",
            "share_class_figi": "BBG00SAFE002",
            "last_updated_utc": "2025-01-02T20:59:59Z",
        }
    )
    future_conflict = {
        **eligible,
        "name": "Future conflicting description",
        "primary_exchange": "XNYS",
        "list_date": "2026-01-01",
        "composite_figi": "BBG00OTHER01",
        "share_class_figi": "BBG00OTHER02",
        "last_updated_utc": "2025-01-02T21:00:00.000001Z",
    }
    observed: list[tuple[Any, ...]] = []
    readiness: list[dict[str, Any]] = []
    for index, rows in enumerate(([eligible], [eligible, future_conflict])):
        conn = massive.connect_database(tmp_path / f"massive-{index}.sqlite")
        try:
            massive.sync_reference_asof(
                conn,
                _client(_QueueOpener([{"status": "OK", "results": rows}])),
                DAY,
            )
            observed.append(
                tuple(
                    conn.execute(
                        "SELECT identity_key,ticker,name,primary_exchange,list_date,"
                        "last_updated_utc,composite_figi,share_class_figi,raw_json "
                        "FROM instrument_master"
                    ).fetchone()
                )
            )
            readiness.append(
                massive.audit_reference_asof_readiness(
                    conn, expected_dates=[DAY], min_rows_per_date=1
                )
            )
        finally:
            conn.close()

    assert observed[0] == observed[1]
    assert readiness[0]["status"] == readiness[1]["status"] == "ready"
    assert readiness[0]["selected_unique_row_count"] == 1
    assert readiness[1]["selected_unique_row_count"] == 1
    assert readiness[0]["future_revision_count"] == 0
    assert readiness[1]["future_revision_count"] == 1
    assert readiness[1]["vendor_revision_collapse_count"] == 1


def test_reference_asof_future_only_duplicate_group_fails_closed(
    tmp_path: Path,
) -> None:
    first = _reference_row("FUTURE", active=True)
    first.update(
        {
            "composite_figi": "BBG00FUTURE1",
            "share_class_figi": "BBG00FUTURE2",
            "last_updated_utc": "2025-01-02T21:00:00.000001Z",
        }
    )
    second = {
        **first,
        "name": "Future revision two",
        "last_updated_utc": "2025-08-22T00:00:00Z",
    }
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception, match="no row eligible by decision cutoff"):
            massive.sync_reference_asof(
                conn,
                _client(
                    _QueueOpener(
                        [{"status": "OK", "results": [first, second]}]
                    )
                ),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_reference_asof_decision_cutoff_uses_new_york_close_with_dst() -> None:
    assert massive._utc_iso(massive._reference_decision_cutoff_utc(DAY)) == (
        "2025-01-02T21:00:00Z"
    )
    assert massive._utc_iso(
        massive._reference_decision_cutoff_utc("2025-07-01")
    ) == "2025-07-01T20:00:00Z"


def test_reference_asof_duplicate_revision_rejects_naive_update_timestamp(
    tmp_path: Path,
) -> None:
    first = _reference_row("NAIVE", active=True)
    first.update(
        {
            "composite_figi": "BBG00NAIVE01",
            "last_updated_utc": "2025-01-02T20:00:00",
        }
    )
    second = {
        **first,
        "name": "Later revision",
        "last_updated_utc": "2025-01-02T20:30:00Z",
    }
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception, match="lacks timezone"):
            massive.sync_reference_asof(
                conn,
                _client(
                    _QueueOpener(
                        [{"status": "OK", "results": [first, second]}]
                    )
                ),
                DAY,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_reference_asof_eligible_revision_may_add_nonconflicting_share_figi(
    tmp_path: Path,
) -> None:
    first = _reference_row("FIGI", active=True)
    first.update(
        {
            "composite_figi": "BBG00COMMON1",
            "last_updated_utc": "2025-01-02T19:00:00Z",
        }
    )
    second = {
        **first,
        "name": "Latest eligible revision",
        "share_class_figi": "BBG00ADDED01",
        "last_updated_utc": "2025-01-02T20:00:00Z",
    }
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        result = massive.sync_reference_asof(
            conn,
            _client(
                _QueueOpener([{"status": "OK", "results": [first, second]}])
            ),
            DAY,
        )
        assert result["vendor_revision_collapse_count"] == 1
        assert conn.execute(
            "SELECT name,composite_figi,share_class_figi FROM instrument_master"
        ).fetchone() == (
            "Latest eligible revision",
            "BBG00COMMON1",
            "BBG00ADDED01",
        )
    finally:
        conn.close()


def test_reference_asof_failed_second_page_resumes_transactionally(
    tmp_path: Path,
) -> None:
    next_url = "https://api.massive.com/v3/reference/tickers?cursor=resume"
    first_page = {
        "status": "OK",
        "results": [_reference_row("AAPL", active=True)],
        "next_url": next_url,
    }
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        with pytest.raises(Exception, match="repeated or conflicted"):
            massive.sync_reference_asof(
                conn,
                _client(
                    _QueueOpener(
                        [
                            first_page,
                            {
                                "status": "OK",
                                "results": [_reference_row("AAPL", active=True)],
                            },
                        ]
                    )
                ),
                DAY,
            )

        snapshot_key = massive.reference_asof_snapshot_key(DAY)
        assert conn.execute(
            "SELECT cursor,status,row_count FROM fetch_checkpoint "
            "WHERE checkpoint_key=?",
            (snapshot_key,),
        ).fetchone() == (next_url, "in_progress", 1)
        assert conn.execute(
            "SELECT COUNT(*) FROM reference_asof_pages WHERE snapshot_key=?",
            (snapshot_key,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM raw_responses WHERE kind=?", (snapshot_key,)
        ).fetchone()[0] == 1

        resume_opener = _QueueOpener(
            [
                {
                    "status": "OK",
                    "results": [_reference_row("MSFT", active=True)],
                }
            ]
        )
        resumed = massive.sync_reference_asof(
            conn, _client(resume_opener), DAY
        )
        assert [call["url"] for call in resume_opener.calls] == [next_url]
        assert resumed["status"] == "complete"
        assert resumed["row_count"] == 2
        assert resumed["pages"] == 2
    finally:
        conn.close()


def test_reference_asof_audit_uses_snapshot_clock_not_provider_list_date(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        massive.sync_splits(
            conn,
            _client(_QueueOpener([{"status": "OK", "results": [_split_row()]}])),
        )
        massive.sync_reference(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_reference_row("NOW", active=True)]}]
                )
            ),
            active=True,
        )
        massive.sync_reference_asof(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_reference_row("AAPL", active=True)]}]
                )
            ),
            DAY,
        )

        reads: list[tuple[str | None, str | None]] = []

        def metadata_only_authorizer(
            action: int,
            table: str | None,
            column: str | None,
            _database: str | None,
            _trigger: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_READ:
                reads.append((table, column))
                if table == "daily_bars":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.set_authorizer(metadata_only_authorizer)
        audit = massive.audit_reference_asof_readiness(
            conn, expected_dates=[DAY], min_rows_per_date=1
        )
        normalization = massive.audit_normalization_readiness(conn, as_of=DAY)
        conn.set_authorizer(None)

        assert audit["status"] == "ready"
        assert audit["expected_dates"] == [DAY]
        assert audit["complete_dates"] == [DAY]
        assert audit["minimum_rows_per_date_required"] == 1
        assert audit["minimum_rows_per_date_observed"] == 1
        assert audit["duplicate_asof_ticker_count"] == 0
        assert audit["raw_page_hash_integrity"] is True
        assert audit["provider_list_date_required"] is False
        assert audit["identity_availability_clock"] == "reference_snapshot_date"
        assert audit["current_reference_row_count"] == 1
        assert audit["current_reference_consumed"] is False
        assert audit["price_or_return_values_read"] is False
        assert audit["pit_tier"] == "research_pit"
        assert audit["result_ceiling"] == "observed_only"
        assert normalization["identity_asof_ready"] is True
        assert normalization["provider_list_date_required"] is False
        assert normalization["replay_ready"] is True
        assert all(table != "daily_bars" for table, _column in reads)
    finally:
        conn.set_authorizer(None)
        conn.close()


def test_reference_asof_audit_rejects_current_only_and_raw_hash_corruption(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        massive.sync_reference(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_reference_row("AAPL", active=True)]}]
                )
            ),
            active=True,
        )
        current_only = massive.audit_reference_asof_readiness(
            conn, expected_dates=[DAY], min_rows_per_date=1
        )
        assert current_only["status"] == "parked"
        assert current_only["complete_dates"] == []
        assert current_only["missing_dates"] == [DAY]
        assert current_only["current_reference_row_count"] == 1
        assert current_only["current_reference_consumed"] is False

        massive.sync_reference_asof(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_reference_row("MSFT", active=True)]}]
                )
            ),
            DAY,
        )
        snapshot_key = massive.reference_asof_snapshot_key(DAY)
        conn.execute(
            "UPDATE raw_responses SET raw_gzip=? WHERE kind=?",
            (sqlite3.Binary(gzip.compress(b'{}', mtime=0)), snapshot_key),
        )
        conn.commit()
        corrupted = massive.audit_reference_asof_readiness(
            conn, expected_dates=[DAY], min_rows_per_date=1
        )
        assert corrupted["status"] == "parked"
        assert corrupted["raw_page_hash_integrity"] is False
        assert DAY in corrupted["invalid_dates"]
        assert "reference_asof_raw_page_hash_integrity_failed" in corrupted["park_reasons"]
    finally:
        conn.close()


def test_reference_asof_cli_date_file_forwards_frozen_19_dates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates_file = tmp_path / "dates.txt"
    dates_file.write_text(
        "\n".join(massive.DEFAULT_REFERENCE_ASOF_DATES), encoding="utf-8"
    )
    captured: dict[str, Any] = {}

    def fake_sync(
        _conn: sqlite3.Connection,
        _client_value: object,
        dates: Iterable[str],
        *,
        max_pages: int,
    ) -> dict[str, Any]:
        captured["dates"] = list(dates)
        captured["max_pages"] = max_pages
        return {
            "status": "complete",
            "expected_dates": captured["dates"],
            "complete_dates": captured["dates"],
            "date_count": len(captured["dates"]),
            "row_count": 0,
            "pages": 0,
            "snapshots": [],
        }

    monkeypatch.setattr(massive, "_build_client", lambda _args: object())
    monkeypatch.setattr(massive, "sync_reference_asof_dates", fake_sync)
    exit_code = massive.main(
        [
            "--db",
            str(tmp_path / "massive.sqlite"),
            "sync-reference-asof",
            "--dates-file",
            str(dates_file),
            "--max-pages",
            "17",
        ]
    )

    assert exit_code == 0
    assert captured["dates"] == list(massive.DEFAULT_REFERENCE_ASOF_DATES)
    assert len(captured["dates"]) == 19
    assert captured["dates"][0] == "2024-10-02"
    assert captured["dates"][-1] == "2026-04-01"
    assert captured["max_pages"] == 17


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--date", DAY], [DAY]),
        (
            ["--dates", "2025-01-02,2025-02-03"],
            ["2025-01-02", "2025-02-03"],
        ),
    ],
    ids=["one-date", "comma-list"],
)
def test_reference_asof_cli_parses_one_date_or_comma_list(
    arguments: list[str], expected: list[str]
) -> None:
    args = massive.build_parser().parse_args(["sync-reference-asof", *arguments])
    assert massive._reference_asof_dates_from_args(args) == expected


def test_reference_asof_audit_cli_defaults_to_frozen_dates_and_fails_closed(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "identity_audit.json"
    exit_code = massive.main(
        [
            "--db",
            str(tmp_path / "massive.sqlite"),
            "audit-reference-asof",
            "--output",
            str(output_path),
        ]
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 3
    assert persisted["status"] == "parked"
    assert persisted["expected_dates"] == list(massive.DEFAULT_REFERENCE_ASOF_DATES)
    assert persisted["complete_dates"] == []
    assert persisted["expected_date_count"] == 19
    assert persisted["current_reference_consumed"] is False
    assert persisted["price_or_return_values_read"] is False
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))


def test_summary_manifest_is_research_pit_unadjusted_and_key_free(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "massive.sqlite"
    manifest_path = tmp_path / "massive_manifest.json"
    conn = massive.connect_database(db_path)
    try:
        massive.ingest_grouped_day(
            conn,
            _client(_QueueOpener([_grouped_payload()])),
            DAY,
        )
        summary = massive.build_summary(conn)
        massive.write_summary_atomic(manifest_path, summary)
    finally:
        conn.close()

    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["pit_tier"] == "research_pit"
    assert persisted["known_future_leakage"] is False
    assert persisted["adjusted"] is False
    assert persisted["result_ceiling"] == "observed_only"
    assert persisted["row_count"] == 1
    assert SECRET not in json.dumps(persisted)
    _assert_secret_absent_from_sqlite_family(db_path)
    assert not list(tmp_path.glob(f".{manifest_path.name}.*.tmp"))


def test_split_sync_paginates_preserves_case_and_hashes_every_raw_page(
    tmp_path: Path,
) -> None:
    next_url = "https://api.massive.com/stocks/v1/splits?cursor=second"
    first_payload = {
        "status": "OK",
        "results": [_split_row("BcPc", provider_id="case-sensitive")],
        "next_url": next_url,
    }
    second_payload = {
        "status": "OK",
        "results": [
            _split_row(
                "MSFT",
                execution_date="2025-02-10",
                provider_id=None,
                split_from=1.0,
                split_to=2.0,
            )
        ],
    }
    raw_pages = [_json_bytes(first_payload), _json_bytes(second_payload)]
    opener = _QueueOpener(raw_pages)
    db_path = tmp_path / "massive.sqlite"
    conn = massive.connect_database(db_path)
    try:
        result = massive.sync_splits(conn, _client(opener))

        assert result["snapshot_key"] == (
            "stock_splits:2024-07-29:2026-07-24"
        )
        assert result["row_count"] == 2
        assert result["pages"] == 2
        assert result["status"] == "complete"
        assert "limit=5000" in opener.calls[0]["url"]
        assert "sort=execution_date.asc" in opener.calls[0]["url"]
        assert "order=" not in opener.calls[0]["url"]
        assert [call["url"] for call in opener.calls][1] == next_url
        assert all(SECRET not in call["url"] for call in opener.calls)

        rows = conn.execute(
            "SELECT ticker,execution_date,adjustment_type,split_from,split_to "
            "FROM stock_splits ORDER BY ticker"
        ).fetchall()
        assert rows == [
            ("BcPc", "2025-01-10", "forward_split", 1.0, 4.0),
            ("MSFT", "2025-02-10", "forward_split", 1.0, 2.0),
        ]
        assert "historical_adjustment_factor" not in {
            str(row[1]) for row in conn.execute("PRAGMA table_info(stock_splits)")
        }

        stored_pages = conn.execute(
            "SELECT p.page_number,p.request_key,p.response_sha256,p.next_url,"
            "p.row_count,r.raw_gzip FROM stock_split_pages p "
            "JOIN raw_responses r USING(request_key) ORDER BY p.page_number"
        ).fetchall()
        assert len(stored_pages) == 2
        for expected_raw, stored in zip(raw_pages, stored_pages):
            assert gzip.decompress(bytes(stored[5])) == expected_raw
            assert stored[2] == hashlib.sha256(expected_raw).hexdigest()
        digest_records = [tuple(row[:5]) for row in stored_pages]
        assert result["all_pages_sha256"] == massive._split_pages_digest(
            digest_records
        )
        checkpoint_digest = conn.execute(
            "SELECT content_sha256 FROM fetch_checkpoint WHERE checkpoint_key=?",
            (result["snapshot_key"],),
        ).fetchone()[0]
        assert checkpoint_digest == result["all_pages_sha256"]
        _assert_secret_absent_from_sqlite_family(db_path)
    finally:
        conn.close()


def test_split_malformed_page_rolls_back_raw_rows_and_checkpoint(
    tmp_path: Path,
) -> None:
    malformed = _split_row("BAD", provider_id="bad")
    malformed.pop("split_to")
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception, match="split_to"):
            massive.sync_splits(
                conn,
                _client(
                    _QueueOpener(
                        [
                            {
                                "status": "OK",
                                "results": [_split_row(), malformed],
                            }
                        ]
                    )
                ),
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()


def test_split_cross_page_conflict_rolls_back_only_conflicting_page(
    tmp_path: Path,
) -> None:
    next_url = "https://api.massive.com/stocks/v1/splits?cursor=conflict"
    first = {
        "status": "OK",
        "results": [_split_row(provider_id="reused-provider", split_to=4.0)],
        "next_url": next_url,
    }
    conflict = {
        "status": "OK",
        "results": [_split_row(provider_id="reused-provider", split_to=5.0)],
    }
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        with pytest.raises(Exception, match="(?i)conflict"):
            massive.sync_splits(
                conn,
                _client(_QueueOpener([first, conflict])),
            )

        assert conn.execute("SELECT COUNT(*) FROM stock_splits").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM stock_split_pages").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM raw_responses WHERE kind='stock_splits'"
        ).fetchone()[0] == 1
        checkpoint = conn.execute(
            "SELECT cursor,status,row_count FROM fetch_checkpoint "
            "WHERE kind='stock_splits'"
        ).fetchone()
        assert checkpoint == (next_url, "in_progress", 1)
    finally:
        conn.close()


def test_split_resume_uses_checkpoint_cursor_then_completed_sync_is_idempotent(
    tmp_path: Path,
) -> None:
    next_url = "https://api.massive.com/stocks/v1/splits?cursor=resume"
    first = {
        "status": "OK",
        "results": [_split_row(provider_id="first")],
        "next_url": next_url,
    }
    malformed = _split_row(
        "MSFT", execution_date="2025-02-10", provider_id="second"
    )
    malformed.pop("adjustment_type")
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        with pytest.raises(Exception, match="adjustment_type"):
            massive.sync_splits(
                conn,
                _client(
                    _QueueOpener(
                        [first, {"status": "OK", "results": [malformed]}]
                    )
                ),
            )

        resume_opener = _QueueOpener(
            [
                {
                    "status": "OK",
                    "results": [
                        _split_row(
                            "MSFT",
                            execution_date="2025-02-10",
                            provider_id="second",
                        )
                    ],
                }
            ]
        )
        resumed = massive.sync_splits(conn, _client(resume_opener))
        counts = _all_counts(conn)
        no_network = _QueueOpener([])
        idempotent = massive.sync_splits(conn, _client(no_network))

        assert [call["url"] for call in resume_opener.calls] == [next_url]
        assert resumed["row_count"] == idempotent["row_count"] == 2
        assert resumed["pages"] == idempotent["pages"] == 2
        assert idempotent["resumed_without_network"] is True
        assert no_network.calls == []
        assert _all_counts(conn) == counts
    finally:
        conn.close()


def test_historical_price_factor_has_strict_event_boundaries_and_ignores_cumulative(
    tmp_path: Path,
) -> None:
    payload = {
        "status": "OK",
        "results": [
            _split_row(
                execution_date="2025-01-10",
                provider_id="forward",
                split_from=1.0,
                split_to=4.0,
                historical_adjustment_factor=999_999_999.0,
            ),
            _split_row(
                execution_date="2025-02-10",
                adjustment_type="reverse_split",
                provider_id="reverse",
                split_from=10.0,
                split_to=1.0,
                historical_adjustment_factor=0.000000001,
            ),
        ],
    }
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        massive.sync_splits(conn, _client(_QueueOpener([payload])))

        assert massive.historical_price_factor(
            conn, "AAPL", price_date="2025-01-09", as_of="2025-01-09"
        ) == pytest.approx(1.0)
        assert massive.historical_price_factor(
            conn, "AAPL", price_date="2025-01-09", as_of="2025-01-10"
        ) == pytest.approx(0.25)
        assert massive.historical_price_factor(
            conn, "AAPL", price_date="2025-01-09", as_of="2025-02-10"
        ) == pytest.approx(2.5)
        assert massive.historical_price_factor(
            conn, "AAPL", price_date="2025-01-10", as_of="2025-02-10"
        ) == pytest.approx(10.0)
        assert massive.historical_price_factor(
            conn, "AAPL", price_date="2025-02-10", as_of="2025-02-10"
        ) == pytest.approx(1.0)
    finally:
        conn.close()


def test_distinct_same_day_stock_dividend_effects_are_retained_and_compose_deterministically(
    tmp_path: Path,
) -> None:
    effects = [
        _split_row(
            "DUAL",
            execution_date="2025-03-14",
            adjustment_type="stock_dividend",
            provider_id="effect-a",
            split_from=100.0,
            split_to=103.0,
        ),
        _split_row(
            "DUAL",
            execution_date="2025-03-14",
            adjustment_type="stock_dividend",
            provider_id="effect-b",
            split_from=10.0,
            split_to=11.0,
        ),
    ]
    observed_factors: list[float] = []
    for index, ordered_effects in enumerate((effects, list(reversed(effects)))):
        conn = massive.connect_database(tmp_path / f"massive-{index}.sqlite")
        try:
            result = massive.sync_splits(
                conn,
                _client(
                    _QueueOpener(
                        [{"status": "OK", "results": ordered_effects}]
                    )
                ),
            )
            stored = conn.execute(
                "SELECT provider_id,event_identity_key,split_from,split_to "
                "FROM stock_splits WHERE ticker='DUAL' ORDER BY provider_id"
            ).fetchall()
            assert result["row_count"] == 2
            assert [row[0] for row in stored] == ["effect-a", "effect-b"]
            assert len({row[1] for row in stored}) == 2
            observed_factors.append(
                massive.historical_price_factor(
                    conn,
                    "DUAL",
                    price_date="2025-03-13",
                    as_of="2025-03-14",
                )
            )
        finally:
            conn.close()

    expected = (100.0 / 103.0) * (10.0 / 11.0)
    assert observed_factors[0] == observed_factors[1]
    assert observed_factors[0] == pytest.approx(expected)


def test_normalization_audit_reads_metadata_only_and_parks_current_identity(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        massive.sync_splits(
            conn,
            _client(_QueueOpener([{"status": "OK", "results": [_split_row()]}])),
        )
        massive.sync_reference(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_reference_row("AAPL", active=True)]}]
                )
            ),
            active=True,
        )

        reads: list[tuple[str | None, str | None]] = []

        def metadata_only_authorizer(
            action: int,
            table: str | None,
            column: str | None,
            _database: str | None,
            _trigger: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_READ:
                reads.append((table, column))
                if table == "daily_bars":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.set_authorizer(metadata_only_authorizer)
        audit = massive.audit_normalization_readiness(conn)
        conn.set_authorizer(None)

        assert audit["status"] == "parked"
        assert audit["split_ready"] is True
        assert audit["identity_asof_ready"] is False
        assert audit["replay_ready"] is False
        assert "identity_current_only_snapshot" in audit["park_reasons"]
        assert "identity_asof_snapshot_missing" in audit["park_reasons"]
        assert audit["provider_list_date_required"] is False
        assert audit["current_reference_consumed"] is False
        assert audit["price_or_return_values_read"] is False
        assert audit["historical_adjustment_factor_used"] is False
        assert audit["grouped_daily_complete_checkpoint_count"] == 0
        assert audit["grouped_daily_expected_checkpoint_count"] == 520
        assert audit["grouped_daily_ready"] is False
        assert audit["identity_missing_both_figis_row_count"] == 1
        assert all(table != "daily_bars" for table, _column in reads)
    finally:
        conn.set_authorizer(None)
        conn.close()


def test_audit_cli_atomically_writes_parked_result_and_returns_three(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "massive.sqlite"
    output_path = tmp_path / "normalization_audit.json"

    exit_code = massive.main(
        [
            "--db",
            str(db_path),
            "audit-normalization",
            "--output",
            str(output_path),
        ]
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 3
    assert persisted["status"] == "parked"
    assert persisted["replay_ready"] is False
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))


def test_split_response_echoing_credential_is_rejected_without_persistence(
    tmp_path: Path,
) -> None:
    row = _split_row()
    row["historical_adjustment_factor"] = SECRET
    db_path = tmp_path / "massive.sqlite"
    conn = massive.connect_database(db_path)
    before = _all_counts(conn)
    try:
        with pytest.raises(Exception) as caught:
            massive.sync_splits(
                conn,
                _client(_QueueOpener([{"status": "OK", "results": [row]}])),
            )
        assert SECRET not in str(caught.value)
        assert _all_counts(conn) == before
    finally:
        conn.close()
    _assert_secret_absent_from_sqlite_family(db_path)


def test_dividend_endpoint_decimal_projection_and_two_page_raw_replay(
    tmp_path: Path,
) -> None:
    next_url = "https://api.massive.com/stocks/v1/dividends?cursor=page-two"
    first_raw = (
        '{"status":"OK","results":[{' 
        '"id":"cash-1","ticker":"BcPc","declaration_date":"2025-01-02",'
        '"cash_amount":1.2300000000000000001,"currency":"USD",'
        '"distribution_type":"CD","frequency":4,'
        '"split_adjusted_cash_amount":9.9,"historical_adjustment_factor":7'
        '}],"next_url":"' + next_url + '"}'
    ).encode("utf-8")
    second_payload = {
        "status": "OK",
        "results": [
            _dividend_row(
                "MSft",
                declaration_date="2025-02-03",
                ex_dividend_date="2025-02-14",
                cash_amount="2.5000",
                provider_id=None,
            )
        ],
    }
    second_raw = _json_bytes(second_payload)
    opener = _QueueOpener([first_raw, second_raw])
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        result = massive.sync_dividends(conn, _client(opener))
        verified = massive._verify_dividend_snapshot_state(conn)
        projection = massive.decision_safe_dividend_rows(conn)

        assert result["pages"] == verified["pages"] == 2
        assert result["row_count"] == verified["row_count"] == 2
        assert result["all_pages_sha256"] == verified["all_pages_sha256"]
        assert "declaration_date.gte" not in opener.calls[0]["url"]
        assert "declaration_date.lte" not in opener.calls[0]["url"]
        assert "limit=5000" in opener.calls[0]["url"]
        assert "sort=" not in opener.calls[0]["url"]
        assert opener.calls[1]["url"] == next_url

        stored = conn.execute(
            "SELECT provider_id,ticker,ex_dividend_date,cash_amount,"
            "typeof(cash_amount),raw_json FROM stock_dividends ORDER BY ticker"
        ).fetchall()
        assert stored[0][:5] == (
            "cash-1",
            "BcPc",
            None,
            "1.2300000000000000001",
            "text",
        )
        assert stored[1][:5] == (None, "MSft", "2025-02-14", "2.5", "text")
        assert "distribution_type" in json.loads(stored[0][5])
        normalized_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(stock_dividends)")
        }
        for forbidden in (
            "distribution_type",
            "frequency",
            "split_adjusted_cash_amount",
            "historical_adjustment_factor",
        ):
            assert forbidden not in normalized_columns
            assert all(forbidden not in row for row in projection)
        assert set(projection[0]) == {
            "provider_id",
            "ticker",
            "declaration_date",
            "ex_dividend_date",
            "cash_amount",
            "currency",
        }
        assert projection[0]["ex_dividend_date"] is None
        assert projection[1]["provider_id"] is None

        pages = conn.execute(
            "SELECT p.page_number,p.request_key,p.response_sha256,p.next_url,"
            "p.row_count,r.raw_gzip FROM stock_dividend_pages p "
            "JOIN raw_responses r USING(request_key) ORDER BY p.page_number"
        ).fetchall()
        assert [gzip.decompress(bytes(row[5])) for row in pages] == [
            first_raw,
            second_raw,
        ]
        assert result["all_pages_sha256"] == massive._dividend_pages_digest(
            [tuple(row[:5]) for row in pages]
        )
        query_plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT provider_id FROM stock_dividends "
            "WHERE snapshot_key=? AND request_key=? ORDER BY provider_id",
            (result["snapshot_key"], pages[0][1]),
        ).fetchall()
        assert any(
            "stock_dividends_request_page_lookup" in str(part)
            for row in query_plan
            for part in row
        )
    finally:
        conn.close()

    with pytest.raises(massive.MassiveError):
        massive._sanitize_dividend_url(
            "https://evil.example/stocks/v1/dividends?cursor=x",
            start="2021-01-01",
            end="2026-05-31",
        )
    with pytest.raises(massive.MassiveError):
        massive._sanitize_dividend_url(
            "https://api.massive.com/stocks/v1/splits?cursor=x",
            start="2021-01-01",
            end="2026-05-31",
        )
    with pytest.raises(massive.MassiveError):
        massive._sanitize_dividend_url(
            "https://api.massive.com/stocks/v1/dividends?ticker=AAPL&cursor=x",
            start="2021-01-01",
            end="2026-05-31",
        )
    with pytest.raises(massive.MassiveError):
        massive._sanitize_dividend_url(
            "https://api.massive.com/stocks/v1/dividends?"
            "declaration_date.gte=2021-01-01&cursor=x",
            start="2021-01-01",
            end="2026-05-31",
        )


def test_dividend_storage_keeps_full_provider_page_but_projection_is_range_bound(
    tmp_path: Path,
) -> None:
    rows = [
        _dividend_row("OLD", declaration_date="2020-12-31", provider_id="old"),
        _dividend_row("IN", declaration_date="2025-01-02", provider_id="in"),
        _dividend_row("NEW", declaration_date="2026-06-01", provider_id="new"),
    ]
    conn = massive.connect_database(tmp_path / "range.sqlite")
    try:
        result = massive.sync_dividends(
            conn, _client(_QueueOpener([{"status": "OK", "results": rows}]))
        )
        projection = massive.decision_safe_dividend_rows(conn)

        assert result["row_count"] == 3
        assert _count(conn, "stock_dividends") == 3
        assert [(row["ticker"], row["declaration_date"]) for row in projection] == [
            ("IN", "2025-01-02")
        ]
    finally:
        conn.close()


@pytest.mark.parametrize("tamper", ["raw", "normalized"])
def test_dividend_verifier_detects_raw_or_normalized_tamper(
    tmp_path: Path, tamper: str
) -> None:
    conn = massive.connect_database(tmp_path / f"massive-{tamper}.sqlite")
    try:
        result = massive.sync_dividends(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [_dividend_row()]}]
                )
            ),
        )
        if tamper == "raw":
            request_key = conn.execute(
                "SELECT request_key FROM stock_dividend_pages"
            ).fetchone()[0]
            conn.execute(
                "UPDATE raw_responses SET raw_gzip=? WHERE request_key=?",
                (sqlite3.Binary(gzip.compress(b"{}", mtime=0)), request_key),
            )
        else:
            conn.execute(
                "UPDATE stock_dividends SET cash_amount='999' WHERE snapshot_key=?",
                (result["snapshot_key"],),
            )
        conn.commit()
        with pytest.raises(massive.MassiveError, match="(?i)dividend"):
            massive._verify_dividend_snapshot_state(conn)
    finally:
        conn.close()


def test_dividend_cursor_cycle_and_page_bound_fail_closed(tmp_path: Path) -> None:
    next_url = "https://api.massive.com/stocks/v1/dividends?cursor=loop"
    first = {
        "status": "OK",
        "results": [_dividend_row(provider_id="first")],
        "next_url": next_url,
    }
    repeated = {
        "status": "OK",
        "results": [
            _dividend_row(
                "MSFT", declaration_date="2025-02-03", provider_id="second"
            )
        ],
        "next_url": next_url,
    }
    conn = massive.connect_database(tmp_path / "cycle.sqlite")
    try:
        with pytest.raises(massive.MassiveError, match="cursor repeated"):
            massive.sync_dividends(
                conn, _client(_QueueOpener([first, repeated]))
            )
        assert _count(conn, "stock_dividends") == 1
        assert _count(conn, "stock_dividend_pages") == 1
    finally:
        conn.close()

    bounded = massive.connect_database(tmp_path / "bounded.sqlite")
    try:
        with pytest.raises(massive.MassiveError, match="page bound"):
            massive.sync_dividends(
                bounded, _client(_QueueOpener([first])), max_pages=1
            )
        assert _count(bounded, "stock_dividends") == 1
        assert _count(bounded, "stock_dividend_pages") == 1
    finally:
        bounded.close()


def test_dividend_page_rollback_and_provider_id_conflict(tmp_path: Path) -> None:
    conn = massive.connect_database(tmp_path / "rollback.sqlite")
    before = _all_counts(conn)
    try:
        def failpoint(**event: Any) -> None:
            if event["stage"] == "after_dividend_rows_insert":
                raise RuntimeError("injected dividend page failure")

        with pytest.raises(RuntimeError, match="injected dividend"):
            massive.sync_dividends(
                conn,
                _client(
                    _QueueOpener(
                        [{"status": "OK", "results": [_dividend_row()]}]
                    )
                ),
                failpoint=failpoint,
            )
        assert _all_counts(conn) == before
    finally:
        conn.close()

    next_url = "https://api.massive.com/stocks/v1/dividends?cursor=conflict"
    conflict_conn = massive.connect_database(tmp_path / "conflict.sqlite")
    try:
        with pytest.raises(massive.MassiveError, match="provider-ID conflict"):
            massive.sync_dividends(
                conflict_conn,
                _client(
                    _QueueOpener(
                        [
                            {
                                "status": "OK",
                                "results": [_dividend_row(provider_id="same")],
                                "next_url": next_url,
                            },
                            {
                                "status": "OK",
                                "results": [
                                    _dividend_row(
                                        provider_id="same", cash_amount="8.0"
                                    )
                                ],
                            },
                        ]
                    )
                ),
            )
        assert _count(conflict_conn, "stock_dividends") == 1
        assert _count(conflict_conn, "stock_dividend_pages") == 1
    finally:
        conflict_conn.close()


def _insert_audit_bars(
    conn: sqlite3.Connection, ticker: str, declaration_date: str
) -> None:
    raw = b'{"test":"predecision-bars"}'
    request_key = f"audit-bars:{ticker}"
    conn.execute(
        "INSERT INTO raw_responses(request_key,kind,sanitized_url,retrieved_at_utc,"
        "http_status,response_sha256,raw_gzip,row_count,adjusted) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (
            request_key,
            "audit_test",
            f"https://api.massive.com/test/{ticker}",
            "2025-01-02T00:00:00Z",
            200,
            hashlib.sha256(raw).hexdigest(),
            sqlite3.Binary(gzip.compress(raw, mtime=0)),
            21,
            0,
        ),
    )
    cursor = date.fromisoformat(declaration_date)
    days: list[date] = []
    while len(days) < 20:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    for day in days:
        conn.execute(
            "INSERT INTO daily_bars(ticker,trade_date,open,high,low,close,volume,"
            "vwap,transactions,source_timestamp_ms,request_key) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                ticker,
                day.isoformat(),
                10.0,
                11.0,
                9.0,
                10.0,
                200_000.0,
                10.0,
                100,
                _millis(day.isoformat()),
                request_key,
            ),
        )
    post_day = date.fromisoformat(declaration_date) + timedelta(days=1)
    conn.execute(
        "INSERT INTO daily_bars(ticker,trade_date,open,high,low,close,volume,"
        "vwap,transactions,source_timestamp_ms,request_key) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            ticker,
            post_day.isoformat(),
            999.0,
            1000.0,
            998.0,
            999.0,
            999_000_000.0,
            999.0,
            100,
            _millis(post_day.isoformat()),
            request_key,
        ),
    )
    conn.commit()


def test_dividend_duplicates_resume_and_audit_are_predecision_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    declaration = "2025-01-02"
    rows = [
        _dividend_row(
            "CaseX", declaration_date=declaration, ex_dividend_date=None,
            provider_id="effect-a",
        ),
        _dividend_row(
            "CaseX", declaration_date=declaration, ex_dividend_date=None,
            provider_id="effect-b",
        ),
    ]
    conn = massive.connect_database(tmp_path / "audit.sqlite")
    try:
        first = massive.sync_dividends(
            conn, _client(_QueueOpener([{"status": "OK", "results": rows}]))
        )
        no_network = _QueueOpener([])
        resumed = massive.sync_dividends(conn, _client(no_network))
        assert first["row_count"] == resumed["row_count"] == 2
        assert resumed["resumed_without_network"] is True
        assert no_network.calls == []

        prior_identity = _reference_row("CaseX", active=True)
        prior_identity["last_updated_utc"] = "2024-12-01T00:00:00Z"
        massive.sync_reference_asof(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [prior_identity]}]
                )
            ),
            "2024-12-02",
        )
        future_identity = _reference_row("OTHER", active=True)
        future_identity["last_updated_utc"] = "2025-02-01T00:00:00Z"
        massive.sync_reference_asof(
            conn,
            _client(
                _QueueOpener(
                    [{"status": "OK", "results": [future_identity]}]
                )
            ),
            "2025-02-03",
        )
        _insert_audit_bars(conn, "CaseX", declaration)
        original_verify = massive._verify_dividend_snapshot_state
        verify_calls = 0

        def counting_verify(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal verify_calls
            verify_calls += 1
            return original_verify(*args, **kwargs)

        monkeypatch.setattr(
            massive, "_verify_dividend_snapshot_state", counting_verify
        )
        statements: list[str] = []
        conn.set_trace_callback(statements.append)
        audit = massive.audit_dividend_readiness(
            conn, min_touches_per_window=1
        )
        conn.set_trace_callback(None)

        selected = audit["windows"]["old_thin"]["selected"]
        assert len(selected) == 1
        assert selected[0]["provider_ids"] == ["effect-a", "effect-b"]
        assert selected[0]["provider_row_count"] == 2
        assert selected[0]["economic_effect_count"] == 1
        assert selected[0]["ex_dividend_date"] is None
        assert selected[0]["identity_snapshot_as_of"] == "2024-12-02"
        assert selected[0]["reference_close_date"] <= declaration
        assert selected[0]["reference_close"] == "10"
        assert selected[0]["trailing20_median_dollar_volume"] == "2000000"
        assert audit["exact_effect_duplicate_rows_collapsed"] == 1
        assert audit["stored_provider_row_count"] == 2
        assert audit["predecision_price_values_read"] is True
        assert audit["post_decision_price_or_return_values_read"] is False
        assert audit["outcome_fields_read"] == []
        assert audit["forward_horizon_read"] is False
        assert verify_calls == 1
        assert audit["status"] == "blocked"
        assert audit["synthesis_pass"]["opportunity_cost_winner"] == (
            "cash/no new core entry"
        )
        assert audit["synthesis_pass"]["pit_tier"] == "research_pit"
        assert audit["synthesis_pass"]["result_ceiling"] == "observed_only"
        assert audit["synthesis_pass"]["research_digest_ledger_append_required"] is False
        price_sql = [sql for sql in statements if "FROM daily_bars" in sql]
        assert price_sql
        assert all("trade_date<=" in sql for sql in price_sql)
        assert "999" not in selected[0]["reference_close"]
    finally:
        conn.set_trace_callback(None)
        conn.close()


def test_dividend_cli_defaults_are_bounded_and_audit_writes_blocked(
    tmp_path: Path,
) -> None:
    sync_args = massive.build_parser().parse_args(["sync-dividends"])
    assert sync_args.start == "2021-01-01"
    assert sync_args.end == "2026-05-31"
    assert sync_args.max_pages > 49

    output = tmp_path / "dividend-audit.json"
    exit_code = massive.main(
        [
            "--db",
            str(tmp_path / "empty.sqlite"),
            "audit-dividends",
            "--output",
            str(output),
        ]
    )
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 3
    assert persisted["status"] == "blocked"
    assert set(persisted["windows"]) == set(massive.DIVIDEND_FIXED_WINDOWS)
    assert persisted["post_decision_price_or_return_values_read"] is False
    assert persisted["outcome_fields_read"] == []


# ── exp-20260805-004: bounded incremental grouped-daily catch-up ─────────────


def _catchup_as_of(day: str, hour_utc: int = 21) -> datetime:
    return datetime.fromisoformat(day).replace(
        hour=hour_utc, tzinfo=timezone.utc
    )


def _seed_grouped_day(conn: sqlite3.Connection, day: str) -> None:
    massive.backfill_grouped_days(
        conn,
        _client(_QueueOpener([_grouped_payload([_bar(day=day)])])),
        start=day,
        end=day,
    )


def test_catchup_fresh_warehouse_makes_no_network_call_and_needs_no_key(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        _seed_grouped_day(conn, "2026-07-31")
        # No client injected and no credential available: a fresh warehouse
        # must return before either would be needed.
        summary = massive.run_incremental_grouped_catchup(
            as_of=_catchup_as_of("2026-07-31"),
            conn=conn,
            api_key_file=tmp_path / "no-such-key.txt",
        )
        assert summary["status"] == "fresh"
        assert summary["alert"] is False
        assert summary["dates_fetched"] == 0
        assert summary["bars_max_trade_date_after"] == "2026-07-31"
    finally:
        conn.close()


def test_catchup_empty_daily_bars_fails_closed(tmp_path: Path) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        summary = massive.run_incremental_grouped_catchup(
            as_of=_catchup_as_of("2026-07-31"), conn=conn
        )
        assert summary["status"] == "blocked_empty_daily_bars"
        assert summary["alert"] is True
    finally:
        conn.close()


def test_catchup_is_bounded_oldest_first_and_reports_remainder(
    tmp_path: Path,
) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        _seed_grouped_day(conn, "2026-07-24")
        opener = _QueueOpener(
            [
                _grouped_payload([_bar(day="2026-07-27")]),
                _grouped_payload([_bar(day="2026-07-28")]),
            ]
        )
        summary = massive.run_incremental_grouped_catchup(
            as_of=_catchup_as_of("2026-07-31"),
            conn=conn,
            client=_client(opener),
            max_sessions=2,
        )
        assert summary["status"] == "complete"
        assert summary["dates_fetched"] == 2
        assert summary["remaining_missing_weekdays"] == 3
        assert summary["bars_max_trade_date_after"] == "2026-07-28"
        assert len(opener.calls) == 2
    finally:
        conn.close()


def test_catchup_api_failure_is_fail_soft_with_alert(tmp_path: Path) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        _seed_grouped_day(conn, "2026-07-30")

        def down(request: Any, **kwargs: Any) -> Any:
            raise urllib.error.URLError("connection refused")

        summary = massive.run_incremental_grouped_catchup(
            as_of=_catchup_as_of("2026-07-31"),
            conn=conn,
            client=_client(down, max_attempts=1),
        )
        assert summary["status"] == "error"
        assert summary["alert"] is True
        assert summary["reason"] == "catchup_fetch_failed"
        assert summary["bars_max_trade_date_after"] == "2026-07-30"
    finally:
        conn.close()


def test_missing_grouped_sessions_weekday_arithmetic(tmp_path: Path) -> None:
    conn = massive.connect_database(tmp_path / "massive.sqlite")
    try:
        _seed_grouped_day(conn, "2026-07-24")
        missing = massive.missing_grouped_sessions(conn, "2026-07-31")
        assert missing == [
            "2026-07-27",
            "2026-07-28",
            "2026-07-29",
            "2026-07-30",
            "2026-07-31",
        ]
        assert massive.missing_grouped_sessions(conn, "2026-07-24") == []
    finally:
        conn.close()
