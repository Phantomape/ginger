"""exp-20260615-005: preflight duplicate rejection for failed-breakdown reclaim.

The proposed alpha hypothesis was that liquid operating-company stocks that
undercut a prior range and reclaim it with relative strength might reflect
stop-run absorption. Preflight history found an exact near-neighbor,
exp-20260601-012 undercut/reclaim absorption, already rejected on the canonical
three windows. This runner records the rejection and broader non-repeat blocker
without changing strategy, production, ranking, sizing, exits, or live orders.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260615-005"
STEM = "failed_breakdown_reclaim_leadership"
OWNER = "alpha-search-automation"
DECISION = "rejected_preflight_duplicate_near_repeat"
STATUS = "rejected"

TRIAL_FAMILY = "failed_breakdown_reclaim_leadership_candidate_pool"
TRIAL_VARIANT_ID = "failed_breakdown_reclaim_leadership_candidate_source_v1"
CHANGED_VARIABLE = "failed_breakdown_reclaim_leadership_candidate_source_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CANONICAL_BASELINE = {
    "source": "docs/backtesting.md",
    "aggregate": {
        "expected_value_score_sum": 7.8941,
        "total_pnl_sum": 234850.99,
        "trade_count_sum": 61,
        "min_survival_rate": 0.7925,
        "max_drawdown_pct_max": 0.1119,
    },
    "by_window": {
        "late_strong": {
            "start": "2025-10-23",
            "end": "2026-04-21",
            "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            "expected_value_score": 5.1628,
            "sharpe_daily": 4.41,
            "total_pnl": 117072.92,
            "strategy_total_return_pct": 1.1707,
            "max_drawdown_pct": 0.0665,
            "trade_count": 18,
            "survival_rate": 0.8039,
        },
        "mid_weak": {
            "start": "2025-04-23",
            "end": "2025-10-22",
            "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            "expected_value_score": 2.1402,
            "sharpe_daily": 2.74,
            "total_pnl": 78110.11,
            "strategy_total_return_pct": 0.7811,
            "max_drawdown_pct": 0.1119,
            "trade_count": 21,
            "survival_rate": 0.7925,
        },
        "old_thin": {
            "start": "2024-10-02",
            "end": "2025-04-22",
            "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            "expected_value_score": 0.5911,
            "sharpe_daily": 1.49,
            "total_pnl": 39667.96,
            "strategy_total_return_pct": 0.3967,
            "max_drawdown_pct": 0.1001,
            "trade_count": 22,
            "survival_rate": 0.8667,
        },
    },
}

PRIOR_DUPLICATE = {
    "experiment_id": "exp-20260601-012",
    "decision": "rejected_undercut_reclaim_absorption_candidate_pool",
    "changed_variable": "undercut_reclaim_absorption_candidate_source_v1",
    "artifact": "experiments/logs/exp-20260601-012.json",
    "card": "experiments/cards/exp-20260601-012.md",
    "aggregate": {
        "before_expected_value_score_sum": 6.3596,
        "after_expected_value_score_sum": 5.8855,
        "expected_value_score_delta_sum": -0.4741,
        "before_total_pnl_sum": 192538.61,
        "after_total_pnl_sum": 186669.45,
        "total_pnl_delta_sum": -5869.16,
        "target_trade_count_sum": 97,
        "max_drawdown_delta_max": 0.0083,
    },
    "by_window": {
        "late_strong": {
            "before_expected_value_score": 4.1082,
            "after_expected_value_score": 3.6508,
            "expected_value_score_delta": -0.4574,
            "total_pnl_delta": -6349.32,
            "target_trade_count": 35,
        },
        "mid_weak": {
            "before_expected_value_score": 2.1405,
            "after_expected_value_score": 2.0996,
            "expected_value_score_delta": -0.0409,
            "total_pnl_delta": -1207.23,
            "target_trade_count": 29,
        },
        "old_thin": {
            "before_expected_value_score": 0.1109,
            "after_expected_value_score": 0.1351,
            "expected_value_score_delta": 0.0242,
            "total_pnl_delta": 1687.39,
            "target_trade_count": 33,
        },
    },
    "failed_reasons": [
        "aggregate_ev_not_positive",
        "aggregate_pnl_not_positive",
        "window_ev_regression",
        "window_pnl_regression",
        "drawdown_drift_too_high",
        "baseline_drift_blocks_promotion",
    ],
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_reversal_relabel",
        "window_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "preflight_duplicate_near_repeat",
    ],
    "confidence_reason": (
        "The ex-ante idea looked plausible as a PIT OHLCV stop-run absorption "
        "field, but history check found exp-20260601-012 already rejected the "
        "same undercut/reclaim mechanism across the canonical three windows."
    ),
    "recorded_at": "2026-06-15T03:09:01+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: liquid operating-company stocks that briefly undercut "
        "a prior range and reclaim it with positive relative strength may "
        "reflect supply exhaustion / stop-run absorption."
    ),
    "2_history_check": {
        "exp-20260601-012": (
            "Exact near-neighbor undercut/reclaim absorption already rejected: "
            "aggregate EV -0.4741, PnL -$5,869.16, late_strong and mid_weak "
            "regressed, max drawdown drift +0.83pp."
        ),
        "exp-20260605-033": "Rejected cross-section pressure/resilience candidate pool.",
        "exp-20260611-019": "Rejected adjacent price/pressure source family.",
        "exp-20260613-016": "Rejected overnight absorption leadership.",
        "exp-20260613-019": "Rejected related relation/microstructure candidate pool.",
        "exp-20260613-021": "Rejected adjacent scarce-leadership relation route.",
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. A runnable alpha "
        "must be non-repeat, PIT, production-visible or have a clear shared "
        "default-off parity path, improve aggregate EV/PnL without window "
        "regression, preserve survival, and avoid unacceptable drawdown drift."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_005_failed_breakdown_reclaim_leadership.py"
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    if not path.exists():
        path.write_text(line + "\n", encoding="utf-8")
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    marker = f'"experiment_id": "{EXPERIMENT_ID}"'
    replaced = False
    next_lines: list[str] = []
    for existing in lines:
        if marker in existing:
            if not replaced:
                next_lines.append(line)
                replaced = True
            continue
        next_lines.append(existing)
    if not replaced:
        next_lines.append(line)
    path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return proc.stdout.strip()


def noop_gate4() -> dict[str, Any]:
    rows = {}
    for label, metrics in CANONICAL_BASELINE["by_window"].items():
        rows[label] = {
            "before_expected_value_score": metrics["expected_value_score"],
            "after_expected_value_score": metrics["expected_value_score"],
            "expected_value_score_delta": 0.0,
            "before_total_pnl": metrics["total_pnl"],
            "after_total_pnl": metrics["total_pnl"],
            "strategy_total_pnl_delta": 0.0,
            "before_trade_count": metrics["trade_count"],
            "after_trade_count": metrics["trade_count"],
            "trade_count_delta": 0,
        }
    return {
        "passed": False,
        "decision": DECISION,
        "strategy_behavior_changed": False,
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "aggregate_trade_count_delta": 0,
        "by_window": rows,
        "failed_reasons": [
            "preflight_duplicate_near_repeat",
            "exact_prior_gate4_rejection",
            "running_backtest_would_duplicate_frozen_near_neighbor",
        ],
    }


def candidate_reviews() -> list[dict[str, Any]]:
    return [
        {
            "candidate": "failed_breakdown_reclaim_leadership",
            "alpha_hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "decision": "rejected_preflight_duplicate_near_repeat",
            "history_check": ["exp-20260601-012"],
            "why_not_run": (
                "The same undercut/reclaim absorption mechanism already lost "
                "two of three windows and worsened drawdown in exp-20260601-012."
            ),
            "retry_requires": (
                "A materially new PIT flow, options, borrow, event-quality, or "
                "forward replacement-value field; do not sweep reclaim thresholds."
            ),
        },
        {
            "candidate": "companyfacts_quality_extensions",
            "alpha_hypothesis": "Free SEC Companyfacts can improve candidate-pool quality when the field is orthogonal.",
            "decision": "blocked_frozen_neighborhood",
            "history_check": [
                "exp-20260528-017",
                "exp-20260614-020",
                "exp-20260614-025",
                "exp-20260615-002",
                "exp-20260615-003",
            ],
            "why_not_run": (
                "Recent cash-conversion, TTM accruals, asset-growth, and "
                "cash-backed asset-growth leads were positive but rejected on "
                "drawdown/window/comparator gates; obvious threshold retries are frozen."
            ),
            "retry_requires": "A sharper PIT discriminator or closed forward replacement rows.",
        },
        {
            "candidate": "sec_text_evidence_spans",
            "alpha_hypothesis": "Richer SEC text provenance can separate true fundamental catalysts from generic language.",
            "decision": "blocked_generic_or_comparator_captured",
            "history_check": ["exp-20260614-013", "exp-20260614-015", "exp-20260614-017", "exp-20260615-001"],
            "why_not_run": (
                "AI-demand, guidance-quality, dividend, and deleveraging/liquidity "
                "text variants were too sparse or failed the accepted SEC RS20 comparator."
            ),
            "retry_requires": "Less generic PIT semantic provenance with source spans and table/commentary separation.",
        },
        {
            "candidate": "ownership_or_form4_standalone_entries",
            "alpha_hypothesis": "Ownership disclosures may identify informed demand or crowding.",
            "decision": "blocked_delayed_or_frozen",
            "history_check": ["exp-20260613-014", "exp-20260613-017", "exp-20260614-018"],
            "why_not_run": (
                "13F and Form 4 standalone entry rules recently failed or are "
                "reserved for context until timing/cluster-quality evidence matures."
            ),
            "retry_requires": "Forward replacement value or a timing/provenance edge, not another count threshold.",
        },
        {
            "candidate": "llm_soft_ranking_or_estimate_revision",
            "alpha_hypothesis": "LLM/estimate semantics could add a non-price data edge.",
            "decision": "blocked_data_coverage_too_thin",
            "history_check": ["exp-20260614-012"],
            "why_not_run": (
                "Local estimate revision and LLM soft-ranking rows are too sparse "
                "for a credible three-window Gate 1-4 alpha launch."
            ),
            "retry_requires": "PIT breadth/dispersion/provenance rows across all canonical windows.",
        },
    ]


def build_payload() -> dict[str, Any]:
    now = utc_now()
    gate4 = noop_gate4()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": STATUS,
        "accepted": False,
        "accepted_alpha": False,
        "decision": DECISION,
        "lane": "alpha_search",
        "owner": OWNER,
        "change_type": "preflight_duplicate_alpha_rejection",
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Liquid sector-known stocks that briefly undercut a 20-day low and "
            "then reclaim the prior range with positive relative strength may "
            "reflect supply exhaustion/stop-run absorption."
        ),
        "prediction": PREDICTION,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_source": CANONICAL_BASELINE["source"],
            "aggregate_baseline": CANONICAL_BASELINE["aggregate"],
            "by_window_baseline": CANONICAL_BASELINE["by_window"],
        },
        "gate2": {
            "passed_for_noop_preflight_record": True,
            "entry_date_required_for_future_alpha": True,
            "target_price_required_for_future_alpha": True,
            "note": "No executable signal rows, target prices, exits, or orders were created.",
        },
        "gate3": {
            "filter_added": False,
            "survival_rate_min": CANONICAL_BASELINE["aggregate"]["min_survival_rate"],
            "survival_guard_passed": True,
        },
        "gate4": gate4,
        "prior_duplicate": PRIOR_DUPLICATE,
        "candidate_reviews": candidate_reviews(),
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "live_ready": False,
            "default_off_paper_only": False,
            "parity_note": (
                "No strategy or production path changed. A positive future "
                "alpha must be shared-paper-first with historical replay plus "
                "daily default-off snapshot parity."
            ),
        },
        "calibration": {
            "actual_success": 0,
            "actual_gate4_passed": False,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - 0.0) ** 2, 6),
            "failure_modes_observed": [
                "preflight_duplicate_near_repeat",
                "prior_window_regression",
                "prior_drawdown_drift",
            ],
            "predicted_failure_mode_hit": True,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The proposed failed-breakdown/reclaim alpha was not run because "
                "exp-20260601-012 already tested the same undercut/reclaim "
                "absorption mechanism and failed Gate 4: aggregate EV -0.4741, "
                "PnL -$5,869.16, two regressed windows, and drawdown drift +0.83pp."
            ),
            "why_no_strategy_experiment": (
                "A fresh strategy run would duplicate a frozen near-neighbor and "
                "would not create trustworthy new evidence under the experiment protocol."
            ),
            "why_negative_or_blocked": (
                "The negative conclusion is about alpha selection quality, not a "
                "software bug: current local evidence points away from another "
                "price-only reclaim rule."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry failed-breakdown, undercut/reclaim, overnight "
                "absorption, post-thrust pause, or gap/reclaim variants by "
                "sweeping lookbacks, volume, close-location, RS, hold, cooldown, "
                "or notional thresholds on the frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs a materially new PIT flow, options, borrow, "
                "event-quality, or closed forward replacement-value field, plus "
                "a shared default-off helper if the evidence is positive."
            ),
            "best_next_alpha_direction": (
                "Stop optimizing price-only reclaim/quality thresholds. The next "
                "high-potential alpha should add a new free PIT data edge: estimate "
                "breadth/dispersion/provenance, richer SEC evidence spans, or "
                "relation/ownership context with forward replacement-value rows."
            ),
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": repo_rel(Path(__file__)),
        "anti_js": "No JavaScript was used.",
    }


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "baseline_result_file": "docs/backtesting.md",
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "prior_duplicate": PRIOR_DUPLICATE,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": row["before_expected_value_score"],
                "expected_value_after": row["after_expected_value_score"],
                "expected_value_delta": row["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["strategy_total_pnl_delta"],
                "trade_count_before": row["before_trade_count"],
                "trade_count_after": row["after_trade_count"],
            }
            for label, row in payload["gate4"]["by_window"].items()
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": "No JavaScript was used.",
    }


def build_card(payload: dict[str, Any]) -> str:
    return f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "{STATUS}"
lane: "alpha_search"
change_type: "preflight_duplicate_alpha_rejection"
mechanism_family: "production_visible_free_ohlcv_relation_alpha"
trial_family: "{TRIAL_FAMILY}"
trial_variant_id: "{TRIAL_VARIANT_ID}"
changed_variable: "{CHANGED_VARIABLE}"
completed_at: "{payload["timestamp"]}"
tags:
  - "alpha_search"
  - "rejected"
  - "preflight_duplicate"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Rejected before running a strategy backtest. The proposed failed-breakdown/reclaim alpha is a near-repeat of `exp-20260601-012`, which already failed Gate 4 on the canonical three windows.

## Hypothesis

{payload["hypothesis"]}

## Prior Three-Window Result

| window | prior EV before | prior EV after | prior EV delta | prior PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 4.1082 | 3.6508 | -0.4574 | $-6,349.32 | 35 |
| mid_weak | 2.1405 | 2.0996 | -0.0409 | $-1,207.23 | 29 |
| old_thin | 0.1109 | 0.1351 | +0.0242 | $+1,687.39 | 33 |

Aggregate prior delta: EV `-0.4741`, PnL `$-5,869.16`, max drawdown drift `+0.83pp`.

## Gate 1-4 For This Run

- Gate 1: baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; runnable alpha launch rejected as duplicate.

## Decision

`{DECISION}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Best Next Direction

{payload["post_run_reflection"]["best_next_alpha_direction"]}

## Closeout

- Artifact: `{payload["artifact"]}`
- Log: `{payload["log"]}`
- Runner: `{payload["runner"]}`
- No JavaScript was used.
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": STATUS,
        "decision": DECISION,
        "generated_at": utc_now(),
        "anti_js": "No JavaScript was used.",
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
    }


def persist(payload: dict[str, Any]) -> None:
    log_record = build_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, payload)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": DECISION,
        "accepted": False,
        "accepted_alpha": False,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate4": payload["gate4"],
        "prior_duplicate": PRIOR_DUPLICATE,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260601-012",
            "exp-20260605-033",
            "exp-20260611-019",
            "exp-20260613-016",
            "exp-20260613-019",
            "exp-20260613-021",
        ],
        "multiple_testing_risk_bucket": "high_after_preflight_duplicate",
        "new_evidence_type": "none_preflight_duplicate",
        "decision": DECISION,
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=STATUS,
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(build_log_record(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
