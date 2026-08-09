"""exp-20260715-007: Treasury auction weak-demand TBT full stack.

The first online run freezes official, date-stamped Treasury auction result
XML and an auxiliary adjusted TBT price response.  Offline runs consume only
those frozen bytes.  Historical replay and the default-off daily snapshot use
the same shared policy helper; no live, paper-order, core ranking, or sizing
path is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import math
import os
import re
import statistics
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


EXPERIMENT_ID = "exp-20260715-007"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260714_004_eia_wpsr_destocking_energy_basket as gate_utils  # noqa: E402
from treasury_auction_weak_demand_tbt_paper_sleeve import (  # noqa: E402
    HOLD_SESSIONS,
    LOOKBACK_AUCTIONS,
    NOTIONAL_USD,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    TICKER,
    build_treasury_auction_tbt_snapshot,
    build_weak_auction_events,
    replay_weak_auction_tbt,
)


OWNER = "alpha-explore"
SLUG = "treasury_auction_weak_demand_tbt_full_stack"
RUNNER = f"quant/experiments/exp_20260715_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "treasury_auction_results"
API_ROWS_PATH = SOURCE_DIR / "api_rows.json"
XML_ZIP_PATH = SOURCE_DIR / "result_xml.zip"
XML_PARTS_DIR = SOURCE_DIR / "result_xml_parts"
PDF_ZIP_PATH = SOURCE_DIR / "result_pdf_fallback.zip"
PDF_PARTS_DIR = SOURCE_DIR / "result_pdf_fallback_parts"
PDF_HTTP_META_PATH = SOURCE_DIR / "result_pdf_fallback_http_metadata.json"
RESULTS_PAGE_PATH = SOURCE_DIR / "auction_results_page.html"
CANONICAL_PATH = SOURCE_DIR / "canonical_records.json"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
TBT_RAW_PATH = OUT_DIR / "tbt_chart_raw.json"
MARKET_RAW_PATHS = {
    "TBT": TBT_RAW_PATH,
    "SPY": OUT_DIR / "spy_chart_raw.json",
    "QQQ": OUT_DIR / "qqq_chart_raw.json",
}
PRICE_PANEL_PATH = OUT_DIR / "price_panel.json"
RESULT_PATH = OUT_DIR / f"exp_20260715_007_{SLUG}.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "treasury_auction_weak_demand_tbt"
    / "latest_snapshot.json"
)
ARTIFACT_PATH = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
CARD_PATH = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_PATH = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
LOG_PATH = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_PATH = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_PATH = REPO_ROOT / "docs" / "experiment_registry.json"
PLAYBOOK_PATH = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
FINGERPRINT_PATH = REPO_ROOT / "scripts" / "experiment_fingerprint.py"
FROZEN_FAMILIES_PATH = REPO_ROOT / "docs" / "frozen_families.jsonl"

BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
SNAPSHOT_PATHS = {
    "old_thin": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    "mid_weak": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    "late_strong": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
}

ALLOWED_ORIGINAL_TERMS = (
    "2-Year",
    "3-Year",
    "5-Year",
    "7-Year",
    "10-Year",
    "20-Year",
    "30-Year",
)
SOURCE_START = "2023-01-01"
API_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
API_PATH = "/v1/accounting/od/auctions_query"
STATIC_RESULT_BASE = (
    "https://fiscaldata.treasury.gov/static-data/published-reports/"
    "auctions-query/results/"
)
RESULTS_PAGE_URL = (
    "https://www.treasurydirect.gov/auctions/announcements-data-results/"
    "announcement-results-press-releases/auction-results/"
)
RESULTS_PAGE_REQUIRED_CLAUSES = (
    "updated on a real-time basis",
    "as soon as auction results are made available",
)
USER_AGENT = (
    "ginger-research/exp-20260715-007 "
    "(read-only official auction archival; no credentials)"
)
HTTP_TIMEOUT = 30
HTTP_ATTEMPTS = 5
HTTP_WORKERS = 3
MAX_API_BYTES = 20_000_000
MAX_XML_BYTES = 200_000
MAX_PDF_BYTES = 2_000_000
MAX_PAGE_BYTES = 3_000_000
MAX_TBT_BYTES = 10_000_000
XML_NAME_RE = re.compile(r"^R_(?P<stamp>\d{8})_\d+\.xml$")
ORIGINAL_TERM_RE = re.compile(r"^(?P<years>\d+)-Year$", re.IGNORECASE)
CONFIRMED_PERSISTENT_XML_503 = {
    "R_20241104_3.xml",
    "R_20241105_2.xml",
    "R_20241106_2.xml",
    "R_20241120_3.xml",
}
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

MIN_TOTAL_TRADES = 30
MIN_WINDOW_TRADES = 10
MAX_DRAWDOWN_WORSE = 0.005
MIN_DSR_PROBABILITY = 0.95
EXPECTED_DSR_ATTEMPTS = 7
MAX_TOP_TENOR_POSITIVE_SHARE = 0.35
MAX_TOP5_TRADE_POSITIVE_SHARE = 0.60
ACCEPTED_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

HYPOTHESIS = (
    "Official Treasury auction results where a nominal coupon auction "
    "bid-to-cover ratio is strictly below the median of the prior 12 auctions "
    "for the same original tenor should predict positive next-session-open "
    "to fifth-session-close TBT replacement value and improve the "
    "core-plus-sleeve aggregate."
)
NEW_EVIDENCE_AXIS = (
    "New source and gate shape: hash-bound official Treasury auction result "
    "XML supplies publication-dated bid-to-cover microstructure, evaluated "
    "as a strict next-session five-session non-overlapping TBT event sleeve."
)
NEARBY_PRIORS = [
    "exp-20260711-016",
    "exp-20260607-024",
    "exp-20260605-030",
    "exp-20260605-032",
    "exp-20260711-004",
]
PREDICTION_FALLBACK = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "next_open_absorbs_auction_signal",
        "nonoverlap_sample_too_small",
        "tbt_daily_reset_decay_and_cost",
        "window_regression",
        "accepted_comparator_not_beaten",
        "static_xml_contract_failure",
        "positive_pnl_concentration",
    ],
    "confidence_reason": (
        "The source and event gate are new, but next-open absorption, leveraged "
        "ETF decay, and the champion comparator make acceptance unlikely."
    ),
}


class SourceContractError(RuntimeError):
    """Raised when official/frozen source bytes violate the fixed contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_bytes(
        path,
        (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        ).encode("utf-8"),
    )


def atomic_write_text(path: Path, payload: str) -> None:
    atomic_write_bytes(path, payload.encode("utf-8"))


def fetch_bytes(url: str, *, max_bytes: int) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, HTTP_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise SourceContractError(f"response exceeded byte cap: {url}")
            if not payload:
                raise SourceContractError(f"empty response: {url}")
            return payload
        except Exception as exc:  # pragma: no cover - network branch
            last_error = exc
            if attempt < HTTP_ATTEMPTS:
                time.sleep(float(2 ** (attempt - 1)))
    raise SourceContractError(f"download failed after {HTTP_ATTEMPTS} attempts: {url}: {last_error}")


