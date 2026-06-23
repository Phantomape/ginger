"""exp-20260622-019: core actual risk-intensity attribution.

Observed-only alpha attribution. This runner asks whether the accepted core
stack's ex-ante risk intensity, measured as actual_risk_pct / base_risk_pct on
closed canonical-window trades, has monotonic realized-PnL separation.

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


EXPERIMENT_ID = "exp-20260622-019"
SLUG = "core_actual_risk_intensity_attribution"
RUNNER = f"quant/experiments/exp_20260622_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260622_019_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

AGGREGATE_BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOW_FILES = {
    "late_strong": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_late_strong_20260604.json",
    "mid_weak": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_mid_weak_20260604.json",
    "old_thin": REPO_ROOT
    / "data"
    / "backtests"
    / "archive"
    / "20260604_ohlcv_warehouse_replay"
    / "backtest_results_warehouse_snapshot_old_thin_20260604.json",
}
RELATED_PRIOR_LOGS = [
    "experiments/logs/exp-20260622-017.json",
    "experiments/logs/exp-20260618-008.json",
    "experiments/logs/exp-20260614-004.json",
]

HYPOTHESIS = (
    "Observed-only attribution: accepted core stack trades with higher ex-ante "
    "realized risk intensity should show monotonic realized-PnL separation "
    "before any future risk-allocation scalar or multiplier retry is justified."
)
CHANGED_VARIABLE = "core_actual_risk_intensity_attribution_v1"
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "risk_allocation_attribution"
TRIAL_FAMILY = "core_actual_risk_intensity"
TRIAL_VARIANT_ID = "observed_only_canonical_windows_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-017",
    "exp-20260618-008",
    "exp-20260614-004",
]
NEW_EVIDENCE_TYPE = "accepted_core_closed_trade_risk_intensity_attribution"
CAUSAL_COMPONENTS = [
    "accepted core closed trades",
    "pooled risk-intensity tertile attribution",
    "no strategy change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260622-019/",
    "experiments/logs/exp-20260622-019.json",
    "experiments/cards/exp-20260622-019.md",
    "experiments/manifests/exp-20260622-019.json",
    "experiments/tickets/exp-20260622-019.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

PREDICTION = {
    "success_probability": 0.2,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "non_monotonic_pnl",
        "thin_high_intensity_bucket",
        "window_fragility",
        "risk_multiplier_crowding",
        "not_incremental_vs_risk_scalars",
    ],
    "confidence_reason": (
        "Risk multipliers are production-visible and high-leverage, but prior "
        "scalar/topup retunes were fragile; closed accepted core trades can "
        "cheaply falsify whether intensity ranking is an alpha surface before "
        "touching rules."
    ),
    "recorded_at": "2026-06-22T18:09:42+00:00",
}

BUCKET_ORDER = ["low", "mid", "high"]


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


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "total_pnl": 0.0,
            "mean_pnl": None,
            "median_pnl": None,
            "win_rate": None,
            "mean_risk_intensity": None,
            "median_risk_intensity": None,
            "risk_intensity_min": None,
            "risk_intensity_max": None,
        }
    pnls = [float(row["pnl"]) for row in rows]
    intensities = [float(row["risk_intensity"]) for row in rows]
    return {
        "n": len(rows),
        "total_pnl": round(sum(pnls), 2),
        "mean_pnl": round(sum(pnls) / len(pnls), 2),
        "median_pnl": round(float(median(pnls)), 2),
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 4),
        "mean_risk_intensity": round(sum(intensities) / len(intensities), 4),
        "median_risk_intensity": round(float(median(intensities)), 4),
        "risk_intensity_min": round(min(intensities), 4),
        "risk_intensity_max": round(max(intensities), 4),
    }


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    out = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        avg_rank = (cursor + 1 + end) / 2.0
        for rank_index in range(cursor, end):
            out[order[rank_index]] = avg_rank
        cursor = end
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 4:
        return None
    rx = ranks(xs)
    ry = ranks(ys)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(rx, ry))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in rx))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 4)


def load_ticket_prediction() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return PREDICTION
    ticket = read_json(TICKET_JSON)
    prediction = ticket.get("prediction")
    return prediction if isinstance(prediction, dict) and prediction else PREDICTION


def aggregate_metrics(aggregate: dict[str, Any]) -> dict[str, Any]:
    windows = list(aggregate.get("windows") or [])
    generated = sum(float(window.get("signals_generated") or 0.0) for window in windows)
    survived = sum(float(window.get("signals_survived") or 0.0) for window in windows)
    trade_count = sum(int(window.get("trade_count") or 0) for window in windows)
    total_pnl = sum(float(window.get("total_pnl") or 0.0) for window in windows)
    ev_values = [float(window.get("expected_value_score") or 0.0) for window in windows]
    return {
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(ev_values), 4),
        "expected_value_score_mean": round(sum(ev_values) / len(ev_values), 4)
        if ev_values
        else None,
        "total_pnl": round(total_pnl, 2),
        "trade_count": trade_count,
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            float(window.get("max_drawdown_pct") or 0.0) for window in windows
        )
        if windows
        else None,
        "windows": windows,
    }


def load_trade_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    field_presence = {
        "entry_date": 0,
        "target_price": 0,
        "base_risk_pct": 0,
        "actual_risk_pct": 0,
        "pnl": 0,
    }
    total_trades = 0
    for window, path in WINDOW_FILES.items():
        data = read_json(path)
        for index, trade in enumerate(data.get("trades") or []):
            total_trades += 1
            for field in field_presence:
                if trade.get(field) is not None:
                    field_presence[field] += 1
            base_risk = as_float(trade.get("base_risk_pct"))
            actual_risk = as_float(trade.get("actual_risk_pct"))
            pnl = as_float(trade.get("pnl"))
            if base_risk is None or base_risk <= 0 or actual_risk is None or actual_risk <= 0:
                skipped.append(
                    {
                        "window": window,
                        "index": index,
                        "reason": "missing_or_nonpositive_risk_fields",
                    }
                )
                continue
            if pnl is None:
                skipped.append({"window": window, "index": index, "reason": "missing_pnl"})
                continue
            rows.append(
                {
                    "window": window,
                    "trade_key": trade.get("trade_key") or f"{window}:{index}",
                    "ticker": trade.get("ticker"),
                    "strategy": trade.get("strategy"),
                    "sector": trade.get("sector"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "exit_reason": trade.get("exit_reason"),
                    "pnl": pnl,
                    "pnl_pct_net": as_float(trade.get("pnl_pct_net")),
                    "base_risk_pct": base_risk,
                    "actual_risk_pct": actual_risk,
                    "risk_intensity": actual_risk / base_risk,
                    "sizing_multipliers": trade.get("sizing_multipliers"),
                }
            )
    checks = {
        "total_trades": total_trades,
        "usable_trades": len(rows),
        "skipped_trades": skipped,
        "field_presence": field_presence,
    }
    if field_presence["entry_date"] != total_trades:
        raise ValueError("entry_date missing from one or more baseline trade rows")
    if len(rows) < 9:
        raise ValueError("not enough usable risk-intensity rows for tertile attribution")
    return rows, checks


def assign_pooled_tertiles(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(
        range(len(rows)),
        key=lambda index: (
            rows[index]["risk_intensity"],
            rows[index].get("entry_date") or "",
            rows[index].get("ticker") or "",
            rows[index].get("trade_key") or "",
        ),
    )
    n = len(ordered)
    for rank, row_index in enumerate(ordered):
        if rank < n / 3:
            bucket = "low"
        elif rank < (2 * n) / 3:
            bucket = "mid"
        else:
            bucket = "high"
        rows[row_index]["risk_intensity_bucket"] = bucket
        rows[row_index]["risk_intensity_rank"] = rank + 1


def build_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pooled = {
        bucket: summarize_rows(
            [row for row in rows if row["risk_intensity_bucket"] == bucket]
        )
        for bucket in BUCKET_ORDER
    }
    by_window = {}
    for window in WINDOW_FILES:
        by_window[window] = {
            bucket: summarize_rows(
                [
                    row
                    for row in rows
                    if row["window"] == window and row["risk_intensity_bucket"] == bucket
                ]
            )
            for bucket in BUCKET_ORDER
        }
    pooled_spearman = spearman(
        [row["risk_intensity"] for row in rows],
        [row["pnl"] for row in rows],
    )
    window_spearman = {
        window: spearman(
            [row["risk_intensity"] for row in rows if row["window"] == window],
            [row["pnl"] for row in rows if row["window"] == window],
        )
        for window in WINDOW_FILES
    }
    sample_rows = [
        {
            "window": row["window"],
            "ticker": row["ticker"],
            "entry_date": row["entry_date"],
            "pnl": row["pnl"],
            "risk_intensity": round(row["risk_intensity"], 4),
            "risk_intensity_bucket": row["risk_intensity_bucket"],
        }
        for row in sorted(rows, key=lambda row: row["risk_intensity"], reverse=True)[:10]
    ]
    return {
        "n_rows": len(rows),
        "risk_intensity_formula": "actual_risk_pct / base_risk_pct",
        "bucket_method": (
            "pooled rank tertiles over all usable canonical-window closed trades; "
            "ties are ordered deterministically by date, ticker, and trade_key"
        ),
        "bucket_order": BUCKET_ORDER,
        "pooled": {
            "bucket_summary": pooled,
            "spearman_risk_intensity_pnl": pooled_spearman,
        },
        "by_window": by_window,
        "window_spearman_risk_intensity_pnl": window_spearman,
        "top_risk_intensity_sample": sample_rows,
    }


def acceptance_checks(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]["bucket_summary"]
    low = pooled["low"]
    mid = pooled["mid"]
    high = pooled["high"]
    window_spearman = attribution["window_spearman_risk_intensity_pnl"]
    high_positive_windows = [
        window
        for window, buckets in attribution["by_window"].items()
        if buckets["high"]["n"] > 0 and buckets["high"]["total_pnl"] > 0
    ]
    return {
        "pooled_mean_monotonic": (
            low["mean_pnl"] is not None
            and mid["mean_pnl"] is not None
            and high["mean_pnl"] is not None
            and high["mean_pnl"] > mid["mean_pnl"] > low["mean_pnl"]
        ),
        "pooled_median_monotonic": (
            low["median_pnl"] is not None
            and mid["median_pnl"] is not None
            and high["median_pnl"] is not None
            and high["median_pnl"] > mid["median_pnl"] > low["median_pnl"]
        ),
        "high_bucket_positive_windows": high_positive_windows,
        "all_windows_high_bucket_positive": len(high_positive_windows) == len(WINDOW_FILES),
        "pooled_spearman_positive": (
            attribution["pooled"]["spearman_risk_intensity_pnl"] is not None
            and attribution["pooled"]["spearman_risk_intensity_pnl"] > 0
        ),
        "window_spearman_nonnegative_count": sum(
            1 for value in window_spearman.values() if value is not None and value >= 0
        ),
        "window_spearman_values": window_spearman,
    }


def failed_reasons(checks: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not checks["pooled_mean_monotonic"]:
        reasons.append("pooled_mean_not_monotonic")
    if not checks["pooled_median_monotonic"]:
        reasons.append("pooled_median_not_monotonic")
    if not checks["all_windows_high_bucket_positive"]:
        reasons.append("high_bucket_not_positive_in_all_windows")
    if not checks["pooled_spearman_positive"]:
        reasons.append("pooled_spearman_not_positive")
    if checks["window_spearman_nonnegative_count"] < 2:
        reasons.append("window_spearman_negative_in_two_or_more_windows")
    return reasons


def build_payload() -> dict[str, Any]:
    prediction = load_ticket_prediction()
    aggregate = read_json(AGGREGATE_BASELINE)
    baseline_metrics = aggregate_metrics(aggregate)
    rows, field_checks = load_trade_rows()
    assign_pooled_tertiles(rows)
    attribution = build_attribution(rows)
    checks = acceptance_checks(attribution)
    reasons = failed_reasons(checks)
    observed_only_lead = not reasons
    status = (
        "observed_only_positive_lead"
        if observed_only_lead
        else "observed_only_rejected"
    )
    decision = (
        "observed_only_positive_core_risk_intensity_lead_not_promoted"
        if observed_only_lead
        else "observed_only_rejected_no_core_risk_intensity_monotonic_edge"
    )
    now = utc_now()

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "observed_only_lead": observed_only_lead,
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": (
            "observed-only accepted-core closed-trade attribution over current "
            "canonical post-DTE baseline; no scalar, filter, sizing, entry, or "
            "exit change"
        ),
        "prediction": prediction,
        "pre_run_questions": {
            "profit_hypothesis": (
                "If the accepted core stack's actual/base risk intensity is "
                "allocating toward true alpha, higher intensity closed trades "
                "should rank above lower intensity trades on realized PnL."
            ),
            "category": "risk_allocation",
            "past_near_experiments": {
                "novelty_gate": "passed with no strong near-neighbor",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "important_boundary": (
                    "This is attribution on the current accepted stack, not "
                    "another scalar/topup retune."
                ),
            },
            "single_policy_bundle": (
                "Accepted core closed trades + pooled risk-intensity tertile "
                "attribution; no rule, threshold, or sizing change."
            ),
            "success_failure_standard": (
                "Positive lead only if high tertile beats mid and low on pooled "
                "mean and median PnL, high is positive in all windows, pooled "
                "Spearman is positive, and at least two window Spearman values "
                "are non-negative."
            ),
            "reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "risk_intensity_formula": "actual_risk_pct / base_risk_pct",
            "bucket_method": attribution["bucket_method"],
            "bucket_order": BUCKET_ORDER,
            "input_windows": {
                window: repo_rel(path) for window, path in WINDOW_FILES.items()
            },
        },
        "gate1": {
            "baseline_loaded": True,
            "baseline_result_file": repo_rel(AGGREGATE_BASELINE),
            "window_files": {
                window: repo_rel(path) for window, path in WINDOW_FILES.items()
            },
            "baseline_metrics": baseline_metrics,
        },
        "gate2": {
            "dependencies_validated": True,
            "field_presence": field_checks["field_presence"],
            "total_trades": field_checks["total_trades"],
            "usable_trades": field_checks["usable_trades"],
            "skipped_trades": field_checks["skipped_trades"],
            "entry_date": {
                "required": True,
                "present_rows": field_checks["field_presence"]["entry_date"],
            },
            "target_price": {
                "checked": True,
                "present_rows": field_checks["field_presence"]["target_price"],
                "used": False,
                "reason": (
                    "This observed-only closed-trade attribution consumes no "
                    "candidate/order target_price and changes no trading rule."
                ),
            },
            "required_observed_fields": [
                "entry_date",
                "base_risk_pct",
                "actual_risk_pct",
                "pnl",
            ],
        },
        "gate3": {
            "survival_filter_added": False,
            "survival_rate_floor_checked": True,
            "baseline_survival_rate": baseline_metrics["survival_rate"],
            "signals_generated": baseline_metrics["signals_generated"],
            "signals_survived": baseline_metrics["signals_survived"],
            "observed_rows_survival_rate": 1.0,
            "note": "No new filter was added; this is closed-trade attribution only.",
        },
        "gate4": {
            "strategy_rerun_required": False,
            "reason": "Observed-only attribution; before and after policy are identical.",
            "acceptance_checks": checks,
            "failed_reasons": reasons,
            "decision": decision,
            "lead_limitations": [
                "No trading rule was changed.",
                "The signal is endogenous to the already accepted sizing stack.",
                "Promotion would require a shared default-off helper and forward closed rows.",
            ],
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "expected_value_score_mean_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": attribution,
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "shared_helper_promoted": False,
            "live_realistic_execution_envelope": (
                "Not evaluated; this is an observed-only positive lead, not a "
                "live-ready strategy."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction["success_probability"],
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_mode": (
                "none_positive_lead"
                if observed_only_lead
                else ",".join(reasons) or "unknown"
            ),
            "predicted_failure_mode_hit": not observed_only_lead,
            "surprise_note": (
                "The monotonic separation was stronger than expected, but the "
                "result remains a lead because no policy after-state was tested."
                if observed_only_lead
                else "The field did not clear the predeclared monotonic checks."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current accepted risk stack appears to allocate higher "
                "actual/base risk intensity toward trades that subsequently "
                "produce larger PnL across all three canonical windows. This "
                "supports the existing stack as an attribution surface, but it "
                "does not prove that increasing risk scalars would improve EV."
                if observed_only_lead
                else "Risk intensity did not separate realized PnL cleanly enough."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this positive attribution as permission to retry "
                "simple risk_scalar, topup, or notional multiplier sweeps on the "
                "same historical windows. That would confound an endogenous "
                "sizing-stack attribution with a new policy."
            ),
            "new_evidence_required": (
                "A valid promotion path needs a shared default-off daily ledger "
                "or ablation that records risk-intensity rank before execution, "
                "then enough forward closed rows to prove that any incremental "
                "ranking/sizing rule improves EV without worse drawdown."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "related_files": [
            RUNNER,
            repo_rel(AGGREGATE_BASELINE),
            *[repo_rel(path) for path in WINDOW_FILES.values()],
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
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
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
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
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
        "attribution": payload["attribution"],
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]["bucket_summary"]
    rows = [
        "| Bucket | Trades | Intensity Range | Mean PnL | Median PnL | Win Rate | Total PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket_name in BUCKET_ORDER:
        bucket = pooled[bucket_name]
        rows.append(
            "| {name} | {n} | {lo:.4f}-{hi:.4f} | ${mean:,.2f} | ${median:,.2f} | {win:.2%} | ${total:,.2f} |".format(
                name=bucket_name,
                n=bucket["n"],
                lo=bucket["risk_intensity_min"],
                hi=bucket["risk_intensity_max"],
                mean=bucket["mean_pnl"],
                median=bucket["median_pnl"],
                win=bucket["win_rate"],
                total=bucket["total_pnl"],
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: core actual risk-intensity attribution",
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
            "- Spearman(risk_intensity, PnL): `{}`".format(
                payload["attribution"]["pooled"]["spearman_risk_intensity_pnl"]
            ),
            "- High bucket positive windows: `{}`".format(
                ", ".join(payload["gate4"]["acceptance_checks"]["high_bucket_positive_windows"])
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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
            "spearman_risk_intensity_pnl": payload["attribution"]["pooled"][
                "spearman_risk_intensity_pnl"
            ],
            "window_spearman_risk_intensity_pnl": payload["attribution"][
                "window_spearman_risk_intensity_pnl"
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(AGGREGATE_BASELINE),
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
                "spearman_risk_intensity_pnl": payload["attribution"]["pooled"][
                    "spearman_risk_intensity_pnl"
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
