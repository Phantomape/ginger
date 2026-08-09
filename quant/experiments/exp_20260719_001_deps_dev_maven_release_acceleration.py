"""exp-20260719-001: deps.dev Maven release acceleration full-stack replay.

The runner freezes the publication timestamps returned by the official deps.dev
v3 GetPackage endpoint for a preregistered set of first-party Maven coordinates.
It then evaluates whether an issuer's completed Monday-Sunday non-SNAPSHOT
release count (at least two and strictly above its prior-eight-week median)
identifies a profitable next-open, ten-session candidate pool.

Source density is evaluated outcome-blind before the warehouse, baseline, or any
price data is opened.  The formal comparison conserves capital: 24% of the
accepted core return stream is replaced by the fully funded default-off sleeve.
This runner never emits orders or changes live configuration.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260719-001"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_fingerprint import infer_fingerprint  # noqa: E402
import deps_dev_maven_release_acceleration_paper_sleeve as policy  # noqa: E402
from quant.constants import ROUND_TRIP_COST_PCT  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.fill_model import (  # noqa: E402
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_TARGET,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
SOURCE_QUERY_START = "2024-08-05"
SOURCE_QUERY_END_EXCLUSIVE = "2026-04-22"
OHLCV_QUERY_START = "2024-08-01"
OHLCV_QUERY_END = "2026-05-15"

DEPS_DEV_API_ROOT = "https://api.deps.dev/v3/systems/maven/packages"
DEPS_DEV_API_HOST = "api.deps.dev"
HTTP_TIMEOUT_SECONDS = 30
HTTP_ATTEMPTS = 4
HTTP_WORKERS = 8
USER_AGENT = "ginger-alpha/exp-20260719-001 (default-off research)"

SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "deps_dev_maven_release_acceleration"
RELEASE_EVENTS_PATH = SOURCE_DIR / "release_events.jsonl"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
ISSUER_MAP_PATH = SOURCE_DIR / "package_issuer_map.json"
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULT_PATH = OUT_DIR / "result.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
VERDICT_PATH = OUT_DIR / "full_stack_verdict.json"
DAILY_SNAPSHOT_PATH = OUT_DIR / "daily_default_off_snapshot.json"
ARTIFACT_PATH = OUT_DIR / "artifact.md"

CORE_WEIGHT = 0.76
SLEEVE_WEIGHT = 0.24
SLEEVE_CAPITAL_USD = policy.PAPER_NOTIONAL_USD * policy.MAX_ACTIVE_POSITIONS
MIN_SETTLED_PER_WINDOW = 20
MIN_TICKERS_PER_WINDOW = 10
MAX_TOP1_COUNT_SHARE = 0.30
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_POSITIVE_HHI = 0.35
ACCEPTED_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10_432.91,
}
EXPECTED_FINGERPRINT = {
    "data_source": "deps_dev_maven_package_releases",
    "gate_shape": "candidate_pool_top3_10d",
}
EXPECTED_PACKAGE_COUNT = 29


class EvaluationContractError(RuntimeError):
    """A source, identity, market, or evaluation invariant failed closed."""


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: Any) -> None:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    _atomic_write_bytes(path, raw)


def _atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    raw = b"".join(
        json.dumps(
            dict(row),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
        for row in rows
    )
    _atomic_write_bytes(path, raw)


def _package_map_rows() -> list[dict[str, Any]]:
    """Return a canonical package-to-issuer map for either supported helper shape."""

    raw = policy.COORDINATE_TO_ISSUER
    rows: list[dict[str, Any]] = []
    default_valid_from = str(
        getattr(policy, "PACKAGE_MAP_EFFECTIVE_FROM", "2024-01-01")
    )[:10]
    if isinstance(raw, Mapping):
        for left, right in raw.items():
            if isinstance(right, str):
                if ":" in str(left):
                    rows.append(
                        {
                            "package": str(left),
                            "ticker": right,
                            "valid_from": default_valid_from,
                            "valid_to": None,
                        }
                    )
                else:
                    rows.append(
                        {
                            "package": right,
                            "ticker": str(left),
                            "valid_from": default_valid_from,
                            "valid_to": None,
                        }
                    )
            elif isinstance(right, Mapping):
                rows.append(
                    {
                        "package": str(
                            right.get("package")
                            or right.get("coordinate")
                            or right.get("package_name")
                            or left
                        ),
                        "ticker": str(right.get("ticker") or right.get("issuer") or left),
                        "valid_from": str(
                            right.get("valid_from")
                            or right.get("effective_from")
                            or default_valid_from
                        )[:10],
                        "valid_to": (
                            str(right["valid_to"])[:10]
                            if right.get("valid_to")
                            else None
                        ),
                    }
                )
            elif isinstance(right, (list, tuple, set)):
                for item in right:
                    if isinstance(item, Mapping):
                        package = item.get("package") or item.get("coordinate")
                        valid_from = item.get("valid_from") or default_valid_from
                        valid_to = item.get("valid_to")
                    else:
                        package = item
                        valid_from = default_valid_from
                        valid_to = None
                    rows.append(
                        {
                            "package": str(package),
                            "ticker": str(left),
                            "valid_from": str(valid_from)[:10],
                            "valid_to": str(valid_to)[:10] if valid_to else None,
                        }
                    )
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            if not isinstance(item, Mapping):
                raise EvaluationContractError("package map row must be an object")
            rows.append(
                {
                    "package": str(item.get("package") or item.get("coordinate")),
                    "ticker": str(item.get("ticker") or item.get("issuer")),
                    "valid_from": str(item.get("valid_from") or default_valid_from)[:10],
                    "valid_to": (
                        str(item["valid_to"])[:10] if item.get("valid_to") else None
                    ),
                }
            )
    else:
        raise EvaluationContractError("unsupported PACKAGE_ISSUER_MAP shape")

    canonical = sorted(rows, key=lambda row: (row["package"], row["ticker"]))
    packages = [row["package"] for row in canonical]
    if len(canonical) != EXPECTED_PACKAGE_COUNT or len(set(packages)) != len(packages):
        raise EvaluationContractError(
            f"package map identity drift: rows={len(canonical)} unique={len(set(packages))}"
        )
    if any(":" not in row["package"] for row in canonical):
        raise EvaluationContractError("Maven coordinate must be group:artifact")
    if any(not row["ticker"] or row["ticker"] == "None" for row in canonical):
        raise EvaluationContractError("package map contains an empty ticker")
    return canonical


def _issuer_tickers() -> set[str]:
    return {str(row["ticker"]) for row in _package_map_rows()}


def _http_json(url: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(HTTP_ATTEMPTS):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                final_url = str(response.geturl())
                host = (urllib.parse.urlsplit(final_url).hostname or "").lower()
                if host != DEPS_DEV_API_HOST:
                    raise EvaluationContractError(
                        f"unexpected deps.dev API redirect host: {final_url}"
                    )
                raw = response.read()
                if not raw:
                    raise EvaluationContractError("empty deps.dev API response")
                payload = json.loads(raw.decode("utf-8"))
                return payload, {
                    "url": url,
                    "final_url": final_url,
                    "status": int(getattr(response, "status", 200)),
                    "bytes": len(raw),
                    "attempts": attempt + 1,
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                }
        except urllib.error.HTTPError as error:
            if int(error.code) == 404:
                return None, {
                    "url": url,
                    "final_url": str(error.geturl()),
                    "status": 404,
                    "bytes": 0,
                    "attempts": attempt + 1,
                    "response_sha256": None,
                }
            last_error = error
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(0.5 * (attempt + 1))
        except Exception as error:  # network errors are retried, contracts fail later
            last_error = error
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(0.5 * (attempt + 1))
    raise EvaluationContractError(f"deps.dev API fetch failed: {last_error}") from last_error


def _fetch_package(
    map_row: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coordinate = str(map_row["package"])
    url = DEPS_DEV_API_ROOT + "/" + urllib.parse.quote(coordinate, safe="")
    payload, audit = _http_json(url)
    audit = {**audit, "package": coordinate, "ticker": str(map_row["ticker"])}
    if payload is None:
        return [], audit
    versions = payload.get("versions") or []
    if not isinstance(versions, list):
        raise EvaluationContractError(f"deps.dev versions schema drift: {coordinate}")
    rows: list[dict[str, Any]] = []
    for version_row in versions:
        if not isinstance(version_row, Mapping):
            continue
        key = version_row.get("versionKey") or {}
        version = (
            key.get("version") if isinstance(key, Mapping) else None
        ) or version_row.get("version")
        published_at = version_row.get("publishedAt") or version_row.get("published_at")
        if not version or not published_at or "SNAPSHOT" in str(version).upper():
            continue
        published_date = str(published_at)[:10]
        if not (SOURCE_QUERY_START <= published_date < SOURCE_QUERY_END_EXCLUSIVE):
            continue
        rows.append(
            {
                "ticker": str(map_row["ticker"]),
                "issuer_ticker": str(map_row["ticker"]),
                "package": coordinate,
                "package_name": coordinate,
                "coordinate": coordinate,
                "version": str(version),
                "published_at": str(published_at),
                "publishedAt": str(published_at),
                "published_date": published_date,
                "valid_from": str(map_row["valid_from"]),
                "valid_to": map_row.get("valid_to"),
            }
        )
    audit["returned_version_count"] = len(versions)
    audit["in_range_non_snapshot_count"] = len(rows)
    return rows, audit


def _issuer_map_payload() -> dict[str, Any]:
    rows = [
        {
            **row,
            "relation_type": "issuer_first_party_or_controlled_maven_coordinate",
            "evidence_basis": "predeclared effective-dated exact-coordinate map",
        }
        for row in _package_map_rows()
    ]
    return {
        "schema": "deps_dev_maven_package_issuer_map_v1",
        "rule_version": policy.SOURCE_RULE_VERSION,
        "ticker_count": len({row["ticker"] for row in rows}),
        "package_count": len(rows),
        "rows": rows,
    }


def materialize_source() -> dict[str, Any]:
    if RESULT_PATH.exists():
        raise EvaluationContractError(
            "immutable evaluation already exists; refusing source refresh"
        )
    map_rows = _package_map_rows()
    audits: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_package, row): str(row["package"])
            for row in map_rows
        }
        for future in concurrent.futures.as_completed(futures):
            package_rows, audit = future.result()
            raw_rows.extend(package_rows)
            audits.append(audit)
    canonical = policy.normalise_deps_dev_maven_release_rows(raw_rows)
    if len(canonical) < 1_000:
        raise EvaluationContractError(
            f"implausibly sparse deps.dev Maven release archive: {len(canonical)}"
        )
    map_payload = _issuer_map_payload()
    if map_payload["package_count"] != EXPECTED_PACKAGE_COUNT:
        raise EvaluationContractError("package issuer map identity drift")
    successful = sum(int(row.get("status") == 200) for row in audits)
    if successful < 20:
        raise EvaluationContractError(
            f"too few deps.dev package responses: {successful}/{EXPECTED_PACKAGE_COUNT}"
        )
    _atomic_write_json(ISSUER_MAP_PATH, map_payload)
    _atomic_write_jsonl(RELEASE_EVENTS_PATH, canonical)

    by_ticker = Counter(str(row["ticker"]) for row in canonical)
    by_window: dict[str, dict[str, Any]] = {}
    for label, (window_start, window_end) in WINDOWS.items():
        selected = [
            row
            for row in canonical
            if window_start <= _event_day(row) <= window_end
        ]
        counts = Counter(str(row["ticker"]) for row in selected)
        by_window[label] = {
            "release_event_count": len(selected),
            "ticker_count": len(counts),
            "top_tickers": counts.most_common(10),
        }
    manifest = {
        "schema": "deps_dev_maven_release_source_manifest_v1",
        "experiment_id": EXPERIMENT_ID,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "Google Open Source Insights deps.dev v3",
            "api": DEPS_DEV_API_ROOT,
            "query_contract": (
                "GetPackage for every frozen group:artifact coordinate; use "
                "authority-reported publishedAt; exclude SNAPSHOT versions"
            ),
            "historical_index_immutable": False,
            "maven_central_components_immutable": True,
            "revision_risk": (
                "deps.dev is a current dependency index, but publishedAt is reported "
                "by the package authority and Maven Central components are immutable; "
                "the exact retrieved canonical event set is hash-bound."
            ),
        },
        "coverage": {
            "start": SOURCE_QUERY_START,
            "end_exclusive": SOURCE_QUERY_END_EXCLUSIVE,
            "release_event_count": len(canonical),
            "ticker_count": len(by_ticker),
            "package_count": len(map_rows),
            "successful_package_count": successful,
            "missing_package_count": EXPECTED_PACKAGE_COUNT - successful,
            "by_window": by_window,
        },
        "files": {
            "release_events": _repo_rel(RELEASE_EVENTS_PATH),
            "release_events_sha256": _file_sha(RELEASE_EVENTS_PATH),
            "issuer_map": _repo_rel(ISSUER_MAP_PATH),
            "issuer_map_sha256": _file_sha(ISSUER_MAP_PATH),
        },
        "queries": sorted(audits, key=lambda row: row["package"]),
        "canonical_release_event_set_sha256": _canonical_sha(canonical),
    }
    _atomic_write_json(SOURCE_MANIFEST_PATH, manifest)
    return manifest


def load_source() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    missing = [
        _repo_rel(path)
        for path in (RELEASE_EVENTS_PATH, SOURCE_MANIFEST_PATH, ISSUER_MAP_PATH)
        if not path.exists()
    ]
    if missing:
        raise EvaluationContractError(f"source bundle missing: {missing}")
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    issuer_map = _read_json(ISSUER_MAP_PATH)
    failures: list[str] = []
    if _file_sha(RELEASE_EVENTS_PATH) != manifest.get("files", {}).get(
        "release_events_sha256"
    ):
        failures.append("release_events_file_hash_mismatch")
    if _file_sha(ISSUER_MAP_PATH) != manifest.get("files", {}).get("issuer_map_sha256"):
        failures.append("issuer_map_file_hash_mismatch")
    expected_map = _issuer_map_payload()
    if issuer_map != expected_map:
        failures.append("issuer_domain_map_policy_drift")
    rows: list[dict[str, Any]] = []
    with RELEASE_EVENTS_PATH.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise EvaluationContractError(
                    f"release events JSONL invalid at line {line_number}"
                ) from error
    canonical = policy.normalise_deps_dev_maven_release_rows(rows)
    if len(canonical) != len(rows):
        failures.append("release_events_not_canonical_or_duplicate")
    if _canonical_sha(canonical) != manifest.get("canonical_release_event_set_sha256"):
        failures.append("canonical_release_event_set_hash_mismatch")
    if manifest.get("coverage", {}).get("package_count") != EXPECTED_PACKAGE_COUNT:
        failures.append("source_package_count_drift")
    if manifest.get("coverage", {}).get("successful_package_count", 0) < 20:
        failures.append("source_successful_package_count_below_20")
    if failures:
        raise EvaluationContractError("source contract failed: " + ", ".join(failures))
    audit = {
        "passed": True,
        "hard_failures": [],

        "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
        "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
        "release_events": _repo_rel(RELEASE_EVENTS_PATH),
        "release_events_sha256": _file_sha(RELEASE_EVENTS_PATH),
        "canonical_release_event_count": len(canonical),
        "canonical_release_event_set_sha256": _canonical_sha(canonical),
        "deps_dev_current_index_revision_risk": True,
        "maven_central_component_immutability": True,
        "forward_append_only_evidence_preferred": True,
    }
    return canonical, manifest, audit


def _event_day(row: Mapping[str, Any]) -> str:
    value = (
        row.get("published_date")
        or row.get("release_date")
        or row.get("published_at")
        or row.get("publishedAt")
    )
    if not value:
        raise EvaluationContractError("release event missing publication date")
    return str(value)[:10]


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _source_density_preflight(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the preregistered source-only density gate before any market read."""

    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        ticker = str(row.get("ticker") or row.get("issuer_ticker") or "")
        day = date.fromisoformat(_event_day(row))
        week_end = day + timedelta(days=6 - day.weekday())
        counts[(ticker, week_end.isoformat())] += 1

    start_day = date.fromisoformat(SOURCE_QUERY_START)
    first_sunday = start_day + timedelta(days=6 - start_day.weekday())
    final_sunday = date.fromisoformat(SOURCE_QUERY_END_EXCLUSIVE) - timedelta(days=1)
    final_sunday -= timedelta(days=(final_sunday.weekday() - 6) % 7)
    sundays: list[str] = []
    cursor = first_sunday
    while cursor <= final_sunday:
        sundays.append(cursor.isoformat())
        cursor += timedelta(days=7)

    eligible: list[dict[str, Any]] = []
    for ticker in sorted(_issuer_tickers()):
        for index, week_end in enumerate(sundays):
            if index < 8:
                continue
            current = counts[(ticker, week_end)]
            prior = [counts[(ticker, day)] for day in sundays[index - 8 : index]]
            prior_median = _median(prior)
            if current >= 2 and current > prior_median:
                eligible.append(
                    {
                        "ticker": ticker,
                        "decision_week_end": week_end,
                        "current_release_count": current,
                        "prior_8w_median": prior_median,
                        "acceleration": current - prior_median,
                    }
                )

    by_window: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for label, (window_start, window_end) in WINDOWS.items():
        selected = [
            row
            for row in eligible
            if window_start <= str(row["decision_week_end"]) <= window_end
        ]
        by_ticker = Counter(str(row["ticker"]) for row in selected)
        top1 = by_ticker.most_common(1)[0][1] / len(selected) if selected else None
        checks = {
            "issuer_week_count_at_least_20": len(selected) >= MIN_SETTLED_PER_WINDOW,
            "ticker_count_at_least_10": len(by_ticker) >= MIN_TICKERS_PER_WINDOW,
            "top1_count_share_at_most_30pct": (
                top1 is not None and top1 <= MAX_TOP1_COUNT_SHARE
            ),
        }
        if not all(checks.values()):
            failures.append(f"outcome_blind_density_failed:{label}")
        by_window[label] = {
            "eligible_issuer_week_count": len(selected),
            "ticker_count": len(by_ticker),
            "top1_ticker": by_ticker.most_common(1)[0][0] if by_ticker else None,
            "top1_count_share": round(top1, 6) if top1 is not None else None,
            "by_ticker": dict(sorted(by_ticker.items())),
            "checks": checks,
        }
    return {
        "passed": not failures,
        "hard_failures": failures,
        "contract": {
            "minimum_current_release_count": 2,
            "prior_complete_weeks": 8,
            "strictly_above_prior_median": True,
            "minimum_eligible_issuer_weeks_per_window": MIN_SETTLED_PER_WINDOW,
            "minimum_tickers_per_window": MIN_TICKERS_PER_WINDOW,
            "maximum_top1_count_share": MAX_TOP1_COUNT_SHARE,
            "price_or_outcome_fields_read": False,
        },
        "eligible_issuer_week_count": len(eligible),
        "canonical_release_event_set_sha256": _canonical_sha(rows),
        "by_window": by_window,
    }


