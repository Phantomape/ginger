"""ORTEX short-interest / borrow-economics sidecar (default-off data fetcher).

ORTEX is the keystone PIT borrow-fee / utilization / short-interest source that the
repo has lacked (see alpha-saturation notes). This module is a *data fetcher only* --
it pulls ORTEX series and persists them under ``data/non_ohlcv/ortex/``. It does NOT
touch any buy/sell/rank/sizing logic, so it ships as a default-off sidecar.

Security
--------
The API key is read from the ``ORTEX_API_KEY`` environment variable (preferred), or,
as a fallback, from a gitignored ``.env`` file at the repo root. The key is NEVER
hardcoded and NEVER committed -- ``.env`` is in ``.gitignore``; only ``.env.example``
(no real value) is tracked. Set the key portably with, on Windows:

    setx ORTEX_API_KEY "your-real-key"      # persists for the user across reboots

Endpoint paths
--------------
ORTEX's exact REST path layout is not published in a scrapable form. Rather than
hardcode a guess, ``--discover`` probes a list of candidate path templates with your
key (or the public ``TEST`` key) and reports which returns HTTP 200. Once you know the
working template, pass it via ``--path`` or set ``ORTEX_SI_PATH`` to skip discovery.

Confirmed facts (docs.ortex.com): auth header is ``Ortex-Api-Key``; the public trial
key is the literal string ``TEST``; endpoint families are short interest (daily),
cost-to-borrow (all / new), and days-to-cover.

Examples
--------
    # 1) Find the working short-interest path using the public trial key (no real key needed):
    python quant/ortex_data_sidecar.py --discover --exchange NASDAQ --ticker AAPL --key TEST

    # 2) Fetch short interest for a ticker once you know the path (key from env):
    python quant/ortex_data_sidecar.py --exchange NASDAQ --ticker AAPL \
        --path "/api/v1/{exchange}/{ticker}/short_interest"

    # 3) Arbitrary endpoint + query params, saved to data/non_ohlcv/ortex/:
    python quant/ortex_data_sidecar.py --path "/api/v1/{exchange}/{ticker}/ctb/all" \
        --exchange NASDAQ --ticker AAPL --param from_date=2026-01-01 --param to_date=2026-06-27
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import requests

try:
    from data_paths import atomic_write_text
except ModuleNotFoundError:  # package import in tooling outside quant/
    from quant.data_paths import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "non_ohlcv" / "ortex"
NORMALIZED_ROWS_PATH = DEFAULT_OUTPUT_DIR / "cost_to_borrow_new_rows.jsonl"

AUTH_HEADER = "Ortex-Api-Key"
DEFAULT_BASE_URL = os.environ.get("ORTEX_BASE_URL", "https://api.ortex.com")
TRIAL_KEY = "TEST"

# Verified ORTEX endpoints: name -> (path template, exchange-casing). Confirmed live
# against the API (TEST key). Note the layout quirks discovered empirically:
#   * short_interest has NO "stock/" segment and wants an UPPER-case exchange (NASDAQ);
#   * the borrow / days-to-cover family DOES have "stock/" and wants LOWER-case (nasdaq).
# All borrow/dtc endpoints accept from_date / to_date (YYYY-MM-DD) for historical ranges.
ENDPOINTS = {
    "short_interest": ("/api/v1/{exchange}/{ticker}/short_interest", "upper"),
    "borrow_fee": ("/api/v1/stock/{exchange}/{ticker}/ctb/all", "lower"),       # cost-to-borrow, all loans
    "borrow_fee_new": ("/api/v1/stock/{exchange}/{ticker}/ctb/new", "lower"),   # cost-to-borrow, new loans
    "days_to_cover": ("/api/v1/stock/{exchange}/{ticker}/dtc", "lower"),
}

# Fixed before the exp-20260718-003 fetch.  Every name has 514 archived
# Moomoo broad short-volume dates, so the ORTEX observer can later be joined to
# a genuinely independent price/flow surface without post-result universe
# selection.  This is a research universe, not an executable watchlist.
FIXED_RESEARCH_TICKERS = (
    "AAPL",
    "MSFT",
    "META",
    "GOOG",
    "AMZN",
    "AMD",
    "AVGO",
    "MU",
    "NVDA",
    "CRDO",
    "COIN",
    "DDOG",
    "PLTR",
    "APP",
    "SNOW",
    "CVX",
    "XOM",
    "JPM",
    "GS",
    "TSLA",
)

TICKER_EXCHANGES = {
    ticker: ("NYSE" if ticker in {"SNOW", "CVX", "XOM", "JPM", "GS"} else "NASDAQ")
    for ticker in FIXED_RESEARCH_TICKERS
}

# These calendar boundaries were predeclared before the historical request.
# They are deliberately not recomputed from whatever warehouse happens to be
# current.  ``materialize_historical_blocks`` additionally requires the
# caller's PIT trading calendar to contain exactly 40 sessions inside each
# boundary (the old_thin block relies on the 2025-01-09 NYSE closure).
HISTORICAL_BLOCKS = (
    {
        "label": "old_thin",
        "start": "2024-12-11",
        "end": "2025-02-10",
        "expected_sessions": 40,
    },
    {
        "label": "mid_weak",
        "start": "2025-06-25",
        "end": "2025-08-20",
        "expected_sessions": 40,
    },
    {
        "label": "late_strong",
        "start": "2025-12-22",
        "end": "2026-02-19",
        "expected_sessions": 40,
    },
)

NORMALIZED_SCHEMA_VERSION = 1
NORMALIZED_ROW_FIELDS = frozenset(
    {
        "schema_version",
        "ticker",
        "exchange",
        "provider_date",
        "usable_trade_date",
        "cost_to_borrow_new_pct",
        "collected_at",
        "source_mode",
        "historical_block",
        "request_start_date",
        "request_end_date",
        "source",
        "provider_field",
        "availability_rule",
        "observer_only",
        "trade_enabled",
    }
)
DEFAULT_CREDIT_BUDGET = 190.0
DEFAULT_MIN_CREDITS_LEFT = 250.0
DEFAULT_ESTIMATED_CREDITS_PER_REQUEST = 3.0
DEFAULT_REQUEST_INTERVAL_S = 0.35
DEFAULT_MAX_REQUESTS = len(FIXED_RESEARCH_TICKERS) * len(HISTORICAL_BLOCKS)
TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}


class OrtexHttpError(RuntimeError):
    """Sanitised ORTEX HTTP failure (never includes request headers/key)."""


class CreditGuardStopped(RuntimeError):
    """Raised by strict callers when the credit guard prevents a request."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _date_text(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalise_trading_dates(trading_dates: Iterable[Any]) -> tuple[str, ...]:
    """Return a sorted, unique, validated caller-supplied trading calendar."""
    values: set[str] = set()
    for raw in trading_dates:
        parsed = _date_text(raw)
        if parsed is None:
            raise ValueError(f"invalid caller-supplied trading date: {raw!r}")
        values.add(parsed)
    return tuple(sorted(values))


