from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import sec_tender_price_history as prices


SECRET = "unit-test-ortex-key-never-persist"


def _row(day: str, close: float = 10.5) -> dict:
    return {
        "date": day,
        "open": 10.0,
        "high": 11.0,
        "low": 9.5,
        "close": close,
        "volume": 1234,
    }


class _Response:
    def __init__(
        self,
        status_code: int,
        payload: dict | None = None,
        headers: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload


def test_key_loader_uses_only_environment_or_fixed_secret_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "secrets" / "ortex.txt"
    secret_file.parent.mkdir()
    secret_file.write_text("file-only-key\n", encoding="utf-8")
    monkeypatch.setattr(prices, "ORTEX_KEY_FILE", secret_file)
    monkeypatch.delenv("ORTEX_API_KEY", raising=False)
    assert prices.load_ortex_api_key() == "file-only-key"
    monkeypatch.setenv("ORTEX_API_KEY", "environment-key")
    assert prices.load_ortex_api_key() == "environment-key"


def test_thirty_calendar_day_chunks_are_inclusive_and_consecutive() -> None:
    chunks = prices.split_calendar_date_chunks("2025-01-01", "2025-03-02")
    assert chunks == (
        ("2025-01-01", "2025-01-30"),
        ("2025-01-31", "2025-03-01"),
        ("2025-03-02", "2025-03-02"),
    )
    for index, (start, end) in enumerate(chunks):
        assert (date.fromisoformat(end) - date.fromisoformat(start)).days + 1 <= 30
        if index:
            assert date.fromisoformat(start) == date.fromisoformat(
                chunks[index - 1][1]
            ) + timedelta(days=1)
    with pytest.raises(ValueError, match="between 1 and 30"):
        prices.split_calendar_date_chunks(
            "2025-01-01", "2025-02-01", max_calendar_days=31
        )


def test_ortex_uses_historical_ticker_param_on_every_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)
    calls: list[dict] = []

    def fake_fetch(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        index = len(calls)
        return {
            "creditsUsed": 0.35,
            "creditsLeft": 1000.0 - 0.35 * index,
            "rows": [_row(kwargs["params"]["from_date"])],
        }

    result = prices.fetch_ortex_closing_price_history(
        "old",
        "NASDAQ",
        "2025-01-01",
        "2025-01-31",
        ticker_as_of_date="2025-01-15",
        credit_budget=1.0,
        estimated_credits_per_request=0.35,
        request_interval_seconds=0,
        fetcher=fake_fetch,
        fetched_at="2026-07-19T00:00:00Z",
    )

    assert len(calls) == 2
    assert all(
        call["url"].endswith("/api/v1/stock/nasdaq/OLD/closing_prices")
        for call in calls
    )
    assert [call["params"] for call in calls] == [
        {
            "from_date": "2025-01-01",
            "to_date": "2025-01-30",
            "ticker_as_of_date": "2025-01-15",
        },
        {
            "from_date": "2025-01-31",
            "to_date": "2025-01-31",
            "ticker_as_of_date": "2025-01-15",
        },
    ]
    assert all(call["headers"][prices.ORTEX_AUTH_HEADER] == SECRET for call in calls)
    assert result["ticker_as_of_date"] == "2025-01-15"
    assert [row["date"] for row in result["rows"]] == ["2025-01-01", "2025-01-31"]


def test_closing_prices_accepts_current_ortex_data_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)

    result = prices.fetch_ortex_closing_price_history(
        "OLD",
        "nasdaq",
        "2025-01-02",
        "2025-01-02",
        ticker_as_of_date="2025-01-02",
        credit_budget=1.0,
        request_interval_seconds=0,
        fetcher=lambda url, **kwargs: {
            "company": "Example Corp",
            "currency": "USD",
            "length": 1,
            "data": [_row("2025-01-02")],
            "creditsUsed": 0.35,
            "creditsLeft": 999.65,
        },
    )

    assert result["rows"] == [_row("2025-01-02")]