def _load_ohlcv() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    tickers = sorted(_issuer_tickers() | {"SPY", "QQQ"})
    placeholders = ",".join("?" for _ in tickers)
    sql = (
        "select ticker, date, open, high, low, close, volume from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(WAREHOUSE_PATH) as connection:
        for ticker, day, open_, high, low, close, volume in connection.execute(
            sql, [*tickers, OHLCV_QUERY_START, OHLCV_QUERY_END]
        ):
            rows_by_ticker[str(ticker)].append(
                {
                    "date": str(day)[:10],
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0.0),
                }
            )
    rows_by_ticker = {ticker: rows for ticker, rows in rows_by_ticker.items() if rows}
    if "SPY" not in rows_by_ticker or "QQQ" not in rows_by_ticker:
        raise EvaluationContractError("warehouse lacks SPY/QQQ calendar rows")
    identity_rows = [
        [ticker, row["date"], row["open"], row["high"], row["low"], row["close"]]
        for ticker, rows in sorted(rows_by_ticker.items())
        for row in rows
    ]
    return rows_by_ticker, {
        "warehouse": _repo_rel(WAREHOUSE_PATH),
        "query_start": OHLCV_QUERY_START,
        "query_end": OHLCV_QUERY_END,
        "ticker_count": len(rows_by_ticker),
        "row_count": len(identity_rows),
        "canonical_rowset_sha256": _canonical_sha(identity_rows),
    }


