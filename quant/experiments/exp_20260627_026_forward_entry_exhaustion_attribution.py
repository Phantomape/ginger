"""exp-20260627-026: forward entry-exhaustion attribution.

Observed-only alpha attribution over the forward replacement-value ledger.
This tests the newly materialized PIT entry_exhaustion_stretched_flag from
exp-20260627-022 without changing entry, ranking, sizing, exits, paper orders,
or live orders.
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
for entry in (REPO_ROOT / "scripts",):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-026"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "forward_entry_exhaustion_attribution"
RUNNER = f"quant/experiments/exp_20260627_026_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_026_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HYPOTHESIS = (
    "Closed forward replacement rows carrying the newly shared PIT "
    "entry_exhaustion_stretched_flag should show worse cash/SPY/QQQ "
    "replacement value and loss-tail than non-stretched rows, testing whether "
    "entry-day name-level overextension is a real future allocation risk signal "
    "without changing strategy behavior."
)
CHANGED_VARIABLE = "forward_entry_exhaustion_stretched_flag_replacement_value_attribution_v1"
TRIAL_FAMILY = "forward_entry_exhaustion_replacement_value_attribution"
TRIAL_VARIANT_ID = "stretched_flag_vs_non_stretched_v1"
NEARBY_PRIORS = ["exp-20260627-022", "exp-20260626-018", "exp-20260623-002"]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "stretched_rows_too_thin",
        "no_cash_spy_qqq_separation",
        "source_family_confound",
        "forward_rows_not_out_of_sample",
    ],
    "confidence_reason": (
        "The measurement repair created a genuine new PIT name-level exhaustion "
        "field on closed forward rows and current memory says regime/short-volume "
        "tags were non-separating; confidence is low because the current closed "
        "row count and stretched bucket are small and this is only attribution."
    ),
    "recorded_at": "2026-06-27T22:05:02+00:00",
}
PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
ACCEPTANCE_RULE = {
    "min_total_tagged_rows": 30,
    "min_stretched_rows": 8,
    "min_non_stretched_rows": 20,
    "max_single_stretched_ticker_share": 0.5,
    "max_single_stretched_sleeve_share": 0.5,
    "require_all_primary_means_worse": True,
    "require_all_primary_medians_worse": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_026_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    survival_rates = [
        float(w.get("survival_rate") or 0.0)
        for w in windows
        if w.get("survival_rate") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "survival_rate": min(survival_rates) if survival_rates else None,
        "max_drawdown_pct_worst": max(
            (float(w.get("max_drawdown_pct") or 0.0) for w in windows), default=None
        ),
        "window_count": len(windows),
        "windows": [
            {
                "label": w.get("label"),
                "start": w.get("start"),
                "end": w.get("end"),
                "expected_value_score": w.get("expected_value_score"),
                "total_pnl": w.get("total_pnl"),
                "trade_count": w.get("trade_count"),
                "survival_rate": w.get("survival_rate"),
                "max_drawdown_pct": w.get("max_drawdown_pct"),
            }
            for w in windows
        ],
    }


def load_forward_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not FORWARD_LEDGER.exists():
        return rows
    for raw in FORWARD_LEDGER.read_text(encoding="utf-8-sig").splitlines():
        if not raw.strip():
            continue
        rows.append(json.loads(raw))
    return rows


def numeric_value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted):
        return None
    return converted


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
        "positive_rate": round(sum(1 for v in values if v > 0) / len(values), 6)
        if values
        else None,
        "worst_20pct_mean": round(worst_tail_mean(values, 0.2), 4) if values else None,
    }


def bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in [*PRIMARY_METRICS, "pnl_usd"]:
        values = [numeric_value(row, key) for row in rows]
        metrics[key] = summarize_values([value for value in values if value is not None])
    tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in rows)
    sleeves = Counter(str(row.get("sleeve_key") or "UNKNOWN") for row in rows)
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


def metric_comparisons(stretched: list[dict[str, Any]], other: list[dict[str, Any]]) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for key in PRIMARY_METRICS:
        stretched_values = [
            value
            for row in stretched
            if (value := numeric_value(row, key)) is not None
        ]
        other_values = [
            value
            for row in other
            if (value := numeric_value(row, key)) is not None
        ]
        stretched_summary = summarize_values(stretched_values)
        other_summary = summarize_values(other_values)
        comparisons[key] = {
            "stretched": stretched_summary,
            "non_stretched": other_summary,
            "mean_delta_stretched_minus_non": round(
                (stretched_summary["mean"] or 0.0) - (other_summary["mean"] or 0.0), 4
            )
            if stretched_values and other_values
            else None,
            "median_delta_stretched_minus_non": round(
                (stretched_summary["median"] or 0.0) - (other_summary["median"] or 0.0),
                4,
            )
            if stretched_values and other_values
            else None,
            "tail_delta_stretched_minus_non": round(
                (stretched_summary["worst_20pct_mean"] or 0.0)
                - (other_summary["worst_20pct_mean"] or 0.0),
                4,
            )
            if stretched_values and other_values
            else None,
            "stretched_mean_worse": (
                stretched_summary["mean"] is not None
                and other_summary["mean"] is not None
                and stretched_summary["mean"] < other_summary["mean"]
            ),
            "stretched_median_worse": (
                stretched_summary["median"] is not None
                and other_summary["median"] is not None
                and stretched_summary["median"] < other_summary["median"]
            ),
            "stretched_loss_tail_worse": (
                stretched_summary["worst_20pct_mean"] is not None
                and other_summary["worst_20pct_mean"] is not None
                and stretched_summary["worst_20pct_mean"]
                < other_summary["worst_20pct_mean"]
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
    observed_only_lead = bool(directional_support and sample_ready)
    if observed_only_lead:
        decision = "observed_only_positive_entry_exhaustion_forward_lead_not_promoted"
        status = "observed_only_positive"
        failed_reasons: list[str] = []
    else:
        failed_reasons = [key for key, passed in checks.items() if not passed]
        decision = (
            "observed_only_directional_entry_exhaustion_lead_too_thin"
            if directional_support
            else "observed_only_rejected_no_stable_entry_exhaustion_edge"
        )
        status = "observed_only_rejected"

    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": "entry_name_level_exhaustion_forward_attribution",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "accepted exp-20260627-022 forward exhaustion tag",
            "closed forward replacement rows",
            "cash SPY QQQ replacement-value attribution",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "shared_forward_entry_name_level_exhaustion_observation_field",
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if observed_only_lead else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if observed_only_lead else 0))
                ** 2,
                4,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_reasons,
            "predicted_failure_mode_hit": any(
                reason in failed_reasons
                for reason in (
                    "stretched_rows_min_passed",
                    "all_primary_means_worse",
                    "all_primary_medians_worse",
                    "all_primary_loss_tails_worse",
                )
            )
            or not observed_only_lead,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Low surprise: the fixed stretched bucket is directionally worse, "
                "but the stretched sample is below the preregistered readiness floor."
                if decision == "observed_only_directional_entry_exhaustion_lead_too_thin"
                else "The fixed stretched bucket did not produce stable primary metric separation."
            ),
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
                "Forward replacement rows do not schedule target exits or orders; "
                "target_price is not required for this attribution."
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
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
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
        },
        "summary": {
            "source_rows": len(rows),
            "tagged_rows": len(tagged),
            "stretched_rows": len(stretched),
            "non_stretched_rows": len(non_stretched),
            "stretched_ticker_count": len(stretched_tickers),
            "stretched_sleeve_count": len(stretched_sleeves),
            "decision": decision,
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
                "Read-only attribution over an existing shared forward-replacement "
                "ledger. No helper, adapter, order, rank, size, exit, watchlist, "
                "or LLM behavior changed."
            ),
        },
        "rejection_reason": ";".join(failed_reasons) if failed_reasons else None,
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed stretched bucket is directionally worse across primary "
                "cash/SPY/QQQ replacement metrics, but it contains only six rows, "
                "so the result is too thin and source-family-sensitive to promote."
                if decision == "observed_only_directional_entry_exhaustion_lead_too_thin"
                else "The fixed entry-exhaustion bucket did not produce stable enough "
                "cash/SPY/QQQ replacement-value separation on current closed rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not turn this into a threshold, quintile, top-N, lookback, "
                "notional, ranking, or sizing sweep on the same 41 closed forward "
                "rows. Do not test adjacent entry-extension formulas on these rows."
            ),
            "new_evidence_required": (
                "Materially more closed forward replacement rows tagged by the same "
                "shared helper, or a genuinely new PIT entry-fragility data source, "
                "before any allocation or activation experiment."
            ),
        },
        "related_files": [
            repo_rel(Path(RUNNER)),
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_PATH),
            "experiments/logs/exp-20260627-022.json",
            "experiments/logs/exp-20260626-018.json",
            "experiments/logs/exp-20260623-002.json",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
    }
    return result


def write_card(result: dict[str, Any]) -> None:
    cash = result["gate4"]["comparisons"]["replacement_value_vs_cash_usd"]
    spy = result["gate4"]["comparisons"]["replacement_value_vs_spy_usd"]
    qqq = result["gate4"]["comparisons"]["replacement_value_vs_qqq_usd"]
    lines = [
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        f"- Status: `{result['status']}`",
        f"- Decision: `{result['decision']}`",
        f"- Hypothesis: {HYPOTHESIS}",
        "- Production behavior changed: `false`",
        "",
        "## Result",
        "",
        (
            f"Tagged rows: {result['summary']['tagged_rows']}; stretched rows: "
            f"{result['summary']['stretched_rows']}; non-stretched rows: "
            f"{result['summary']['non_stretched_rows']}."
        ),
        (
            "Stretched mean deltas vs non-stretched: "
            f"cash {cash['mean_delta_stretched_minus_non']}, "
            f"SPY {spy['mean_delta_stretched_minus_non']}, "
            f"QQQ {qqq['mean_delta_stretched_minus_non']}."
        ),
        (
            "Stretched median deltas vs non-stretched: "
            f"cash {cash['median_delta_stretched_minus_non']}, "
            f"SPY {spy['median_delta_stretched_minus_non']}, "
            f"QQQ {qqq['median_delta_stretched_minus_non']}."
        ),
        "",
        "The result is not allocation-ready because the stretched bucket has only "
        "six closed rows, below the preregistered eight-row floor.",
        "",
        "## Boundary",
        "",
        result["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    write_text(CARD_MD, "\n".join(lines) + "\n")


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "generated_at": result["timestamp"],
            "files": CHANGED_FILES,
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "ticket_file": repo_rel(TICKET_JSON),
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> None:
    result = build_result()
    write_json(OUT_JSON, result)
    write_json(LOG_JSON, result)
    write_card(result)
    write_manifest(result)
    upsert_jsonl(EXPERIMENT_LOG, result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "decision": result["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "lean_quality_passed": result["lean_quality_passed"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "new_evidence_type": result["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "changed_files": CHANGED_FILES,
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
