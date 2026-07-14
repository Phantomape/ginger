"""exp-20260714-003: FDIC Call Report deposit-franchise repair ranking.

This shared-paper-first experiment freezes the current FDIC active-institution
mapping and current-vintage quarterly Financials API rows before replay.  The
only selection implementation lives in
``fdic_call_report_deposit_repair_paper_sleeve``: this runner is a source,
OHLCV, Gate 1-5, comparator, and artifact adapter.

The historical parent map is intentionally conservative but imperfect: an
exact current SEC issuer title is joined to the current FDIC top-holder name,
then current active certificates are carried backward.  The result therefore
retains explicit current-mapping and current-vintage revision caveats.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for import_path in (REPO_ROOT, REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from deflated_sharpe import build_report as build_dsr_report  # noqa: E402
from fdic_call_report_deposit_repair_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    QBP_RELEASE_DATES,
    ROUND_TRIP_COST_PCT,
    RULE_VERSION,
    build_fdic_call_report_deposit_repair_paper_sleeve_snapshot,
    replay_fdic_call_report_deposit_repair_paper_trades,
)
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)
from quant.experiments.exp_20260713_008_clinicaltrials_phase3_results_green_spy_relative_top1_10d_v1 import (  # noqa: E402
    _target_summary,
    combine_window,
)


EXPERIMENT_ID = "exp-20260714-003"
OWNER = "alpha-explore"
TRIAL_FAMILY = "fdic_qbp_deposit_franchise_repair_candidate_pool"
TRIAL_VARIANT_ID = "coredep_growth_uninsured_share_improvement_top5_20d_v1"
CHANGED_VARIABLE = "fdic_deposit_franchise_repair_quarterly_ranking"

FDIC_API_BASE = "https://api.fdic.gov/banks"
FDIC_API_DOCS = "https://api.fdic.gov/banks/docs"
FDIC_QBP_INDEX = "https://www.fdic.gov/quarterly-banking-profile"
QBP_STATEMENT_URLS = {
    "2024-09-30": "https://www.fdic.gov/news/speeches/2024/quarterly-banking-profile-third-quarter-2024",
    "2024-12-31": "https://www.fdic.gov/news/speeches/2025/fdic-quarterly-banking-profile-fourth-quarter-2024",
    "2025-03-31": "https://www.fdic.gov/news/speeches/2025/fdic-quarterly-banking-profile-first-quarter-2025",
    "2025-06-30": "https://www.fdic.gov/news/speeches/2025/fdic-quarterly-banking-profile-second-quarter-2025",
    "2025-09-30": "https://www.fdic.gov/news/speeches/2025/fdic-quarterly-banking-profile-third-quarter-2025",
    "2025-12-31": "https://www.fdic.gov/news/speeches/2026/fdic-quarterly-banking-profile-fourth-quarter-2025",
}
SEC_REFERENCE = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_SUMMARY = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)

SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "fdic_call_reports"
INSTITUTIONS_PATH = SOURCE_DIR / "active_institutions_current.json"
FINANCIALS_PATH = SOURCE_DIR / "financials_2023q3_2025q4_current_vintage.json"
PARENT_MAP_PATH = SOURCE_DIR / "sec_exact_parent_map_current.json"
QBP_DATES_PATH = SOURCE_DIR / "official_qbp_release_dates.json"
RECORDS_PATH = SOURCE_DIR / "canonical_records.json"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
AUX_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "fdic_call_report_deposit_repair_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
DSR_PANEL_PATH = OUT_DIR / "deflated_sharpe_panel.json"
DSR_REPORT_PATH = OUT_DIR / "deflated_sharpe_report.json"
PAPER_DIR = REPO_ROOT / "data" / "paper_sleeves" / "fdic_call_report_deposit_repair"
PAPER_SNAPSHOT_PATH = PAPER_DIR / "latest_snapshot.json"
ARTIFACT_PATH = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_fdic_call_report_deposit_repair.md"
)

WINDOWS = OrderedDict(
    (
        ("late_strong", ("2025-10-23", "2026-04-21")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("old_thin", ("2024-10-02", "2025-04-22")),
    )
)
REPORT_DATES = (
    "2023-09-30",
    "2023-12-31",
    "2024-03-31",
    "2024-06-30",
    "2024-09-30",
    "2024-12-31",
    "2025-03-31",
    "2025-06-30",
    "2025-09-30",
    "2025-12-31",
)
SIGNAL_REPORT_DATES = REPORT_DATES[4:]
BENCHMARKS = ("CASH", "SPY", "QQQ", "XLF", "KBE")
PAPER_SNAPSHOT_AS_OF = "2026-07-13"
SOURCE_FIELDS_INSTITUTIONS = (
    "ACTIVE,CERT,NAME,NAMEHCR,RSSDHCR,RSSDID,ASSET,REPDTE"
)
SOURCE_FIELDS_FINANCIALS = (
    "CERT,REPDTE,ASSET,COREDEP,DEPUNINS,DEPDOM,NAME,NAMEHCR,RSSDHCR"
)
API_PAGE_LIMIT = 10_000
EXPECTED_DSR_ATTEMPTS = 1
MAX_DRAWDOWN_WORSE = 0.005
DERIVED_SOURCE_SCHEMA_VERSION = 2
ACCEPTED_CANDIDATE_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10_432.91,
}
CALCULATION_FILES = OrderedDict(
    (
        (
            "runner",
            REPO_ROOT
            / "quant"
            / "experiments"
            / "exp_20260714_003_fdic_call_report_deposit_repair.py",
        ),
        (
            "shared_selection_helper",
            REPO_ROOT / "quant" / "fdic_call_report_deposit_repair_paper_sleeve.py",
        ),
        (
            "combine_window_owner",
            REPO_ROOT
            / "quant"
            / "experiments"
            / "exp_20260713_008_clinicaltrials_phase3_results_green_spy_relative_top1_10d_v1.py",
        ),
        (
            "full_stack_candidate_pool",
            REPO_ROOT / "quant" / "full_stack_candidate_pool.py",
        ),
        ("evaluator_gates", REPO_ROOT / "quant" / "evaluator_gates.py"),
        ("sharpe_inference", REPO_ROOT / "quant" / "sharpe_inference.py"),
        ("deflated_sharpe_adapter", REPO_ROOT / "scripts" / "deflated_sharpe.py"),
    )
)

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1200.0,
    "main_failure_modes": [
        "quarter_cluster_effective_sample_too_small",
        "current_vintage_revision_bias",
        "parent_mapping_survivorship",
        "merger_contamination",
        "bank_beta_not_incremental",
        "window_regression",
        "comparator_not_beaten",
        "concentration_failed",
    ],
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _canonical_sha(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _return_series_sha(rows: list[dict[str, Any]]) -> str:
    return _canonical_sha(
        {"schema": "dated_periodic_return_series_v1", "rows": rows}
    )


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _calculation_identity(auxiliary: dict[str, Any]) -> dict[str, Any]:
    missing = [str(path) for path in CALCULATION_FILES.values() if not path.exists()]
    if missing:
        raise RuntimeError(f"calculation dependency missing: {missing}")
    if not AUX_OHLCV_PATH.exists():
        raise RuntimeError("frozen auxiliary OHLCV missing from calculation identity")
    return {
        "schema": "fdic_deposit_repair_calculation_identity_v1",
        "code_files": {
            label: {"path": _repo_rel(path), "sha256": _file_sha(path)}
            for label, path in CALCULATION_FILES.items()
        },
        "frozen_auxiliary_ohlcv": {
            "path": _repo_rel(AUX_OHLCV_PATH),
            "file_sha256": _file_sha(AUX_OHLCV_PATH),
            "rowset_sha256": auxiliary["rowset_sha256"],
            "source_at_freeze": auxiliary.get("source_at_freeze"),
        },
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso_report_date(value: Any) -> str | None:
    text = str(value or "").strip().replace("/", "").replace("-", "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _quarter(report_date: str) -> str:
    date = datetime.strptime(report_date, "%Y-%m-%d").date()
    return f"{date.year}Q{(date.month - 1) // 3 + 1}"


def _normalized_qbp_dates() -> dict[str, str]:
    output: dict[str, str] = {}
    report_date_by_quarter = {_quarter(day): day for day in REPORT_DATES}
    for raw_report, raw_release in dict(QBP_RELEASE_DATES).items():
        raw_key = str(raw_report).strip().upper()
        report = report_date_by_quarter.get(raw_key) or _iso_report_date(raw_report)
        release_value = raw_release
        if isinstance(raw_release, dict):
            release_value = (
                raw_release.get("release_date")
                or raw_release.get("availability_date")
                or raw_release.get("date")
            )
        release = _iso_report_date(release_value)
        if report and release:
            output[report] = release
    missing = sorted(set(SIGNAL_REPORT_DATES) - set(output))
    if missing:
        raise RuntimeError(f"shared helper QBP release dates missing: {missing}")
    return {date: output[date] for date in SIGNAL_REPORT_DATES}


def _fetch_paged(
    endpoint: str,
    *,
    filters: str,
    fields: str,
    sort_by: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    page_meta: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None
    request_urls: list[str] = []
    while total is None or offset < total:
        params = {
            "filters": filters,
            "fields": fields,
            "limit": API_PAGE_LIMIT,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": "ASC",
            "format": "json",
        }
        url = f"{FDIC_API_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "ginger-exp-20260714-003/1.0"},
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError(f"FDIC {endpoint} response contract changed")
        page_rows = [
            dict(item.get("data") or {})
            for item in payload["data"]
            if isinstance(item, dict) and isinstance(item.get("data"), dict)
        ]
        meta = dict(payload.get("meta") or {})
        reported_total = meta.get("total")
        if total is None:
            total = int(reported_total)
        elif reported_total is not None and int(reported_total) != total:
            raise RuntimeError(f"FDIC {endpoint} total changed during pagination")
        rows.extend(page_rows)
        request_urls.append(url)
        page_meta.append(
            {
                "offset": offset,
                "row_count": len(page_rows),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "index": meta.get("index"),
            }
        )
        if not page_rows:
            break
        offset += len(page_rows)
    if total is None or len(rows) != total:
        raise RuntimeError(
            f"FDIC {endpoint} pagination incomplete: expected={total}, got={len(rows)}"
        )
    return {
        "schema": "fdic_bankfind_api_frozen_rows_v1",
        "endpoint": endpoint,
        "filters": filters,
        "fields": fields.split(","),
        "sort_by": sort_by,
        "request_urls": request_urls,
        "page_meta": page_meta,
        "row_count": len(rows),
        "rows": rows,
    }


def _first_exact_sec_titles() -> tuple[dict[str, dict[str, Any]], str]:
    payload = _read_json(SEC_REFERENCE)
    if not isinstance(payload, dict):
        raise RuntimeError("SEC company ticker reference must be an object")
    first: dict[str, dict[str, Any]] = {}
    for row in payload.values():
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip().upper()
        ticker = str(row.get("ticker") or "").strip().upper()
        if title and ticker and title not in first:
            first[title] = {
                "sec_title": title,
                "ticker": ticker,
                "cik": int(row["cik_str"]),
            }
    return first, _file_sha(SEC_REFERENCE)


def _build_parent_map(institution_rows: list[dict[str, Any]]) -> dict[str, Any]:
    sec_by_title, sec_sha = _first_exact_sec_titles()
    banks_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in institution_rows:
        parent = str(row.get("NAMEHCR") or "").strip().upper()
        if parent:
            banks_by_parent[parent].append(row)
    matches: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    missing_group_id: list[str] = []
    for parent in sorted(set(banks_by_parent) & set(sec_by_title)):
        sec = sec_by_title[parent]
        banks = sorted(
            banks_by_parent[parent], key=lambda row: int(row.get("CERT") or 0)
        )
        group_ids = sorted(
            {
                str(row.get("RSSDHCR") or "").strip()
                for row in banks
                if str(row.get("RSSDHCR") or "").strip()
            }
        )
        if not group_ids:
            missing_group_id.append(parent)
            continue
        if len(group_ids) != 1:
            ambiguous.append(
                {
                    "fdic_parent_name": parent,
                    "ticker": sec["ticker"],
                    "current_rssdhcr": group_ids,
                    "current_active_certs": [int(row["CERT"]) for row in banks],
                }
            )
            continue
        matches.append(
            {
                **sec,
                "fdic_parent_name": parent,
                "parent_group_id": group_ids[0],
                "current_rssdhcr": group_ids,
                "current_active_certs": [
                    int(row["CERT"])
                    for row in banks
                    if str(row.get("RSSDHCR") or "").strip() == group_ids[0]
                ],
                "current_active_bank_names": [
                    str(row.get("NAME") or "")
                    for row in banks
                    if str(row.get("RSSDHCR") or "").strip() == group_ids[0]
                ],
            }
        )
    return {
        "schema": "fdic_sec_exact_current_parent_map_v1",
        "mapping_method": (
            "uppercase-trimmed exact equality of current FDIC NAMEHCR and current "
            "SEC title; first SEC JSON row for that exact title is the frozen ticker"
        ),
        "no_fuzzy_aliases": True,
        "current_mapping_survivorship_caveat": True,
        "unique_nonblank_rssdhcr_required": True,
        "parent_group_asset_denominator": (
            "sum of historical ASSET for certificates that are current-active "
            "members of the one frozen RSSDHCR; not consolidated parent assets"
        ),
        "sec_reference_path": _repo_rel(SEC_REFERENCE),
        "sec_reference_sha256": sec_sha,
        "exact_parent_count": len(matches),
        "ambiguous_parent_count": len(ambiguous),
        "ambiguous_parents": ambiguous,
        "missing_group_id_parent_count": len(missing_group_id),
        "missing_group_id_parents": missing_group_id,
        "matches": matches,
    }


def _build_canonical_records(
    institutions: list[dict[str, Any]],
    financials: list[dict[str, Any]],
    parent_map: dict[str, Any],
) -> dict[str, Any]:
    match_by_parent = {
        str(row["fdic_parent_name"]): row for row in parent_map["matches"]
    }
    current_by_cert: dict[int, dict[str, Any]] = {}
    for row in institutions:
        parent = str(row.get("NAMEHCR") or "").strip().upper()
        cert = int(row.get("CERT") or 0)
        if cert and parent in match_by_parent:
            frozen_group = str(match_by_parent[parent]["parent_group_id"])
            current_group = str(row.get("RSSDHCR") or "").strip()
            if current_group != frozen_group:
                continue
            current_by_cert[cert] = {
                "parent": parent,
                "rssdhcr": frozen_group,
                "bank_name": str(row.get("NAME") or "").strip(),
            }
    relevant: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for row in financials:
        cert = int(row.get("CERT") or 0)
        report_date = _iso_report_date(row.get("REPDTE"))
        current = current_by_cert.get(cert)
        if current and report_date in REPORT_DATES:
            relevant.append((row, current, report_date))
    group_assets: dict[tuple[str, str], float] = defaultdict(float)
    for row, current, report_date in relevant:
        assets = _number(row.get("ASSET"))
        if assets is not None:
            group_key = current["rssdhcr"] or current["parent"]
            group_assets[(group_key, report_date)] += assets
    records: list[dict[str, Any]] = []
    missing_required = Counter()
    for row, current, report_date in relevant:
        parent = current["parent"]
        sec = match_by_parent[parent]
        group_key = current["rssdhcr"] or parent
        values = {
            "bank_assets_thousands": _number(row.get("ASSET")),
            "core_deposits_thousands": _number(row.get("COREDEP")),
            "uninsured_deposits_thousands": _number(row.get("DEPUNINS")),
            "domestic_deposits_thousands": _number(row.get("DEPDOM")),
        }
        for field, value in values.items():
            if value is None:
                missing_required[field] += 1
        records.append(
            {
                "quarter": _quarter(report_date),
                "report_date": report_date,
                "ticker": sec["ticker"],
                "bank_id": str(int(row["CERT"])),
                "CERT": int(row["CERT"]),
                "bank_name": str(row.get("NAME") or current["bank_name"]),
                "NAME": str(row.get("NAME") or current["bank_name"]),
                "ASSET": values["bank_assets_thousands"],
                "COREDEP": values["core_deposits_thousands"],
                "DEPUNINS": values["uninsured_deposits_thousands"],
                "DEPDOM": values["domestic_deposits_thousands"],
                **values,
                "parent_group_assets_thousands": group_assets.get(
                    (group_key, report_date)
                ),
                "parent_group_id": group_key,
                "fdic_parent_name": parent,
                "current_parent_rssd": current["rssdhcr"] or None,
                "sec_cik": sec["cik"],
                "source_record_id": str(row.get("ID") or f"{row['CERT']}_{report_date}"),
            }
        )
    records.sort(key=lambda row: (row["report_date"], row["ticker"], row["CERT"]))
    return {
        "schema": "fdic_call_report_deposit_repair_canonical_records_v1",
        "current_vintage_caveat": (
            "FDIC API rows are the snapshot retrieved for this experiment and can "
            "contain revisions filed after the original QBP release."
        ),
        "current_parent_mapping_caveat": (
            "Current active CERT-to-NAMEHCR/RSSDHCR membership is carried backward; "
            "historical mergers, divestitures, delistings, and parent changes are not "
            "reconstructed."
        ),
        "parent_group_asset_denominator": (
            "Historical quarter ASSET summed only across insured-bank CERTs that "
            "are active members of the unique current RSSDHCR snapshot. This is "
            "not consolidated holding-company assets and blocks live eligibility."
        ),
        "report_dates": list(REPORT_DATES),
        "record_count": len(records),
        "ticker_count": len({row["ticker"] for row in records}),
        "bank_count": len({row["CERT"] for row in records}),
        "missing_required_values": dict(sorted(missing_required.items())),
        "records": records,
    }


def _source_paths() -> tuple[Path, ...]:
    return (
        INSTITUTIONS_PATH,
        FINANCIALS_PATH,
        PARENT_MAP_PATH,
        QBP_DATES_PATH,
        RECORDS_PATH,
    )


def _validate_source_bundle() -> dict[str, Any]:
    if not SOURCE_MANIFEST_PATH.exists():
        raise FileNotFoundError(SOURCE_MANIFEST_PATH)
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    for path in _source_paths():
        row = (manifest.get("files") or {}).get(path.name) or {}
        if not path.exists() or row.get("sha256") != _file_sha(path):
            raise RuntimeError(f"frozen FDIC source hash mismatch: {path.name}")
    qbp = _read_json(QBP_DATES_PATH)
    if qbp.get("release_dates") != _normalized_qbp_dates():
        raise RuntimeError("frozen QBP release dates differ from shared helper")
    if qbp.get("statement_urls") != QBP_STATEMENT_URLS:
        raise RuntimeError("frozen QBP statement URL map is incomplete")
    return manifest


def _upgrade_frozen_qbp_provenance() -> None:
    """Add exact official statement URLs before any outcome evaluation.

    The first source-only freeze preceded the independent provenance review by
    minutes.  This deterministic migration changes no financial row, mapping,
    release date, policy, or outcome input; it only binds the six audited FDIC
    statement pages and updates that one file hash in the source manifest.
    """

    if not SOURCE_MANIFEST_PATH.exists() or not QBP_DATES_PATH.exists():
        return
    qbp = _read_json(QBP_DATES_PATH)
    if qbp.get("statement_urls") == QBP_STATEMENT_URLS:
        return
    qbp["statement_urls"] = dict(QBP_STATEMENT_URLS)
    qbp["statement_evidence"] = {
        report_date: {
            "release_date": _normalized_qbp_dates()[report_date],
            "url": url,
        }
        for report_date, url in QBP_STATEMENT_URLS.items()
    }
    qbp["provenance_note"] = (
        "Release dates were manually frozen from the exact official FDIC QBP "
        "statement pages listed here; the helper constant is the executable authority."
    )
    _write_json(QBP_DATES_PATH, qbp)
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    manifest["files"][QBP_DATES_PATH.name]["sha256"] = _file_sha(QBP_DATES_PATH)
    manifest["qbp_statement_pages"] = dict(QBP_STATEMENT_URLS)
    _write_json(SOURCE_MANIFEST_PATH, manifest)


def _upgrade_frozen_derived_sources() -> None:
    """Rebuild mapping/records from frozen raw API rows before outcomes.

    Version 2 rejects an exact NAMEHCR when its current active institutions
    point to zero or multiple nonblank RSSDHCR values and carries the unique
    ``parent_group_id`` into every canonical record.  No network access and no
    financial value mutation occurs here.
    """

    if not SOURCE_MANIFEST_PATH.exists():
        return
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    if manifest.get("derived_source_schema_version") == DERIVED_SOURCE_SCHEMA_VERSION:
        return
    institutions_payload = _read_json(INSTITUTIONS_PATH)
    financials_payload = _read_json(FINANCIALS_PATH)
    parent_map = _build_parent_map(list(institutions_payload["rows"]))
    canonical = _build_canonical_records(
        list(institutions_payload["rows"]),
        list(financials_payload["rows"]),
        parent_map,
    )
    retrieved_at = str(manifest["retrieved_at"])
    parent_map["retrieved_at"] = retrieved_at
    canonical["retrieved_at"] = retrieved_at
    _write_json(PARENT_MAP_PATH, parent_map)
    _write_json(RECORDS_PATH, canonical)
    for path in (PARENT_MAP_PATH, RECORDS_PATH):
        manifest["files"][path.name]["sha256"] = _file_sha(path)
    manifest["derived_source_schema_version"] = DERIVED_SOURCE_SCHEMA_VERSION
    manifest["parent_group_contract"] = {
        "unique_nonblank_rssdhcr_required": True,
        "ambiguous_parent_count": parent_map["ambiguous_parent_count"],
        "ambiguous_parent_names": [
            row["fdic_parent_name"] for row in parent_map["ambiguous_parents"]
        ],
        "missing_group_id_parent_count": parent_map[
            "missing_group_id_parent_count"
        ],
        "asset_denominator": parent_map["parent_group_asset_denominator"],
        "live_eligibility_blocked": True,
    }
    manifest["coverage"].update(
        {
            "exact_sec_parents": parent_map["exact_parent_count"],
            "ambiguous_exact_sec_parents_excluded": parent_map[
                "ambiguous_parent_count"
            ],
            "canonical_records": canonical["record_count"],
            "canonical_tickers": canonical["ticker_count"],
        }
    )
    _write_json(SOURCE_MANIFEST_PATH, manifest)


def materialize_source(*, offline: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if SOURCE_MANIFEST_PATH.exists():
        _upgrade_frozen_qbp_provenance()
        _upgrade_frozen_derived_sources()
        manifest = _validate_source_bundle()
        return list(_read_json(RECORDS_PATH)["records"]), manifest
    if offline:
        raise RuntimeError("offline mode requested before FDIC source was frozen")
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    institutions = _fetch_paged(
        "institutions",
        filters="ACTIVE:1",
        fields=SOURCE_FIELDS_INSTITUTIONS,
        sort_by="CERT",
    )
    financials = _fetch_paged(
        "financials",
        filters="REPDTE:[20230930 TO 20251231]",
        fields=SOURCE_FIELDS_FINANCIALS,
        sort_by="REPDTE",
    )
    parent_map = _build_parent_map(institutions["rows"])
    qbp = {
        "schema": "fdic_official_qbp_release_dates_v1",
        "release_dates": _normalized_qbp_dates(),
        "official_index_url": FDIC_QBP_INDEX,
        "statement_urls": dict(QBP_STATEMENT_URLS),
        "statement_evidence": {
            report_date: {
                "release_date": _normalized_qbp_dates()[report_date],
                "url": url,
            }
            for report_date, url in QBP_STATEMENT_URLS.items()
        },
        "provenance_note": (
            "Release dates were manually frozen from the exact official FDIC QBP "
            "statement pages listed here; the helper constant is the executable authority."
        ),
        "availability_rule": "exact official QBP release date; first strictly later market open",
    }
    canonical = _build_canonical_records(
        institutions["rows"], financials["rows"], parent_map
    )
    for payload in (institutions, financials, parent_map, qbp, canonical):
        payload["retrieved_at"] = retrieved_at
    for path, payload in (
        (INSTITUTIONS_PATH, institutions),
        (FINANCIALS_PATH, financials),
        (PARENT_MAP_PATH, parent_map),
        (QBP_DATES_PATH, qbp),
        (RECORDS_PATH, canonical),
    ):
        _write_json(path, payload)
    manifest = {
        "schema": "fdic_call_report_deposit_repair_source_manifest_v1",
        "experiment_id": EXPERIMENT_ID,
        "retrieved_at": retrieved_at,
        "official_api_docs": FDIC_API_DOCS,
        "current_vintage": True,
        "current_parent_mapping": True,
        "first_vintage_reconstructed": False,
        "derived_source_schema_version": DERIVED_SOURCE_SCHEMA_VERSION,
        "qbp_statement_pages": dict(QBP_STATEMENT_URLS),
        "parent_group_contract": {
            "unique_nonblank_rssdhcr_required": True,
            "ambiguous_parent_count": parent_map["ambiguous_parent_count"],
            "ambiguous_parent_names": [
                row["fdic_parent_name"] for row in parent_map["ambiguous_parents"]
            ],
            "missing_group_id_parent_count": parent_map[
                "missing_group_id_parent_count"
            ],
            "asset_denominator": parent_map["parent_group_asset_denominator"],
            "live_eligibility_blocked": True,
        },
        "files": {
            path.name: {"path": _repo_rel(path), "sha256": _file_sha(path)}
            for path in _source_paths()
        },
        "coverage": {
            "institution_rows": institutions["row_count"],
            "financial_rows": financials["row_count"],
            "exact_sec_parents": parent_map["exact_parent_count"],
            "ambiguous_exact_sec_parents_excluded": parent_map[
                "ambiguous_parent_count"
            ],
            "canonical_records": canonical["record_count"],
            "canonical_tickers": canonical["ticker_count"],
        },
    }
    _write_json(SOURCE_MANIFEST_PATH, manifest)
    return list(canonical["records"]), manifest


def _load_ohlcv(
    tickers: list[str], start: str, end: str
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if AUX_OHLCV_PATH.exists():
        payload = _read_json(AUX_OHLCV_PATH)
        rows = payload.get("ohlcv") or {}
        if payload.get("start") != start or payload.get("end") != end:
            raise RuntimeError("frozen auxiliary OHLCV range mismatch")
        if sorted(payload.get("tickers") or []) != sorted(tickers):
            raise RuntimeError("frozen auxiliary OHLCV ticker universe mismatch")
        if payload.get("rowset_sha256") != _canonical_sha(rows):
            raise RuntimeError("frozen auxiliary OHLCV hash mismatch")
        return rows, {
            "path": _repo_rel(AUX_OHLCV_PATH),
            "rowset_sha256": payload["rowset_sha256"],
            "source_at_freeze": payload.get("source_at_freeze"),
        }
    placeholders = ",".join("?" for _ in tickers)
    query = f"""
        SELECT ticker, date, open, high, low, close
        FROM ohlcv
        WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    output: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(str(WAREHOUSE)) as connection:
        for ticker, day, open_, high, low, close in connection.execute(
            query, [*tickers, start, end]
        ):
            output[str(ticker)].append(
                {
                    "date": str(day),
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                }
            )
    payload = {
        "schema": "fdic_call_report_deposit_repair_auxiliary_ohlcv_v1",
        "source_at_freeze": _repo_rel(WAREHOUSE),
        "start": start,
        "end": end,
        "tickers": tickers,
        "rowset_sha256": _canonical_sha(output),
        "ohlcv": output,
    }
    _write_json(AUX_OHLCV_PATH, payload)
    return output, {
        "path": _repo_rel(AUX_OHLCV_PATH),
        "rowset_sha256": payload["rowset_sha256"],
        "source_at_freeze": payload["source_at_freeze"],
    }


