"""Secure historical-price adapters for SEC cash-tender replay.

ORTEX is the authoritative price source for this replay because its
``ticker_as_of_date`` lookup can resolve symbols that no longer trade.  The
Moomoo helper in this module is deliberately only a current-symbol feasibility
probe; a successful Moomoo response does not make a replay delisting-safe.

Nothing in this module performs I/O at import time.  Network clients and sleep
functions are injectable so unit tests never need a live service.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
ORTEX_KEY_FILE = REPO_ROOT / "secrets" / "ortex.txt"
ORTEX_BASE_URL = "https://api.ortex.com"
ORTEX_AUTH_HEADER = "Ortex-Api-Key"
ORTEX_CLOSING_PRICE_ENDPOINT = "/api/v1/stock/{exchange}/{ticker}/closing_prices"
MAX_CHUNK_CALENDAR_DAYS = 30
DEFAULT_MIN_CREDITS_LEFT = 250.0
# The closing-price endpoint reported 0.35 credits in the preflight that
# motivated exp-20260719-003.  Callers may raise this reservation when their
# account/endpoint reports a larger page cost; observed costs ratchet it up.
DEFAULT_ESTIMATED_CREDITS_PER_REQUEST = 0.35
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.35
TRANSIENT_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})
PRICE_HISTORY_SCHEMA_VERSION = 1

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_FORBIDDEN_CACHE_KEY_PARTS = (
    "apikey",
    "api_key",
    "authorization",
    "credential",
    "header",
    "secret",
)


class PriceHistoryError(RuntimeError):
    """Base exception for a fail-closed price-history operation."""


class OrtexConfigurationError(PriceHistoryError):
    """ORTEX credentials or request configuration are unavailable/invalid."""


class OrtexHttpError(PriceHistoryError):
    """Sanitized ORTEX transport failure (never includes headers or API key)."""


class OrtexPayloadError(PriceHistoryError):
    """ORTEX returned an unusable or internally inconsistent payload."""


class OrtexCreditGuardError(PriceHistoryError):
    """A request was prevented because its declared credit envelope was unsafe."""

    def __init__(self, reason: str) -> None:
        self.reason = str(reason)
        super().__init__(f"ORTEX credit guard stopped the request: {self.reason}")


class ImmutableCacheConflict(PriceHistoryError):
    """An immutable cache path already contains different bytes."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _iso_date(value: Any, *, field: str) -> str:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        raw = str(value or "").strip()
        try:
            parsed = date.fromisoformat(raw[:10])
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO calendar date") from exc
        if len(raw) < 10:
            raise ValueError(f"{field} must be an ISO calendar date")
    return parsed.isoformat()


def _validated_identifier(value: str, *, field: str) -> str:
    cleaned = str(value or "").strip()
    if not _SYMBOL_RE.fullmatch(cleaned):
        raise ValueError(f"{field} contains unsupported path characters")
    return cleaned


def split_calendar_date_chunks(
    start_date: Any,
    end_date: Any,
    *,
    max_calendar_days: int = MAX_CHUNK_CALENDAR_DAYS,
) -> tuple[tuple[str, str], ...]:
    """Split an inclusive range into consecutive, at-most-30-day chunks."""

    if not 1 <= int(max_calendar_days) <= MAX_CHUNK_CALENDAR_DAYS:
        raise ValueError(
            f"max_calendar_days must be between 1 and {MAX_CHUNK_CALENDAR_DAYS}"
        )
    start_text = _iso_date(start_date, field="start_date")
    end_text = _iso_date(end_date, field="end_date")
    cursor = date.fromisoformat(start_text)
    final = date.fromisoformat(end_text)
    if cursor > final:
        raise ValueError("start_date must be on or before end_date")
    chunks: list[tuple[str, str]] = []
    width = int(max_calendar_days)
    while cursor <= final:
        chunk_end = min(cursor + timedelta(days=width - 1), final)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return tuple(chunks)


def load_ortex_api_key() -> str:
    """Load ORTEX auth only from ``ORTEX_API_KEY`` or ``secrets/ortex.txt``.

    The file is intentionally a fixed repository path under a gitignored
    directory.  There is no explicit-key argument that could accidentally be
    serialized into a runner configuration or artifact.
    """

    env_key = os.environ.get("ORTEX_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        raw = ORTEX_KEY_FILE.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise OrtexConfigurationError(
            "ORTEX API key is unavailable; set ORTEX_API_KEY or secrets/ortex.txt"
        ) from exc
    except OSError as exc:
        raise OrtexConfigurationError("ORTEX API key file could not be read") from exc
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) != 1:
        raise OrtexConfigurationError("secrets/ortex.txt must contain exactly one key line")
    return lines[0]