def next_usable_trade_date(provider_date: Any, trading_dates: Iterable[Any]) -> str:
    """Map a provider date to the strictly *next* supplied market session.

    Same-day use is forbidden even when ORTEX says its daily file is updated
    before the open.  The conservative clock is explicit and replayable.
    """
    provider_day = _date_text(provider_date)
    sessions = normalise_trading_dates(trading_dates)
    if provider_day is None:
        raise ValueError(f"invalid provider_date: {provider_date!r}")
    index = bisect.bisect_right(sessions, provider_day)
    if index >= len(sessions):
        raise ValueError(
            f"trading calendar has no session strictly after provider_date={provider_day}"
        )
    return sessions[index]


def validate_historical_blocks(
    trading_dates: Iterable[Any],
    blocks: Sequence[Mapping[str, Any]] = HISTORICAL_BLOCKS,
) -> dict[str, tuple[str, ...]]:
    """Validate all predeclared blocks against the caller's trading calendar."""
    sessions = normalise_trading_dates(trading_dates)
    if not sessions:
        raise ValueError("trading_dates must be a non-empty caller-supplied calendar")
    validated: dict[str, tuple[str, ...]] = {}
    labels: set[str] = set()
    for block in blocks:
        label = str(block.get("label") or "").strip()
        start = _date_text(block.get("start"))
        end = _date_text(block.get("end"))
        expected = int(block.get("expected_sessions") or 0)
        if not label or label in labels or start is None or end is None or start > end:
            raise ValueError(f"invalid historical block: {dict(block)!r}")
        labels.add(label)
        inside = tuple(day for day in sessions if start <= day <= end)
        if len(inside) != expected:
            raise ValueError(
                f"historical block {label!r} must contain exactly {expected} supplied "
                f"sessions inside {start}..{end}; got {len(inside)}"
            )
        if bisect.bisect_right(sessions, end) >= len(sessions):
            raise ValueError(
                f"trading calendar must extend beyond block {label!r} end={end}"
            )
        validated[label] = inside
    return validated


def normalise_cost_to_borrow_new_rows(
    payload: Mapping[str, Any],
    *,
    ticker: str,
    exchange: str,
    trading_dates: Iterable[Any],
    collected_at: str,
    source_mode: str,
    request_start_date: str,
    request_end_date: str,
    historical_block: str | None = None,
) -> list[dict[str, Any]]:
    """Reduce an ORTEX response to the immutable, key-free observer schema.

    Only the locked ``costToBorrowNew`` field is accepted.  Raw payloads,
    pagination links, request headers, credit metadata, and API keys are never
    written to the sidecar ledger.
    """
    symbol = str(ticker).upper().strip()
    venue = str(exchange).upper().strip()
    start = _date_text(request_start_date)
    end = _date_text(request_end_date)
    if not symbol or start is None or end is None:
        raise ValueError("ticker and valid request date boundaries are required")
    rows = payload.get("rows") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return []
    sessions = normalise_trading_dates(trading_dates)
    normalised: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        provider_day = _date_text(raw.get("date"))
        value = _finite_float(raw.get("costToBorrowNew"))
        if provider_day is None or not (start <= provider_day <= end) or value is None:
            continue
        if provider_day in seen_dates:
            continue
        # Fail closed rather than guessing a weekday/holiday calendar.
        usable_day = next_usable_trade_date(provider_day, sessions)
        seen_dates.add(provider_day)
        normalised.append(
            {
                "schema_version": NORMALIZED_SCHEMA_VERSION,
                "ticker": symbol,
                "exchange": venue,
                "provider_date": provider_day,
                "usable_trade_date": usable_day,
                "cost_to_borrow_new_pct": value,
                "collected_at": str(collected_at),
                "source_mode": str(source_mode),
                "historical_block": historical_block,
                "request_start_date": start,
                "request_end_date": end,
                "source": "ortex_api_cost_to_borrow_new",
                "provider_field": "costToBorrowNew",
                "availability_rule": "strict_next_caller_supplied_trading_session",
                "observer_only": True,
                "trade_enabled": False,
            }
        )
    normalised.sort(key=lambda row: (row["ticker"], row["provider_date"]))
    return normalised