def test_closing_prices_accepts_exact_ortex_no_data_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)

    result = prices.fetch_ortex_closing_price_history(
        "OLD",
        "nasdaq",
        "2025-01-02",
        "2025-01-02",
        ticker_as_of_date="2025-01-02",
        credit_budget=1.0,
        request_interval_seconds=0,
        fetcher=lambda url, **kwargs: {
            "company": "Example Corp",
            "currency": "USD",
            "length": 0,
            "data": {"message": "No data returned for the given query parameters"},
            "creditsUsed": 0.35,
            "creditsLeft": 999.65,
        },
    )

    assert result["rows"] == []


def test_closing_prices_rejects_unrecognized_mapping_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)

    with pytest.raises(prices.OrtexPayloadError, match="list of objects"):
        prices.fetch_ortex_closing_price_history(
            "OLD",
            "nasdaq",
            "2025-01-02",
            "2025-01-02",
            ticker_as_of_date="2025-01-02",
            credit_budget=1.0,
            request_interval_seconds=0,
            fetcher=lambda url, **kwargs: {
                "data": {"message": "unexpected provider response"},
                "creditsUsed": 0.35,
                "creditsLeft": 999.65,
            },
        )


def test_pagination_merges_sorts_and_deduplicates_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)
    calls: list[dict] = []
    next_url = (
        "https://api.ortex.com/api/v1/stock/nasdaq/OLD/closing_prices?cursor=page2"
    )

    def fake_fetch(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        if "cursor=page2" not in url:
            return {
                "creditsUsed": 0.35,
                "creditsLeft": 999.65,
                "rows": [_row("2025-01-02"), _row("2025-01-01")],
                "paginationLinks": {"next": next_url},
            }
        return {
            "creditsUsed": 0.35,
            "creditsLeft": 999.3,
            "rows": [_row("2025-01-02"), _row("2025-01-03")],
            "paginationLinks": {"next": None},
        }

    result = prices.fetch_ortex_closing_price_history(
        "OLD",
        "nasdaq",
        "2025-01-01",
        "2025-01-03",
        ticker_as_of_date="2025-01-01",
        credit_budget=1.0,
        estimated_credits_per_request=0.35,
        request_interval_seconds=0,
        fetcher=fake_fetch,
    )

    assert [row["date"] for row in result["rows"]] == [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
    ]
    assert result["request_metadata"]["duplicate_rows_removed"] == 1
    assert result["request_metadata"]["successful_requests"] == 2
    assert result["request_metadata"]["credits_used"] == pytest.approx(0.7)
    assert calls[1]["url"] == next_url
    assert calls[1]["params"] == {"ticker_as_of_date": "2025-01-01"}


def test_credit_floor_stops_before_the_next_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)
    calls: list[dict] = []

    def fake_fetch(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return {
            "creditsUsed": 0.5,
            "creditsLeft": 250.25,
            "rows": [_row(kwargs["params"]["from_date"])],
        }

    with pytest.raises(
        prices.OrtexCreditGuardError,
        match="projected_minimum_credits_left_breached",
    ):
        prices.fetch_ortex_closing_price_history(
            "OLD",
            "NASDAQ",
            "2025-01-01",
            "2025-01-31",
            ticker_as_of_date="2025-01-01",
            credit_budget=2.0,
            min_credits_left=250,
            estimated_credits_per_request=0.5,
            request_interval_seconds=0,
            fetcher=fake_fetch,
        )
    assert len(calls) == 1


def test_credit_budget_can_block_before_any_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)
    calls: list[dict] = []

    with pytest.raises(prices.OrtexCreditGuardError, match="projected_credit_budget"):
        prices.fetch_ortex_closing_price_history(
            "OLD",
            "NASDAQ",
            "2025-01-01",
            "2025-01-02",
            ticker_as_of_date="2025-01-01",
            credit_budget=0.25,
            estimated_credits_per_request=0.35,
            request_interval_seconds=0,
            fetcher=lambda url, **kwargs: calls.append({"url": url, **kwargs}),
        )
    assert calls == []


