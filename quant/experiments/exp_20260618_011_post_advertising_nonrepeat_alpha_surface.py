"""exp-20260618-011: post-advertising non-repeat alpha surface blocker.

This is an alpha-search direction-selection experiment, not a strategy replay.
It records why the next alpha should not be another adjacent Companyfacts,
SEC-item, Form4, ownership, options, borrow, or lead-lag retune after
exp-20260618-010 failed the standard three-window acceptance test.

No trading rule, helper, ranking, sizing, exit, LLM/news behavior, daily runner,
watchlist, or order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260618-011"
SLUG = "post_advertising_nonrepeat_alpha_surface"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260618_011_post_advertising_nonrepeat_alpha_surface.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260618_011_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

PREDICTION = {
    "success_probability": 0.10,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "all_candidate_surfaces_frozen_or_missing_pit_fields",
        "near_neighbor_retries_not_trustworthy",
        "no_shared_daily_helper_for_positive_replay",
    ],
    "confidence_reason": (
        "Recent accepted/frozen logs show Companyfacts, SEC item text, Form4, "
        "ownership, filer-status, options, and lead-lag lanes are either "
        "rejected or lack PIT fields; this checks before creating another "
        "untrustworthy strategy change."
    ),
}

NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260618-010",
    "exp-20260618-007",
    "exp-20260618-005",
    "exp-20260617-026",
    "exp-20260617-024",
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
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = record["experiment_id"]
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("experiment_id") == experiment_id:
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


def summarize_sec_aggregate_text() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
    rows = read_jsonl(path)
    forms = Counter((row.get("form") or row.get("form_type") or "") for row in rows)
    dates = [
        str(row.get("filing_date") or row.get("date") or row.get("accepted_date"))[:10]
        for row in rows
        if row.get("filing_date") or row.get("date") or row.get("accepted_date")
    ]
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "rows": len(rows),
        "form_counts": dict(forms.most_common()),
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "blocking_read": (
            "The fixed-window aggregate SEC text file contains only 8-K rows, "
            "so periodic-report cover-page or 10-K/10-Q text alphas would not "
            "be measured on the canonical three-window protocol."
        ),
    }


def summarize_sec_submissions() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
    files = sorted(root.glob("*.json")) if root.exists() else []
    categories: Counter[str] = Counter()
    recent_forms: Counter[str] = Counter()
    dates: list[str] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        categories[payload.get("category") or payload.get("filerCategory") or ""] += 1
        recent = (payload.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        filing_dates = recent.get("filingDate") or []
        for form, date in zip(forms, filing_dates):
            if form in {
                "4",
                "8-K",
                "10-K",
                "10-Q",
                "13D",
                "13G",
                "144",
                "S-8",
                "424B5",
                "NT 10-K",
                "NT 10-Q",
            }:
                recent_forms[form] += 1
                if date:
                    dates.append(str(date)[:10])
    return {
        "path": repo_rel(root),
        "exists": root.exists(),
        "submission_files": len(files),
        "top_level_categories": dict(categories.most_common()),
        "recent_target_form_counts": dict(recent_forms.most_common()),
        "min_recent_filing_date": min(dates) if dates else None,
        "max_recent_filing_date": max(dates) if dates else None,
        "blocking_read": (
            "Submissions JSON has useful recent form lists, but the top-level "
            "filer category is current metadata, not a point-in-time historical "
            "cover-page category keyed by accession/date."
        ),
    }


def summarize_options_chain() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "non_ohlcv"
    files = sorted(root.glob("options_onclickmedia_chain_*.jsonl"))
    dates = filename_dates(files)
    sample_rows = read_jsonl(files[-1]) if files else []
    tickers = {str(row.get("ticker")) for row in sample_rows if row.get("ticker")}
    return {
        "path_glob": "data/non_ohlcv/options_onclickmedia_chain_*.jsonl",
        "files": len(files),
        "min_snapshot_date": min(dates) if dates else None,
        "max_snapshot_date": max(dates) if dates else None,
        "latest_snapshot_rows": len(sample_rows),
        "latest_snapshot_unique_tickers": len(tickers),
        "latest_snapshot_sample_keys": sorted(sample_rows[0].keys()) if sample_rows else [],
        "blocking_read": (
            "Options snapshots are forward collection rows, not full canonical "
            "old_thin/mid_weak/late_strong historical chains with closed "
            "outcomes and shared daily adapter semantics."
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
    tickers = {str(row.get("ticker")) for row in rows if isinstance(row, dict) and row.get("ticker")}
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "rows": len(rows),
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "unique_tickers": len(tickers),
        "sample_keys": sorted(rows[0].keys()) if rows else [],
        "blocking_read": (
            "FINRA short-interest rows exist, but recent FINRA/borrow-pressure "
            "three-window attempts were rejected; actual borrow fee/rebate "
            "history is still absent."
        ),
    }


def summarize_13f() -> dict[str, Any]:
    root = REPO_ROOT / "data" / "kova" / "institutional"
    files = sorted(root.glob("sec13f_ownership_*.jsonl")) if root.exists() else []
    dates = filename_dates(files)
    latest_rows = read_jsonl(files[-1]) if files else []
    tickers = {str(row.get("ticker")) for row in latest_rows if row.get("ticker")}
    return {
        "path_glob": "data/kova/institutional/sec13f_ownership_*.jsonl",
        "files": len(files),
        "min_snapshot_date": min(dates) if dates else None,
        "max_snapshot_date": max(dates) if dates else None,
        "latest_rows": len(latest_rows),
        "latest_unique_tickers": len(tickers),
        "latest_sample_keys": sorted(latest_rows[0].keys()) if latest_rows else [],
        "blocking_read": (
            "Kova 13F rows are daily snapshot/status surfaces; they do not give "
            "a three-window PIT manager-holder initiation or stake-change "
            "surface beyond the already tested 13F families."
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
            "Forward replacement-value rows are useful for accepted paper "
            "monitoring, but 31 rows across 14 tickers are not enough to open a "
            "new broad candidate-pool alpha without a new evidence axis."
        ),
    }


def build_candidate_surfaces() -> list[dict[str, Any]]:
    return [
        {
            "surface": "parsed_13g_13d_holder_stake_quality",
            "alpha_hypothesis": (
                "Initial passive or activist stake disclosure could identify "
                "under-owned leaders with informed sponsorship."
            ),
            "status": "blocked_frozen_or_missing_parsed_pit_fields",
            "related_history": [
                "exp-20260612-015",
                "exp-20260612-016",
                "Form4/ownership frozen families in docs/frozen_families.jsonl",
            ],
            "gate2_required_fields": [
                "issuer ticker",
                "filing date",
                "holder identity",
                "stake percent",
                "initial/add/change classification",
                "PIT accession-level source",
            ],
            "why_not_executable_now": (
                "SEC submissions expose recent forms but not a parsed "
                "accession-level 13G/13D holder/stake event surface across the "
                "three canonical windows. Raw 13G/13D event retries are already "
                "frozen."
            ),
            "new_evidence_needed": (
                "A parsed PIT 13G/13D event table with holder, stake, action "
                "type, issuer ticker, and accession date."
            ),
        },
        {
            "surface": "pit_filer_status_or_accelerated_filer_transition",
            "alpha_hypothesis": (
                "Accelerated filer upgrades or emerging-growth exits could mark "
                "liquidity and disclosure-quality inflections."
            ),
            "status": "blocked_missing_pit_cover_page_category",
            "related_history": ["exp-20260618-007"],
            "gate2_required_fields": [
                "filing date",
                "accession number",
                "cover-page filer status",
                "issuer ticker",
                "PIT daily availability",
            ],
            "why_not_executable_now": (
                "The submissions cache contains current top-level category "
                "metadata. Using it for historical 2024-2026 windows would leak "
                "future filer status."
            ),
            "new_evidence_needed": (
                "Historical cover-page filer status parsed from each 10-K/10-Q "
                "accession and joined to the same date seen by production."
            ),
        },
        {
            "surface": "new_sec_item_or_filing_text_absorption",
            "alpha_hypothesis": (
                "Specific SEC text events can be mispriced when price absorbs "
                "the event slowly."
            ),
            "status": "blocked_recent_item_code_rejections",
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
                "The recent sequence of 8-K item/text scouts failed. The "
                "aggregate three-window SEC text file is 8-K only, so moving to "
                "10-K/10-Q text would change the data surface without a fixed "
                "measurement base."
            ),
            "new_evidence_needed": (
                "A materially new structured event tuple or LLM-labeled event "
                "field, not another item-code or regex gate."
            ),
        },
        {
            "surface": "options_skew_open_interest_candidate_pool",
            "alpha_hypothesis": (
                "Options skew and open interest could identify informed demand "
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
                "Options snapshots are recent forward rows and do not cover the "
                "old_thin standard window. Positive forward rows would be leads, "
                "not an accepted Gate-4 alpha."
            ),
            "new_evidence_needed": (
                "Historical PIT options chain snapshots covering all three "
                "standard windows, plus shared daily snapshot semantics."
            ),
        },
        {
            "surface": "borrow_fee_or_crowding_relief",
            "alpha_hypothesis": (
                "Borrow-fee relief or short-interest covering could improve "
                "candidate selection around crowded winners."
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
                "FINRA short-interest rows exist, but the non-duplicate edge "
                "would require borrow-fee or rebate history. That field is not "
                "available in the repository."
            ),
            "new_evidence_needed": (
                "Free or stored PIT borrow-fee/rebate data joined to FINRA "
                "short interest across the standard windows."
            ),
        },
        {
            "surface": "companyfacts_next_ratio_after_advertising",
            "alpha_hypothesis": (
                "A less-explored fundamentals ratio might improve the candidate "
                "pool after advertising efficiency failed."
            ),
            "status": "blocked_near_neighbor_frozen_companyfacts_family",
            "related_history": [
                "exp-20260618-010",
                "exp-20260617-026",
                "exp-20260617-001",
                "exp-20260617-002",
                "exp-20260616-003",
                "exp-20260614-029",
            ],
            "gate2_required_fields": [
                "filed-date Companyfacts value",
                "prior period value",
                "ticker",
                "entry date",
                "target price",
            ],
            "why_not_executable_now": (
                "The novelty gate classified this reservation as a Companyfacts "
                "near-neighbor. Recent Companyfacts runs mostly failed or are "
                "already accepted helpers; another tag/threshold sweep would be "
                "a multiple-testing retry, not a new edge."
            ),
            "new_evidence_needed": (
                "A genuinely new free fundamentals data source or a structured "
                "field not covered by prior Companyfacts ratio families."
            ),
        },
        {
            "surface": "public_float_or_supply_scarcity_retest",
            "alpha_hypothesis": (
                "Low float or scarce supply could increase squeeze-like upside "
                "for leaders."
            ),
            "status": "blocked_recent_rejection_and_concentration_failure",
            "related_history": ["exp-20260617-026"],
            "gate2_required_fields": [
                "PIT public float",
                "ticker",
                "volume/liquidity",
                "entry date",
                "target price",
            ],
            "why_not_executable_now": (
                "The recent public-float scout improved EV modestly but failed "
                "coverage and concentration standards. Retuning float thresholds "
                "would not add a new evidence axis."
            ),
            "new_evidence_needed": (
                "A broader PIT float/history source or a separate supply-demand "
                "field that fixes old_thin coverage and concentration."
            ),
        },
        {
            "surface": "static_ohlcv_or_intraindustry_lead_lag_direction",
            "alpha_hypothesis": (
                "Peer leadership or laggard catch-up could expand the candidate "
                "pool without paid data."
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
                "The latest lead-lag direction-stability experiment did not "
                "establish a robust direction. Repeating static OHLCV peer "
                "gates risks fitting the same windows."
            ),
            "new_evidence_needed": (
                "External PIT peer relationship evidence or a production-visible "
                "event trigger that explains the lead-lag direction."
            ),
        },
        {
            "surface": "13f_sponsorship_or_low_crowding_extension",
            "alpha_hypothesis": (
                "Institutional sponsorship changes could identify durable "
                "leaders or under-owned winners."
            ),
            "status": "blocked_snapshot_only_or_previously_tested",
            "related_history": [
                "exp-20260615-009",
                "exp-20260613-014",
                "exp-20260613-017",
            ],
            "gate2_required_fields": [
                "manager id",
                "issuer ticker",
                "as-of date",
                "filed date",
                "holding value/shares",
                "initiation/change classification",
            ],
            "why_not_executable_now": (
                "The current Kova 13F surface exposes daily status rows, not a "
                "new three-window manager-holder delta table. Prior 13F "
                "sponsorship/crowding attempts already cover the obvious shapes."
            ),
            "new_evidence_needed": (
                "A PIT 13F holding-delta table with manager identity, filing "
                "date, value/share changes, and closed outcomes."
            ),
        },
    ]


def build_result() -> dict[str, Any]:
    before_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    after_aggregate = dict(before_aggregate)
    delta = {
        key: round(after_aggregate[key] - before_aggregate[key], 4)
        if isinstance(after_aggregate[key], float)
        else after_aggregate[key] - before_aggregate[key]
        for key in before_aggregate
    }

    data_coverage = {
        "sec_aggregate_text": summarize_sec_aggregate_text(),
        "sec_submissions": summarize_sec_submissions(),
        "options_chain": summarize_options_chain(),
        "finra_short_interest": summarize_finra_short_interest(),
        "sec13f_kova": summarize_13f(),
        "forward_replacement_value": summarize_forward_replacement_value(),
    }

    candidate_surfaces = build_candidate_surfaces()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "status": "blocked",
        "lane": "alpha_search",
        "hypothesis": (
            "After exp-20260618-010 failed, the next alpha should only proceed "
            "if a non-repeat PIT production-visible data-edge surface is "
            "available for all three canonical windows."
        ),
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "nonrepeat_candidate_pool_data_edge_readiness",
        "trial_family": "post_companyfacts_advertising_alpha_direction",
        "trial_variant_id": "post_advertising_nonrepeat_surface_v1",
        "single_causal_variable": (
            "post_advertising_nonrepeat_alpha_surface_readiness_v1"
        ),
        "changed_variable": "post_advertising_nonrepeat_alpha_surface_readiness_v1",
        "causal_components": [
            "history_scan",
            "field_availability_audit",
            "standard_gate_baseline",
            "no_strategy_change_without_gate4_ready_pit_field",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "novelty_override_basis": (
            "Reservation was near-neighbor to Companyfacts candidate-pool "
            "families. Override is justified because this run does not tune a "
            "Companyfacts rule; it audits whether any non-repeat surface is "
            "ready after the advertising failure."
        ),
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
                "Every high-potential free-data surface found in the post-run "
                "history scan is either frozen/recently rejected or lacks the "
                "PIT fields needed for a production-visible shared helper."
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
                "No new filter was added, and baseline survival remains above "
                "the 5% floor in all three windows."
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
                "Another Companyfacts ratio/tag threshold would violate the novelty gate.",
                "SEC item/text retries are recent negative/frozen families.",
                "Positive private forward-only options/13F rows would not satisfy Gate 4.",
                "Proceeding with current-only filer category metadata would create a backtest/production mismatch.",
            ],
        },
        "delta_metrics": delta,
        "data_coverage_audit": data_coverage,
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface",
        "production_impact": {
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "runner_changed": False,
            "daily_snapshot_changed": False,
            "backtest_production_parity": (
                "No strategy or production helper was changed. The blocker "
                "prevents introducing a backtester-only alpha on current-only "
                "or forward-only data."
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
                "The history scan did find data files, but none created a new "
                "three-window PIT production-visible edge distinct from recent "
                "frozen families."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The free-data lanes with plausible edge have been worked hard. "
                "The remaining attractive ideas require new PIT structured data "
                "rather than another rule threshold: parsed ownership events, "
                "historical filer-status cover pages, full-window options chains, "
                "borrow-fee history, or structured customer/supplier economics."
            ),
            "negative_reflection": (
                "The alpha was not run because the candidate surfaces failed "
                "readiness before Gate 4. Forcing a replay anyway would either "
                "repeat frozen families or rely on current-only/forward-only "
                "data, producing an untrustworthy result."
            ),
            "do_not_retry_near_neighbors": [
                "Companyfacts advertising/public-float/R&D/sharecount threshold sweeps",
                "raw 8-K item-code or SEC text regex absorption scouts",
                "raw 13G/13D/Form4 event gates without parsed holder/stake context",
                "current SEC submissions filer-category historical backtests",
                "forward-only options/13F rows as accepted historical alpha",
                "static OHLCV peer lead-lag direction retunes without new event evidence",
            ],
            "best_next_alpha_direction": (
                "Create or ingest a new free PIT structured data table before "
                "the next alpha search: parsed 13G/13D holder-stake events are "
                "the highest-upside candidate, followed by accession-level "
                "10-K/10-Q cover-page filer status or full-window options "
                "chain history. Then implement shared-paper-first and run Gate 1-4."
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
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260618_011_post_advertising_nonrepeat_alpha_surface.py"
        ),
        "created_at": now_utc(),
        "anti_js": "No JavaScript was used.",
    }
    return result


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


def build_card(result: dict[str, Any]) -> str:
    aggregate = result["gate4"]["before"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - post-advertising non-repeat alpha surface",
            "",
            f"- Lane: `{result['lane']}`",
            f"- Status: `{result['status']}`",
            f"- Decision: `{result['decision']}`",
            f"- Hypothesis: {result['hypothesis']}",
            f"- Nearby history: {', '.join(NEARBY_PRIOR_EXPERIMENTS)}",
            f"- Three-window baseline EV: `{aggregate['aggregate_expected_value_score']}`",
            f"- Three-window baseline PnL: `${aggregate['aggregate_total_pnl']}`",
            f"- Gate 4 delta: `{result['delta_metrics']}`",
            "- Production impact: no strategy, daily snapshot, ranking, sizing, exit, "
            "order path, or LLM behavior changed.",
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


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
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
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "causal_components": result["causal_components"],
        "prior_trial_count": 9,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "post_advertising_full_history_and_pit_surface_readiness_audit",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_result_happened"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": result["delta_metrics"][
            "aggregate_expected_value_score"
        ],
        "aggregate_strategy_total_pnl_delta": result["delta_metrics"][
            "aggregate_total_pnl"
        ],
        "post_run_reflection": result["post_run_reflection"],
        "production_impact": result["production_impact"],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


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