def _baseline_window_map(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): dict(row) for row in summary.get("windows") or []}


def _baseline_returns(window: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    series = artifact.get("sharpe_inference", {}).get("return_series") or []
    output = [
        {"date": str(row["date"])[:10], "return": float(row["return"])}
        for row in series
    ]
    if not output:
        raise EvaluationContractError(f"baseline return series missing: {window['label']}")
    equity = 100_000.0
    for row in output:
        equity *= 1.0 + row["return"]
    expected = 100_000.0 + float(window["total_pnl"])
    if abs(equity - expected) > 0.02:
        raise EvaluationContractError(f"baseline curve drift: {window['label']}")
    return output


def _bar_indices(
    ohlcv: Mapping[str, list[dict[str, Any]]]
) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, list[str]]]:
    exact: dict[str, dict[str, dict[str, float]]] = {}
    dates: dict[str, list[str]] = {}
    for ticker, rows in ohlcv.items():
        exact[ticker] = {
            str(row["date"]): {
                "open": float(row["open"]),
                "close": float(row["close"]),
            }
            for row in rows
        }
        dates[ticker] = sorted(exact[ticker])
    return exact, dates


def _close_on_or_before(
    exact: Mapping[str, Mapping[str, Mapping[str, float]]],
    dates: Mapping[str, list[str]],
    ticker: str,
    day: str,
) -> float:
    row = exact.get(ticker, {}).get(day)
    if row is not None:
        return float(row["close"])
    prior = [value for value in dates.get(ticker, []) if value <= day]
    if not prior:
        raise EvaluationContractError(f"missing MTM close for {ticker} on {day}")
    return float(exact[ticker][prior[-1]]["close"])


