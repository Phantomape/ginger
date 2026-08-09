"""exp-20260714-004: first-release EIA WPSR de-stocking full stack.

This module owns the source/data boundary for the EIA WPSR de-stocking
experiment and its preregistered Gate evaluation. Online mode reads the
official versioned WPSR archive, validates every selected Table 4 CSV, and
freezes both raw bytes and a compact canonical record set. Offline mode
re-parses those bytes and fails closed on identity or schema drift. The fixed
OHLCV surface is copied read-only from the local warehouse; historical replay
and the as-of-safe daily snapshot share one default-off helper.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260714-004"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from eia_wpsr_destocking_energy_basket_paper_sleeve import (  # noqa: E402
    ENERGY_BASKET_V1,
    HOLD_SESSIONS,
    LEG_NOTIONAL_USD,
    MIN_AVG_DOLLAR_VOLUME_20D,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    SLIPPAGE_BPS_TARGET,
    build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot,
    empty_eia_wpsr_destocking_energy_basket_paper_state,
    replay_eia_wpsr_destocking_energy_basket_paper_trades,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)

ARCHIVE_INDEX_URL = "https://www.eia.gov/petroleum/supply/weekly/archive/"
SOURCE_START_DATE = date(2019, 1, 1)
HTTP_TIMEOUT_SECONDS = 30
HTTP_ATTEMPTS = 3
HTTP_WORKERS = 6
MAX_HTTP_BYTES = 5_000_000
USER_AGENT = (
    "ginger-research/exp-20260714-004 "
    "(read-only academic source archival; no API key)"
)

SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "eia_wpsr"
CANONICAL_RECORDS_PATH = SOURCE_DIR / "canonical_records.json"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
RAW_ARCHIVE_PATH = SOURCE_DIR / "raw_table4_csv.zip"

WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUXILIARY_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "eia_wpsr_destocking_energy_basket_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "eia_wpsr_destocking_energy_basket"
    / "latest_snapshot.json"
)
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_eia_wpsr_destocking_energy_basket.md"
)
BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
AUXILIARY_START = "2023-08-29"
AUXILIARY_END = "2026-04-21"

ENERGY_BASKET = (
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "OXY",
    "SLB",
    "BKR",
    "MPC",
    "VLO",
    "PSX",
)
REFERENCE_TICKERS = ("XLE", "USO", "SPY", "QQQ")
ALL_OHLCV_TICKERS = ENERGY_BASKET + REFERENCE_TICKERS

REQUIRED_SERIES = OrderedDict(
    (
        ("commercial_crude_oil_excluding_spr", "Commercial (Excluding SPR)"),
        ("total_motor_gasoline", "Total Motor Gasoline"),
        ("distillate_fuel_oil", "Distillate Fuel Oil"),
    )
)

OFFICIAL_ERRATA_RELEASE_DATE = "2023-12-28"
OFFICIAL_ERRATA_NOTICE_ZIP_MEMBER = (
    "issues/2023/2023_12_28/wpsr_2023_12_28_notice.html"
)
OFFICIAL_ERRATA_NOTICE_SUMMARY = (
    "EIA's December 28, 2023 notice says a prior propane/propylene correction "
    "introduced publication-wide revisions, so published weekly differences "
    "use corrected prior values that can differ from the displayed prior column."
)
OFFICIAL_ERRATA_NOTICE_FRAGMENTS = (
    "December 28, 2023 Notice",
    "discrepancy in many data series",
    "correction to propane/propylene stocks",
    "weekly difference value",
    "calculated using the revisions",
    "corrected values can be inferred",
    "adding the published weekly difference",
)
ARITHMETIC_TOLERANCE = 0.0021
KNOWN_STALE_DUPLICATE_RELEASE_DATE = "2019-07-03"
KNOWN_STALE_DUPLICATE_CANONICAL_RELEASE_DATE = "2019-06-26"
KNOWN_STALE_DUPLICATE_WEEK_ENDING = "2019-06-21"
KNOWN_STALE_DUPLICATE_SHA256 = (
    "e8e75163084b1d967d681a80de2f5e5d1b74279ce79ab2dbf6e30e79ab85c51f"
)

WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)

MIN_SETTLED_EVENTS = 12
MIN_SETTLED_EVENTS_PER_WINDOW = 3
MAX_DRAWDOWN_WORSE = 0.005
EXPECTED_DSR_ATTEMPTS = 1
PAPER_SNAPSHOT_AS_OF = AUXILIARY_END
ACCEPTED_CANDIDATE_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "event_cluster_sample_too_small",
        "seasonal_baseline_instability",
        "energy_beta_not_incremental",
        "basket_survivorship",
        "window_regression",
        "accepted_comparator_not_beaten",
        "concentration_failed",
    ],
}

ISSUE_PATH_RE = re.compile(
    r"^/petroleum/supply/weekly/archive/"
    r"(?P<year>20\d{2})/(?P<stamp>20\d{2}_\d{2}_\d{2})/"
    r"wpsr_(?P=stamp)\.php$"
)
HREF_RE = re.compile(r"\bhref\s*=\s*([\"'])(?P<href>.*?)\1", re.IGNORECASE)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class SourceContractError(RuntimeError):
    """Raised when official or frozen source bytes violate the fixed contract."""


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _bytes_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
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
    _atomic_write_bytes(path, _json_bytes(payload))


def _fetch_bytes(url: str, *, accept: str) -> tuple[bytes, dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(HTTP_ATTEMPTS):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": USER_AGENT,
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed official HTTPS URLs
                request, timeout=HTTP_TIMEOUT_SECONDS
            ) as response:
                status = int(getattr(response, "status", 200))
                if status != 200:
                    raise SourceContractError(f"HTTP {status} for {url}")
                raw = response.read(MAX_HTTP_BYTES + 1)
                if len(raw) > MAX_HTTP_BYTES:
                    raise SourceContractError(f"response too large for {url}")
                if not raw:
                    raise SourceContractError(f"empty response for {url}")
                final_url = str(response.geturl())
                if urllib.parse.urlsplit(final_url).hostname not in {
                    "www.eia.gov",
                    "eia.gov",
                }:
                    raise SourceContractError(
                        f"unexpected redirect host for {url}: {final_url}"
                    )
                return raw, {
                    "status": status,
                    "final_url": final_url,
                    "content_type": response.headers.get_content_type(),
                    "content_length": len(raw),
                    "attempts": attempt + 1,
                }
        except Exception as error:  # urllib emits several transport subclasses
            last_error = error
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(0.5 * (2**attempt))
    raise SourceContractError(
        f"failed to fetch {url} after {HTTP_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def _archive_issues(index_raw: bytes) -> list[dict[str, Any]]:
    try:
        text = index_raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SourceContractError("archive index is not valid UTF-8") from error

    by_date: dict[str, dict[str, Any]] = {}
    for match in HREF_RE.finditer(text):
        href = html.unescape(match.group("href")).strip()
        absolute = urllib.parse.urljoin(ARCHIVE_INDEX_URL, href)
        parsed = urllib.parse.urlsplit(absolute)
        path_match = ISSUE_PATH_RE.fullmatch(parsed.path)
        if parsed.hostname not in {"www.eia.gov", "eia.gov"} or not path_match:
            continue
        release = datetime.strptime(
            path_match.group("stamp"), "%Y_%m_%d"
        ).date()
        if release < SOURCE_START_DATE:
            continue
        release_text = release.isoformat()
        issue_url = urllib.parse.urlunsplit(
            ("https", "www.eia.gov", parsed.path, "", "")
        )
        csv_url = urllib.parse.urljoin(issue_url, "csv/table4.csv")
        member = (
            f"issues/{release.year}/{release.strftime('%Y_%m_%d')}/table4.csv"
        )
        candidate = {
            "release_date": release_text,
            "issue_url": issue_url,
            "csv_url": csv_url,
            "raw_zip_member": member,
        }
        previous = by_date.get(release_text)
        if previous is not None and previous != candidate:
            raise SourceContractError(
                f"conflicting archive issue URLs for {release_text}"
            )
        by_date[release_text] = candidate

    issues = [by_date[key] for key in sorted(by_date)]
    if not issues:
        raise SourceContractError("archive index has no issues since 2019-01-01")
    if issues[0]["release_date"] > "2019-01-10":
        raise SourceContractError(
            f"archive begins unexpectedly late: {issues[0]['release_date']}"
        )
    for previous, current in zip(issues, issues[1:]):
        left = date.fromisoformat(previous["release_date"])
        right = date.fromisoformat(current["release_date"])
        if (right - left).days > 15:
            raise SourceContractError(
                f"archive issue gap exceeds 15 days: {left} -> {right}"
            )
    return issues


def _parse_header_date(value: str, *, field: str, release_date: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%m/%d/%y").date()
    except ValueError as error:
        raise SourceContractError(
            f"invalid {field} {value!r} for release {release_date}"
        ) from error


def _number(value: str, *, field: str, release_date: str) -> float:
    try:
        result = float(value.strip())
    except ValueError as error:
        raise SourceContractError(
            f"non-numeric {field} {value!r} for release {release_date}"
        ) from error
    if not math.isfinite(result):
        raise SourceContractError(
            f"non-finite {field} {value!r} for release {release_date}"
        )
    return result


def _normal_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _validate_official_errata_notice(
    issue: dict[str, Any], raw: bytes
) -> dict[str, Any]:
    release_text = str(issue.get("release_date") or "")
    if release_text != OFFICIAL_ERRATA_RELEASE_DATE:
        raise SourceContractError(
            f"official errata notice is not allowlisted for {release_text!r}"
        )
    expected_url = (
        "https://www.eia.gov/petroleum/supply/weekly/archive/2023/"
        "2023_12_28/wpsr_2023_12_28.php"
    )
    if issue.get("issue_url") != expected_url:
        raise SourceContractError(
            f"unexpected official errata notice URL: {issue.get('issue_url')!r}"
        )
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SourceContractError("official errata notice is not valid UTF-8") from error
    plain_text = html.unescape(re.sub(r"<[^>]+>", " ", source))
    plain_text = re.sub(r"\s+", " ", plain_text).strip().casefold()
    missing = [
        fragment
        for fragment in OFFICIAL_ERRATA_NOTICE_FRAGMENTS
        if fragment.casefold() not in plain_text
    ]
    if missing:
        raise SourceContractError(
            f"official errata notice text contract drift: missing={missing}"
        )
    return {
        "official_notice_url": expected_url,
        "official_notice_sha256": _bytes_sha(raw),
        "official_notice_bytes": len(raw),
        "official_notice_zip_member": OFFICIAL_ERRATA_NOTICE_ZIP_MEMBER,
        "official_notice_summary": OFFICIAL_ERRATA_NOTICE_SUMMARY,
    }


def _parse_table4(issue: dict[str, Any], raw: bytes) -> dict[str, Any]:
    release_text = str(issue["release_date"])
    release = date.fromisoformat(release_text)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SourceContractError(
            f"Table 4 is not valid UTF-8 for {release_text}"
        ) from error

    rows = [
        row
        for row in csv.reader(io.StringIO(text, newline=""))
        if row and any(cell.strip() for cell in row)
    ]
    if len(rows) < 4:
        raise SourceContractError(f"Table 4 has too few rows for {release_text}")
    if any(len(row) != 8 for row in rows):
        widths = sorted({len(row) for row in rows})
        raise SourceContractError(
            f"Table 4 column drift for {release_text}: widths={widths}"
        )

    header = rows[0]
    if not (
        header[0].strip() == "STUB_1"
        and header[3].strip() == "Difference"
        and header[5].strip() == "Percent Change"
        and header[7].strip() == "Percent Change"
    ):
        raise SourceContractError(
            f"Table 4 header contract drift for {release_text}: {header}"
        )
    week_ending = _parse_header_date(
        header[1], field="week_ending", release_date=release_text
    )
    prior_week_ending = _parse_header_date(
        header[2], field="prior_week_ending", release_date=release_text
    )
    if (week_ending - prior_week_ending).days != 7:
        raise SourceContractError(
            f"Table 4 prior week is not seven days earlier for {release_text}"
        )
    release_lag = (release - week_ending).days
    if not 2 <= release_lag <= 13:
        raise SourceContractError(
            f"implausible release/week-ending lag for {release_text}: {release_lag}"
        )
    # The two comparison-date columns are dynamic but must remain dates.
    _parse_header_date(header[4], field="prior_year_date", release_date=release_text)
    _parse_header_date(header[6], field="two_year_date", release_date=release_text)

    by_label: dict[str, list[str]] = {}
    labels: list[str] = []
    for row in rows[1:]:
        label = _normal_label(row[0])
        if not label:
            raise SourceContractError(f"blank Table 4 label for {release_text}")
        if label in by_label:
            raise SourceContractError(
                f"duplicate Table 4 label {label!r} for {release_text}"
            )
        labels.append(label)
        by_label[label] = row
    if len(labels) != 26:
        raise SourceContractError(
            f"Table 4 data-row count drift for {release_text}: {len(labels)}"
        )

    is_official_errata = release_text == OFFICIAL_ERRATA_RELEASE_DATE
    if is_official_errata:
        required_notice_fields = (
            "official_notice_url",
            "official_notice_sha256",
            "official_notice_bytes",
            "official_notice_zip_member",
            "official_notice_summary",
        )
        missing_notice_fields = [
            field for field in required_notice_fields if not issue.get(field)
        ]
        if missing_notice_fields:
            raise SourceContractError(
                f"official errata metadata missing for {release_text}: "
                f"{missing_notice_fields}"
            )

    series: dict[str, dict[str, Any]] = {}
    has_arithmetic_mismatch = False
    for key, source_label in REQUIRED_SERIES.items():
        row = by_label.get(source_label)
        if row is None:
            raise SourceContractError(
                f"missing required Table 4 row {source_label!r} for {release_text}"
            )
        current = _number(
            row[1], field=f"{source_label}.current", release_date=release_text
        )
        prior = _number(
            row[2], field=f"{source_label}.prior", release_date=release_text
        )
        difference = _number(
            row[3], field=f"{source_label}.difference", release_date=release_text
        )
        implied_corrected_prior = round(current - difference, 6)
        arithmetic_residual = round(prior - implied_corrected_prior, 6)
        if abs(arithmetic_residual) > ARITHMETIC_TOLERANCE:
            has_arithmetic_mismatch = True
        if abs(arithmetic_residual) > ARITHMETIC_TOLERANCE and not is_official_errata:
            raise SourceContractError(
                f"difference arithmetic drift for {source_label!r} "
                f"on {release_text}: {current} - {prior} != {difference}"
            )
        series[key] = {
            "source_label": source_label,
            "unit": "million_barrels",
            "current": current,
            "prior": prior,
            "difference": difference,
            "implied_corrected_prior": implied_corrected_prior,
            "arithmetic_residual": arithmetic_residual,
        }

    if is_official_errata and not has_arithmetic_mismatch:
        raise SourceContractError(
            f"allowlisted official errata mismatch disappeared for {release_text}"
        )

    record = {
        "release_date": release_text,
        "week_ending": week_ending.isoformat(),
        "prior_week_ending": prior_week_ending.isoformat(),
        "issue_url": issue["issue_url"],
        "csv_url": issue["csv_url"],
        "source_url": issue["csv_url"],
        "raw_zip_member": issue["raw_zip_member"],
        "raw_csv_sha256": _bytes_sha(raw),
        "raw_sha256": _bytes_sha(raw),
        "raw_csv_bytes": len(raw),
        "schema": {
            "column_count": 8,
            "data_row_count": len(labels),
            "row_labels_sha256": _canonical_sha(labels),
            "dynamic_header": list(header),
        },
        "inventories": series,
        "series": series,
        "difference_semantics": (
            "official_errata_revision"
            if is_official_errata
            else "published_difference"
        ),
    }
    if is_official_errata:
        for field in (
            "official_notice_url",
            "official_notice_sha256",
            "official_notice_bytes",
            "official_notice_zip_member",
            "official_notice_summary",
        ):
            record[field] = issue[field]
    return record


def _download_issue_bundle(
    issues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, bytes], dict[str, Any]]:
    records_by_date: dict[str, dict[str, Any]] = {}
    raw_by_member: dict[str, bytes] = {}
    attempts = Counter()
    errors: list[str] = []

    def worker(issue: dict[str, Any]) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
        raw, response = _fetch_bytes(issue["csv_url"], accept="text/csv,*/*;q=0.1")
        return _parse_table4(issue, raw), raw, response

    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as executor:
        future_map = {executor.submit(worker, issue): issue for issue in issues}
        completed = 0
        for future in as_completed(future_map):
            issue = future_map[future]
            try:
                record, raw, response = future.result()
            except Exception as error:
                errors.append(f"{issue['release_date']}: {error}")
                continue
            release_text = record["release_date"]
            records_by_date[release_text] = record
            raw_by_member[record["raw_zip_member"]] = raw
            attempts[int(response["attempts"])] += 1
            completed += 1
            if completed % 50 == 0 or completed == len(issues):
                print(
                    f"EIA WPSR source: validated {completed}/{len(issues)} issues",
                    flush=True,
                )
    if errors:
        preview = "; ".join(errors[:10])
        raise SourceContractError(
            f"{len(errors)} EIA issue downloads failed; no source files written: {preview}"
        )
    records = [records_by_date[key] for key in sorted(records_by_date)]
    if len(records) != len(issues) or len(raw_by_member) != len(issues):
        raise SourceContractError("downloaded issue count does not match archive index")
    schema_fingerprints = {
        record["schema"]["row_labels_sha256"] for record in records
    }
    if len(schema_fingerprints) != 1:
        raise SourceContractError(
            f"Table 4 row-label schema drift: {sorted(schema_fingerprints)}"
        )
    return records, raw_by_member, {
        "attempt_histogram": {
            str(key): value for key, value in sorted(attempts.items())
        },
        "schema_fingerprint": next(iter(schema_fingerprints)),
    }


def _exclude_known_stale_duplicate(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_release = {row["release_date"]: row for row in records}
    stale = by_release.get(KNOWN_STALE_DUPLICATE_RELEASE_DATE)
    canonical = by_release.get(KNOWN_STALE_DUPLICATE_CANONICAL_RELEASE_DATE)
    if stale is None or canonical is None:
        raise SourceContractError("known 2019 stale duplicate releases are missing")
    if not (
        stale["week_ending"] == KNOWN_STALE_DUPLICATE_WEEK_ENDING
        and canonical["week_ending"] == KNOWN_STALE_DUPLICATE_WEEK_ENDING
        and stale["raw_sha256"] == KNOWN_STALE_DUPLICATE_SHA256
        and canonical["raw_sha256"] == KNOWN_STALE_DUPLICATE_SHA256
        and stale["inventories"] == canonical["inventories"]
    ):
        raise SourceContractError("known 2019 stale duplicate contract drifted")
    filtered = [
        row
        for row in records
        if row["release_date"] != KNOWN_STALE_DUPLICATE_RELEASE_DATE
    ]
    week_endings = [row["week_ending"] for row in filtered]
    if len(week_endings) != len(set(week_endings)):
        raise SourceContractError("unexpected duplicate EIA week-ending remains")
    return filtered, {
        "excluded_release_date": stale["release_date"],
        "canonical_release_date": canonical["release_date"],
        "week_ending": stale["week_ending"],
        "raw_sha256": stale["raw_sha256"],
        "raw_zip_member": stale["raw_zip_member"],
        "reason": (
            "The archived 2019-07-03 Table 4 CSV is byte-identical to the "
            "2019-06-26 issue and repeats week ending 2019-06-21; retain raw "
            "proof but exclude the later duplicate from statistical history."
        ),
    }


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for member, raw in sorted(members.items()):
            info = zipfile.ZipInfo(member, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    result = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(result), mode="r") as archive:
        if archive.testzip() is not None:
            raise SourceContractError("new deterministic source ZIP failed CRC validation")
    return result


def _window_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for label, (start, end) in WINDOWS.items():
        selected = [
            row["release_date"]
            for row in records
            if start <= row["release_date"] <= end
        ]
        output[label] = {
            "start": start,
            "end": end,
            "issue_count": len(selected),
            "first_release_date": selected[0] if selected else None,
            "last_release_date": selected[-1] if selected else None,
        }
    return output


def _gap_diagnostics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for previous, current in zip(records, records[1:]):
        left = date.fromisoformat(previous["release_date"])
        right = date.fromisoformat(current["release_date"])
        days = (right - left).days
        if days > 8:
            gaps.append(
                {
                    "previous_release_date": left.isoformat(),
                    "next_release_date": right.isoformat(),
                    "calendar_days": days,
                }
            )
    return gaps


def _validate_frozen_source_bundle() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required = (CANONICAL_RECORDS_PATH, SOURCE_MANIFEST_PATH, RAW_ARCHIVE_PATH)
    missing = [_repo_rel(path) for path in required if not path.exists()]
    if missing:
        raise SourceContractError(f"frozen EIA source bundle missing: {missing}")

    manifest = _read_json(SOURCE_MANIFEST_PATH)
    canonical = _read_json(CANONICAL_RECORDS_PATH)
    if manifest.get("schema") != "eia_wpsr_source_manifest_v1":
        raise SourceContractError("unexpected EIA source manifest schema")
    if canonical.get("schema") != "eia_wpsr_table4_canonical_records_v1":
        raise SourceContractError("unexpected EIA canonical-record schema")
    if manifest["files"]["canonical_records"]["sha256"] != _file_sha(
        CANONICAL_RECORDS_PATH
    ):
        raise SourceContractError("canonical_records.json file hash mismatch")
    if manifest["files"]["raw_archive"]["sha256"] != _file_sha(RAW_ARCHIVE_PATH):
        raise SourceContractError("raw_table4_csv.zip file hash mismatch")

    records = list(canonical.get("records") or [])
    if canonical.get("record_count") != len(records):
        raise SourceContractError("canonical EIA record count mismatch")
    if canonical.get("records_sha256") != _canonical_sha(records):
        raise SourceContractError("canonical EIA record-set hash mismatch")
    release_dates = [str(row.get("release_date") or "") for row in records]
    if release_dates != sorted(set(release_dates)):
        raise SourceContractError("canonical EIA release dates are not unique/sorted")
    if not release_dates or release_dates[0] < SOURCE_START_DATE.isoformat():
        raise SourceContractError("canonical EIA release-date range is invalid")
    week_endings = [str(row.get("week_ending") or "") for row in records]
    if week_endings != list(dict.fromkeys(week_endings)):
        raise SourceContractError("canonical EIA week endings are not unique")

    expected_members = {"source/archive_index.html"}
    expected_members.update(str(row["raw_zip_member"]) for row in records)
    expected_members.update(
        str(row["official_notice_zip_member"])
        for row in records
        if row.get("official_notice_zip_member")
    )
    stale_duplicate = manifest.get("known_stale_duplicate") or {}
    stale_member = str(stale_duplicate.get("raw_zip_member") or "")
    if stale_member:
        expected_members.add(stale_member)
    schema_fingerprints: set[str] = set()
    with zipfile.ZipFile(RAW_ARCHIVE_PATH, mode="r") as archive:
        if archive.testzip() is not None:
            raise SourceContractError("frozen EIA raw ZIP failed CRC validation")
        actual_members = set(archive.namelist())
        if actual_members != expected_members:
            raise SourceContractError(
                "frozen EIA raw ZIP members do not match canonical records"
            )
        index_raw = archive.read("source/archive_index.html")
        if _bytes_sha(index_raw) != manifest["archive_index"]["sha256"]:
            raise SourceContractError("frozen archive index hash mismatch")
        if (
            not stale_member
            or stale_duplicate.get("excluded_release_date")
            != KNOWN_STALE_DUPLICATE_RELEASE_DATE
            or stale_duplicate.get("canonical_release_date")
            != KNOWN_STALE_DUPLICATE_CANONICAL_RELEASE_DATE
            or stale_duplicate.get("week_ending")
            != KNOWN_STALE_DUPLICATE_WEEK_ENDING
            or stale_duplicate.get("raw_sha256")
            != KNOWN_STALE_DUPLICATE_SHA256
            or _bytes_sha(archive.read(stale_member))
            != KNOWN_STALE_DUPLICATE_SHA256
        ):
            raise SourceContractError("known stale duplicate manifest contract mismatch")
        selected_index_dates = {
            row["release_date"] for row in _archive_issues(index_raw)
        }
        if not set(release_dates).issubset(selected_index_dates):
            raise SourceContractError("canonical releases are absent from frozen index")
        for record in records:
            raw = archive.read(record["raw_zip_member"])
            if _bytes_sha(raw) != record["raw_csv_sha256"]:
                raise SourceContractError(
                    f"raw CSV hash mismatch for {record['release_date']}"
                )
            reparsed = _parse_table4(record, raw)
            if reparsed != record:
                raise SourceContractError(
                    f"raw/canonical replay mismatch for {record['release_date']}"
                )
            if record["release_date"] == OFFICIAL_ERRATA_RELEASE_DATE:
                notice_raw = archive.read(record["official_notice_zip_member"])
                notice_metadata = _validate_official_errata_notice(record, notice_raw)
                if any(
                    record.get(field) != value
                    for field, value in notice_metadata.items()
                ):
                    raise SourceContractError(
                        "official errata notice/canonical metadata mismatch"
                    )
            schema_fingerprints.add(record["schema"]["row_labels_sha256"])
    if schema_fingerprints != {manifest["table4_contract"]["row_labels_sha256"]}:
        raise SourceContractError("frozen Table 4 schema fingerprint mismatch")
    if manifest["coverage"]["record_count"] != len(records):
        raise SourceContractError("manifest EIA record count mismatch")
    errata_record = next(
        (
            record
            for record in records
            if record["release_date"] == OFFICIAL_ERRATA_RELEASE_DATE
        ),
        None,
    )
    if errata_record is None:
        raise SourceContractError("official errata release missing from canonical records")
    errata_manifest = manifest.get("official_errata") or {}
    if (
        errata_manifest.get("release_date") != OFFICIAL_ERRATA_RELEASE_DATE
        or errata_manifest.get("notice_url")
        != errata_record["official_notice_url"]
        or errata_manifest.get("notice_sha256")
        != errata_record["official_notice_sha256"]
        or errata_manifest.get("notice_zip_member")
        != errata_record["official_notice_zip_member"]
    ):
        raise SourceContractError("official errata manifest contract mismatch")
    return records, manifest


def materialize_source(
    *, offline: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch and freeze, or offline-validate, the first-release source bundle."""

    if offline:
        return _validate_frozen_source_bundle()

    index_raw, index_response = _fetch_bytes(
        ARCHIVE_INDEX_URL, accept="text/html,*/*;q=0.1"
    )
    issues = _archive_issues(index_raw)
    errata_issues = [
        issue
        for issue in issues
        if issue["release_date"] == OFFICIAL_ERRATA_RELEASE_DATE
    ]
    if len(errata_issues) != 1:
        raise SourceContractError(
            "archive index must contain exactly one 2023-12-28 errata issue"
        )
    errata_issue = errata_issues[0]
    notice_raw, notice_response = _fetch_bytes(
        errata_issue["issue_url"], accept="text/html,*/*;q=0.1"
    )
    notice_metadata = _validate_official_errata_notice(errata_issue, notice_raw)
    errata_issue.update(notice_metadata)
    print(
        f"EIA WPSR source: archive selected {len(issues)} issues "
        f"from {issues[0]['release_date']} through {issues[-1]['release_date']}",
        flush=True,
    )
    records, raw_by_member, download = _download_issue_bundle(issues)
    records, stale_duplicate = _exclude_known_stale_duplicate(records)
    raw_by_member[OFFICIAL_ERRATA_NOTICE_ZIP_MEMBER] = notice_raw

    canonical = {
        "schema": "eia_wpsr_table4_canonical_records_v1",
        "source": "U.S. EIA Weekly Petroleum Status Report archived Table 4",
        "source_start_release_date": SOURCE_START_DATE.isoformat(),
        "first_release_date": records[0]["release_date"],
        "last_release_date": records[-1]["release_date"],
        "record_count": len(records),
        "records_sha256": _canonical_sha(records),
        "records": records,
    }
    canonical_raw = _json_bytes(canonical)

    zip_members = {"source/archive_index.html": index_raw, **raw_by_member}
    archive_raw = _zip_bytes(zip_members)
    counts_by_year = Counter(row["release_date"][:4] for row in records)
    manifest = {
        "schema": "eia_wpsr_source_manifest_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "U.S. EIA Weekly Petroleum Status Report",
            "table": "Table 4",
            "description": (
                "Stocks of Crude Oil by PAD District, and Stocks of Petroleum "
                "Products, U.S. Totals"
            ),
            "authentication": "none",
            "api_key_required": False,
            "point_in_time_boundary": (
                "versioned archive issue date; CSV week-ending date is data time, "
                "not availability time"
            ),
        },
        "archive_index": {
            "url": ARCHIVE_INDEX_URL,
            "sha256": _bytes_sha(index_raw),
            "bytes": len(index_raw),
            "http": index_response,
        },
        "official_errata": {
            "release_date": OFFICIAL_ERRATA_RELEASE_DATE,
            "notice_url": notice_metadata["official_notice_url"],
            "notice_sha256": notice_metadata["official_notice_sha256"],
            "notice_bytes": notice_metadata["official_notice_bytes"],
            "notice_zip_member": notice_metadata["official_notice_zip_member"],
            "notice_summary": notice_metadata["official_notice_summary"],
            "validated_text_fragments": list(OFFICIAL_ERRATA_NOTICE_FRAGMENTS),
            "http": notice_response,
        },
        "known_stale_duplicate": stale_duplicate,
        "table4_contract": {
            "archive_url_template": (
                "https://www.eia.gov/petroleum/supply/weekly/archive/"
                "YYYY/YYYY_MM_DD/csv/table4.csv"
            ),
            "columns": [
                "STUB_1",
                "current_week_dynamic_date",
                "prior_week_dynamic_date",
                "Difference",
                "prior_year_dynamic_date",
                "Percent Change",
                "two_year_dynamic_date",
                "Percent Change",
            ],
            "duplicate_header_warning": (
                "Percent Change occurs twice; parse positionally with csv.reader"
            ),
            "required_rows": dict(REQUIRED_SERIES),
            "unit": "million_barrels",
            "data_row_count": 26,
            "row_labels_sha256": download["schema_fingerprint"],
            "difference_semantics": {
                "normal": "published_difference",
                "errata_allowlist": {
                    OFFICIAL_ERRATA_RELEASE_DATE: "official_errata_revision"
                },
                "implied_corrected_prior_formula": "current - difference",
                "arithmetic_residual_formula": (
                    "displayed prior - (current - published difference)"
                ),
                "normal_absolute_tolerance_million_barrels": (
                    ARITHMETIC_TOLERANCE
                ),
            },
        },
        "coverage": {
            "requested_start_release_date": SOURCE_START_DATE.isoformat(),
            "archive_issue_count": len(issues),
            "first_release_date": records[0]["release_date"],
            "last_release_date": records[-1]["release_date"],
            "record_count": len(records),
            "counts_by_year": {
                key: value for key, value in sorted(counts_by_year.items())
            },
            "canonical_windows": _window_counts(records),
            "gaps_over_eight_calendar_days": _gap_diagnostics(records),
        },
        "download": {
            "workers": HTTP_WORKERS,
            "attempt_histogram": download["attempt_histogram"],
            "fail_closed": True,
        },
        "files": {
            "canonical_records": {
                "path": _repo_rel(CANONICAL_RECORDS_PATH),
                "sha256": _bytes_sha(canonical_raw),
                "bytes": len(canonical_raw),
            },
            "raw_archive": {
                "path": _repo_rel(RAW_ARCHIVE_PATH),
                "sha256": _bytes_sha(archive_raw),
                "bytes": len(archive_raw),
                "member_count": len(zip_members),
                "deterministic_zip_timestamp": "1980-01-01T00:00:00",
            },
        },
    }

    # Manifest is the commit marker: only replace it after both referenced files.
    _atomic_write_bytes(RAW_ARCHIVE_PATH, archive_raw)
    _atomic_write_bytes(CANONICAL_RECORDS_PATH, canonical_raw)
    _atomic_write_json(SOURCE_MANIFEST_PATH, manifest)
    return _validate_frozen_source_bundle()


