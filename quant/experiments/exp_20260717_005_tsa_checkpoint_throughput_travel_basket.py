"""Outcome-blind PIT source audit for exp-20260717-005.

This runner deliberately stops before loading OHLCV.  It verifies whether the
TSA annual checkpoint table used during the density preflight is equivalent to
an immutable weekly FOIA report.  A mismatch or a post-cover PDF modification
date invalidates the preflight source contract and parks the policy before any
return is observed.
"""

from __future__ import annotations

import concurrent.futures
import email.utils
import hashlib
import html
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import fitz
import requests
from bs4 import BeautifulSoup


EXPERIMENT_ID = "exp-20260717-005"
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.tsa_checkpoint_throughput_paper_sleeve import (  # noqa: E402
    evaluate_tsa_checkpoint_throughput_events,
)

SOURCE_DIR = ROOT / "data" / "non_ohlcv" / "tsa_checkpoint_throughput"
EXPERIMENT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_PATH = (
    ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_tsa_checkpoint_throughput_preflight.md"
)

READING_ROOM_URL = (
    "https://www.tsa.gov/foia/readingroom?"
    "field_foia_category_value=Airport&title=&page={page}"
)
ANNUAL_2025_URL = "https://www.tsa.gov/travel/passenger-volumes/2025"
SENTINEL_PDF_URL = (
    "https://www.tsa.gov/sites/default/files/foia-readingroom/"
    "tsa-total-throughput-data-october-19-2025-to-october-25-2025.pdf"
)
CORRUPTED_COMPARATOR_PDF_URL = (
    "https://www.tsa.gov/sites/default/files/foia-readingroom/"
    "tsa-total-throughput-data-september-24-2023-to-september-30-2023.pdf"
)

DATE_TOKEN_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
INTEGER_TOKEN_RE = re.compile(r"^[\d,]+$")
PERIOD_RE = re.compile(
    r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s+to\s+"
    r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})"
)
PDF_META_DATE_RE = re.compile(r"D:(\d{4})(\d{2})(\d{2})")