def load_normalised_rows(path: str | Path = NORMALIZED_ROWS_PATH) -> list[dict[str, Any]]:
    """Load the append-only ledger, failing on malformed persisted JSON."""
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        target.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed JSONL at {target}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"non-object JSONL row at {target}:{line_number}")
        rows.append(row)
    return rows


def _normalised_row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("ticker") or "").upper(), str(row.get("provider_date") or ""))


@contextmanager
def _exclusive_ledger_lock(
    path: Path,
    *,
    timeout_s: float = 10.0,
    sleep_fn: Callable[[float], None] = time.sleep,
):
    """Small cross-platform O_EXCL lock protecting read-merge-replace writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii", errors="ignore"))
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out acquiring ORTEX ledger lock: {lock_path}")
            sleep_fn(0.05)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def append_normalised_rows_atomic(
    rows: Iterable[Mapping[str, Any]],
    *,
    path: str | Path = NORMALIZED_ROWS_PATH,
    lock_timeout_s: float = 10.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Atomically append unseen ticker/provider-date rows without rewrites.

    A later provider response for an existing key is deliberately ignored,
    even if its value differs.  That preserves the first locally observed PIT
    row and reports the discrepancy as a conflict for audit.
    """
    target = Path(path)
    incoming = [dict(row) for row in rows]
    for row in incoming:
        unexpected = sorted(set(row) - NORMALIZED_ROW_FIELDS)
        if unexpected:
            raise ValueError(
                "refusing to persist non-normalised ORTEX fields: " + ", ".join(unexpected)
            )
    with _exclusive_ledger_lock(target, timeout_s=lock_timeout_s, sleep_fn=sleep_fn):
        existing = load_normalised_rows(target)
        by_key = {_normalised_row_key(row): row for row in existing}
        appended: list[dict[str, Any]] = []
        duplicates = 0
        conflicts = 0
        for row in sorted(incoming, key=_normalised_row_key):
            key = _normalised_row_key(row)
            if not all(key):
                raise ValueError(f"normalised row missing ticker/provider_date: {row!r}")
            old = by_key.get(key)
            if old is not None:
                duplicates += 1
                if old != row:
                    conflicts += 1
                continue
            by_key[key] = row
            appended.append(row)
        if appended:
            serialised = "\n".join(
                json.dumps(row, sort_keys=True, ensure_ascii=True) for row in existing + appended
            ) + "\n"
            atomic_write_text(serialised, target)
        return {
            "incoming": len(incoming),
            "appended": len(appended),
            "duplicates": duplicates,
            "conflicts": conflicts,
            "total": len(existing) + len(appended),
        }


def _exchange_for(exchange: str, casing: str) -> str:
    return exchange.lower() if casing == "lower" else exchange.upper()


# Candidate path templates probed by --discover. The first that returns HTTP 200 wins.
# Add/trim these as ORTEX's published layout is confirmed; supersede entirely with --path.
SHORT_INTEREST_PATH_CANDIDATES = (
    "/api/v1/{exchange}/{ticker}/short_interest",
    "/api/v1/stock/{exchange}/{ticker}/short_interest",
    "/api/v1/short_interest/{exchange}/{ticker}",
    "/v1/{exchange}/{ticker}/short_interest",
    "/api/v1/{exchange}/{ticker}/si",
)


# Git Bash (MSYS) on Windows rewrites a leading-slash CLI arg like "/api/v1/..." into
# a Windows path, e.g. "C:/Program Files/Git/api/v1/...". That silently corrupts the
# endpoint path (the server then 302s to its marketing homepage). Detect the injected
# drive-letter prefix and recover the intended REST path beginning at /api/ or /v<N>/.
_MSYS_MANGLED_RE = re.compile(r"^[A-Za-z]:[\\/].*?(/(?:api|v\d+)/.*)$")


def normalize_path(path: str) -> str:
    """Undo Git Bash POSIX-path mangling of a leading-slash endpoint argument."""
    if not path:
        return path
    match = _MSYS_MANGLED_RE.match(path)
    return match.group(1) if match else path


# Plaintext key file (one line, just the key). The whole secrets/ dir is gitignored.
SECRETS_KEY_FILE = REPO_ROOT / "secrets" / "ortex.txt"