def _validate_auxiliary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != "eia_wpsr_auxiliary_ohlcv_v1":
        raise SourceContractError("unexpected EIA auxiliary OHLCV schema")
    if payload.get("start") != AUXILIARY_START or payload.get("end") != AUXILIARY_END:
        raise SourceContractError("frozen EIA auxiliary OHLCV range mismatch")
    if tuple(payload.get("tickers") or ()) != ALL_OHLCV_TICKERS:
        raise SourceContractError("frozen EIA auxiliary OHLCV ticker mismatch")
    ohlcv = payload.get("ohlcv") or {}
    if payload.get("rowset_sha256") != _canonical_sha(ohlcv):
        raise SourceContractError("frozen EIA auxiliary OHLCV row-set hash mismatch")
    expected_dates: list[str] | None = None
    total = 0
    for ticker in ALL_OHLCV_TICKERS:
        rows = list(ohlcv.get(ticker) or [])
        dates = [str(row.get("date") or "") for row in rows]
        if dates != sorted(set(dates)):
            raise SourceContractError(f"OHLCV dates not unique/sorted for {ticker}")
        if not dates or dates[0] != AUXILIARY_START or dates[-1] != AUXILIARY_END:
            raise SourceContractError(f"OHLCV boundary coverage mismatch for {ticker}")
        if expected_dates is None:
            expected_dates = dates
        elif dates != expected_dates:
            raise SourceContractError(f"OHLCV trading calendar mismatch for {ticker}")
        for row in rows:
            for field in ("open", "high", "low", "close", "volume"):
                value = row.get(field)
                if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise SourceContractError(
                        f"invalid OHLCV {field} for {ticker} {row.get('date')}"
                    )
        total += len(rows)
    if payload.get("row_count") != total:
        raise SourceContractError("frozen EIA auxiliary OHLCV row count mismatch")
    return payload