def _finite_nonnegative(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise OrtexPayloadError(f"ORTEX {field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OrtexPayloadError(f"ORTEX {field} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise OrtexPayloadError(f"ORTEX {field} must be finite and non-negative")
    return number


def _credit_metadata(payload: Mapping[str, Any]) -> tuple[float, float]:
    if "creditsUsed" not in payload or "creditsLeft" not in payload:
        raise OrtexPayloadError("ORTEX response omitted creditsUsed/creditsLeft")
    return (
        _finite_nonnegative(payload["creditsUsed"], field="creditsUsed"),
        _finite_nonnegative(payload["creditsLeft"], field="creditsLeft"),
    )


def _response_parts(response: Any) -> tuple[int, Mapping[str, Any], Mapping[str, Any]]:
    """Return status/body/headers from a response-like object or test mapping."""

    if isinstance(response, Mapping):
        return 200, response, {}
    try:
        status = int(response.status_code)
    except (AttributeError, TypeError, ValueError) as exc:
        raise OrtexHttpError("ORTEX fetcher returned no HTTP status") from exc
    headers = getattr(response, "headers", {})
    if not isinstance(headers, Mapping):
        headers = {}
    if status != 200:
        return status, {}, headers
    try:
        payload = response.json()
    except Exception:
        raise OrtexPayloadError("ORTEX response was not valid JSON") from None
    if not isinstance(payload, Mapping):
        raise OrtexPayloadError("ORTEX response JSON must be an object")
    return status, payload, headers


def _request_ortex_json(
    url: str,
    *,
    params: Mapping[str, Any] | None,
    api_key: str,
    requester: Callable[..., Any],
    timeout_seconds: float,
    retries: int,
    sleep_fn: Callable[[float], None],
    request_interval_seconds: float,
) -> tuple[Mapping[str, Any], int]:
    """Issue one logical GET, retrying only bounded transient failures."""

    headers = {ORTEX_AUTH_HEADER: api_key, "Accept": "application/json"}
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        if attempt:
            sleep_fn(float(request_interval_seconds))
        try:
            response = requester(
                url,
                headers=headers,
                params=dict(params or {}),
                timeout=float(timeout_seconds),
            )
        except Exception:
            if attempt + 1 >= attempts:
                raise OrtexHttpError("ORTEX request failed after bounded retries") from None
            sleep_fn(min(30.0, float(2**attempt)))
            continue
        status, payload, response_headers = _response_parts(response)
        if status == 200:
            return payload, attempt + 1
        if status not in TRANSIENT_HTTP_STATUS or attempt + 1 >= attempts:
            raise OrtexHttpError(f"ORTEX request failed with HTTP {status}")
        retry_after = response_headers.get("Retry-After")
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            delay = float(2**attempt)
        sleep_fn(min(30.0, max(0.0, delay)))
    raise OrtexHttpError("ORTEX request failed after bounded retries")


def _first_present(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def _price_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise OrtexPayloadError(f"price row {field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OrtexPayloadError(f"price row {field} must be numeric") from exc
    if not math.isfinite(result) or result <= 0:
        raise OrtexPayloadError(f"price row {field} must be finite and positive")
    return result


def _volume_number(value: Any) -> int | float:
    if isinstance(value, bool):
        raise OrtexPayloadError("price row volume must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OrtexPayloadError("price row volume must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise OrtexPayloadError("price row volume must be finite and non-negative")
    return int(result) if result.is_integer() else result


def normalize_closing_price_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize an ORTEX/Moomoo daily row to the replay's six-field schema."""

    if not isinstance(row, Mapping):
        raise OrtexPayloadError("price row must be an object")
    try:
        day = _iso_date(
            _first_present(row, ("date", "tradingDate", "priceDate", "time_key")),
            field="price row date",
        )
    except ValueError as exc:
        raise OrtexPayloadError("price row date must be an ISO calendar date") from exc
    opened = _price_number(_first_present(row, ("open", "openPrice")), field="open")
    high = _price_number(_first_present(row, ("high", "highPrice")), field="high")
    low = _price_number(_first_present(row, ("low", "lowPrice")), field="low")
    closed = _price_number(_first_present(row, ("close", "closePrice")), field="close")
    volume = _volume_number(_first_present(row, ("volume", "shareVolume")))
    if low > min(opened, high, closed) or high < max(opened, low, closed):
        raise OrtexPayloadError(f"price row {day} has inconsistent high/low bounds")
    return {
        "date": day,
        "open": opened,
        "high": high,
        "low": low,
        "close": closed,
        "volume": volume,
    }


def _rows_from_payload(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    # ORTEX's closing-prices endpoint currently returns its observations under
    # ``data``.  Some list endpoints (and the generated examples used by older
    # adapters) use ``rows``, so accept both without weakening validation.
    rows = payload.get("data") if "data" in payload else payload.get("rows")
    if rows is None:
        return []
    if rows == {"message": "No data returned for the given query parameters"}:
        return []
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise OrtexPayloadError("ORTEX data/rows must be a list of objects")
    return rows


def _pagination_next(payload: Mapping[str, Any]) -> str | None:
    links = payload.get("paginationLinks", payload.get("pagination_links"))
    if links is None:
        return None
    if not isinstance(links, Mapping):
        raise OrtexPayloadError("ORTEX paginationLinks must be an object")
    value = links.get("next")
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise OrtexPayloadError("ORTEX pagination next link must be text")
    return value


def _safe_next_url(next_link: str, *, current_url: str, base_url: str) -> str:
    resolved = urljoin(current_url, next_link)
    expected = urlparse(base_url)
    actual = urlparse(resolved)
    if (actual.scheme.lower(), actual.netloc.lower()) != (
        expected.scheme.lower(),
        expected.netloc.lower(),
    ):
        raise OrtexPayloadError("ORTEX pagination attempted to change API origin")
    for name, _ in parse_qsl(actual.query, keep_blank_values=True):
        canonical = name.lower().replace("-", "_")
        if canonical in {"api_key", "apikey", "authorization"}:
            raise OrtexPayloadError("ORTEX pagination link contained credential material")
    return resolved


def _check_credit_before_request(
    *,
    credits_used: float,
    credit_budget: float,
    credits_left: float | None,
    min_credits_left: float,
    projected_cost: float,
) -> None:
    if credits_used + projected_cost > credit_budget + 1e-12:
        raise OrtexCreditGuardError("projected_credit_budget_exceeded")
    if credits_left is not None and credits_left - projected_cost < min_credits_left:
        raise OrtexCreditGuardError("projected_minimum_credits_left_breached")


def fetch_ortex_closing_price_history(
    ticker: str,
    exchange: str,
    start_date: Any,
    end_date: Any,
    *,
    ticker_as_of_date: Any,
    credit_budget: float,
    min_credits_left: float = DEFAULT_MIN_CREDITS_LEFT,
    estimated_credits_per_request: float = DEFAULT_ESTIMATED_CREDITS_PER_REQUEST,
    max_calendar_days: int = MAX_CHUNK_CALENDAR_DAYS,
    max_pages_per_chunk: int = 100,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    timeout_seconds: float = 30.0,
    retries: int = 4,
    base_url: str = ORTEX_BASE_URL,
    session: Any | None = None,
    fetcher: Callable[..., Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    """Fetch a complete ORTEX daily-price range under a hard credit envelope.

    ``credit_budget`` is intentionally required.  Before every page/chunk the
    adapter reserves the larger of the caller's estimate and the largest
    observed page cost.  Every successful body must report both
    ``creditsUsed`` and ``creditsLeft``; missing metadata fails closed.
    """

    symbol = _validated_identifier(ticker, field="ticker").upper()
    venue = _validated_identifier(exchange, field="exchange").lower()
    ticker_day = _iso_date(ticker_as_of_date, field="ticker_as_of_date")
    chunks = split_calendar_date_chunks(
        start_date, end_date, max_calendar_days=max_calendar_days
    )
    range_start, range_end = chunks[0][0], chunks[-1][1]
    try:
        budget = float(credit_budget)
        floor = float(min_credits_left)
        estimate = float(estimated_credits_per_request)
    except (TypeError, ValueError) as exc:
        raise ValueError("credit controls must be numeric") from exc
    if not all(math.isfinite(value) for value in (budget, floor, estimate)):
        raise ValueError("credit controls must be finite")
    if budget <= 0 or floor < 0 or estimate <= 0:
        raise ValueError("credit budget/estimate must be positive and floor non-negative")
    if int(max_pages_per_chunk) <= 0 or int(retries) <= 0:
        raise ValueError("max pages and retries must be positive")
    if float(request_interval_seconds) < 0 or float(timeout_seconds) <= 0:
        raise ValueError("request interval/timeout is invalid")

    parsed_base = urlparse(str(base_url))
    if parsed_base.scheme.lower() != "https" or not parsed_base.netloc:
        raise ValueError("ORTEX base_url must be an absolute HTTPS origin")
    endpoint_path = ORTEX_CLOSING_PRICE_ENDPOINT.format(exchange=venue, ticker=symbol)
    first_url = str(base_url).rstrip("/") + "/" + endpoint_path.lstrip("/")
    api_key = load_ortex_api_key()

    owned_session = None
    if fetcher is not None:
        requester = fetcher
    elif session is not None:
        requester = session.get
    else:
        owned_session = requests.Session()
        requester = owned_session.get

    by_date: dict[str, dict[str, Any]] = {}
    duplicate_rows = 0
    out_of_range_rows = 0
    successful_requests = 0
    http_attempts = 0
    credits_used_total = 0.0
    credits_left: float | None = None
    projected_cost = estimate
    request_records: list[dict[str, Any]] = []

    try:
        for chunk_index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            seen_pagination_urls: set[str] = set()
            current_url = first_url
            params: Mapping[str, Any] | None = {
                "from_date": chunk_start,
                "to_date": chunk_end,
                "ticker_as_of_date": ticker_day,
            }
            page_index = 1
            while True:
                if page_index > int(max_pages_per_chunk):
                    raise OrtexPayloadError("ORTEX pagination exceeded max_pages_per_chunk")
                _check_credit_before_request(
                    credits_used=credits_used_total,
                    credit_budget=budget,
                    credits_left=credits_left,
                    min_credits_left=floor,
                    projected_cost=projected_cost,
                )
                if successful_requests:
                    sleep_fn(float(request_interval_seconds))
                payload, attempts = _request_ortex_json(
                    current_url,
                    params=params,
                    api_key=api_key,
                    requester=requester,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    sleep_fn=sleep_fn,
                    request_interval_seconds=request_interval_seconds,
                )
                http_attempts += attempts
                successful_requests += 1
                page_credits_used, page_credits_left = _credit_metadata(payload)
                credits_used_total += page_credits_used
                credits_left = page_credits_left
                projected_cost = max(projected_cost, page_credits_used)
                if credits_used_total > budget + 1e-12:
                    raise OrtexCreditGuardError("reported_credit_budget_exceeded")
                if credits_left < floor:
                    raise OrtexCreditGuardError("reported_minimum_credits_left_breached")

                raw_rows = _rows_from_payload(payload)
                accepted_on_page = 0
                for raw_row in raw_rows:
                    row = normalize_closing_price_row(raw_row)
                    if not (range_start <= row["date"] <= range_end):
                        out_of_range_rows += 1
                        continue
                    old = by_date.get(row["date"])
                    if old is not None:
                        duplicate_rows += 1
                        if old != row:
                            raise OrtexPayloadError(
                                f"ORTEX returned conflicting duplicate price row for {row['date']}"
                            )
                        continue
                    by_date[row["date"]] = row
                    accepted_on_page += 1
                request_records.append(
                    {
                        "chunk_index": chunk_index,
                        "page_index": page_index,
                        "from_date": chunk_start,
                        "to_date": chunk_end,
                        "ticker_as_of_date": ticker_day,
                        "rows_received": len(raw_rows),
                        "rows_accepted": accepted_on_page,
                        "credits_used": page_credits_used,
                        "credits_left": page_credits_left,
                    }
                )

                next_link = _pagination_next(payload)
                if not next_link:
                    break
                next_url = _safe_next_url(
                    next_link, current_url=current_url, base_url=str(base_url)
                )
                if next_url in seen_pagination_urls:
                    raise OrtexPayloadError("ORTEX pagination link repeated")
                seen_pagination_urls.add(next_url)
                current_url = next_url
                query_names = {
                    name.lower().replace("-", "_")
                    for name, _ in parse_qsl(urlparse(next_url).query, keep_blank_values=True)
                }
                # Preserve the historical-symbol identity on every page even
                # when a provider next-link omits the original query fields.
                params = (
                    None
                    if "ticker_as_of_date" in query_names
                    else {"ticker_as_of_date": ticker_day}
                )
                page_index += 1
    finally:
        if owned_session is not None:
            owned_session.close()

    return {
        "schema_version": PRICE_HISTORY_SCHEMA_VERSION,
        "source": "ortex_closing_prices",
        "status": "complete",
        "ticker": symbol,
        "exchange": venue.upper(),
        "ticker_as_of_date": ticker_day,
        "start_date": range_start,
        "end_date": range_end,
        "fetched_at": fetched_at or _utc_now(),
        "rows": [by_date[day] for day in sorted(by_date)],
        "request_metadata": {
            "endpoint": ORTEX_CLOSING_PRICE_ENDPOINT,
            "max_chunk_calendar_days": int(max_calendar_days),
            "chunk_count": len(chunks),
            "successful_requests": successful_requests,
            "http_attempts": http_attempts,
            "credits_used": round(credits_used_total, 8),
            "credits_left": credits_left,
            "credit_budget": budget,
            "minimum_credits_left": floor,
            "duplicate_rows_removed": duplicate_rows,
            "out_of_range_rows_removed": out_of_range_rows,
            "requests": request_records,
        },
        "delisted_consistency": "ortex_required_and_satisfied",
        "trade_enabled": False,
    }


def _iter_records(value: Any) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            records = value.to_dict("records")
        except TypeError:
            records = None
        if isinstance(records, list):
            value = records
    if isinstance(value, Mapping):
        rows = value.get("rows", [])
        value = rows
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PriceHistoryError("Moomoo history response rows were not tabular")
    if any(not isinstance(row, Mapping) for row in value):
        raise PriceHistoryError("Moomoo history response contained a non-object row")
    return list(value)


def _is_unknown_symbol_message(value: Any) -> bool:
    message = str(value or "").lower()
    markers = (
        "unknown stock",
        "unknown symbol",
        "stock code is wrong",
        "stock does not exist",
        "security not found",
    )
    return any(marker in message for marker in markers)


def probe_moomoo_current_symbol_history(
    ticker: str,
    start_date: Any,
    end_date: Any,
    *,
    exchange_prefix: str = "US",
    fetcher: Callable[..., Any] | None = None,
    context: Any | None = None,
    ret_ok: Any | None = None,
    host: str = "127.0.0.1",
    port: int = 11111,
    max_pages: int = 100,
) -> dict[str, Any]:
    """Probe Moomoo daily history for a *current* symbol, failing closed.

    The function never persists anything and returns no OpenD configuration or
    SDK error text.  Even a complete response remains ineligible as the sole
    merger-arbitrage replay source because renamed/delisted symbols require
    ORTEX ``ticker_as_of_date`` resolution.
    """

    symbol = _validated_identifier(ticker, field="ticker").upper()
    prefix = _validated_identifier(exchange_prefix, field="exchange_prefix").upper()
    start_text = _iso_date(start_date, field="start_date")
    end_text = _iso_date(end_date, field="end_date")
    if start_text > end_text:
        raise ValueError("start_date must be on or before end_date")
    if int(max_pages) <= 0:
        raise ValueError("max_pages must be positive")

    owned_context = None
    if fetcher is None:
        if context is None:
            try:
                from moomoo import AuType, KLType, OpenQuoteContext, RET_OK
            except Exception:
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": "sdk_unavailable",
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            ret_ok = RET_OK
            try:
                owned_context = OpenQuoteContext(host=host, port=int(port))
            except Exception:
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": "opend_unavailable",
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            context = owned_context

            def fetcher(**kwargs: Any) -> Any:
                return context.request_history_kline(
                    kwargs["code"],
                    start=kwargs["start"],
                    end=kwargs["end"],
                    ktype=KLType.K_DAY,
                    autype=AuType.NONE,
                    max_count=kwargs["max_count"],
                    page_req_key=kwargs["page_req_key"],
                    extended_time=False,
                )
        elif ret_ok is None:
            ret_ok = 0
            fetcher = lambda **kwargs: context.request_history_kline(  # noqa: E731
                kwargs["code"],
                start=kwargs["start"],
                end=kwargs["end"],
                max_count=kwargs["max_count"],
                page_req_key=kwargs["page_req_key"],
            )
    if ret_ok is None:
        ret_ok = 0

    by_date: dict[str, dict[str, Any]] = {}
    page_key: Any = None
    pages = 0
    try:
        while True:
            if pages >= int(max_pages):
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": "pagination_limit",
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            try:
                response = fetcher(
                    code=f"{prefix}.{symbol}",
                    start=start_text,
                    end=end_text,
                    max_count=1000,
                    page_req_key=page_key,
                )
            except Exception:
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": "query_failed",
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            if not isinstance(response, tuple) or len(response) != 3:
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": "query_failed",
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            result_code, raw_rows, next_key = response
            if result_code != ret_ok:
                status = (
                    "symbol_unavailable"
                    if _is_unknown_symbol_message(raw_rows)
                    else "query_failed"
                )
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": status,
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            pages += 1
            try:
                records = _iter_records(raw_rows)
                for raw_row in records:
                    row = normalize_closing_price_row(raw_row)
                    if start_text <= row["date"] <= end_text:
                        old = by_date.get(row["date"])
                        if old is not None and old != row:
                            raise PriceHistoryError(
                                f"Moomoo returned conflicting duplicate row for {row['date']}"
                            )
                        by_date[row["date"]] = row
            except PriceHistoryError:
                return {
                    "source": "moomoo_current_symbol_history",
                    "status": "invalid_rows",
                    "ticker": symbol,
                    "rows": [],
                    "role": "current_symbol_feasibility_probe",
                    "delisted_consistency": "ortex_required",
                    "replay_eligible": False,
                    "fail_closed": True,
                }
            if next_key is None:
                break
            page_key = next_key
    finally:
        if owned_context is not None:
            try:
                owned_context.close()
            except Exception:
                pass

    return {
        "source": "moomoo_current_symbol_history",
        "status": "complete",
        "ticker": symbol,
        "start_date": start_text,
        "end_date": end_text,
        "rows": [by_date[day] for day in sorted(by_date)],
        "request_metadata": {"pages": pages, "current_symbol_only": True},
        "role": "current_symbol_feasibility_probe",
        "delisted_consistency": "ortex_required",
        "replay_eligible": False,
        "fail_closed": False,
    }


def _assert_cache_safe(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            canonical = key.lower().replace("-", "_")
            if canonical == "key" or any(part in canonical for part in _FORBIDDEN_CACHE_KEY_PARTS):
                raise ValueError(f"refusing sensitive cache field at {path}.{key}")
            _assert_cache_safe(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_cache_safe(child, path=f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if "ortex-api-key" in lowered or lowered.startswith("authorization:"):
            raise ValueError(f"refusing sensitive cache value at {path}")


def write_immutable_price_cache(path: str | Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Atomically create an immutable JSON cache, allowing exact idempotency.

    A different document can never replace an existing cache.  The temp file is
    fsynced and atomically hard-linked into place, so readers cannot observe a
    partial JSON document and concurrent writers cannot win by overwriting.
    """

    if not isinstance(payload, Mapping):
        raise TypeError("price cache payload must be a mapping")
    if not isinstance(payload.get("request_metadata"), Mapping):
        raise ValueError("price cache payload must include request_metadata")
    _assert_cache_safe(payload)
    serialized = (
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    # Defense in depth: even if a caller hid the key under an innocuous field,
    # the currently configured secret must not appear in immutable bytes.
    try:
        configured_secret = load_ortex_api_key()
    except OrtexConfigurationError:
        configured_secret = ""
    if len(configured_secret) >= 8 and configured_secret.encode("utf-8") in serialized:
        raise ValueError("refusing to persist configured ORTEX secret")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(serialized).hexdigest()
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temp_path = Path(temp_name)
    created = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, target)
            created = True
        except FileExistsError:
            try:
                existing = target.read_bytes()
            except OSError as exc:
                raise ImmutableCacheConflict(
                    f"immutable cache already exists and could not be verified: {target}"
                ) from exc
            if existing != serialized:
                raise ImmutableCacheConflict(
                    f"immutable cache already exists with different content: {target}"
                )
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
    return {
        "path": str(target),
        "sha256": digest,
        "created": created,
        "idempotent": not created,
        "bytes": len(serialized),
    }


__all__ = [
    "DEFAULT_MIN_CREDITS_LEFT",
    "ImmutableCacheConflict",
    "MAX_CHUNK_CALENDAR_DAYS",
    "ORTEX_CLOSING_PRICE_ENDPOINT",
    "OrtexConfigurationError",
    "OrtexCreditGuardError",
    "OrtexHttpError",
    "OrtexPayloadError",
    "fetch_ortex_closing_price_history",
    "load_ortex_api_key",
    "normalize_closing_price_row",
    "probe_moomoo_current_symbol_history",
    "split_calendar_date_chunks",
    "write_immutable_price_cache",
]