def test_retry_is_bounded_and_honors_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)
    responses = [
        _Response(429, headers={"Retry-After": "0.1"}),
        _Response(
            200,
            {
                "creditsUsed": 0.35,
                "creditsLeft": 999.65,
                "rows": [_row("2025-01-01")],
            },
        ),
    ]
    sleeps: list[float] = []
    calls: list[dict] = []

    def fake_fetch(url: str, **kwargs):
        calls.append({"url": url, **kwargs})
        return responses.pop(0)

    result = prices.fetch_ortex_closing_price_history(
        "OLD",
        "NASDAQ",
        "2025-01-01",
        "2025-01-01",
        ticker_as_of_date="2025-01-01",
        credit_budget=1.0,
        estimated_credits_per_request=0.35,
        request_interval_seconds=0,
        retries=2,
        fetcher=fake_fetch,
        sleep_fn=sleeps.append,
    )
    assert result["request_metadata"]["http_attempts"] == 2
    assert len(calls) == 2
    assert 0.1 in sleeps


def test_result_and_immutable_cache_never_leak_secret_or_headers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ORTEX_API_KEY", SECRET)

    def fake_fetch(url: str, **kwargs):
        return {
            "creditsUsed": 0.35,
            "creditsLeft": 999.65,
            "rows": [_row("2025-01-01")],
            "requestHeaders": {prices.ORTEX_AUTH_HEADER: SECRET},
            "echoedSecret": SECRET,
        }

    result = prices.fetch_ortex_closing_price_history(
        "OLD",
        "NASDAQ",
        "2025-01-01",
        "2025-01-01",
        ticker_as_of_date="2025-01-01",
        credit_budget=1.0,
        estimated_credits_per_request=0.35,
        request_interval_seconds=0,
        fetcher=fake_fetch,
        fetched_at="2026-07-19T00:00:00Z",
    )
    serialized_result = json.dumps(result)
    assert SECRET not in serialized_result
    assert "requestHeaders" not in serialized_result
    assert prices.ORTEX_AUTH_HEADER not in serialized_result

    target = tmp_path / "OLD_2025-01-01_2025-01-01.json"
    first = prices.write_immutable_price_cache(target, result)
    second = prices.write_immutable_price_cache(target, result)
    assert first["created"] is True
    assert second["idempotent"] is True
    persisted = target.read_text(encoding="utf-8")
    assert SECRET not in persisted
    assert "header" not in persisted.lower()

    changed = json.loads(json.dumps(result))
    changed["rows"][0]["close"] = 10.75
    with pytest.raises(prices.ImmutableCacheConflict, match="different content"):
        prices.write_immutable_price_cache(target, changed)


def test_cache_rejects_header_or_key_fields(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sensitive cache field"):
        prices.write_immutable_price_cache(
            tmp_path / "unsafe.json",
            {
                "request_metadata": {"request_headers": {"Ortex-Api-Key": SECRET}},
                "rows": [],
            },
        )


def test_moomoo_unknown_stock_fails_closed_without_raw_error() -> None:
    calls: list[dict] = []

    def fake_fetch(**kwargs):
        calls.append(kwargs)
        return 1, "Unknown stock code: US.GONE private detail", None

    result = prices.probe_moomoo_current_symbol_history(
        "GONE",
        "2025-01-01",
        "2025-01-10",
        fetcher=fake_fetch,
        ret_ok=0,
    )
    assert calls[0]["code"] == "US.GONE"
    assert result["status"] == "symbol_unavailable"
    assert result["rows"] == []
    assert result["fail_closed"] is True
    assert result["replay_eligible"] is False
    assert result["delisted_consistency"] == "ortex_required"
    assert "private detail" not in json.dumps(result)


def test_moomoo_success_remains_current_symbol_probe_only() -> None:
    result = prices.probe_moomoo_current_symbol_history(
        "LIVE",
        "2025-01-01",
        "2025-01-02",
        fetcher=lambda **kwargs: (
            0,
            [
                {**_row("2025-01-02"), "time_key": "2025-01-02 00:00:00"},
                {**_row("2025-01-01"), "time_key": "2025-01-01 00:00:00"},
            ],
            None,
        ),
        ret_ok=0,
    )
    assert result["status"] == "complete"
    assert [row["date"] for row in result["rows"]] == ["2025-01-01", "2025-01-02"]
    assert result["replay_eligible"] is False
    assert result["role"] == "current_symbol_feasibility_probe"
