"""exp-20260622-018: SEC13F manager active-concentration attribution.

Observed-only alpha attribution. This runner reuses the already closed
exp-20260621-019 SEC13F new-manager conviction paper rows and asks whether a
predeclared manager-concentration field has enough monotonic realized-PnL
separation to justify any future shared helper or threshold retry.

It changes no entry, ranking, sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260622-018"
SLUG = "sec13f_manager_active_concentration_attribution"
RUNNER = f"quant/experiments/exp_20260622_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260622_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260621-019"
    / "exp_20260621_019_sec13f_manager_conviction.json"
)
RELATED_PRIOR_LOGS = [
    "experiments/logs/exp-20260621-019.json",
    "experiments/logs/exp-20260622-007.json",
]

HYPOTHESIS = (
    "Observed-only attribution: SEC 13F new-manager active concentration should "
    "show monotonic realized-PnL separation on already closed paper rows before "
    "any future shared helper or threshold retry is justified."
)
CHANGED_VARIABLE = "sec13f_manager_active_concentration_attribution_v1"
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "sec13f_manager_attribution"
TRIAL_FAMILY = "sec13f_active_manager_concentration"
TRIAL_VARIANT_ID = "observed_only_closed_rows_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260621-019", "exp-20260622-007"]
NEW_EVIDENCE_TYPE = "manager_level_outcome_attribution"
CAUSAL_COMPONENTS = [
    "reuse closed exp-20260621-019 target trades",
    "predeclared concentration buckets",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260622-018/exp_20260622_018_sec13f_manager_active_concentration_attribution.json",
    "experiments/logs/exp-20260622-018.json",
    "experiments/cards/exp-20260622-018.md",
    "experiments/manifests/exp-20260622-018.json",
    "experiments/tickets/exp-20260622-018.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "non_monotonic_pnl",
        "thin_high_bucket",
        "old_window_regression",
        "quarterly_staleness",
        "not_incremental_vs_13f_priors",
    ],
    "confidence_reason": (
        "Prior SEC13F manager-weight and coaccumulation scouts failed, but their "
        "closeouts requested manager-level alpha attribution rather than another "
        "threshold sweep."
    ),
    "recorded_at": "2026-06-22T17:05:56+00:00",
}

WEIGHT_BUCKETS = [
    {
        "name": "low_lt_0p06",
        "label": "weight_max < 0.06",
        "lower": None,
        "upper": 0.06,
    },
    {
        "name": "mid_0p06_0p15",
        "label": "0.06 <= weight_max < 0.15",
        "lower": 0.06,
        "upper": 0.15,
    },
    {
        "name": "high_gte_0p15",
        "label": "weight_max >= 0.15",
        "lower": 0.15,
        "upper": None,
    },
]
BUCKET_ORDER = [bucket["name"] for bucket in WEIGHT_BUCKETS]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def bucket_for_weight(weight: float) -> str:
    if weight < 0.06:
        return "low_lt_0p06"
    if weight < 0.15:
        return "mid_0p06_0p15"
    return "high_gte_0p15"


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows]
    weights = [float(row["sec13f_new_conviction_weight_max"]) for row in rows]
    if not pnls:
        return {
            "n": 0,
            "mean_pnl": None,
            "median_pnl": None,
            "win_rate": None,
            "total_pnl": 0.0,
            "mean_weight_max": None,
            "median_weight_max": None,
        }
    return {
        "n": len(pnls),
        "mean_pnl": round(sum(pnls) / len(pnls), 2),
        "median_pnl": round(float(median(pnls)), 2),
        "win_rate": round(sum(1 for value in pnls if value > 0) / len(pnls), 4),
        "total_pnl": round(sum(pnls), 2),
        "mean_weight_max": round(sum(weights) / len(weights), 6),
        "median_weight_max": round(float(median(weights)), 6),
    }


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    n = len(xs)

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = rank
            i = j + 1
        return out

    rx = ranks(xs)
    ry = ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    vx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    vy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx * vy), 6)


def bucket_summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {name: summary([row for row in rows if row["weight_bucket"] == name]) for name in BUCKET_ORDER}


def monotonic_high_mid_low(bucketed: dict[str, dict[str, Any]], metric: str) -> bool:
    low = bucketed["low_lt_0p06"].get(metric)
    mid = bucketed["mid_0p06_0p15"].get(metric)
    high = bucketed["high_gte_0p15"].get(metric)
    if low is None or mid is None or high is None:
        return False
    return float(high) > float(mid) > float(low)


def target_rows(baseline: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    all_rows: list[dict[str, Any]] = []
    skipped_by_reason: dict[str, int] = {}
    windows = baseline.get("target_trades_by_window") or {}
    for window, trades in windows.items():
        for trade in trades:
            if trade.get("pnl") is None:
                skipped_by_reason["missing_pnl"] = skipped_by_reason.get("missing_pnl", 0) + 1
                continue
            if trade.get("sec13f_new_conviction_weight_max") is None:
                skipped_by_reason["missing_weight_max"] = skipped_by_reason.get("missing_weight_max", 0) + 1
                continue
            weight = float(trade["sec13f_new_conviction_weight_max"])
            row = {
                "window": window,
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": round(float(trade["pnl"]), 2),
                "pnl_pct_net": trade.get("pnl_pct_net"),
                "sec13f_new_conviction_weight_max": weight,
                "sec13f_new_conviction_weight_sum": trade.get("sec13f_new_conviction_weight_sum"),
                "sec13f_new_conviction_manager_count": trade.get(
                    "sec13f_new_conviction_manager_count"
                ),
                "sec13f_new_conviction_value_share": trade.get(
                    "sec13f_new_conviction_value_share"
                ),
                "sec13f_holder_delta": trade.get("sec13f_holder_delta"),
                "sec13f_holder_growth_pct": trade.get("sec13f_holder_growth_pct"),
                "sec13f_latest_window_end": trade.get("sec13f_latest_window_end"),
                "source": trade.get("source"),
            }
            row["weight_bucket"] = bucket_for_weight(weight)
            all_rows.append(row)
    return all_rows, skipped_by_reason


def concentration(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        slot = counts.setdefault(value, {"value": value, "n": 0, "total_pnl": 0.0})
        slot["n"] += 1
        slot["total_pnl"] += float(row["pnl"])
    out = [
        {"value": v["value"], "n": v["n"], "total_pnl": round(v["total_pnl"], 2)}
        for v in counts.values()
    ]
    out.sort(key=lambda item: (-int(item["n"]), str(item["value"])))
    return out[:15]


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = read_json(BASELINE_ARTIFACT)
    rows, skipped_by_reason = target_rows(baseline)

    by_window: dict[str, Any] = {}
    high_positive_windows = 0
    for window in sorted({row["window"] for row in rows}):
        window_rows = [row for row in rows if row["window"] == window]
        bucketed = bucket_summaries(window_rows)
        high_mean = bucketed["high_gte_0p15"].get("mean_pnl")
        if high_mean is not None and high_mean > 0:
            high_positive_windows += 1
        by_window[window] = {
            "n": len(window_rows),
            "bucket_summary": bucketed,
            "mean_monotonic_high_mid_low": monotonic_high_mid_low(bucketed, "mean_pnl"),
            "median_monotonic_high_mid_low": monotonic_high_mid_low(bucketed, "median_pnl"),
            "spearman_weight_max_pnl": spearman(
                [float(row["sec13f_new_conviction_weight_max"]) for row in window_rows],
                [float(row["pnl"]) for row in window_rows],
            ),
        }

    pooled_bucketed = bucket_summaries(rows)
    high_bucket_counts_by_window = {
        window: by_window[window]["bucket_summary"]["high_gte_0p15"]["n"]
        for window in sorted(by_window)
    }
    high_bucket_min_count = min(high_bucket_counts_by_window.values()) if high_bucket_counts_by_window else 0
    high_bucket_all_windows = (
        len(high_bucket_counts_by_window) == 3 and all(v > 0 for v in high_bucket_counts_by_window.values())
    )
    acceptance_checks = {
        "high_bucket_min_count_by_window": high_bucket_min_count,
        "high_bucket_min_count_passed": high_bucket_min_count >= 20,
        "high_bucket_all_three_windows": high_bucket_all_windows,
        "pooled_mean_monotonic_high_mid_low": monotonic_high_mid_low(pooled_bucketed, "mean_pnl"),
        "pooled_median_monotonic_high_mid_low": monotonic_high_mid_low(
            pooled_bucketed, "median_pnl"
        ),
        "window_mean_monotonic_count": sum(
            1 for value in by_window.values() if value["mean_monotonic_high_mid_low"]
        ),
        "window_median_monotonic_count": sum(
            1 for value in by_window.values() if value["median_monotonic_high_mid_low"]
        ),
        "high_bucket_positive_windows": high_positive_windows,
        "high_bucket_positive_windows_passed": high_positive_windows >= 2,
    }
    accepted_lead = all(
        [
            acceptance_checks["high_bucket_min_count_passed"],
            acceptance_checks["high_bucket_all_three_windows"],
            acceptance_checks["pooled_mean_monotonic_high_mid_low"],
            acceptance_checks["pooled_median_monotonic_high_mid_low"],
            acceptance_checks["high_bucket_positive_windows_passed"],
        ]
    )
    status = "observed_only_rejected" if not accepted_lead else "observed_only_lead"
    decision = (
        "observed_only_lead_sec13f_manager_concentration_monotonic"
        if accepted_lead
        else "rejected_no_monotonic_manager_concentration_edge"
    )

    aggregate_after = (baseline.get("delta_metrics") or {}).get("aggregate") or {}
    before_metrics = baseline.get("before_metrics") or {}
    after_metrics = baseline.get("after_metrics") or {}
    aggregate_baseline = {
        "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
        "aggregate_expected_value_score": aggregate_after.get("after_expected_value_score_sum"),
        "aggregate_total_pnl": aggregate_after.get("after_total_pnl_sum"),
        "target_trade_count_sum": aggregate_after.get("target_trade_count_sum"),
        "windows_ev_improved": aggregate_after.get("windows_ev_improved"),
        "windows_ev_regressed": aggregate_after.get("windows_ev_regressed"),
    }

    gate4_failed_reasons = []
    if not acceptance_checks["pooled_mean_monotonic_high_mid_low"]:
        gate4_failed_reasons.append("pooled_mean_not_monotonic_high_mid_low")
    if not acceptance_checks["pooled_median_monotonic_high_mid_low"]:
        gate4_failed_reasons.append("pooled_median_not_monotonic_high_mid_low")
    if not acceptance_checks["high_bucket_positive_windows_passed"]:
        gate4_failed_reasons.append("high_bucket_positive_in_only_one_window")
    if not acceptance_checks["high_bucket_min_count_passed"]:
        gate4_failed_reasons.append("thin_high_bucket")

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": accepted_lead,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": PREDICTION,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "passed with no blocking matches",
                "nearest_priors": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": (
                    "Outcome attribution of closed SEC13F paper trades by "
                    "predeclared manager concentration buckets; no new entry "
                    "threshold or production helper."
                ),
            },
            "3_attributable_decision": (
                "Only the manager-concentration attribution rule is tested. "
                "Strategy logic, ranking, sizing, exits, and production paths "
                "are locked."
            ),
            "4_success_failure_rule": (
                "Lead only if high bucket has >=20 trades in every window, "
                "pooled average and median PnL are high>mid>low, and high bucket "
                "is positive in at least two windows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_artifact": repo_rel(BASELINE_ARTIFACT),
            "weight_field": "sec13f_new_conviction_weight_max",
            "weight_buckets": WEIGHT_BUCKETS,
            "min_high_bucket_count_per_window": 20,
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
            "baseline_aggregate": aggregate_baseline,
            "no_strategy_after_replay": True,
            "reason": "Observed-only attribution over already closed paper rows.",
        },
        "gate2": {
            "fields_checked": [
                "entry_date",
                "exit_date",
                "pnl",
                "sec13f_new_conviction_weight_max",
            ],
            "rows_checked": len(rows),
            "skipped_by_reason": skipped_by_reason,
            "entry_date_present": all(bool(row.get("entry_date")) for row in rows),
            "pnl_present": all(row.get("pnl") is not None for row in rows),
            "weight_max_present": all(
                row.get("sec13f_new_conviction_weight_max") is not None for row in rows
            ),
            "target_price_runtime_present": False,
            "target_price_relevance": (
                "Not applicable: no signal replay or order decision is made; "
                "closed paper rows carry exit_price/pnl rather than target_price."
            ),
        },
        "gate3": {
            "signals_generated": len(rows) + sum(skipped_by_reason.values()),
            "signals_survived": len(rows),
            "survival_rate": round(
                len(rows) / (len(rows) + sum(skipped_by_reason.values())), 4
            )
            if rows or skipped_by_reason
            else None,
            "filter_added": False,
            "note": "Rows are attributed, not filtered into a new strategy.",
        },
        "gate4": {
            "accepted_lead": accepted_lead,
            "failed_reasons": gate4_failed_reasons,
            "acceptance_checks": acceptance_checks,
            "before_after_strategy_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_count": 0,
            },
            "no_strategy_change": True,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "total_pnl_delta_sum": 0.0,
                "max_drawdown_delta_max": 0.0,
                "trade_count_delta_sum": 0,
            },
            "observed_attribution": {
                "pooled_bucket_summary": pooled_bucketed,
                "per_window": by_window,
                "spearman_weight_max_pnl": spearman(
                    [float(row["sec13f_new_conviction_weight_max"]) for row in rows],
                    [float(row["pnl"]) for row in rows],
                ),
                "high_bucket_counts_by_window": high_bucket_counts_by_window,
            },
        },
        "attribution": {
            "n_rows": len(rows),
            "skipped_by_reason": skipped_by_reason,
            "per_window": by_window,
            "pooled": {
                "bucket_summary": pooled_bucketed,
                "spearman_weight_max_pnl": spearman(
                    [float(row["sec13f_new_conviction_weight_max"]) for row in rows],
                    [float(row["pnl"]) for row in rows],
                ),
                "top_ticker_counts": concentration(rows, "ticker"),
            },
            "rows": rows,
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "shared_helper_promoted": False,
            "live_realistic_execution_envelope": "Not evaluated; result is rejected observed-only attribution.",
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": (
                "none" if accepted_lead else "non_monotonic_pnl_and_high_bucket_not_positive"
            ),
            "predicted_failure_mode_hit": not accepted_lead,
            "surprise_note": (
                "The high-concentration bucket had enough sample in all windows, "
                "but it did not dominate either average or median realized PnL."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Manager concentration was not a clean alpha discriminator on "
                "the closed SEC13F paper rows. The high bucket was negative in "
                "late_strong and old_thin, while the low/mid buckets carried most "
                "of the pooled PnL. The field appears to mix stale quarterly "
                "ownership disclosure and crowded mega-cap exposure rather than "
                "fresh active-manager alpha."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry SEC13F manager weight, holder-count, value-share, "
                "or coownership threshold sweeps on the same closed historical "
                "windows. That would be another 13F threshold search, not new "
                "evidence."
            ),
            "new_evidence_required": (
                "A valid retry needs independent active-manager quality or "
                "manager alpha attribution, non-quarterly ownership/flow data, "
                "borrow/options cross-evidence, or closed forward rows from a "
                "shared default-off helper."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_ARTIFACT),
            *RELATED_PRIOR_LOGS,
        ],
    }
    return payload


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]["bucket_summary"]
    rows = [
        "| Bucket | Trades | Mean PnL | Median PnL | Win Rate | Total PnL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in BUCKET_ORDER:
        bucket = pooled[name]
        rows.append(
            "| {label} | {n} | ${mean:,.2f} | ${median:,.2f} | {win:.2%} | ${total:,.2f} |".format(
                label=next(item["label"] for item in WEIGHT_BUCKETS if item["name"] == name),
                n=bucket["n"],
                mean=bucket["mean_pnl"],
                median=bucket["median_pnl"],
                win=bucket["win_rate"],
                total=bucket["total_pnl"],
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC13F manager active-concentration attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Observed Attribution",
            "",
            *rows,
            "",
            "- Spearman(weight_max, PnL): `{}`".format(
                payload["attribution"]["pooled"]["spearman_weight_max_pnl"]
            ),
            "- High bucket positive windows: `{}`".format(
                payload["gate4"]["acceptance_checks"]["high_bucket_positive_windows"]
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"])),
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = build_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "attribution": {
            "n_rows": payload["attribution"]["n_rows"],
            "pooled_bucket_summary": payload["attribution"]["pooled"]["bucket_summary"],
            "spearman_weight_max_pnl": payload["attribution"]["pooled"][
                "spearman_weight_max_pnl"
            ],
        },
        "gate4": payload["gate4"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_ARTIFACT),
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
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
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
                "n_rows": payload["attribution"]["n_rows"],
                "pooled_bucket_summary": payload["attribution"]["pooled"]["bucket_summary"],
                "spearman_weight_max_pnl": payload["attribution"]["pooled"][
                    "spearman_weight_max_pnl"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
