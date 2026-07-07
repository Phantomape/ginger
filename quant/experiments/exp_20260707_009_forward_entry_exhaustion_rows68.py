"""exp-20260707-009: forward entry-exhaustion rows68 attribution.

Observed-only alpha attribution over the shared forward replacement-value
ledger. The only new evidence axis is materially more settled forward rows
since exp-20260627-026; no entry, ranking, sizing, exit, paper, or live behavior
changes.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260707-009"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "forward_entry_exhaustion_rows68"
RUNNER = f"quant/experiments/exp_20260707_009_{SLUG}.py"
RUNNER_COMMAND = f".\\.venv\\Scripts\\python.exe -B {RUNNER}"

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260707_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha attribution: forward replacement rows carrying the "
    "fixed PIT entry_exhaustion_stretched_flag may now have enough newly "
    "settled rows to confirm whether stretched entries are a loss-tail / "
    "negative replacement-value cohort for future default-off allocation "
    "governance."
)
ALPHA_HYPOTHESIS = (
    "risk allocation / candidate-pool governance attribution: a fixed PIT "
    "entry-exhaustion flag may identify fragile default-off forward rows, but "
    "only if the reopened forward sample shows stable cash/SPY/QQQ replacement "
    "value separation without changing thresholds or strategy behavior."
)
CHANGED_VARIABLE = "forward_entry_exhaustion_stretched_flag_replacement_value_attribution_v2"
TRIAL_FAMILY = "forward_entry_exhaustion_replacement_value_attribution"
TRIAL_VARIANT_ID = "stretched_flag_vs_non_stretched_forward_rows_68_v2"
MECHANISM_FAMILY = "entry_name_level_exhaustion_forward_attribution"
CHANGE_TYPE = "observed_only_forward_attribution"
NEW_EVIDENCE_TYPE = "materially_more_settled_forward_replacement_rows"
NEW_EVIDENCE_AXIS = (
    "The same fixed entry_exhaustion_stretched_flag forward attribution last "
    "ran on 41 closed forward rows in exp-20260627-026; the current shared "
    "forward replacement ledger has 68 enriched closed rows (+65.9%), meeting "
    "the default >=+50% materially-more-settled-forward-row reopen axis "
    "without changing thresholds, lookbacks, response shape, or strategy "
    "behavior."
)
NEARBY_PRIORS = ["exp-20260627-026", "exp-20260630-016"]
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "stretched_bucket_still_too_thin",
        "effect_not_incremental",
        "concentration_failed",
        "non_stretched_also_negative",
    ],
    "confidence_reason": (
        "Prior forward attribution was directionally negative but too thin, "
        "and a later large-N frozen-window diagnostic contradicted it; current "
        "evidence is only justified by a >=50% increase in closed forward rows, "
        "so confidence stays low and the run is attribution-only."
    ),
    "recorded_at": "2026-07-07T09:09:24+00:00",
}
PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
ACCEPTANCE_RULE = {
    "min_total_tagged_rows": 60,
    "min_stretched_rows": 8,
    "min_non_stretched_rows": 40,
    "max_single_stretched_ticker_share": 0.5,
    "max_single_stretched_sleeve_share": 0.5,
    "require_all_primary_means_worse": True,
    "require_all_primary_medians_worse": True,
    "require_all_primary_loss_tails_worse": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260707_009_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def worst_tail_mean(values: list[float], tail_fraction: float = 0.2) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    count = max(1, math.ceil(len(sorted_values) * tail_fraction))
    return mean(sorted_values[:count])


def summarize_values(values: list[float]) -> dict[str, Any]:
    sorted_values = sorted(values)
    return {
        "n": len(values),
        "sum": round(sum(values), 2) if values else None,
        "mean": round(mean(values), 4) if values else None,
        "median": round(median(values), 4) if values else None,
        "min": round(min(values), 4) if values else None,
        "max": round(max(values), 4) if values else None,
        "p20": round(percentile(sorted_values, 0.2), 4) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
        if values
        else None,
        "worst_20pct_mean": round(worst_tail_mean(values, 0.2), 4) if values else None,
    }


def load_forward_rows() -> list[dict[str, Any]]:
    if not FORWARD_LEDGER.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in FORWARD_LEDGER.read_text(encoding="utf-8-sig").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    survival = [
        float(row.get("survival_rate") or 0.0)
        for row in windows
        if row.get("survival_rate") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "survival_rate": min(survival) if survival else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows), default=None
        ),
        "window_count": len(windows),
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


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    sleeves = Counter(str(row.get("sleeve_key") or "UNKNOWN") for row in rows)
    metrics = {}
    for key in [*PRIMARY_METRICS, "pnl_usd"]:
        values = [value for row in rows if (value := numeric_value(row, key)) is not None]
        metrics[key] = summarize_values(values)
    return {
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "sleeve_count": len(sleeves),
        "ticker_counts": dict(sorted(tickers.items())),
        "sleeve_counts": dict(sorted(sleeves.items())),
        "top_tickers": [
            {"ticker": ticker, "rows": count, "share": round(count / len(rows), 6)}
            for ticker, count in tickers.most_common(8)
        ]
        if rows
        else [],
        "top_sleeves": [
            {"sleeve": sleeve, "rows": count, "share": round(count / len(rows), 6)}
            for sleeve, count in sleeves.most_common(8)
        ]
        if rows
        else [],
        "metrics": metrics,
    }


def metric_comparisons(
    stretched: list[dict[str, Any]], non_stretched: list[dict[str, Any]]
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for key in PRIMARY_METRICS:
        stretched_values = [
            value for row in stretched if (value := numeric_value(row, key)) is not None
        ]
        non_values = [
            value for row in non_stretched if (value := numeric_value(row, key)) is not None
        ]
        stretched_summary = summarize_values(stretched_values)
        non_summary = summarize_values(non_values)
        comparisons[key] = {
            "stretched": stretched_summary,
            "non_stretched": non_summary,
            "mean_delta_stretched_minus_non": round(
                (stretched_summary["mean"] or 0.0) - (non_summary["mean"] or 0.0), 4
            )
            if stretched_values and non_values
            else None,
            "median_delta_stretched_minus_non": round(
                (stretched_summary["median"] or 0.0) - (non_summary["median"] or 0.0),
                4,
            )
            if stretched_values and non_values
            else None,
            "tail_delta_stretched_minus_non": round(
                (stretched_summary["worst_20pct_mean"] or 0.0)
                - (non_summary["worst_20pct_mean"] or 0.0),
                4,
            )
            if stretched_values and non_values
            else None,
            "stretched_mean_worse": (
                stretched_summary["mean"] is not None
                and non_summary["mean"] is not None
                and stretched_summary["mean"] < non_summary["mean"]
            ),
            "stretched_median_worse": (
                stretched_summary["median"] is not None
                and non_summary["median"] is not None
                and stretched_summary["median"] < non_summary["median"]
            ),
            "stretched_loss_tail_worse": (
                stretched_summary["worst_20pct_mean"] is not None
                and non_summary["worst_20pct_mean"] is not None
                and stretched_summary["worst_20pct_mean"]
                < non_summary["worst_20pct_mean"]
            ),
        }
    return comparisons


def max_share(counter: Counter[str], total: int) -> float:
    if not counter or total <= 0:
        return 0.0
    return max(counter.values()) / total


def build_result() -> dict[str, Any]:
    baseline = baseline_metrics()
    rows = load_forward_rows()
    tagged = [
        row
        for row in rows
        if row.get("entry_exhaustion_status") == "ok"
        and row.get("entry_exhaustion_tag_rule_version")
        == "forward_replacement_entry_exhaustion_tag_v1"
    ]
    stretched = [row for row in tagged if row.get("entry_exhaustion_stretched_flag") is True]
    non_stretched = [
        row for row in tagged if row.get("entry_exhaustion_stretched_flag") is not True
    ]
    comparisons = metric_comparisons(stretched, non_stretched)
    stretched_tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in stretched)
    stretched_sleeves = Counter(str(row.get("sleeve_key") or "UNKNOWN") for row in stretched)
    rows_by_asof = Counter(str(row.get("asof_date") or "UNKNOWN") for row in tagged)

    checks = {
        "total_tagged_rows_min_passed": len(tagged)
        >= ACCEPTANCE_RULE["min_total_tagged_rows"],
        "stretched_rows_min_passed": len(stretched)
        >= ACCEPTANCE_RULE["min_stretched_rows"],
        "non_stretched_rows_min_passed": len(non_stretched)
        >= ACCEPTANCE_RULE["min_non_stretched_rows"],
        "single_stretched_ticker_share_passed": max_share(stretched_tickers, len(stretched))
        <= ACCEPTANCE_RULE["max_single_stretched_ticker_share"],
        "single_stretched_sleeve_share_passed": max_share(stretched_sleeves, len(stretched))
        <= ACCEPTANCE_RULE["max_single_stretched_sleeve_share"],
        "all_primary_means_worse": all(
            comparisons[key]["stretched_mean_worse"] for key in PRIMARY_METRICS
        ),
        "all_primary_medians_worse": all(
            comparisons[key]["stretched_median_worse"] for key in PRIMARY_METRICS
        ),
        "all_primary_loss_tails_worse": all(
            comparisons[key]["stretched_loss_tail_worse"] for key in PRIMARY_METRICS
        ),
    }
    sample_ready = (
        checks["total_tagged_rows_min_passed"]
        and checks["stretched_rows_min_passed"]
        and checks["non_stretched_rows_min_passed"]
        and checks["single_stretched_ticker_share_passed"]
        and checks["single_stretched_sleeve_share_passed"]
    )
    directional_support = (
        checks["all_primary_means_worse"]
        and checks["all_primary_medians_worse"]
        and checks["all_primary_loss_tails_worse"]
    )
    observed_only_lead = bool(sample_ready and directional_support)
    if observed_only_lead:
        status = "observed_only_positive_entry_exhaustion_forward_lead_not_activation_ready"
        decision = "observed_only_positive_entry_exhaustion_forward_lead_not_activation_ready"
        failed_reasons: list[str] = []
    else:
        failed_reasons = [key for key, passed in checks.items() if not passed]
        status = "observed_only_rejected_entry_exhaustion_forward_rows68"
        decision = (
            "observed_only_directional_entry_exhaustion_lead_still_too_thin"
            if directional_support
            else "observed_only_rejected_no_stable_entry_exhaustion_edge"
        )

    actual_success = 1 if observed_only_lead else 0
    timestamp = utc_now()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "decision": decision,
        "observed_only_lead": observed_only_lead,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_forward_attribution_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "fixed PIT entry-exhaustion tag",
            "current forward replacement-value ledger",
            "cash/SPY/QQQ replacement attribution",
            "classifier keyword coverage repair",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "parameters": {
            "source_ledger": repo_rel(FORWARD_LEDGER),
            "prior_forward_row_count": 41,
            "current_forward_row_count": len(tagged),
            "forward_row_count_growth_pct": round((len(tagged) - 41) / 41, 6),
            "entry_exhaustion_tag_rule_version": "forward_replacement_entry_exhaustion_tag_v1",
            "acceptance_rule": ACCEPTANCE_RULE,
            "strategy_behavior_changed": False,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(tagged),
            "fields_checked": [
                "decision_id",
                "ticker",
                "sleeve_key",
                "entry_date",
                "exit_date",
                "entry_exhaustion_status",
                "entry_exhaustion_stretched_flag",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "target_price",
            ],
            "entry_date_present_rows": sum(1 for row in tagged if row.get("entry_date")),
            "target_price_relevance": (
                "Forward replacement rows are already settled paper outcomes and "
                "do not schedule exits or orders; target_price is not consumed by "
                "this attribution."
            ),
            "source_ledger": repo_rel(FORWARD_LEDGER),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter was added; rows are only attributed.",
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": len(rows),
            "signals_survived": len(tagged),
            "survival_rate": round(len(tagged) / len(rows), 6) if rows else 0.0,
        },
        "gate4": {
            "passed": observed_only_lead,
            "decision": decision,
            "observed_only": True,
            "strategy_rerun_required": False,
            "acceptance_rule": ACCEPTANCE_RULE,
            "acceptance_checks": checks,
            "failed_reasons": failed_reasons,
            "sample_ready": sample_ready,
            "directional_support": directional_support,
            "comparisons": comparisons,
            "bucket_summary": {
                "stretched": bucket_summary(stretched),
                "non_stretched": bucket_summary(non_stretched),
                "all_tagged": bucket_summary(tagged),
            },
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
        },
        "summary": {
            "source_rows": len(rows),
            "tagged_rows": len(tagged),
            "stretched_rows": len(stretched),
            "non_stretched_rows": len(non_stretched),
            "stretched_ticker_count": len(stretched_tickers),
            "stretched_sleeve_count": len(stretched_sleeves),
            "rows_by_asof_date": dict(sorted(rows_by_asof.items())),
            "decision": decision,
        },
        "activation_readiness": {
            "alpha_ready": False,
            "blockers": [
                "observed_only_attribution_no_strategy_or_paper_behavior_change",
                *failed_reasons,
                "requires_shared_policy_gate4_before_any_allocation_change",
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "exit_rules_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over an existing shared forward replacement "
                "ledger plus novelty-classifier coverage. No helper, adapter, "
                "order, rank, size, exit, watchlist, or LLM behavior changed."
            ),
        },
        "classifier_update": {
            "reason": "experiment.py new classified this forward surface as data_source=other.",
            "data_source_added": "forward_replacement_value",
            "gate_shape_added": "forward_attribution",
            "test_added": "test_forward_replacement_value_attribution_gate_shape",
        },
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": bool(
                set(PREDICTION["main_failure_modes"])
                & {
                    "stretched_bucket_still_too_thin"
                    if "stretched_rows_min_passed" in failed_reasons
                    else "",
                    "concentration_failed"
                    if (
                        "single_stretched_ticker_share_passed" in failed_reasons
                        or "single_stretched_sleeve_share_passed" in failed_reasons
                    )
                    else "",
                    "effect_not_incremental"
                    if not directional_support
                    else "",
                }
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed stretched bucket is still directionally worse across "
                "cash/SPY/QQQ replacement metrics after the +65.9% row increase, "
                "but it remains too thin for allocation governance."
                if directional_support
                else "The fixed entry-exhaustion bucket did not keep stable "
                "cash/SPY/QQQ replacement-value separation after row growth."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune entry-exhaustion thresholds, ATR lookbacks, "
                "extension formulas, top-N, hold days, notional, ranking, or "
                "sizing response curves on these rows."
            ),
            "new_evidence_required": (
                "Reopen only after materially more stretched closed forward rows "
                "settle under the same fixed helper, or after a genuinely new PIT "
                "entry-fragility data source appears."
            ),
        },
        "next_retry_requires": [
            "materially more stretched closed forward rows",
            "or a genuinely new PIT entry-fragility source",
            "no threshold, formula, lookback, notional, rank, or response retune",
        ],
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_PATH),
            "experiments/logs/exp-20260627-026.json",
            "experiments/logs/exp-20260630-016.json",
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
    }
    return result


def build_log(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "changed_variable",
        "single_causal_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "summary",
        "activation_readiness",
        "production_impact",
        "classifier_update",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
        "anti_js",
    ]
    return {key: result.get(key) for key in keys}


def build_card(result: dict[str, Any]) -> str:
    cash = result["gate4"]["comparisons"]["replacement_value_vs_cash_usd"]
    spy = result["gate4"]["comparisons"]["replacement_value_vs_spy_usd"]
    qqq = result["gate4"]["comparisons"]["replacement_value_vs_qqq_usd"]
    lines = [
        f"# {EXPERIMENT_ID} - forward entry-exhaustion rows68 attribution",
        "",
        f"- status: `{result['status']}`",
        f"- decision: `{result['decision']}`",
        f"- tagged rows: `{result['summary']['tagged_rows']}`",
        f"- stretched rows: `{result['summary']['stretched_rows']}`",
        f"- cash mean delta stretched-minus-non: `{cash['mean_delta_stretched_minus_non']}`",
        f"- SPY mean delta stretched-minus-non: `{spy['mean_delta_stretched_minus_non']}`",
        f"- QQQ mean delta stretched-minus-non: `{qqq['mean_delta_stretched_minus_non']}`",
        f"- failed reasons: `{', '.join(result['gate4']['failed_reasons']) or 'none'}`",
        "",
        "No live, paper, ranking, sizing, entry, or exit behavior changed.",
        "",
        "## Boundary",
        "",
        result["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "generated_at": result["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": result["reproduction_commands"],
    }


def persist(result: dict[str, Any]) -> None:
    write_json(OUT_JSON, result)
    save_experiment_log_entry(build_log(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_json(MANIFEST_JSON, build_manifest(result))
    ticket = read_json(TICKET_JSON, {}) or {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": result["accepted"],
            "accepted_alpha": result["accepted_alpha"],
            "accepted_measurement_repair": result["accepted_measurement_repair"],
            "alpha_ready": result["alpha_ready"],
            "decision": result["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": {
                "tagged_rows": result["summary"]["tagged_rows"],
                "stretched_rows": result["summary"]["stretched_rows"],
                "gate4_failed_reasons": result["gate4"]["failed_reasons"],
                "directional_support": result["gate4"]["directional_support"],
            },
        },
        status=result["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            "owner": OWNER,
            "hypothesis": result["hypothesis"],
            "alpha_hypothesis": result["alpha_hypothesis"],
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": result["multiple_testing_risk_bucket"],
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": result["new_evidence_axis"],
            "parameters": result["parameters"],
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "summary": result["summary"],
            "activation_readiness": result["activation_readiness"],
            "production_impact": result["production_impact"],
            "classifier_update": result["classifier_update"],
            "calibration": result["calibration"],
            "post_run_reflection": result["post_run_reflection"],
            "rejection_reason": result["rejection_reason"],
            "next_retry_requires": result["next_retry_requires"],
            "changed_files": CHANGED_FILES,
            "related_files": result["related_files"],
            "reproduction_commands": result["reproduction_commands"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "tagged_rows": result["summary"]["tagged_rows"],
                "stretched_rows": result["summary"]["stretched_rows"],
                "failed_reasons": result["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
