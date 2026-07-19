from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import ortex_data_sidecar as sidecar


def _forty_weekdays(start: str) -> list[str]:
    day = date.fromisoformat(start)
    result: list[str] = []
    while len(result) < 40:
        if day.weekday() < 5:
            result.append(day.isoformat())
        day += timedelta(days=1)
    return result


def _fixed_block_calendar() -> list[str]:
    sessions: list[str] = []
    for block in sidecar.HISTORICAL_BLOCKS:
        block_days = _forty_weekdays(str(block["start"]))
        assert block_days[-1] <= block["end"]
        sessions.extend(block_days)
        sessions.append((date.fromisoformat(str(block["end"])) + timedelta(days=1)).isoformat())
    return sorted(set(sessions))


def _row(ticker: str, provider_date: str, value: float = 1.0) -> dict:
    return {
        "schema_version": 1,
        "ticker": ticker,
        "exchange": "NASDAQ",
        "provider_date": provider_date,
        "usable_trade_date": (date.fromisoformat(provider_date) + timedelta(days=1)).isoformat(),
        "cost_to_borrow_new_pct": value,
        "collected_at": "2026-07-18T00:00:00Z",
        "source_mode": "historical_block",
        "historical_block": "test",
        "source": "ortex_api_cost_to_borrow_new",
        "trade_enabled": False,
    }


def test_fixed_universe_and_blocks_are_predeclared() -> None:
    assert sidecar.FIXED_RESEARCH_TICKERS == (
        "AAPL", "MSFT", "META", "GOOG", "AMZN",
        "AMD", "AVGO", "MU", "NVDA", "CRDO",
        "COIN", "DDOG", "PLTR", "APP", "SNOW",
        "CVX", "XOM", "JPM", "GS", "TSLA",
    )
    assert len(set(sidecar.FIXED_RESEARCH_TICKERS)) == 20
    assert {ticker for ticker, venue in sidecar.TICKER_EXCHANGES.items() if venue == "NYSE"} == {
        "SNOW", "CVX", "XOM", "JPM", "GS"
    }
    assert [(row["label"], row["start"], row["end"]) for row in sidecar.HISTORICAL_BLOCKS] == [
        ("old_thin", "2024-12-11", "2025-02-10"),
        ("mid_weak", "2025-06-25", "2025-08-20"),
        ("late_strong", "2025-12-22", "2026-02-19"),
    ]


def test_next_usable_trade_date_is_strictly_after_provider_date() -> None:
    sessions = ["2026-07-17", "2026-07-20", "2026-07-21"]
    assert sidecar.next_usable_trade_date("2026-07-17", sessions) == "2026-07-20"
    assert sidecar.next_usable_trade_date("2026-07-18", sessions) == "2026-07-20"
    with pytest.raises(ValueError, match="strictly after"):
        sidecar.next_usable_trade_date("2026-07-21", sessions)


def test_validate_historical_blocks_requires_exactly_forty_supplied_sessions() -> None:
    calendar = _fixed_block_calendar()
    validated = sidecar.validate_historical_blocks(calendar)
    assert all(len(days) == 40 for days in validated.values())
    with pytest.raises(ValueError, match="exactly 40"):
        sidecar.validate_historical_blocks(calendar[1:])


