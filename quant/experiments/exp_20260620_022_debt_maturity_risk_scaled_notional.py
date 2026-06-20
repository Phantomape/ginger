"""exp-20260620-022: debt maturity relief risk-scaled notional.

Replay-only alpha search. The decision hypothesis is risk allocation, not a
new candidate source: keep the exp-20260619-005 debt-maturity-cliff relief
candidate ledger fixed, then scale paper notional down only when point-in-time
20d volatility or 20d dollar liquidity implies the leg can dominate drawdown.

No production code, shared adapter, live/default orders, ranking, exits,
LLM/news path, or watchlist behavior is changed. A numeric pass is only a
default-off replay lead until one shared historical/daily helper reproduces the
same candidate source and notional envelope. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260619_005_debt_maturity_cliff_relief as prior  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260620-022"
STEM = "debt_maturity_risk_scaled_notional"
TRIAL_FAMILY = "debt_maturity_cliff_relief_risk_allocation"
TRIAL_VARIANT_ID = "debt_maturity_cliff_relief_pit_vol_liquidity_cap_top1_next_open_10d_v1"
CHANGED_VARIABLE = "debt_maturity_cliff_relief_pit_vol_liquidity_notional_cap_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PRIOR_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260619-005"
    / "exp_20260619_005_debt_maturity_cliff_relief.json"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

# Same conservative one-way envelope shape as the successful supplier-financing
# risk scout, fixed before this run. It never upsizes a prior selected trade.
TARGET_REALIZED_VOL_20D = 0.0275
LIQUIDITY_FULL_SIZE_ADV20 = 1_000_000_000.0
MIN_VOL_SCALAR = 0.40
MIN_LIQUIDITY_SCALAR = 0.50
MIN_TOTAL_SCALAR = 0.35
MAX_TOTAL_SCALAR = 1.00

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "notional_cap_reduces_winners",
        "accepted_distribution_not_beaten",
        "old_thin_still_regresses",
        "source_edge_too_weak",
        "concentration_failed",
    ],
    "confidence_reason": (
        "The fixed debt maturity source already produced positive late/mid "
        "evidence but failed old_thin and concentration. Supplier-financing "
        "improved materially under this PIT volatility/liquidity envelope, so "
        "this is a targeted risk-allocation test rather than a source-threshold "
        "sweep."
    ),
    "recorded_at": "2026-06-20T17:14:56+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "paper_notional_changed": True,
    "uses_llm": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        **prior.PRODUCTION_IMPACT["execution_envelope"],
        "target_notional_per_paper_trade": (
            "$4,000 base notional scaled one-way to 0.35x-1.00x using PIT "
            "20d realized volatility and PIT ADV20; never upsizes"
        ),
        "liquidity_source": (
            "candidate_avg_dollar_volume_20d from the exp-20260619-005 PIT "
            "OHLCV candidate ledger"
        ),
        "volatility_source": (
            "candidate_realized_vol_20d from the exp-20260619-005 PIT OHLCV "
            "candidate ledger"
        ),
        "max_position_notional_usd": BASE_NOTIONAL_USD,
        "min_position_notional_usd": round(BASE_NOTIONAL_USD * MIN_TOTAL_SCALAR, 2),
    },
    "parity_note": (
        "This experiment changes no production code. A numeric pass is only a "
        "replay lead until one shared default-off helper computes the same debt "
        "maturity candidate source and PIT volatility/liquidity notional scalar "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "risk_allocation: the fixed debt-maturity-cliff relief candidate source "
        "from exp-20260619-005 may contain usable financing-risk relief value, "
        "but its old_thin regression and concentration failure come from "
        "uniform $4,000 notional on lower-liquidity or higher-volatility paper "
        "legs. A one-way PIT ADV/realized-volatility notional cap can preserve "
        "the source while making the execution envelope more realistic."
    ),
    "2_history_check": {
        "exp-20260619-005": (
            "Same candidate source had 62 trades, positive aggregate EV/PnL, "
            "but failed old_thin, concentration, and accepted distribution "
            "comparators under uniform notional."
        ),
        "exp-20260620-007": (
            "Supplier-financing debt-relief improved under the same risk-envelope "
            "shape. This run applies the envelope to a different fixed financing "
            "source and locks candidate selection."
        ),
        "novelty_gate": (
            "Override recorded: same PIT ADV20/realized-volatility envelope "
            "shape, but a different fixed debt-maturity source; not a sweep of "
            "maturity tags, thresholds, price gates, hold, cooldown, or top-N."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no unacceptable window EV/PnL regression, survival >=5%, "
        "at least 20 paper trades, drawdown drift <=0.5pp, concentration pass, "
        "and accepted compression/distribution comparators beaten. Positive "
        "replay is not retained without shared daily/historical parity."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_022_debt_maturity_risk_scaled_notional.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _positive_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


def _standard_metrics() -> dict[str, dict[str, Any]]:
    payload = json.loads(BASELINE_RESULT_JSON.read_text(encoding="utf-8"))
    return {str(row["label"]): dict(row) for row in payload["windows"]}


def _metric_digits(key: str) -> int:
    if key == "total_pnl":
        return 2
    if key in {"expected_value_score", "max_drawdown_pct", "strategy_total_return_pct"}:
        return 4
    if key in {"sharpe_daily", "win_rate", "survival_rate"}:
        return 4
    return 6


def _normalize_window_metrics(
    *,
    label: str,
    standard: dict[str, dict[str, Any]],
    dynamic_before: dict[str, Any],
    dynamic_after: dict[str, Any],
    dynamic_delta: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    before = dict(dynamic_before)
    after = dict(dynamic_after)
    baseline = standard[label]
    metric_keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "strategy_total_return_pct",
    )
    for key in metric_keys:
        if key not in baseline:
            continue
        before[key] = baseline[key]
        change = dynamic_delta.get(key, 0.0)
        if isinstance(baseline[key], (int, float)) and isinstance(change, (int, float)):
            after[key] = round(float(baseline[key]) + float(change), _metric_digits(key))
    delta = prior.base.framework.overlay_helper._delta(after, before)
    before["baseline_metric_source"] = _repo_rel(BASELINE_RESULT_JSON)
    after["baseline_metric_source"] = _repo_rel(BASELINE_RESULT_JSON)
    return before, after, delta


def _notional_scalar_payload(trade: dict[str, Any]) -> dict[str, Any]:
    realized_vol = _positive_float(trade.get("candidate_realized_vol_20d"))
    adv20 = _positive_float(trade.get("candidate_avg_dollar_volume_20d"))

    if realized_vol is None:
        vol_scalar = MIN_VOL_SCALAR
        vol_reason = "missing_realized_vol"
    else:
        vol_scalar = min(1.0, TARGET_REALIZED_VOL_20D / realized_vol)
        vol_scalar = max(MIN_VOL_SCALAR, vol_scalar)
        vol_reason = (
            "vol_at_or_below_target"
            if realized_vol <= TARGET_REALIZED_VOL_20D
            else "vol_above_target"
        )

    if adv20 is None:
        liquidity_scalar = MIN_LIQUIDITY_SCALAR
        liquidity_reason = "missing_adv20"
    else:
        liquidity_scalar = min(1.0, math.sqrt(adv20 / LIQUIDITY_FULL_SIZE_ADV20))
        liquidity_scalar = max(MIN_LIQUIDITY_SCALAR, liquidity_scalar)
        liquidity_reason = (
            "adv_at_or_above_full_size"
            if adv20 >= LIQUIDITY_FULL_SIZE_ADV20
            else "adv_below_full_size"
        )

    total_scalar = max(
        MIN_TOTAL_SCALAR,
        min(MAX_TOTAL_SCALAR, vol_scalar * liquidity_scalar),
    )
    return {
        "risk_notional_scalar": _round(total_scalar, 6),
        "risk_volatility_scalar": _round(vol_scalar, 6),
        "risk_liquidity_scalar": _round(liquidity_scalar, 6),
        "risk_realized_vol_20d": _round(realized_vol, 6),
        "risk_avg_dollar_volume_20d": _round(adv20, 2),
        "risk_volatility_reason": vol_reason,
        "risk_liquidity_reason": liquidity_reason,
        "risk_rule_version": RULE_VERSION,
    }


def _apply_risk_scaled_notional(
    trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    scalar_distribution: Counter[str] = Counter()
    original_pnl_by_bucket: Counter[str] = Counter()
    adjusted_pnl_by_bucket: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for trade in trades:
        payload = _notional_scalar_payload(trade)
        scalar = float(payload["risk_notional_scalar"] or 1.0)
        original_pnl = float(trade.get("pnl") or 0.0)
        original_notional = float(
            trade.get("paper_notional_usd")
            or trade.get("notional_usd")
            or BASE_NOTIONAL_USD
        )
        adjusted_pnl = round(original_pnl * scalar, 2)
        adjusted_notional = round(original_notional * scalar, 2)
        bucket = (
            "full_size"
            if scalar >= 0.999
            else "mild_downsize"
            if scalar >= 0.75
            else "moderate_downsize"
            if scalar >= 0.50
            else "floor_downsize"
        )

        row = deepcopy(trade)
        row["source"] = "DEBT_MATURITY_CLIFF_RELIEF_RISK_SCALED_PAPER"
        row["target_price"] = row.get("target_price", row.get("exit_price"))
        row["original_pnl_before_risk_scaling"] = round(original_pnl, 2)
        row["original_paper_notional_before_risk_scaling"] = round(
            original_notional, 2
        )
        row["pnl"] = adjusted_pnl
        row["paper_notional_usd"] = adjusted_notional
        row["notional_usd"] = adjusted_notional
        row["risk_notional_bucket"] = bucket
        row.update(payload)
        adjusted.append(row)

        scalar_distribution[bucket] += 1
        original_pnl_by_bucket[bucket] += original_pnl
        adjusted_pnl_by_bucket[bucket] += adjusted_pnl
        if scalar < 0.999 and len(examples) < 20:
            examples.append(
                {
                    "signal_date": row.get("signal_date") or row.get("date"),
                    "ticker": row.get("ticker"),
                    "bucket": bucket,
                    "scalar": _round(scalar, 6),
                    "original_notional": round(original_notional, 2),
                    "adjusted_notional": adjusted_notional,
                    "original_pnl": round(original_pnl, 2),
                    "adjusted_pnl": adjusted_pnl,
                    "realized_vol_20d": payload["risk_realized_vol_20d"],
                    "avg_dollar_volume_20d": payload["risk_avg_dollar_volume_20d"],
                }
            )

    affected_count = sum(
        1 for row in adjusted if float(row["risk_notional_scalar"]) < 0.999
    )
    return adjusted, {
        "rule_version": RULE_VERSION,
        "source": "selected_exp_20260619_005_trades_with_pit_vol_liquidity_scalar",
        "trade_count": len(trades),
        "risk_scaled_trade_count": affected_count,
        "risk_scaled_trade_share": _round(affected_count / max(len(trades), 1), 6),
        "base_notional_usd": BASE_NOTIONAL_USD,
        "target_realized_vol_20d": TARGET_REALIZED_VOL_20D,
        "liquidity_full_size_adv20": LIQUIDITY_FULL_SIZE_ADV20,
        "min_total_scalar": MIN_TOTAL_SCALAR,
        "max_total_scalar": MAX_TOTAL_SCALAR,
        "scalar_distribution": dict(sorted(scalar_distribution.items())),
        "original_pnl_by_bucket": {
            key: round(float(value), 2)
            for key, value in sorted(original_pnl_by_bucket.items())
        },
        "adjusted_pnl_by_bucket": {
            key: round(float(value), 2)
            for key, value in sorted(adjusted_pnl_by_bucket.items())
        },
        "affected_examples": examples,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_debt_maturity_risk_scaled_notional"
        if gate["passed"]
        else "rejected_debt_maturity_risk_scaled_notional"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    gate2_open_positions = prior.base.framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    prior_payload = json.loads(PRIOR_ARTIFACT.read_text(encoding="utf-8"))
    universe = sorted(prior.base.framework.get_universe())
    standard = _standard_metrics()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    risk_scaling_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in prior.base.framework.WINDOWS.items():
        print(f"[{label}] core baseline and risk-scaled debt-maturity replay")
        before_result = prior.base.framework.shadow._run_baseline(universe, cfg)
        dynamic_before = prior.base.framework.overlay_helper._metrics(before_result)
        selected_trades = list(prior_payload["target_trades_by_window"].get(label) or [])
        adjusted_trades, risk_scan = _apply_risk_scaled_notional(selected_trades)
        overlay = prior.base.framework.sleeve._overlay_from_paper_trades(
            before_result,
            adjusted_trades,
        )
        dynamic_after = prior.base.framework.overlay_helper._metrics_with_overlay(
            before_result,
            overlay,
        )
        dynamic_delta = prior.base.framework.overlay_helper._delta(
            dynamic_after,
            dynamic_before,
        )
        before, after, delta = _normalize_window_metrics(
            label=label,
            standard=standard,
            dynamic_before=dynamic_before,
            dynamic_after=dynamic_after,
            dynamic_delta=dynamic_delta,
        )

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = adjusted_trades
        risk_scaling_scan_by_window[label] = risk_scan
        raw_candidate_counts[label] = int(
            prior_payload.get("raw_candidate_counts", {}).get(label, len(selected_trades))
            or 0
        )
        context_scan_by_window[label] = dict(
            prior_payload.get("context_scan_by_window", {}).get(label, {})
        )
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(adjusted_trades),
            "raw_candidate_count": raw_candidate_counts[label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = prior.base.framework._aggregate_window_rows(window_rows)
    target_summary = prior.base.framework.sleeve._target_trade_summary(
        target_trades_by_window
    )
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    failed = gate4["failed_reasons"]
    if gate4["passed"]:
        interpretation = (
            "The fixed debt-maturity-cliff relief source cleared Gate 4 after "
            "PIT volatility/liquidity notional scaling, but remains only a "
            "replay lead because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "Rejected. The PIT volatility/liquidity notional scalar did not "
            f"clear Gate 4 (failed: {', '.join(failed) or 'none'}). The source "
            "edge was not strong enough after a live-realistic risk envelope."
        )

    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": failed,
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": gate4["passed"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_risk_allocation_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_companyfacts_debt_maturity_risk_allocation",
        "new_evidence_type": "pit_execution_envelope_risk_scaling_on_fixed_debt_maturity_source",
        "nearby_prior_experiments": ["exp-20260619-005", "exp-20260620-007"],
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "fixed exp-20260619-005 selected paper ledger with risk-scaled "
                "notional overlay"
            ),
            "windows": prior.base.framework.WINDOWS,
            "baseline_result_file": _repo_rel(BASELINE_RESULT_JSON),
            "prior_source_artifact": _repo_rel(PRIOR_ARTIFACT),
            "entry_semantics": "signal close known before next-session open paper entry",
            "exit_semantics": f"{HOLD_DAYS}-trading-day close exit",
            "costs": "same overlay cost model as accepted candidate-pool sleeves",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "fixed_prior_candidate_source": "exp-20260619-005",
            "target_realized_vol_20d": TARGET_REALIZED_VOL_20D,
            "liquidity_full_size_adv20": LIQUIDITY_FULL_SIZE_ADV20,
            "min_vol_scalar": MIN_VOL_SCALAR,
            "min_liquidity_scalar": MIN_LIQUIDITY_SCALAR,
            "min_total_scalar": MIN_TOTAL_SCALAR,
            "max_total_scalar": MAX_TOTAL_SCALAR,
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md canonical three-window baseline",
            "baseline_metrics": before_metrics,
            "passed": True,
        },
        "gate2": {
            "open_positions_field_audit": gate2_open_positions,
            "runtime_candidate_fields_checked": [
                "entry_date",
                "target_price",
                "candidate_realized_vol_20d",
                "candidate_avg_dollar_volume_20d",
                "paper_notional_usd",
                "raw SEC Companyfacts debt maturity ladder fields",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate "
                "source is fixed from exp-20260619-005; only paper notional is "
                "scaled after selection."
            ),
        },
        "gate4": gate4,
        "accepted_compression_comparator": prior.base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": prior.base.DISTRIBUTION_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "risk_scaling_scan_by_window": risk_scaling_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(failed),
        "next_evidence_needed": (
            "If numeric positive, build a shared default-off historical/daily "
            "helper before retention. If rejected, do not sweep the scalar "
            "levels on the frozen windows; seek parsed refinancing terms, "
            "covenant headroom, credit-rating changes, or forward replacement "
            "rows."
        ),
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown drift {:+.4f}; {} paper trades.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    target_summary["total_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping debt maturity tags, wall-relief "
                "thresholds, volatility targets, ADV targets, scalar floors, "
                "price guards, top-N, hold days, cooldown, or notional on these "
                "frozen windows."
            ),
            "new_evidence_required": (
                "Need parsed refinancing transaction terms, covenant headroom, "
                "credit-rating changes, borrow-cost/availability, or closed "
                "forward replacement-value rows before revisiting this debt "
                "maturity risk family."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Risk-scaled | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        risk = payload["risk_scaling_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {scaled} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                scaled=risk.get("risk_scaled_trade_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Debt Maturity Risk-Scaled Notional",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Max drawdown drift: `{:+.4f}`".format(
                aggregate["max_drawdown_delta_max"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                prior.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                prior.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                prior.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                prior.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, or exit behavior changed. A positive "
                "numeric result is not production-retained without shared "
                "historical/daily parity."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(BASELINE_RESULT_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": prior.base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": prior.base.DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "risk_scaled_trade_count": payload["risk_scaling_scan_by_window"][label][
                    "risk_scaled_trade_count"
                ],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in prior.base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): prior.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): prior.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prior.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prior.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prior.base.framework._sha256(CARD_MD),
        },
    }
    prior.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    prior.base.framework._write_json(OUT_JSON, payload)
    prior.base.framework._write_json(LOG_JSON, payload)
    prior.base.framework._write_text(CARD_MD, _build_card(payload))
    prior.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
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
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            prior.base.framework._safe(_build_log_record(payload)),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