def _sleeve_marks(
    trades: list[dict[str, Any]],
    core_dates: list[str],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> list[float]:
    exact, dates = _bar_indices(ohlcv)
    marks: list[float] = []
    for day in core_dates:
        cumulative = 0.0
        for trade in trades:
            if day < str(trade["entry_date"]):
                continue
            if day >= str(trade["exit_date"]):
                cumulative += float(trade["pnl"])
                continue
            close = _close_on_or_before(exact, dates, str(trade["ticker"]), day)
            gross = close / float(trade["entry_price"]) - 1.0
            cumulative += float(trade["paper_notional_usd"]) * (
                gross - ROUND_TRIP_COST_PCT / 2.0
            )
        marks.append(cumulative)
    return marks


def _curve_metrics(
    dated_returns: list[dict[str, Any]], *, trade_count: int
) -> dict[str, Any]:
    equity = 100_000.0
    peak = equity
    max_drawdown = 0.0
    samples: list[float] = []
    curve: list[dict[str, Any]] = []
    for row in dated_returns:
        value = float(row["return"])
        samples.append(value)
        equity *= 1.0 + value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
        curve.append({"date": str(row["date"]), "return": value, "equity": equity})
    sharpe = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(252)
    total_pnl = equity - 100_000.0
    public_return = round(total_pnl / 100_000.0, 4)
    public_sharpe = round(sharpe, 2) if sharpe is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": public_return},
        "sharpe_daily": public_sharpe,
        "sharpe_daily_full_precision": sharpe,
        "expected_value_score": (
            round(public_return * public_sharpe, 4)
            if public_sharpe is not None
            else None
        ),
        "max_drawdown_pct": round(max_drawdown, 4),
        "total_trades": int(trade_count),
        "return_series": [
            {"date": row["date"], "return": row["return"]} for row in curve
        ],
        "return_series_sha256": _canonical_sha(
            [{"date": row["date"], "return": row["return"]} for row in curve]
        ),
    }


