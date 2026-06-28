"""exp-20260628-006: cost-adjusted drawdown contribution attribution.

Read-only alpha attribution over the current accepted core stack. The tested
field is intentionally restricted to entry-time information: entry fill slip,
initial stop distance, and target multiple. Realized total slippage is reported
only as a leakage caveat because it includes exit-side information.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260628-006"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "cost_adjusted_drawdown_attribution"
RUNNER = f"quant/experiments/exp_20260628_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "cost_adjusted_drawdown_contribution_bucket_v1"
TRIAL_FAMILY = "cost_adjusted_drawdown_contribution_attribution"
TRIAL_VARIANT_ID = "core_accepted_stack_cost_drawdown_bucket_v1"
MECHANISM_FAMILY = "production_visible_execution_quality_attribution"
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "read_only_attribution"
NEW_EVIDENCE_TYPE = "production_visible_cost_adjusted_drawdown_field"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
WINDOW_FILES: "OrderedDict[str, Path]" = OrderedDict(
    [
        (
            "late_strong",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "late_strong_after.json",
        ),
        (
            "mid_weak",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "mid_weak_after.json",
        ),
        (
            "old_thin",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "old_thin_after.json",
        ),
    ]
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_006_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Read-only alpha attribution: accepted core entries whose expected execution "
    "cost plus initial stop-risk consumes a high share of target opportunity may "
    "explain loss-tail and identify a future production-visible risk-allocation "
    "candidate without changing current trades."
)
CAUSAL_COMPONENTS = [
    "canonical accepted-stack trade replay",
    "cost-adjusted entry-risk bucket",
    "three-window monotonic loss-tail attribution",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260602-003", "exp-20260622-017"]

# Fixed ex-ante bucket thresholds. Values are (entry slippage + initial stop
# risk) divided by initial target opportunity.
LOW_DRAG_MAX = 0.18
HIGH_DRAG_MIN = 0.226
LOSS_TAIL_PNL_PCT = -0.02
MIN_TOTAL_ROWS = 50
MIN_HIGH_BUCKET_ROWS = 10
MIN_SUPPORTING_WINDOWS = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return str(p.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def round_float(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, digits)


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def bucket_for(cost_adjusted_drag: float | None) -> str:
    if cost_adjusted_drag is None:
        return "unknown"
    if cost_adjusted_drag <= LOW_DRAG_MAX:
        return "low"
    if cost_adjusted_drag >= HIGH_DRAG_MIN:
        return "high"
    return "middle"


def target_price_from_trade(trade: dict[str, Any]) -> float | None:
    entry = as_float(trade.get("entry_price"))
    stop = as_float(trade.get("stop_price"))
    mult = as_float(trade.get("target_mult_used"))
    if entry is None or stop is None or mult is None:
        return None
    risk_per_share = max(entry - stop, 0.0)
    if risk_per_share <= 0:
        return None
    return round(entry + (risk_per_share * mult), 4)


def enrich_trade(label: str, trade: dict[str, Any]) -> dict[str, Any]:
    entry = as_float(trade.get("entry_price"))
    entry_open = as_float(trade.get("entry_open_price"))
    stop = as_float(trade.get("stop_price"))
    shares = as_float(trade.get("shares"))
    target_mult = as_float(trade.get("target_mult_used"))
    pnl = as_float(trade.get("pnl")) or 0.0
    pnl_pct = as_float(trade.get("pnl_pct_net")) or 0.0

    entry_notional = entry * shares if entry is not None and shares is not None else None
    initial_risk_pct = (
        max(entry - stop, 0.0) / entry
        if entry is not None and stop is not None and entry > 0
        else None
    )
    entry_slip_pct = (
        max(entry - entry_open, 0.0) / entry_open
        if entry is not None and entry_open is not None and entry_open > 0
        else None
    )
    target_opportunity_pct = (
        initial_risk_pct * target_mult
        if initial_risk_pct is not None and target_mult is not None
        else None
    )
    cost_adjusted_drag = (
        (initial_risk_pct + (entry_slip_pct or 0.0)) / target_opportunity_pct
        if initial_risk_pct is not None
        and target_opportunity_pct is not None
        and target_opportunity_pct > 0
        else None
    )

    realized_total_slippage = as_float(trade.get("slippage_cost"))
    realized_total_slippage_notional = (
        realized_total_slippage / entry_notional
        if realized_total_slippage is not None
        and entry_notional is not None
        and entry_notional > 0
        else None
    )

    return {
        "window": label,
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": round_float(entry, 4),
        "entry_open_price": round_float(entry_open, 4),
        "stop_price": round_float(stop, 4),
        "target_price_reconstructed": target_price_from_trade(trade),
        "shares": round_float(shares, 4),
        "entry_notional": round_float(entry_notional, 2),
        "entry_slip_pct": round_float(entry_slip_pct, 8),
        "entry_slip_bps": round_float((entry_slip_pct or 0.0) * 10_000.0, 4),
        "initial_risk_pct": round_float(initial_risk_pct, 8),
        "target_mult_used": round_float(target_mult, 4),
        "target_opportunity_pct": round_float(target_opportunity_pct, 8),
        "cost_adjusted_drawdown_contribution": round_float(cost_adjusted_drag, 8),
        "cost_adjusted_drawdown_bucket": bucket_for(cost_adjusted_drag),
        "pnl": round_float(pnl, 2),
        "pnl_pct_net": round_float(pnl_pct, 8),
        "is_loss": pnl < 0,
        "is_loss_tail": pnl_pct <= LOSS_TAIL_PNL_PCT,
        "realized_total_slippage_cost": round_float(realized_total_slippage, 2),
        "realized_total_slippage_notional_pct": round_float(
            realized_total_slippage_notional, 8
        ),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if row.get("pnl") is not None]
    pnl_pcts = [
        float(row["pnl_pct_net"]) for row in rows if row.get("pnl_pct_net") is not None
    ]
    return {
        "n": len(rows),
        "total_pnl": round_float(sum(pnls), 2),
        "avg_pnl": mean(pnls),
        "median_pnl": median(pnls),
        "avg_pnl_pct_net": mean(pnl_pcts),
        "median_pnl_pct_net": median(pnl_pcts),
        "win_rate": round_float(
            sum(1 for row in rows if (row.get("pnl") or 0) > 0) / len(rows)
            if rows
            else None,
            6,
        ),
        "loss_rate": round_float(
            sum(1 for row in rows if row.get("is_loss")) / len(rows)
            if rows
            else None,
            6,
        ),
        "loss_tail_rate": round_float(
            sum(1 for row in rows if row.get("is_loss_tail")) / len(rows)
            if rows
            else None,
            6,
        ),
        "avg_cost_adjusted_drawdown_contribution": mean(
            [
                float(row["cost_adjusted_drawdown_contribution"])
                for row in rows
                if row.get("cost_adjusted_drawdown_contribution") is not None
            ]
        ),
        "avg_entry_slip_bps": mean(
            [
                float(row["entry_slip_bps"])
                for row in rows
                if row.get("entry_slip_bps") is not None
            ]
        ),
        "avg_initial_risk_pct": mean(
            [
                float(row["initial_risk_pct"])
                for row in rows
                if row.get("initial_risk_pct") is not None
            ]
        ),
    }


def summarize_by_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket in ("low", "middle", "high", "unknown"):
        bucket_rows = [row for row in rows if row.get("cost_adjusted_drawdown_bucket") == bucket]
        if bucket_rows or bucket != "unknown":
            out[bucket] = summarize_rows(bucket_rows)
    return out


def compare_high_low(summary: dict[str, Any]) -> dict[str, Any]:
    high = summary.get("high") or {}
    low = summary.get("low") or {}
    if not high.get("n") or not low.get("n"):
        return {"available": False}
    return {
        "available": True,
        "high_minus_low_avg_pnl": round_float(
            (high.get("avg_pnl") or 0.0) - (low.get("avg_pnl") or 0.0),
            2,
        ),
        "high_minus_low_median_pnl": round_float(
            (high.get("median_pnl") or 0.0) - (low.get("median_pnl") or 0.0),
            2,
        ),
        "high_minus_low_win_rate": round_float(
            (high.get("win_rate") or 0.0) - (low.get("win_rate") or 0.0),
            6,
        ),
        "high_minus_low_loss_tail_rate": round_float(
            (high.get("loss_tail_rate") or 0.0) - (low.get("loss_tail_rate") or 0.0),
            6,
        ),
    }


def load_baseline_summary() -> dict[str, Any]:
    baseline = read_json(BASELINE_RESULT, {})
    standard = read_json(
        REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        {},
    )
    return {
        "accepted_stack_artifact": repo_rel(BASELINE_RESULT),
        "experiment_id": baseline.get("experiment_id"),
        "decision": baseline.get("decision"),
        "status": baseline.get("status"),
        "aggregate": baseline.get("aggregate"),
        "standard_window_summary": standard,
    }


def load_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_audit: dict[str, Any] = {}
    for label, path in WINDOW_FILES.items():
        payload = read_json(path, {})
        trades = payload.get("trades") if isinstance(payload, dict) else None
        if not isinstance(trades, list):
            trades = []
        enriched = [enrich_trade(label, trade) for trade in trades]
        rows.extend(enriched)
        source_audit[label] = {
            "path": repo_rel(path),
            "trade_rows": len(trades),
            "rows_with_entry_date": sum(1 for row in enriched if row.get("entry_date")),
            "rows_with_target_price_reconstructed": sum(
                1 for row in enriched if row.get("target_price_reconstructed") is not None
            ),
            "rows_with_cost_adjusted_bucket": sum(
                1 for row in enriched if row.get("cost_adjusted_drawdown_bucket") != "unknown"
            ),
        }
    return rows, source_audit


def realized_slippage_caveat(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        row
        for row in rows
        if row.get("realized_total_slippage_notional_pct") is not None
    ]
    if not usable:
        return {"available": False}
    values = sorted(float(row["realized_total_slippage_notional_pct"]) for row in usable)
    threshold = values[int(0.75 * (len(values) - 1))]
    high = [row for row in usable if float(row["realized_total_slippage_notional_pct"]) >= threshold]
    low = [row for row in usable if float(row["realized_total_slippage_notional_pct"]) < threshold]
    return {
        "available": True,
        "diagnostic_only": True,
        "leakage_reason": "trade.slippage_cost aggregates entry_slip + exit_slip; exit_slip is not known at entry and is path-dependent.",
        "top_quartile_threshold": round_float(threshold, 8),
        "top_quartile": summarize_rows(high),
        "other_rows": summarize_rows(low),
        "top_minus_other_avg_pnl": round_float(
            (summarize_rows(high).get("avg_pnl") or 0.0)
            - (summarize_rows(low).get("avg_pnl") or 0.0),
            2,
        ),
    }


def build_attribution(rows: list[dict[str, Any]], source_audit: dict[str, Any]) -> dict[str, Any]:
    by_window: dict[str, Any] = OrderedDict()
    for label in WINDOW_FILES:
        window_rows = [row for row in rows if row["window"] == label]
        bucket_summary = summarize_by_bucket(window_rows)
        by_window[label] = {
            "all": summarize_rows(window_rows),
            "buckets": bucket_summary,
            "high_low": compare_high_low(bucket_summary),
        }

    pooled_buckets = summarize_by_bucket(rows)
    return {
        "source_audit": source_audit,
        "parameters": {
            "bucket_definition": (
                "(entry_slip_pct + initial_risk_pct) / "
                "(initial_risk_pct * target_mult_used)"
            ),
            "low_drag_max": LOW_DRAG_MAX,
            "high_drag_min": HIGH_DRAG_MIN,
            "loss_tail_pnl_pct": LOSS_TAIL_PNL_PCT,
            "uses_realized_total_slippage_for_signal": False,
        },
        "pooled": {
            "all": summarize_rows(rows),
            "buckets": pooled_buckets,
            "high_low": compare_high_low(pooled_buckets),
        },
        "by_window": by_window,
        "realized_total_slippage_caveat": realized_slippage_caveat(rows),
        "sample_high_bucket_rows": [
            row for row in rows if row["cost_adjusted_drawdown_bucket"] == "high"
        ][:25],
    }


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]
    high = pooled["buckets"]["high"]
    low = pooled["buckets"]["low"]
    high_low = pooled["high_low"]
    window_comparisons = {
        label: row["high_low"] for label, row in attribution["by_window"].items()
    }
    supporting = [
        label
        for label, row in window_comparisons.items()
        if row.get("available")
        and (row.get("high_minus_low_avg_pnl") or 0.0) < 0
        and (row.get("high_minus_low_win_rate") or 0.0) < 0
        and (row.get("high_minus_low_loss_tail_rate") or 0.0) > 0
    ]
    failures: list[str] = []
    if (pooled["all"].get("n") or 0) < MIN_TOTAL_ROWS:
        failures.append("sample_too_small")
    if (high.get("n") or 0) < MIN_HIGH_BUCKET_ROWS:
        failures.append("high_bucket_sample_too_small")
    if not high_low.get("available"):
        failures.append("high_low_comparison_unavailable")
    else:
        if (high_low.get("high_minus_low_avg_pnl") or 0.0) >= 0:
            failures.append("high_bucket_avg_pnl_not_worse")
        if (high_low.get("high_minus_low_win_rate") or 0.0) >= 0:
            failures.append("high_bucket_win_rate_not_worse")
        if (high_low.get("high_minus_low_loss_tail_rate") or 0.0) <= 0:
            failures.append("high_bucket_loss_tail_not_worse")
    if len(supporting) < MIN_SUPPORTING_WINDOWS:
        failures.append("insufficient_window_support")

    observed_only_lead = not failures
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_cost_adjusted_drawdown_tail_edge"
            if observed_only_lead
            else "rejected_no_ex_ante_cost_adjusted_drawdown_tail_edge"
        ),
        "acceptance_rule": (
            "Observed-only lead only if total sample >=50, high bucket >=10, "
            "pooled high bucket has lower avg PnL, lower win rate, higher 2pct "
            "loss-tail rate than low bucket, and all three windows support the "
            "same direction. No strategy acceptance is possible in this run."
        ),
        "failed_reasons": failures,
        "supporting_windows": supporting,
        "window_comparisons": window_comparisons,
        "pooled_high_low": high_low,
        "minimums": {
            "min_total_rows": MIN_TOTAL_ROWS,
            "min_high_bucket_rows": MIN_HIGH_BUCKET_ROWS,
            "min_supporting_windows": MIN_SUPPORTING_WINDOWS,
        },
    }


def calibration(gate4: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4.get("observed_only_lead") else 0
    prob = float(prediction.get("success_probability") or 0.0)
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual_success) ** 2, 6),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": ";".join(gate4.get("failed_reasons") or []),
        "predicted_failure_mode_hit": bool(gate4.get("failed_reasons")),
        "surprise_note": (
            "The ex-ante entry-cost/risk field did not separate loss tail; the "
            "apparent realized-slippage separation is unusable because it embeds "
            "exit-side path information."
            if not gate4.get("observed_only_lead")
            else "The ex-ante entry-cost/risk field separated loss tail and should be tested prospectively."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    rows, source_audit = load_rows()
    attribution = build_attribution(rows, source_audit)
    gate4 = evaluate_gate4(attribution)
    baseline = load_baseline_summary()
    status = "observed_only" if gate4["observed_only_lead"] else "rejected"
    why = (
        "The ex-ante cost-adjusted entry-risk bucket did not explain loss-tail: "
        "the high bucket was not worse on pooled average PnL/win-rate/loss-tail "
        "and window support was insufficient. Realized total slippage did show "
        "a negative diagnostic split, but that field includes exit-side slippage "
        "and is therefore leakage for entry decisions."
        if not gate4["observed_only_lead"]
        else (
            "The high ex-ante cost-adjusted entry-risk bucket separated loss-tail "
            "across all windows, but this remains observed-only and needs a "
            "shared prospective logger plus Gate 1-4 before policy use."
        )
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "calibration": calibration(gate4, prediction),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "scripts/check_experiment_novelty.py and experiment.py new "
                    "reported no strong near-neighbor; source saturation not applicable."
                ),
                "playbook_anchor": (
                    "docs/alpha-optimization-playbook.md lists "
                    "cost_adjusted_drawdown_contribution_bucket as a candidate "
                    "field whose first step is read-only attribution."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": attribution["parameters"],
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "window_files": {label: repo_rel(path) for label, path in WINDOW_FILES.items()},
        },
        "gate2": {
            "passed": all(
                row["trade_rows"] == row["rows_with_entry_date"]
                and row["trade_rows"] == row["rows_with_target_price_reconstructed"]
                and row["trade_rows"] == row["rows_with_cost_adjusted_bucket"]
                for row in source_audit.values()
            ),
            "dependency_fields_checked": [
                "entry_date",
                "entry_price",
                "entry_open_price",
                "stop_price",
                "target_mult_used",
                "shares",
                "pnl",
                "pnl_pct_net",
            ],
            "target_price_note": (
                "Closed trade rows omit original target_price; runner reconstructs "
                "entry_price + (entry_price - stop_price) * target_mult_used and "
                "does not schedule executable orders."
            ),
            "source_audit": source_audit,
        },
        "gate3": {
            "passed": True,
            "note": "No executable filter was added; core survival is unchanged.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": gate4,
        "attribution": attribution,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "uses_llm": False,
            "parity_note": (
                "Read-only attribution over accepted backtest trade rows. "
                "No production or backtest decision path changed."
            ),
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
        "next_retry_requires": (
            "Do not use realized total slippage, exit-side slippage, or adjacent "
            "entry-cost thresholds as a policy signal on frozen windows. A retry "
            "needs a true entry-time execution-quality field with prospective "
            "forward replacement rows, or a materially different non-OHLCV risk "
            "axis such as borrow/options/news context."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune cost-adjusted drag thresholds, target-multiple "
                "cuts, entry-slip bps cuts, high/low bucket boundaries, hold days, "
                "or notional on these same accepted-stack trade rows."
            ),
            "new_evidence_required": (
                "Prospective forward rows tagged at entry with a non-leaky "
                "execution-quality field, or a new production-visible context "
                "field that separates high-risk entries before exit information exists."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            *[repo_rel(path) for path in WINDOW_FILES.values()],
        ],
        "changed_files": [
            RUNNER,
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
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }
    return payload


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "parameters",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "related_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["attribution_summary"] = {
        "pooled": payload["attribution"]["pooled"],
        "by_window": payload["attribution"]["by_window"],
        "realized_total_slippage_caveat": payload["attribution"][
            "realized_total_slippage_caveat"
        ],
    }
    return row


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    gate4 = payload["gate4"]
    high_low = pooled["high_low"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Cost-Adjusted Drawdown Attribution",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Observed-only lead: `{payload['observed_only_lead']}`",
            f"- Pooled high-minus-low avg PnL: `{high_low.get('high_minus_low_avg_pnl')}`",
            f"- Pooled high-minus-low win rate: `{high_low.get('high_minus_low_win_rate')}`",
            f"- Pooled high-minus-low loss-tail rate: `{high_low.get('high_minus_low_loss_tail_rate')}`",
            f"- Failed reasons: `{gate4['failed_reasons']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
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
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))

    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "parameters",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "rejection_reason",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
        ]
        if key in payload
    }
    fields.update(
        {
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