def load_api_key(explicit: str | None = None) -> str | None:
    """Resolve the key, never hardcoded.

    Priority: explicit arg > ORTEX_API_KEY env var > secrets/ortex.txt > .env file.
    All file sources live under gitignored paths, so the key never enters git.
    """
    if explicit:
        return explicit.strip()
    env = os.environ.get("ORTEX_API_KEY")
    if env:
        return env.strip()
    # secrets/ortex.txt: a one-line plaintext key file (gitignored secrets/ dir).
    if SECRETS_KEY_FILE.exists():
        key = SECRETS_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    # Fallback: minimal .env parse (no python-dotenv dependency). .env is gitignored.
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "ORTEX_API_KEY":
                return value.strip().strip('"').strip("'")
    return None


def _mask(key: str) -> str:
    """Render a key for logs without leaking it (e.g. 'ab..yz')."""
    if not key or key == TRIAL_KEY:
        return key or "<none>"
    return f"{key[:2]}..{key[-2:]}" if len(key) > 4 else "****"


def _get(
    url,
    *,
    api_key,
    params=None,
    timeout=30.0,
    retries=3,
    request_get: Callable[..., requests.Response] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """GET an absolute URL with the auth header; retry/backoff on 429/5xx."""
    headers = {AUTH_HEADER: api_key, "Accept": "application/json"}
    if os.environ.get("ORTEX_DEBUG"):
        masked = {k: (v[:2] + ".." if k == AUTH_HEADER else v) for k, v in headers.items()}
        print(f"[debug] GET url={url!r} headers={masked} params={params or {}}", file=sys.stderr)
    last: requests.Response | None = None
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        resp = request_get(url, headers=headers, params=params or {}, timeout=timeout)
        last = resp
        if resp.status_code not in TRANSIENT_HTTP_STATUS:
            return resp
        if attempt == attempts - 1:
            break
        # Honour a small Retry-After when supplied, while keeping the retry
        # bounded.  The key remains in the header and is never logged.
        retry_after = _finite_float((getattr(resp, "headers", {}) or {}).get("Retry-After"))
        delay = retry_after if retry_after is not None and retry_after >= 0 else 2 ** attempt
        sleep_fn(min(float(delay), 30.0))
    return last  # type: ignore[return-value]


def fetch(
    path_template: str,
    *,
    exchange: str,
    ticker: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    params: dict | None = None,
    timeout: float = 30.0,
    retries: int = 3,
    request_get: Callable[..., requests.Response] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """GET a single ORTEX endpoint (first page) with auth header."""
    path = normalize_path(path_template).format(exchange=exchange, ticker=ticker)
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    return _get(
        url,
        api_key=api_key,
        params=params,
        timeout=timeout,
        retries=retries,
        request_get=request_get,
        sleep_fn=sleep_fn,
    )


def fetch_cost_to_borrow_new_payload(
    *,
    ticker: str,
    exchange: str,
    from_date: str,
    to_date: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
    retries: int = 4,
    request_get: Callable[..., requests.Response] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Mapping[str, Any]:
    """Fetch one bounded CTB-new range and return its in-memory payload.

    This helper never persists the response.  The only persistence path used by
    the observer is ``normalise_cost_to_borrow_new_rows`` followed by the
    append-only ledger merge.
    """
    response = fetch(
        ENDPOINTS["borrow_fee_new"][0],
        exchange=_exchange_for(exchange, ENDPOINTS["borrow_fee_new"][1]),
        ticker=str(ticker).upper(),
        api_key=api_key,
        base_url=base_url,
        params={"from_date": from_date, "to_date": to_date},
        timeout=timeout,
        retries=retries,
        request_get=request_get,
        sleep_fn=sleep_fn,
    )
    if int(response.status_code) != 200:
        raise OrtexHttpError(
            f"ORTEX CTB-new request failed for {str(ticker).upper()} with "
            f"HTTP {int(response.status_code)}"
        )
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise OrtexHttpError(
            f"ORTEX CTB-new response for {str(ticker).upper()} was not JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise OrtexHttpError(
            f"ORTEX CTB-new response for {str(ticker).upper()} was not an object"
        )
    return payload


def _request_credit_metadata(payload: Mapping[str, Any]) -> tuple[float | None, float | None]:
    used = payload.get("creditsUsed", payload.get("credits_used"))
    left = payload.get("creditsLeft", payload.get("credits_left"))
    return (_finite_float(used), _finite_float(left))


def _existing_dates_by_ticker(path: str | Path) -> dict[str, set[str]]:
    by_ticker: dict[str, set[str]] = {}
    for row in load_normalised_rows(path):
        ticker = str(row.get("ticker") or "").upper()
        provider_day = _date_text(row.get("provider_date"))
        if ticker and provider_day:
            by_ticker.setdefault(ticker, set()).add(provider_day)
    return by_ticker


def _credit_stop_reason(
    *,
    requests_made: int,
    max_requests: int,
    credits_used_total: float,
    credit_budget: float,
    credits_left: float | None,
    min_credits_left: float,
    projected_next_cost: float,
) -> str | None:
    if requests_made >= max_requests:
        return "max_requests_reached"
    if credits_used_total + projected_next_cost > credit_budget + 1e-12:
        return "projected_credit_budget_exceeded"
    if credits_left is not None and credits_left - projected_next_cost <= min_credits_left:
        return "projected_credit_floor_reached"
    return None


def _call_range_fetcher(
    fetcher: Callable[..., Any],
    *,
    ticker: str,
    exchange: str,
    start: str,
    end: str,
    api_key: str,
    base_url: str,
    timeout: float,
    retries: int,
    request_get: Callable[..., requests.Response],
    sleep_fn: Callable[[float], None],
) -> Mapping[str, Any]:
    result = fetcher(
        ticker=ticker,
        exchange=exchange,
        from_date=start,
        to_date=end,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        retries=retries,
        request_get=request_get,
        sleep_fn=sleep_fn,
    )
    # Test/adapter fetchers may return (payload, metadata); metadata is ignored
    # because the canonical credit fields are read from the payload itself.
    if isinstance(result, tuple) and result:
        result = result[0]
    if not isinstance(result, Mapping):
        raise TypeError("ORTEX range fetcher must return a mapping payload")
    return result


def _materialize_ranges(
    *,
    ranges: Sequence[Mapping[str, Any]],
    trading_dates: Iterable[Any],
    tickers: Sequence[str],
    output_path: str | Path,
    api_key: str | None,
    source_mode: str,
    fetcher: Callable[..., Any],
    exchange_by_ticker: Mapping[str, str],
    credit_budget: float,
    min_credits_left: float,
    estimated_credits_per_request: float,
    max_requests: int,
    request_interval_s: float,
    base_url: str,
    timeout: float,
    retries: int,
    request_get: Callable[..., requests.Response],
    sleep_fn: Callable[[float], None],
    collected_at: str | None,
) -> dict[str, Any]:
    """Credit-guarded, resumable implementation shared by history/daily."""
    key = load_api_key(api_key)
    if not key:
        raise ValueError("ORTEX API key is unavailable")
    sessions = normalise_trading_dates(trading_dates)
    if not sessions:
        raise ValueError("trading_dates must be supplied explicitly")
    if credit_budget <= 0 or min_credits_left < 0 or estimated_credits_per_request <= 0:
        raise ValueError("credit controls must be positive (floor may be zero)")
    if max_requests <= 0 or request_interval_s < 0:
        raise ValueError("max_requests must be positive and interval non-negative")

    timestamp = collected_at or utc_now_iso()
    existing_dates = _existing_dates_by_ticker(output_path)
    requests_made = 0
    credits_used_total = 0.0
    credits_left: float | None = None
    projected_next_cost = float(estimated_credits_per_request)
    rows_received = 0
    rows_appended = 0
    duplicate_rows = 0
    conflict_rows = 0
    skipped_complete = 0
    stop_reason: str | None = None
    request_records: list[dict[str, Any]] = []

    # Range-major ordering gives every ticker one 40-session block before any
    # ticker consumes a second block.  If the credit guard stops early this
    # preserves cross-sectional breadth (the experiment's primary readiness
    # condition) instead of deeply filling only the first few names.
    for block in ranges:
        label = str(block.get("label") or "")
        start = _date_text(block.get("start"))
        end = _date_text(block.get("end"))
        expected_sessions = int(block.get("expected_sessions") or 0)
        if not label or start is None or end is None or start > end:
            raise ValueError(f"invalid materialization range: {dict(block)!r}")
        required_dates = {day for day in sessions if start <= day <= end}
        if expected_sessions and len(required_dates) != expected_sessions:
            raise ValueError(
                f"range {label!r} expected {expected_sessions} sessions; "
                f"caller supplied {len(required_dates)}"
            )
        for ticker_value in tickers:
            ticker = str(ticker_value).upper().strip()
            if ticker not in exchange_by_ticker:
                raise ValueError(f"missing exchange mapping for {ticker!r}")
            already = existing_dates.get(ticker, set())
            # A complete session footprint is enough to skip a paid replay.
            if required_dates and required_dates.issubset(already):
                skipped_complete += 1
                continue

            stop_reason = _credit_stop_reason(
                requests_made=requests_made,
                max_requests=max_requests,
                credits_used_total=credits_used_total,
                credit_budget=float(credit_budget),
                credits_left=credits_left,
                min_credits_left=float(min_credits_left),
                projected_next_cost=projected_next_cost,
            )
            if stop_reason:
                break

            payload = _call_range_fetcher(
                fetcher,
                ticker=ticker,
                exchange=str(exchange_by_ticker[ticker]).upper(),
                start=start,
                end=end,
                api_key=key,
                base_url=base_url,
                timeout=timeout,
                retries=retries,
                request_get=request_get,
                sleep_fn=sleep_fn,
            )
            requests_made += 1
            used, left = _request_credit_metadata(payload)
            if used is not None:
                credits_used_total += used
                projected_next_cost = max(projected_next_cost, used)
            if left is not None:
                credits_left = left
            normalised = normalise_cost_to_borrow_new_rows(
                payload,
                ticker=ticker,
                exchange=str(exchange_by_ticker[ticker]).upper(),
                trading_dates=sessions,
                collected_at=timestamp,
                source_mode=source_mode,
                request_start_date=start,
                request_end_date=end,
                historical_block=label if source_mode == "historical_block" else None,
            )
            merge = append_normalised_rows_atomic(
                normalised,
                path=output_path,
                sleep_fn=sleep_fn,
            )
            rows_received += len(normalised)
            rows_appended += merge["appended"]
            duplicate_rows += merge["duplicates"]
            conflict_rows += merge["conflicts"]
            existing_dates.setdefault(ticker, set()).update(
                str(row["provider_date"]) for row in normalised
            )
            request_records.append(
                {
                    "ticker": ticker,
                    "exchange": str(exchange_by_ticker[ticker]).upper(),
                    "range_label": label,
                    "from_date": start,
                    "to_date": end,
                    "normalised_rows": len(normalised),
                    "rows_appended": merge["appended"],
                    "credits_used": used,
                    "credits_left": left,
                }
            )

            # A response at/below the floor or a response that consumed more
            # than the declared budget stops all subsequent requests.  The
            # just-fetched normalised rows are retained so a later run resumes.
            if left is not None and left <= float(min_credits_left):
                stop_reason = "reported_credit_floor_reached"
                break
            if credits_used_total > float(credit_budget) + 1e-12:
                stop_reason = "reported_credit_budget_exceeded"
                break
            if request_interval_s:
                sleep_fn(float(request_interval_s))
        if stop_reason:
            break

    total_rows = len(load_normalised_rows(output_path))
    return {
        "status": "credit_guard_stopped" if stop_reason else "completed",
        "source_mode": source_mode,
        "requests_made": requests_made,
        "requests_skipped_complete": skipped_complete,
        "rows_received": rows_received,
        "rows_appended": rows_appended,
        "duplicate_rows": duplicate_rows,
        "conflict_rows": conflict_rows,
        "total_rows": total_rows,
        "credits_used_total": round(credits_used_total, 6),
        "credits_left_last_reported": credits_left,
        "credit_budget": float(credit_budget),
        "min_credits_left": float(min_credits_left),
        "stop_reason": stop_reason,
        "request_records": request_records,
        "output_path": str(Path(output_path)),
        "api_key_persisted": False,
        "trade_enabled": False,
    }


def materialize_historical_blocks(
    *,
    trading_dates: Iterable[Any],
    tickers: Sequence[str] = FIXED_RESEARCH_TICKERS,
    blocks: Sequence[Mapping[str, Any]] = HISTORICAL_BLOCKS,
    output_path: str | Path = NORMALIZED_ROWS_PATH,
    api_key: str | None = None,
    fetcher: Callable[..., Any] = fetch_cost_to_borrow_new_payload,
    exchange_by_ticker: Mapping[str, str] = TICKER_EXCHANGES,
    credit_budget: float = DEFAULT_CREDIT_BUDGET,
    min_credits_left: float = DEFAULT_MIN_CREDITS_LEFT,
    estimated_credits_per_request: float = DEFAULT_ESTIMATED_CREDITS_PER_REQUEST,
    max_requests: int = DEFAULT_MAX_REQUESTS,
    request_interval_s: float = DEFAULT_REQUEST_INTERVAL_S,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
    retries: int = 4,
    request_get: Callable[..., requests.Response] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Materialize the three fixed 40-session blocks without raw persistence."""
    # Consume iterators once, then use the same immutable calendar everywhere.
    sessions = normalise_trading_dates(trading_dates)
    validate_historical_blocks(sessions, blocks)
    return _materialize_ranges(
        ranges=blocks,
        trading_dates=sessions,
        tickers=tickers,
        output_path=output_path,
        api_key=api_key,
        source_mode="historical_block",
        fetcher=fetcher,
        exchange_by_ticker=exchange_by_ticker,
        credit_budget=credit_budget,
        min_credits_left=min_credits_left,
        estimated_credits_per_request=estimated_credits_per_request,
        max_requests=max_requests,
        request_interval_s=request_interval_s,
        base_url=base_url,
        timeout=timeout,
        retries=retries,
        request_get=request_get,
        sleep_fn=sleep_fn,
        collected_at=collected_at,
    )


def materialize_daily_refresh(
    *,
    as_of: Any,
    trading_dates: Iterable[Any],
    tickers: Sequence[str] = FIXED_RESEARCH_TICKERS,
    output_path: str | Path = NORMALIZED_ROWS_PATH,
    api_key: str | None = None,
    fetcher: Callable[..., Any] = fetch_cost_to_borrow_new_payload,
    exchange_by_ticker: Mapping[str, str] = TICKER_EXCHANGES,
    max_refresh_tickers: int = 4,
    min_refresh_age_days: int = 5,
    credit_budget: float = 50.0,
    min_credits_left: float = 250.0,
    estimated_credits_per_request: float = DEFAULT_ESTIMATED_CREDITS_PER_REQUEST,
    request_interval_s: float = DEFAULT_REQUEST_INTERVAL_S,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 30.0,
    retries: int = 4,
    request_get: Callable[..., requests.Response] = requests.get,
    sleep_fn: Callable[[float], None] = time.sleep,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Refresh at most four stale names, oldest first, with a hard credit floor."""
    as_of_day = _date_text(as_of)
    if as_of_day is None:
        raise ValueError(f"invalid as_of date: {as_of!r}")
    if max_refresh_tickers <= 0 or min_refresh_age_days < 0:
        raise ValueError("daily refresh limits are invalid")
    sessions = normalise_trading_dates(trading_dates)
    if not sessions:
        raise ValueError("trading_dates must be supplied explicitly")
    existing = _existing_dates_by_ticker(output_path)
    as_of_value = date.fromisoformat(as_of_day)
    eligible: list[tuple[str, str]] = []
    missing_history: list[str] = []
    for ticker_value in tickers:
        ticker = str(ticker_value).upper()
        known = sorted(day for day in existing.get(ticker, set()) if day <= as_of_day)
        if not known:
            missing_history.append(ticker)
            continue
        last = known[-1]
        age = (as_of_value - date.fromisoformat(last)).days
        if age >= int(min_refresh_age_days):
            eligible.append((last, ticker))
    eligible.sort(key=lambda item: (item[0], tuple(tickers).index(item[1])))
    selected = eligible[: int(max_refresh_tickers)]
    ranges_by_ticker = {
        ticker: {
            "label": f"daily_refresh_{ticker}_{as_of_day}",
            "start": (date.fromisoformat(last) + timedelta(days=1)).isoformat(),
            "end": as_of_day,
            "expected_sessions": 0,
        }
        for last, ticker in selected
    }
    if not selected:
        return {
            "status": "no_stale_tickers",
            "as_of": as_of_day,
            "eligible_tickers": 0,
            "selected_tickers": [],
            "missing_history_tickers": missing_history,
            "requests_made": 0,
            "rows_appended": 0,
            "credits_used_total": 0.0,
            "credits_left_last_reported": None,
            "trade_enabled": False,
        }

    # Ranges differ by ticker, so execute one bounded internal call per name
    # while carrying the total credit envelope forward.
    aggregate_records: list[dict[str, Any]] = []
    aggregate_rows = 0
    aggregate_received = 0
    aggregate_used = 0.0
    last_left: float | None = None
    projected_next_cost = float(estimated_credits_per_request)
    stop_reason: str | None = None
    requests_made = 0
    for _, ticker in selected:
        remaining_budget = float(credit_budget) - aggregate_used
        if remaining_budget < float(estimated_credits_per_request):
            stop_reason = "projected_credit_budget_exceeded"
            break
        if last_left is not None and last_left - projected_next_cost <= float(min_credits_left):
            stop_reason = "projected_credit_floor_reached"
            break
        result = _materialize_ranges(
            ranges=(ranges_by_ticker[ticker],),
            trading_dates=sessions,
            tickers=(ticker,),
            output_path=output_path,
            api_key=api_key,
            source_mode="daily_refresh",
            fetcher=fetcher,
            exchange_by_ticker=exchange_by_ticker,
            credit_budget=remaining_budget,
            min_credits_left=min_credits_left,
            estimated_credits_per_request=estimated_credits_per_request,
            max_requests=1,
            request_interval_s=request_interval_s,
            base_url=base_url,
            timeout=timeout,
            retries=retries,
            request_get=request_get,
            sleep_fn=sleep_fn,
            collected_at=collected_at,
        )
        requests_made += int(result["requests_made"])
        aggregate_rows += int(result["rows_appended"])
        aggregate_received += int(result["rows_received"])
        aggregate_used += float(result["credits_used_total"])
        aggregate_records.extend(result["request_records"])
        for record in result["request_records"]:
            used = _finite_float(record.get("credits_used"))
            if used is not None:
                projected_next_cost = max(projected_next_cost, used)
        if result["credits_left_last_reported"] is not None:
            last_left = float(result["credits_left_last_reported"])
        if result["stop_reason"]:
            stop_reason = str(result["stop_reason"])
            break
        if last_left is not None and last_left <= float(min_credits_left):
            stop_reason = "reported_credit_floor_reached"
            break
    return {
        "status": "credit_guard_stopped" if stop_reason else "completed",
        "as_of": as_of_day,
        "eligible_tickers": len(eligible),
        "selected_tickers": [ticker for _, ticker in selected],
        "missing_history_tickers": missing_history,
        "requests_made": requests_made,
        "rows_received": aggregate_received,
        "rows_appended": aggregate_rows,
        "credits_used_total": round(aggregate_used, 6),
        "credits_left_last_reported": last_left,
        "credit_budget": float(credit_budget),
        "min_credits_left": float(min_credits_left),
        "stop_reason": stop_reason,
        "request_records": aggregate_records,
        "api_key_persisted": False,
        "trade_enabled": False,
    }


def fetch_all_pages(
    path_template: str,
    *,
    exchange: str,
    ticker: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    params: dict | None = None,
    max_pages: int = 100,
):
    """Fetch every page by following ``paginationLinks.next`` and merging ``rows``.

    Returns ``(resp, payload)`` where ``payload`` is the first page's JSON with ``rows``
    replaced by the concatenation of all pages (plus ``pagesFetched`` / ``rowCount``).
    On a non-200 first page, returns ``(resp, None)`` so the caller can report the error.
    ORTEX caps each page at 100 rows; the ``next`` link is an absolute URL whose key
    still travels in the header, not the query string.
    """
    resp = fetch(path_template, exchange=exchange, ticker=ticker, api_key=api_key,
                 base_url=base_url, params=params)
    if resp.status_code != 200:
        return resp, None
    try:
        payload = resp.json()
    except ValueError:
        return resp, None
    rows = list(payload.get("rows") or [])
    pages = 1
    nxt = (payload.get("paginationLinks") or {}).get("next")
    while nxt and pages < max_pages:
        page_resp = _get(nxt, api_key=api_key)
        if page_resp.status_code != 200:
            print(f"WARNING: pagination stopped at page {pages + 1}: HTTP "
                  f"{page_resp.status_code}", file=sys.stderr)
            break
        try:
            page = page_resp.json()
        except ValueError:
            break
        rows.extend(page.get("rows") or [])
        pages += 1
        nxt = (page.get("paginationLinks") or {}).get("next")
    if nxt and pages >= max_pages:
        print(f"WARNING: hit --max-pages={max_pages}; more pages remain (next={nxt})",
              file=sys.stderr)
    payload["rows"] = rows
    payload["pagesFetched"] = pages
    payload["rowCount"] = len(rows)
    payload.pop("paginationLinks", None)  # merged view: links no longer meaningful
    return resp, payload


def discover_path(
    *,
    exchange: str,
    ticker: str,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    candidates=SHORT_INTEREST_PATH_CANDIDATES,
) -> str | None:
    """Probe candidate short-interest path templates; return the first that returns 200."""
    for template in candidates:
        try:
            resp = fetch(
                template, exchange=exchange, ticker=ticker, api_key=api_key,
                base_url=base_url, retries=1, timeout=15.0,
            )
        except requests.RequestException as exc:
            print(f"  {template:50s} -> request error: {exc}")
            continue
        marker = "OK" if resp.status_code == 200 else ""
        print(f"  {template:50s} -> HTTP {resp.status_code} {marker}")
        if resp.status_code == 200:
            return template
    return None


def save_json(payload, *, exchange: str, ticker: str, label: str, output_dir: Path) -> Path:
    """Persist a fetched payload as pretty JSON under data/non_ohlcv/ortex/."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe = f"{exchange}_{ticker}_{label}".replace("/", "_").upper()
    out = output_dir / f"ortex_{safe}.json"
    tmp = out.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.replace(tmp, out)
    except OSError:
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.unlink(missing_ok=True)
    return out


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch ORTEX short-interest / borrow data.")
    p.add_argument("--exchange", required=True, help="e.g. NASDAQ, NYSE")
    p.add_argument("--ticker", required=True, help="e.g. AAPL")
    p.add_argument("--endpoint", choices=sorted(ENDPOINTS), default=None,
                   help="Named verified endpoint (handles path + exchange casing). "
                        "Overrides --path/--discover.")
    p.add_argument("--path", default=os.environ.get("ORTEX_SI_PATH"),
                   help="Raw endpoint path template with {exchange}/{ticker}. Skips discovery.")
    p.add_argument("--param", action="append", default=[], metavar="k=v",
                   help="Query parameter (repeatable), e.g. --param from_date=2026-01-01")
    p.add_argument("--key", default=None,
                   help="API key override (else ORTEX_API_KEY env / .env). Use TEST to trial.")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    p.add_argument("--label", default="short_interest", help="Filename label for the saved JSON.")
    p.add_argument("--max-pages", type=int, default=100,
                   help="Max pages to follow via paginationLinks.next (100 rows each).")
    p.add_argument("--discover", action="store_true",
                   help="Probe candidate path templates and print which returns 200.")
    return p


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    api_key = load_api_key(args.key)
    if not api_key:
        print("ERROR: no API key. Set ORTEX_API_KEY (env or .env), or pass --key TEST.",
              file=sys.stderr)
        return 2
    print(f"Using key {_mask(api_key)} against {args.base_url}")

    # A named endpoint resolves the path and the per-endpoint exchange casing, and
    # supplies a sensible filename label. It wins over --path / --discover.
    exchange = args.exchange
    if args.endpoint:
        path_template, casing = ENDPOINTS[args.endpoint]
        args.path = path_template
        exchange = _exchange_for(args.exchange, casing)
        if args.label == "short_interest":
            args.label = args.endpoint

    if args.discover or not args.path:
        print("Discovering working short-interest path:")
        found = discover_path(
            exchange=exchange, ticker=args.ticker, api_key=api_key, base_url=args.base_url,
        )
        if not found:
            print("No candidate returned 200. Confirm the path from app.ortex.com/apis "
                  "(the docs 'API' tab shows a curl example) and pass it via --path.",
                  file=sys.stderr)
            return 1
        print(f"Working path: {found}")
        if args.discover:
            return 0
        args.path = found

    params = {}
    for item in args.param:
        k, _, v = item.partition("=")
        params[k.strip()] = v.strip()

    resp, payload = fetch_all_pages(args.path, exchange=exchange, ticker=args.ticker,
                                    api_key=api_key, base_url=args.base_url, params=params,
                                    max_pages=args.max_pages)
    if payload is None:
        if resp.status_code != 200:
            print(f"ERROR: HTTP {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        else:
            ct = resp.headers.get("content-type")
            sent_auth = AUTH_HEADER in (resp.request.headers or {})
            print(f"ERROR: response was not JSON (HTTP {resp.status_code}, content-type={ct!r}, "
                  f"{len(resp.text)} bytes). url={resp.url!r} auth_header_sent={sent_auth} "
                  f"Body head: {resp.text[:200]!r}", file=sys.stderr)
        return 1
    print(f"Fetched {payload.get('rowCount')} rows across {payload.get('pagesFetched')} page(s)")
    out = save_json(payload, exchange=args.exchange, ticker=args.ticker,
                    label=args.label, output_dir=Path(args.output_dir))
    print(f"Saved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