def _capital_neutral_window(
    baseline_window: Mapping[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    core_returns = _baseline_returns(baseline_window)
    dates = [row["date"] for row in core_returns]
    marks = _sleeve_marks(trades, dates, ohlcv)
    sleeve_returns: list[float] = []
    previous_equity = SLEEVE_CAPITAL_USD
    for mark in marks:
        equity = SLEEVE_CAPITAL_USD + mark
        if equity <= 0:
            raise EvaluationContractError("funded Maven sleeve equity became non-positive")
        sleeve_returns.append(equity / previous_equity - 1.0)
        previous_equity = equity
    combined_returns = [
        {
            "date": row["date"],
            "return": CORE_WEIGHT * float(row["return"]) + SLEEVE_WEIGHT * sleeve_return,
        }
        for row, sleeve_return in zip(core_returns, sleeve_returns)
    ]
    before = _curve_metrics(core_returns, trade_count=int(baseline_window["trade_count"]))
    after = _curve_metrics(
        combined_returns,
        trade_count=int(baseline_window["trade_count"]) + len(trades),
    )
    sleeve = {
        "initial_capital": SLEEVE_CAPITAL_USD,
        "ending_equity": round(previous_equity, 2),
        "total_pnl": round(previous_equity - SLEEVE_CAPITAL_USD, 2),
        "return_series": [
            {"date": day, "return": value}
            for day, value in zip(dates, sleeve_returns)
        ],
        "return_series_sha256": _canonical_sha(
            [{"date": day, "return": value} for day, value in zip(dates, sleeve_returns)]
        ),
        "capital_conserving": True,
        "core_weight": CORE_WEIGHT,
        "sleeve_weight": SLEEVE_WEIGHT,
    }
    return before, after, sleeve


def _aggregate_windows(windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(float(row["before"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "before_total_pnl_sum": round(
            sum(float(row["before"]["total_pnl"]) for row in windows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(float(row["after"]["total_pnl"]) for row in windows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(float(row["delta"]["total_pnl"]) for row in windows.values()), 2
        ),
        "windows_ev_improved": sum(
            float(row["delta"]["expected_value_score"]) > 0 for row in windows.values()
        ),
        "windows_ev_regressed": sum(
            float(row["delta"]["expected_value_score"]) < 0 for row in windows.values()
        ),
        "windows_pnl_improved": sum(
            float(row["delta"]["total_pnl"]) > 0 for row in windows.values()
        ),
        "windows_pnl_regressed": sum(
            float(row["delta"]["total_pnl"]) < 0 for row in windows.values()
        ),
        "max_drawdown_worse_max": max(
            float(row["delta"]["max_drawdown_pct"]) for row in windows.values()
        ),
    }


def _trade_summary(trades_by_window: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    count_by_ticker: Counter[str] = Counter()
    pnl_by_ticker: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            count_by_ticker[ticker] += 1
            pnl_by_ticker[ticker] += float(trade["pnl"])
    positive = {ticker: pnl for ticker, pnl in pnl_by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    shares = sorted(
        (pnl / positive_total for pnl in positive.values()), reverse=True
    ) if positive_total > 0 else []
    return {
        "settled_trade_count": sum(len(rows) for rows in trades_by_window.values()),
        "by_window": {label: len(trades_by_window[label]) for label in WINDOWS},
        "ticker_count": len(count_by_ticker),
        "by_ticker_count": dict(sorted(count_by_ticker.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(pnl_by_ticker.items())
        },
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "top_5_positive_pnl_share": round(sum(shares[:5]), 6) if shares else None,
        "hhi_positive_pnl": round(sum(share * share for share in shares), 6) if shares else None,
    }


def _benchmark_diagnostics(
    trades: list[dict[str, Any]],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    exact, _ = _bar_indices(ohlcv)
    target_pnl = sum(float(trade["pnl"]) for trade in trades)
    result: dict[str, Any] = {
        "target_pnl": round(target_pnl, 2),
        "cash_pnl": 0.0,
        "cash_replacement_value": round(target_pnl, 2),
    }
    passed = bool(trades) and target_pnl > 0
    for benchmark in ("SPY", "QQQ"):
        benchmark_pnl = 0.0
        missing: list[str] = []
        for trade in trades:
            entry = exact.get(benchmark, {}).get(str(trade["entry_date"]))
            exit_row = exact.get(benchmark, {}).get(str(trade["exit_date"]))
            if entry is None or exit_row is None:
                missing.append(str(trade["decision_id"]))
                continue
            entry_price = float(entry["open"]) * (1.0 + SLIPPAGE_BPS_ENTRY / 10_000.0)
            exit_price = float(exit_row["close"]) * (1.0 - SLIPPAGE_BPS_TARGET / 10_000.0)
            net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
            benchmark_pnl += policy.PAPER_NOTIONAL_USD * net_return
        value = round(benchmark_pnl, 2) if not missing else None
        replacement = round(target_pnl - benchmark_pnl, 2) if not missing else None
        result[benchmark.lower() + "_pnl"] = value
        result[benchmark.lower() + "_replacement_value"] = replacement
        result[benchmark.lower() + "_missing_decision_ids"] = missing
        passed = passed and not missing and replacement is not None and replacement > 0
    result["passed"] = bool(passed)
    return result


def _fingerprint_audit() -> dict[str, Any]:
    fingerprint = infer_fingerprint(
        "deps.dev Maven release acceleration ranks the top three liquid issuers "
        "for a next-open ten-session candidate pool.",
        "deps_dev_maven_release_acceleration",
        "deps_dev_maven_release_acceleration_top3_10d",
        "exact_coordinate_current_ge2_above_prior8w_median_top3_next_open_h10_v1",
    )
    failures = [
        f"fingerprint_{key}_mismatch"
        for key, expected in EXPECTED_FINGERPRINT.items()
        if fingerprint.get(key) != expected
    ]
    return {
        "passed": not failures,
        "hard_failures": failures,
        "expected": EXPECTED_FINGERPRINT,
        "actual": fingerprint,
    }


def build_evaluation() -> dict[str, Any]:
    release_events, source_manifest, source_audit = load_source()
    fingerprint = _fingerprint_audit()
    if not fingerprint["passed"]:
        raise EvaluationContractError(
            "fingerprint contract failed: " + ", ".join(fingerprint["hard_failures"])
        )
    # Hard ordering contract: this source-only gate must finish before any
    # warehouse, baseline, benchmark, price, or outcome artifact is opened.
    source_density_preflight = _source_density_preflight(release_events)
    if not source_density_preflight["passed"]:
        raise EvaluationContractError(
            "outcome-blind source density failed: "
            + ", ".join(source_density_preflight["hard_failures"])
        )

    ohlcv, market_identity = _load_ohlcv()
    calendar = [row["date"] for row in ohlcv["SPY"]]
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise EvaluationContractError("active Gate-1 window labels drifted")

    windows: dict[str, dict[str, Any]] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = policy.build_deps_dev_maven_release_acceleration_historical_trades(
            release_rows=release_events,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
            as_of=end,
            trading_dates=calendar,
            archive_start=SOURCE_QUERY_START,
        )
        trades = [dict(row, window=label) for row in replay["trades"]]
        before, after, sleeve = _capital_neutral_window(
            baseline_windows[label], trades, ohlcv
        )
        count_by_ticker = Counter(str(row["ticker"]) for row in trades)
        top1_share = (
            count_by_ticker.most_common(1)[0][1] / len(trades) if trades else None
        )
        benchmarks = _benchmark_diagnostics(trades, ohlcv)
        generated_total += int(replay["signals_generated"])
        survived_total += int(replay["signals_survived"])
        trades_by_window[label] = trades
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    float(after["expected_value_score"])
                    - float(before["expected_value_score"]),
                    4,
                ),
                "total_pnl": round(
                    float(after["total_pnl"]) - float(before["total_pnl"]), 2
                ),
                "max_drawdown_pct": round(
                    float(after["max_drawdown_pct"])
                    - float(before["max_drawdown_pct"]),
                    4,
                ),
            },
            "signals_generated": replay["signals_generated"],
            "signals_survived": replay["signals_survived"],
            "survival_rate": replay["survival_rate"],
            "eligible_weekly_rows": replay.get("window_eligible_rows") or [],
            "selected_decisions": replay["window_decisions"],
            "trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "settled_trade_count": len(trades),
            "settled_ticker_count": len(count_by_ticker),
            "settled_top1_count_share": round(top1_share, 6) if top1_share is not None else None,
            "matched_benchmarks": benchmarks,
            "funded_sleeve": sleeve,
            "orders": [],
        }

    aggregate = _aggregate_windows(windows)
    trade_summary = _trade_summary(trades_by_window)
    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    sentinel_fields = ("entry_date", "target_price", "entry_price", "exit_date", "exit_price")
    missing_sentinels = [
        str(trade.get("decision_id"))
        for trade in all_trades
        if any(trade.get(field) in (None, "") for field in sentinel_fields)
    ]
    gate2_failures: list[str] = []
    if not all_trades:
        gate2_failures.append("no_settled_shared_helper_trades")
    if missing_sentinels:
        gate2_failures.append("signal_contract_sentinel_missing")
    if any(trade.get("trade_enabled") is not False for trade in all_trades):
        gate2_failures.append("shared_helper_trade_enabled_drift")
    gate2 = {
        "passed": not gate2_failures,
        "hard_failures": gate2_failures,
        "sentinel_fields": list(sentinel_fields),
        "missing_sentinel_decision_ids": missing_sentinels,
        "orders": [],
    }
    survival_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0 and survival_rate >= 0.05,
        "unit": "eligible Maven-release-acceleration issuer-week",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(survival_rate, 6),
    }

    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": trade_summary["settled_trade_count"],
        "adjusted_windows": list(WINDOWS),
        "adjusted_window_count": len(WINDOWS),
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": trade_summary["single_ticker_positive_share"],
        "top_5_contribution_pct": trade_summary["top_5_positive_pnl_share"],
        "hhi_concentration": trade_summary["hhi_positive_pnl"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / trade_summary["settled_trade_count"]
            if trade_summary["settled_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_SETTLED_PER_WINDOW * len(WINDOWS),
        min_adjusted_windows=len(WINDOWS),
        min_ev_improved_windows=len(WINDOWS),
        max_ev_regressed_windows=0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        max_single_ticker_positive_share=1.0,
        max_top_5_contribution_pct=1.0,
        max_hhi_concentration=1.0,
        require_tail_concentration_evidence=False,
        require_tail_concentration_not_worse=False,
    )
    canonical_gate = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    strict_gate = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=True
    )
    failures = list(canonical_gate["hard_failures"])
    failures.extend(gate2["hard_failures"])
    if not gate3["passed"]:
        failures.append("gate3_survival_below_5pct")
    for label in WINDOWS:
        row = windows[label]
        if row["settled_trade_count"] < MIN_SETTLED_PER_WINDOW:
            failures.append(f"settled_trade_count_below_20:{label}")
        if row["settled_ticker_count"] < MIN_TICKERS_PER_WINDOW:
            failures.append(f"settled_ticker_count_below_10:{label}")
        top1 = row["settled_top1_count_share"]
        if top1 is None or top1 > MAX_TOP1_COUNT_SHARE:
            failures.append(f"settled_top1_share_above_30pct:{label}")
        if row["delta"]["total_pnl"] <= 0:
            failures.append(f"window_pnl_not_improved:{label}")
        if not row["matched_benchmarks"]["passed"]:
            failures.append(f"cash_spy_qqq_replacement_failed:{label}")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failures.append("accepted_candidate_pool_ev_comparator_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_candidate_pool_pnl_comparator_not_beaten")
    if (
        trade_summary["single_ticker_positive_share"] is None
        or trade_summary["single_ticker_positive_share"] > MAX_SINGLE_POSITIVE_SHARE
    ):
        failures.append("single_ticker_positive_pnl_concentration")
    if (
        trade_summary["top_5_positive_pnl_share"] is None
        or trade_summary["top_5_positive_pnl_share"] > MAX_TOP5_POSITIVE_SHARE
    ):
        failures.append("top5_positive_pnl_concentration")
    if (
        trade_summary["hhi_positive_pnl"] is None
        or trade_summary["hhi_positive_pnl"] > MAX_POSITIVE_HHI
    ):
        failures.append("positive_pnl_hhi_concentration")
    failures = list(dict.fromkeys(failures))
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical_candidate_pool_gate": canonical_gate,
        "strict_materiality_diagnostic_nonbinding": strict_gate,
        "metrics": gate_metrics,
        "accepted_candidate_comparator": ACCEPTED_COMPARATOR,
        "capital_accounting": {
            "passed": True,
            "core_weight": CORE_WEIGHT,
            "sleeve_weight": SLEEVE_WEIGHT,
            "sleeve_capital_usd": SLEEVE_CAPITAL_USD,
            "paper_pnl_overlay_on_full_core": False,
        },
        "source_contract": source_audit,
        "outcome_blind_source_density_preflight": source_density_preflight,
        "fingerprint_contract": fingerprint,
    }
    envelope = ExecutionEnvelope(
        base_notional=policy.PAPER_NOTIONAL_USD,
        max_capital_pct=SLEEVE_WEIGHT,
        min_dollar_volume=0.0,
        slippage_bps=float(SLIPPAGE_BPS_ENTRY + SLIPPAGE_BPS_TARGET),
        max_displacement=0,
        max_concurrent=policy.MAX_ACTIVE_POSITIONS,
        order_semantics="default_off_next_regular_open_then_session10_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "One active position per ticker; six positions x $4,000 = $24,000. "
            "Formal Gate4 is a 24% funded sleeve replacing core capital. Frozen "
            "deps.dev bytes are reproducible, but prospective rows and execution "
            "parity remain required before any live eligibility."
        ),
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=None,
    )
    verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)
    snapshot = policy.build_deps_dev_maven_release_acceleration_snapshot(
        release_rows=release_events,
        ohlcv_by_ticker=ohlcv,
        as_of=WINDOWS["late_strong"][1],
        start=WINDOWS["late_strong"][0],
        trading_dates=calendar,
        archive_start=SOURCE_QUERY_START,
        persist=False,
    )
    snapshot_replay = snapshot.get("replay") or {}
    replay_trade_ids = sorted(
        str(row["decision_id"]) for row in windows["late_strong"]["trades"]
    )
    snapshot_trade_ids = sorted(
        str(row["decision_id"]) for row in snapshot_replay.get("trades") or []
    )
    replay_decision_ids = sorted(
        str(row["decision_id"])
        for row in windows["late_strong"]["selected_decisions"]
    )
    snapshot_decision_ids = sorted(
        str(row["decision_id"])
        for row in snapshot_replay.get("window_decisions") or []
    )
    parity_failures: list[str] = []
    if snapshot.get("trade_enabled") is not False:
        parity_failures.append("snapshot_trade_enabled_drift")
    if snapshot.get("orders") not in (None, []):
        parity_failures.append("snapshot_orders_nonempty")
    if replay_trade_ids != snapshot_trade_ids:
        parity_failures.append("snapshot_historical_trade_ids_mismatch")
    if replay_decision_ids != snapshot_decision_ids:
        parity_failures.append("snapshot_historical_decision_ids_mismatch")
    daily_snapshot_parity = {
        "passed": not parity_failures,
        "hard_failures": parity_failures,
        "rule_version": snapshot["rule_version"],
        "source_rule_version": snapshot["source_rule_version"],
        "trade_enabled": snapshot["trade_enabled"],
        "orders": snapshot.get("orders") or [],
        "historical_trade_decision_ids_match": replay_trade_ids
        == snapshot_trade_ids,
        "historical_selected_decision_ids_match": replay_decision_ids
        == snapshot_decision_ids,
    }
    if parity_failures:
        raise EvaluationContractError(
            "daily/replay parity failed: " + ", ".join(parity_failures)
        )

    accepted = bool(gate4["passed"])
    result = {
        "schema": "deps_dev_maven_release_acceleration_full_stack_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_deps_dev_maven_release_acceleration"
            if accepted
            else "rejected_deps_dev_maven_release_acceleration"
        ),
        "accepted_alpha": accepted,
        "hypothesis": (
            "Weekly acceleration in immutable first-party Maven package releases "
            "is a PIT proxy for issuer product delivery and developer adoption."
        ),
        "locked_policy": {
            "rule_version": policy.RULE_VERSION,
            "source_rule_version": policy.SOURCE_RULE_VERSION,
            "complete_utc_week": True,
            "minimum_current_release_count": policy.MIN_CURRENT_RELEASE_COUNT,
            "prior_complete_weeks": policy.PRIOR_COMPLETE_WEEKS,
            "strictly_above_prior_median": True,
            "weekly_top_n": policy.MAX_WEEKLY_CANDIDATES,
            "entry": "first regular-session open after completed Sunday",
            "exit": "tenth session close",
            "paper_notional_usd": policy.PAPER_NOTIONAL_USD,
            "one_active_position_per_ticker": True,
            "max_active_positions": policy.MAX_ACTIVE_POSITIONS,
            "entry_slippage_bps": SLIPPAGE_BPS_ENTRY,
            "exit_slippage_bps": SLIPPAGE_BPS_TARGET,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "formal_core_weight": CORE_WEIGHT,
            "formal_sleeve_weight": SLEEVE_WEIGHT,
            "trade_enabled": False,
            "retunes": [],
        },
        "source": {
            "audit": source_audit,
            "manifest_coverage": source_manifest["coverage"],
            "outcome_blind_density_preflight": source_density_preflight,
            "revision_risk_disclosed": True,
        },
        "market_data": market_identity,
        "baseline": {
            "path": _repo_rel(BASELINE_SUMMARY_PATH),
            "sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "experiment_id": baseline_summary.get("experiment_id"),
        },
        "windows": windows,
        "aggregate": aggregate,
        "trade_summary": trade_summary,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "gate5": live,
        "full_stack_verdict": verdict,
        "daily_snapshot_parity": daily_snapshot_parity,
        "production_impact": {
            "shared_helper_used": True,
            "daily_default_off_snapshot_written": True,
            "daily_run_wiring_retained": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "trade_enabled": False,
            "deps_dev_current_index_revision_risk_disclosed": True,
            "maven_central_component_immutability": True,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed capital-neutral Maven release sleeve passed every binding "
                "Gate4 and comparator condition."
                if accepted
                else "The fixed capital-neutral Maven release sleeve failed one or more preregistered Gate4 conditions."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune current-count, prior-week span, acceleration threshold, "
                "top-N, coordinate subset, hold, costs, or capital weight on these windows."
            ),
            "new_evidence_required": (
                "At least 30 closed append-only forward Maven-release decisions with "
                "positive cash/SPY/QQQ replacement value, or a genuinely new source "
                "or gate shape."
            ),
        },
    }
    _atomic_write_json(DAILY_SNAPSHOT_PATH, snapshot)
    return result


def _aggregate_artifact(result: Mapping[str, Any], *, after: bool) -> dict[str, Any]:
    aggregate = result["aggregate"]
    metric_rows = [result["windows"][label]["after" if after else "before"] for label in WINDOWS]
    pnl_key = "after_total_pnl_sum" if after else "before_total_pnl_sum"
    ev_key = "after_expected_value_score_sum" if after else "before_expected_value_score_sum"
    return {
        "schema": "deps_dev_maven_release_acceleration_gate_artifact_v1",
        "experiment_id": EXPERIMENT_ID,
        "side": "after" if after else "before",
        "expected_value_score": aggregate[ev_key],
        "total_pnl": aggregate[pnl_key],
        "sharpe_daily": None,
        "benchmarks": {
            "strategy_total_return_pct": round(aggregate[pnl_key] / 300_000.0, 6)
        },
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in metric_rows),
        "total_trades": sum(int(row["total_trades"]) for row in metric_rows),
        "survival_rate": min(
            float(result["windows"][label]["survival_rate"]) for label in WINDOWS
        ) if after else min(
            float(_baseline_window_map(_read_json(BASELINE_SUMMARY_PATH))[label]["survival_rate"])
            for label in WINDOWS
        ),
        "windows": {
            label: result["windows"][label]["after" if after else "before"]
            for label in WINDOWS
        },
        "full_stack_gate4": result["gate4"],
    }


def _artifact_markdown(result: Mapping[str, Any]) -> str:
    preflight = result["source"]["outcome_blind_density_preflight"]
    lines = [
        f"# {EXPERIMENT_ID}: deps.dev Maven release acceleration",
        "",
        f"- Status: `{result['status']}`",
        f"- Decision: `{result['decision']}`",
        "- Policy: completed Monday-Sunday count >=2 and strictly above the prior-eight-week median; weekly top 3; next open; tenth-session close.",
        "- Capital: 24% funded sleeve + 76% accepted core; default-off; no orders.",
        f"- Source event SHA-256: `{preflight['canonical_release_event_set_sha256']}`",
        "",
        "## Outcome-blind source density",
        "",
        "| Window | Eligible issuer-weeks | Tickers | Top-1 share | Pass |",
        "|---|---:|---:|---:|:---:|",
    ]
    for label in WINDOWS:
        row = preflight["by_window"][label]
        lines.append(
            f"| {label} | {row['eligible_issuer_week_count']} | "
            f"{row['ticker_count']} | {float(row['top1_count_share'] or 0):.2%} | "
            f"{'yes' if all(row['checks'].values()) else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Gate 1-4 replay",
            "",
            "| Window | Settled | Tickers | EV delta | PnL delta | Cash/SPY/QQQ |",
            "|---|---:|---:|---:|---:|:---:|",
        ]
    )
    for label in WINDOWS:
        row = result["windows"][label]
        lines.append(
            f"| {label} | {row['settled_trade_count']} | "
            f"{row['settled_ticker_count']} | {row['delta']['expected_value_score']:.4f} | "
            f"{row['delta']['total_pnl']:.2f} | "
            f"{'pass' if row['matched_benchmarks']['passed'] else 'fail'} |"
        )
    aggregate = result["aggregate"]
    lines.extend(
        [
            "",
            f"Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']}`.",
            f"Aggregate PnL delta: `{aggregate['total_pnl_delta_sum']}`.",
            f"Gate 2: `{'pass' if result['gate2']['passed'] else 'fail'}`; Gate 3: `{'pass' if result['gate3']['passed'] else 'fail'}`; Gate 4: `{'pass' if result['gate4']['passed'] else 'fail'}`.",
            "",
            "## Binding failures",
            "",
        ]
    )
    failures = list(result["gate4"]["hard_failures"])
    lines.extend(f"- `{failure}`" for failure in failures)
    if not failures:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "The source bundle and all result JSON files are hash-bound/reproducible. "
            "This paper sleeve remains live-ineligible until forward replacement-value and kill-switch parity requirements pass.",
            "",
        ]
    )
    return "\n".join(lines)


