"""Gate 1-4 replay for Senate LDA issuer regulatory-friction sizing.

The source-only phase queries the official anonymous LDA filings API once per
frozen direct issuer name, preserves every raw response page, and authenticates
all cached pages through an atomic SHA256 manifest.  The alpha phase applies
the shared helper's fixed 0.5 scalar after unchanged selection/sizing and
before unchanged cash admission.  It never removes a signal or changes the
backtester implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for entry in (str(QUANT), str(EXPERIMENTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import active_book_marginal_variance as scalar_policy  # noqa: E402
import backtester as bt  # noqa: E402
import exp_20260712_015_post_mtm_gate1_baseline as gate1  # noqa: E402
import senate_lda_regulatory_friction as lda_policy  # noqa: E402
from us_market_calendar import is_us_equity_session  # noqa: E402


EXPERIMENT_ID = "exp-20260720-005"
PROTOCOL_ID = "senate_lda_issue_breadth_entry_admission_v1"
HYPOTHESIS = (
    "Shared-paper-first entry-admission alpha: when a directly mapped core "
    "issuer's completed Senate LDA quarterly-filing week has at least three "
    "distinct lobbying issue codes and breadth strictly above the median of "
    "its prior four nonempty filing weeks, regulatory-friction intensity is "
    "rising; downweight only new core entries by 50 percent for the next ten "
    "trading sessions."
)

ACTIVE_BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)
FROZEN_INPUTS = (
    ROOT / "data" / "experiments" / "exp-20260712-015" / "frozen_behavior_inputs.json"
)
SOURCE_ROOT = ROOT / "data" / "non_ohlcv" / "senate_lda"
SOURCE_MANIFEST = SOURCE_ROOT / "manifest.json"
RAW_ROOT = SOURCE_ROOT / "raw_pages"
EXP_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BACKTEST_DIR = EXP_DIR / "backtests"
SOURCE_PREFLIGHT_FILE = EXP_DIR / "source_preflight.json"
BEFORE_FILE = EXP_DIR / "before_measurement.json"
AFTER_FILE = EXP_DIR / "after_measurement.json"
SUMMARY_FILE = EXP_DIR / "summary.json"
PAPER_DIR = ROOT / "data" / "paper_sleeves" / "senate_lda_regulatory_friction"
LATEST_SNAPSHOT = PAPER_DIR / "latest.json"

API_ENDPOINT = "https://lda.gov/api/v1/filings/"
SOURCE_START = "2023-01-01"
SOURCE_END = "2026-07-20"
PAGE_SIZE = 25
ANON_REQUESTS_PER_MINUTE = 15
MIN_REQUEST_INTERVAL_SECONDS = 4.1
MAX_REQUEST_ATTEMPTS = 5
USER_AGENT = "ginger-research-exp-20260720-005/1.0"

SIZING_KEY = "senate_lda_regulatory_friction_scalar"
REQUESTED_KEY = "senate_lda_regulatory_friction_requested_scalar"
BASELINE_SHARES_KEY = "senate_lda_regulatory_friction_baseline_shares"
MIN_SURVIVAL_RATE = 0.05
MIN_TOUCHED_EXECUTED_PER_WINDOW = 5
MIN_ISSUER_WEEKS_PER_WINDOW = 20
MIN_TICKERS_PER_WINDOW = 10
MAX_TOP1_SHARE = 0.30
REQUIRED_EV_DELTA = 0.6206
REQUIRED_PNL_DELTA = 10_432.91
MAX_DRAWDOWN_DRIFT = 0.005


def _path_text(path: Path) -> str:
    try:
        return gate1._repo_rel(path)
    except ValueError:
        return str(path.resolve())


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _client_queries() -> dict[str, str]:
    queries = lda_policy.senate_lda_client_query_names()
    if not isinstance(queries, Mapping):
        raise RuntimeError("Senate LDA helper query-name contract must be a mapping")
    normalized = {
        str(ticker).strip().upper(): str(name).strip()
        for ticker, name in queries.items()
        if str(ticker).strip() and str(name).strip()
    }
    if len(normalized) != 15 or len(set(normalized.values())) != 15:
        raise RuntimeError(
            "Senate LDA source contract requires exactly 15 unique direct-name queries"
        )
    return dict(sorted(normalized.items()))


class _AnonymousRateLimiter:
    def __init__(self, interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS) -> None:
        self.interval_seconds = float(interval_seconds)
        self._last_request: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last_request is not None:
            remaining = self.interval_seconds - (now - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()


def _request_page(
    url: str,
    limiter: _AnonymousRateLimiter,
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        limiter.wait()
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS host
                body = response.read()
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("results"), list
                ):
                    raise RuntimeError("LDA API page is not a paginated JSON object")
                return body, payload, {
                    "http_status": int(getattr(response, "status", 200)),
                    "response_date": response.headers.get("Date"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "deprecation": response.headers.get("Deprecation"),
                    "sunset": response.headers.get("Sunset"),
                }
        except HTTPError as exc:
            last_error = exc
            if exc.code != 429 and exc.code < 500:
                raise RuntimeError(f"LDA API HTTP {exc.code} for {url}") from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = max(float(retry_after), MIN_REQUEST_INTERVAL_SECONDS)
            except (TypeError, ValueError):
                delay = MIN_REQUEST_INTERVAL_SECONDS * attempt
            time.sleep(min(delay, 60.0))
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(MIN_REQUEST_INTERVAL_SECONDS * attempt, 30.0))
    raise RuntimeError(f"LDA API request exhausted retries for {url}: {last_error}")


def _fetch_source_archive() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    queries = _client_queries()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    batch_dir = RAW_ROOT / batch_id
    limiter = _AnonymousRateLimiter()
    page_records: list[dict[str, Any]] = []

    for ticker, client_name in queries.items():
        page = 1
        while True:
            params = {
                "client_name": client_name,
                "filing_dt_posted_after": SOURCE_START,
                "filing_dt_posted_before": SOURCE_END,
                "page": page,
                "page_size": PAGE_SIZE,
            }
            url = f"{API_ENDPOINT}?{urlencode(params)}"
            body, payload, response_meta = _request_page(url, limiter)
            filename = f"{ticker.lower()}_page_{page:04d}.json"
            path = batch_dir / filename
            _atomic_write_bytes(path, body)
            record = {
                "ticker": ticker,
                "client_name": client_name,
                "page": page,
                "request": {"endpoint": API_ENDPOINT, "params": params},
                "request_sha256": gate1._stable_hash(
                    {"endpoint": API_ENDPOINT, "params": params}
                ),
                "path": _path_text(path),
                "sha256": gate1._file_sha256(path),
                "bytes": path.stat().st_size,
                "payload_sha256": gate1._stable_hash(payload),
                "response_count": int(payload.get("count") or 0),
                "result_count": len(payload["results"]),
                "next_present": bool(payload.get("next")),
                "previous_present": bool(payload.get("previous")),
                **response_meta,
            }
            page_records.append(record)
            print(
                f"[source] {ticker} page {page}: {record['result_count']} rows",
                flush=True,
            )
            if not payload.get("next"):
                break
            page += 1
            expected_pages = max(1, math.ceil(record["response_count"] / PAGE_SIZE))
            if page > expected_pages:
                raise RuntimeError(f"LDA pagination exceeded declared count for {ticker}")

    manifest_body = {
        "schema": "senate_lda_official_filings_manifest_v1",
        "experiment_id": EXPERIMENT_ID,
        "source": "official Senate Lobbying Disclosure Act REST API",
        "endpoint": API_ENDPOINT,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "query_start": SOURCE_START,
        "query_end": SOURCE_END,
        "anonymous": True,
        "authorization_header_sent": False,
        "anonymous_request_limit_per_minute": ANON_REQUESTS_PER_MINUTE,
        "minimum_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS,
        "page_size": PAGE_SIZE,
        "query_names": queries,
        "query_count": len(queries),
        "pages": page_records,
        "page_count": len(page_records),
        "raw_result_count": sum(row["result_count"] for row in page_records),
    }
    manifest = {
        **manifest_body,
        "manifest_sha256": gate1._stable_hash(manifest_body),
    }
    gate1._atomic_write_json(SOURCE_MANIFEST, manifest)
    return _load_verified_source_archive(SOURCE_MANIFEST)


def _manifest_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    source_root = SOURCE_ROOT.resolve()
    if path != source_root and source_root not in path.parents:
        raise RuntimeError(f"LDA manifest page escapes source root: {value}")
    return path


def _load_verified_source_archive(
    manifest_path: Path = SOURCE_MANIFEST,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared_hash = manifest.get("manifest_sha256")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("schema") != "senate_lda_official_filings_manifest_v1":
        raise RuntimeError("Unexpected Senate LDA source-manifest schema")
    if declared_hash != gate1._stable_hash(body):
        raise RuntimeError("Senate LDA manifest self-hash mismatch")
    if (
        manifest.get("endpoint") != API_ENDPOINT
        or manifest.get("query_start") != SOURCE_START
        or manifest.get("query_end") != SOURCE_END
        or manifest.get("query_names") != _client_queries()
        or int(manifest.get("query_count") or 0) != 15
    ):
        raise RuntimeError("Senate LDA cached query contract drifted")

    pages = manifest.get("pages") or []
    if not isinstance(pages, list) or not pages:
        raise RuntimeError("Senate LDA manifest has no cached pages")
    rows: list[dict[str, Any]] = []
    page_counts: Counter[str] = Counter()
    page_numbers: defaultdict[str, list[int]] = defaultdict(list)
    terminal_pages: Counter[str] = Counter()
    response_counts: defaultdict[str, set[int]] = defaultdict(set)
    verified_pages: list[dict[str, Any]] = []
    for record in pages:
        path = _manifest_path(str(record.get("path") or ""))
        if not path.is_file() or gate1._file_sha256(path) != record.get("sha256"):
            raise RuntimeError(f"Senate LDA raw-page hash mismatch: {path}")
        raw = path.read_bytes()
        if len(raw) != int(record.get("bytes") or -1):
            raise RuntimeError(f"Senate LDA raw-page byte count mismatch: {path}")
        payload = json.loads(raw.decode("utf-8"))
        if gate1._stable_hash(payload) != record.get("payload_sha256"):
            raise RuntimeError(f"Senate LDA parsed-page hash mismatch: {path}")
        ticker = str(record.get("ticker") or "").upper()
        page = int(record.get("page") or 0)
        params = (record.get("request") or {}).get("params") or {}
        expected_params = {
            "client_name": _client_queries().get(ticker),
            "filing_dt_posted_after": SOURCE_START,
            "filing_dt_posted_before": SOURCE_END,
            "page": page,
            "page_size": PAGE_SIZE,
        }
        if params != expected_params or record.get("request_sha256") != gate1._stable_hash(
            {"endpoint": API_ENDPOINT, "params": expected_params}
        ):
            raise RuntimeError(f"Senate LDA request identity mismatch: {ticker}/{page}")
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != record.get("result_count"):
            raise RuntimeError(f"Senate LDA result-count mismatch: {path}")
        page_counts[ticker] += len(results)
        page_numbers[ticker].append(page)
        response_counts[ticker].add(int(payload.get("count") or 0))
        if not payload.get("next"):
            terminal_pages[ticker] += 1
        rows.extend(dict(row) for row in results if isinstance(row, Mapping))
        verified_pages.append(
            {"path": _path_text(path), "sha256": record["sha256"], "ticker": ticker}
        )

    for ticker in _client_queries():
        numbers = sorted(page_numbers[ticker])
        if (
            not numbers
            or numbers != list(range(1, len(numbers) + 1))
            or terminal_pages[ticker] != 1
            or len(response_counts[ticker]) != 1
            or page_counts[ticker] != next(iter(response_counts[ticker]))
        ):
            raise RuntimeError(f"Senate LDA pagination contract failed for {ticker}")

    by_uuid: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for row in rows:
        filing_uuid = str(row.get("filing_uuid") or row.get("id") or "").strip()
        dt_posted = str(row.get("dt_posted") or "")
        if not filing_uuid or not (SOURCE_START <= dt_posted[:10] <= SOURCE_END):
            raise RuntimeError("Senate LDA response row lacks in-range UUID/dt_posted")
        previous = by_uuid.get(filing_uuid)
        if previous is not None:
            duplicate_count += 1
            if gate1._stable_hash(previous) != gate1._stable_hash(row):
                raise RuntimeError(f"Conflicting Senate LDA payload for {filing_uuid}")
        else:
            by_uuid[filing_uuid] = row
    filings = [by_uuid[key] for key in sorted(by_uuid)]
    identity = {
        "manifest_path": _path_text(manifest_path),
        "manifest_file_sha256": gate1._file_sha256(manifest_path),
        "manifest_sha256": declared_hash,
        "endpoint": API_ENDPOINT,
        "query_start": SOURCE_START,
        "query_end": SOURCE_END,
        "query_names": _client_queries(),
        "query_count": 15,
        "page_count": len(pages),
        "raw_result_count": len(rows),
        "deduplicated_filing_count": len(filings),
        "cross_query_duplicate_count": duplicate_count,
        "filings_sha256": gate1._stable_hash(filings),
        "verified_pages": verified_pages,
        "all_pages_hash_verified": True,
        "pagination_complete": True,
    }
    return filings, identity


def _load_or_fetch_source(
    *, offline: bool, refresh: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if offline and refresh:
        raise ValueError("--offline and --refresh-source are mutually exclusive")
    if SOURCE_MANIFEST.exists() and not refresh:
        try:
            return _load_verified_source_archive()
        except Exception:
            if offline:
                raise
    if offline:
        raise RuntimeError("--offline requires a complete hash-valid Senate LDA cache")
    return _fetch_source_archive()


def _all_sessions() -> list[str]:
    start = date.fromisoformat(SOURCE_START)
    end = date.fromisoformat(SOURCE_END) + timedelta(days=30)
    sessions: list[str] = []
    current = start
    while current <= end:
        if is_us_equity_session(current):
            sessions.append(current.isoformat())
        current += timedelta(days=1)
    return sessions


def _row_day(row: Mapping[str, Any]) -> str | None:
    for key in (
        "week_end",
        "completed_week_end",
        "filing_week_end",
        "dt_posted",
        "trigger_dt_posted",
    ):
        value = str(row.get(key) or "")[:10]
        if len(value) == 10:
            return value
    return None


def _density_by_window(weekly_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        rows = [
            row
            for row in weekly_rows
            if (day := _row_day(row)) is not None
            and spec["start"] <= day <= spec["end"]
        ]
        ticker_counts = Counter(str(row.get("ticker") or "").upper() for row in rows)
        ticker_counts.pop("", None)
        top_ticker, top_count = ticker_counts.most_common(1)[0] if ticker_counts else (None, 0)
        count = len(rows)
        checks = {
            "issuer_weeks_gte_20": count >= MIN_ISSUER_WEEKS_PER_WINDOW,
            "tickers_gte_10": len(ticker_counts) >= MIN_TICKERS_PER_WINDOW,
            "top1_lte_30pct": bool(count) and top_count / count <= MAX_TOP1_SHARE,
        }
        output[spec["label"]] = {
            "issuer_week_count": count,
            "ticker_count": len(ticker_counts),
            "top1_ticker": top_ticker,
            "top1_count": top_count,
            "top1_share": round(top_count / count, 6) if count else None,
            "by_ticker": dict(sorted(ticker_counts.items())),
            "checks": checks,
            "all_pass": all(checks.values()),
        }
    output["all_windows_pass"] = all(
        output[spec["label"]]["all_pass"] for spec in gate1.WINDOWS
    )
    return output


def _resolver_scalar(resolver: Any, as_of: str, ticker: str) -> tuple[float, dict[str, Any]]:
    result = resolver.evaluate(as_of, ticker)
    if not isinstance(result, Mapping):
        raise RuntimeError("Senate LDA resolver evaluate() must return a mapping")
    scalar = _number(result.get("scalar", result.get("notional_scalar")))
    if scalar not in (1.0, float(lda_policy.ENTRY_SCALAR)):
        raise RuntimeError(f"Unexpected Senate LDA scalar: {scalar}")
    return float(scalar), dict(result)


def _snapshot_scalars(snapshot: Mapping[str, Any], tickers: Sequence[str]) -> dict[str, float]:
    raw = snapshot.get("ticker_scalars") or {}
    return {
        ticker: float(_number(raw.get(ticker)) or 1.0)
        for ticker in tickers
    }


def _daily_parity(
    resolver: Any,
    sessions: Sequence[str],
    tickers: Sequence[str],
) -> dict[str, Any]:
    canonical = {
        day
        for spec in gate1.WINDOWS
        for day in sessions
        if spec["start"] <= day <= spec["end"]
    }
    mismatches: list[dict[str, Any]] = []
    checked = 0
    for day in sorted(canonical):
        snapshot = lda_policy.build_daily_snapshot_from_resolver(
            resolver,
            day,
            candidate_tickers=tickers,
        )
        daily = _snapshot_scalars(snapshot, tickers)
        replay = {
            ticker: _resolver_scalar(resolver, day, ticker)[0] for ticker in tickers
        }
        checked += 1
        if daily != replay:
            mismatches.append({"as_of": day, "daily": daily, "replay": replay})
    return {
        "session_count": checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "all_sessions_match": checked > 0 and not mismatches,
    }


def _zero_price_preflight(
    filings: list[dict[str, Any]], source_identity: dict[str, Any]
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    sessions = _all_sessions()
    normalized = lda_policy.normalise_senate_lda_filings(filings)
    evaluation = lda_policy.evaluate_senate_lda_regulatory_friction_weeks(
        filings, as_of=SOURCE_END
    )
    resolver = lda_policy.SenateLDARegulatoryFrictionResolver(
        filings,
        sessions,
        source_identity=source_identity,
    )
    if not isinstance(resolver.metadata, Mapping) or not isinstance(resolver.index, Mapping):
        raise RuntimeError("Senate LDA resolver metadata/index contract failed")
    weekly_rows = list(evaluation.get("weekly_rows") or [])
    density = _density_by_window(weekly_rows)
    tickers = sorted(_client_queries())
    parity = _daily_parity(resolver, sessions, tickers)
    latest = lda_policy.build_daily_snapshot(
        filings,
        SOURCE_END,
        sessions,
        candidate_tickers=tickers,
        source_identity=source_identity,
    )
    latest_from_resolver = lda_policy.build_daily_snapshot_from_resolver(
        resolver,
        SOURCE_END,
        candidate_tickers=tickers,
    )
    gate1._atomic_write_json(LATEST_SNAPSHOT, latest)

    normalized_checks = {
        "rows_present": bool(normalized),
        "uuid_complete": all(bool(row.get("filing_uuid")) for row in normalized),
        "dt_posted_complete": all(bool(row.get("dt_posted")) for row in normalized),
        "client_effective_date_complete": all(
            bool(row.get("client_effective_date")) for row in normalized
        ),
        "issue_codes_canonical": all(
            isinstance(row.get("issue_codes"), list)
            and row.get("issue_codes") == sorted(set(row.get("issue_codes") or []))
            for row in normalized
        ),
        "row_hashes_complete": all(
            bool(row.get("payload_hash")) and bool(row.get("row_hash"))
            for row in normalized
        ),
    }
    latest_checks = {
        "trade_enabled_false": latest.get("trade_enabled") is False,
        "orders_empty": not (
            latest.get("orders")
            or latest.get("order_intents")
            or latest.get("proposed_orders")
        ),
        "snapshot_persisted_exact": (
            json.loads(LATEST_SNAPSHOT.read_text(encoding="utf-8")) == latest
        ),
        "fresh_build_matches_reused_resolver": latest == latest_from_resolver,
    }
    source_checks = {
        "official_endpoint_exact": source_identity.get("endpoint") == API_ENDPOINT,
        "fifteen_direct_queries": source_identity.get("query_count") == 15,
        "all_page_hashes_verified": source_identity.get("all_pages_hash_verified") is True,
        "pagination_complete": source_identity.get("pagination_complete") is True,
        "policy_constants_exact": (
            float(lda_policy.ENTRY_SCALAR) == 0.5
            and int(lda_policy.ACTIVE_SESSIONS) == 10
            and int(lda_policy.MIN_ISSUE_BREADTH) == 3
            and int(lda_policy.PRIOR_NONEMPTY_WEEKS) == 4
            and lda_policy.TRADE_ENABLED is False
        ),
        "normalized_contract": all(normalized_checks.values()),
        "density_all_windows": density["all_windows_pass"],
        "daily_replay_parity": parity["all_sessions_match"],
        "index_hashes_present": bool(
            resolver.index.get("index_hash") and resolver.index.get("source_hash")
        ),
        "latest_default_off_snapshot": all(latest_checks.values()),
    }
    report = {
        "schema": "senate_lda_zero_price_preflight_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_identity": source_identity,
        "source_manifest_identity": {
            "path": _path_text(SOURCE_MANIFEST),
            "sha256": gate1._file_sha256(SOURCE_MANIFEST),
        },
        "normalized_row_count": len(normalized),
        "normalized_sha256": gate1._stable_hash(normalized),
        "weekly_row_count": len(weekly_rows),
        "trigger_row_count": len(evaluation.get("trigger_rows") or []),
        "evaluation_hash": gate1._stable_hash(evaluation),
        "resolver_metadata": dict(resolver.metadata),
        "index_identity": {
            key: resolver.index.get(key)
            for key in (
                "source_hash",
                "index_hash",
                "trading_sessions_hash",
                "issuer_map_hash",
                "weekly_rows_hash",
                "trigger_rows_hash",
            )
        },
        "density": density,
        "daily_parity": parity,
        "normalized_checks": normalized_checks,
        "latest_snapshot": {
            "path": _path_text(LATEST_SNAPSHOT),
            "sha256": gate1._file_sha256(LATEST_SNAPSHOT),
            "checks": latest_checks,
        },
        "checks": source_checks,
        "all_pass": all(source_checks.values()),
    }
    gate1._atomic_write_json(SOURCE_PREFLIGHT_FILE, report)
    return resolver, report, latest


def _load_frozen() -> dict[str, Any]:
    payload = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if payload.get("schema") != "post_mtm_frozen_behavior_inputs_v1":
        raise RuntimeError("Unexpected frozen Gate-1 behavior-input schema")
    if payload.get("behavior_sha256") != gate1._stable_hash(payload.get("behavior")):
        raise RuntimeError("Frozen Gate-1 behavior-input hash mismatch")
    return payload


def _runtime_context() -> dict[str, Any]:
    required = ("today", "ohlcv_all", "all_dates")
    for frame_info in inspect.stack():
        values = frame_info.frame.f_locals
        if all(name in values for name in required):
            return {name: values[name] for name in required}
    raise RuntimeError("could not resolve BacktestEngine.run decision context")


def _future_fill_date(frame: Any, today: Any, all_dates: Sequence[Any]) -> str | None:
    for day in [value for value in all_dates if value > today][:3]:
        if frame is not None and day in frame.index:
            return str(day)[:10]
    return None


def _rename_scalar_fields(sizing: dict[str, Any]) -> dict[str, Any]:
    renamed = dict(sizing)
    mappings = {
        "active_book_marginal_variance_scalar": SIZING_KEY,
        "active_book_marginal_variance_requested_scalar": REQUESTED_KEY,
        "active_book_marginal_variance_baseline_shares": BASELINE_SHARES_KEY,
    }
    for old, new in mappings.items():
        if old in renamed:
            renamed[new] = renamed.pop(old)
    return renamed


def _evaluate_signal(
    signal: dict[str, Any], context: Mapping[str, Any], resolver: Any
) -> dict[str, Any]:
    signal_date = str(context["today"])[:10]
    ticker = str(signal.get("ticker") or "").upper()
    frame = context["ohlcv_all"].get(ticker)
    entry_date = _future_fill_date(frame, context["today"], context["all_dates"])
    if entry_date is None:
        metadata = dict(resolver.metadata)
        scalar = 1.0
        evaluation = {
            "status": "fail_open_no_entry_date",
            "source_hash": metadata.get("source_hash"),
            "index_hash": metadata.get("index_hash"),
            "provenance": {
                "reason": "no_future_fill_session_in_window",
                "signal_date": signal_date,
                "ticker": ticker,
            },
            "trigger_rows": [],
        }
    else:
        scalar, evaluation = _resolver_scalar(resolver, entry_date, ticker)
    sizing = dict(signal.get("sizing") or {})
    scaled, share_audit = scalar_policy.apply_scalar_to_sizing(sizing, scalar)
    signal["sizing"] = _rename_scalar_fields(scaled)
    provenance = {
        "rule_version": lda_policy.RULE_VERSION,
        "source": lda_policy.SOURCE,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "ticker": ticker,
        "requested_scalar": scalar,
        "realized_scalar": share_audit.get("realized_scalar"),
        "resolver_status": evaluation.get("status"),
        "source_hash": evaluation.get("source_hash"),
        "index_hash": evaluation.get("index_hash"),
        "resolver_provenance": evaluation.get("provenance") or {},
        "trigger_rows": evaluation.get("trigger_rows") or [],
        "trade_enabled": False,
    }
    signal["entry_date"] = entry_date
    signal["senate_lda_regulatory_friction_provenance"] = provenance
    return {
        **provenance,
        "target_price": signal.get("target_price"),
        "target_price_present": (
            (_number(signal.get("target_price")) or 0.0) > 0.0
        ),
        "entry_date_present": entry_date is not None,
        "share_audit": share_audit,
        "material_share_change": (
            share_audit.get("scaled_shares") != share_audit.get("baseline_shares")
        ),
    }


def _make_plan_wrapper(
    original: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
    resolver: Any,
    state: dict[str, Any],
) -> Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]:
    def wrapped(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        selected, plan = original(*args, **kwargs)
        before_ids = [id(signal) for signal in selected]
        if selected:
            context = _runtime_context()
            for signal in selected:
                state["annotations"].append(_evaluate_signal(signal, context, resolver))
        state["selection_identity_passed"] = before_ids == [id(signal) for signal in selected]
        return selected, plan

    return wrapped


def _run_after(
    spec: dict[str, str], frozen: dict[str, Any], resolver: Any
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    state: dict[str, Any] = {"annotations": [], "selection_identity_passed": True}
    original_plan = bt.plan_entry_candidates
    original_keys = bt.SIZING_MULTIPLIER_KEYS
    bt.plan_entry_candidates = _make_plan_wrapper(original_plan, resolver, state)
    if SIZING_KEY not in original_keys:
        bt.SIZING_MULTIPLIER_KEYS = (*original_keys, SIZING_KEY)
    try:
        result, identity = gate1._run_window(spec, frozen)
    finally:
        bt.plan_entry_candidates = original_plan
        bt.SIZING_MULTIPLIER_KEYS = original_keys
    state["patch_restored"] = (
        bt.plan_entry_candidates is original_plan
        and bt.SIZING_MULTIPLIER_KEYS == original_keys
    )
    return result, identity, state


def _persist_result(
    arm: str, spec: Mapping[str, str], result: Mapping[str, Any]
) -> dict[str, str]:
    path = BACKTEST_DIR / f"{spec['label']}_{arm}_{EXPERIMENT_ID}.json"
    gate1._atomic_write_json(path, gate1._persistable_backtest_result(dict(result)))
    return {"path": _path_text(path), "sha256": gate1._file_sha256(path)}


def _headline(result: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "worst_trade_pct",
        "tail_loss_share",
        "win_rate",
        "total_trades",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    output = {key: result.get(key) for key in keys}
    output["trade_count"] = output.pop("total_trades")
    output["benchmarks"] = dict(result.get("benchmarks") or {})
    return output


def _delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in set(after) | set(before):
        left = _number(before.get(key))
        right = _number(after.get(key))
        if left is not None and right is not None:
            output[key] = round(right - left, 6)
    return output


def _aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in rows), 4
        ),
        "total_pnl": round(sum(float(row["total_pnl"]) for row in rows), 2),
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in rows),
        "minimum_survival_rate": min(float(row["survival_rate"]) for row in rows),
        "trade_count": sum(int(row["trade_count"]) for row in rows),
    }


def _positive_concentration(result: Mapping[str, Any]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for trade in result.get("trades") or []:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0)
    values = sorted((value for value in by_ticker.values() if value > 0), reverse=True)
    total = sum(values)
    shares = [value / total for value in values] if total else []
    return {
        "positive_pnl": total,
        "ticker_count": len(values),
        "single_share": max(shares) if shares else None,
        "top5_share": sum(shares[:5]) if shares else None,
        "hhi": sum(value * value for value in shares) if shares else None,
    }


def _touched_executed(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    annotations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    annotation_by_key = {
        (str(row.get("ticker") or "").upper(), str(row.get("entry_date") or "")[:10]): row
        for row in annotations
        if row.get("material_share_change")
    }
    before_trades = {
        (
            str(trade.get("ticker") or "").upper(),
            str(trade.get("entry_date") or "")[:10],
        ): trade
        for trade in before.get("trades") or []
    }
    touched: list[dict[str, Any]] = []
    for trade in after.get("trades") or []:
        key = (
            str(trade.get("ticker") or "").upper(),
            str(trade.get("entry_date") or "")[:10],
        )
        annotation = annotation_by_key.get(key)
        baseline_trade = before_trades.get(key)
        baseline_shares = baseline_trade.get("shares") if baseline_trade else None
        if annotation is None or trade.get("shares") == baseline_shares:
            continue
        touched.append(
            {
                "ticker": key[0],
                "entry_date": key[1],
                "exit_date": trade.get("exit_date"),
                "shares": trade.get("shares"),
                "baseline_shares": baseline_shares,
                "pnl": trade.get("pnl"),
                "requested_scalar": annotation["requested_scalar"],
                "realized_scalar": (annotation.get("share_audit") or {}).get(
                    "realized_scalar"
                ),
                "annotation_matched": True,
                "source_hash": annotation.get("source_hash"),
                "index_hash": annotation.get("index_hash"),
            }
        )
    return touched


def _reference_checks(
    result: Mapping[str, Any], identity: Mapping[str, Any], reference: Mapping[str, Any]
) -> dict[str, bool]:
    checks = {
        "expected_value_score": result.get("expected_value_score") == reference.get("expected_value_score"),
        "total_pnl": result.get("total_pnl") == reference.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily") == reference.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct") == reference.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades") == reference.get("trade_count"),
        "signals_generated": result.get("signals_generated") == reference.get("signals_generated"),
        "signals_survived": result.get("signals_survived") == reference.get("signals_survived"),
        "survival_rate": result.get("survival_rate") == reference.get("survival_rate"),
        "trade_rows_sha256": identity.get("trade_rows_sha256") == reference.get("trade_rows_sha256"),
        "daily_return_series_sha256": identity.get("daily_return_series_sha256") == reference.get("daily_return_series_sha256"),
        "sharpe_contract": identity.get("sharpe_inference_contract_passed") is True,
    }
    return checks


def _cash_passed(result: Mapping[str, Any]) -> bool:
    cash = result.get("cash_ledger") or {}
    return bool(
        cash.get("enforced") is True
        and cash.get("negative_cash_event_count") == 0
        and (_number(cash.get("min_cash")) or 0.0) >= 0.0
        and cash.get("cash_conservation_passed") is True
        and abs(_number(cash.get("cash_conservation_error")) or 0.0) < 1e-9
    )


def _run_gate_replay(
    resolver: Any,
    source_report: Mapping[str, Any],
    source_identity_before: Mapping[str, Any],
) -> dict[str, Any]:
    frozen = _load_frozen()
    active = json.loads(ACTIVE_BASELINE.read_text(encoding="utf-8"))
    references = {row["label"]: row for row in active["windows"]}
    windows: dict[str, Any] = {}
    before_results: dict[str, Any] = {}
    after_results: dict[str, Any] = {}

    for spec in gate1.WINDOWS:
        label = spec["label"]
        print(f"[{label}] before: exact cash-feasible Gate-1 replay", flush=True)
        before, before_identity = gate1._run_window(spec, frozen)
        reference_checks = _reference_checks(before, before_identity, references[label])
        if not all(reference_checks.values()):
            raise RuntimeError(f"{label}: Gate-1 identity mismatch: {reference_checks}")
        print(f"[{label}] after: Senate LDA 0.5 admission scalar", flush=True)
        after, after_identity, state = _run_after(spec, frozen, resolver)
        annotations = state["annotations"]
        touched = _touched_executed(before, after, annotations)
        before_head = _headline(before)
        after_head = _headline(after)
        signal_checks = {
            "entry_date_complete": all(
                row.get("entry_date_present") for row in annotations if row.get("entry_date")
            ),
            "target_price_complete": all(row.get("target_price_present") for row in annotations),
            "source_hash_complete": all(bool(row.get("source_hash")) for row in annotations),
            "index_hash_complete": all(bool(row.get("index_hash")) for row in annotations),
            "trade_annotations_match": all(row["annotation_matched"] for row in touched),
            "never_hard_excludes": before.get("signals_survived") == after.get("signals_survived"),
            "selection_identity": state["selection_identity_passed"],
            "patch_restored": state["patch_restored"],
        }
        windows[label] = {
            "window": dict(spec),
            "reference_checks": reference_checks,
            "before": before_head,
            "after": after_head,
            "delta": _delta(after_head, before_head),
            "before_identity": before_identity,
            "after_identity": after_identity,
            "before_artifact": _persist_result("before", spec, before),
            "after_artifact": _persist_result("after", spec, after),
            "annotations": annotations,
            "annotation_count": len(annotations),
            "material_annotation_count": sum(
                bool(row.get("material_share_change")) for row in annotations
            ),
            "touched_executed": touched,
            "touched_executed_count": len(touched),
            "signal_contract_checks": signal_checks,
            "signal_contract_passed": all(signal_checks.values()),
            "cash_passed": _cash_passed(after),
            "before_concentration": _positive_concentration(before),
            "after_concentration": _positive_concentration(after),
        }
        before_results[label] = before
        after_results[label] = after

    before_aggregate = _aggregate([windows[s["label"]]["before"] for s in gate1.WINDOWS])
    after_aggregate = _aggregate([windows[s["label"]]["after"] for s in gate1.WINDOWS])
    aggregate_delta = _delta(after_aggregate, before_aggregate)
    concentration: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before_c = windows[label]["before_concentration"]
        after_c = windows[label]["after_concentration"]
        checks: dict[str, bool] = {}
        for key, cap in (("single_share", 0.50), ("top5_share", 0.60), ("hhi", 0.35)):
            before_value = _number(before_c.get(key))
            after_value = _number(after_c.get(key))
            checks[key] = bool(
                before_value is not None
                and after_value is not None
                and after_value <= before_value + 1e-12
                and after_value <= cap + 1e-12
            )
        concentration[label] = {**checks, "all_pass": all(checks.values())}

    source_identity_after = _load_verified_source_archive()[1]
    source_unchanged = source_identity_after == source_identity_before
    gate1_pass = all(
        all(windows[s["label"]]["reference_checks"].values()) for s in gate1.WINDOWS
    )
    gate2_checks = {
        "zero_price_source_contract": source_report.get("all_pass") is True,
        "source_cache_unchanged_during_replay": source_unchanged,
        "runtime_signal_contract": all(
            windows[s["label"]]["signal_contract_passed"] for s in gate1.WINDOWS
        ),
        "cash_integrity": all(windows[s["label"]]["cash_passed"] for s in gate1.WINDOWS),
        "shared_daily_parity": (source_report.get("daily_parity") or {}).get(
            "all_sessions_match"
        ) is True,
    }
    gate3_checks = {
        s["label"]: windows[s["label"]]["after"]["survival_rate"] >= MIN_SURVIVAL_RATE
        for s in gate1.WINDOWS
    }
    per_window_gate4: dict[str, Any] = {}
    for spec in gate1.WINDOWS:
        label = spec["label"]
        before = windows[label]["before"]
        after = windows[label]["after"]
        benchmarks = after.get("benchmarks") or {}
        checks = {
            "minimum_five_touched_executed": windows[label]["touched_executed_count"]
            >= MIN_TOUCHED_EXECUTED_PER_WINDOW,
            "ev_non_regressing": after["expected_value_score"] >= before["expected_value_score"],
            "pnl_non_regressing": after["total_pnl"] >= before["total_pnl"],
            "drawdown_no_worse_than_plus_0p5pp": after["max_drawdown_pct"]
            <= before["max_drawdown_pct"] + MAX_DRAWDOWN_DRIFT,
            "worst_trade_non_regressing": after["worst_trade_pct"] >= before["worst_trade_pct"],
            "tail_loss_share_non_regressing": after["tail_loss_share"] <= before["tail_loss_share"],
            "trade_sample_floor": after["trade_count"] >= max(
                10, math.floor(0.80 * before["trade_count"])
            ),
            "beats_spy": float(benchmarks.get("strategy_vs_spy_pct") or 0.0) > 0.0,
            "beats_qqq": float(benchmarks.get("strategy_vs_qqq_pct") or 0.0) > 0.0,
            "concentration": concentration[label]["all_pass"],
        }
        per_window_gate4[label] = {**checks, "all_pass": all(checks.values())}
    gate4_checks = {
        "aggregate_ev_delta_gt_0p6206": aggregate_delta["expected_value_score"]
        > REQUIRED_EV_DELTA,
        "aggregate_pnl_delta_gt_10432p91": aggregate_delta["total_pnl"]
        > REQUIRED_PNL_DELTA,
        "aggregate_drawdown_guard": after_aggregate["max_drawdown_pct"]
        <= before_aggregate["max_drawdown_pct"] + MAX_DRAWDOWN_DRIFT,
        "survival_all_windows": all(gate3_checks.values()),
        "all_window_risk_sample_concentration": all(
            row["all_pass"] for row in per_window_gate4.values()
        ),
    }

    gates = {
        "gate1_exact_baseline": gate1_pass,
        "gate2_source_pit_signal_daily_hash_contract": all(gate2_checks.values()),
        "gate3_survival": all(gate3_checks.values()),
        "gate4_alpha_hurdle": all(gate4_checks.values()),
    }
    accepted = all(gates.values())
    before_measurement = {
        **before_aggregate,
        "windows": {label: row["before"] for label, row in windows.items()},
    }
    after_measurement = {
        **after_aggregate,
        "windows": {label: row["after"] for label, row in windows.items()},
    }
    gate1._atomic_write_json(BEFORE_FILE, before_measurement)
    gate1._atomic_write_json(AFTER_FILE, after_measurement)
    summary = {
        "schema": "senate_lda_regulatory_friction_gate4_v1",
        "experiment_id": EXPERIMENT_ID,
        "protocol_id": PROTOCOL_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": HYPOTHESIS,
        "baseline": {
            "path": _path_text(ACTIVE_BASELINE),
            "sha256": gate1._file_sha256(ACTIVE_BASELINE),
            "experiment_id": "exp-20260715-010",
        },
        "source_preflight": {
            "path": _path_text(SOURCE_PREFLIGHT_FILE),
            "sha256": gate1._file_sha256(SOURCE_PREFLIGHT_FILE),
            "report": dict(source_report),
        },
        "before": before_aggregate,
        "after": after_aggregate,
        "delta": aggregate_delta,
        "windows": windows,
        "concentration": concentration,
        "gate1": {"passed": gate1_pass},
        "gate2": {"checks": gate2_checks, "passed": all(gate2_checks.values())},
        "gate3": {"by_window": gate3_checks, "passed": all(gate3_checks.values())},
        "gate4": {
            "fixed_hurdles": {
                "minimum_touched_executed_per_window": MIN_TOUCHED_EXECUTED_PER_WINDOW,
                "aggregate_ev_delta_strictly_greater_than": REQUIRED_EV_DELTA,
                "aggregate_pnl_delta_strictly_greater_than": REQUIRED_PNL_DELTA,
                "max_drawdown_drift_percentage_points": 0.5,
            },
            "per_window": per_window_gate4,
            "checks": gate4_checks,
            "passed": all(gate4_checks.values()),
        },
        "gates": gates,
        "decision": "accepted_default_off" if accepted else "rejected",
        "shared_policy_contract": {
            "helper_module": "quant.senate_lda_regulatory_friction",
            "rule_version": lda_policy.RULE_VERSION,
            "scalar": lda_policy.ENTRY_SCALAR,
            "active_sessions": lda_policy.ACTIVE_SESSIONS,
            "post_selection_post_sizing": True,
            "never_hard_excludes": True,
            "backtester_monkeypatch_restored": True,
            "daily_snapshot": _path_text(LATEST_SNAPSHOT),
            "trade_enabled": False,
        },
        "execution_envelope": {
            "capital": "Only requested fresh-core entry shares are halved; native cash competition and caps remain in replay.",
            "liquidity_and_slippage": "Unchanged accepted next-open fill, gap-cancel, slippage and round-trip-cost contracts.",
            "portfolio_exposure": "Existing max-position, sector, heat and concentration limits remain unchanged.",
            "order_semantics": "Whole shares floor at one; no candidate is excluded; source failure resolves scalar 1.0.",
            "kill_switch": "Shared helper and latest snapshot are default-off with no order intents.",
            "live_ready": False,
        },
        "fingerprint_caveat": {
            "reservation": "Ticket initially classified as core_entry_admission/entry_admission and required the justified new-source override.",
            "repair": "The classifier was fixed in this same experiment ID to route the official source to senate_lda_quarterly_filings/entry_admission.",
            "close_requirement": "Before close, rebuild docs/frozen_families.jsonl and verify this family uses senate_lda_quarterly_filings.",
        },
        "production_impact": {
            "shared_helper": True,
            "daily_default_off_snapshot": True,
            "backtester_changed": False,
            "run_py_changed_by_this_runner": False,
            "live_orders_changed": False,
            "trade_enabled": False,
            "live_ready": False,
        },
        "reproduction": {
            "source_only": ".\\.venv\\Scripts\\python.exe -u -B quant\\experiments\\exp_20260720_005_senate_lda_regulatory_friction.py --source-only",
            "offline_gate1_4": ".\\.venv\\Scripts\\python.exe -u -B quant\\experiments\\exp_20260720_005_senate_lda_regulatory_friction.py --offline",
        },
    }
    gate1._atomic_write_json(SUMMARY_FILE, summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="fetch/load and validate the zero-price source contract; do not run backtests",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="refuse network and require a complete hash-valid source cache",
    )
    parser.add_argument(
        "--refresh-source",
        action="store_true",
        help="fetch a new source batch and atomically replace the manifest",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    filings, source_identity = _load_or_fetch_source(
        offline=args.offline, refresh=args.refresh_source
    )
    resolver, source_report, _latest = _zero_price_preflight(
        filings, source_identity
    )
    if not source_report["all_pass"]:
        failed = [key for key, passed in source_report["checks"].items() if not passed]
        raise RuntimeError(f"Senate LDA zero-price preflight failed: {failed}")
    if args.source_only:
        print(
            json.dumps(
                {
                    "source_only": True,
                    "source_manifest": _path_text(SOURCE_MANIFEST),
                    "source_preflight": _path_text(SOURCE_PREFLIGHT_FILE),
                    "latest_snapshot": _path_text(LATEST_SNAPSHOT),
                    "filing_count": source_identity["deduplicated_filing_count"],
                    "checks": source_report["checks"],
                },
                indent=2,
            )
        )
        return 0
    summary = _run_gate_replay(resolver, source_report, source_identity)
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "before": summary["before"],
                "after": summary["after"],
                "delta": summary["delta"],
                "gates": summary["gates"],
                "summary": _path_text(SUMMARY_FILE),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
