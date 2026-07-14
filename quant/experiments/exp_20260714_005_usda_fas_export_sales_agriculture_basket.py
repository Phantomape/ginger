"""exp-20260714-005: USDA FAS as-published export-sales event basket.

The single decision under test is fixed before any return is inspected: an
official weekly corn/soybean export-demand composite above its trailing p75
enters a ten-leg agriculture value-chain basket for ten sessions.  Historical
replay and the one-shot daily paper snapshot call the same default-off helper.

Source values come only from archived USDA ESRQS PDF bytes.  The current ESR
API is deliberately excluded because USDA documents that historical export
figures can be revised.  Online source refresh stores hashes and normalized
Corn/Soybeans excerpts, never bearer tokens or executable orders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import statistics
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260714-005"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)
from usda_fas_export_sales_paper_sleeve import (  # noqa: E402
    AGRICULTURE_BASKET_V1,
    RULE_VERSION,
    ROUND_TRIP_COST_PCT,
    build_usda_fas_export_sales_agriculture_basket_paper_snapshot,
    empty_usda_fas_export_sales_agriculture_basket_paper_state,
    replay_usda_fas_export_sales_agriculture_basket_paper_trades,
)


class SourceContractError(RuntimeError):
    """Raised when frozen evidence violates the preregistered contract."""


WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)

BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "usda_fas_export_sales"
SOURCE_RECORDS_PATH = SOURCE_DIR / "normalized_records.json"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "usda_fas_export_sales_agriculture_basket_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_SNAPSHOT_PATH = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "usda_fas_export_sales_agriculture_basket"
    / "latest_snapshot.json"
)
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_usda_fas_export_sales_agriculture_basket.md"
)

AGRICULTURE_BASKET = (
    "CORN",
    "SOYB",
    "DBA",
    "ADM",
    "BG",
    "CTVA",
    "DE",
    "MOS",
    "NTR",
    "CF",
)
REFERENCE_TICKERS = ("SPY", "QQQ", "DBA", "CORN", "SOYB")
ALL_OHLCV_TICKERS = tuple(
    dict.fromkeys((*AGRICULTURE_BASKET, *REFERENCE_TICKERS))
)
AUXILIARY_START = "2024-09-01"
AUXILIARY_END = "2026-04-30"
MIN_SETTLED_EVENTS = 12
MIN_SETTLED_EVENTS_PER_WINDOW = 3
MIN_POSITIVE_TICKERS = 9
MAX_DRAWDOWN_WORSE = 0.005
EXPECTED_DSR_ATTEMPTS = 1
PAPER_SNAPSHOT_AS_OF = "2026-04-21"
ACCEPTED_COMPARATORS = (
    {
        "experiment_id": "exp-20260608-013",
        "expected_value_score_delta_sum": 0.1608,
        "total_pnl_delta_sum": 2248.98,
    },
    {
        "experiment_id": "exp-20260611-007",
        "expected_value_score_delta_sum": 0.5286,
        "total_pnl_delta_sum": 10432.91,
    },
)

ESRQS_ROOT = "https://apps.fas.usda.gov/esrqs"
ESRQS_API = f"{ESRQS_ROOT}/api"
ESRQS_TOKEN_URL = f"{ESRQS_ROOT}/token"
ESRQS_PUBLIC_CLIENT_ID = "eAuth_Client"
# This is the public anonymous-client value embedded in USDA's ESRQS SPA,
# not a user credential.  Access tokens returned by the service are ephemeral
# and are never persisted.
ESRQS_PUBLIC_CLIENT_SECRET = (
    "00000000-0000-0000-0000-000000000000"
    "00000000-0000-0000-0000-000000000000"
)
SOURCE_START_YEAR = 2017
SOURCE_END_YEAR = 2026
HTTP_TIMEOUT_SECONDS = 120
HTTP_WORKERS = 4
MAX_PDF_BYTES = 8_000_000
USER_AGENT = (
    "ginger-research/exp-20260714-005 "
    "(read-only academic source archival)"
)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
FOOTER_DATE_RE = re.compile(
    r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\s+\d+\s+"
    r"FOREIGN\s+AGRICULTURAL\s+SERVICE/USDA",
    re.IGNORECASE,
)
BELL_RELEASE_DATE_RE = re.compile(
    r"release\s+after\s+8:30\s*A\.?M\.?\s+on\s+(\d{1,2}-\d{1,2}-20\d{2})",
    re.IGNORECASE,
)
NET_SALES_RE = re.compile(
    r"(?P<prefix>(?:total\s+)?net\s+sales(?:\s+reductions)?"
    r"(?:\s+of|\s+totaling)?\s+)"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?)\s+(?:metric\s+tons\s+\()?MT\)?\s+"
    r"for\s+(?P<marketing_year>20\d{2}/20\d{2})",
    re.IGNORECASE,
)
JOINED_MARKETING_YEAR_RE = re.compile(
    r"^\s*[,;]?\s*and\s+(?P<amount>\d[\d,]*(?:\.\d+)?)\s+"
    r"(?:metric\s+tons\s+\()?MT\)?\s+for\s+"
    r"(?P<marketing_year>20\d{2}/20\d{2})",
    re.IGNORECASE,
)


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _json_bytes(payload)
    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, dir=path.parent, prefix=f".{path.name}."
    ) as handle:
        handle.write(raw)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _fetch_bytes(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    max_bytes: int = MAX_PDF_BYTES,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=request_headers,
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed USDA HTTPS host
        raw = response.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise SourceContractError(f"unexpected response size for {url}: {len(raw)}")
    return raw


def _anonymous_bearer() -> str:
    body = urllib.parse.urlencode(
        {
            "client_id": ESRQS_PUBLIC_CLIENT_ID,
            "client_secret": ESRQS_PUBLIC_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }
    ).encode("ascii")
    raw = _fetch_bytes(
        ESRQS_TOKEN_URL,
        method="POST",
        data=body,
        headers={"Content-Type": "text/plain"},
        max_bytes=200_000,
    )
    payload = json.loads(raw.decode("utf-8"))
    token = str(payload.get("access_token") or "")
    if not token or len(token) < 40:
        raise SourceContractError("USDA ESRQS anonymous access token missing")
    return token


def _archive_rows(token: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_weeks: set[str] = set()
    for year in range(SOURCE_START_YEAR, SOURCE_END_YEAR + 1):
        url = (
            f"{ESRQS_API}/reports/GetArchivedWeeklyReportsList?selectedYear={year}"
        )
        raw = _fetch_bytes(url, headers=headers, max_bytes=2_000_000)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, list):
            raise SourceContractError(f"USDA archive list is not a list for {year}")
        for item in payload:
            report_id = str(item.get("id") or "").lower()
            week_ending = _iso_date(item.get("weekEndingDate"))
            if (
                UUID_RE.fullmatch(report_id) is None
                or week_ending is None
                or not week_ending.startswith(str(year))
                or report_id in seen_ids
                or week_ending in seen_weeks
            ):
                raise SourceContractError(
                    f"invalid or duplicate USDA archive row for {year}: {item!r}"
                )
            seen_ids.add(report_id)
            seen_weeks.add(week_ending)
            rows.append(
                {
                    "year": year,
                    "report_id": report_id,
                    "week_ending": week_ending,
                    "full_file_name": str(item.get("fullFileName") or ""),
                    "file_type": str(item.get("fileType") or ""),
                    "file_extension": str(item.get("fileExtension") or ""),
                }
            )
    return sorted(rows, key=lambda row: row["week_ending"])


def _commodity_section(text: str, name: str, following: tuple[str, ...]) -> str:
    start_match = re.search(rf"\b{re.escape(name)}\s*:", text, re.IGNORECASE)
    if start_match is None:
        raise SourceContractError(f"{name} narrative section missing")
    end = len(text)
    for label in following:
        match = re.search(
            rf"\b{re.escape(label)}\s*:", text[start_match.end() :], re.IGNORECASE
        )
        if match is not None:
            end = min(end, start_match.end() + match.start())
    return " ".join(text[start_match.start() : end].split())


def _net_sales_sum(section: str, commodity: str) -> tuple[float, list[dict[str, Any]]]:
    export_match = re.search(r"\bExports?\s+(?:of|were|totaled)", section, re.IGNORECASE)
    sales_text = section[: export_match.start()] if export_match else section
    values: list[dict[str, Any]] = []
    match = NET_SALES_RE.search(sales_text)
    if match is not None:
        prefix = str(match.group("prefix"))
        sign = -1.0 if "reduction" in prefix.lower() else 1.0
        values.append(
            {
                "marketing_year": match.group("marketing_year"),
                "net_sales_mt": sign * float(match.group("amount").replace(",", "")),
            }
        )
        joined = JOINED_MARKETING_YEAR_RE.match(sales_text[match.end() :])
        if joined is not None:
            values.append(
                {
                    "marketing_year": joined.group("marketing_year"),
                    "net_sales_mt": sign
                    * float(joined.group("amount").replace(",", "")),
                }
            )
    if not values:
        no_sales = re.search(
            r"\bno\s+(?:net\s+)?sales\b.*?\b(?:reported|for the week)\b",
            sales_text,
            re.IGNORECASE,
        )
        if no_sales is None:
            raise SourceContractError(f"{commodity} net-sales amount missing")
        values.append({"marketing_year": None, "net_sales_mt": 0.0})
    if len(values) > 2:
        raise SourceContractError(
            f"{commodity} has more than two marketing-year values: {values!r}"
        )
    return sum(float(row["net_sales_mt"]) for row in values), values


def _parse_pdf(item: dict[str, Any], raw: bytes) -> dict[str, Any]:
    if not raw.startswith(b"%PDF"):
        raise SourceContractError(f"non-PDF bytes for {item['report_id']}")
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SourceContractError("PyMuPDF/fitz is required for source refresh") from exc
    document = fitz.open(stream=raw, filetype="pdf")
    if len(document) < 2:
        raise SourceContractError(f"short USDA PDF for {item['report_id']}")
    text = "\n".join(
        document[index].get_text() for index in range(min(7, len(document)))
    )
    corn_section = _commodity_section(text, "Corn", ("Barley", "Sorghum", "Rice"))
    soy_section = _commodity_section(
        text,
        "Soybeans",
        (
            "Exports for Own Account",
            "Soybean Cake and Meal",
            "Soybean Cake & Meal",
            "Soybean Oil",
        ),
    )
    corn_total, corn_marketing_years = _net_sales_sum(corn_section, "Corn")
    soy_total, soy_marketing_years = _net_sales_sum(soy_section, "Soybeans")

    footer_evidence: dict[date, str] = {}
    bell_evidence: dict[date, str] = {}
    for match in FOOTER_DATE_RE.finditer(text):
        try:
            parsed = datetime.strptime(match.group(1), "%B %d, %Y").date()
        except ValueError:
            continue
        footer_evidence.setdefault(parsed, match.group(0))
    for match in BELL_RELEASE_DATE_RE.finditer(text):
        try:
            parsed = datetime.strptime(match.group(1), "%m-%d-%Y").date()
        except ValueError:
            continue
        bell_evidence.setdefault(parsed, match.group(0))
    week = date.fromisoformat(item["week_ending"])
    valid_footer_dates = sorted(day for day in footer_evidence if day > week)
    valid_bell_dates = sorted(day for day in bell_evidence if day > week)
    valid_release_dates = sorted({*valid_footer_dates, *valid_bell_dates})
    if not valid_release_dates:
        raise SourceContractError(
            f"actual USDA PDF release date missing for {item['week_ending']}"
        )
    release = valid_release_dates[0]
    release_source = (
        "pdf_bell_confidentiality_header"
        if release in valid_bell_dates
        else "pdf_release_header"
    )
    release_excerpt = (
        bell_evidence[release]
        if release_source == "pdf_bell_confidentiality_header"
        else footer_evidence[release]
    )
    lag_days = (release - week).days
    if not 5 <= lag_days <= 70:
        raise SourceContractError(
            f"implausible USDA release lag {lag_days} for {item['week_ending']}"
        )
    source_url = f"{ESRQS_API}/reports/GetPdfFile?Id={item['report_id']}"
    return {
        "release_date": release.isoformat(),
        "release_time_et": "08:30:00",
        "release_date_source": release_source,
        "release_date_semantics": "pdf_embedded_actual_release_date",
        "release_lag_days": lag_days,
        "week_ending": item["week_ending"],
        "corn_net_sales_mt": corn_total,
        "soybeans_net_sales_mt": soy_total,
        "corn_marketing_years": corn_marketing_years,
        "soybeans_marketing_years": soy_marketing_years,
        "source_report_id": item["report_id"],
        "source_url": source_url,
        "source_list_endpoint": (
            f"{ESRQS_API}/reports/GetArchivedWeeklyReportsList?selectedYear={item['year']}"
        ),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "excerpt_sha256": {
            "corn": hashlib.sha256(corn_section.encode("utf-8")).hexdigest(),
            "soybeans": hashlib.sha256(soy_section.encode("utf-8")).hexdigest(),
        },
        "corn_source_excerpt": corn_section,
        "soybeans_source_excerpt": soy_section,
        "corn_source_excerpt_sha256": hashlib.sha256(
            corn_section.encode("utf-8")
        ).hexdigest(),
        "soybeans_source_excerpt_sha256": hashlib.sha256(
            soy_section.encode("utf-8")
        ).hexdigest(),
        "release_source_excerpt": release_excerpt,
        "release_source_excerpt_sha256": hashlib.sha256(
            release_excerpt.encode("utf-8")
        ).hexdigest(),
        "parser_format": (
            "legacy_weekly_report_narrative_v1"
            if valid_footer_dates
            else "esrqs_weekly_report_narrative_v1"
        ),
        "source_rule_version": "usda_esrqs_archived_pdf_as_published_v1",
    }


def refresh_source() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Download and normalize official archived reports without persisting PDFs."""

    token = _anonymous_bearer()
    archive = _archive_rows(token)
    headers = {"Authorization": f"Bearer {token}"}
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def fetch_one(item: dict[str, Any]) -> dict[str, Any]:
        url = f"{ESRQS_API}/reports/GetPdfFile?Id={item['report_id']}"
        raw = _fetch_bytes(url, headers=headers)
        return _parse_pdf(item, raw)

    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as executor:
        futures = {executor.submit(fetch_one, item): item for item in archive}
        for future in as_completed(futures):
            item = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:  # fail closed after complete diagnostics
                errors.append(
                    {
                        "report_id": item["report_id"],
                        "week_ending": item["week_ending"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    records.sort(key=lambda row: (row["release_date"], row["week_ending"]))
    if errors or len(records) != len(archive):
        raise SourceContractError(
            f"USDA archive parse incomplete: {len(records)}/{len(archive)}; "
            f"errors={errors[:12]!r}"
        )
    payload = {
        "schema": "usda_fas_export_sales_normalized_records_v1",
        "source_rule_version": "usda_esrqs_archived_pdf_as_published_v1",
        "records": records,
    }
    manifest = {
        "schema": "usda_fas_export_sales_source_manifest_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "official_service": ESRQS_ROOT,
        "archive_list_endpoint_template": (
            f"{ESRQS_API}/reports/GetArchivedWeeklyReportsList?selectedYear={{year}}"
        ),
        "pdf_endpoint_template": f"{ESRQS_API}/reports/GetPdfFile?Id={{id}}",
        "source_years": [SOURCE_START_YEAR, SOURCE_END_YEAR],
        "archive_row_count": len(archive),
        "normalized_record_count": len(records),
        "parse_error_count": 0,
        "coverage_fraction": 1.0,
        "week_ending_min": records[0]["week_ending"],
        "week_ending_max": records[-1]["week_ending"],
        "release_date_min": records[0]["release_date"],
        "release_date_max": records[-1]["release_date"],
        "parser_format_counts": dict(
            sorted(Counter(row["parser_format"] for row in records).items())
        ),
        "records_sha256": _canonical_sha(records),
        "raw_pdf_set_sha256": _canonical_sha(
            [
                {
                    "source_report_id": row["source_report_id"],
                    "raw_sha256": row["raw_sha256"],
                }
                for row in records
            ]
        ),
        "current_api_values_used": False,
        "trade_enabled": False,
    }
    _atomic_write(SOURCE_RECORDS_PATH, payload)
    _atomic_write(SOURCE_MANIFEST_PATH, manifest)
    return validate_source()


def validate_source() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not SOURCE_RECORDS_PATH.exists() or not SOURCE_MANIFEST_PATH.exists():
        raise SourceContractError(
            "frozen USDA source missing; run without --offline once"
        )
    payload = _read_json(SOURCE_RECORDS_PATH)
    records = payload.get("records") if isinstance(payload, dict) else payload
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    if not isinstance(records, list) or not isinstance(manifest, dict):
        raise SourceContractError("USDA source artifacts have invalid top-level schema")
    canonical: list[dict[str, Any]] = []
    seen_weeks: set[str] = set()
    seen_ids: set[str] = set()
    allowed_release_sources = {
        "pdf_release_header",
        "pdf_bell_confidentiality_header",
        "official_usda_catchup_schedule",
    }
    for raw in records:
        if not isinstance(raw, dict):
            raise SourceContractError("USDA canonical record is not an object")
        release_date = _iso_date(raw.get("release_date"))
        week_ending = _iso_date(raw.get("week_ending"))
        report_id = str(raw.get("source_report_id") or raw.get("report_id") or "").lower()
        raw_sha = str(raw.get("raw_sha256") or "").lower()
        corn = _number(raw.get("corn_net_sales_mt"))
        soy = _number(raw.get("soybeans_net_sales_mt"))
        source_url = str(raw.get("source_url") or "")
        release_source = str(raw.get("release_date_source") or "")
        corn_excerpt = str(raw.get("corn_source_excerpt") or "")
        soy_excerpt = str(raw.get("soybeans_source_excerpt") or "")
        release_excerpt = str(raw.get("release_source_excerpt") or "")
        corn_excerpt_sha = str(raw.get("corn_source_excerpt_sha256") or "")
        soy_excerpt_sha = str(raw.get("soybeans_source_excerpt_sha256") or "")
        release_excerpt_sha = str(raw.get("release_source_excerpt_sha256") or "")
        if (
            release_date is None
            or week_ending is None
            or UUID_RE.fullmatch(report_id) is None
            or SHA256_RE.fullmatch(raw_sha) is None
            or corn is None
            or soy is None
            or report_id in seen_ids
            or week_ending in seen_weeks
            or not source_url.startswith(f"{ESRQS_API}/reports/GetPdfFile?Id=")
            or release_source not in allowed_release_sources
            or str(raw.get("release_time_et") or "") != "08:30:00"
            or not corn_excerpt
            or not soy_excerpt
            or not release_excerpt
            or hashlib.sha256(corn_excerpt.encode("utf-8")).hexdigest()
            != corn_excerpt_sha
            or hashlib.sha256(soy_excerpt.encode("utf-8")).hexdigest()
            != soy_excerpt_sha
            or hashlib.sha256(release_excerpt.encode("utf-8")).hexdigest()
            != release_excerpt_sha
        ):
            raise SourceContractError(f"invalid USDA canonical record: {raw!r}")
        if release_source == "official_usda_catchup_schedule" and (
            not str(raw.get("release_schedule_url") or "").startswith(
                "https://www.fas.usda.gov/"
            )
            or SHA256_RE.fullmatch(
                str(raw.get("release_schedule_raw_sha256") or "")
            )
            is None
        ):
            raise SourceContractError(
                f"invalid USDA catch-up schedule evidence for {week_ending}"
            )
        lag = (date.fromisoformat(release_date) - date.fromisoformat(week_ending)).days
        if not 5 <= lag <= 70:
            raise SourceContractError(f"invalid USDA release lag for {week_ending}: {lag}")
        seen_ids.add(report_id)
        seen_weeks.add(week_ending)
        canonical.append(
            {
                **raw,
                "release_date": release_date,
                "week_ending": week_ending,
                "source_report_id": report_id,
                "raw_sha256": raw_sha,
                "corn_net_sales_mt": corn,
                "soybeans_net_sales_mt": soy,
                "release_time_et": str(raw.get("release_time_et") or "08:30:00"),
                "source_rule_version": str(
                    raw.get("source_rule_version")
                    or "usda_esrqs_archived_pdf_as_published_v1"
                ),
            }
        )
    canonical.sort(key=lambda row: (row["release_date"], row["week_ending"]))
    manifest_count = int(
        manifest.get("normalized_record_count")
        or manifest.get("record_count")
        or len(canonical)
    )
    parse_errors = int(manifest.get("parse_error_count") or 0)
    coverage = _number(manifest.get("coverage_fraction"))
    manifest_sha = str(manifest.get("records_sha256") or "")
    if manifest_count != len(canonical) or parse_errors != 0:
        raise SourceContractError("USDA manifest count/error contract failed")
    if coverage is not None and not math.isclose(coverage, 1.0, abs_tol=1e-12):
        raise SourceContractError("USDA manifest is not complete")
    if manifest_sha and manifest_sha != _canonical_sha(canonical):
        # A preflight artifact may hash the uncoerced but semantically equal
        # payload.  Require its stored records file hash instead of silently
        # accepting a mismatched canonical hash.
        stored_records = payload.get("records") if isinstance(payload, dict) else payload
        if manifest_sha != _canonical_sha(stored_records):
            raise SourceContractError("USDA normalized records hash mismatch")
    return canonical, manifest


def materialize_ohlcv() -> dict[str, Any]:
    if not WAREHOUSE_PATH.exists():
        raise SourceContractError(f"warehouse missing: {WAREHOUSE_PATH}")
    placeholders = ",".join("?" for _ in ALL_OHLCV_TICKERS)
    query = (
        "SELECT ticker,date,open,high,low,close,volume,source,updated_at "
        f"FROM ohlcv WHERE ticker IN ({placeholders}) AND date>=? AND date<=? "
        "ORDER BY ticker,date"
    )
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {
        ticker: [] for ticker in ALL_OHLCV_TICKERS
    }
    with sqlite3.connect(WAREHOUSE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            query, (*ALL_OHLCV_TICKERS, AUXILIARY_START, AUXILIARY_END)
        ).fetchall()
    for row in rows:
        item = dict(row)
        ticker = str(item.pop("ticker"))
        rows_by_ticker[ticker].append(item)
    missing = sorted(ticker for ticker, rows in rows_by_ticker.items() if not rows)
    if missing:
        raise SourceContractError(f"required auxiliary OHLCV missing: {missing}")
    payload = {
        "schema": "usda_fas_export_sales_auxiliary_ohlcv_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warehouse": _repo_rel(WAREHOUSE_PATH),
        "query_start": AUXILIARY_START,
        "query_end": AUXILIARY_END,
        "tickers": list(ALL_OHLCV_TICKERS),
        "ticker_row_counts": {
            ticker: len(rows_by_ticker[ticker]) for ticker in ALL_OHLCV_TICKERS
        },
        "row_count": sum(len(rows) for rows in rows_by_ticker.values()),
        "rowset_sha256": _canonical_sha(rows_by_ticker),
        "ohlcv": rows_by_ticker,
    }
    _atomic_write(OHLCV_PATH, payload)
    return payload


def load_ohlcv() -> dict[str, Any]:
    if not OHLCV_PATH.exists():
        return materialize_ohlcv()
    payload = _read_json(OHLCV_PATH)
    rows = payload.get("ohlcv") or {}
    if set(ALL_OHLCV_TICKERS) - set(rows):
        return materialize_ohlcv()
    if payload.get("rowset_sha256") != _canonical_sha(rows):
        raise SourceContractError("frozen auxiliary OHLCV hash mismatch")
    return payload


def _baseline_windows(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


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
        raise SourceContractError(f"window OHLCV missing: {missing}")
    return output, {
        "gate1_snapshot": _repo_rel(snapshot_path),
        "gate1_snapshot_sha256": _file_sha(snapshot_path),
        "exact_snapshot_tickers": sorted(exact),
        "auxiliary_fill_tickers": sorted(set(ALL_OHLCV_TICKERS) - set(exact)),
    }


def _bar_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or "")[:10]


def _bar_index(
    ohlcv: dict[str, list[dict[str, Any]]]
) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, rows in ohlcv.items():
        output[ticker] = {}
        for row in rows:
            day = _bar_date(row)
            open_price = _number(row.get("open") if "open" in row else row.get("Open"))
            close = _number(row.get("close") if "close" in row else row.get("Close"))
            if day and open_price is not None and close is not None:
                output[ticker][day] = {"open": open_price, "close": close}
    return output


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha({"schema": "dated_periodic_return_series_v1", "rows": rows})


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


def _target_mark(
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
    max_drawdown = 0.0
    for day, equity in curve:
        periodic_return = equity / previous - 1.0 if previous else 0.0
        returns.append({"date": day, "return": periodic_return})
        previous = equity
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
    values = [float(row["return"]) for row in returns]
    sharpe_full = None
    if len(values) >= 2:
        mean = statistics.mean(values)
        variance = statistics.variance(values)
        if variance > 0:
            sharpe_full = mean / math.sqrt(variance) * math.sqrt(252)
    total_pnl = curve[-1][1] - 100_000.0
    total_return = round(total_pnl / 100_000.0, 4)
    sharpe_public = round(sharpe_full, 2) if sharpe_full is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": total_return},
        "sharpe_daily": sharpe_public,
        "sharpe_daily_full_precision": sharpe_full,
        "expected_value_score": (
            round(total_return * sharpe_public, 4)
            if sharpe_public is not None
            else None
        ),
        "max_drawdown_pct": round(max_drawdown, 4),
        "total_trades": trade_count,
        "return_series": returns,
        "return_series_sha256": _return_series_sha(returns),
    }


def _combine_window(
    baseline: dict[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_curve = _baseline_curve(baseline)
    lookup = _bar_index(ohlcv)
    combined = [
        (day, equity + _target_mark(trades, lookup, day))
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
        "sharpe_daily_full_precision": baseline["sharpe_daily_full_precision"],
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
    return before, after


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
        "positive_contribution_ticker_count": len(positive),
        "positive_contribution_tickers": sorted(positive),
        "window_count": sum(count > 0 for count in event_counts.values()),
        "by_window_trade_count": {
            label: len(trades_by_window.get(label) or []) for label in WINDOWS
        },
        "by_window_settled_event_count": event_counts,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "hhi_concentration": (
            round(sum(share * share for share in shares), 6) if shares else None
        ),
        "top_5_contribution_pct": round(sum(shares[:5]), 6) if shares else None,
    }


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(float(row["before"]["expected_value_score"]) for row in rows.values()), 4
        ),
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in rows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in rows.values()), 4
        ),
        "before_total_pnl_sum": round(
            sum(float(row["before"]["total_pnl"]) for row in rows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(float(row["after"]["total_pnl"]) for row in rows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(float(row["delta"]["total_pnl"]) for row in rows.values()), 2
        ),
        "windows_ev_improved": sum(
            float(row["delta"]["expected_value_score"]) > 0 for row in rows.values()
        ),
        "windows_ev_regressed": sum(
            float(row["delta"]["expected_value_score"]) < 0 for row in rows.values()
        ),
        "windows_pnl_improved": sum(
            float(row["delta"]["total_pnl"]) > 0 for row in rows.values()
        ),
        "windows_pnl_regressed": sum(
            float(row["delta"]["total_pnl"]) < 0 for row in rows.values()
        ),
        "max_drawdown_worse_max": max(
            float(row["delta"]["max_drawdown_pct"]) for row in rows.values()
        ),
    }


def _benchmark_diagnostics(
    trades: list[dict[str, Any]],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade["decision_id"])].append(trade)
    lookup = _bar_index(ohlcv)
    events: list[dict[str, Any]] = []
    for decision_id, legs in sorted(grouped.items()):
        entry_dates = {str(row["entry_date"]) for row in legs}
        scheduled_dates = {str(row["scheduled_exit_date"]) for row in legs}
        if len(entry_dates) != 1 or len(scheduled_dates) != 1 or len(legs) != 10:
            raise SourceContractError(f"benchmark event contract failed: {decision_id}")
        notional = sum(float(row["paper_notional_usd"]) for row in legs)
        events.append(
            {
                "decision_id": decision_id,
                "entry_date": next(iter(entry_dates)),
                "scheduled_exit_date": next(iter(scheduled_dates)),
                "notional_usd": notional,
                "target_return": sum(float(row["pnl"]) for row in legs) / notional,
            }
        )
    target_returns = [row["target_return"] for row in events]
    target_mean = statistics.mean(target_returns) if target_returns else None
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

    for ticker in ("SPY", "QQQ", "DBA"):
        returns: list[float] = []
        missing: list[str] = []
        for event in events:
            entry = lookup.get(ticker, {}).get(event["entry_date"])
            exit_row = lookup.get(ticker, {}).get(event["scheduled_exit_date"])
            if entry is None or exit_row is None:
                missing.append(event["decision_id"])
                continue
            returns.append(
                exit_row["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
            )
        complete = bool(events) and not missing
        comparators[ticker] = {
            "available": complete,
            "event_count": len(returns),
            "missing_decision_ids": missing,
            "mean_event_return": statistics.mean(returns) if complete else None,
            "matched_total_pnl": (
                sum(
                    value * event["notional_usd"]
                    for value, event in zip(returns, events, strict=True)
                )
                if complete
                else None
            ),
        }

    direct_returns: list[float] = []
    direct_missing: list[str] = []
    for event in events:
        component_returns: list[float] = []
        for ticker in ("CORN", "SOYB"):
            entry = lookup.get(ticker, {}).get(event["entry_date"])
            exit_row = lookup.get(ticker, {}).get(event["scheduled_exit_date"])
            if entry is None or exit_row is None:
                component_returns = []
                break
            component_returns.append(
                exit_row["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
            )
        if len(component_returns) != 2:
            direct_missing.append(event["decision_id"])
        else:
            direct_returns.append(statistics.mean(component_returns))
    direct_complete = bool(events) and not direct_missing
    comparators["CORN_SOYB_DIRECT"] = {
        "available": direct_complete,
        "event_count": len(direct_returns),
        "missing_decision_ids": direct_missing,
        "mean_event_return": (
            statistics.mean(direct_returns) if direct_complete else None
        ),
        "matched_total_pnl": (
            sum(
                value * event["notional_usd"]
                for value, event in zip(direct_returns, events, strict=True)
            )
            if direct_complete
            else None
        ),
    }
    required = ["CASH", "SPY", "QQQ", "DBA", "CORN_SOYB_DIRECT"]
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
        "benchmark_horizon": "same entry open to scheduled tenth-session close",
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "comparators": comparators,
        "required_comparators": required,
        "unavailable_comparators": unavailable,
        "failed_performance_comparators": failed_performance,
        "failed_comparators": list(dict.fromkeys([*unavailable, *failed_performance])),
        "passed": bool(events) and not unavailable and not failed_performance,
    }


def _aggregate_benchmark_diagnostics(
    windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate exact per-window benchmark rows without swapping OHLCV sources."""

    names = ("TARGET", "CASH", "SPY", "QQQ", "DBA", "CORN_SOYB_DIRECT")
    required = ["CASH", "SPY", "QQQ", "DBA", "CORN_SOYB_DIRECT"]
    nonempty = [
        row["benchmark"]
        for row in windows.values()
        if int(row["benchmark"].get("event_count") or 0) > 0
    ]
    comparators: dict[str, Any] = {}
    for name in names:
        parts = [row["comparators"][name] for row in nonempty]
        event_count = sum(int(part.get("event_count") or 0) for part in parts)
        complete = bool(parts) and all(bool(part.get("available")) for part in parts)
        weighted_return = (
            sum(
                float(part["mean_event_return"]) * int(part["event_count"])
                for part in parts
            )
            / event_count
            if complete and event_count
            else None
        )
        comparators[name] = {
            "available": complete,
            "event_count": event_count,
            "mean_event_return": weighted_return,
            "matched_total_pnl": (
                sum(float(part["matched_total_pnl"]) for part in parts)
                if complete
                else None
            ),
            "missing_decision_ids": [
                decision_id
                for part in parts
                for decision_id in (part.get("missing_decision_ids") or [])
            ],
        }
    target_mean = comparators["TARGET"]["mean_event_return"]
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
        "event_count": comparators["TARGET"]["event_count"],
        "event_equal_weighted": True,
        "benchmark_horizon": "same entry open to scheduled tenth-session close",
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "comparators": comparators,
        "required_comparators": required,
        "unavailable_comparators": unavailable,
        "failed_performance_comparators": failed_performance,
        "failed_comparators": list(dict.fromkeys([*unavailable, *failed_performance])),
        "passed": bool(nonempty) and not unavailable and not failed_performance,
        "aggregation": "event-count-weighted exact per-window OHLCV comparators",
    }


def _open_positions_gate() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = _read_json(path)
    if isinstance(payload, dict):
        rows = payload.get("positions") or payload.get("open_positions") or []
    else:
        rows = payload
    rows = rows if isinstance(rows, list) else []
    missing_entry = []
    missing_target = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "UNKNOWN")
        if not row.get("entry_date"):
            missing_entry.append(ticker)
        if row.get("target_price") in (None, ""):
            missing_target.append(ticker)
    return {
        "path": _repo_rel(path),
        "position_count": len(rows),
        "missing_entry_date_tickers": sorted(missing_entry),
        "missing_target_price_tickers": sorted(missing_target),
        "passed": not missing_entry and not missing_target,
    }


def _build_dsr(
    windows: dict[str, dict[str, Any]], manifest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    ordered = list(WINDOWS)
    series = [
        point
        for label in ordered
        for point in windows[label]["after"]["return_series"]
    ]
    dates = [str(row["date"]) for row in series]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SourceContractError("DSR return dates are not strictly aligned")
    panel = {
        "selected_config_id": "usda_fas_export_sales_agriculture_basket_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": True,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            {
                "config_id": "usda_fas_export_sales_agriculture_basket_on",
                "config": {
                    "rule_version": RULE_VERSION,
                    "basket": list(AGRICULTURE_BASKET),
                },
                "attempted": True,
                "selection_scope": "usda_fas_export_sales_as_published_agriculture_basket",
                "window": {
                    "segments": [
                        {"label": label, "start": WINDOWS[label][0], "end": WINDOWS[label][1]}
                        for label in ordered
                    ]
                },
                "frequency": "daily",
                "return_basis": "core_plus_usda_fixed_agriculture_basket_daily_mtm_post_cost",
                "risk_free_assumption": "zero",
                "protocol": {
                    "id": "post_mtm_gate1_plus_usda_fas_export_sales_v1",
                    "rule_version": RULE_VERSION,
                },
                "data": {
                    "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY_PATH),
                    "source_manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
                    "source_generated_at": (
                        manifest.get("generated_at")
                        or manifest.get("generated_at_utc")
                    ),
                    "auxiliary_ohlcv_sha256": _file_sha(OHLCV_PATH),
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
    _atomic_write(DSR_PANEL_PATH, panel)
    _atomic_write(DSR_REPORT_PATH, report)
    return panel, report


def build_evaluation(*, offline: bool) -> dict[str, Any]:
    if tuple(AGRICULTURE_BASKET_V1) != AGRICULTURE_BASKET:
        raise SourceContractError("runner/helper agriculture basket drift")
    records, source_manifest = validate_source() if offline else refresh_source()
    auxiliary = load_ohlcv()
    broad = {
        ticker: list(rows) for ticker, rows in (auxiliary.get("ohlcv") or {}).items()
    }
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_windows(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise SourceContractError("Gate-1 baseline window labels drifted")

    window_results: dict[str, dict[str, Any]] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    events_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    selected_total = 0
    source_audits_valid = True
    gate2_fields_valid = True
    ohlcv_identity: dict[str, Any] = {}

    for label, (start, end) in WINDOWS.items():
        baseline = baseline_windows[label]
        window_bars, identity = _window_ohlcv(broad, baseline)
        ohlcv_identity[label] = identity
        trading_dates = sorted({_bar_date(row) for row in window_bars["SPY"] if _bar_date(row)})
        replay = replay_usda_fas_export_sales_agriculture_basket_paper_trades(
            records=records,
            ohlcv_by_ticker=window_bars,
            start=start,
            end=end,
            trading_dates=trading_dates,
        )
        trades = list(replay.get("trades") or [])
        events = list(replay.get("event_trades") or [])
        audit = replay.get("candidate_audit") or {}
        generated_total += int(replay.get("signals_generated") or 0)
        selected_total += int(replay.get("signals_survived") or 0)
        source_audits_valid = source_audits_valid and (
            audit.get("measurement_valid") is True
        )
        selected_candidates = list(replay.get("selected_candidates") or [])
        gate2_fields_valid = gate2_fields_valid and all(
            candidate.get("entry_date")
            and candidate.get("trade_enabled") is False
            and len(candidate.get("legs") or []) == 10
            and all(
                leg.get("entry_date")
                and leg.get("target_price") is not None
                and leg.get("trade_enabled") is False
                for leg in (candidate.get("legs") or [])
            )
            for candidate in selected_candidates
        )
        if any(len([row for row in trades if row["decision_id"] == event["decision_id"]]) != 10 for event in events):
            gate2_fields_valid = False
        before, after = _combine_window(baseline, trades, window_bars)
        delta = {
            "expected_value_score": round(
                float(after["expected_value_score"])
                - float(before["expected_value_score"]),
                4,
            ),
            "total_pnl": round(float(after["total_pnl"]) - float(before["total_pnl"]), 2),
            "max_drawdown_pct": round(
                float(after["max_drawdown_pct"])
                - float(before["max_drawdown_pct"]),
                4,
            ),
            "trade_count": int(after["total_trades"]) - int(before["total_trades"]),
        }
        trades_by_window[label] = trades
        events_by_window[label] = events
        window_results[label] = {
            "label": label,
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": delta,
            "replay": replay,
            "benchmark": _benchmark_diagnostics(trades, window_bars),
            "ohlcv_identity": identity,
        }

    aggregate = _aggregate_windows(window_results)
    target = _target_summary(trades_by_window, events_by_window)
    benchmarks = _aggregate_benchmark_diagnostics(window_results)
    open_positions = _open_positions_gate()
    gate2_passed = (
        source_audits_valid
        and gate2_fields_valid
        and open_positions["passed"]
        and len(records) > 0
        and selected_total > 0
        and int(source_manifest.get("parse_error_count") or 0) == 0
    )
    event_survival_rate = selected_total / generated_total if generated_total else 0.0
    gate3 = {
        "signals_generated": generated_total,
        "signals_survived": selected_total,
        "signals_settled": target["settled_event_count"],
        "survival_rate": round(event_survival_rate, 6),
        "passed": generated_total > 0 and event_survival_rate >= 0.05,
        "unit": "independent_release_event",
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
        "single_ticker_positive_share": target["single_ticker_positive_share"],
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
        min_ev_improved_windows=2,
        max_ev_regressed_windows=1,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        require_tail_concentration_not_worse=False,
    )
    canonical_gate4 = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    failures = list(canonical_gate4["hard_failures"])
    if aggregate["windows_pnl_improved"] < 2 or aggregate["windows_pnl_regressed"] > 1:
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
    if target["positive_contribution_ticker_count"] < MIN_POSITIVE_TICKERS:
        failures.append("positive_contribution_tickers_below_9")
    if not benchmarks["passed"]:
        failures.append("required_cash_spy_qqq_dba_corn_soyb_comparator_not_beaten")
    for comparator in ACCEPTED_COMPARATORS:
        if (
            aggregate["expected_value_score_delta_sum"]
            <= comparator["expected_value_score_delta_sum"]
        ):
            failures.append(
                f"accepted_candidate_ev_not_beaten:{comparator['experiment_id']}"
            )
        if aggregate["total_pnl_delta_sum"] <= comparator["total_pnl_delta_sum"]:
            failures.append(
                f"accepted_candidate_pnl_not_beaten:{comparator['experiment_id']}"
            )
    failures = list(dict.fromkeys(failures))
    numeric_gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical": canonical_gate4,
        "metrics": gate_metrics,
        "comparator_gate": benchmarks,
        "accepted_candidate_comparators": list(ACCEPTED_COMPARATORS),
    }
    panel, dsr_report = _build_dsr(window_results, source_manifest)
    envelope = ExecutionEnvelope(
        base_notional=5000.0,
        max_capital_pct=0.10,
        min_dollar_volume=250000.0,
        slippage_bps=5.0,
        max_displacement=0,
        max_concurrent=2,
        order_semantics="default-off paper next regular open; no live order emitted",
        kill_switch_drawdown_pct=0.05,
        sleeve_drawdown_stop_pct=0.08,
        notes=(
            "ETF legs also cap notional at 0.2 percent ADV; equities require "
            "50 million USD ADV20. All ten legs are mandatory."
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
    stack = full_stack_verdict(
        gate4=numeric_gate4, live_readiness=live, envelope=envelope
    )
    snapshot = build_usda_fas_export_sales_agriculture_basket_paper_snapshot(
        as_of_date=PAPER_SNAPSHOT_AS_OF,
        records=records,
        ohlcv_by_ticker=broad,
        trading_dates=sorted({_bar_date(row) for row in broad["SPY"] if _bar_date(row)}),
        state=empty_usda_fas_export_sales_agriculture_basket_paper_state(),
    )
    production_impact = {
        "enabled": False,
        "paper_enabled": True,
        "trade_enabled": False,
        "run_adapter_changed": False,
        "live_orders_changed": False,
        "core_ranking_changed": False,
        "core_sizing_changed": False,
        "core_exits_changed": False,
        "daily_snapshot_role": "one-shot default-off parity artifact only",
    }
    return {
        "schema": "usda_fas_export_sales_agriculture_basket_full_stack_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "As-published USDA FAS weekly corn/soybean export-sales strength "
            "above the fixed prior-104 p75 may lead a fixed ten-leg agriculture "
            "value-chain basket over ten sessions."
        ),
        "rule_version": RULE_VERSION,
        "source": {
            "records_path": _repo_rel(SOURCE_RECORDS_PATH),
            "records_sha256": _file_sha(SOURCE_RECORDS_PATH),
            "manifest_path": _repo_rel(SOURCE_MANIFEST_PATH),
            "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
            "record_count": len(records),
            "manifest": source_manifest,
        },
        "gate1": {
            "passed": True,
            "baseline": _repo_rel(BASELINE_SUMMARY_PATH),
            "baseline_sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "baseline_aggregate": baseline_summary["aggregate"],
            "ohlcv_identity": ohlcv_identity,
        },
        "gate2": {
            "passed": gate2_passed,
            "source_audits_valid": source_audits_valid,
            "candidate_entry_date_target_price_valid": gate2_fields_valid,
            "open_positions": open_positions,
            "runtime_fields": [
                "official ESRQS archive report id and PDF sha256",
                "week_ending and audited actual release date at 08:30 ET",
                "Corn and Soybeans current plus next marketing-year net sales",
                "warehouse Date/Open/High/Low/Close/Volume",
                "entry_date",
                "target_price",
            ],
        },
        "gate3": gate3,
        "gate4": numeric_gate4,
        "gate5": {
            "deflated_sharpe": dsr_report,
            "panel_path": _repo_rel(DSR_PANEL_PATH),
            "report_path": _repo_rel(DSR_REPORT_PATH),
            "live_readiness": live,
        },
        "full_stack": stack,
        "windows": window_results,
        "aggregate": aggregate,
        "target_summary": target,
        "matched_benchmarks": benchmarks,
        "paper_snapshot": snapshot,
        "production_impact": production_impact,
        "decision": (
            "accepted_paper_pending_forward"
            if stack["verdict"] == "accepted_paper_pending_forward"
            else "rejected_usda_fas_export_sales_agriculture_basket"
        ),
        "trade_enabled": False,
        "orders": [],
    }


def write_outputs(payload: dict[str, Any]) -> None:
    _atomic_write(RESULT_PATH, payload)
    _atomic_write(PAPER_SNAPSHOT_PATH, payload["paper_snapshot"])
    aggregate = payload["aggregate"]
    target = payload["target_summary"]
    gate3 = payload["gate3"]
    core_survival_rate = round(
        float(payload["gate1"]["baseline_aggregate"]["minimum_survival_rate"]),
        6,
    )
    before = {
        "schema": "usda_fas_export_sales_gate4_before_v1",
        "experiment_id": EXPERIMENT_ID,
        "expected_value_score": aggregate["before_expected_value_score_sum"],
        "total_pnl": aggregate["before_total_pnl_sum"],
        "max_drawdown_pct": round(
            max(row["before"]["max_drawdown_pct"] for row in payload["windows"].values()),
            4,
        ),
        "total_trades": sum(
            int(row["before"]["total_trades"]) for row in payload["windows"].values()
        ),
        "survival_rate": core_survival_rate,
        "benchmarks": {
            "strategy_total_return_pct": round(
                aggregate["before_total_pnl_sum"] / 100_000.0, 4
            )
        },
    }
    after = {
        "schema": "usda_fas_export_sales_gate4_after_v1",
        "experiment_id": EXPERIMENT_ID,
        "expected_value_score": aggregate["after_expected_value_score_sum"],
        "total_pnl": aggregate["after_total_pnl_sum"],
        "max_drawdown_pct": round(
            max(row["after"]["max_drawdown_pct"] for row in payload["windows"].values()),
            4,
        ),
        "total_trades": sum(
            int(row["after"]["total_trades"]) for row in payload["windows"].values()
        ),
        "survival_rate": core_survival_rate,
        "usda_event_survival_rate": gate3["survival_rate"],
        "benchmarks": {
            "strategy_total_return_pct": round(
                aggregate["after_total_pnl_sum"] / 100_000.0, 4
            )
        },
    }
    _atomic_write(BEFORE_PATH, before)
    _atomic_write(AFTER_PATH, after)
    lines = [
        f"# {EXPERIMENT_ID} USDA FAS export-sales agriculture basket",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Full-stack verdict: `{payload['full_stack']['verdict']}`",
        f"- Settled releases / legs: `{target['settled_event_count']}` / `{target['total_trade_count']}`",
        f"- Window events: `{target['by_window_settled_event_count']}`",
        f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
        f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
        f"- Gate 3 event survival: `{gate3['survival_rate']:.2%}`",
        f"- Positive-contribution tickers: `{target['positive_contribution_ticker_count']}`",
        f"- Top-five contribution: `{target['top_5_contribution_pct']}`",
        f"- Failed matched benchmarks: `{payload['matched_benchmarks']['failed_comparators']}`",
        f"- Gate 4 failures: `{payload['gate4']['hard_failures']}`",
        f"- DSR: `{payload['gate5']['deflated_sharpe'].get('status')}`",
        "",
        "## Window deltas",
        "",
    ]
    for label, row in payload["windows"].items():
        lines.append(
            f"- {label}: events={len(row['replay'].get('event_trades') or [])}, "
            f"legs={len(row['replay'].get('trades') or [])}, "
            f"EV={row['delta']['expected_value_score']:+.4f}, "
            f"PnL=${row['delta']['total_pnl']:+,.2f}, "
            f"drawdown={row['delta']['max_drawdown_pct']:+.4f}."
        )
    lines.extend(
        [
            "",
            "## Evidence contract",
            "",
            "Every independent sample is one archived weekly USDA release; stock legs do not inflate the sample count. Current revisable ESR API values are excluded.",
            "",
            "The daily snapshot is default-off and one-shot. No run.py, live order, core ranking, sizing, or exit path changed.",
            "",
            f"Reproduce offline: `.\\.venv\\Scripts\\python.exe -B {_repo_rel(Path(__file__))} --offline`",
        ]
    )
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use frozen official normalized records; do not access USDA.",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Refresh/validate source and stop before OHLCV evaluation.",
    )
    args = parser.parse_args()
    if args.source_only:
        records, manifest = validate_source() if args.offline else refresh_source()
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "record_count": len(records),
                    "manifest": manifest,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    payload = build_evaluation(offline=args.offline)
    write_outputs(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "verdict": payload["full_stack"]["verdict"],
                "events": payload["target_summary"]["settled_event_count"],
                "events_by_window": payload["target_summary"]["by_window_settled_event_count"],
                "aggregate_ev_delta": payload["aggregate"]["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": payload["aggregate"]["total_pnl_delta_sum"],
                "gate4_failures": payload["gate4"]["hard_failures"],
                "result": _repo_rel(RESULT_PATH),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