def test_normalisation_keeps_only_locked_field_and_never_raw_metadata() -> None:
    secret = "secret-key-must-not-land"
    payload = {
        "creditsUsed": 1.25,
        "creditsLeft": 998.75,
        "requestHeaders": {"Ortex-Api-Key": secret},
        "rows": [
            {"date": "2026-07-17", "costToBorrowNew": "3.5", "extra": "drop"},
            {"date": "2026-07-18", "costToBorrowAll": 7.0},
            {"date": "bad", "costToBorrowNew": 9.0},
        ],
    }
    rows = sidecar.normalise_cost_to_borrow_new_rows(
        payload,
        ticker="aapl",
        exchange="nasdaq",
        trading_dates=["2026-07-17", "2026-07-20", "2026-07-21"],
        collected_at="2026-07-18T10:00:00Z",
        source_mode="daily_refresh",
        request_start_date="2026-07-17",
        request_end_date="2026-07-18",
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["cost_to_borrow_new_pct"] == 3.5
    assert rows[0]["usable_trade_date"] == "2026-07-20"
    serialised = json.dumps(rows)
    assert secret not in serialised
    assert "creditsUsed" not in serialised
    assert "extra" not in serialised
    assert rows[0]["trade_enabled"] is False


def test_atomic_append_is_idempotent_and_first_row_wins(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    first = _row("AAPL", "2026-07-17", 1.0)
    assert sidecar.append_normalised_rows_atomic([first], path=path)["appended"] == 1
    same = sidecar.append_normalised_rows_atomic([first], path=path)
    assert same["appended"] == 0
    assert same["duplicates"] == 1
    changed = sidecar.append_normalised_rows_atomic(
        [{**first, "cost_to_borrow_new_pct": 99.0}], path=path
    )
    assert changed["conflicts"] == 1
    assert sidecar.load_normalised_rows(path)[0]["cost_to_borrow_new_pct"] == 1.0
    assert not path.with_name("rows.jsonl.lock").exists()


def test_atomic_append_rejects_raw_or_secret_fields(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    with pytest.raises(ValueError, match="non-normalised"):
        sidecar.append_normalised_rows_atomic(
            [{**_row("AAPL", "2026-07-17"), "api_key": "must-not-land"}],
            path=path,
        )
    assert not path.exists()


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_get_retries_429_with_retry_after_without_leaking_key() -> None:
    responses = [
        _Response(429, headers={"Retry-After": "0.25"}),
        _Response(200, {"rows": []}),
    ]
    calls: list[dict] = []
    sleeps: list[float] = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return responses.pop(0)

    response = sidecar._get(
        "https://example.invalid/ctb/new",
        api_key="private-key",
        retries=3,
        request_get=fake_get,
        sleep_fn=sleeps.append,
    )
    assert response.status_code == 200
    assert len(calls) == 2
    assert calls[0]["headers"][sidecar.AUTH_HEADER] == "private-key"
    assert sleeps == [0.25]


def test_materializer_is_credit_guarded_resumable_and_key_free(tmp_path: Path) -> None:
    output = tmp_path / "rows.jsonl"
    blocks = ({"label": "tiny", "start": "2026-07-01", "end": "2026-07-02", "expected_sessions": 2},)
    calendar = ["2026-07-01", "2026-07-02", "2026-07-03"]
    calls: list[dict] = []
    secret = "do-not-persist-this-key"

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return {
            "creditsUsed": 1.0,
            "creditsLeft": 250.0,
            "rows": [
                {"date": kwargs["from_date"], "costToBorrowNew": 2.0},
                {"date": kwargs["to_date"], "costToBorrowNew": 2.5},
            ],
            "echoedSecret": kwargs["api_key"],
        }

    summary = sidecar.materialize_historical_blocks(
        trading_dates=calendar,
        tickers=("AAPL", "MSFT"),
        blocks=blocks,
        output_path=output,
        api_key=secret,
        fetcher=fake_fetch,
        exchange_by_ticker={"AAPL": "NASDAQ", "MSFT": "NASDAQ"},
        credit_budget=10,
        min_credits_left=250,
        max_requests=2,
        request_interval_s=0,
        collected_at="2026-07-18T00:00:00Z",
    )
    assert summary["status"] == "credit_guard_stopped"
    assert summary["stop_reason"] == "reported_credit_floor_reached"
    assert summary["requests_made"] == 1
    assert len(calls) == 1
    assert summary["request_records"][0]["credits_left"] == 250.0
    assert len(sidecar.load_normalised_rows(output)) == 2
    assert secret not in output.read_text(encoding="utf-8")
    assert secret not in json.dumps(summary)


def test_daily_refresh_rotates_only_four_oldest_and_uses_incremental_ranges(tmp_path: Path) -> None:
    output = tmp_path / "rows.jsonl"
    tickers = ("AAPL", "MSFT", "META", "GOOG", "AMZN")
    last_days = {
        "AAPL": "2026-07-01",
        "MSFT": "2026-07-02",
        "META": "2026-07-03",
        "GOOG": "2026-07-04",
        "AMZN": "2026-07-05",
    }
    sidecar.append_normalised_rows_atomic(
        [_row(ticker, day) for ticker, day in last_days.items()], path=output
    )
    calls: list[dict] = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return {
            "creditsUsed": 1.0,
            "creditsLeft": 900.0,
            "rows": [{"date": kwargs["from_date"], "costToBorrowNew": 4.0}],
        }

    calendar = [
        (date(2026, 7, 1) + timedelta(days=offset)).isoformat() for offset in range(25)
    ]
    result = sidecar.materialize_daily_refresh(
        as_of="2026-07-20",
        trading_dates=calendar,
        tickers=tickers,
        output_path=output,
        api_key="in-memory-only",
        fetcher=fake_fetch,
        exchange_by_ticker={ticker: "NASDAQ" for ticker in tickers},
        max_refresh_tickers=4,
        min_refresh_age_days=5,
        credit_budget=10,
        min_credits_left=250,
        estimated_credits_per_request=1,
        request_interval_s=0,
        collected_at="2026-07-20T00:00:00Z",
    )
    assert result["selected_tickers"] == ["AAPL", "MSFT", "META", "GOOG"]
    assert result["requests_made"] == 4
    assert [call["from_date"] for call in calls] == [
        "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"
    ]
    assert all(call["to_date"] == "2026-07-20" for call in calls)
    assert "AMZN" not in [call["ticker"] for call in calls]
