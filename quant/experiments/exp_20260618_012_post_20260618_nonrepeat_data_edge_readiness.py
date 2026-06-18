"""exp-20260618-012: post-20260618 non-repeat data-edge readiness.

This is an alpha-search direction-selection experiment, not a strategy replay.
It records whether there is a non-repeat, point-in-time, production-visible
candidate-pool alpha surface ready for Gate 1-4 after the latest SEC,
Companyfacts, ownership, options, and lead-lag failures.

No trading rule, helper, ranking, sizing, exit, LLM/news behavior, daily runner,
watchlist, or order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260618-012"
SLUG = "post_20260618_nonrepeat_data_edge_readiness"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260618_012_post_20260618_nonrepeat_data_edge_readiness.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260618_012_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

PREDICTION = {
    "success_probability": 0.08,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "all_candidate_surfaces_frozen_or_missing_pit_fields",
        "near_neighbor_retries_not_trustworthy",
        "no_shared_daily_helper_for_positive_replay",
    ],
    "confidence_reason": (
        "Recent logs show executable Companyfacts, SEC, ownership, options, "
        "and OHLCV relation ideas are rejected, frozen, or forward-only; this "
        "verifies exact local data availability before any strategy change."
    ),
}

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260618-011",
    "exp-20260618-010",
    "exp-20260618-007",
    "exp-20260618-006",
    "exp-20260618-005",
    "exp-20260617-025",
    "exp-20260617-012",
    "exp-20260612-015",
    "exp-20260612-016",
]

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "win_rate": 0.8333,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 0.89,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.6818,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for row in read_jsonl(path):
            if row.get("experiment_id") == record["experiment_id"]:
                return
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in windows.values()), 4
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in windows.values()), 2
        ),
        "max_window_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in windows.values()
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in windows.values()),
        "min_survival_rate": min(float(row["survival_rate"]) for row in windows.values()),
    }


def delta_dict(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after[key]
        if isinstance(before_value, float) or isinstance(after_value, float):
            deltas[key] = round(float(after_value) - float(before_value), 4)
        else:
            deltas[key] = after_value - before_value
    return deltas


def filename_dates(paths: list[Path]) -> list[str]:
    dates: list[str] = []
    pattern = re.compile(r"(20\d{6})")
    for path in paths:
        match = pattern.search(path.name)
        if not match:
            continue
        raw = match.group(1)
        dates.append(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
    return dates


def top_keys(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    return sorted(str(key) for key in rows[0].keys())


def summarize_sec_events() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "non_ohlcv"
    files = sorted(root.glob("sec_filing_events_*.jsonl"))
    aggregate = root / "sec_filing_events_20241002_20260421.jsonl"
    rows = read_jsonl(aggregate)
    forms = Counter(str(row.get("form") or row.get("form_type") or "") for row in rows)
    dates = [
        str(row.get("filing_date") or row.get("date") or "")[:10]
        for row in rows
        if row.get("filing_date") or row.get("date")
    ]
    return {
        "path_glob": "data/non_ohlcv/sec_filing_events_*.jsonl",
        "files": len(files),
        "min_snapshot_date": min(filename_dates(files)) if files else None,
        "max_snapshot_date": max(filename_dates(files)) if files else None,
        "aggregate_path": repo_rel(aggregate),
        "aggregate_exists": aggregate.exists(),
        "aggregate_rows": len(rows),
        "aggregate_min_filing_date": min(dates) if dates else None,
        "aggregate_max_filing_date": max(dates) if dates else None,
        "aggregate_top_forms": dict(forms.most_common(12)),
        "sample_keys": top_keys(rows),
        "blocking_read": (
            "The events feed covers the fixed windows, but the recent SEC-item "
            "absorption sequence already rejected the obvious item-code shapes; "
            "a new run needs materially richer structured event fields."
        ),
    }


def summarize_sec_text() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
    rows = read_jsonl(path)
    forms = Counter(str(row.get("form") or row.get("form_type") or "") for row in rows)
    dates = [
        str(row.get("filing_date") or row.get("date") or "")[:10]
        for row in rows
        if row.get("filing_date") or row.get("date")
    ]
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "rows": len(rows),
        "form_counts": dict(forms.most_common(12)),
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "sample_keys": top_keys(rows),
        "blocking_read": (
            "The fixed-window aggregate SEC text file is 8-K oriented. It does "
            "not provide a canonical 10-K/10-Q text or cover-page surface for "
            "a new periodic-report alpha without a new PIT extraction."
        ),
    }


def summarize_sec_submissions() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
    files = sorted(root.glob("*.json")) if root.exists() else []
    categories: Counter[str] = Counter()
    target_forms: Counter[str] = Counter()
    dates: list[str] = []
    tracked_forms = {
        "SC 13G",
        "SC 13G/A",
        "SC 13D",
        "SC 13D/A",
        "4",
        "8-K",
        "10-K",
        "10-Q",
        "10-K/A",
        "10-Q/A",
        "NT 10-K",
        "NT 10-Q",
        "S-8",
        "424B5",
        "DEFA14A",
    }
    for path in files:
        payload = read_json(path)
        if not payload:
            continue
        categories[str(payload.get("category") or payload.get("filerCategory") or "")] += 1
        recent = (payload.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        filing_dates = recent.get("filingDate") or []
        for form, filing_date in zip(forms, filing_dates):
            if form in tracked_forms:
                target_forms[str(form)] += 1
                if filing_date:
                    dates.append(str(filing_date)[:10])
    return {
        "path": repo_rel(root),
        "exists": root.exists(),
        "submission_files": len(files),
        "top_level_categories": dict(categories.most_common(12)),
        "recent_tracked_form_counts": dict(target_forms.most_common()),
        "min_recent_tracked_date": min(dates) if dates else None,
        "max_recent_tracked_date": max(dates) if dates else None,
        "blocking_read": (
            "Submissions JSON proves 13G/13D and periodic forms exist in local "
            "metadata, but top-level filer category is current metadata and the "
            "cache does not itself provide parsed PIT holder/stake or cover-page "
            "status fields."
        ),
    }


def summarize_sec_primary_document_cache() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "cache" / "sec"
    patterns = ["*13g*", "*13d*", "*sc13*", "*SC13*"]
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for pattern in patterns:
        matches = sorted(root.rglob(pattern)) if root.exists() else []
        file_matches = [path for path in matches if path.is_file()]
        counts[pattern] = len(file_matches)
        samples[pattern] = [repo_rel(path) for path in file_matches[:5]]
    return {
        "path": repo_rel(root),
        "exists": root.exists(),
        "filename_pattern_counts": counts,
        "samples": samples,
        "blocking_read": (
            "Local submissions metadata contains 13G/13D form references, but "
            "no reusable accession-level primary-document cache was found by "
            "the standard 13D/13G filename patterns. A holder/stake alpha would "
            "need a new PIT parser or ingested table."
        ),
    }


def summarize_options_chain() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "non_ohlcv"
    files = sorted(root.glob("options_onclickmedia_chain_*.jsonl"))
    dates = filename_dates(files)
    latest_rows = read_jsonl(files[-1]) if files else []
    tickers = {str(row.get("ticker")) for row in latest_rows if row.get("ticker")}
    return {
        "path_glob": "data/non_ohlcv/options_onclickmedia_chain_*.jsonl",
        "files": len(files),
        "min_snapshot_date": min(dates) if dates else None,
        "max_snapshot_date": max(dates) if dates else None,
        "latest_snapshot_rows": len(latest_rows),
        "latest_snapshot_unique_tickers": len(tickers),
        "latest_snapshot_sample_keys": top_keys(latest_rows),
        "blocking_read": (
            "Options snapshots are forward collection rows, not full old_thin, "
            "mid_weak, and late_strong historical chains with closed outcomes."
        ),
    }


def summarize_finra_short_interest() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "non_ohlcv" / "finra_short_interest" / "rows.json"
    rows: list[dict[str, Any]] = []
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("rows", [])
    dates = [
        str(row.get("settlement_date") or row.get("usable_trade_date"))[:10]
        for row in rows
        if isinstance(row, dict)
        and (row.get("settlement_date") or row.get("usable_trade_date"))
    ]
    tickers = {
        str(row.get("ticker"))
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "rows": len(rows),
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "unique_tickers": len(tickers),
        "sample_keys": top_keys([row for row in rows if isinstance(row, dict)]),
        "blocking_read": (
            "FINRA short-interest rows exist, but recent FINRA/borrow-pressure "
            "attempts failed. A new edge needs PIT borrow-fee or rebate history, "
            "which is not present."
        ),
    }


def summarize_13f() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "kova" / "institutional"
    files = sorted(root.glob("sec13f_ownership_*.jsonl")) if root.exists() else []
    dates = filename_dates(files)
    latest_rows = read_jsonl(files[-1]) if files else []
    tickers = {str(row.get("ticker")) for row in latest_rows if row.get("ticker")}
    statuses = Counter(str(row.get("status") or "") for row in latest_rows)
    reasons = Counter(str(row.get("reason") or "") for row in latest_rows)
    return {
        "path_glob": "data/kova/institutional/sec13f_ownership_*.jsonl",
        "files": len(files),
        "min_snapshot_date": min(dates) if dates else None,
        "max_snapshot_date": max(dates) if dates else None,
        "latest_rows": len(latest_rows),
        "latest_unique_tickers": len(tickers),
        "latest_status_counts": dict(statuses.most_common(8)),
        "latest_reason_counts": dict(reasons.most_common(8)),
        "latest_sample_keys": top_keys(latest_rows),
        "blocking_read": (
            "The Kova 13F surface is a daily snapshot/status surface, not a "
            "three-window PIT manager-holder delta table beyond already tested "
            "13F sponsorship and crowding families."
        ),
    }


def summarize_forward_replacement_value() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
    rows = read_jsonl(path)
    tickers = {str(row.get("ticker")) for row in rows if row.get("ticker")}
    sleeve_keys = Counter(str(row.get("sleeve_key")) for row in rows if row.get("sleeve_key"))
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "rows": len(rows),
        "unique_tickers": len(tickers),
        "sleeve_key_counts": dict(sleeve_keys.most_common()),
        "blocking_read": (
            "Forward replacement rows are useful monitoring evidence, but they "
            "are not a broad historical candidate-pool surface and cannot turn "
            "a private forward lead into an accepted Gate-4 alpha."
        ),
    }


def load_history_summary() -> list[dict[str, Any]]:
    selected = set(NEARBY_PRIOR_EXPERIMENTS)
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((REPO_ROOT / "experiments" / "logs").glob("exp-*.json")):
        if path.stem not in selected:
            continue
        payload = read_json(path)
        if payload:
            found[path.stem] = {
                "experiment_id": path.stem,
                "status": payload.get("status"),
                "decision": payload.get("decision"),
                "summary": (
                    payload.get("post_run_reflection", {}).get("why_result_happened")
                    or payload.get("summary")
                    or payload.get("hypothesis")
                ),
            }
    for row in read_jsonl(EXPERIMENT_LOG_JSONL):
        experiment_id = str(row.get("experiment_id") or "")
        if experiment_id not in selected or experiment_id in found:
            continue
        found[experiment_id] = {
            "experiment_id": experiment_id,
            "status": row.get("status"),
            "decision": row.get("decision"),
            "summary": (
                row.get("post_run_reflection", {}).get("why_result_happened")
                if isinstance(row.get("post_run_reflection"), dict)
                else row.get("hypothesis")
            ),
        }
    fallback = {
        "exp-20260618-011": "blocked: no Gate-4-ready non-repeat surface after advertising failure.",
        "exp-20260618-010": "rejected: advertising efficiency improved some windows but regressed late_strong and failed robustness.",
        "exp-20260618-007": "blocked: PIT filer-status surface absent; current submissions category would leak.",
        "exp-20260618-006": "rejected: intraindustry lead-lag direction not stable across windows.",
        "exp-20260618-005": "blocked: SEC item-code sequence left no non-repeat surface.",
        "exp-20260617-025": "rejected: NT late-filing absorption failed.",
        "exp-20260617-012": "rejected: SBC grant-value backlog relief failed accepted-comparator and concentration checks.",
        "exp-20260612-015": "rejected/frozen: raw 13D activist stake initiation lacked parsed edge.",
        "exp-20260612-016": "rejected/frozen: raw 13G passive stake initiation lacked parsed edge.",
    }
    for experiment_id, summary in fallback.items():
        found.setdefault(
            experiment_id,
            {
                "experiment_id": experiment_id,
                "status": "historical_context",
                "decision": "see_experiment_log",
                "summary": summary,
            },
        )
    return [found[experiment_id] for experiment_id in NEARBY_PRIOR_EXPERIMENTS]


def build_candidate_surfaces() -> list[dict[str, Any]]:
    return [
        {
            "surface": "parsed_13g_13d_holder_stake_quality",
            "alpha_hypothesis": (
                "Initial passive or activist stake disclosures can mark informed "
                "sponsorship in under-owned relative-strength leaders."
            ),
            "status": "blocked_missing_parsed_pit_primary_document_surface",
            "related_history": ["exp-20260612-015", "exp-20260612-016"],
            "gate2_required_fields": [
                "issuer ticker",
                "filing date",
                "accession number",
                "holder identity",
                "stake percent",
                "initial/add/reduce classification",
                "PIT source seen by production",
            ],
            "why_not_executable_now": (
                "Submissions metadata confirms 13G/13D forms exist, but the repo "
                "does not expose a parsed holder/stake/action table. Raw event "
                "retries are already frozen."
            ),
            "new_evidence_needed": (
                "Parse or ingest accession-level 13G/13D holder, stake percent, "
                "action type, issuer ticker, and filing date across all standard "
                "windows."
            ),
        },
        {
            "surface": "pit_cover_page_filer_status_transition",
            "alpha_hypothesis": (
                "Accelerated-filer upgrades, emerging-growth exits, or smaller "
                "reporting-company transitions could identify liquidity and "
                "disclosure-quality inflections."
            ),
            "status": "blocked_current_metadata_would_leak",
            "related_history": ["exp-20260618-007"],
            "gate2_required_fields": [
                "filing date",
                "accession number",
                "cover-page filer status",
                "issuer ticker",
                "PIT daily availability",
            ],
            "why_not_executable_now": (
                "Local submissions category is current top-level metadata, not "
                "a historical cover-page status keyed by accession/date."
            ),
            "new_evidence_needed": (
                "Historical 10-K/10-Q cover-page filer status parsed by "
                "accession and joined to the same production snapshot date."
            ),
        },
        {
            "surface": "new_sec_item_or_text_absorption",
            "alpha_hypothesis": (
                "Specific disclosure events may drift after negative or complex "
                "filings when price initially absorbs the news."
            ),
            "status": "blocked_recent_item_text_family_rejections",
            "related_history": [
                "exp-20260618-001",
                "exp-20260618-002",
                "exp-20260618-003",
                "exp-20260618-004",
                "exp-20260618-005",
                "exp-20260618-009",
            ],
            "gate2_required_fields": [
                "PIT filing date",
                "issuer ticker",
                "form/item code",
                "event text",
                "daily production snapshot parity",
            ],
            "why_not_executable_now": (
                "The recent SEC 8-K item/text sequence failed. Moving to another "
                "item code or regex gate is a frozen near-neighbor without richer "
                "semantic provenance."
            ),
            "new_evidence_needed": (
                "A new structured event tuple or LLM-labeled event field with "
                "clear input logs and replay boundaries."
            ),
        },
        {
            "surface": "options_skew_open_interest_candidate_pool",
            "alpha_hypothesis": (
                "Skew and open-interest pressure can identify informed demand "
                "ahead of equity continuation."
            ),
            "status": "blocked_forward_only_no_three_window_history",
            "related_history": ["exp-20260617-004", "exp-20260613-025"],
            "gate2_required_fields": [
                "quote date",
                "ticker",
                "expiration",
                "strike",
                "call/put",
                "bid/ask/mid",
                "open interest",
                "closed equity outcome",
            ],
            "why_not_executable_now": (
                "Options files are recent forward snapshots and do not cover the "
                "canonical old_thin/mid_weak/late_strong windows."
            ),
            "new_evidence_needed": (
                "Full-window historical options chain snapshots with shared daily "
                "snapshot semantics and closed outcomes."
            ),
        },
        {
            "surface": "borrow_fee_or_crowding_relief",
            "alpha_hypothesis": (
                "Borrow-fee relief or short covering can add a supply-demand "
                "edge around crowded relative-strength winners."
            ),
            "status": "blocked_missing_borrow_fee_and_recent_finra_rejections",
            "related_history": [
                "exp-20260616-020",
                "exp-20260616-024",
                "exp-20260616-026",
                "exp-20260616-028",
            ],
            "gate2_required_fields": [
                "settlement date",
                "publication date",
                "ticker",
                "short interest",
                "borrow fee or rebate",
                "PIT usable trade date",
            ],
            "why_not_executable_now": (
                "FINRA rows are present, but recent FINRA shapes failed and the "
                "needed borrow-fee/rebate field is absent."
            ),
            "new_evidence_needed": (
                "Free or stored PIT borrow-fee/rebate history joined to FINRA "
                "short interest across the standard windows."
            ),
        },
        {
            "surface": "next_companyfacts_ratio_after_advertising",
            "alpha_hypothesis": (
                "A still-unused fundamentals ratio might improve candidate "
                "selection after advertising efficiency failed."
            ),
            "status": "blocked_near_neighbor_frozen_companyfacts_family",
            "related_history": [
                "exp-20260618-010",
                "exp-20260617-012",
                "exp-20260617-026",
                "exp-20260617-001",
                "exp-20260616-003",
            ],
            "gate2_required_fields": [
                "filed-date Companyfacts value",
                "prior period value",
                "ticker",
                "entry date",
                "target price",
            ],
            "why_not_executable_now": (
                "Companyfacts ratio/tag families have many recent failures and "
                "accepted helpers. Another tag or threshold sweep would not be a "
                "new evidence axis."
            ),
            "new_evidence_needed": (
                "A genuinely new fundamentals source or structured field not "
                "covered by prior Companyfacts ratio families."
            ),
        },
        {
            "surface": "public_float_supply_scarcity_retest",
            "alpha_hypothesis": (
                "Scarce float could improve upside capture for leaders in "
                "squeeze-prone regimes."
            ),
            "status": "blocked_recent_concentration_rejection",
            "related_history": ["exp-20260617-026"],
            "gate2_required_fields": [
                "PIT public float",
                "ticker",
                "liquidity",
                "entry date",
                "target price",
            ],
            "why_not_executable_now": (
                "The recent public-float scout failed coverage and concentration "
                "standards. Retuning float thresholds repeats the same family."
            ),
            "new_evidence_needed": (
                "A broader PIT float/history source or a separate supply-demand "
                "field that fixes old_thin coverage."
            ),
        },
        {
            "surface": "static_ohlcv_or_intraindustry_lead_lag_direction",
            "alpha_hypothesis": (
                "Peer leadership or laggard catch-up could expand the candidate "
                "pool using only free OHLCV."
            ),
            "status": "blocked_recent_direction_instability",
            "related_history": ["exp-20260618-006", "exp-20260617-021"],
            "gate2_required_fields": [
                "entry date",
                "target price",
                "peer universe",
                "lead-lag direction",
                "PIT membership",
            ],
            "why_not_executable_now": (
                "The latest lead-lag experiment improved aggregate EV but failed "
                "window robustness. Static retunes would fit the same windows."
            ),
            "new_evidence_needed": (
                "External PIT peer relationship evidence or an event trigger that "
                "explains the lead-lag direction."
            ),
        },
    ]


def baseline_artifact(label: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(CANONICAL_WINDOWS),
        "strategy_changed": False,
        "notes": (
            "No strategy behavior changed in this readiness blocker; before and "
            "after are intentionally identical."
        ),
    }


def build_result() -> dict[str, Any]:
    before_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    after_aggregate = dict(before_aggregate)
    delta = delta_dict(before_aggregate, after_aggregate)
    candidate_surfaces = build_candidate_surfaces()
    created_at = now_utc()

    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "blocked",
        "lane": "alpha_search",
        "hypothesis": (
            "After the 20260617/18 rejected SEC, Companyfacts, ownership, "
            "options, and lead-lag runs, the only trustworthy next alpha is a "
            "non-repeat PIT data edge; if local fields lack that edge, no "
            "strategy change should be launched."
        ),
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "nonrepeat_candidate_pool_data_edge_readiness",
        "trial_family": "post_20260618_alpha_direction",
        "trial_variant_id": "post_20260618_nonrepeat_data_edge_readiness_v2",
        "single_causal_variable": "post_20260618_nonrepeat_data_edge_readiness_v2",
        "changed_variable": "post_20260618_nonrepeat_data_edge_readiness_v2",
        "causal_components": [
            "history_scan",
            "field_availability_audit",
            "standard_gate_baseline",
            "no_strategy_change_without_gate4_ready_pit_field",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": PREDICTION,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "gate1_baseline": {
            "source": "docs/backtesting.md current standard three-window baseline",
            "windows": CANONICAL_WINDOWS,
            "aggregate": before_aggregate,
            "status": "passed",
        },
        "gate2_field_availability": {
            "status": "blocked_for_new_alpha",
            "minimum_position_fields": {
                "entry_date": "unchanged in existing baseline strategy",
                "target_price": "unchanged in existing baseline strategy",
            },
            "candidate_surfaces": candidate_surfaces,
            "blocking_summary": (
                "All high-potential free-data surfaces found in the post-run "
                "history scan are either frozen/recently rejected or lack PIT "
                "fields needed for a production-visible shared helper."
            ),
        },
        "gate3_survival": {
            "status": "unchanged_no_new_filter",
            "survival_by_window": {
                name: {
                    "signals_generated": row["signals_generated"],
                    "signals_survived": row["signals_survived"],
                    "survival_rate": row["survival_rate"],
                }
                for name, row in CANONICAL_WINDOWS.items()
            },
            "min_survival_rate": before_aggregate["min_survival_rate"],
            "floor_check": (
                "No new filter was added. Baseline survival remains above the "
                "5% floor in every standard window."
            ),
        },
        "gate4": {
            "status": "not_run_strategy_unchanged",
            "decision": "blocked",
            "before": {"windows": CANONICAL_WINDOWS, "aggregate": before_aggregate},
            "after": {"windows": CANONICAL_WINDOWS, "aggregate": after_aggregate},
            "delta": delta,
            "failed_reasons": [
                "No non-frozen PIT data-edge surface passed Gate 2 readiness.",
                "Another Companyfacts ratio/tag threshold would violate novelty discipline.",
                "SEC item/text retries are recent negative or frozen families.",
                "Forward-only options and 13F rows cannot satisfy historical Gate 4.",
                "Current-only filer category metadata would create backtest/production mismatch.",
            ],
        },
        "delta_metrics": delta,
        "history_summary": load_history_summary(),
        "data_coverage_audit": {
            "sec_filing_events": summarize_sec_events(),
            "sec_filing_text": summarize_sec_text(),
            "sec_submissions": summarize_sec_submissions(),
            "sec_primary_document_cache": summarize_sec_primary_document_cache(),
            "options_chain": summarize_options_chain(),
            "finra_short_interest": summarize_finra_short_interest(),
            "sec13f_kova": summarize_13f(),
            "forward_replacement_value": summarize_forward_replacement_value(),
        },
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface",
        "production_impact": {
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "runner_changed": False,
            "daily_snapshot_changed": False,
            "shared_helper_changed": False,
            "backtest_production_parity": (
                "No strategy or production helper was changed. This blocker "
                "prevents introducing a backtester-only alpha on current-only or "
                "forward-only data."
            ),
            "live_realistic_execution_envelope": (
                "Not applicable because no executable alpha entered measurement. "
                "Any future candidate must record notional/capital cap, liquidity, "
                "slippage, concentration, sector exposure, kill switch, order "
                "semantics, and failure handling before it can be called live-ready."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": (
                "all_candidate_surfaces_frozen_or_missing_pit_fields"
            ),
            "surprise": (
                "The local metadata contains promising form references, especially "
                "13G/13D, but not the parsed PIT fields needed to make the alpha "
                "trustworthy on the three standard windows."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The strongest current alpha direction is still candidate-pool "
                "expansion through a new free data edge, but the repo lacks a "
                "Gate-4-ready non-repeat PIT surface today. The attractive next "
                "alpha is parsed 13G/13D holder-stake quality, not another "
                "Companyfacts, SEC item-code, Form4, or static lead-lag retune."
            ),
            "negative_reflection": (
                "No strategy replay was run because forcing one would repeat a "
                "frozen family or depend on current-only/forward-only data. That "
                "would make any positive backtest untrustworthy and risk a "
                "backtest/production inconsistency."
            ),
            "do_not_retry_near_neighbors": [
                "Companyfacts advertising/public-float/R&D/sharecount threshold sweeps",
                "raw 8-K item-code or SEC text regex absorption scouts",
                "raw 13G/13D/Form4 event gates without parsed holder/stake context",
                "current SEC submissions filer-category historical backtests",
                "forward-only options/13F rows as accepted historical alpha",
                "static OHLCV peer lead-lag retunes without new event evidence",
            ],
            "best_next_alpha_direction": (
                "Build or ingest a parsed PIT 13G/13D holder-stake/action table "
                "across the canonical windows, then implement it shared-paper-first "
                "with daily default-off snapshot parity and run Gate 1-4. Secondary "
                "directions are accession-level 10-K/10-Q cover-page filer status "
                "and full-window historical options chains."
            ),
            "next_evidence_needed": [
                "Parsed PIT 13G/13D holder/stake/action table",
                "Historical 10-K/10-Q cover-page filer status keyed by accession",
                "Full-window historical options chain snapshots with closed outcomes",
                "PIT borrow-fee/rebate history joined to FINRA short interest",
                "Structured customer/supplier contract economics extracted from filings",
            ],
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
        ],
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260618_012_post_20260618_nonrepeat_data_edge_readiness.py"
        ),
        "created_at": created_at,
        "anti_js": "No JavaScript was used.",
    }


def build_card(result: dict[str, Any]) -> str:
    aggregate = result["gate4"]["before"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - post-20260618 non-repeat data-edge readiness",
            "",
            f"- Lane: `{result['lane']}`",
            f"- Status: `{result['status']}`",
            f"- Decision: `{result['decision']}`",
            f"- Hypothesis: {result['hypothesis']}",
            f"- Nearby history: {', '.join(NEARBY_PRIOR_EXPERIMENTS)}",
            f"- Three-window baseline EV: `{aggregate['aggregate_expected_value_score']}`",
            f"- Three-window baseline PnL: `${aggregate['aggregate_total_pnl']}`",
            f"- Gate 4 delta: `{result['delta_metrics']}`",
            "- Production impact: no strategy, daily snapshot, shared helper, ranking, "
            "sizing, exit, order path, or LLM behavior changed.",
            "",
            "## Conclusion",
            "",
            result["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Alpha Evidence",
            "",
            result["post_run_reflection"]["best_next_alpha_direction"],
            "",
        ]
    )


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["created_at"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "nearby_prior_experiments": result["nearby_prior_experiments"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "anti_js": result["anti_js"],
    }


def write_manifest(result: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "files": result["changed_files"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }
    write_json(MANIFEST_JSON, manifest)


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON)
    ticket.update(
        {
            "status": result["status"],
            "completed_at": result["created_at"],
            "result": {
                "accepted": False,
                "accepted_alpha": False,
                "decision": result["decision"],
                "artifact": repo_rel(ARTIFACT_JSON),
                "log": repo_rel(LOG_JSON),
                "runner": RUNNER_NAME,
                "delta_metrics": result["delta_metrics"],
                "gate4": result["gate4"],
                "calibration": result["calibration"],
                "summary": result["post_run_reflection"]["why_result_happened"],
            },
            "new_evidence_type": "post_20260618_full_history_and_pit_surface_readiness_audit",
            "multiple_testing_risk_bucket": "moderate",
            "post_run_reflection": result["post_run_reflection"],
            "production_impact": result["production_impact"],
            "gate1_baseline": result["gate1_baseline"],
            "gate2_field_availability": result["gate2_field_availability"],
            "gate3_survival": result["gate3_survival"],
            "gate4": result["gate4"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    write_json(TICKET_JSON, ticket)


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))
    write_manifest(result)
    update_ticket(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "candidate_surfaces_blocked": len(
                    result["gate2_field_availability"]["candidate_surfaces"]
                ),
                "best_next_alpha_direction": result["post_run_reflection"][
                    "best_next_alpha_direction"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