WINDOWS = {
    "old_thin": (date(2024, 10, 2), date(2025, 4, 22)),
    "mid_weak": (date(2025, 4, 23), date(2025, 10, 22)),
    "late_strong": (date(2025, 10, 23), date(2026, 4, 21)),
}
DECLARED_PREFLIGHT_REPORT_COUNTS = {
    "old_thin": 26,
    "mid_weak": 24,
    "late_strong": 26,
}
RAW_MANIFEST_START = date(2023, 9, 1)
RAW_MANIFEST_END = date(2026, 4, 25)
MANIFEST_EXCEPTIONS = [
    {
        "period_start": "2024-10-27",
        "period_end": "2024-11-02",
        "conservative_cover_date": "2024-11-04",
        "title": "TSA Total Throughput Data October 27, 2024 to November 2, 2024",
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-total-throughput-data-october-27-2924-to-november-2-2024.pdf"
        ),
        "official_filename_caveat": "URL spells the start year as 2924",
    },
    {
        "period_start": "2025-10-19",
        "period_end": "2025-10-25",
        "conservative_cover_date": "2025-10-27",
        "title": "TSA Total Throughput Data October 19, 2025 to October 25, 2025",
        "source_url": SENTINEL_PDF_URL,
    },
    {
        "period_start": "2025-10-26",
        "period_end": "2025-11-01",
        "conservative_cover_date": "2025-11-03",
        "title": "TSA Total Throughput Data October 26, 2025 to November 1, 2025",
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-total-throughput-data-october-26-2025-to-november-1-2025.pdf"
        ),
    },
    {
        "period_start": "2025-11-02",
        "period_end": "2025-11-08",
        "conservative_cover_date": "2025-11-10",
        "title": "TSA Total Throughput Data November 2, 2025 to November 8, 2025",
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-total-thoughput-data-november-2-2025-to-november-8-2025.pdf"
        ),
        "official_filename_caveat": "URL spells throughput as thoughput",
    },
    {
        "period_start": "2025-11-09",
        "period_end": "2025-11-15",
        "conservative_cover_date": "2025-11-17",
        "title": "TSA Total Throughput Data November 9, 2025 to November 15, 2025",
        "source_url": (
            "https://www.tsa.gov/sites/default/files/foia-readingroom/"
            "tsa-total-thoughput-data-november-9-2025-to-november-15-2025.pdf"
        ),
        "official_filename_caveat": "URL spells throughput as thoughput",
    },
]
ACTIVE_BASELINE_METRICS = {
    "expected_value_score": 6.2057,
    "total_pnl": 130_992.36,
    "trade_count": 49,
    "max_drawdown_pct": 0.0889,
    "survival_rate": 0.8116,
    "strategy_total_return_pct": 0.4366,
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _int_token(value: Any) -> int | None:
    text = str(value or "").replace(",", "").strip()
    return int(text) if text.isdigit() else None


def _pdf_metadata_date(value: Any) -> str | None:
    match = PDF_META_DATE_RE.search(str(value or ""))
    if match is None:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()


def _parse_transition_table(page: fitz.Page) -> tuple[dict[str, int], int]:
    candidates = []
    for table in page.find_tables().tables:
        rows = table.extract()
        if rows and len(rows[0]) >= 8 and "Date" in str(rows[0][0]):
            candidates.append(rows)
    if len(candidates) != 1:
        raise RuntimeError(f"expected one throughput table, got {len(candidates)}")
    totals: Counter[str] = Counter()
    current_date: str | None = None
    row_count = 0
    for row in candidates[0][1:]:
        if not row:
            continue
        candidate_date = str(row[0] or "").replace("\n", "").strip()
        if DATE_TOKEN_RE.fullmatch(candidate_date):
            current_date = candidate_date
        total = _int_token(row[-1])
        if total is None:
            continue
        if current_date is None:
            raise RuntimeError("numeric throughput row preceded its date")
        totals[current_date] += total
        row_count += 1
    if not totals:
        raise RuntimeError("transition page yielded no throughput rows")
    return dict(totals), row_count


def parse_weekly_pdf(payload: bytes) -> dict[str, Any]:
    """Extract report totals with a word-coordinate fast path and table fallback."""

    document = fitz.open(stream=payload, filetype="pdf")
    daily_totals: Counter[str] = Counter()
    cover_dates: set[str] = set()
    transition_pages: list[int] = []
    row_count = 0
    for page_index, page in enumerate(document):
        words = page.get_text("words")
        table_dates = []
        totals = []
        for x0, y0, _x1, _y1, token, *_rest in words:
            token = str(token).strip()
            if 250 <= x0 <= 350 and y0 < 120 and DATE_TOKEN_RE.fullmatch(token):
                cover_dates.add(token)
            if 40 <= x0 <= 100 and DATE_TOKEN_RE.fullmatch(token):
                table_dates.append(token)
            if x0 > 430 and INTEGER_TOKEN_RE.fullmatch(token):
                value = _int_token(token)
                if value is not None:
                    totals.append(value)
        distinct_dates = list(dict.fromkeys(table_dates))
        if len(distinct_dates) == 1:
            if not totals:
                raise RuntimeError(f"page {page_index + 1} has no throughput values")
            daily_totals[distinct_dates[0]] += sum(totals)
            row_count += len(totals)
        elif len(distinct_dates) > 1:
            transition_pages.append(page_index + 1)
            transition, transition_rows = _parse_transition_table(page)
            daily_totals.update(transition)
            row_count += transition_rows
        else:
            raise RuntimeError(f"page {page_index + 1} has no table date")

    metadata = dict(document.metadata or {})
    if len(cover_dates) != 1:
        raise RuntimeError(f"expected one cover date, got {sorted(cover_dates)}")
    return {
        "sha256": _sha256(payload),
        "bytes": len(payload),
        "pages": document.page_count,
        "row_count": row_count,
        "transition_pages": transition_pages,
        "cover_date": next(iter(cover_dates)),
        "creation_date": _pdf_metadata_date(metadata.get("creationDate")),
        "modification_date": _pdf_metadata_date(metadata.get("modDate")),
        "creator": metadata.get("creator"),
        "producer": metadata.get("producer"),
        "daily_totals": dict(sorted(daily_totals.items())),
        "weekly_total": sum(daily_totals.values()),
    }


def parse_annual_table(payload: bytes) -> dict[str, int]:
    text = html.unescape(payload.decode("utf-8", errors="replace"))
    # Drupal serialises the static table inside escaped JSON in this response.
    decoded = (
        text.replace(r"\u003C", "<")
        .replace(r"\u003E", ">")
        .replace(r"\u0022", '"')
        .replace(r"\u0026", "&")
        .replace(r"\/", "/")
        .replace(r'\"', '"')
    )
    pairs = re.findall(
        r"(\d{1,2}/\d{1,2}/\d{4})</td><td[^>]*>([\d,]+)</td>", decoded
    )
    values = {day: int(value.replace(",", "")) for day, value in pairs}
    if len(values) < 300:
        raise RuntimeError(f"annual TSA table parsed only {len(values)} rows")
    return values


def enumerate_reading_room(session: requests.Session) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reports: dict[tuple[date, date], dict[str, Any]] = {}
    index_pages = []
    for page in range(50):
        url = READING_ROOM_URL.format(page=page)
        response = session.get(url, timeout=60)
        response.raise_for_status()
        index_pages.append(
            {"page": page, "url": url, "bytes": len(response.content), "sha256": _sha256(response.content)}
        )
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a[href]"):
            href = str(anchor.get("href") or "")
            if not href.endswith(".pdf"):
                continue
            title = " ".join(anchor.get_text(" ", strip=True).replace("\xa0", " ").split())
            match = PERIOD_RE.search(title)
            if match is None:
                continue
            start = datetime.strptime(match.group(1), "%B %d, %Y").date()
            end = datetime.strptime(match.group(2), "%B %d, %Y").date()
            source_url = href if href.startswith("https://") else "https://www.tsa.gov" + href
            reports[(start, end)] = {
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "conservative_cover_date": (end + timedelta(days=2)).isoformat(),
                "title": title,
                "source_url": source_url,
            }
    return [reports[key] for key in sorted(reports)], index_pages


def _window_structure(reports: list[dict[str, Any]]) -> dict[str, Any]:
    period_ends = {date.fromisoformat(row["period_end"]) for row in reports}
    result = {}
    for name, (start, end) in WINDOWS.items():
        selected = [
            row
            for row in reports
            if start <= date.fromisoformat(row["conservative_cover_date"]) <= end
        ]
        selected_ends = {date.fromisoformat(row["period_end"]) for row in selected}
        structure_ready = sorted(
            day
            for day in selected_ends
            if day - timedelta(days=7) in period_ends
            and day - timedelta(days=364) in period_ends
            and day - timedelta(days=371) in period_ends
        )
        result[name] = {
            "declared_preflight_report_count": DECLARED_PREFLIGHT_REPORT_COUNTS[name],
            "indexed_report_count": len(selected),
            "raw_pdf_structure_ready_count": len(structure_ready),
            "raw_pdf_structure_ready_period_ends": [day.isoformat() for day in structure_ready],
            "indexed_reports": selected,
        }
    return result


def _http_date(value: str | None) -> str | None:
    if not value:
        return None
    parsed = email.utils.parsedate_to_datetime(value)
    return parsed.date().isoformat()


def _raw_manifest(indexed_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_period = {
        (row["period_start"], row["period_end"]): dict(row)
        for row in indexed_reports
        if RAW_MANIFEST_START <= date.fromisoformat(row["period_start"]) <= RAW_MANIFEST_END
    }
    for row in MANIFEST_EXCEPTIONS:
        by_period[(row["period_start"], row["period_end"])] = dict(row)
    return [by_period[key] for key in sorted(by_period)]


def _download_and_parse_raw_report(row: dict[str, Any]) -> dict[str, Any]:
    response: requests.Response | None = None
    last_error = "not_attempted"
    for attempt in range(3):
        try:
            response = requests.get(
                row["source_url"],
                timeout=180,
                headers={"User-Agent": "ginger-alpha-research/1.0"},
            )
            if response.status_code == 200 and response.content.startswith(b"%PDF"):
                break
            last_error = f"http_{response.status_code}:{response.headers.get('Content-Type')}"
        except requests.RequestException as error:
            last_error = type(error).__name__
        time.sleep(1 + attempt * 2)
    if response is None or response.status_code != 200 or not response.content.startswith(b"%PDF"):
        raise RuntimeError(last_error)

    parsed = parse_weekly_pdf(response.content)
    parsed_dates = sorted(
        datetime.strptime(day, "%m/%d/%Y").date() for day in parsed["daily_totals"]
    )
    expected_start = date.fromisoformat(row["period_start"])
    expected_end = date.fromisoformat(row["period_end"])
    if parsed_dates[0] != expected_start or parsed_dates[-1] != expected_end:
        raise RuntimeError(
            f"period_mismatch:{parsed_dates[0]}:{parsed_dates[-1]}:"
            f"{expected_start}:{expected_end}"
        )
    cover_date = datetime.strptime(parsed["cover_date"], "%m/%d/%Y").date().isoformat()
    http_last_modified = response.headers.get("Last-Modified")
    http_last_modified_date = _http_date(http_last_modified)
    availability_candidates = [
        value
        for value in (
            cover_date,
            parsed.get("creation_date"),
            parsed.get("modification_date"),
            http_last_modified_date,
        )
        if value
    ]
    knowledge_date = max(availability_candidates)
    return {
        **row,
        "report_date": cover_date,
        "knowledge_date": knowledge_date,
        "week_ending": expected_end.isoformat(),
        "weekly_total": parsed["weekly_total"],
        "source_sha256": parsed["sha256"],
        "source_bytes": parsed["bytes"],
        "source_pages": parsed["pages"],
        "source_row_count": parsed["row_count"],
        "source_transition_pages": parsed["transition_pages"],
        "pdf_creation_date": parsed.get("creation_date"),
        "pdf_modification_date": parsed.get("modification_date"),
        "http_last_modified": http_last_modified,
        "http_last_modified_date": http_last_modified_date,
        "http_etag": response.headers.get("ETag"),
        "is_report": True,
        "late_versioned_after_cover": knowledge_date > cover_date,
    }


def _run_raw_pdf_source_audit(indexed_reports: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = _raw_manifest(indexed_reports)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_download_and_parse_raw_report, row): row for row in manifest
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            completed += 1
            try:
                records.append(future.result())
            except Exception as error:  # fail closed and preserve exact URL
                errors.append(
                    {
                        "period_start": row["period_start"],
                        "period_end": row["period_end"],
                        "source_url": row["source_url"],
                        "error": f"{type(error).__name__}:{error}",
                    }
                )
            if completed % 10 == 0 or completed == len(manifest):
                print(
                    f"raw_pdf_audit {completed}/{len(manifest)} "
                    f"parsed={len(records)} errors={len(errors)}",
                    flush=True,
                )
    records.sort(key=lambda row: (row["week_ending"], row["source_url"]))
    evaluations, evaluation_audit = evaluate_tsa_checkpoint_throughput_events(records)
    window_counts = {}
    for name, (start, end) in WINDOWS.items():
        rows = [
            row
            for row in evaluations
            if start <= date.fromisoformat(row["report_date"]) <= end
        ]
        triggered = [row for row in rows if row["triggered"]]
        timely = [
            row
            for row in triggered
            if row["knowledge_date"] == row["report_date"]
        ]
        window_counts[name] = {
            "report_count": len(rows),
            "event_ready_count": sum(bool(row["event_ready"]) for row in rows),
            "locked_signal_count": len(triggered),
            "timely_locked_signal_count": len(timely),
            "timely_independent_knowledge_dates": len(
                {row["knowledge_date"] for row in timely}
            ),
            "late_signal_count": len(triggered) - len(timely),
            "timely_signal_week_endings": [row["week_ending"] for row in timely],
            "late_signal_week_endings": [
                row["week_ending"]
                for row in triggered
                if row["knowledge_date"] != row["report_date"]
            ],
        }
    sample_gate_passed = not errors and evaluation_audit["measurement_valid"] and all(
        row["timely_locked_signal_count"] >= 10
        and row["timely_independent_knowledge_dates"] >= 10
        for row in window_counts.values()
    )
    return {
        "manifest_start": RAW_MANIFEST_START.isoformat(),
        "manifest_end": RAW_MANIFEST_END.isoformat(),
        "manifest_count": len(manifest),
        "parsed_count": len(records),
        "error_count": len(errors),
        "errors": errors,
        "records": records,
        "records_sha256": hashlib.sha256(
            json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "evaluation_audit": evaluation_audit,
        "window_counts": window_counts,
        "minimum_sample_gate_passed": sample_gate_passed,
        "late_discovery_rule": (
            "A weekly report whose conservative knowledge date is after its cover "
            "date is missed, not retroactively entered."
        ),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": "ginger-alpha-research/1.0"})

    sentinel_response = session.get(SENTINEL_PDF_URL, timeout=120)
    sentinel_response.raise_for_status()
    sentinel = parse_weekly_pdf(sentinel_response.content)
    annual_response = session.get(ANNUAL_2025_URL, timeout=60)
    annual_response.raise_for_status()
    annual_values = parse_annual_table(annual_response.content)
    comparator_response = session.get(CORRUPTED_COMPARATOR_PDF_URL, timeout=120)
    comparator_response.raise_for_status()
    comparator_parse_error = None
    comparator_parsed = None
    try:
        comparator_parsed = parse_weekly_pdf(comparator_response.content)
    except Exception as error:
        comparator_parse_error = f"{type(error).__name__}:{error}"

    comparisons = []
    for day, pdf_value in sentinel["daily_totals"].items():
        annual_value = annual_values.get(day)
        comparisons.append(
            {
                "date": day,
                "weekly_pdf_total": pdf_value,
                "current_annual_table_total": annual_value,
                "delta": None if annual_value is None else annual_value - pdf_value,
                "equal": annual_value == pdf_value,
            }
        )
    annual_weekly_total = sum(int(row["current_annual_table_total"]) for row in comparisons)
    indexed_reports, index_pages = enumerate_reading_room(session)
    window_structure = _window_structure(indexed_reports)

    cover_date = datetime.strptime(sentinel["cover_date"], "%m/%d/%Y").date()
    modification_date = (
        date.fromisoformat(sentinel["modification_date"])
        if sentinel["modification_date"]
        else None
    )
    report_counts_match = all(
        window_structure[name]["indexed_report_count"] == expected
        for name, expected in DECLARED_PREFLIGHT_REPORT_COUNTS.items()
    )
    daily_values_match = all(bool(row["equal"]) for row in comparisons)
    post_cover_modification = bool(modification_date and modification_date > cover_date)
    failure_reasons = []
    if not daily_values_match:
        failure_reasons.append("current_annual_table_differs_from_hash_bound_weekly_pdf")
    if post_cover_modification:
        failure_reasons.append("weekly_pdf_modification_date_is_after_cover_date")
    if comparator_parse_error:
        failure_reasons.append("exact_364_day_raw_pdf_comparator_is_unparseable")
    preflight_warnings = []
    if not report_counts_match:
        preflight_warnings.append("reading_room_index_requires_filename_exception_manifest")
    source_contract_passed = False
    decision = "rejected_before_price_read"

    result = {
        "experiment_id": EXPERIMENT_ID,
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "hypothesis": (
            "Positive TSA weekly passenger-throughput YoY with positive acceleration "
            "predicts five-session continuation in a fixed 14-name travel basket."
        ),
        "policy_locked": True,
        "price_or_return_data_read": False,
        "decision": decision,
        "pit_source_contract_passed": source_contract_passed,
        "failure_reasons": failure_reasons,
        "preflight_warnings": preflight_warnings,
        "sentinel": {
            "source_url": SENTINEL_PDF_URL,
            **sentinel,
            "http_last_modified": sentinel_response.headers.get("Last-Modified"),
            "http_etag": sentinel_response.headers.get("ETag"),
        },
        "annual_table": {
            "source_url": ANNUAL_2025_URL,
            "sha256": _sha256(annual_response.content),
            "bytes": len(annual_response.content),
            "parsed_row_count": len(annual_values),
            "sentinel_week_total": annual_weekly_total,
        },
        "sentinel_comparison": {
            "rows": comparisons,
            "weekly_pdf_total": sentinel["weekly_total"],
            "current_annual_table_total": annual_weekly_total,
            "delta": annual_weekly_total - sentinel["weekly_total"],
            "delta_pct_of_pdf": round(
                annual_weekly_total / sentinel["weekly_total"] - 1.0, 8
            ),
            "all_daily_values_equal": daily_values_match,
        },
        "raw_pdf_comparator_sentinel": {
            "period_start": "2023-09-24",
            "period_end": "2023-09-30",
            "source_url": CORRUPTED_COMPARATOR_PDF_URL,
            "sha256": _sha256(comparator_response.content),
            "bytes": len(comparator_response.content),
            "http_last_modified": comparator_response.headers.get("Last-Modified"),
            "http_etag": comparator_response.headers.get("ETag"),
            "parse_error": comparator_parse_error,
            "parsed": comparator_parsed,
            "official_foia_log_context": (
                "TSA FY23 Q3/Q4 and FY24 Q1 FOIA log records request "
                "2024-TSFO-00003 reporting this exact weekly PDF as corrupted."
            ),
        },
        "reading_room": {
            "query_template": READING_ROOM_URL,
            "index_page_count": len(index_pages),
            "index_pages": index_pages,
            "parsed_report_count": len(indexed_reports),
            "window_structure": window_structure,
            "filename_exception_manifest": MANIFEST_EXCEPTIONS,
        },
        "reopen_condition": (
            "Reopen only when an authorized immutable/versioned TSA weekly release "
            "archive supplies publication timestamps and original bytes for enough "
            "current, preceding-week, and exact-364-day reports to yield >=10 locked "
            "signal events in every canonical window; the mutable annual table and "
            "current post-modified PDFs do not qualify."
        ),
        "production_impact": {
            "shared_helper_retained_for_reproducibility": True,
            "daily_wiring_added": False,
            "live_or_default_behavior_changed": False,
            "orders_created": False,
        },
    }

    _write_json(SOURCE_DIR / "preflight.json", result)
    _write_json(EXPERIMENT_DIR / "preflight.json", result)
    before = {
        **ACTIVE_BASELINE_METRICS,
        "benchmarks": {
            "strategy_total_return_pct": ACTIVE_BASELINE_METRICS[
                "strategy_total_return_pct"
            ]
        },
        "total_trades": ACTIVE_BASELINE_METRICS["trade_count"],
        "artifact": "before",
        "experiment_id": EXPERIMENT_ID,
        "source": "active cash-feasible Gate-1 anchor exp-20260715-010",
    }
    after = {
        **ACTIVE_BASELINE_METRICS,
        "benchmarks": {
            "strategy_total_return_pct": ACTIVE_BASELINE_METRICS[
                "strategy_total_return_pct"
            ]
        },
        "total_trades": ACTIVE_BASELINE_METRICS["trade_count"],
        "artifact": "after_not_measured",
        "experiment_id": EXPERIMENT_ID,
        "source_contract_valid": False,
        "price_or_return_data_read": False,
        "note": "No strategy measurement was run after the PIT source contract failed.",
    }
    _write_json(EXPERIMENT_DIR / "before.json", before)
    _write_json(EXPERIMENT_DIR / "after.json", after)

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        "\n".join(
            [
                f"# {EXPERIMENT_ID}: TSA checkpoint throughput PIT preflight",
                "",
                "## Decision",
                "",
                "Rejected before any price or return data was read.",
                "",
                "## Machine-checked evidence",
                "",
                f"- Hash-bound FOIA PDF weekly total: {sentinel['weekly_total']:,}.",
                f"- Current TSA annual-table total for the same dates: {annual_weekly_total:,}.",
                f"- Difference: {annual_weekly_total - sentinel['weekly_total']:,} "
                f"({(annual_weekly_total / sentinel['weekly_total'] - 1.0) * 100:.3f}%).",
                f"- PDF cover date: {cover_date.isoformat()}; metadata modification date: "
                f"{sentinel['modification_date']}.",
                "- Reading-room indexed / raw-structure-ready counts: "
                + ", ".join(
                    f"{name}={row['indexed_report_count']}/{row['raw_pdf_structure_ready_count']}"
                    for name, row in window_structure.items()
                )
                + ".",
                f"- Exact-364-day comparator sentinel parse: {comparator_parse_error}.",
                "- Four late-window filename exceptions are official but were "
                "batch-modified on 2025-11-17, so stale reports are missed rather "
                "than retroactively entered.",
                "- OHLCV and returns read: no.",
                "",
                "## Reopen condition",
                "",
                result["reopen_condition"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": result["decision"],
        "failure_reasons": failure_reasons,
        "preflight_warnings": preflight_warnings,
        "sentinel_pdf_total": sentinel["weekly_total"],
        "annual_table_total": annual_weekly_total,
        "window_counts": {
            name: {
                "indexed": row["indexed_report_count"],
                "structure_ready": row["raw_pdf_structure_ready_count"],
            }
            for name, row in window_structure.items()
        },
        "comparator_parse_error": comparator_parse_error,
    }, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    run()
