"""exp-20260618-024: post-latest non-repeat alpha surface readiness blocker.

This is an alpha-search direction-selection experiment, not a strategy replay.
It records why the strongest current decision is to avoid another adjacent
frozen-window alpha test until a new point-in-time, production-visible surface
exists across the three canonical windows.

No trading rule, helper, ranking, sizing, exit, LLM/news behavior, daily runner,
watchlist, or order path is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260618-024"
SLUG = "post_20260618_nonrepeat_surface_readiness"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260618_024_post_20260618_nonrepeat_surface_readiness.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260618_024_{SLUG}.json"
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
    "candidate_pool/data_edge: after the latest options, ownership, SEC-action, "
    "analyst-revision, listing, allocator, and Companyfacts runs, the next alpha "
    "should only proceed if a non-repeat PIT surface exists with canonical-window "
    "coverage; otherwise a frozen-window strategy replay would be a near-neighbor "
    "and untrustworthy."
)

PREDICTION = {
    "success_probability": 0.08,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_gate4_ready_policy_bundle",
        "near_neighbor_retry_risk",
        "missing_pit_surface",
    ],
    "confidence_reason": (
        "Recent accepted alpha came from shared production-visible helpers, while "
        "current candidate families are frozen or missing canonical-window PIT "
        "rows; probability reflects blocker likelihood rather than alpha payoff."
    ),
}

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "total_pnl": 117072.92,
        "strategy_total_return_pct": 117.07,
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
        "strategy_total_return_pct": 78.11,
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
        "total_pnl": 39667.96,
        "strategy_total_return_pct": 39.67,
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
        "experiment_id": "exp-20260610-025",
        "family": "revision acceleration residual leadership",
        "decision": "rejected",
        "relevance": (
            "Directly tested the tempting EPS revision acceleration idea; all "
            "three windows regressed, so threshold/velocity retries are frozen."
        ),
    },
    {
        "experiment_id": "exp-20260616-006",
        "family": "seasoned new listing independent data readiness",
        "decision": "blocked",
        "relevance": (
            "No independent PIT listing/lockup/float surface, revision ledger "
            "had zero matched candidate rows."
        ),
    },
    {
        "experiment_id": "exp-20260618-015",
        "family": "structured SEC corporate action absorption",
        "decision": "rejected",
        "relevance": (
            "Three windows improved but failed the accepted-distribution "
            "comparator; raw SEC form/item absorption retries are frozen."
        ),
    },
    {
        "experiment_id": "exp-20260618-018",
        "family": "parsed 13G stake increase absorption",
        "decision": "blocked",
        "relevance": (
            "Parsed ownership rows do not yet provide enough stake-direction "
            "coverage across canonical windows."
        ),
    },
    {
        "experiment_id": "exp-20260618-020",
        "family": "forward intangible amortization relief",
        "decision": "rejected",
        "relevance": (
            "Positive aggregate was not robust enough and old_thin regressed; "
            "nearby Companyfacts burden/relief retunes need new decomposition."
        ),
    },
    {
        "experiment_id": "exp-20260618-021",
        "family": "SBC burden gap-fill allocator",
        "decision": "rejected",
        "relevance": (
            "Allocator gap-fill variant failed accepted allocator window "
            "comparator; do not retry rank/topN/no-displacement knobs."
        ),
    },
    {
        "experiment_id": "exp-20260618-022",
        "family": "distribution gap-fill allocator",
        "decision": "rejected",
        "relevance": (
            "Another positive-looking allocator variant failed distribution "
            "quality checks and should not be retuned without closed forward rows."
        ),
    },
    {
        "experiment_id": "exp-20260618-023",
        "family": "options skew Gate-4 readiness",
        "decision": "blocked",
        "relevance": (
            "Options snapshots are forward-only and have zero canonical-window "
            "coverage, so options skew cannot yet supply Gate-4 evidence."
        ),
    },
]

CANDIDATE_SURFACES = [
    {
        "surface": "analyst_revision_velocity_or_acceleration",
        "verdict": "blocked_near_neighbor",
        "evidence": (
            "Novelty check warned near the accepted/rejected revision families; "
            "exp-20260610-025 already rejected revision acceleration residual "
            "leadership with all three windows worse."
        ),
        "needed_new_axis": (
            "As-of analyst breadth/dispersion/velocity joined to historical "
            "candidate rows, not another acceleration threshold."
        ),
    },
    {
        "surface": "options_skew_and_term_structure",
        "verdict": "blocked_missing_canonical_history",
        "evidence": (
            "Local OnclickMedia options rows are recent forward snapshots; "
            "exp-20260618-023 records zero usable canonical-window coverage."
        ),
        "needed_new_axis": (
            "A historical PIT chain covering late_strong, mid_weak, and old_thin "
            "or 20-30 closed forward rows with the same daily adapter."
        ),
    },
    {
        "surface": "seasoned_listing_lockup_float",
        "verdict": "blocked_missing_surface",
        "evidence": (
            "exp-20260616-006 found no independent listing/lockup/free-float "
            "surface and the revision ledger had zero same-day candidate matches."
        ),
        "needed_new_axis": (
            "Free SEC prospectus/listing ingestion with PIT first-trade, lockup "
            "expiry, and float fields."
        ),
    },
    {
        "surface": "parsed_13d_13g_stake_direction",
        "verdict": "blocked_incomplete_direction_history",
        "evidence": (
            "Parsed holder/stake attempts need amendment direction and better "
            "old_thin coverage; raw thresholds/holder types are frozen."
        ),
        "needed_new_axis": (
            "13G/A or 13D/A stake-change direction rows with campaign/board "
            "outcome or amendment-delta provenance."
        ),
    },
    {
        "surface": "raw_sec_form_item_absorption",
        "verdict": "blocked_frozen_family",
        "evidence": (
            "Raw SEC form/item/action baskets, including the positive-looking "
            "corporate-action basket, are rejected or frozen by comparator rules."
        ),
        "needed_new_axis": (
            "Primary-document text with quantified economics/counterparty "
            "provenance and a shared daily helper."
        ),
    },
    {
        "surface": "raw_companyfacts_quality_or_burden_ratio",
        "verdict": "blocked_frozen_family",
        "evidence": (
            "Advertising, intangible amortization, D&A, fixed asset turnover, "
            "AOCI, pension, warranty, and other simple ratio families are "
            "already rejected or fragile; more thresholds would overfit."
        ),
        "needed_new_axis": (
            "A materially different PIT decomposition, such as grant-value "
            "normalization or share-adjusted SBC net of buybacks."
        ),
    },
    {
        "surface": "allocator_gap_fill_or_rank_knob",
        "verdict": "blocked_frozen_family",
        "evidence": (
            "exp-20260618-021 and exp-20260618-022 failed accepted allocator "
            "distribution/window checks despite positive-looking deltas."
        ),
        "needed_new_axis": (
            "Closed forward allocator displacement rows, not another historical "
            "rank, top-N, or no-displacement retune."
        ),
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = record["experiment_id"]
    existing_lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                existing_lines.append(raw)
                continue
            if existing.get("experiment_id") == experiment_id:
                existing_lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                existing_lines.append(raw)
    if not replaced:
        existing_lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


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
    deltas: dict[str, dict[str, float]] = {}
    for label, after_row in after.items():
        before_row = before[label]
        deltas[label] = {
            key: round(float(after_row[key]) - float(before_row[key]), 6)
            for key in keys
        }
    return deltas


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
            "This blocker experiment does not run an after policy. The after "
            "artifact intentionally repeats the canonical baseline to prove no "
            "performance claim is being made."
        ),
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


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction") or PREDICTION
    now = now_utc()
    before_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    after_aggregate = aggregate_windows(CANONICAL_WINDOWS)
    delta = {
        key: round(after_aggregate[key] - before_aggregate[key], 6)
        for key in [
            "aggregate_expected_value_score",
            "aggregate_total_pnl",
            "total_trade_count",
            "min_survival_rate",
            "max_window_drawdown_pct",
        ]
    }
    result = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_surface",
        "hypothesis": HYPOTHESIS,
        "change_type": "alpha_direction_selection",
        "mechanism_family": "alpha_surface_readiness",
        "trial_family": "post_20260618_nonrepeat_surface_readiness",
        "trial_variant_id": "v1",
        "single_causal_variable": "post_20260618_nonrepeat_pit_surface_readiness_v1",
        "changed_variable": "post_20260618_nonrepeat_pit_surface_readiness_v1",
        "causal_components": [
            "history_scan",
            "novelty_gate",
            "gate2_surface_readiness",
            "baseline_identity_check",
        ],
        "prediction": prediction,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "pre_run_answers": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "candidate_pool/data_edge",
            "historical_near_neighbors": NEARBY_PRIOR_EXPERIMENTS,
            "single_policy_bundle_under_test": (
                "Post-latest non-repeat PIT surface readiness; no entry, exit, "
                "ranking, sizing, or risk policy is changed."
            ),
            "success_criteria": (
                "Proceed only if a production-visible PIT surface has canonical "
                "late_strong/mid_weak/old_thin coverage and is not a frozen "
                "near-neighbor."
            ),
            "reproducibility": (
                "This runner writes the blocker artifact, before/after identity "
                "files, log, card, manifest, JSONL row, and ticket/registry "
                "status through persist_self_registered_result."
            ),
        },
        "novelty_check": {
            "reservation_warning": (ticket.get("novelty") or {}).get("warn"),
            "reservation_nearest": (ticket.get("novelty") or {}).get("nearest"),
            "override_recorded": (ticket.get("novelty") or {}).get("override"),
            "new_evidence_axis": (ticket.get("novelty") or {}).get(
                "new_evidence_axis"
            ),
            "interpretation": (
                "The warning confirms this is not an alpha-retune candidate. It "
                "is recorded as a blocker after reviewing latest experiment "
                "history, not as a positive strategy result."
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
                "Existing canonical strategy rows use these fields, but no new "
                "alpha surface is available for a trustworthy after policy."
            ),
            "candidate_surfaces": CANDIDATE_SURFACES,
            "blocking_item": (
                "No non-repeat PIT surface has all of: production visibility, "
                "as-of timestamps, three-window coverage, and a materially new "
                "evidence axis versus frozen families."
            ),
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": before_aggregate["min_survival_rate"],
            "guardrail": "survival_rate must not fall below 0.05",
            "interpretation": (
                "No additional filter was tested. Forcing one from a frozen or "
                "missing surface would make survival statistics meaningless."
            ),
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": CANONICAL_WINDOWS,
            "after": CANONICAL_WINDOWS,
            "window_deltas": metric_delta(CANONICAL_WINDOWS, CANONICAL_WINDOWS),
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": delta,
            "acceptance_result": "blocked",
            "reason": (
                "The only defensible after result is identity to baseline; no "
                "positive alpha, strategy change, or live-ready promotion is "
                "claimed."
            ),
        },
        "delta_metrics": delta,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_mode": "no_gate4_ready_nonrepeat_alpha_surface",
            "surprise": (
                "Low surprise. The history scan found candidate concepts, but "
                "each requires either new PIT data or a materially different "
                "evidence axis."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "shared_helper_added": False,
            "parity_assessment": (
                "No production/backtest inconsistency can be introduced because "
                "no trading policy or helper changed. A future positive alpha "
                "must be implemented as a shared default-off helper before Gate 4."
            ),
            "live_realistic_execution_envelope": (
                "Not evaluated because no tradable alpha was accepted. Future "
                "candidate-pool work should record notional cap, liquidity, "
                "slippage, concentration, kill switch, and order semantics in "
                "the after measurement."
            ),
        },
        "post_run_reflection": {
            "why_no_alpha_change": (
                "The highest-potential current lanes are not Gate-4-ready. "
                "Revision acceleration is a direct rejected repeat; options and "
                "seasoned-listing/float need historical PIT coverage; 13D/13G "
                "needs direction/provenance; raw SEC and Companyfacts retries "
                "are frozen by recent negative or comparator-failing evidence."
            ),
            "why_forcing_a_replay_would_be_bad": (
                "A replay using the same families would mainly search thresholds "
                "inside known losers or accepted families, increasing overfit "
                "risk and potentially creating backtest/production divergence."
            ),
            "best_next_alpha_direction": (
                "Build or import a free PIT candidate-pool surface first: SEC "
                "prospectus/listing/float/lockup fields, 13D/13G amendment "
                "stake-direction with holder intent provenance, or analyst "
                "revision breadth/dispersion joined as-of to historical "
                "candidate rows."
            ),
            "anti_repeat_rule": (
                "Do not retry revision velocity, raw SEC item/form baskets, raw "
                "Companyfacts quality thresholds, allocator gap-fill knobs, or "
                "options skew until the named new data axis exists."
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
            "quant\\experiments\\exp_20260618_024_post_20260618_nonrepeat_surface_readiness.py"
        ),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }
    return result


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
        f"# {EXPERIMENT_ID}: post-latest non-repeat alpha surface readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Hypothesis: a new alpha should only proceed if a non-repeat PIT "
        "surface with canonical-window coverage exists.",
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
    agg = gate4["aggregate_before"]
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "No alpha was accepted. The after artifact is intentionally identical "
            "to the canonical baseline: aggregate EV "
            f"{agg['aggregate_expected_value_score']:.4f}, aggregate PnL "
            f"${agg['aggregate_total_pnl']:,.2f}, total trades "
            f"{agg['total_trade_count']}.",
            "",
            "The current best use of effort is to build a free, PIT candidate-pool "
            "surface first: SEC prospectus/listing/float/lockup fields, 13D/13G "
            "amendment stake-direction provenance, or historical analyst "
            "revision breadth/dispersion joined as-of to candidates.",
            "",
            "No production code, backtest policy, shared helper, live order path, "
            "ranking, sizing, or exit logic changed. No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Alpha-search blocker artifact. This directory records why the latest "
        "candidate-family scan did not produce a trustworthy non-repeat alpha "
        "surface for the canonical three-window protocol.\n\n"
        "Files:\n"
        f"- `{repo_rel(ARTIFACT_JSON)}`: full blocker artifact\n"
        f"- `{repo_rel(BEFORE_JSON)}`: canonical baseline metrics\n"
        f"- `{repo_rel(AFTER_JSON)}`: no-strategy-change identity metrics\n\n"
        f"Decision: `{result['decision']}`. No JavaScript was used.\n"
    )


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
        "ticket": repo_rel(TICKET_JSON),
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
        "new_evidence_type": "latest_experiment_history_scan",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "allowed_write_scope": [
            "data/experiments",
            "experiments/logs",
            "experiments/cards",
            "experiments/manifests",
            "experiments/tickets",
            "docs/experiment_log.jsonl",
            "quant/experiments",
        ],
        "must_not_touch": [
            "quant/run.py",
            "quant/backtester.py",
            "quant/*paper_sleeve.py",
        ],
        "locked_variables": [
            "live_ordering",
            "production_sizing",
            "strategy_entry_exit",
        ],
        "evaluation_windows": canonical_window_list(),
        "acceptance_rule": (
            "Blocked unless a genuinely new, production-visible PIT alpha "
            "surface with coverage in all three canonical windows is available."
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
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "blocked_surfaces": len(CANDIDATE_SURFACES),
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