def materialize_auxiliary_ohlcv(*, offline: bool = False) -> dict[str, Any]:
    """Freeze the locked 10-stock basket and four references from SQLite."""

    if AUXILIARY_OHLCV_PATH.exists():
        return _validate_auxiliary_payload(_read_json(AUXILIARY_OHLCV_PATH))
    if offline:
        raise SourceContractError(
            f"offline auxiliary OHLCV missing: {_repo_rel(AUXILIARY_OHLCV_PATH)}"
        )
    if not WAREHOUSE_PATH.exists():
        raise SourceContractError(f"warehouse missing: {_repo_rel(WAREHOUSE_PATH)}")

    placeholders = ",".join("?" for _ in ALL_OHLCV_TICKERS)
    query = f"""
        SELECT ticker, date, open, high, low, close, volume, source, updated_at
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {
        ticker: [] for ticker in ALL_OHLCV_TICKERS
    }
    updated_at_values: list[str] = []
    source_counts = Counter()
    database_uri = WAREHOUSE_PATH.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        for row in connection.execute(
            query, [*ALL_OHLCV_TICKERS, AUXILIARY_START, AUXILIARY_END]
        ):
            (
                ticker,
                day,
                open_,
                high,
                low,
                close,
                volume,
                source,
                updated_at,
            ) = row
            ticker_text = str(ticker)
            updated_text = str(updated_at)
            source_text = str(source)
            rows_by_ticker[ticker_text].append(
                {
                    "date": str(day),
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume),
                    "source": source_text,
                    "updated_at": updated_text,
                }
            )
            updated_at_values.append(updated_text)
            source_counts[source_text] += 1
        run_manifest_generated_at = connection.execute(
            "SELECT MAX(generated_at) FROM run_manifest"
        ).fetchone()[0]

    stat = WAREHOUSE_PATH.stat()
    payload = {
        "schema": "eia_wpsr_auxiliary_ohlcv_v1",
        "experiment_id": EXPERIMENT_ID,
        "source_at_freeze": _repo_rel(WAREHOUSE_PATH),
        "warehouse_identity": {
            "sha256": _file_sha(WAREHOUSE_PATH),
            "bytes": stat.st_size,
            "filesystem_updated_at": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            "selected_rows_updated_at_min": min(updated_at_values),
            "selected_rows_updated_at_max": max(updated_at_values),
            "run_manifest_generated_at_max": run_manifest_generated_at,
            "selected_source_counts": {
                key: value for key, value in sorted(source_counts.items())
            },
            "read_only_sqlite_uri": True,
        },
        "start": AUXILIARY_START,
        "end": AUXILIARY_END,
        "energy_basket": list(ENERGY_BASKET),
        "reference_tickers": list(REFERENCE_TICKERS),
        "tickers": list(ALL_OHLCV_TICKERS),
        "ticker_row_counts": {
            ticker: len(rows_by_ticker[ticker]) for ticker in ALL_OHLCV_TICKERS
        },
        "row_count": sum(len(rows) for rows in rows_by_ticker.values()),
        "rowset_sha256": _canonical_sha(rows_by_ticker),
        "ohlcv": rows_by_ticker,
    }
    _validate_auxiliary_payload(payload)
    _atomic_write_json(AUXILIARY_OHLCV_PATH, payload)
    return _validate_auxiliary_payload(_read_json(AUXILIARY_OHLCV_PATH))


def _metric_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _bar_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or "")[:10]


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha(
        {"schema": "dated_periodic_return_series_v1", "rows": rows}
    )


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


def _baseline_curve(window: dict[str, Any]) -> list[tuple[str, float]]:
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    series = artifact["sharpe_inference"]["return_series"]
    equity = 100_000.0
    curve: list[tuple[str, float]] = []
    for row in series:
        equity *= 1.0 + float(row["return"])
        curve.append((str(row["date"]), equity))
    expected = 100_000.0 + float(window["total_pnl"])
    if not curve or abs(curve[-1][1] - expected) > 0.02:
        raise SourceContractError(
            f"baseline return-series reconstruction drift for {window['label']}"
        )
    return curve


def _window_ohlcv(
    broad: dict[str, list[dict[str, Any]]], baseline: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    snapshot_path = REPO_ROOT / str(baseline["source"])
    snapshot = (_read_json(snapshot_path).get("ohlcv") or {})
    output = {ticker: list(rows) for ticker, rows in broad.items()}
    exact: list[str] = []
    for ticker in ALL_OHLCV_TICKERS:
        if snapshot.get(ticker):
            output[ticker] = list(snapshot[ticker])
            exact.append(ticker)
    missing = sorted(ticker for ticker in ALL_OHLCV_TICKERS if not output.get(ticker))
    if missing:
        raise SourceContractError(f"required OHLCV coverage missing: {missing}")
    return output, {
        "gate1_snapshot": _repo_rel(snapshot_path),
        "gate1_snapshot_sha256": _file_sha(snapshot_path),
        "exact_snapshot_tickers": sorted(exact),
        "auxiliary_fill_tickers": sorted(set(ALL_OHLCV_TICKERS) - set(exact)),
    }


def _bar_index(
    ohlcv: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, rows in ohlcv.items():
        output[ticker] = {}
        for row in rows:
            day = str(row.get("date") or row.get("Date") or "")[:10]
            open_price = _metric_number(
                row.get("open") if "open" in row else row.get("Open")
            )
            close = _metric_number(
                row.get("close") if "close" in row else row.get("Close")
            )
            if day and open_price is not None and close is not None:
                output[ticker][day] = {"open": open_price, "close": close}
    return output


def _target_mark_on_date(
    trades: list[dict[str, Any]],
    bars: dict[str, dict[str, dict[str, float]]],
    day: str,
) -> float:
    mark = 0.0
    for trade in trades:
        if day < str(trade["entry_date"]):
            continue
        if day >= str(trade["exit_date"]):
            mark += float(trade["pnl"])
            continue
        close_row = bars.get(str(trade["ticker"]), {}).get(day)
        if close_row is None:
            raise SourceContractError(
                f"missing MTM close for {trade['ticker']} on {day}"
            )
        gross = close_row["close"] / float(trade["entry_price"]) - 1.0
        mark += float(trade["paper_notional_usd"]) * (
            gross - ROUND_TRIP_COST_PCT / 2.0
        )
    return mark


def _curve_metrics(
    curve: list[tuple[str, float]], *, trade_count: int
) -> dict[str, Any]:
    previous = 100_000.0
    returns: list[dict[str, Any]] = []
    peak = 100_000.0
    drawdown = 0.0
    for day, equity in curve:
        periodic_return = equity / previous - 1.0 if previous else 0.0
        returns.append({"date": day, "return": periodic_return})
        previous = equity
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    samples = [float(row["return"]) for row in returns]
    sharpe_full = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (
            len(samples) - 1
        )
        if variance > 0:
            sharpe_full = mean / math.sqrt(variance) * math.sqrt(252)
    total_pnl = curve[-1][1] - 100_000.0
    total_return_public = round(total_pnl / 100_000.0, 4)
    sharpe_public = round(sharpe_full, 2) if sharpe_full is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": total_return_public},
        "sharpe_daily": sharpe_public,
        "sharpe_daily_full_precision": sharpe_full,
        "expected_value_score": (
            round(total_return_public * sharpe_public, 4)
            if sharpe_public is not None
            else None
        ),
        "max_drawdown_pct": round(drawdown, 4),
        "total_trades": trade_count,
        "return_series": returns,
        "return_series_sha256": _return_series_sha(returns),
    }


def _combine_window(
    baseline: dict[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, float]]]:
    base_curve = _baseline_curve(baseline)
    bar_index = _bar_index(ohlcv)
    combined = [
        (day, equity + _target_mark_on_date(trades, bar_index, day))
        for day, equity in base_curve
    ]
    before = {
        "total_pnl": baseline["total_pnl"],
        "benchmarks": {
            "strategy_total_return_pct": round(
                float(baseline["total_pnl"]) / 100_000.0, 4
            )
        },
        "sharpe_daily": baseline["sharpe_daily"],
        "sharpe_daily_full_precision": baseline[
            "sharpe_daily_full_precision"
        ],
        "expected_value_score": baseline["expected_value_score"],
        "max_drawdown_pct": baseline["max_drawdown_pct"],
        "total_trades": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
    }
    after = _curve_metrics(
        combined, trade_count=int(baseline["trade_count"]) + len(trades)
    )
    return before, after, combined


def _target_summary(
    trades_by_window: dict[str, list[dict[str, Any]]],
    events_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    by_ticker_pnl: Counter[str] = Counter()
    by_ticker_count: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            by_ticker_pnl[ticker] += float(trade["pnl"])
            by_ticker_count[ticker] += 1
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    shares = (
        sorted((pnl / positive_total for pnl in positive.values()), reverse=True)
        if positive_total
        else []
    )
    event_counts = {
        label: len(events_by_window.get(label) or []) for label in WINDOWS
    }
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "settled_event_count": sum(event_counts.values()),
        "ticker_count": len(by_ticker_count),
        "tickers": sorted(by_ticker_count),
        "window_count": sum(count > 0 for count in event_counts.values()),
        "by_window_trade_count": {
            label: len(trades_by_window.get(label) or []) for label in WINDOWS
        },
        "by_window_settled_event_count": event_counts,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2)
            for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "hhi_concentration": (
            round(sum(share * share for share in shares), 6) if shares else None
        ),
        "top_5_contribution_pct": (
            round(sum(shares[:5]), 6) if shares else None
        ),
    }


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(row["before"]["expected_value_score"] for row in rows.values()),
            4,
        ),
        "after_expected_value_score_sum": round(
            sum(row["after"]["expected_value_score"] for row in rows.values()),
            4,
        ),
        "expected_value_score_delta_sum": round(
            sum(row["delta"]["expected_value_score"] for row in rows.values()),
            4,
        ),
        "before_total_pnl_sum": round(
            sum(row["before"]["total_pnl"] for row in rows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(row["after"]["total_pnl"] for row in rows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(row["delta"]["total_pnl"] for row in rows.values()), 2
        ),
        "windows_ev_improved": sum(
            row["delta"]["expected_value_score"] > 0 for row in rows.values()
        ),
        "windows_ev_regressed": sum(
            row["delta"]["expected_value_score"] < 0 for row in rows.values()
        ),
        "windows_pnl_improved": sum(
            row["delta"]["total_pnl"] > 0 for row in rows.values()
        ),
        "windows_pnl_regressed": sum(
            row["delta"]["total_pnl"] < 0 for row in rows.values()
        ),
        "max_drawdown_worse_max": max(
            row["delta"]["max_drawdown_pct"] for row in rows.values()
        ),
    }


def _benchmark_diagnostics(
    trades: list[dict[str, Any]],
    broad_ohlcv: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade["decision_id"])].append(trade)
    lookup = _bar_index(broad_ohlcv)
    events: list[dict[str, Any]] = []
    for decision_id, legs in sorted(grouped.items()):
        entry_dates = {str(row["entry_date"]) for row in legs}
        scheduled_dates = {str(row["scheduled_exit_date"]) for row in legs}
        if len(entry_dates) != 1 or len(scheduled_dates) != 1:
            raise SourceContractError(
                f"benchmark event dates disagree for {decision_id}"
            )
        notional = sum(float(row["paper_notional_usd"]) for row in legs)
        events.append(
            {
                "decision_id": decision_id,
                "entry_date": next(iter(entry_dates)),
                "scheduled_exit_date": next(iter(scheduled_dates)),
                "notional_usd": notional,
                "target_return": sum(float(row["pnl"]) for row in legs)
                / notional,
            }
        )
    target_returns = [row["target_return"] for row in events]
    target_mean = sum(target_returns) / len(target_returns) if events else None
    comparators: dict[str, Any] = {
        "TARGET": {
            "available": bool(events),
            "event_count": len(events),
            "mean_event_return": target_mean,
            "matched_total_pnl": sum(
                row["target_return"] * row["notional_usd"] for row in events
            ),
        },
        "CASH": {
            "available": bool(events),
            "event_count": len(events),
            "mean_event_return": 0.0 if events else None,
            "matched_total_pnl": 0.0 if events else None,
        },
    }
    for ticker in REFERENCE_TICKERS:
        returns: list[float] = []
        matched_pnl = 0.0
        missing: list[str] = []
        for event in events:
            entry = lookup.get(ticker, {}).get(event["entry_date"])
            exit_row = lookup.get(ticker, {}).get(event["scheduled_exit_date"])
            if entry is None or exit_row is None:
                missing.append(event["decision_id"])
                continue
            value = (
                exit_row["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
            )
            returns.append(value)
            matched_pnl += value * event["notional_usd"]
        complete = bool(events) and not missing
        comparators[ticker] = {
            "available": complete,
            "event_count": len(returns),
            "missing_decision_ids": missing,
            "mean_event_return": (
                sum(returns) / len(returns) if complete else None
            ),
            "matched_total_pnl": matched_pnl if complete else None,
        }
    required = ["CASH", *REFERENCE_TICKERS]
    unavailable = [name for name in required if not comparators[name]["available"]]
    failed_performance = [
        name
        for name in required
        if comparators[name]["available"]
        and (
            target_mean is None
            or target_mean <= float(comparators[name]["mean_event_return"])
        )
    ]
    return {
        "event_count": len(events),
        "event_equal_weighted": True,
        "benchmark_horizon": "same entry open to shared scheduled 10th-session close",
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "comparators": comparators,
        "required_comparators": required,
        "unavailable_comparators": unavailable,
        "failed_performance_comparators": failed_performance,
        "failed_comparators": list(
            dict.fromkeys([*unavailable, *failed_performance])
        ),
        "missing_required_is_hard_failure": True,
        "passed": bool(events) and not unavailable and not failed_performance,
    }


def _build_dsr(
    rows: dict[str, dict[str, Any]], source_manifest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    ordered_windows = sorted(WINDOWS, key=lambda label: WINDOWS[label][0])
    series = [
        point
        for label in ordered_windows
        for point in rows[label]["after"]["return_series"]
    ]
    dates = [str(point["date"]) for point in series]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SourceContractError("DSR return dates are not strictly aligned")
    panel = {
        "selected_config_id": "eia_wpsr_destocking_energy_basket_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": True,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            {
                "config_id": "eia_wpsr_destocking_energy_basket_on",
                "config": {
                    "rule_version": RULE_VERSION,
                    "series": list(REQUIRED_SERIES),
                    "basket": list(ENERGY_BASKET),
                },
                "attempted": True,
                "selection_scope": "eia_wpsr_first_release_destocking_energy_basket",
                "window": {
                    "segments": [
                        {
                            "label": label,
                            "start": WINDOWS[label][0],
                            "end": WINDOWS[label][1],
                        }
                        for label in ordered_windows
                    ]
                },
                "frequency": "daily",
                "return_basis": (
                    "core_plus_eia_fixed_energy_basket_daily_mtm_post_cost"
                ),
                "risk_free_assumption": "zero",
                "protocol": {
                    "id": "post_mtm_gate1_plus_eia_wpsr_destocking_v1",
                    "rule_version": RULE_VERSION,
                },
                "data": {
                    "baseline_summary_sha256": _file_sha(
                        BASELINE_SUMMARY_PATH
                    ),
                    "source_manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
                    "source_generated_at": source_manifest["generated_at"],
                    "auxiliary_ohlcv_sha256": _file_sha(AUXILIARY_OHLCV_PATH),
                },
                "cost": {"round_trip_cost_pct": ROUND_TRIP_COST_PCT},
                "return_series": series,
                "return_series_sha256": _return_series_sha(series),
                "return_series_source": (
                    f"{_repo_rel(RESULT_PATH)}#windows.*.after.return_series"
                ),
            }
        ],
    }
    report = build_dsr_report(panel)
    report["gate4_independence"] = True
    if report.get("status") != "computable":
        report["fail_closed_reason"] = (
            "single_preregistered_trial_has_no_cross_trial_dispersion"
        )
    _atomic_write_json(DSR_PANEL_PATH, panel)
    _atomic_write_json(DSR_REPORT_PATH, report)
    return panel, report


def _build_evaluation_payload(*, offline: bool) -> dict[str, Any]:
    if tuple(ENERGY_BASKET) != tuple(ENERGY_BASKET_V1):
        raise SourceContractError("source runner/helper energy basket drift")
    records, source_manifest = materialize_source(offline=offline)
    auxiliary = materialize_auxiliary_ohlcv(offline=offline)
    broad = {
        ticker: list(rows)
        for ticker, rows in (auxiliary.get("ohlcv") or {}).items()
    }
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise SourceContractError("active baseline window labels drifted")

    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]] = {}
    bar_identity: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv_by_window[label], bar_identity[label] = _window_ohlcv(
            broad, baseline_windows[label]
        )

    windows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    events_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    source_audits_valid = True
    for label, (start, end) in WINDOWS.items():
        ohlcv = ohlcv_by_window[label]
        trading_dates = [_bar_date(row) for row in ohlcv["SPY"]]
        replay = replay_eia_wpsr_destocking_energy_basket_paper_trades(
            records=records,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
            trading_dates=trading_dates,
        )
        trades = [dict(row, window=label) for row in replay["trades"]]
        events = [dict(row, window=label) for row in replay["event_trades"]]
        before, after, combined_curve = _combine_window(
            baseline_windows[label], trades, ohlcv
        )
        generated = int(replay["signals_generated"])
        survived = int(replay["signals_survived"])
        generated_total += generated
        survived_total += survived
        source_audits_valid = bool(
            source_audits_valid
            and replay["candidate_audit"].get("measurement_valid")
        )
        trades_by_window[label] = trades
        events_by_window[label] = events
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    after["expected_value_score"]
                    - before["expected_value_score"],
                    4,
                ),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"],
                    4,
                ),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": (
                float(replay["survival_rate"])
                if replay.get("survival_rate") is not None
                else (survived / generated if generated else 0.0)
            ),
            "selected_candidates": replay["selected_candidates"],
            "target_trades": trades,
            "event_trades": events,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "candidate_audit": replay["candidate_audit"],
            "combined_curve_sha256": _canonical_sha(combined_curve),
            "bar_identity": bar_identity[label],
        }

    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    all_selected_legs = [
        leg
        for label in WINDOWS
        for candidate in windows[label]["selected_candidates"]
        for leg in candidate["legs"]
    ]
    target = _target_summary(trades_by_window, events_by_window)
    aggregate = _aggregate_windows(windows)
    benchmark_surface: dict[str, list[dict[str, Any]]] = {
        ticker: [] for ticker in REFERENCE_TICKERS
    }
    for label, (start, end) in WINDOWS.items():
        for ticker in REFERENCE_TICKERS:
            benchmark_surface[ticker].extend(
                row
                for row in ohlcv_by_window[label][ticker]
                if start <= _bar_date(row) <= end
            )
    benchmarks = _benchmark_diagnostics(all_trades, benchmark_surface)

    gate2_passed = bool(all_selected_legs) and source_audits_valid and all(
        leg.get("entry_date") and leg.get("target_price")
        for leg in all_selected_legs
    )
    gate3_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0 and gate3_rate >= 0.05,
        "unit": "EIA weekly release event",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(gate3_rate, 6),
    }
    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["settled_event_count"],
        "adjusted_windows": [
            label
            for label, count in target["by_window_settled_event_count"].items()
            if count
        ],
        "adjusted_window_count": target["window_count"],
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target[
            "single_ticker_positive_share"
        ],
        "hhi_concentration": target["hhi_concentration"],
        "top_5_contribution_pct": target["top_5_contribution_pct"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["settled_event_count"]
            if target["settled_event_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_SETTLED_EVENTS,
        min_adjusted_windows=len(WINDOWS),
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        require_tail_concentration_not_worse=False,
    )
    canonical = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    strict = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=True
    )
    failures = list(canonical["hard_failures"])
    if aggregate["windows_pnl_regressed"]:
        failures.append("window_pnl_regression")
    if not gate2_passed:
        failures.append("gate2_signal_or_source_contract_failed")
    if not gate3["passed"]:
        failures.append("gate3_event_survival_below_5pct")
    if target["settled_event_count"] < MIN_SETTLED_EVENTS:
        failures.append("settled_event_count_below_12")
    for label, count in target["by_window_settled_event_count"].items():
        if count < MIN_SETTLED_EVENTS_PER_WINDOW:
            failures.append(f"settled_event_count_below_3:{label}")
    if not benchmarks["passed"]:
        failures.append("required_xle_uso_spy_qqq_cash_comparator_not_beaten")
    if (
        aggregate["expected_value_score_delta_sum"]
        <= ACCEPTED_CANDIDATE_COMPARATOR[
            "expected_value_score_delta_sum"
        ]
    ):
        failures.append("accepted_candidate_pool_ev_comparator_not_beaten")
    if (
        aggregate["total_pnl_delta_sum"]
        <= ACCEPTED_CANDIDATE_COMPARATOR["total_pnl_delta_sum"]
    ):
        failures.append("accepted_candidate_pool_pnl_comparator_not_beaten")
    failures = list(dict.fromkeys(failures))
    numeric_gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical": canonical,
        "strict_materiality": strict,
        "metrics": gate_metrics,
        "comparator_gate": benchmarks,
        "accepted_candidate_comparator": ACCEPTED_CANDIDATE_COMPARATOR,
    }
    measurement_validity_gate = {
        "passed": source_audits_valid,
        "status": "passed" if source_audits_valid else "blocked",
        "historical_first_release_vintage_pit": source_audits_valid,
        "archive_bytes_hash_verified": source_audits_valid,
        "release_date_availability_used": source_audits_valid,
        "known_2023_12_28_errata_contract_verified": source_audits_valid,
        "hard_failures": (
            [] if source_audits_valid else ["eia_source_contract_failed"]
        ),
        "fixed_current_basket_survivorship": (
            "disclosed selection-risk caveat; fixed deployment basket, not a "
            "post-result historical membership filter"
        ),
    }
    gate4_failures = list(
        dict.fromkeys(
            [
                *numeric_gate4["hard_failures"],
                *measurement_validity_gate["hard_failures"],
            ]
        )
    )
    gate4 = {
        **numeric_gate4,
        "passed": not gate4_failures,
        "status": "passed" if not gate4_failures else "blocked",
        "hard_failures": gate4_failures,
        "numeric_gate4": numeric_gate4,
        "measurement_validity_gate": measurement_validity_gate,
    }

    panel, dsr_report = _build_dsr(windows, source_manifest)
    envelope = ExecutionEnvelope(
        base_notional=LEG_NOTIONAL_USD,
        max_capital_pct=0.10,
        min_dollar_volume=MIN_AVG_DOLLAR_VOLUME_20D,
        slippage_bps=SLIPPAGE_BPS_TARGET,
        max_displacement=0,
        max_concurrent=len(ENERGY_BASKET),
        order_semantics=(
            "first_strictly_later_open_then_atr_target_or_10th_session_close"
        ),
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "Default-off one-event fixed basket; $1k per eligible leg, no "
            "missing-leg redistribution, 35bps round trip, no core displacement."
        ),
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=dsr_report,
    )
    verdict = full_stack_verdict(
        gate4=gate4, live_readiness=live, envelope=envelope
    )
    gate5 = {
        "passed": bool(live["ready"]),
        "status": "passed" if live["ready"] else "blocked",
        "gate4_independent": True,
        "honest_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "declared_selection_pool_complete": bool(
            panel.get("selection_pool_complete")
        ),
        "selection_pool_complete": bool(
            (dsr_report.get("gate5_dsr_report") or {}).get(
                "selection_pool_complete", False
            )
        ),
        "dsr_status": dsr_report.get("status"),
        "dsr_reason_codes": (
            (dsr_report.get("gate5_dsr_report") or {}).get("reason_codes")
            or (dsr_report.get("panel_result") or {}).get("reason_codes")
            or []
        ),
        "forward_live_readiness": live,
        "panel_path": _repo_rel(DSR_PANEL_PATH),
        "report_path": _repo_rel(DSR_REPORT_PATH),
    }

    late_surface = ohlcv_by_window["late_strong"]
    snapshot = build_eia_wpsr_destocking_energy_basket_paper_sleeve_snapshot(
        as_of_date=PAPER_SNAPSHOT_AS_OF,
        records=records,
        ohlcv_by_ticker=late_surface,
        trading_dates=[_bar_date(row) for row in late_surface["SPY"]],
        state=empty_eia_wpsr_destocking_energy_basket_paper_state(),
    )
    snapshot = {
        **snapshot,
        "experiment_id": EXPERIMENT_ID,
        "source_manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
        "one_shot_parity_artifact": True,
        "daily_wiring_retained": False,
        "live_orders_changed": False,
    }
    _atomic_write_json(PAPER_SNAPSHOT_PATH, snapshot)

    accepted = bool(gate4["passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_eia_wpsr_destocking_energy_basket"
            if accepted
            else "rejected_eia_wpsr_destocking_energy_basket_candidate_pool"
        ),
        "accepted_alpha": accepted,
        "hypothesis": (
            "A first-release broad de-stocking shock across commercial crude, "
            "motor gasoline, and distillate inventories precedes 10-session "
            "returns in a fixed diversified U.S. energy equity basket."
        ),
        "rule_version": RULE_VERSION,
        "locked_policy": {
            "source": "versioned first-release EIA WPSR archived Table 4 bytes",
            "series": list(REQUIRED_SERIES),
            "seasonal_baseline": "prior 5 years, same ISO week +/-2, minimum 15",
            "score": "negative equal-weight mean of three seasonal excess rates",
            "trigger": "at least 2 negative excess and strict trailing-104 p80",
            "cooldown_sessions": HOLD_SESSIONS,
            "basket": list(ENERGY_BASKET),
            "leg_notional_usd": LEG_NOTIONAL_USD,
            "entry": "first regular-session open strictly after release date",
            "exit": "3.5 ATR14 target otherwise 10th session close",
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
        "source": {
            "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
            "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
            "canonical_records": _repo_rel(CANONICAL_RECORDS_PATH),
            "canonical_records_sha256": _file_sha(CANONICAL_RECORDS_PATH),
            "raw_archive": _repo_rel(RAW_ARCHIVE_PATH),
            "raw_archive_sha256": _file_sha(RAW_ARCHIVE_PATH),
            "coverage": source_manifest["coverage"],
            "official_errata": source_manifest["official_errata"],
        },
        "calculation_identity": {
            "helper": {
                "path": "quant/eia_wpsr_destocking_energy_basket_paper_sleeve.py",
                "sha256": _file_sha(
                    REPO_ROOT
                    / "quant"
                    / "eia_wpsr_destocking_energy_basket_paper_sleeve.py"
                ),
            },
            "runner": {
                "path": _repo_rel(Path(__file__)),
                "sha256": _file_sha(Path(__file__)),
            },
            "auxiliary_ohlcv": {
                "path": _repo_rel(AUXILIARY_OHLCV_PATH),
                "file_sha256": _file_sha(AUXILIARY_OHLCV_PATH),
                "rowset_sha256": auxiliary["rowset_sha256"],
            },
        },
        "windows": windows,
        "aggregate": aggregate,
        "target_summary": target,
        "event_cluster_summary": {
            "unit": "settled EIA release decision",
            "settled_event_count": target["settled_event_count"],
            "by_window": target["by_window_settled_event_count"],
            "leg_rows_are_not_independent_events": True,
        },
        "benchmark_diagnostics": benchmarks,
        "accepted_candidate_comparator": ACCEPTED_CANDIDATE_COMPARATOR,
        "gate1": {
            "passed": True,
            "baseline": _repo_rel(BASELINE_SUMMARY_PATH),
            "baseline_sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "baseline_experiment_id": baseline_summary["experiment_id"],
            "auxiliary_ohlcv": _repo_rel(AUXILIARY_OHLCV_PATH),
            "bar_identity": bar_identity,
        },
        "gate2": {
            "passed": gate2_passed,
            "sentinel_fields": ["entry_date", "target_price"],
            "source_audits_valid": source_audits_valid,
        },
        "gate3": gate3,
        "numeric_gate4": numeric_gate4,
        "measurement_validity_gate": measurement_validity_gate,
        "gate4": gate4,
        "gate5": gate5,
        "deflated_sharpe": gate5,
        "full_stack": {
            "verdict": verdict,
            "one_shot_helper_snapshot_parity": True,
            "daily_candidate_as_of_safety_tested": True,
            "daily_wiring_retained": False,
            "forward_collection_automatic": False,
            "paper_snapshot": _repo_rel(PAPER_SNAPSHOT_PATH),
            "execution_envelope": envelope.to_dict(),
            "live_readiness": live,
        },
        "dsr_panel_sha256": _canonical_sha(panel),
        "prediction": PREDICTION,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "core_exits_changed": False,
            "run_adapter_changed": False,
            "shared_helper": (
                "quant/eia_wpsr_destocking_energy_basket_paper_sleeve.py"
            ),
            "historical_and_daily_selection_share_helper": True,
        },
        "residual_unknowns": [
            "The fixed current ten-stock deployment basket creates selection and survivorship risk even though no historical membership filter is used.",
            "The single preregistered attempt cannot supply cross-trial dispersion, so DSR is honestly not computable.",
            "No prospective closed events, replacement-value proof, or kill-switch parity exist yet.",
            "A historical three-window result cannot establish that the physical inventory relationship survives a future energy regime.",
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(gate4["hard_failures"])
                if gate4["hard_failures"]
                else "The locked first-release composite cleared every Gate-4 bar."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune series, seasonal window, p80, breadth, basket, "
                "hold, target, liquidity, cost, or canonical windows on this sample."
            ),
            "next_retry_requires": (
                "A genuinely new source/gate shape or materially more prospectively "
                "settled first-release EIA events with replacement-value evidence."
            ),
        },
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --offline --source-only",
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --offline",
        ],
    }


def _write_evaluation_outputs(payload: dict[str, Any]) -> None:
    _atomic_write_json(RESULT_PATH, payload)
    for path, side in ((BEFORE_PATH, "before"), (AFTER_PATH, "after")):
        _atomic_write_json(
            path,
            {
                "schema": f"eia_wpsr_destocking_energy_basket_gate4_{side}_v1",
                "experiment_id": EXPERIMENT_ID,
                "expected_value_score": payload["aggregate"][
                    f"{side}_expected_value_score_sum"
                ],
                "total_pnl": payload["aggregate"][f"{side}_total_pnl_sum"],
                "max_drawdown_pct": max(
                    row[side]["max_drawdown_pct"]
                    for row in payload["windows"].values()
                ),
                "total_trades": sum(
                    row[side]["total_trades"]
                    for row in payload["windows"].values()
                ),
                "survival_rate": (
                    payload["gate3"]["survival_rate"]
                    if side == "after"
                    else min(
                        row["before"]["survival_rate"]
                        for row in payload["windows"].values()
                    )
                ),
                "benchmarks": {
                    "strategy_total_return_pct": round(
                        payload["aggregate"][f"{side}_total_pnl_sum"]
                        / 100_000.0,
                        4,
                    )
                },
            },
        )

    lines = [
        f"# {EXPERIMENT_ID} EIA WPSR de-stocking energy basket",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Full-stack verdict: `{payload['full_stack']['verdict']['verdict']}`",
        (
            "- Settled EIA events / stock legs: "
            f"`{payload['target_summary']['settled_event_count']}` / "
            f"`{payload['target_summary']['total_trade_count']}`"
        ),
        f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']:+.4f}`",
        f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:+,.2f}`",
        f"- Gate 3 event survival: `{payload['gate3']['survival_rate']:.2%}`",
        (
            "- Failed matched benchmarks: `"
            + (", ".join(payload["benchmark_diagnostics"]["failed_comparators"]) or "none")
            + "`"
        ),
        (
            "- Numeric Gate 4 failures: `"
            + (", ".join(payload["numeric_gate4"]["hard_failures"]) or "none")
            + "`"
        ),
        (
            "- Binding Gate 4 failures: `"
            + (", ".join(payload["gate4"]["hard_failures"]) or "none")
            + "`"
        ),
        f"- Gate 5 / DSR: `{payload['gate5']['status']}` / `{payload['gate5']['dsr_status']}`",
        "",
        "## Window deltas",
        "",
    ]
    for label in WINDOWS:
        row = payload["windows"][label]
        lines.append(
            f"- {label}: settled_events={len(row['event_trades'])}, "
            f"legs={len(row['target_trades'])}, "
            f"EV={row['delta']['expected_value_score']:+.4f}, "
            f"PnL=${row['delta']['total_pnl']:+,.2f}, "
            f"drawdown={row['delta']['max_drawdown_pct']:+.4f}."
        )
    lines.extend(
        [
            "",
            "## Evidence contract",
            "",
            (
                f"The source bundle contains {payload['source']['coverage']['record_count']} "
                "versioned first-release issues. The 2023-12-28 arithmetic mismatch "
                "is accepted only under the frozen official EIA errata notice; every "
                "other issue remains fail-closed."
            ),
            "",
            (
                "Stock legs are used for PnL and concentration, but the independent "
                "sample unit is the settled weekly EIA release event. XLE, USO, SPY, "
                "QQQ, and cash are compared event-equally from the same entry open to "
                "the shared scheduled tenth-session close with the same 35 bps cost."
            ),
            "",
            (
                "The daily snapshot is a one-shot default-off parity artifact. No "
                "run.py wiring, automatic forward collection, live order, core "
                "ranking, sizing, or exit path changed."
            ),
            "",
            (
                "Reproduce offline: "
                f"`.\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --offline`"
            ),
        ]
    )
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Never access the network; require and revalidate frozen source bytes.",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Freeze or validate the EIA source bundle without materializing OHLCV.",
    )
    args = parser.parse_args()
    if args.source_only:
        records, manifest = materialize_source(offline=args.offline)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "mode": "offline" if args.offline else "online",
                    "source_only": True,
                    "source": {
                        "record_count": len(records),
                        "first_release_date": records[0]["release_date"],
                        "last_release_date": records[-1]["release_date"],
                        "records_sha256": _canonical_sha(records),
                        "canonical_window_coverage": manifest["coverage"][
                            "canonical_windows"
                        ],
                        "manifest_path": _repo_rel(SOURCE_MANIFEST_PATH),
                        "raw_archive_path": _repo_rel(RAW_ARCHIVE_PATH),
                    },
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return

    payload = _build_evaluation_payload(offline=args.offline)
    _write_evaluation_outputs(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "target_summary": payload["target_summary"],
                "aggregate": payload["aggregate"],
                "benchmark_gate": payload["benchmark_diagnostics"],
                "gate4_failures": payload["gate4"]["hard_failures"],
                "gate5": payload["gate5"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