def fetch_bytes_with_headers(
    url: str, *, max_bytes: int
) -> tuple[bytes, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(1, HTTP_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                payload = response.read(max_bytes + 1)
                headers = {
                    str(key).lower(): str(value)
                    for key, value in response.headers.items()
                }
            if len(payload) > max_bytes:
                raise SourceContractError(f"response exceeded byte cap: {url}")
            if not payload:
                raise SourceContractError(f"empty response: {url}")
            return payload, headers
        except Exception as exc:  # pragma: no cover - network branch
            last_error = exc
            if attempt < HTTP_ATTEMPTS:
                time.sleep(float(2 ** (attempt - 1)))
    raise SourceContractError(
        f"download with headers failed after {HTTP_ATTEMPTS} attempts: {url}: {last_error}"
    )


def auction_api_url() -> str:
    query = urllib.parse.urlencode(
        {
            "filter": f"auction_date:gte:{SOURCE_START}",
            "page[size]": "10000",
        }
    )
    return f"{API_BASE}{API_PATH}?{query}"


def filter_api_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = payload.get("data")
    if not isinstance(raw_rows, list):
        raise SourceContractError("Fiscal Data payload missing data rows")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        if raw.get("security_type") not in {"Note", "Bond"}:
            continue
        if raw.get("inflation_index_security") != "No" or raw.get("floating_rate") != "No":
            continue
        if raw.get("original_security_term") not in ALLOWED_ORIGINAL_TERMS:
            continue
        if not raw.get("bid_to_cover_ratio") or not raw.get("xml_filenm_comp_results"):
            continue
        if not XML_NAME_RE.fullmatch(str(raw.get("xml_filenm_comp_results"))):
            raise SourceContractError(
                f"unexpected result XML filename: {raw.get('xml_filenm_comp_results')!r}"
            )
        auction_date = str(raw.get("auction_date") or "")[:10]
        cusip = str(raw.get("cusip") or "").strip()
        key = (auction_date, cusip)
        if not auction_date or not cusip or key in seen:
            raise SourceContractError(f"duplicate/missing auction identity: {key}")
        seen.add(key)
        rows.append(dict(raw))
    rows.sort(key=lambda row: (str(row["auction_date"]), str(row["original_security_term"]), str(row["cusip"])))
    if len(rows) < 200:
        raise SourceContractError(f"nominal coupon auction coverage unexpectedly thin: {len(rows)}")
    return rows


def xml_field_map(payload: bytes) -> dict[str, str]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise SourceContractError(f"invalid Treasury result XML: {exc}") from exc
    values: dict[str, str] = {}
    for node in root.iter():
        name = node.tag.rsplit("}", 1)[-1]
        text = (node.text or "").strip()
        if name and name not in values:
            values[name] = text
    return values


def normalize_contract_text(value: Any) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split()
    )


def parse_contract_date(value: Any, *, field: str, filename: str) -> date:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError as exc:
        raise SourceContractError(f"invalid {field} for {filename}: {value!r}") from exc


def expected_anniversary(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(month=2, day=28, year=day.year + years)


def parse_release_time(value: Any, *, filename: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%H:%M").time()
    except ValueError as exc:
        raise SourceContractError(f"invalid ReleaseTime for {filename}: {text!r}") from exc
    if parsed.hour >= 16:
        raise SourceContractError(
            f"auction result is not safely observable before next-session entry: {filename} {text}"
        )
    return parsed.strftime("%H:%M")


def page_supports_publication_clock(payload: bytes) -> bool:
    decoded = payload.decode("utf-8", errors="replace")
    visible = re.sub(r"<[^>]+>", " ", html.unescape(decoded))
    normalized = " ".join(visible.lower().split())
    return all(clause in normalized for clause in RESULTS_PAGE_REQUIRED_CLAUSES)


def validate_xml_row(row: dict[str, Any], payload: bytes) -> dict[str, Any]:
    filename = str(row["xml_filenm_comp_results"])
    match = XML_NAME_RE.fullmatch(filename)
    if not match:
        raise SourceContractError(f"unexpected result XML filename: {filename}")
    filename_date = datetime.strptime(match.group("stamp"), "%Y%m%d").date().isoformat()
    fields = xml_field_map(payload)
    auction_date = str(row["auction_date"])[:10]
    if filename_date != auction_date or fields.get("AuctionDate") != auction_date:
        raise SourceContractError(f"result date mismatch for {filename}")
    if fields.get("CUSIP") != str(row["cusip"]):
        raise SourceContractError(f"CUSIP mismatch for {filename}")
    if fields.get("SecurityType", "").title() != str(row["security_type"]):
        raise SourceContractError(f"security type mismatch for {filename}")
    xml_security_term = " ".join(
        value
        for value in (
            fields.get("SecurityTermWeekYear", ""),
            fields.get("SecurityTermDayMonth", ""),
        )
        if value and not value.startswith("0-")
    )
    if normalize_contract_text(xml_security_term) != normalize_contract_text(
        row.get("security_term")
    ):
        raise SourceContractError(
            f"security term mismatch for {filename}: {xml_security_term!r}"
        )
    if str(fields.get("InflationIndexSecurity") or "").strip().upper() != "N":
        raise SourceContractError(f"inflation-indexed result rejected: {filename}")
    if str(fields.get("FloatingRate") or "").strip().upper() != "N":
        raise SourceContractError(f"floating-rate result rejected: {filename}")
    xml_reopening = str(fields.get("ReOpeningIndicator") or "").strip().upper() == "Y"
    api_reopening = str(row.get("reopening") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }
    if xml_reopening != api_reopening:
        raise SourceContractError(f"reopening mismatch for {filename}")
    original_term_match = ORIGINAL_TERM_RE.fullmatch(
        str(row.get("original_security_term") or "").strip()
    )
    if not original_term_match:
        raise SourceContractError(f"unverifiable original tenor for {filename}")
    original_issue_value = fields.get("OriginalIssueDate") or fields.get("IssueDate")
    if xml_reopening and not fields.get("OriginalIssueDate"):
        raise SourceContractError(
            f"reopening result lacks OriginalIssueDate: {filename}"
        )
    original_issue = parse_contract_date(
        original_issue_value, field="OriginalIssueDate/IssueDate", filename=filename
    )
    maturity = parse_contract_date(
        fields.get("MaturityDate"), field="MaturityDate", filename=filename
    )
    anniversary = expected_anniversary(
        original_issue, int(original_term_match.group("years"))
    )
    if abs((maturity - anniversary).days) > 31:
        raise SourceContractError(
            f"original tenor is not supported by XML dates for {filename}: "
            f"{original_issue} -> {maturity}"
        )
    if row.get("issue_date") and fields.get("IssueDate") != str(row["issue_date"])[:10]:
        raise SourceContractError(f"issue date mismatch for {filename}")
    release_time = parse_release_time(fields.get("ReleaseTime"), filename=filename)
    try:
        api_ratio = float(row["bid_to_cover_ratio"])
        xml_ratio = float(fields["BidToCoverRatio"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceContractError(f"missing bid-to-cover for {filename}") from exc
    if abs(api_ratio - xml_ratio) > 1e-9:
        raise SourceContractError(f"bid-to-cover mismatch for {filename}")
    return {
        "auction_date": auction_date,
        "first_public_result_date": filename_date,
        "result_publication_date": filename_date,
        "result_release_time_et": release_time,
        "cusip": str(row["cusip"]),
        "security_type": str(row["security_type"]),
        "original_security_term": str(row["original_security_term"]),
        "security_term": str(row.get("security_term") or ""),
        "reopening": str(row.get("reopening") or ""),
        "tips": "No",
        "floating_rate": "No",
        "bid_to_cover_ratio": api_ratio,
        "record_date": str(row.get("record_date") or "")[:10],
        "issue_date": str(row.get("issue_date") or "")[:10],
        "original_issue_date": original_issue.isoformat(),
        "maturity_date": maturity.isoformat(),
        "result_filename": filename,
        "result_url": STATIC_RESULT_BASE + filename,
        "result_sha256": sha256_bytes(payload),
        "result_bytes": len(payload),
        "result_format": "official_static_xml",
        "availability_rule": (
            "result_filename_and_AuctionDate_equal_auction_date;ReleaseTime_before_16:00_ET;"
            "trade_strictly_next_session"
        ),
    }


def pdf_text(payload: bytes, *, filename: str) -> str:
    if not payload.startswith(b"%PDF"):
        raise SourceContractError(f"official PDF fallback is not a PDF: {filename}")
    try:
        import fitz  # type: ignore

        document = fitz.open(stream=payload, filetype="pdf")
        try:
            text = "\n".join(page.get_text("text") for page in document)
        finally:
            document.close()
    except Exception as exc:
        raise SourceContractError(f"could not parse official PDF fallback: {filename}") from exc
    if len(text.strip()) < 500:
        raise SourceContractError(f"official PDF fallback text too thin: {filename}")
    return text


def date_appears_in_pdf(day: date, text: str) -> bool:
    variants = {
        f"{day.strftime('%B')} {day.day}, {day.year}".lower(),
        f"{day.strftime('%B')} {day.day:02d}, {day.year}".lower(),
    }
    normalized = " ".join(text.lower().split())
    return any(value in normalized for value in variants)


def validate_pdf_http_clock(
    row: dict[str, Any], metadata: dict[str, Any], *, filename: str
) -> tuple[str, str]:
    content_type = str(metadata.get("content-type") or "").lower()
    if "application/pdf" not in content_type:
        raise SourceContractError(f"official PDF content type mismatch: {filename}")
    try:
        last_modified = parsedate_to_datetime(str(metadata["last-modified"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceContractError(f"official PDF lacks Last-Modified: {filename}") from exc
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)
    local = last_modified.astimezone(ZoneInfo("America/New_York"))
    auction_date = date.fromisoformat(str(row["auction_date"])[:10])
    if local.date() != auction_date or local.hour >= 16:
        raise SourceContractError(
            f"official PDF publication clock is not PIT-safe: {filename} {local.isoformat()}"
        )
    return local.date().isoformat(), local.strftime("%H:%M")


def validate_pdf_row(
    row: dict[str, Any], payload: bytes, metadata: dict[str, Any]
) -> dict[str, Any]:
    xml_filename = str(row["xml_filenm_comp_results"])
    pdf_filename = str(row.get("pdf_filenm_comp_results") or "")
    if pdf_filename != xml_filename[:-4] + ".pdf":
        raise SourceContractError(f"PDF/XML fallback identity mismatch: {xml_filename}")
    text = pdf_text(payload, filename=pdf_filename)
    publication_date, release_time = validate_pdf_http_clock(
        row, metadata, filename=pdf_filename
    )
    auction_date = date.fromisoformat(str(row["auction_date"])[:10])
    if not date_appears_in_pdf(auction_date, text):
        raise SourceContractError(f"auction date missing from PDF: {pdf_filename}")
    if str(row["cusip"]).upper() not in text.upper():
        raise SourceContractError(f"CUSIP missing from PDF: {pdf_filename}")
    term_and_type = normalize_contract_text(
        f"{row.get('security_term')} {row.get('security_type')}"
    )
    if term_and_type not in normalize_contract_text(text):
        raise SourceContractError(
            f"security term/type missing from PDF: {pdf_filename} {term_and_type!r}"
        )
    ratio_match = re.search(
        r"Bid-to-Cover\s+Ratio\s*:\s*.*?=\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if ratio_match is None or abs(
        float(ratio_match.group(1)) - float(row["bid_to_cover_ratio"])
    ) > 1e-9:
        raise SourceContractError(f"bid-to-cover mismatch in PDF: {pdf_filename}")
    issue_date = parse_contract_date(
        row.get("issue_date"), field="issue_date", filename=pdf_filename
    )
    maturity = parse_contract_date(
        row.get("maturity_date"), field="maturity_date", filename=pdf_filename
    )
    raw_original_issue = str(row.get("original_issue_date") or "").strip().lower()
    original_issue = (
        issue_date
        if raw_original_issue in {"", "null", "none"}
        else parse_contract_date(
            row.get("original_issue_date"),
            field="original_issue_date",
            filename=pdf_filename,
        )
    )
    for required_date in {issue_date, maturity, original_issue}:
        if not date_appears_in_pdf(required_date, text):
            raise SourceContractError(
                f"required security date missing from PDF: {pdf_filename} {required_date}"
            )
    original_term_match = ORIGINAL_TERM_RE.fullmatch(
        str(row.get("original_security_term") or "").strip()
    )
    if not original_term_match:
        raise SourceContractError(f"unverifiable PDF original tenor: {pdf_filename}")
    anniversary = expected_anniversary(
        original_issue, int(original_term_match.group("years"))
    )
    if abs((maturity - anniversary).days) > 31:
        raise SourceContractError(
            f"PDF original tenor dates disagree: {pdf_filename}"
        )
    api_reopening = str(row.get("reopening") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }
    if api_reopening != (original_issue != issue_date):
        raise SourceContractError(f"PDF reopening identity mismatch: {pdf_filename}")
    return {
        "auction_date": auction_date.isoformat(),
        "first_public_result_date": publication_date,
        "result_publication_date": publication_date,
        "result_release_time_et": release_time,
        "cusip": str(row["cusip"]),
        "security_type": str(row["security_type"]),
        "original_security_term": str(row["original_security_term"]),
        "security_term": str(row.get("security_term") or ""),
        "reopening": str(row.get("reopening") or ""),
        "tips": "No",
        "floating_rate": "No",
        "bid_to_cover_ratio": float(row["bid_to_cover_ratio"]),
        "record_date": str(row.get("record_date") or "")[:10],
        "issue_date": issue_date.isoformat(),
        "original_issue_date": original_issue.isoformat(),
        "maturity_date": maturity.isoformat(),
        "result_filename": pdf_filename,
        "result_url": STATIC_RESULT_BASE + pdf_filename,
        "result_sha256": sha256_bytes(payload),
        "result_bytes": len(payload),
        "result_format": "official_static_pdf_fault_recovery",
        "failed_xml_filename": xml_filename,
        "http_last_modified": str(metadata.get("last-modified") or ""),
        "http_etag": str(metadata.get("etag") or ""),
        "availability_rule": (
            "official_PDF_Last-Modified_on_auction_date_before_16:00_ET;"
            "trade_strictly_next_session"
        ),
    }


def build_deterministic_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for filename in sorted(files):
            info = zipfile.ZipInfo(filename, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[filename])
    return buffer.getvalue()


def parse_frozen_source() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frozen_paths = (
        API_ROWS_PATH,
        XML_ZIP_PATH,
        PDF_ZIP_PATH,
        PDF_HTTP_META_PATH,
        RESULTS_PAGE_PATH,
        CANONICAL_PATH,
        SOURCE_MANIFEST_PATH,
    )
    for path in frozen_paths:
        if not path.exists():
            raise SourceContractError(f"frozen source missing: {repo_rel(path)}")
    manifest = read_json(SOURCE_MANIFEST_PATH)
    expected_hashes = manifest.get("file_sha256") or {}
    for path in frozen_paths[:-1]:
        if file_sha(path) != expected_hashes.get(repo_rel(path)):
            raise SourceContractError(f"frozen source hash mismatch: {repo_rel(path)}")
    page_bytes = RESULTS_PAGE_PATH.read_bytes()
    if not page_supports_publication_clock(page_bytes):
        raise SourceContractError("TreasuryDirect publication-clock statement missing")
    api_rows = read_json(API_ROWS_PATH).get("data") or []
    expected_records = read_json(CANONICAL_PATH).get("records") or []
    pdf_metadata = (read_json(PDF_HTTP_META_PATH).get("files") or {})
    source_formats = manifest.get("source_format_by_xml") or {}
    rebuilt: list[dict[str, Any]] = []
    with zipfile.ZipFile(XML_ZIP_PATH, "r") as xml_archive, zipfile.ZipFile(
        PDF_ZIP_PATH, "r"
    ) as pdf_archive:
        expected_xml = {
            str(contract["member"])
            for contract in source_formats.values()
            if contract.get("format") == "xml"
        }
        expected_pdf = {
            str(contract["member"])
            for contract in source_formats.values()
            if contract.get("format") == "pdf_fault_recovery"
        }
        if set(xml_archive.namelist()) != expected_xml:
            raise SourceContractError("frozen XML member set mismatch")
        if set(pdf_archive.namelist()) != expected_pdf:
            raise SourceContractError("frozen PDF fallback member set mismatch")
        for row in api_rows:
            xml_filename = str(row["xml_filenm_comp_results"])
            contract = source_formats.get(xml_filename) or {}
            if contract.get("format") == "xml":
                rebuilt.append(
                    validate_xml_row(row, xml_archive.read(str(contract["member"])))
                )
            elif contract.get("format") == "pdf_fault_recovery":
                member = str(contract["member"])
                rebuilt.append(
                    validate_pdf_row(
                        row,
                        pdf_archive.read(member),
                        dict(pdf_metadata.get(member) or {}),
                    )
                )
            else:
                raise SourceContractError(
                    f"missing frozen source format contract: {xml_filename}"
                )
    rebuilt.sort(key=lambda row: (row["auction_date"], row["original_security_term"], row["cusip"]))
    if canonical_bytes(rebuilt) != canonical_bytes(expected_records):
        raise SourceContractError(
            "canonical auction records do not replay from frozen official files"
        )
    return rebuilt, manifest


def materialize_source(*, online: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not online:
        return parse_frozen_source()
    api_url = auction_api_url()
    api_payload_bytes = fetch_bytes(api_url, max_bytes=MAX_API_BYTES)
    try:
        api_payload = json.loads(api_payload_bytes)
    except json.JSONDecodeError as exc:
        raise SourceContractError("Fiscal Data API returned invalid JSON") from exc
    rows = filter_api_rows(api_payload)
    api_rows_payload = {
        "schema": "treasury_auction_api_rows_v1",
        "source_url": api_url,
        "data": rows,
    }
    atomic_write_json(API_ROWS_PATH, api_rows_payload)
    files: dict[str, bytes] = {}
    pdf_files: dict[str, bytes] = {}
    pdf_metadata = (
        read_json(PDF_HTTP_META_PATH).get("files")
        if PDF_HTTP_META_PATH.exists()
        else {}
    ) or {}
    source_formats: dict[str, dict[str, str]] = {}
    missing_rows: list[dict[str, Any]] = []
    confirmed_fault_rows: dict[str, str] = {}
    XML_PARTS_DIR.mkdir(parents=True, exist_ok=True)
    PDF_PARTS_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        filename = str(row["xml_filenm_comp_results"])
        part_path = XML_PARTS_DIR / filename
        if part_path.exists():
            payload = part_path.read_bytes()
            try:
                validate_xml_row(row, payload)
            except SourceContractError:
                pass
            else:
                files[filename] = payload
                source_formats[filename] = {"format": "xml", "member": filename}
                continue
        pdf_filename = str(row.get("pdf_filenm_comp_results") or "")
        pdf_path = PDF_PARTS_DIR / pdf_filename
        if pdf_filename and pdf_path.exists() and pdf_filename in pdf_metadata:
            payload = pdf_path.read_bytes()
            try:
                validate_pdf_row(row, payload, dict(pdf_metadata[pdf_filename]))
            except SourceContractError:
                pass
            else:
                pdf_files[pdf_filename] = payload
                source_formats[filename] = {
                    "format": "pdf_fault_recovery",
                    "member": pdf_filename,
                }
                continue
        if filename in CONFIRMED_PERSISTENT_XML_503:
            confirmed_fault_rows[filename] = (
                "five-attempt runner failure plus browser-UA curl HTTP 503 preflight"
            )
            continue
        missing_rows.append(row)
    rows_by_xml = {str(row["xml_filenm_comp_results"]): row for row in rows}
    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {
            pool.submit(fetch_bytes, STATIC_RESULT_BASE + str(row["xml_filenm_comp_results"]), max_bytes=MAX_XML_BYTES): str(row["xml_filenm_comp_results"])
            for row in missing_rows
        }
        download_errors: dict[str, str] = dict(confirmed_fault_rows)
        for future in as_completed(futures):
            filename = futures[future]
            try:
                payload = future.result()
            except Exception as exc:  # pragma: no cover - network fault recovery
                download_errors[filename] = str(exc)
                continue
            validate_xml_row(rows_by_xml[filename], payload)
            atomic_write_bytes(XML_PARTS_DIR / filename, payload)
            files[filename] = payload
            source_formats[filename] = {"format": "xml", "member": filename}
    fallback_errors: list[str] = []
    for xml_filename, xml_error in sorted(download_errors.items()):
        row = rows_by_xml[xml_filename]
        pdf_filename = str(row.get("pdf_filenm_comp_results") or "")
        if pdf_filename != xml_filename[:-4] + ".pdf":
            fallback_errors.append(
                f"{xml_filename}: no identity-matched official PDF fallback ({xml_error})"
            )
            continue
        try:
            payload, headers = fetch_bytes_with_headers(
                STATIC_RESULT_BASE + pdf_filename, max_bytes=MAX_PDF_BYTES
            )
            validate_pdf_row(row, payload, headers)
        except Exception as exc:  # pragma: no cover - network fault recovery
            fallback_errors.append(f"{xml_filename}: {exc}")
            continue
        atomic_write_bytes(PDF_PARTS_DIR / pdf_filename, payload)
        pdf_files[pdf_filename] = payload
        pdf_metadata[pdf_filename] = headers
        atomic_write_json(
            PDF_HTTP_META_PATH,
            {
                "schema": "treasury_auction_pdf_http_metadata_v1",
                "files": pdf_metadata,
            },
        )
        source_formats[xml_filename] = {
            "format": "pdf_fault_recovery",
            "member": pdf_filename,
        }
    if fallback_errors:
        raise SourceContractError(
            f"official result source recovery failed: {fallback_errors}"
        )
    if len(files) + len(pdf_files) != len(rows):
        raise SourceContractError("not all Treasury result files were archived")
    records: list[dict[str, Any]] = []
    for row in rows:
        xml_filename = str(row["xml_filenm_comp_results"])
        contract = source_formats[xml_filename]
        if contract["format"] == "xml":
            records.append(validate_xml_row(row, files[contract["member"]]))
        else:
            member = contract["member"]
            records.append(
                validate_pdf_row(row, pdf_files[member], dict(pdf_metadata[member]))
            )
    records.sort(key=lambda row: (row["auction_date"], row["original_security_term"], row["cusip"]))
    results_page = fetch_bytes(RESULTS_PAGE_URL, max_bytes=MAX_PAGE_BYTES)
    if not page_supports_publication_clock(results_page):
        raise SourceContractError("TreasuryDirect publication-clock statement missing")
    canonical_payload = {"schema": "treasury_auction_canonical_records_v1", "records": records}
    atomic_write_bytes(XML_ZIP_PATH, build_deterministic_zip(files))
    atomic_write_bytes(PDF_ZIP_PATH, build_deterministic_zip(pdf_files))
    atomic_write_json(
        PDF_HTTP_META_PATH,
        {"schema": "treasury_auction_pdf_http_metadata_v1", "files": pdf_metadata},
    )
    atomic_write_bytes(RESULTS_PAGE_PATH, results_page)
    atomic_write_json(CANONICAL_PATH, canonical_payload)
    source_counts = Counter(row["original_security_term"] for row in records)
    manifest = {
        "schema": "treasury_auction_source_manifest_v1",
        "generated_at": utc_now(),
        "api_url": api_url,
        "static_result_base": STATIC_RESULT_BASE,
        "results_page_url": RESULTS_PAGE_URL,
        "availability_contract": (
            "TreasuryDirect says the results page updates as soon as auction results are "
            "available; every frozen result filename embeds and matches auction_date, and "
            "the policy enters only at the next market session open. Four persistently-503 "
            "XML endpoints use the identity-matched official static PDF only after its HTTP "
            "Last-Modified proves auction-date publication before 16:00 ET. record_date is "
            "retained for audit but is not used as the signal clock."
        ),
        "record_count": len(records),
        "date_min": records[0]["auction_date"],
        "date_max": records[-1]["auction_date"],
        "original_term_counts": dict(sorted(source_counts.items())),
        "release_time_et_min": min(row["result_release_time_et"] for row in records),
        "release_time_et_max": max(row["result_release_time_et"] for row in records),
        "xml_count": len(files),
        "pdf_fallback_count": len(pdf_files),
        "pdf_fallback_xml_failures": sorted(download_errors),
        "source_format_by_xml": dict(sorted(source_formats.items())),
        "checkpoint_caches": [repo_rel(XML_PARTS_DIR), repo_rel(PDF_PARTS_DIR)],
        "xml_member_sha256": {name: sha256_bytes(payload) for name, payload in sorted(files.items())},
        "pdf_member_sha256": {
            name: sha256_bytes(payload) for name, payload in sorted(pdf_files.items())
        },
        "canonical_records_sha256": sha256_bytes(canonical_bytes(records)),
        "file_sha256": {
            repo_rel(API_ROWS_PATH): file_sha(API_ROWS_PATH),
            repo_rel(XML_ZIP_PATH): file_sha(XML_ZIP_PATH),
            repo_rel(PDF_ZIP_PATH): file_sha(PDF_ZIP_PATH),
            repo_rel(PDF_HTTP_META_PATH): file_sha(PDF_HTTP_META_PATH),
            repo_rel(RESULTS_PAGE_PATH): file_sha(RESULTS_PAGE_PATH),
            repo_rel(CANONICAL_PATH): file_sha(CANONICAL_PATH),
        },
    }
    atomic_write_json(SOURCE_MANIFEST_PATH, manifest)
    return parse_frozen_source()


def yahoo_chart_url(ticker: str, end_date: date) -> str:
    chart_start = date.fromisoformat(SOURCE_START) - timedelta(days=30)
    start_epoch = int(
        datetime.combine(chart_start, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    )
    end_epoch = int(datetime.combine(end_date + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    query = urllib.parse.urlencode(
        {
            "period1": start_epoch,
            "period2": end_epoch,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{query}"


def parse_adjusted_chart(payload: bytes, *, expected_ticker: str) -> list[dict[str, Any]]:
    try:
        root = json.loads(payload)
        result = root["chart"]["result"][0]
        symbol = str(result["meta"]["symbol"]).upper()
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        adjusted = result["indicators"]["adjclose"][0]["adjclose"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise SourceContractError(
            f"invalid {expected_ticker} Yahoo chart response"
        ) from exc
    if symbol != expected_ticker.upper():
        raise SourceContractError(
            f"Yahoo chart symbol mismatch: expected {expected_ticker}, got {symbol}"
        )
    rows: list[dict[str, Any]] = []
    for index, raw_timestamp in enumerate(timestamps):
        values = {key: quote.get(key, [None] * len(timestamps))[index] for key in ("open", "high", "low", "close", "volume")}
        adj_close = adjusted[index]
        if any(values[key] is None for key in ("open", "high", "low", "close", "volume")) or adj_close is None:
            continue
        raw_close = float(values["close"])
        if raw_close <= 0:
            continue
        factor = float(adj_close) / raw_close
        day = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc).date().isoformat()
        rows.append(
            {
                "date": day,
                "open": round(float(values["open"]) * factor, 8),
                "high": round(float(values["high"]) * factor, 8),
                "low": round(float(values["low"]) * factor, 8),
                "close": round(float(adj_close), 8),
                "volume": float(values["volume"]),
                "adjustment_factor": round(factor, 12),
                "adjusted": True,
                "price_basis": "split_and_distribution_adjusted",
            }
        )
    rows.sort(key=lambda row: row["date"])
    if len(rows) < 380 or len({row["date"] for row in rows}) != len(rows):
        raise SourceContractError(
            f"{expected_ticker} chart coverage invalid: {len(rows)} rows"
        )
    return rows


def parse_tbt_chart(payload: bytes) -> list[dict[str, Any]]:
    return parse_adjusted_chart(payload, expected_ticker=TICKER)


def snapshot_rows(label: str, ticker: str) -> list[dict[str, Any]]:
    payload = read_json(SNAPSHOT_PATHS[label])
    rows = (payload.get("ohlcv") or {}).get(ticker) or []
    if not rows:
        raise SourceContractError(f"snapshot missing {ticker}: {label}")
    return [
        {
            "date": str(row.get("Date") or row.get("date"))[:10],
            "open": float(row.get("Open") if "Open" in row else row.get("open")),
            "high": float(row.get("High") if "High" in row else row.get("high")),
            "low": float(row.get("Low") if "Low" in row else row.get("low")),
            "close": float(row.get("Close") if "Close" in row else row.get("close")),
            "volume": float(row.get("Volume") if "Volume" in row else row.get("volume") or 0.0),
            "adjusted": True,
            "price_basis": "yfinance_auto_adjusted_snapshot",
        }
        for row in rows
    ]


def materialize_price_panel(*, online: bool) -> dict[str, Any]:
    if online:
        urls = {ticker: yahoo_chart_url(ticker, date.today()) for ticker in MARKET_RAW_PATHS}
        raw_payloads: dict[str, bytes] = {}
        with ThreadPoolExecutor(max_workers=len(urls)) as pool:
            futures = {
                pool.submit(fetch_bytes, url, max_bytes=MAX_TBT_BYTES): ticker
                for ticker, url in urls.items()
            }
            for future in as_completed(futures):
                raw_payloads[futures[future]] = future.result()
        daily_prices = {
            ticker: parse_adjusted_chart(raw_payloads[ticker], expected_ticker=ticker)
            for ticker in MARKET_RAW_PATHS
        }
        for ticker, path in MARKET_RAW_PATHS.items():
            atomic_write_bytes(path, raw_payloads[ticker])
        panel = {
            "schema": "treasury_auction_tbt_price_panel_v1",
            "generated_at": utc_now(),
            "market_source_urls": urls,
            "market_raw_sha256": {
                ticker: sha256_bytes(raw_payloads[ticker]) for ticker in MARKET_RAW_PATHS
            },
            "tbt_source_url": urls[TICKER],
            "tbt_raw_sha256": sha256_bytes(raw_payloads[TICKER]),
            "tbt_rows_sha256": sha256_bytes(canonical_bytes(daily_prices[TICKER])),
            "tbt": daily_prices[TICKER],
            "daily_prices": daily_prices,
            "benchmarks": {
                label: {ticker: snapshot_rows(label, ticker) for ticker in ("SPY", "QQQ", "TLT")}
                for label in WINDOWS
            },
            "snapshot_sha256": {label: file_sha(path) for label, path in SNAPSHOT_PATHS.items()},
        }
        atomic_write_json(PRICE_PANEL_PATH, panel)
    if not all(path.exists() for path in MARKET_RAW_PATHS.values()) or not PRICE_PANEL_PATH.exists():
        raise SourceContractError("frozen TBT price panel is missing")
    panel = read_json(PRICE_PANEL_PATH)
    for ticker, path in MARKET_RAW_PATHS.items():
        raw_bytes = path.read_bytes()
        expected_hash = (panel.get("market_raw_sha256") or {}).get(ticker)
        if sha256_bytes(raw_bytes) != expected_hash:
            raise SourceContractError(f"{ticker} raw response hash mismatch")
        reparsed = parse_adjusted_chart(raw_bytes, expected_ticker=ticker)
        if canonical_bytes(reparsed) != canonical_bytes(
            (panel.get("daily_prices") or {}).get(ticker) or []
        ):
            raise SourceContractError(
                f"{ticker} chart does not reproduce frozen rows"
            )
    if canonical_bytes(panel.get("tbt") or []) != canonical_bytes(
        (panel.get("daily_prices") or {}).get(TICKER) or []
    ):
        raise SourceContractError("TBT price aliases disagree")
    for label, path in SNAPSHOT_PATHS.items():
        if file_sha(path) != (panel.get("snapshot_sha256") or {}).get(label):
            raise SourceContractError(f"fixed OHLCV snapshot drift: {label}")
    return panel


def load_prediction() -> dict[str, Any]:
    if TICKET_PATH.exists():
        prediction = read_json(TICKET_PATH).get("prediction")
        if isinstance(prediction, dict):
            return prediction
    return dict(PREDICTION_FALLBACK)


def merged_fixed_benchmarks(price_panel: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    merged = {ticker: [] for ticker in ("SPY", "QQQ")}
    for label, (start, end) in WINDOWS.items():
        for ticker in merged:
            merged[ticker].extend(
                row
                for row in price_panel["benchmarks"][label][ticker]
                if start <= str(row["date"]) <= end
            )
    for ticker, rows in merged.items():
        dates = [str(row["date"]) for row in rows]
        if len(dates) != len(set(dates)):
            raise SourceContractError(f"duplicate fixed benchmark dates: {ticker}")
    return merged


def validate_market_alignment(price_panel: dict[str, Any]) -> dict[str, Any]:
    tbt_dates = {str(row["date"]) for row in price_panel.get("tbt") or []}
    audit: dict[str, Any] = {}
    for label, (start, end) in WINDOWS.items():
        spy_dates = {
            str(row["date"])
            for row in price_panel["benchmarks"][label]["SPY"]
            if start <= str(row["date"]) <= end
        }
        qqq_dates = {
            str(row["date"])
            for row in price_panel["benchmarks"][label]["QQQ"]
            if start <= str(row["date"]) <= end
        }
        missing_tbt = sorted(spy_dates - tbt_dates)
        if not spy_dates or spy_dates != qqq_dates or missing_tbt:
            raise SourceContractError(
                f"market calendar alignment failed for {label}: "
                f"spy={len(spy_dates)} qqq={len(qqq_dates)} missing_tbt={missing_tbt[:5]}"
            )
        audit[label] = {
            "session_count": len(spy_dates),
            "spy_qqq_exact_calendar_match": True,
            "tbt_covers_every_session": True,
        }
    return audit


def partition_global_replay(
    replay: dict[str, Any], *, start: str, end: str
) -> dict[str, Any]:
    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for trade in replay.get("trades") or []:
        entry_date = str(trade.get("entry_date") or "")
        if not (start <= entry_date <= end):
            continue
        if str(trade.get("exit_date") or "") <= end:
            trades.append(dict(trade))
        else:
            skipped.append(
                {
                    **dict(trade),
                    "reason": "standard_window_boundary_censored",
                    "realized_outcome_excluded_from_window_metrics": True,
                }
            )
    for row in replay.get("skipped") or []:
        assignment_date = str(row.get("entry_date") or row.get("signal_date") or "")
        if start <= assignment_date <= end:
            skipped.append(dict(row))
    generated = len(trades) + len(skipped)
    return {
        "rule_version": replay.get("rule_version"),
        "ticker": replay.get("ticker"),
        "trades": trades,
        "signals_generated": generated,
        "signals_survived": len(trades),
        "survival_rate": round(len(trades) / generated, 6) if generated else 0.0,
        "skipped": skipped,
        "total_pnl": round(sum(float(row["pnl"]) for row in trades), 2),
        "cash_replacement_usd": round(
            sum(float(row["cash_replacement_usd"]) for row in trades), 2
        ),
        "spy_replacement_usd": round(
            sum(float(row["spy_replacement_usd"]) for row in trades), 2
        ),
        "qqq_replacement_usd": round(
            sum(float(row["qqq_replacement_usd"]) for row in trades), 2
        ),
        "trade_enabled": False,
        "orders": [],
        "partition_rule": (
            "continuous_global_single_slot;assign_by_entry_date;exclude_cross-window "
            "outcomes from per-window metrics while retaining their slot occupancy"
        ),
    }


def mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return round(result, digits) if math.isfinite(result) else None


def format_money(value: Any) -> str:
    number = round_or_none(value, 2)
    return "n/a" if number is None else f"${number:,.2f}"


def return_series_sha(rows: list[dict[str, Any]]) -> str:
    normalized = [
        {"date": str(row["date"]), "return": float(row["return"])}
        for row in rows
    ]
    return sha256_bytes(
        canonical_bytes({"schema": "dated_periodic_return_series_v1", "rows": normalized})
    )


def window_trade_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(trade["net_return"]) for trade in trades]
    cash = [float(trade["cash_replacement_usd"]) for trade in trades]
    spy = [float(trade["spy_replacement_usd"]) for trade in trades]
    qqq = [float(trade["qqq_replacement_usd"]) for trade in trades]
    return {
        "trade_count": len(trades),
        "mean_net_return": round_or_none(mean_or_none(returns)),
        "median_net_return": round_or_none(statistics.median(returns) if returns else None),
        "win_rate": round_or_none(sum(value > 0 for value in returns) / len(returns) if returns else None),
        "total_pnl": round(sum(cash), 2),
        "mean_cash_replacement_usd": round_or_none(mean_or_none(cash), 2),
        "mean_spy_replacement_usd": round_or_none(mean_or_none(spy), 2),
        "mean_qqq_replacement_usd": round_or_none(mean_or_none(qqq), 2),
        "entry_date_min": min((str(trade["entry_date"]) for trade in trades), default=None),
        "exit_date_max": max((str(trade["exit_date"]) for trade in trades), default=None),
    }


def concentration_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    positive = [trade for trade in trades if float(trade["pnl"]) > 0]
    total_positive = sum(float(trade["pnl"]) for trade in positive)
    top5_share = None
    if total_positive > 0:
        top5_share = sum(
            sorted((float(trade["pnl"]) for trade in positive), reverse=True)[:5]
        ) / total_positive
    by_tenor: Counter[str] = Counter()
    for trade in positive:
        tenors = sorted(set(str(value) for value in (trade.get("tenors") or [])))
        if not tenors:
            raise SourceContractError("trade missing predeclared tenor attribution")
        allocation = float(trade["pnl"]) / len(tenors)
        for tenor in tenors:
            by_tenor[tenor] += allocation
    top_tenor = by_tenor.most_common(1)[0] if by_tenor else None
    return {
        "attribution_rule": "equal_split_across_same_day_trigger_tenors",
        "positive_pnl_total": round(total_positive, 2),
        "top5_trade_positive_pnl_share": round_or_none(top5_share),
        "top_tenor": top_tenor[0] if top_tenor else None,
        "top_tenor_positive_pnl_share": round_or_none(
            top_tenor[1] / total_positive if top_tenor and total_positive > 0 else None
        ),
        "positive_pnl_by_tenor": {
            tenor: round(value, 2) for tenor, value in sorted(by_tenor.items())
        },
    }


def build_dsr(
    windows: dict[str, dict[str, Any]],
    source_manifest: dict[str, Any],
    price_panel: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    ordered = list(WINDOWS)
    series = [
        {"date": str(row["date"]), "return": float(row["return"])}
        for label in ordered
        for row in windows[label]["after"]["return_series"]
    ]
    dates = [row["date"] for row in series]
    panel = {
        "selected_config_id": "treasury_auction_weak_demand_tbt_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": False,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            {
                "config_id": "treasury_auction_weak_demand_tbt_on",
                "config": {
                    "rule_version": RULE_VERSION,
                    "lookback_auctions": LOOKBACK_AUCTIONS,
                    "hold_sessions": HOLD_SESSIONS,
                    "notional_usd": NOTIONAL_USD,
                    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                    "ticker": TICKER,
                    "original_terms": list(ALLOWED_ORIGINAL_TERMS),
                },
                "attempted": True,
                "selection_scope": "treasury_auction_bid_to_cover_tbt_event_response",
                "window": {
                    "segments": [
                        {"label": label, "start": WINDOWS[label][0], "end": WINDOWS[label][1]}
                        for label in ordered
                    ]
                },
                "frequency": "daily",
                "return_basis": "core_plus_treasury_auction_tbt_daily_mtm_post_cost",
                "risk_free_assumption": "zero",
                "protocol": {
                    "id": "post_mtm_gate1_plus_treasury_auction_tbt_v1",
                    "rule_version": RULE_VERSION,
                },
                "data": {
                    "baseline_summary_sha256": file_sha(BASELINE_SUMMARY_PATH),
                    "source_manifest_sha256": file_sha(SOURCE_MANIFEST_PATH),
                    "source_generated_at": source_manifest["generated_at"],
                    "tbt_raw_sha256": price_panel["tbt_raw_sha256"],
                },
                "cost": {"round_trip_cost_pct": ROUND_TRIP_COST_PCT},
                "return_series": series,
                "return_series_sha256": return_series_sha(series),
                "return_series_source": f"{repo_rel(RESULT_PATH)}#windows.*.after.return_series",
            }
        ],
    }
    report = build_dsr_report(panel)
    report["gate4_independence"] = True
    report["expected_attempt_count_policy"] = (
        "Seven economically adjacent macro/rates response attempts were declared, "
        "but no complete aligned seven-row return panel exists. DSR therefore fails "
        "closed rather than inventing loser returns or treating one selected test as seven."
    )
    atomic_write_json(DSR_PANEL_PATH, panel)
    atomic_write_json(DSR_REPORT_PATH, report)
    return panel, report


def build_evaluation(*, online: bool) -> dict[str, Any]:
    prediction = load_prediction()
    source_records, source_manifest = materialize_source(online=online)
    price_panel = materialize_price_panel(online=online)
    events = build_weak_auction_events(source_records)
    if not events:
        raise SourceContractError(
            "canonical Treasury rows produced zero weak-auction events"
        )
    market_alignment = validate_market_alignment(price_panel)
    global_benchmarks = merged_fixed_benchmarks(price_panel)
    global_replay = replay_weak_auction_tbt(
        events,
        list(price_panel["tbt"]),
        global_benchmarks,
        next(iter(WINDOWS.values()))[0],
        next(reversed(WINDOWS.values()))[1],
    )
    baseline_summary = read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = gate_utils._baseline_window_map(baseline_summary)

    windows: dict[str, dict[str, Any]] = {}
    all_trades: list[dict[str, Any]] = []
    for label, (start, end) in WINDOWS.items():
        replay = partition_global_replay(global_replay, start=start, end=end)
        trades = list(replay.get("trades") or [])
        all_trades.extend(trades)
        before, after, _curve = gate_utils._combine_window(
            baseline_windows[label], trades, {TICKER: list(price_panel["tbt"])}
        )
        after.update(
            {
                "signals_generated": before["signals_generated"],
                "signals_survived": before["signals_survived"],
                "survival_rate": before["survival_rate"],
            }
        )
        delta = {
            "expected_value_score": round(
                float(after["expected_value_score"]) - float(before["expected_value_score"]), 4
            ),
            "total_pnl": round(float(after["total_pnl"]) - float(before["total_pnl"]), 2),
            "max_drawdown_pct": round(
                float(after["max_drawdown_pct"]) - float(before["max_drawdown_pct"]), 4
            ),
            "total_trades": int(after["total_trades"]) - int(before["total_trades"]),
        }
        windows[label] = {
            "start": start,
            "end": end,
            "source_snapshot": repo_rel(SNAPSHOT_PATHS[label]),
            "replay": replay,
            "trade_summary": window_trade_summary(trades),
            "before": before,
            "after": after,
            "delta": delta,
        }

    aggregate = gate_utils._aggregate_windows(windows)
    aggregate["worst_max_drawdown_delta"] = round(
        max(row["delta"]["max_drawdown_pct"] for row in windows.values()), 4
    )
    aggregate["positive_pnl_windows"] = sum(
        row["delta"]["total_pnl"] > 0 for row in windows.values()
    )
    aggregate["positive_ev_windows"] = sum(
        row["delta"]["expected_value_score"] > 0 for row in windows.values()
    )
    concentration = concentration_summary(all_trades)
    _dsr_panel, dsr_report = build_dsr(windows, source_manifest, price_panel)
    dsr_gate = dsr_report.get("gate5_dsr_report") or {}
    dsr_probability = dsr_gate.get("dsr_probability")
    source_archive_complete = (
        int(source_manifest.get("xml_count") or 0)
        + int(source_manifest.get("pdf_fallback_count") or 0)
        == int(source_manifest.get("record_count") or 0)
    )
    gate2_dependencies_validated = (
        bool(all_trades)
        and source_archive_complete
        and all(
            trade.get("entry_date")
            and trade.get("target_price")
            and trade.get("exit_date")
            for trade in all_trades
        )
    )

    per_window_counts = {
        label: int(row["trade_summary"]["trade_count"]) for label, row in windows.items()
    }
    checks = {
        "source_archive_complete": source_archive_complete,
        "market_alignment_complete": all(
            row["spy_qqq_exact_calendar_match"] and row["tbt_covers_every_session"]
            for row in market_alignment.values()
        ),
        "gate2_dependencies_validated": gate2_dependencies_validated,
        "fingerprint_source_repaired": "treasury_auction_results" in FINGERPRINT_PATH.read_text(encoding="utf-8"),
        "fingerprint_gate_repaired": "event_driven_inverse_treasury_etf_5d" in FINGERPRINT_PATH.read_text(encoding="utf-8"),
        "total_trade_count": len(all_trades),
        "min_total_trades": MIN_TOTAL_TRADES,
        "per_window_trade_count": per_window_counts,
        "min_window_trades": MIN_WINDOW_TRADES,
        "sample_passed": len(all_trades) >= MIN_TOTAL_TRADES
        and all(count >= MIN_WINDOW_TRADES for count in per_window_counts.values()),
        "all_window_ev_nonnegative": all(
            row["delta"]["expected_value_score"] >= 0 for row in windows.values()
        ),
        "all_window_pnl_nonnegative": all(
            row["delta"]["total_pnl"] >= 0 for row in windows.values()
        ),
        "all_window_cash_replacement_positive": all(
            (row["trade_summary"]["mean_cash_replacement_usd"] or 0) > 0
            for row in windows.values()
        ),
        "all_window_qqq_replacement_positive": all(
            (row["trade_summary"]["mean_qqq_replacement_usd"] or 0) > 0
            for row in windows.values()
        ),
        "aggregate_ev_beats_accepted_comparator": aggregate["expected_value_score_delta_sum"]
        > ACCEPTED_COMPARATOR["expected_value_score_delta_sum"],
        "aggregate_pnl_beats_accepted_comparator": aggregate["total_pnl_delta_sum"]
        > ACCEPTED_COMPARATOR["total_pnl_delta_sum"],
        "drawdown_passed": aggregate["worst_max_drawdown_delta"] <= MAX_DRAWDOWN_WORSE,
        "dsr_probability": dsr_probability,
        "dsr_probability_min": MIN_DSR_PROBABILITY,
        "dsr_passed": dsr_probability is not None
        and float(dsr_probability) >= MIN_DSR_PROBABILITY,
        "top_tenor_positive_pnl_share": concentration["top_tenor_positive_pnl_share"],
        "top_tenor_share_max": MAX_TOP_TENOR_POSITIVE_SHARE,
        "top_tenor_concentration_passed": concentration["top_tenor_positive_pnl_share"] is not None
        and float(concentration["top_tenor_positive_pnl_share"]) <= MAX_TOP_TENOR_POSITIVE_SHARE,
        "top5_trade_positive_pnl_share": concentration["top5_trade_positive_pnl_share"],
        "top5_trade_share_max": MAX_TOP5_TRADE_POSITIVE_SHARE,
        "top5_trade_concentration_passed": concentration["top5_trade_positive_pnl_share"] is not None
        and float(concentration["top5_trade_positive_pnl_share"]) <= MAX_TOP5_TRADE_POSITIVE_SHARE,
    }
    required_boolean_checks = [
        "source_archive_complete",
        "market_alignment_complete",
        "gate2_dependencies_validated",
        "fingerprint_source_repaired",
        "fingerprint_gate_repaired",
        "sample_passed",
        "all_window_ev_nonnegative",
        "all_window_pnl_nonnegative",
        "all_window_cash_replacement_positive",
        "all_window_qqq_replacement_positive",
        "aggregate_ev_beats_accepted_comparator",
        "aggregate_pnl_beats_accepted_comparator",
        "drawdown_passed",
        "dsr_passed",
        "top_tenor_concentration_passed",
        "top5_trade_concentration_passed",
    ]
    failed = [name for name in required_boolean_checks if checks.get(name) is not True]
    accepted = not failed
    overall_cash = sum(float(trade["cash_replacement_usd"]) for trade in all_trades)
    overall_qqq = sum(float(trade["qqq_replacement_usd"]) for trade in all_trades)
    observed_lead = (
        not accepted
        and checks["sample_passed"]
        and aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["positive_ev_windows"] >= 2
        and aggregate["positive_pnl_windows"] >= 2
        and overall_cash > 0
        and overall_qqq > 0
    )
    status = (
        "accepted_paper_pending_forward"
        if accepted
        else "observed_only_positive_lead"
        if observed_lead
        else "rejected"
    )
    decision = (
        "accepted_default_off_treasury_auction_tbt_pending_forward"
        if accepted
        else "observed_only_treasury_auction_tbt_lead_not_promoted"
        if observed_lead
        else "rejected_treasury_auction_tbt_edge_not_robust"
    )

    snapshot = build_treasury_auction_tbt_snapshot(
        as_of_date=date.today().isoformat(),
        events=events,
        price_rows={
            ticker: list(rows)
            for ticker, rows in (price_panel.get("daily_prices") or {}).items()
            if ticker in {TICKER, "SPY", "QQQ"}
        },
        previous_state=None,
    )
    snapshot["experiment_id"] = EXPERIMENT_ID
    snapshot["trade_enabled"] = False
    snapshot["source_manifest_sha256"] = file_sha(SOURCE_MANIFEST_PATH)

    probability = float(prediction.get("success_probability") or 0.0)
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    failure_text = " ".join(failed)
    mode_keywords = {
        "next_open_absorbs_auction_signal": ("window", "replacement", "pnl"),
        "nonoverlap_sample_too_small": ("sample", "trade_count"),
        "tbt_daily_reset_decay_and_cost": ("pnl", "replacement"),
        "window_regression": ("all_window",),
        "accepted_comparator_not_beaten": ("comparator",),
        "static_xml_contract_failure": ("source_archive",),
        "positive_pnl_concentration": ("concentration", "top_tenor", "top5"),
    }
    predicted_hit = [
        mode
        for mode in predicted_modes
        if any(keyword in failure_text for keyword in mode_keywords.get(mode, ()))
    ]

    why = (
        "The fixed auction-demand event sleeve cleared every preregistered historical "
        "and selection-bias gate, but remains default-off pending forward outcomes."
        if accepted
        else "The event sleeve was directionally positive but did not clear the champion, "
        "cross-window, concentration, and complete-panel DSR contract; it remains a "
        "default-off diagnostic lead only."
        if observed_lead
        else "The fixed weak-auction TBT response did not provide robust incremental "
        "value after next-open execution, non-overlap, costs, and cross-window checks."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": "shared_paper_first_new_source",
        "mechanism_family": "treasury_auction_demand_microstructure",
        "trial_family": "treasury_auction_bid_to_cover_tbt_event_response",
        "trial_variant_id": "nominal_coupon_all_7_tenors_trailing12_median_tbt_h5_v1",
        "changed_variable": "treasury_nominal_auction_btc_trailing12_weak_tbt_5session_v1",
        "single_causal_variable": "treasury_nominal_auction_btc_trailing12_weak_tbt_5session_v1",
        "causal_components": [
            "official hash-bound Treasury result XML",
            "trailing-12 same-original-tenor median",
            "strict next-session TBT entry",
            "five-session non-overlapping paper hold",
            "core-plus-sleeve Gate 4",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_official_data_source_and_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "parameters": {
            "rule_version": RULE_VERSION,
            "original_security_terms": list(ALLOWED_ORIGINAL_TERMS),
            "lookback_auctions": LOOKBACK_AUCTIONS,
            "weak_rule": "bid_to_cover_ratio < median(prior_12_same_original_term)",
            "same_day_signal_rule": "one_signal",
            "same_day_tenor_pnl_attribution": "equal_split",
            "hold_sessions": HOLD_SESSIONS,
            "notional_usd": NOTIONAL_USD,
            "max_concurrent_positions": 1,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "ticker": TICKER,
            "trade_enabled": False,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_override_reason": (
                    "Reservation was initially over-matched to forward replacement because "
                    "the true source lacked a dedicated fingerprint. The same experiment "
                    "adds treasury_auction_results and event-driven inverse-Treasury routing."
                ),
                "nearby_prior_experiments": NEARBY_PRIORS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One fixed weak-auction event response with an official PIT archive, actual "
                "TBT bars, non-overlap capital envelope, and shared historical/daily helper."
            ),
            "4_success_failure_standard": read_json(TICKET_PATH).get("acceptance_rule"),
            "5_reproducibility": RUNNER_COMMAND + " --offline",
        },
        "source": source_manifest,
        "price_panel": {
            "path": repo_rel(PRICE_PANEL_PATH),
            "sha256": file_sha(PRICE_PANEL_PATH),
            "tbt_raw_path": repo_rel(TBT_RAW_PATH),
            "tbt_raw_sha256": price_panel["tbt_raw_sha256"],
            "market_raw_sha256": price_panel["market_raw_sha256"],
            "tbt_rows": len(price_panel["tbt"]),
            "tbt_date_min": price_panel["tbt"][0]["date"],
            "tbt_date_max": price_panel["tbt"][-1]["date"],
            "warehouse_tbt_gap": "TBT was absent from canonical warehouse; actual frozen adjusted TBT bars were used, never -2x TLT.",
            "market_alignment": market_alignment,
        },
        "gate1": {
            "baseline_loaded": BASELINE_SUMMARY_PATH.exists(),
            "baseline_path": repo_rel(BASELINE_SUMMARY_PATH),
            "baseline_sha256": file_sha(BASELINE_SUMMARY_PATH),
            "baseline_aggregate": baseline_summary.get("aggregate"),
        },
        "gate2": {
            "dependencies_validated": gate2_dependencies_validated,
            "fields_checked": [
                "auction_date",
                "first_public_result_date",
                "result_filename",
                "result_sha256",
                "cusip",
                "security_type",
                "original_security_term",
                "bid_to_cover_ratio",
                "entry_date",
                "target_price",
                "exit_date",
            ],
            "entry_date_present_count": sum(bool(trade.get("entry_date")) for trade in all_trades),
            "target_price_present_count": sum(trade.get("target_price") is not None for trade in all_trades),
            "target_price_relevance": (
                "A 3.5x-ATR sentinel is emitted for the signal contract; this fixed-horizon "
                "paper policy exits on session five and does not promote a target exit."
            ),
            "actual_tbt_not_synthetic": True,
        },
        "gate3": {
            "filter_added_to_core": False,
            "signals_generated": sum(int(row["replay"].get("signals_generated") or 0) for row in windows.values()),
            "signals_survived": len(all_trades),
            "survival_rate": round(
                len(all_trades)
                / max(1, sum(int(row["replay"].get("signals_generated") or 0) for row in windows.values())),
                4,
            ),
            "note": "Non-overlap is the fixed $16k capital envelope, not a tuned alpha filter.",
            "window_boundary_rule": (
                "One continuous single-slot replay spans all standard windows; trades are "
                "assigned by entry date, and a trade crossing a boundary retains slot "
                "occupancy but is censored from both windows' outcome metrics."
            ),
        },
        "gate4": {
            "checks": checks,
            "failed_reasons": failed,
            "accepted_comparator": ACCEPTED_COMPARATOR,
            "aggregate": aggregate,
            "concentration": concentration,
            "decision": decision,
        },
        "gate5": dsr_gate,
        "deflated_sharpe": dsr_report,
        "windows": windows,
        "aggregate": aggregate,
        "concentration": concentration,
        "daily_snapshot": snapshot,
        "full_stack": {
            "shared_helper": "quant/treasury_auction_weak_demand_tbt_paper_sleeve.py",
            "historical_and_daily_share_helper": True,
            "daily_snapshot_path": repo_rel(PAPER_SNAPSHOT_PATH),
            "daily_wiring_retained": False,
            "forward_collection_automatic": False,
            "trade_enabled": False,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "run_py_changed": False,
            "live_realistic_execution_envelope": {
                "instrument": "TBT (actual daily-reset -2x Treasury ETF)",
                "max_notional_usd": NOTIONAL_USD,
                "max_concurrent_positions": 1,
                "entry": "strict next market-session open after official auction result",
                "exit": "fifth market-session close",
                "cost_pct": ROUND_TRIP_COST_PCT,
                "kill_switch": "source/XML/hash/price dependency failure emits no candidate",
                "order_semantics": "default-off snapshot only; no order submitted",
            },
        },
        "residual_unknowns": [
            (
                "Static Treasury result XML is hash-bound now and its embedded auction date, "
                "release time, security identity, nominal status and original-tenor dates are "
                "cross-validated, but the file itself has no historical content hash proving "
                "that today's bytes exactly equal first-public bytes."
            ),
            (
                "Yahoo adjusted OHLC is frozen and symbol/calendar checked, but a future vendor "
                "corporate-action revision could change a newly downloaded historical panel."
            ),
            (
                "The seven-attempt selection family lacks a complete aligned return panel, so "
                "DSR fails closed rather than quantifying selection bias from invented trials."
            ),
            "No prospectively closed unchanged-policy auction decisions exist yet.",
            (
                "A continuous single-slot replay preserves cross-window occupancy, but any trade "
                "whose outcome crosses a standard-window boundary is censored from window metrics."
            ),
        ],
        "calibration": {
            "predicted_success_probability": probability,
            "actual_success": accepted,
            "brier_score": round((probability - float(accepted)) ** 2, 6),
            "predicted_failure_modes": predicted_modes,
            "failed_reasons": failed,
            "predicted_failure_modes_hit": predicted_hit,
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "realized_failure_mode": ",".join(failed) if failed else "none",
            "forbidden_near_neighbor_retry": (
                "Do not retune the bid-to-cover threshold, lookback, tenor subset, same-day "
                "attribution, TBT/short-TLT proxy, entry timing, hold, cost, overlap, or "
                "notional on these frozen auction rows."
            ),
            "new_evidence_required": (
                "A genuinely new auction microstructure source/gate, or at least 30 "
                "prospectively closed unchanged-policy forward decisions plus a complete "
                "aligned selection panel before promotion."
            ),
        },
        "related_files": [
            RUNNER,
            "quant/treasury_auction_weak_demand_tbt_paper_sleeve.py",
            repo_rel(SOURCE_MANIFEST_PATH),
            repo_rel(PRICE_PANEL_PATH),
            repo_rel(PAPER_SNAPSHOT_PATH),
            repo_rel(FINGERPRINT_PATH),
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }
    return payload


def compact_window(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": row["start"],
        "end": row["end"],
        "source_snapshot": row["source_snapshot"],
        "trade_summary": row["trade_summary"],
        "replay": row["replay"],
        "before": {key: value for key, value in row["before"].items() if key != "return_series"},
        "after": {key: value for key, value in row["after"].items() if key != "return_series"},
        "delta": row["delta"],
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"windows", "deflated_sharpe", "daily_snapshot"}
    } | {
        "windows": {label: compact_window(row) for label, row in payload["windows"].items()},
        "deflated_sharpe": {
            "status": payload["deflated_sharpe"].get("status"),
            "gate5_dsr_report": payload["deflated_sharpe"].get("gate5_dsr_report"),
            "expected_attempt_count_policy": payload["deflated_sharpe"].get("expected_attempt_count_policy"),
        },
        "artifact": repo_rel(RESULT_PATH),
        "log": repo_rel(LOG_PATH),
    }


def upsert_experiment_log(record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
    rows: list[str] = []
    replaced = False
    if EXPERIMENT_LOG_PATH.exists():
        for raw in EXPERIMENT_LOG_PATH.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    atomic_write_text(EXPERIMENT_LOG_PATH, "\n".join(rows) + "\n")


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: Treasury auction weak-demand TBT",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Production orders changed: no",
        "- Policy: prior-12 same-tenor BTC median, strict next open, one $16k TBT position, fifth-session close",
        "",
        "| Window | Trades | Mean TBT net | Mean cash repl. | Mean QQQ repl. | EV delta | PnL delta | Max-DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["windows"][label]
        summary = row["trade_summary"]
        lines.append(
            f"| {label} | {summary['trade_count']} | {summary['mean_net_return']} | "
            f"{format_money(summary['mean_cash_replacement_usd'])} | "
            f"{format_money(summary['mean_qqq_replacement_usd'])} | "
            f"{row['delta']['expected_value_score']:.4f} | ${row['delta']['total_pnl']:,.2f} | "
            f"{row['delta']['max_drawdown_pct']:.4f} |"
        )
    lines.extend(
        [
            "",
            f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']}`",
            f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:,.2f}`",
            f"- DSR: `{payload['gate5'].get('status')}` / probability `{payload['gate5'].get('dsr_probability')}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "treasury_auction_weak_demand_tbt_paper_sleeve.py",
        REPO_ROOT / "quant" / "test_treasury_auction_weak_demand_tbt_paper_sleeve.py",
        API_ROWS_PATH,
        XML_ZIP_PATH,
        PDF_ZIP_PATH,
        PDF_HTTP_META_PATH,
        RESULTS_PAGE_PATH,
        CANONICAL_PATH,
        SOURCE_MANIFEST_PATH,
        *MARKET_RAW_PATHS.values(),
        PRICE_PANEL_PATH,
        RESULT_PATH,
        BEFORE_PATH,
        AFTER_PATH,
        DSR_PANEL_PATH,
        DSR_REPORT_PATH,
        PAPER_SNAPSHOT_PATH,
        ARTIFACT_PATH,
        CARD_PATH,
        LOG_PATH,
        TICKET_PATH,
        FINGERPRINT_PATH,
        FROZEN_FAMILIES_PATH,
        PLAYBOOK_PATH,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "runner": RUNNER,
        "command_online": RUNNER_COMMAND + " --online",
        "command_offline": RUNNER_COMMAND + " --offline",
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": file_sha(path)} for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    before_payload = {
        "schema": "treasury_auction_tbt_before_v1",
        "windows": {label: row["before"] for label, row in payload["windows"].items()},
        "aggregate": {
            "expected_value_score_sum": payload["aggregate"]["before_expected_value_score_sum"],
            "total_pnl_sum": payload["aggregate"]["before_total_pnl_sum"],
        },
    }
    after_payload = {
        "schema": "treasury_auction_tbt_after_v1",
        "windows": {label: row["after"] for label, row in payload["windows"].items()},
        "aggregate": {
            "expected_value_score_sum": payload["aggregate"]["after_expected_value_score_sum"],
            "total_pnl_sum": payload["aggregate"]["after_total_pnl_sum"],
        },
    }
    atomic_write_json(BEFORE_PATH, before_payload)
    atomic_write_json(AFTER_PATH, after_payload)
    atomic_write_json(RESULT_PATH, payload)
    atomic_write_json(PAPER_SNAPSHOT_PATH, payload["daily_snapshot"])
    markdown = build_markdown(payload)
    atomic_write_text(ARTIFACT_PATH, markdown)
    atomic_write_text(CARD_PATH, markdown)
    log_record = build_log(payload)
    atomic_write_json(LOG_PATH, log_record)
    upsert_experiment_log(log_record)

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(RESULT_PATH),
        "log": repo_rel(LOG_PATH),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "gate5": payload["gate5"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_PATH,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": "shared_paper_first_historical_and_daily",
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_SUMMARY_PATH),
            "decision": payload["decision"],
            "artifact": repo_rel(RESULT_PATH),
            "log": repo_rel(LOG_PATH),
            "card_file": repo_rel(CARD_PATH),
            "revision_manifest_file": repo_rel(MANIFEST_PATH),
            "aggregate_expected_value_delta": payload["aggregate"]["expected_value_score_delta_sum"],
            "aggregate_strategy_total_pnl_delta": payload["aggregate"]["total_pnl_delta_sum"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "gate5": payload["gate5"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": read_json(TICKET_PATH).get("allowed_write_scope"),
            "related_files": payload["related_files"],
        },
    )
    atomic_write_json(MANIFEST_PATH, build_manifest(payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--online", action="store_true", help="Fetch and freeze source bytes")
    mode.add_argument("--offline", action="store_true", help="Replay only frozen bytes")
    args = parser.parse_args(argv)
    payload = build_evaluation(online=bool(args.online))
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "trades_by_window": {
                    label: row["trade_summary"]["trade_count"]
                    for label, row in payload["windows"].items()
                },
                "aggregate_ev_delta": payload["aggregate"]["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": payload["aggregate"]["total_pnl_delta_sum"],
                "dsr_probability": payload["gate5"].get("dsr_probability"),
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
