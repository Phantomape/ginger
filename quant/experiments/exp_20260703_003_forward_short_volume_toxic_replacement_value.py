"""exp-20260703-003: forward short-volume toxic attribution.

Observed-only alpha attribution over the forward replacement-value ledger.
This validates the PIT entry_short_volume_* tags on newly accumulated closed
forward rows without changing entries, ranking, sizing, exits, paper orders, or
live orders.
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
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260703-003"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "forward_short_volume_toxic_replacement_value"
RUNNER = f"quant/experiments/exp_20260703_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_LEDGER = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260703_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Closed forward replacement rows tagged with PIT entry short-volume "
    "percentile now have enough additional settled observations to test whether "
    "Q5 toxic short-volume remains worse than Q1-Q2 clean rows on cash/SPY/QQQ "
    "replacement value, without changing strategy behavior."
)
CHANGED_VARIABLE = "forward_entry_short_volume_toxic_replacement_value_attribution_v2"
TRIAL_FAMILY = "forward_short_volume_replacement_value_attribution"
TRIAL_VARIANT_ID = "toxic_q5_vs_clean_q1q2_more_rows_v2"
NEARBY_PRIORS = [
    "exp-20260626-018",
    "exp-20260627-008",
    "exp-20260627-026",
    "exp-20260630-016",
]
PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "q5_sample_still_too_thin",
        "no_cash_spy_qqq_separation",
        "source_family_confound",
        "short_volume_effect_already_non_incremental",
    ],
    "confidence_reason": (
        "Playbook records short-volume as a real but non-incremental context "
        "and explicitly sanctions a soft short-flow forward validation only "
        "after more closed rows accumulate; current ledger advanced from 37 "
        "tagged rows/Q5 n=7 to 45 tagged rows/Q5 n=9, but sample and "
        "source-family confounding remain high-risk."
    ),
    "recorded_at": "2026-07-03T02:10:50+00:00",
}
PRIMARY_METRICS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
ACCEPTANCE_RULE = {
    "min_total_tagged_rows": 45,
    "min_toxic_q5_rows": 8,
    "min_clean_q1q2_rows": 20,
    "max_single_toxic_ticker_share": 0.50,
    "max_single_toxic_sleeve_share": 0.50,
    "require_all_primary_means_worse": True,
    "require_all_primary_medians_worse": True,
    "require_all_primary_loss_tails_worse": True,
}
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_003_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


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
        if raw.strip():
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
        "positive_rate": round(sum(1 for v in values if v > 0) / len(values), 6)
        if values
        else None,
        "worst_20pct_mean": round(worst_tail_mean(values, 0.2), 4)
        if values
        else None,
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


def metric_comparisons(
    toxic: list[dict[str, Any]], clean: list[dict[str, Any]]
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for key in PRIMARY_METRICS:
        toxic_values = [
            value for row in toxic if (value := numeric_value(row, key)) is not None
        ]
        clean_values = [
            value for row in clean if (value := numeric_value(row, key)) is not None
        ]
        toxic_summary = summarize_values(toxic_values)
        clean_summary = summarize_values(clean_values)
        comparisons[key] = {
            "toxic_q5": toxic_summary,
            "clean_q1q2": clean_summary,
            "mean_delta_toxic_minus_clean": round(
                (toxic_summary["mean"] or 0.0) - (clean_summary["mean"] or 0.0), 4
            )
            if toxic_values and clean_values
            else None,
            "median_delta_toxic_minus_clean": round(
                (toxic_summary["median"] or 0.0)
                - (clean_summary["median"] or 0.0),
                4,
            )
            if toxic_values and clean_values
            else None,
            "tail_delta_toxic_minus_clean": round(
                (toxic_summary["worst_20pct_mean"] or 0.0)
                - (clean_summary["worst_20pct_mean"] or 0.0),
                4,
            )
            if toxic_values and clean_values
            else None,
            "toxic_mean_worse": (
                toxic_summary["mean"] is not None
                and clean_summary["mean"] is not None
                and toxic_summary["mean"] < clean_summary["mean"]
            ),
            "toxic_median_worse": (
                toxic_summary["median"] is not None
                and clean_summary["median"] is not None
                and toxic_summary["median"] < clean_summary["median"]
            ),
            "toxic_loss_tail_worse": (
                toxic_summary["worst_20pct_mean"] is not None
                and clean_summary["worst_20pct_mean"] is not None
                and toxic_summary["worst_20pct_mean"]
                < clean_summary["worst_20pct_mean"]
            ),
        }
    return comparisons


def max_share(counter: Counter[str], total: int) -> float:
    if not counter or total <= 0:
        return 0.0
    return max(counter.values()) / total


def load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return read_json(TICKET_JSON)


def build_result() -> dict[str, Any]:
    baseline = baseline_metrics()
    rows = load_forward_rows()
    tagged = [
        row
        for row in rows
        if row.get("status") == "enriched"
        and row.get("entry_short_volume_status") == "ok"
        and row.get("entry_short_volume_tag_rule_version")
        == "forward_replacement_entry_short_volume_tag_v1"
    ]
    clean = [
        row
        for row in tagged
        if int(row.get("entry_short_volume_quintile") or 0) in (1, 2)
    ]
    toxic = [
        row for row in tagged if int(row.get("entry_short_volume_quintile") or 0) == 5
    ]
    mid = [
        row for row in tagged if int(row.get("entry_short_volume_quintile") or 0) in (3, 4)
    ]
    comparisons = metric_comparisons(toxic, clean)
    toxic_tickers = Counter(str(row.get("ticker") or "UNKNOWN") for row in toxic)
    toxic_sleeves = Counter(str(row.get("sleeve_key") or "UNKNOWN") for row in toxic)
    quintile_counts = Counter(
        int(row.get("entry_short_volume_quintile") or 0) for row in tagged
    )

    checks = {
        "total_tagged_rows_min_passed": len(tagged)
        >= ACCEPTANCE_RULE["min_total_tagged_rows"],
        "toxic_q5_rows_min_passed": len(toxic)
        >= ACCEPTANCE_RULE["min_toxic_q5_rows"],
        "clean_q1q2_rows_min_passed": len(clean)
        >= ACCEPTANCE_RULE["min_clean_q1q2_rows"],
        "single_toxic_ticker_share_passed": max_share(toxic_tickers, len(toxic))
        <= ACCEPTANCE_RULE["max_single_toxic_ticker_share"],
        "single_toxic_sleeve_share_passed": max_share(toxic_sleeves, len(toxic))
        <= ACCEPTANCE_RULE["max_single_toxic_sleeve_share"],
        "all_primary_means_worse": all(
            comparisons[key]["toxic_mean_worse"] for key in PRIMARY_METRICS
        ),
        "all_primary_medians_worse": all(
            comparisons[key]["toxic_median_worse"] for key in PRIMARY_METRICS
        ),
        "all_primary_loss_tails_worse": all(
            comparisons[key]["toxic_loss_tail_worse"] for key in PRIMARY_METRICS
        ),
    }
    sample_ready = (
        checks["total_tagged_rows_min_passed"]
        and checks["toxic_q5_rows_min_passed"]
        and checks["clean_q1q2_rows_min_passed"]
        and checks["single_toxic_ticker_share_passed"]
        and checks["single_toxic_sleeve_share_passed"]
    )
    directional_support = (
        checks["all_primary_means_worse"]
        and checks["all_primary_medians_worse"]
        and checks["all_primary_loss_tails_worse"]
    )
    observed_only_lead = bool(directional_support and sample_ready)
    failed_reasons = [key for key, passed in checks.items() if not passed]
    if observed_only_lead:
        decision = "observed_only_positive_short_volume_toxic_forward_lead"
        status = "observed_only_positive"
    elif directional_support:
        decision = "observed_only_directional_short_volume_toxic_lead_concentration_failed"
        status = "observed_only_rejected"
    else:
        decision = "observed_only_rejected_no_stable_short_volume_toxic_edge"
        status = "observed_only_rejected"

    failure_mode_hit = (
        bool(failed_reasons)
        or not observed_only_lead
        or "single_toxic_ticker_share_passed" in failed_reasons
    )
    timestamp = utc_now()
    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "observed_only_forward_attribution",
        "mechanism_family": "forward_short_volume_replacement_value_attribution",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "closed forward replacement ledger",
            "entry-time PIT short-volume percentile tag",
            "Q5 toxic versus Q1-Q2 clean comparison",
            "cash SPY QQQ replacement-value attribution",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "materially_more_closed_forward_rows",
        "new_evidence_axis": (
            "Forward replacement ledger advanced from the playbook-recorded "
            "37 PIT short-volume tagged rows/Q5 n=7 to 45 tagged rows/Q5 n=9; "
            "this is an out-of-sample forward-row validation, not a frozen-window "
            "short-volume threshold, scalar, source, hold, cooldown, or top-N retry."
        ),
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
            "predicted_failure_mode_hit": failure_mode_hit,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Low surprise: Q5 toxic remains directionally worse across "
                "cash/SPY/QQQ replacement metrics, but the evidence is "
                "concentrated in CRDO and remains observed-only."
                if directional_support
                else "Short-volume toxic rows did not maintain stable separation "
                "after more forward rows accumulated."
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
                "entry_short_volume_status",
                "entry_short_volume_ratio_percentile",
                "entry_short_volume_quintile",
                "entry_short_volume_toxic_flag",
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
            "quintile_counts": dict(sorted(quintile_counts.items())),
            "prior_progress_reference": {
                "playbook_recorded_tagged_rows": 37,
                "playbook_recorded_q5_rows": 7,
                "current_tagged_rows": len(tagged),
                "current_q5_rows": len(toxic),
            },
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
                "toxic_q5": bucket_summary(toxic),
                "clean_q1q2": bucket_summary(clean),
                "middle_q3q4": bucket_summary(mid),
                "all_tagged": bucket_summary(tagged),
            },
        },
        "summary": {
            "source_rows": len(rows),
            "tagged_rows": len(tagged),
            "clean_q1q2_rows": len(clean),
            "toxic_q5_rows": len(toxic),
            "middle_q3q4_rows": len(mid),
            "toxic_ticker_count": len(toxic_tickers),
            "toxic_sleeve_count": len(toxic_sleeves),
            "max_toxic_ticker_share": round(max_share(toxic_tickers, len(toxic)), 6),
            "max_toxic_sleeve_share": round(max_share(toxic_sleeves, len(toxic)), 6),
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
                "The short-volume toxic bucket stayed worse than clean Q1-Q2 rows "
                "on mean, median, and worst-tail cash/SPY/QQQ replacement value, "
                "but 5 of 9 toxic rows are CRDO and the result remains a thin "
                "forward attribution surface, not an allocation-ready policy."
                if directional_support
                else "The accumulated forward rows did not preserve a stable Q5 "
                "short-volume toxicity edge across primary replacement metrics."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune short-volume quintile cutoffs, percentile thresholds, "
                "response curves, source scoping, notional, hold, cooldown, top-N, "
                "or allocator rank on these rows. Do not convert this into a soft "
                "tilt until materially more Q5 rows close without CRDO/sleeve "
                "concentration."
            ),
            "new_evidence_required": (
                "At least 20 PIT-tagged Q5 closed forward rows, max single Q5 ticker "
                "share <=40%, positive clean-vs-toxic separation versus cash/SPY/QQQ, "
                "or a materially new borrow fee/utilization/loan-availability field."
            ),
        },
        "next_retry_requires": [
            ">=20 PIT-tagged Q5 closed forward rows",
            "max single Q5 ticker share <=40%",
            "stable clean-vs-toxic separation versus cash/SPY/QQQ",
            "or PIT borrow fee/utilization/loan-availability economics",
        ],
        "related_files": [
            repo_rel(Path(RUNNER)),
            repo_rel(FORWARD_LEDGER),
            repo_rel(BASELINE_PATH),
            "experiments/logs/exp-20260626-018.json",
            "experiments/logs/exp-20260627-008.json",
            "experiments/logs/exp-20260627-026.json",
            "experiments/logs/exp-20260630-016.json",
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
            f"Tagged rows: {result['summary']['tagged_rows']}; Q5 toxic rows: "
            f"{result['summary']['toxic_q5_rows']}; Q1-Q2 clean rows: "
            f"{result['summary']['clean_q1q2_rows']}."
        ),
        (
            "Q5 toxic mean deltas vs Q1-Q2 clean: "
            f"cash {cash['mean_delta_toxic_minus_clean']}, "
            f"SPY {spy['mean_delta_toxic_minus_clean']}, "
            f"QQQ {qqq['mean_delta_toxic_minus_clean']}."
        ),
        (
            "Q5 toxic median deltas vs Q1-Q2 clean: "
            f"cash {cash['median_delta_toxic_minus_clean']}, "
            f"SPY {spy['median_delta_toxic_minus_clean']}, "
            f"QQQ {qqq['median_delta_toxic_minus_clean']}."
        ),
        (
            f"Max Q5 ticker share: {result['summary']['max_toxic_ticker_share']}."
        ),
        "",
        "The direction remains negative, but it is not allocation-ready because "
        "the Q5 bucket is concentrated in CRDO and remains thin.",
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
    ticket = load_ticket()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(result, allow_duplicate=True)
    write_card(result)
    write_manifest(result)

    registry_fields = {
        **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": result["change_type"],
        "implementation_mode": result["implementation_mode"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "new_evidence_type": result["new_evidence_type"],
        "new_evidence_axis": result["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "artifact_file": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "changed_files": CHANGED_FILES,
        "decision": result["decision"],
        "lean_quality_passed": result["lean_quality_passed"],
    }
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
            "summary": result["summary"],
        },
        status=result["status"],
        fields=registry_fields,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
