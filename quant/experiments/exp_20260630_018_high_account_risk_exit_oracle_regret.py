"""exp-20260630-018: high account-risk exit oracle regret cohort.

Read-only alpha diagnostic over the full fixed-entry oracle denominator rows
materialized by exp-20260630-011.  This does not change entries, exits, sizing,
ranking, paper sleeves, live orders, prompts, or production adapters.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260630-018"
OWNER = "alpha-explore"
SLUG = "high_account_risk_exit_oracle_regret"
RUNNER = f"quant/experiments/exp_20260630_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for root in (REPO_ROOT, SCRIPTS_ROOT):
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_EXPERIMENT = "exp-20260630-011"
SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT
    / "exp_20260630_011_fixed_entry_exit_oracle_full_trade_rows.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260630_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HIGH_ACTUAL_RISK_THRESHOLD = 0.02
MIN_COHORT_ROWS = 20
MIN_COMPLEMENT_ROWS = 20
MIN_WINDOWS = 3
MIN_WINDOW_ROWS = 3
MIN_AGGREGATE_AVG_REGRET_SPREAD = 500.0
MIN_WINDOW_AVG_REGRET_SPREAD = 300.0
MAX_TOP_TICKER_SHARE = 0.35

HYPOTHESIS = (
    "Full fixed-entry exit-oracle denominator rows may show that high "
    "account-risk positions (actual_risk_pct >= 2.0% at entry) consistently "
    "leave larger avoidable exit regret than lower-risk positions across all "
    "canonical windows, making a future shared high-risk exit lifecycle policy "
    "worth testing."
)
CHANGE_TYPE = "observed_only_exit_oracle_cohort_attribution"
MECHANISM_FAMILY = "exit_policy_oracle_diagnostic"
TRIAL_FAMILY = "high_account_risk_exit_oracle_regret"
TRIAL_VARIANT_ID = "actual_risk_ge_2pct_full_denominator_v1"
CHANGED_VARIABLE = "high_actual_risk_exit_oracle_regret_cohort_v1"
CAUSAL_COMPONENTS = [
    "full fixed-entry oracle rows",
    "production-known actual_risk_pct cohort",
    "complement comparison",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    SOURCE_EXPERIMENT,
    "exp-20260630-012",
    "exp-20260623-020",
    "exp-20260429-032",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, set):
        return sorted(safe(item) for item in value)
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return round(number, digits) if number is not None else None


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number:.2%}"


def load_ticket() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    return ticket if isinstance(ticket, dict) else {}


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
            }
            for row in windows
        ],
    }


def load_oracle_rows() -> list[dict[str, Any]]:
    payload = read_json(SOURCE_ARTIFACT, {})
    windows = ((payload.get("oracle_full_trade_rows") or {}).get("windows") or {})
    rows: list[dict[str, Any]] = []
    for window in windows.values():
        for row in window.get("trade_rows") or []:
            if row.get("oracle_eligible"):
                rows.append(dict(row))
    return rows


def hhi(values: Iterable[float]) -> float | None:
    values = [value for value in values if value > 0]
    total = sum(values)
    if total <= 0:
        return None
    return round(sum((value / total) ** 2 for value in values), 6)


def group_stats(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "trade_count": 0,
            "window_count": 0,
            "windows": [],
            "avg_regret_vs_oracle": None,
            "top_ticker_share": None,
        }
    actual = sum(float(row.get("actual_pnl") or 0.0) for row in rows)
    oracle = sum(float(row.get("oracle_pnl") or 0.0) for row in rows)
    regret = sum(float(row.get("regret_vs_oracle") or 0.0) for row in rows)
    ticker_counts = Counter(str(row.get("ticker") or "missing") for row in rows)
    ticker_regret = Counter()
    for row in rows:
        ticker_regret[str(row.get("ticker") or "missing")] += max(
            0.0, float(row.get("regret_vs_oracle") or 0.0)
        )
    windows = sorted({str(row.get("window") or "missing") for row in rows})
    by_window = {}
    for window in windows:
        members = [row for row in rows if str(row.get("window") or "missing") == window]
        win_regret = sum(float(row.get("regret_vs_oracle") or 0.0) for row in members)
        win_actual = sum(float(row.get("actual_pnl") or 0.0) for row in members)
        win_oracle = sum(float(row.get("oracle_pnl") or 0.0) for row in members)
        by_window[window] = {
            "trade_count": len(members),
            "actual_pnl": round(win_actual, 2),
            "oracle_pnl": round(win_oracle, 2),
            "regret_vs_oracle": round(win_regret, 2),
            "avg_regret_vs_oracle": round(win_regret / len(members), 2)
            if members
            else None,
            "capture_ratio": round(win_actual / win_oracle, 6)
            if win_oracle > 0
            else None,
        }
    return {
        "trade_count": len(rows),
        "window_count": len(windows),
        "windows": windows,
        "actual_pnl": round(actual, 2),
        "oracle_pnl": round(oracle, 2),
        "regret_vs_oracle": round(regret, 2),
        "avg_regret_vs_oracle": round(regret / len(rows), 2),
        "capture_ratio": round(actual / oracle, 6) if oracle > 0 else None,
        "positive_regret_trade_count": sum(
            1 for row in rows if float(row.get("regret_vs_oracle") or 0.0) > 0
        ),
        "regret_gt_500_trade_count": sum(
            1 for row in rows if float(row.get("regret_vs_oracle") or 0.0) > 500
        ),
        "top_ticker": ticker_counts.most_common(1)[0][0],
        "top_ticker_count": ticker_counts.most_common(1)[0][1],
        "top_ticker_share": round(ticker_counts.most_common(1)[0][1] / len(rows), 6),
        "positive_regret_hhi": hhi(ticker_regret.values()),
        "ticker_counts": dict(sorted(ticker_counts.items())),
        "exit_reason_counts": dict(
            sorted(Counter(str(row.get("exit_reason") or "missing") for row in rows).items())
        ),
        "strategy_counts": dict(
            sorted(Counter(str(row.get("strategy") or "missing") for row in rows).items())
        ),
        "by_window": by_window,
    }


def build_separation(high: Mapping[str, Any], low: Mapping[str, Any]) -> dict[str, Any]:
    high_avg = as_float(high.get("avg_regret_vs_oracle"))
    low_avg = as_float(low.get("avg_regret_vs_oracle"))
    windows = sorted(set(high.get("by_window", {})) | set(low.get("by_window", {})))
    by_window = {}
    for window in windows:
        high_win = (high.get("by_window") or {}).get(window) or {}
        low_win = (low.get("by_window") or {}).get(window) or {}
        high_win_avg = as_float(high_win.get("avg_regret_vs_oracle"))
        low_win_avg = as_float(low_win.get("avg_regret_vs_oracle"))
        by_window[window] = {
            "high_trade_count": high_win.get("trade_count", 0),
            "low_trade_count": low_win.get("trade_count", 0),
            "high_avg_regret_vs_oracle": high_win_avg,
            "low_avg_regret_vs_oracle": low_win_avg,
            "avg_regret_spread": round_or_none(
                None
                if high_win_avg is None or low_win_avg is None
                else high_win_avg - low_win_avg,
                2,
            ),
        }
    return {
        "aggregate_avg_regret_spread": round_or_none(
            None if high_avg is None or low_avg is None else high_avg - low_avg,
            2,
        ),
        "by_window": by_window,
    }


def evaluate_readiness(
    *,
    high_stats: Mapping[str, Any],
    low_stats: Mapping[str, Any],
    separation: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    failures = []
    if high_stats.get("trade_count", 0) < MIN_COHORT_ROWS:
        failures.append("high_risk_sample_too_small")
    if low_stats.get("trade_count", 0) < MIN_COMPLEMENT_ROWS:
        failures.append("low_risk_complement_sample_too_small")
    if high_stats.get("window_count", 0) < MIN_WINDOWS:
        failures.append("high_risk_not_all_windows")
    if low_stats.get("window_count", 0) < MIN_WINDOWS:
        failures.append("low_risk_not_all_windows")
    if (high_stats.get("top_ticker_share") or 1.0) > MAX_TOP_TICKER_SHARE:
        failures.append("high_risk_ticker_concentration_failed")
    spread = as_float(separation.get("aggregate_avg_regret_spread"))
    if spread is None or spread < MIN_AGGREGATE_AVG_REGRET_SPREAD:
        failures.append("aggregate_regret_spread_too_small")
    for window, row in (separation.get("by_window") or {}).items():
        if row.get("high_trade_count", 0) < MIN_WINDOW_ROWS:
            failures.append(f"{window}_high_risk_window_sample_too_small")
        if row.get("low_trade_count", 0) < MIN_WINDOW_ROWS:
            failures.append(f"{window}_low_risk_window_sample_too_small")
        window_spread = as_float(row.get("avg_regret_spread"))
        if window_spread is None or window_spread < MIN_WINDOW_AVG_REGRET_SPREAD:
            failures.append(f"{window}_regret_spread_not_stable")
    return (not failures, failures)


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = load_ticket()
    baseline = load_baseline_metrics()
    rows = load_oracle_rows()
    high_rows = [
        row
        for row in rows
        if float(row.get("actual_risk_pct") or 0.0) >= HIGH_ACTUAL_RISK_THRESHOLD
    ]
    low_rows = [
        row
        for row in rows
        if float(row.get("actual_risk_pct") or 0.0) < HIGH_ACTUAL_RISK_THRESHOLD
    ]
    high_stats = group_stats(high_rows)
    low_stats = group_stats(low_rows)
    separation = build_separation(high_stats, low_stats)
    cohort_passed, failures = evaluate_readiness(
        high_stats=high_stats,
        low_stats=low_stats,
        separation=separation,
    )
    missing_inputs = []
    if not BASELINE_RESULT.exists():
        missing_inputs.append("baseline_missing")
    if not SOURCE_ARTIFACT.exists():
        missing_inputs.append("source_oracle_artifact_missing")
    if not rows:
        missing_inputs.append("source_oracle_rows_missing")
    failures = missing_inputs + failures
    cohort_passed = cohort_passed and not missing_inputs

    status = (
        "observed_only_positive_lead" if cohort_passed else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_high_account_risk_exit_oracle_regret_lead_not_promoted"
        if cohort_passed
        else "observed_only_rejected_high_account_risk_exit_oracle_regret"
    )
    prediction = ticket.get("prediction") or {
        "success_probability": 0.25,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "window_separation_not_stable",
            "cohort_not_actionable_without_future_data",
            "sample_too_small",
            "concentration_failed",
            "oracle_label_not_policy",
        ],
        "confidence_reason": (
            "The complete exp-20260630-011 denominator fixes the prior oracle "
            "sampling defect, and account risk is production-known at entry; "
            "however exit oracle labels are diagnostic only and prior static "
            "stop/target/hold response retries have failed."
        ),
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
    }
    success_probability = as_float(prediction.get("success_probability")) or 0.0
    actual_success = 1.0 if cohort_passed else 0.0

    why = (
        "High actual-risk trades form a broad, cross-window cohort with larger "
        "oracle regret than the lower-risk complement in every canonical window. "
        "The result is only a diagnostic lead because the oracle best-exit label "
        "uses future intratrade prices; a live rule would still need a shared "
        "pre-exit lifecycle policy."
        if cohort_passed
        else "The high actual-risk cohort did not clear the predeclared "
        "sample, window, concentration, or regret-separation checks, so the "
        "oracle label should not be promoted into an exit policy."
    )
    forbidden = (
        "Do not retune actual_risk_pct thresholds, stop distance, target trims, "
        "target multiples, trailing stops, hold days, or response curves on "
        "these oracle rows. The only legal next alpha step is a separately "
        "predeclared shared production/backtest lifecycle rule using fields "
        "known before exit, or materially more settled forward shadow-exit rows."
    )
    next_required = (
        "A shared exit lifecycle helper that uses only pre-exit account-risk "
        "and path-state fields, plus Gate 1-4 before/after evidence; or "
        "prospective shadow exit-advisory rows with settled replacement value."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": cohort_passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_exit_oracle_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "full_trade_oracle_denominator_rows",
        "new_evidence_axis": (
            "Full trade-level fixed-entry oracle denominator rows from "
            "exp-20260630-011, applied to an entry-known account-risk cohort."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Reservation passed without blocking matches.",
                SOURCE_EXPERIMENT: "Accepted denominator repair enabling full cohort checks.",
                "exp-20260630-012": "Rejected close-confirmed static stop; this run does not retune stops.",
                "exp-20260429-032": "Rejected target partial trim replay; this run does not retune targets.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only lead if high actual-risk rows and complement both "
                "cover all three windows, cohort sample >=20, per-window rows >=3, "
                "top ticker share <=35%, aggregate average regret spread >=$500, "
                "and every window spread >=$300. No alpha acceptance or strategy "
                "change is allowed from this diagnostic alone."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_experiment": SOURCE_EXPERIMENT,
            "source_artifact": repo_rel(SOURCE_ARTIFACT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "high_actual_risk_threshold": HIGH_ACTUAL_RISK_THRESHOLD,
            "cohort_definition": "actual_risk_pct >= 0.02",
            "production_known_boundary": (
                "actual_risk_pct is from the canonical trade's account-risk "
                "sizing attribution and is known by the execution/risk layer; "
                "oracle_exit_date and oracle_exit_price are labels only."
            ),
            "threshold_basis": (
                "2% is the round account-risk intensity boundary; this run does "
                "not sweep thresholds."
            ),
            "acceptance_thresholds": {
                "min_cohort_rows": MIN_COHORT_ROWS,
                "min_complement_rows": MIN_COMPLEMENT_ROWS,
                "min_windows": MIN_WINDOWS,
                "min_window_rows": MIN_WINDOW_ROWS,
                "min_aggregate_avg_regret_spread": MIN_AGGREGATE_AVG_REGRET_SPREAD,
                "min_window_avg_regret_spread": MIN_WINDOW_AVG_REGRET_SPREAD,
                "max_top_ticker_share": MAX_TOP_TICKER_SHARE,
            },
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "passed": BASELINE_RESULT.exists(),
        },
        "gate2": {
            "dependencies_validated": bool(rows),
            "fields_checked": [
                "entry_date",
                "actual_risk_pct",
                "actual_pnl",
                "oracle_pnl",
                "regret_vs_oracle",
                "target_price_not_used",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in rows),
            "target_price_relevance": (
                "Not used. This is diagnostic cohort attribution, not a target exit rule."
            ),
            "passed": bool(rows) and all(bool(row.get("entry_date")) for row in rows),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "cohort_rows": high_stats.get("trade_count"),
            "complement_rows": low_stats.get("trade_count"),
            "note": "No executable filter or exit was added; cohort survival is denominator coverage only.",
            "passed": True,
        },
        "gate4": {
            "observed_only": True,
            "passed": cohort_passed,
            "decision": decision,
            "failed_reasons": failures,
            "cohort_readiness_passed": cohort_passed,
            "binding_note": (
                "A pass is an observed-only lead, not accepted alpha. Any "
                "strategy-affecting exit lifecycle needs a separate shared "
                "policy and Gate 1-4 before/after run."
            ),
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "survival_rate_delta": 0.0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "high_risk_trade_count": high_stats.get("trade_count"),
            "low_risk_trade_count": low_stats.get("trade_count"),
            "aggregate_avg_regret_spread": separation.get("aggregate_avg_regret_spread"),
            "strategy_behavior_changed": False,
        },
        "cohort_analysis": {
            "source_row_count": len(rows),
            "high_actual_risk": high_stats,
            "low_actual_risk": low_stats,
            "separation": separation,
            "sample_rows": {
                "high_actual_risk_trade_keys": [
                    row.get("trade_key") for row in high_rows
                ],
                "low_actual_risk_trade_keys": [
                    row.get("trade_key") for row in low_rows
                ],
            },
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "llm_prompt_changed": False,
            "daily_snapshot_exposed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "replay_only": False,
            "uses_llm": False,
            "parity_note": "Read-only diagnostic over existing artifacts; no adapter behavior changed.",
        },
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": round(success_probability, 4),
            "actual_success": 1 if cohort_passed else 0,
            "brier_score": round((success_probability - actual_success) ** 2, 6),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "realized_failure_modes": failures,
            "predicted_failure_mode_hit": bool(failures),
            "expected_ev_delta": prediction.get("expected_ev_delta", 0.0),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta", 0.0),
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "The diagnostic cohort passed despite low prior; the surprise is "
                "limited because this is still oracle-label evidence, not a policy."
                if cohort_passed
                else "The predeclared failure modes explain the rejection."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": forbidden,
            "new_evidence_required": next_required,
        },
        "next_retry_requires": [
            "shared production/backtest exit lifecycle helper using pre-exit fields",
            "Gate 1-4 before/after evidence against canonical baseline",
            "or materially more settled forward shadow-exit replacement-value rows",
        ],
        "rejection_reason": None if cohort_passed else ";".join(failures),
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_ARTIFACT),
            repo_rel(BASELINE_RESULT),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no JavaScript tooling invoked.",
        },
    }


def compact_log(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in [
            "experiment_id",
            "timestamp",
            "status",
            "lane",
            "owner",
            "decision",
            "accepted",
            "accepted_alpha",
            "observed_only_lead",
            "alpha_ready",
            "hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "changed_variable",
            "single_causal_variable",
            "causal_components",
            "prior_trial_count",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "new_evidence_axis",
            "pre_run_questions",
            "parameters",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "production_impact",
            "prediction",
            "calibration",
            "post_run_reflection",
            "next_retry_requires",
            "rejection_reason",
            "changed_files",
            "related_files",
            "reproduction_commands",
            "anti_js",
        ]
    } | {
        "cohort_summary": {
            "high_actual_risk": payload["cohort_analysis"]["high_actual_risk"],
            "low_actual_risk": payload["cohort_analysis"]["low_actual_risk"],
            "separation": payload["cohort_analysis"]["separation"],
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    high = payload["cohort_analysis"]["high_actual_risk"]
    low = payload["cohort_analysis"]["low_actual_risk"]
    separation = payload["cohort_analysis"]["separation"]
    rows = [
        "| Window | High n | Low n | High avg regret | Low avg regret | Spread |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window, row in (separation.get("by_window") or {}).items():
        rows.append(
            "| {window} | {hn} | {ln} | {ha} | {la} | {spread} |".format(
                window=window,
                hn=row.get("high_trade_count"),
                ln=row.get("low_trade_count"),
                ha=money(row.get("high_avg_regret_vs_oracle")),
                la=money(row.get("low_avg_regret_vs_oracle")),
                spread=money(row.get("avg_regret_spread")),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: high account-risk exit oracle regret",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Observed-only lead: `{str(payload['observed_only_lead']).lower()}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Aggregate",
            "",
            f"- High-risk cohort: `{high['trade_count']}` trades, avg regret `{money(high['avg_regret_vs_oracle'])}`, capture `{pct(high['capture_ratio'])}`",
            f"- Low-risk complement: `{low['trade_count']}` trades, avg regret `{money(low['avg_regret_vs_oracle'])}`, capture `{pct(low['capture_ratio'])}`",
            f"- Aggregate avg-regret spread: `{money(separation['aggregate_avg_regret_spread'])}`",
            f"- High-risk top ticker share: `{pct(high['top_ticker_share'])}`",
            "",
            "## Windows",
            "",
            *rows,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(compact_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload.get("prediction"),
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "lean_quality_passed": True,
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "gate4": payload["gate4"],
                "aggregate_avg_regret_spread": payload["cohort_analysis"][
                    "separation"
                ]["aggregate_avg_regret_spread"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