def write_evaluation(result: dict[str, Any]) -> None:
    if RESULT_PATH.exists():
        raise EvaluationContractError("result commit marker exists; refusing overwrite")
    before = _aggregate_artifact(result, after=False)
    after = _aggregate_artifact(result, after=True)
    verdict = {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "accepted_alpha": result["accepted_alpha"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "gate5": result["gate5"],
        "full_stack_verdict": result["full_stack_verdict"],
    }
    result["output_bundle"] = {
        "before": _repo_rel(BEFORE_PATH),
        "after": _repo_rel(AFTER_PATH),
        "verdict": _repo_rel(VERDICT_PATH),
        "daily_snapshot": _repo_rel(DAILY_SNAPSHOT_PATH),
        "artifact_markdown": _repo_rel(ARTIFACT_PATH),
    }
    _atomic_write_json(BEFORE_PATH, before)
    _atomic_write_json(AFTER_PATH, after)
    _atomic_write_json(VERDICT_PATH, verdict)
    _atomic_write_bytes(ARTIFACT_PATH, _artifact_markdown(result).encode("utf-8"))
    _atomic_write_json(RESULT_PATH, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--refresh-source",
        action="store_true",
        help="Fetch and hash-bind all frozen deps.dev Maven package histories.",
    )
    modes.add_argument(
        "--offline",
        action="store_true",
        help="Evaluate only from the frozen source and warehouse; never fetch.",
    )
    args = parser.parse_args()
    try:
        if args.refresh_source:
            manifest = materialize_source()
            release_events, _, _ = load_source()
            preflight = _source_density_preflight(release_events)
            print(
                json.dumps(
                    {
                        "experiment_id": EXPERIMENT_ID,
                        "mode": "refresh_source",
                        "release_event_count": manifest["coverage"][
                            "release_event_count"
                        ],
                        "ticker_count": manifest["coverage"]["ticker_count"],
                        "package_count": manifest["coverage"]["package_count"],
                        "successful_package_count": manifest["coverage"][
                            "successful_package_count"
                        ],
                        "outcome_blind_density_passed": preflight["passed"],
                        "outcome_blind_density_by_window": preflight["by_window"],
                        "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
                        "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
                    },
                    indent=2,
                )
            )
            return 0 if preflight["passed"] else 3
        if not args.offline:
            raise EvaluationContractError(
                "choose exactly one mode: --refresh-source, then --offline"
            )
        result = build_evaluation()
        write_evaluation(result)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": result["status"],
                    "gate4_passed": result["gate4"]["passed"],
                    "aggregate_ev_delta": result["aggregate"]["expected_value_score_delta_sum"],
                    "aggregate_pnl_delta": result["aggregate"]["total_pnl_delta_sum"],
                    "hard_failures": result["gate4"]["hard_failures"],
                    "result": _repo_rel(RESULT_PATH),
                },
                indent=2,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": "failed_closed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
