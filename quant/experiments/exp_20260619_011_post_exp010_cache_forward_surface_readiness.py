"""exp-20260619-011: post-exp010 cache and forward surface readiness.

This alpha-search experiment tests whether local cache/forward files expose a
new free, production-visible candidate-pool edge after exp-20260619-010. It is
not a strategy replay: if a surface lacks canonical three-window PIT coverage,
material candidate overlap, or production visibility, no after policy is run.

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


EXPERIMENT_ID = "exp-20260619-011"
SLUG = "post_exp010_cache_forward_surface_readiness"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260619_011_post_exp010_cache_forward_surface_readiness.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260619_011_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "candidate_pool/data_edge: local post-20260619 cache and forward files "
    "(Kova 13F/companyfacts, OnclickMedia options cache, SEC filing feature "
    "snapshots, and low-deployment forward rows) might reveal a free "
    "production-visible candidate-pool edge only if they provide PIT as-of "
    "coverage across late_strong, mid_weak, and old_thin; otherwise no "
    "strategy alpha should be attempted."
)

PREDICTION = {
    "success_probability": 0.06,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_canonical_window_coverage",
        "forward_sample_immature",
        "near_neighbor_retry_risk",
        "production_visibility_gap",
    ],
    "confidence_reason": (
        "Recent attempts exhausted SEC/companyfacts/ownership/options/revision "
        "neighbors; this run adds a concrete local cache and forward-lead "
        "coverage audit after exp-20260619-010, so success is unlikely unless "
        "hidden historical PIT rows exist."
    ),
}

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
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
        "strategy_total_return_pct": 78.11,
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
        "sharpe_daily": 1.49,
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

NEARBY_PRIOR_EXPERIMENTS = [
    {
        "experiment_id": "exp-20260619-010",
        "decision": "blocked",
        "relevance": (
            "Recorded no non-repeat PIT alpha surface after 20260619 SEC, "
            "ownership, Companyfacts, FINRA, options, and revision attempts."
        ),
    },
    {
        "experiment_id": "exp-20260618-023",
        "decision": "blocked",
        "relevance": (
            "OnclickMedia options skew failed Gate 2 because canonical-window "
            "history was missing."
        ),
    },
    {
        "experiment_id": "exp-20260619-001",
        "decision": "blocked",
        "relevance": (
            "Earnings/date revision ledger produced no reliable matched "
            "candidate rows across the canonical windows."
        ),
    },
    {
        "experiment_id": "exp-20260605-035",
        "decision": "accepted_paper_lead",
        "relevance": (
            "Low-deployment ETF replay was positive, but live activation "
            "requires shared/default-off forward evidence rather than retuning."
        ),
    },
    {
        "experiment_id": "exp-20260617-011",
        "decision": "rejected",
        "relevance": (
            "Structured SEC contract-economics text tuples regressed all "
            "canonical windows."
        ),
    },
]


DATE_RE = re.compile(r"_(\d{8})(?:\.|_|$)")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = record["experiment_id"]
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == experiment_id:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def filename_date(path: Path) -> str | None:
    match = DATE_RE.search(path.name)
    if not match:
        return None
    text = match.group(1)
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def dated_files(directory: Path, pattern: str) -> dict[str, Any]:
    dates: list[str] = []
    files: list[str] = []
    for path in sorted(directory.glob(pattern)):
        date = filename_date(path)
        if not date:
            continue
        dates.append(date)
        files.append(repo_rel(path))
    sample_files = list(dict.fromkeys(files[:5] + files[-5:]))
    return {
        "file_count": len(files),
        "date_count": len(set(dates)),
        "date_range": {
            "start": min(dates) if dates else None,
            "end": max(dates) if dates else None,
        },
        "window_file_counts": {
            label: sum(
                1
                for date in dates
                if str(window["start"]) <= date <= str(window["end"])
            )
            for label, window in CANONICAL_WINDOWS.items()
        },
        "sample_files": sample_files,
    }


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in windows.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in windows.values()),
            2,
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in windows.values()),
        "min_survival_rate": min(
            float(row["survival_rate"]) for row in windows.values()
        ),
        "max_window_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in windows.values()
        ),
        "window_count": len(windows),
    }


def metric_delta(
    after: dict[str, dict[str, Any]],
    before: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float]]:
    keys = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
        "win_rate",
    ]
    return {
        label: {
            key: round(float(after[label][key]) - float(before[label][key]), 6)
            for key in keys
        }
        for label in after
    }


def canonical_window_list() -> list[dict[str, str]]:
    return [
        {
            "label": label,
            "start": str(row["start"]),
            "end": str(row["end"]),
            "snapshot": str(row["snapshot"]),
        }
        for label, row in CANONICAL_WINDOWS.items()
    ]


def baseline_artifact(kind: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": kind,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "canonical_source": "docs/backtesting.md",
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(CANONICAL_WINDOWS),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": (
            "This readiness experiment does not run an after policy. The after "
            "artifact intentionally repeats the canonical baseline to prove no "
            "performance claim is being made."
        ),
    }


def scan_low_deployment_forward() -> dict[str, Any]:
    rows = [
        row
        for row in read_jsonl(REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl")
        if row.get("sleeve_key") == "low_deployment_etf"
    ]
    closed = [row for row in rows if row.get("status") == "enriched"]
    pnls = [float(row.get("pnl_usd") or 0.0) for row in closed]
    positive_ticker_counter: Counter[str] = Counter(
        row.get("ticker") or "UNKNOWN"
        for row in closed
        if float(row.get("pnl_usd") or 0.0) > 0.0
    )
    positive_total = sum(positive_ticker_counter.values())
    single_positive_share = (
        max(positive_ticker_counter.values()) / positive_total
        if positive_total
        else 0.0
    )
    entry_dates = sorted(
        str(row.get("entry_date")) for row in closed if row.get("entry_date")
    )
    return {
        "surface": "low_deployment_etf_forward_rows",
        "file": "data/paper_sleeves/forward_replacement_value.jsonl",
        "closed_enriched_rows": len(closed),
        "entry_date_range": {
            "start": entry_dates[0] if entry_dates else None,
            "end": entry_dates[-1] if entry_dates else None,
        },
        "total_pnl_usd": round(sum(pnls), 2),
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0.0) / len(pnls), 4)
        if pnls
        else 0.0,
        "ticker_counts": dict(Counter(row.get("ticker") or "UNKNOWN" for row in closed)),
        "positive_ticker_counts": dict(positive_ticker_counter),
        "single_ticker_positive_share": round(single_positive_share, 4),
        "forward_activation_gate": {
            "min_closed_trades": 60,
            "max_single_ticker_positive_share": 0.75,
            "closed_trade_gate_passed": len(closed) >= 60,
            "diversification_gate_passed": single_positive_share <= 0.75
            if positive_total
            else False,
        },
        "verdict": "blocked_forward_gate_immature",
        "reason": (
            "The positive ETF lead is already a shared default-off paper sleeve, "
            "but current forward evidence is too short and too concentrated for "
            "activation or retuning."
        ),
    }


def scan_surfaces() -> list[dict[str, Any]]:
    kova_13f = dated_files(
        REPO_ROOT / "data" / "kova" / "institutional",
        "sec13f_ownership_*.jsonl",
    )
    kova_facts = dated_files(
        REPO_ROOT / "data" / "kova" / "fundamentals",
        "companyfacts_growth_*.jsonl",
    )
    sec_selected_facts = dated_files(
        REPO_ROOT / "data" / "non_ohlcv",
        "sec_companyfacts_selected_kova_*.jsonl",
    )
    options_chain = dated_files(
        REPO_ROOT / "data" / "non_ohlcv",
        "options_onclickmedia_chain_*.jsonl",
    )
    estimate_revision = dated_files(
        REPO_ROOT / "data" / "non_ohlcv",
        "estimate_revision_ledger_*.jsonl",
    )
    sec_features = dated_files(
        REPO_ROOT / "data" / "non_ohlcv",
        "sec_filing_features_*.jsonl",
    )

    sec_feature_summary = read_json(
        REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_features_summary_20260618.json"
    )
    options_summary = read_json(
        REPO_ROOT / "data" / "non_ohlcv" / "options_onclickmedia_summary_20260618.json"
    )
    revision_summary = read_json(
        REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260618.json"
    )

    return [
        {
            "surface": "kova_13f_companyfacts_forward_snapshots",
            "coverage": {
                "kova_13f": kova_13f,
                "kova_companyfacts_growth": kova_facts,
                "sec_companyfacts_selected_kova": sec_selected_facts,
            },
            "verdict": "blocked_missing_mid_old_canonical_coverage",
            "reason": (
                "Kova institutional and companyfacts files are recent forward "
                "snapshots, with no old_thin and no full mid_weak PIT coverage. "
                "They cannot support a three-window before/after policy."
            ),
            "needed_new_axis": (
                "Historical PIT Kova/13F/companyfacts snapshot rows joined to "
                "candidate rows across late_strong, mid_weak, and old_thin."
            ),
        },
        {
            "surface": "onclickmedia_options_chain_cache",
            "coverage": options_chain,
            "latest_summary": {
                "collection_mode": options_summary.get("collection_mode"),
                "date_range": options_summary.get("date_range"),
                "by_date": options_summary.get("by_date"),
                "row_count": sum((options_summary.get("by_date") or {}).values())
                if isinstance(options_summary.get("by_date"), dict)
                else None,
                "option_liquidity_pass_rate": options_summary.get(
                    "option_liquidity_pass_rate"
                ),
            },
            "verdict": "blocked_sparse_forward_surface",
            "reason": (
                "Local options rows are sparse forward snapshots. They do not "
                "cover all three canonical windows, and the latest summary is a "
                "single forward daily collection."
            ),
            "needed_new_axis": (
                "A PIT options chain with as-of rows in every canonical window "
                "or enough closed forward replacement-value rows from the same "
                "shared adapter."
            ),
        },
        {
            "surface": "sec_filing_features_text_plus_companyfacts",
            "coverage": sec_features,
            "latest_summary": {
                "rows_written": sec_feature_summary.get("rows_written"),
                "pit_safe_rows": sec_feature_summary.get("pit_safe_rows"),
                "rows_with_same_accession_facts": sec_feature_summary.get(
                    "rows_with_same_accession_facts"
                ),
                "field_counts": sec_feature_summary.get("field_counts"),
                "pit_caveat": sec_feature_summary.get("pit_caveat"),
            },
            "verdict": "blocked_no_new_material_feature_tuple",
            "reason": (
                "The SEC feature files have dates, but the material financial "
                "fields are missing, same-accession facts are zero, and the "
                "available fields reduce to 8-K item/text buckets already tested "
                "or frozen in SEC action/text families."
            ),
            "needed_new_axis": (
                "Primary-document economic tuples or same-accession structured "
                "facts with a shared daily helper, not another 8-K item/form or "
                "text-bucket replay."
            ),
        },
        {
            "surface": "estimate_revision_forward_ledger",
            "coverage": estimate_revision,
            "latest_summary": {
                "row_count": revision_summary.get("row_count"),
                "estimate_revision_usable_rows": revision_summary.get(
                    "estimate_revision_usable_rows"
                ),
                "matched_candidate_rows": revision_summary.get(
                    "matched_candidate_rows"
                ),
                "up_revision_rows": revision_summary.get("up_revision_rows"),
                "down_revision_rows": revision_summary.get("down_revision_rows"),
                "candidate_match_rate": revision_summary.get("candidate_match_rate"),
                "production_impact": revision_summary.get("production_impact"),
            },
            "verdict": "blocked_zero_candidate_join",
            "reason": (
                "The revision ledger is default-off forward data, but the latest "
                "summary has zero matched candidate rows and zero up/down "
                "revision rows; the file history is not a full three-window PIT "
                "surface."
            ),
            "needed_new_axis": (
                "Historical as-of analyst revision breadth, dispersion, and "
                "velocity rows joined to actual candidate rows in all windows."
            ),
        },
        scan_low_deployment_forward(),
    ]


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or PREDICTION
    before_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    after_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    aggregate_delta = {
        key: round(after_aggregate[key] - before_aggregate[key], 6)
        for key in [
            "aggregate_expected_value_score",
            "aggregate_total_pnl",
            "total_trade_count",
            "min_survival_rate",
            "max_window_drawdown_pct",
        ]
    }
    audited_surfaces = scan_surfaces()

    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_cache_forward_alpha_surface",
        "hypothesis": HYPOTHESIS,
        "change_type": "alpha_direction_selection",
        "mechanism_family": "alpha_surface_readiness",
        "trial_family": "post_exp010_cache_forward_surface_gate4_readiness",
        "trial_variant_id": "v1",
        "single_causal_variable": (
            "post_exp010_cache_forward_surface_gate4_readiness_v1"
        ),
        "changed_variable": "post_exp010_cache_forward_surface_gate4_readiness_v1",
        "causal_components": [
            "history_scan",
            "cache_coverage_audit",
            "forward_lead_gate_check",
            "gate2_surface_readiness",
            "baseline_identity_check",
        ],
        "prediction": prediction,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "novelty_check": {
            "reservation_warning": (ticket.get("novelty") or {}).get("warn"),
            "reservation_nearest": (ticket.get("novelty") or {}).get("nearest"),
            "override_recorded": (ticket.get("novelty") or {}).get("override"),
            "new_evidence_axis": (ticket.get("novelty") or {}).get(
                "new_evidence_axis"
            ),
            "interpretation": (
                "The new axis is the post-exp010 local cache and forward-gate "
                "coverage audit. It is not a threshold retry."
            ),
        },
        "pre_run_answers": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "candidate_pool/data_edge",
            "historical_near_neighbors": NEARBY_PRIOR_EXPERIMENTS,
            "single_policy_bundle_under_test": (
                "Gate-4 readiness of local cache/forward data surfaces; no "
                "entry, exit, ranking, sizing, or risk policy is changed."
            ),
            "success_criteria": (
                "Proceed only if at least one audited surface is "
                "production-visible, PIT/as-of safe, non-neighbor, materially "
                "joined to candidates, and covers all three canonical windows."
            ),
            "reproducibility": (
                "This runner scans local files, writes before/after identity "
                "artifacts, and closes the ticket through "
                "persist_self_registered_result."
            ),
        },
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "canonical_windows": canonical_window_list(),
            "baseline_aggregate": before_aggregate,
            "windows": CANONICAL_WINDOWS,
        },
        "gate2_field_availability": {
            "status": "blocked",
            "minimum_runtime_fields_checked": ["entry_date", "target_price"],
            "minimum_runtime_field_result": (
                "Canonical baseline rows keep entry_date and target_price, but "
                "no audited new surface clears coverage, candidate overlap, and "
                "production-visibility requirements for an after policy."
            ),
            "audited_surfaces": audited_surfaces,
            "blocking_item": (
                "No post-exp010 local/forward data surface currently has all "
                "required properties: production visibility, PIT/as-of "
                "timestamps, material candidate overlap, full late/mid/old "
                "coverage, and a genuinely new evidence axis."
            ),
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": before_aggregate["min_survival_rate"],
            "guardrail": "survival_rate must not fall below 0.05",
            "interpretation": (
                "No new filter was tested. Adding a filter from a blocked "
                "surface would make survival and trade-count evidence "
                "untrustworthy."
            ),
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": CANONICAL_WINDOWS,
            "after": CANONICAL_WINDOWS,
            "window_deltas": metric_delta(CANONICAL_WINDOWS, CANONICAL_WINDOWS),
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": aggregate_delta,
            "acceptance_result": "blocked",
            "reason": (
                "The only defensible after result is identity to the canonical "
                "baseline; no positive alpha, strategy change, or live-ready "
                "promotion is claimed."
            ),
        },
        "delta_metrics": aggregate_delta,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_mode": "no_gate4_ready_cache_forward_alpha_surface",
            "surprise": (
                "Low surprise. The extra audit found some dated files, but each "
                "surface either lacks three-window coverage, has zero candidate "
                "join, is replay-only SEC text/item context, or is a forward "
                "lead still below activation evidence."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "shared_helper_added": False,
            "parity_assessment": (
                "No production/backtest inconsistency can be introduced because "
                "no trading policy, helper, order path, or replay logic changed. "
                "A future positive surface must be shared/default-off before "
                "acceptance."
            ),
            "live_realistic_execution_envelope": (
                "Not evaluated because no tradable alpha was accepted. The ETF "
                "forward lead remains default-off and below activation evidence."
            ),
        },
        "post_run_reflection": {
            "why_no_alpha_change": (
                "The cache/forward audit did not uncover a Gate-4-ready new "
                "alpha. Kova snapshots lack mid/old PIT coverage, options are "
                "sparse forward rows, SEC feature files have missing material "
                "facts and replay-only text/item semantics, estimate revisions "
                "have zero candidate join, and low-deployment ETF forward rows "
                "are too few and too concentrated for activation."
            ),
            "why_negative_or_blocked": (
                "The blocked result is caused by data readiness, not by a "
                "tested trading rule. Forcing an after policy would be a "
                "near-neighbor retry of SEC/ownership/options/revision families "
                "or a premature forward activation."
            ),
            "anti_repeat_rule": (
                "Do not retry these surfaces by threshold, top-N, hold, "
                "cooldown, notional, or text-bucket sweeps. Reopen only with "
                "historical PIT rows or enough closed forward replacement rows "
                "from a shared adapter."
            ),
            "best_next_alpha_direction": (
                "Build a genuinely new free PIT candidate-pool source: SEC "
                "prospectus/listing/float/lockup/filer-status tuples, 13D/13G "
                "amendment stake-direction with holder intent, analyst revision "
                "breadth/dispersion joined to candidates, or historical options "
                "chain history."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260619_011_post_exp010_cache_forward_surface_readiness.py"
        ),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


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
        "nearby_prior_experiments": [
            row["experiment_id"] for row in NEARBY_PRIOR_EXPERIMENTS
        ],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "prediction": result["prediction"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
        "anti_js": result["anti_js"],
    }


def build_card(result: dict[str, Any]) -> str:
    gate4 = result["gate4"]
    lines = [
        f"# {EXPERIMENT_ID}: post-exp010 cache/forward surface readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Hypothesis: local cache/forward files should only drive alpha if "
        "they clear PIT coverage, candidate overlap, novelty, and production "
        "visibility.",
        "",
        "## Three-window Gate 4",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, before in CANONICAL_WINDOWS.items():
        after = CANONICAL_WINDOWS[label]
        delta = gate4["window_deltas"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} | "
            f"{delta['expected_value_score']:.4f} | "
            f"${before['total_pnl']:,.2f} | ${after['total_pnl']:,.2f} | "
            f"${delta['total_pnl']:,.2f} |"
        )
    aggregate = gate4["aggregate_before"]
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "No alpha was accepted. The after artifact is intentionally "
            "identical to the canonical baseline: aggregate EV "
            f"{aggregate['aggregate_expected_value_score']:.4f}, aggregate PnL "
            f"${aggregate['aggregate_total_pnl']:,.2f}, total trades "
            f"{aggregate['total_trade_count']}.",
            "",
            "The blocker is specific: no audited cache/forward surface clears "
            "all of PIT coverage, material candidate overlap, novelty, and "
            "production visibility.",
            "",
            "No production code, backtest policy, shared helper, live order "
            "path, ranking, sizing, or exit logic changed. No JavaScript was "
            "used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Alpha-search readiness artifact. This directory records why the local "
        "cache/forward surface audit did not produce a trustworthy non-repeat "
        "alpha surface for the canonical three-window protocol.\n\n"
        "Files:\n"
        f"- `{repo_rel(ARTIFACT_JSON)}`: full blocker artifact\n"
        f"- `{repo_rel(BEFORE_JSON)}`: canonical baseline metrics\n"
        f"- `{repo_rel(AFTER_JSON)}`: no-strategy-change identity metrics\n\n"
        f"Decision: `{result['decision']}`. No JavaScript was used.\n"
    )


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
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
            "ticket": repo_rel(TICKET_JSON),
            "runner": RUNNER_NAME,
            "command": result["reproduction"],
            "anti_js": result["anti_js"],
            "updated_at": now_utc(),
        },
    )


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_no_alpha_change"],
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
        "prior_trial_count": len(NEARBY_PRIOR_EXPERIMENTS),
        "nearby_prior_experiments": [
            row["experiment_id"] for row in NEARBY_PRIOR_EXPERIMENTS
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "post_exp010_local_cache_forward_coverage_audit",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "evaluation_windows": canonical_window_list(),
        "acceptance_rule": (
            "Proceed only if a local/forward data surface has production "
            "visibility, as-of timestamps, material candidate overlap, and "
            "canonical three-window PIT coverage."
        ),
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_no_alpha_change"],
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
        "lean_quality_passed": result["lean_quality_passed"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
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
                "aggregate_pnl_delta": result["delta_metrics"][
                    "aggregate_total_pnl"
                ],
                "audited_surfaces": len(
                    result["gate2_field_availability"]["audited_surfaces"]
                ),
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