def _baseline_window_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): row for row in summary["windows"]}


def _window_ohlcv(
    broad: dict[str, list[dict[str, Any]]], baseline: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    snapshot_path = REPO_ROOT / baseline["source"]
    snapshot = (_read_json(snapshot_path).get("ohlcv") or {})
    output = {ticker: list(rows) for ticker, rows in broad.items()}
    exact: list[str] = []
    for ticker in sorted(output):
        if snapshot.get(ticker):
            output[ticker] = list(snapshot[ticker])
            exact.append(ticker)
    return output, {
        "gate1_snapshot": _repo_rel(snapshot_path),
        "exact_snapshot_tickers": exact,
        "auxiliary_fill_tickers": sorted(
            ticker for ticker, rows in output.items() if rows and ticker not in exact
        ),
        "missing_tickers": sorted(ticker for ticker, rows in output.items() if not rows),
    }


def _bar_lookup(rows: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, bars in rows.items():
        output[ticker] = {}
        for bar in bars:
            day = str(bar.get("date") or bar.get("Date") or "")[:10]
            open_ = _number(bar.get("open") if "open" in bar else bar.get("Open"))
            close = _number(bar.get("close") if "close" in bar else bar.get("Close"))
            if day and open_ and close:
                output[ticker][day] = {"open": open_, "close": close}
    return output


def _benchmark_diagnostics(
    trades: list[dict[str, Any]], broad_ohlcv: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    lookup = _bar_lookup(broad_ohlcv)
    target_returns = [
        float(row["pnl_pct_net"])
        for row in trades
        if _number(row.get("pnl_pct_net")) is not None
    ]
    target_mean = sum(target_returns) / len(target_returns) if target_returns else None
    rows: dict[str, Any] = {
        "TARGET": {
            "available": bool(target_returns),
            "count": len(target_returns),
            "mean_return": target_mean,
            "total_pnl_4000": sum(value * BASE_NOTIONAL_USD for value in target_returns),
        },
        "CASH": {
            "available": bool(trades),
            "count": len(trades),
            "mean_return": 0.0 if trades else None,
            "total_pnl_4000": 0.0 if trades else None,
        },
    }
    for ticker in BENCHMARKS[1:]:
        returns: list[float] = []
        missing = 0
        for trade in trades:
            entry = lookup.get(ticker, {}).get(str(trade.get("entry_date")))
            exit_ = lookup.get(ticker, {}).get(str(trade.get("exit_date")))
            if not entry or not exit_:
                missing += 1
                continue
            returns.append(
                exit_["close"] / entry["open"] - 1.0 - ROUND_TRIP_COST_PCT
            )
        complete = bool(trades) and not missing
        rows[ticker] = {
            "available": complete,
            "count": len(returns),
            "missing_trade_dates": missing,
            "mean_return": sum(returns) / len(returns) if complete else None,
            "total_pnl_4000": (
                sum(value * BASE_NOTIONAL_USD for value in returns)
                if complete
                else None
            ),
        }
    available = [name for name in BENCHMARKS if rows[name]["available"]]
    unavailable = [name for name in BENCHMARKS if not rows[name]["available"]]
    failed_performance = [
        name
        for name in available
        if target_mean is None
        or rows[name]["mean_return"] is None
        or target_mean <= float(rows[name]["mean_return"])
    ]
    return {
        "same_entry_exit_and_35bps_cost": True,
        "comparators": rows,
        "required_comparators": list(BENCHMARKS),
        "binding_available_comparators": available,
        "unavailable_comparators": unavailable,
        "failed_performance_comparators": failed_performance,
        "failed_comparators": list(dict.fromkeys([*unavailable, *failed_performance])),
        "missing_required_is_hard_failure": True,
        "passed": bool(target_returns) and not unavailable and not failed_performance,
    }


def _cluster_diagnostics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[float]] = defaultdict(list)
    by_window: Counter[str] = Counter()
    for trade in trades:
        cluster = str(
            trade.get("report_date")
            or trade.get("quarter")
            or trade.get("qbp_release_date")
            or "unknown"
        )
        value = _number(trade.get("pnl_pct_net"))
        if value is not None:
            clusters[cluster].append(value)
        if trade.get("window"):
            by_window[str(trade["window"])] += 1
    rows = [
        {
            "cluster": cluster,
            "trade_count": len(values),
            "mean_return": sum(values) / len(values),
            "total_pnl": sum(values) * BASE_NOTIONAL_USD,
        }
        for cluster, values in sorted(clusters.items())
    ]
    nominal_trade_count = sum(len(values) for values in clusters.values())
    return {
        "cluster_unit": "QBP report quarter",
        "nominal_trade_count": nominal_trade_count,
        "effective_cluster_n": len(clusters),
        "expected_effective_cluster_n": 6,
        "cluster_count_matches_ticket": len(clusters) == 6,
        "clusters": rows,
        "warning": (
            f"{nominal_trade_count} stock rows share {len(clusters)} release "
            "decisions and are not independent observations."
        ),
    }


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(row["before"]["expected_value_score"] for row in rows.values()), 6
        ),
        "after_expected_value_score_sum": round(
            sum(row["after"]["expected_value_score"] for row in rows.values()), 6
        ),
        "expected_value_score_delta_sum": round(
            sum(row["delta"]["expected_value_score"] for row in rows.values()), 6
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
        raise RuntimeError("DSR return dates are not strictly aligned")
    context = {
        "selection_scope": TRIAL_FAMILY,
        "window": {
            "segments": [
                {"label": label, "start": WINDOWS[label][0], "end": WINDOWS[label][1]}
                for label in ordered_windows
            ]
        },
        "frequency": "daily",
        "return_basis": "core_plus_fdic_fixed_notional_daily_mtm_post_cost",
        "risk_free_assumption": "zero",
        "protocol": {
            "id": "post_mtm_gate1_plus_fdic_quarterly_top5_v1",
            "rule_version": RULE_VERSION,
        },
        "data": {
            "baseline_summary_sha256": _file_sha(BASELINE_SUMMARY),
            "source_manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
            "source_retrieved_at": source_manifest["retrieved_at"],
        },
        "cost": {"round_trip_cost_pct": ROUND_TRIP_COST_PCT},
    }
    panel = {
        "selected_config_id": "fdic_deposit_repair_on",
        "expected_attempt_count": EXPECTED_DSR_ATTEMPTS,
        "selection_pool_complete": True,
        "expected_return_dates": dates,
        "periods_per_year": 252,
        "trials": [
            {
                "config_id": "fdic_deposit_repair_on",
                "config": {"rule_version": RULE_VERSION},
                "attempted": True,
                **context,
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
    if report.get("status") != "computed":
        report["fail_closed_reason"] = (
            "single_preregistered_trial_has_no_cross_trial_dispersion"
        )
    _write_json(DSR_PANEL_PATH, panel)
    _write_json(DSR_REPORT_PATH, report)
    return panel, report


def build_payload(*, offline: bool) -> dict[str, Any]:
    records, source_manifest = materialize_source(offline=offline)
    baseline_windows = _baseline_window_map(_read_json(BASELINE_SUMMARY))
    tickers = sorted({str(row["ticker"]) for row in records} | set(BENCHMARKS[1:]))
    broad, auxiliary = _load_ohlcv(tickers, "2024-09-01", "2026-05-31")
    calculation_identity = _calculation_identity(auxiliary)
    trading_dates = [str(row["date"]) for row in broad.get("SPY", [])]
    if not trading_dates:
        raise RuntimeError("SPY trading calendar missing")
    ohlcv_by_window: dict[str, dict[str, Any]] = {}
    bar_identity: dict[str, Any] = {}
    for label in WINDOWS:
        ohlcv_by_window[label], bar_identity[label] = _window_ohlcv(
            broad, baseline_windows[label]
        )

    windows: dict[str, Any] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = replay_fdic_call_report_deposit_repair_paper_trades(
            records=records,
            ohlcv_by_ticker=ohlcv_by_window[label],
            start=start,
            end=end,
        )
        trades = [dict(row, window=label) for row in replay.get("trades") or []]
        before, after, combined_curve = combine_window(
            baseline_windows[label], trades, ohlcv_by_window[label]
        )
        generated = int(replay.get("signals_generated") or 0)
        survived = int(replay.get("signals_survived") or replay.get("survived") or 0)
        generated_total += generated
        survived_total += survived
        trades_by_window[label] = trades
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    after["expected_value_score"] - before["expected_value_score"], 6
                ),
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"], 6
                ),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": (
                float(replay.get("survival_rate"))
                if replay.get("survival_rate") is not None
                else (survived / generated if generated else 0.0)
            ),
            "selected_candidates": replay.get("selected_candidates") or [],
            "target_trades": trades,
            "unsettled": replay.get("unsettled") or [],
            "reject_totals": replay.get("reject_totals") or {},
            "combined_curve_sha256": _canonical_sha(combined_curve),
        }

    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    target = _target_summary(trades_by_window)
    aggregate = _aggregate_windows(windows)
    benchmarks = _benchmark_diagnostics(all_trades, broad)
    clusters = _cluster_diagnostics(all_trades)
    gate2_passed = bool(all_trades) and all(
        trade.get("entry_date") and trade.get("target_price") for trade in all_trades
    )
    gate3_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0 and gate3_rate >= 0.05,
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(gate3_rate, 6),
    }
    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": target["total_trade_count"],
        "adjusted_windows": [label for label, rows in trades_by_window.items() if rows],
        "adjusted_window_count": target["window_count"],
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": target["single_ticker_positive_share"],
        "hhi_concentration": target["hhi_concentration"],
        "top_5_contribution_pct": target["top_5_contribution_pct"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target["total_trade_count"]
            if target["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        require_tail_concentration_not_worse=False,
    )
    canonical = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    strict = evaluate_gate4(gate_metrics, thresholds=thresholds, check_materiality=True)
    failures = list(canonical["hard_failures"])
    if aggregate["windows_pnl_regressed"]:
        failures.append("window_pnl_regression")
    if not gate2_passed:
        failures.append("gate2_signal_contract_failed")
    if not gate3["passed"]:
        failures.append("gate3_survival_below_5pct")
    if not benchmarks["passed"]:
        failures.append(
            "required_cash_spy_qqq_xlf_kbe_comparator_missing_or_not_beaten"
        )
    if (
        aggregate["expected_value_score_delta_sum"]
        <= ACCEPTED_CANDIDATE_COMPARATOR["expected_value_score_delta_sum"]
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
        "passed": False,
        "status": "blocked",
        "historical_value_vintage_pit": False,
        "historical_entity_mapping_pit": False,
        "effective_quarter_cluster_n": clusters["effective_cluster_n"],
        "settled_forward_quarter_count": 0,
        "hard_failures": [
            "historical_fdic_first_release_vintage_not_reconstructed",
            "historical_parent_cert_security_mapping_not_reconstructed",
        ],
        "binding_reason": (
            "Current-vintage FDIC values and current active CERT/RSSDHCR/SEC "
            "mapping directly determine the historical top5 selection."
        ),
    }
    gate4 = {
        **numeric_gate4,
        "passed": bool(numeric_gate4["passed"] and measurement_validity_gate["passed"]),
        "status": (
            "passed"
            if numeric_gate4["passed"] and measurement_validity_gate["passed"]
            else "blocked"
        ),
        "hard_failures": list(
            dict.fromkeys(
                [
                    *numeric_gate4["hard_failures"],
                    *measurement_validity_gate["hard_failures"],
                ]
            )
        ),
        "numeric_gate4": numeric_gate4,
        "measurement_validity_gate": measurement_validity_gate,
    }

    panel, dsr_report = _build_dsr(windows, source_manifest)
    envelope = ExecutionEnvelope(
        base_notional=BASE_NOTIONAL_USD,
        max_capital_pct=0.20,
        min_dollar_volume=None,
        slippage_bps=17.5,
        max_displacement=0,
        max_concurrent=5,
        order_semantics="first_strictly_later_open_then_20th_session_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "Default-off quarterly top5; 35bps round trip; no core displacement. "
            "No stock-liquidity cutoff was preregistered, so the live envelope "
            "fails closed instead of treating bank assets as stock ADV."
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
    live["blockers"] = list(
        dict.fromkeys(
            [
                *live.get("blockers", []),
                "current_active_cert_parent_asset_denominator_not_live_ready",
            ]
        )
    )
    live["ready"] = False
    verdict = full_stack_verdict(
        gate4=gate4, live_readiness=live, envelope=envelope
    )
    gate5 = {
        "passed": bool(live.get("ready")),
        "status": "passed" if live.get("ready") else "blocked",
        "gate4_independent": True,
        "honest_attempt_count": EXPECTED_DSR_ATTEMPTS,
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
        "effective_quarter_cluster_n": clusters["effective_cluster_n"],
        "parent_group_denominator_blocks_live": True,
        "forward_live_readiness": live,
        "panel_path": _repo_rel(DSR_PANEL_PATH),
        "report_path": _repo_rel(DSR_REPORT_PATH),
    }

    snapshot = build_fdic_call_report_deposit_repair_paper_sleeve_snapshot(
        as_of_date=PAPER_SNAPSHOT_AS_OF,
        records=records,
        trading_dates=trading_dates,
    )
    if not isinstance(snapshot, dict):
        raise RuntimeError("shared helper paper snapshot must be an object")
    snapshot = {
        **snapshot,
        "experiment_id": EXPERIMENT_ID,
        "trade_enabled": False,
        "live_orders_changed": False,
        "source_manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
    }
    _write_json(PAPER_SNAPSHOT_PATH, snapshot)

    numeric_pass = bool(numeric_gate4["passed"])
    observed_only_lead = bool(numeric_pass and not measurement_validity_gate["passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": source_manifest["retrieved_at"],
        "lane": "alpha_search",
        "status": "observed_only_positive_lead" if observed_only_lead else "rejected",
        "decision": (
            "observed_only_positive_lead_not_pit_qualified"
            if observed_only_lead
            else "rejected_fdic_call_report_deposit_repair_candidate_pool"
        ),
        "accepted_alpha": False,
        "observed_only_positive_lead": observed_only_lead,
        "hypothesis": (
            "After each official FDIC QBP release, exact-mapped listed bank parents "
            "with a dominant >=$10bn insured bank, positive YoY core-deposit growth, "
            "and falling uninsured-deposit share continue to reprice over 20 sessions."
        ),
        "rule_version": RULE_VERSION,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "locked_policy": {
            "qbp_release_dates": _normalized_qbp_dates(),
            "mapping": "current exact SEC title == current FDIC NAMEHCR",
            "dominant_bank_min_share": 0.80,
            "min_bank_assets_thousands": 10_000_000,
            "max_abs_asset_yoy": 0.25,
            "core_deposit_yoy": ">0",
            "uninsured_share_yoy_delta": "<0",
            "rank": "most negative uninsured-share delta top5 per report quarter",
            "entry": "first strictly later open",
            "exit": "20th session close",
            "notional_usd": BASE_NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
        "source": {
            "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
            "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
            "coverage": source_manifest["coverage"],
            "current_vintage_revision_caveat": True,
            "current_parent_mapping_caveat": True,
        },
        "calculation_identity": calculation_identity,
        "windows": windows,
        "aggregate": aggregate,
        "target_summary": target,
        "accepted_candidate_comparator": ACCEPTED_CANDIDATE_COMPARATOR,
        "benchmark_diagnostics": benchmarks,
        "quarter_cluster_diagnostics": clusters,
        "gate1": {
            "passed": True,
            "baseline": _repo_rel(BASELINE_SUMMARY),
            "baseline_sha256": _file_sha(BASELINE_SUMMARY),
            "active_reference": "2026-07-12 post-MTM standard windows",
            "auxiliary_ohlcv": auxiliary,
            "bar_identity": bar_identity,
        },
        "gate2": {
            "passed": gate2_passed,
            "sentinel_fields": ["entry_date", "target_price"],
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
            "daily_candidate_parity_complete": False,
            "daily_wiring_retained": False,
            "forward_collection_automatic": False,
            "daily_wiring_reason": (
                "The rejected experiment retained no run.py, report, or ledger wiring; "
                "the current snapshot is a one-shot default-off helper parity check."
            ),
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
            "shared_helper": "quant/fdic_call_report_deposit_repair_paper_sleeve.py",
            "historical_and_daily_selection_share_helper": True,
            "one_shot_helper_snapshot_parity": True,
            "daily_wiring_retained": False,
            "forward_collection_automatic": False,
        },
        "residual_unknowns": [
            "Current FDIC financial rows can include post-release amendments; first-vintage values are not reconstructed.",
            "Current active parent/certificate membership is carried backward and can embed merger or delisting survivorship.",
            "The nominal stock rows collapse to six QBP release clusters.",
            "XLF/KBE comparators bind only when the frozen warehouse contains complete entry/exit bars.",
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "; ".join(numeric_gate4["hard_failures"])
                if numeric_gate4["hard_failures"]
                else (
                    "The numeric policy cleared its scorecard but cannot become "
                    "evidence-qualified without PIT vintages and entity mappings."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune mappings, $10bn/80%/25% gates, ratio formula, rank, "
                "top-N, release timing, hold, notional, costs, or window slices."
            ),
            "new_evidence_required": (
                "First-release/as-of FDIC vintages plus historical group/security mapping "
                "and exact-top5 sensitivity proof, or enough prospectively settled QBP "
                "quarters; same-source field or threshold sweeps are forbidden."
            ),
        },
        "reopen_condition": (
            "Reopen only with first-release/as-of FDIC vintages plus historical "
            "group/security mapping and exact-top5 sensitivity proof, or materially "
            "more prospectively settled QBP quarters."
        ),
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name}",
            f".\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --offline",
        ],
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    _write_json(RESULT_PATH, payload)
    for path, side in ((BEFORE_PATH, "before"), (AFTER_PATH, "after")):
        _write_json(
            path,
            {
                "schema": f"fdic_deposit_repair_gate4_{side}_v1",
                "expected_value_score": payload["aggregate"][
                    f"{side}_expected_value_score_sum"
                ],
                "total_pnl": payload["aggregate"][f"{side}_total_pnl_sum"],
                "max_drawdown_pct": max(
                    row[side]["max_drawdown_pct"]
                    for row in payload["windows"].values()
                ),
                "total_trades": sum(
                    row[side]["total_trades"] for row in payload["windows"].values()
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
                        payload["aggregate"][f"{side}_total_pnl_sum"] / 100_000.0,
                        4,
                    )
                },
            },
        )
    lines = [
        f"# {EXPERIMENT_ID} FDIC Call Report deposit repair",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Full-stack verdict: `{payload['full_stack']['verdict']['verdict']}`",
        (
            "- Target trades / tickers / effective quarter clusters: "
            f"`{payload['target_summary']['total_trade_count']}` / "
            f"`{payload['target_summary']['ticker_count']}` / "
            f"`{payload['quarter_cluster_diagnostics']['effective_cluster_n']}`"
        ),
        f"- Aggregate EV delta: `{payload['aggregate']['expected_value_score_delta_sum']:+.6f}`",
        f"- Aggregate PnL delta: `${payload['aggregate']['total_pnl_delta_sum']:+,.2f}`",
        f"- Gate 3 survival: `{payload['gate3']['survival_rate']:.2%}`",
        f"- Available comparators: `{', '.join(payload['benchmark_diagnostics']['binding_available_comparators'])}`",
        f"- Failed comparators: `{', '.join(payload['benchmark_diagnostics']['failed_comparators']) or 'none'}`",
        f"- Numeric Gate 4 failures: `{', '.join(payload['numeric_gate4']['hard_failures']) or 'none'}`",
        f"- Measurement-validity failures: `{', '.join(payload['measurement_validity_gate']['hard_failures']) or 'none'}`",
        f"- Binding Gate 4 failures: `{', '.join(payload['gate4']['hard_failures']) or 'none'}`",
        (
            "- Accepted candidate-pool comparator: actual EV / required EV "
            f"`{payload['aggregate']['expected_value_score_delta_sum']:+.6f}` / "
            f"`>{payload['accepted_candidate_comparator']['expected_value_score_delta_sum']:+.6f}`; "
            "actual PnL / required PnL "
            f"`${payload['aggregate']['total_pnl_delta_sum']:+,.2f}` / "
            f"`>${payload['accepted_candidate_comparator']['total_pnl_delta_sum']:+,.2f}` "
            f"(`{payload['accepted_candidate_comparator']['experiment_id']}`)."
        ),
        f"- Gate 5 / DSR: `{payload['gate5']['status']}` / `{payload['gate5']['dsr_status']}`",
        f"- Evaluator selection-pool complete: `{payload['gate5']['selection_pool_complete']}`",
        "",
        "## Window deltas",
        "",
    ]
    for label in WINDOWS:
        row = payload["windows"][label]
        lines.append(
            f"- {label}: trades={len(row['target_trades'])}, EV="
            f"{row['delta']['expected_value_score']:+.6f}, PnL="
            f"${row['delta']['total_pnl']:+,.2f}, drawdown="
            f"{row['delta']['max_drawdown_pct']:+.6f}."
        )
    lines.extend(["", "## Unsettled selected rows", ""])
    unsettled_count = 0
    for label in WINDOWS:
        for row in payload["windows"][label]["unsettled"]:
            unsettled_count += 1
            lines.append(
                f"- {label}: report={row.get('report_date')}, ticker={row.get('ticker')}, "
                f"entry={row.get('entry_date')}, reason={row.get('unsettled_reason')}."
            )
    if not unsettled_count:
        lines.append("- none")
    lines.extend(["", "## Calculation identity", ""])
    for label, identity in payload["calculation_identity"]["code_files"].items():
        lines.append(
            f"- {label}: `{identity['path']}` sha256 `{identity['sha256']}`"
        )
    auxiliary = payload["calculation_identity"]["frozen_auxiliary_ohlcv"]
    lines.append(
        f"- frozen_auxiliary_ohlcv: `{auxiliary['path']}` file sha256 "
        f"`{auxiliary['file_sha256']}`, rowset sha256 `{auxiliary['rowset_sha256']}`"
    )
    lines.extend(
        [
            "",
            "## Evidence limits",
            "",
            f"The {payload['quarter_cluster_diagnostics']['nominal_trade_count']} settled rows are only {payload['quarter_cluster_diagnostics']['effective_cluster_n']} quarterly release clusters. FDIC financials are current-vintage and the exact current SEC/FDIC parent map is carried backward; neither first-release amendments nor historical ownership are reconstructed.",
            "",
            "Historical replay and the one-shot default-off paper snapshot call the same shared selection helper. Because the alpha was rejected, no run.py/report/ledger daily wiring or automatic forward collection was retained. No live order, core ranking, sizing, or exit path changed.",
            "",
            f"Reproduce offline: `.\\.venv\\Scripts\\python.exe -B quant\\experiments\\{Path(__file__).name} --offline`",
        ]
    )
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Require the frozen FDIC source bundle; never access the network.",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Freeze or validate source data without inspecting outcomes.",
    )
    args = parser.parse_args()
    if args.source_only:
        records, manifest = materialize_source(offline=args.offline)
        print(
            json.dumps(
                {"records": len(records), "source_manifest": manifest},
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    payload = build_payload(offline=args.offline)
    _write_outputs(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "target_summary": payload["target_summary"],
                "aggregate": payload["aggregate"],
                "benchmark_gate": payload["benchmark_diagnostics"],
                "quarter_clusters": payload["quarter_cluster_diagnostics"],
                "gate4_failures": payload["gate4"]["hard_failures"],
                "gate5": payload["gate5"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
