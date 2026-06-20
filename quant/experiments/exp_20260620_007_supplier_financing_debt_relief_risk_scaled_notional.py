"""exp-20260620-007: supplier financing/debt relief risk-scaled notional.

Replay-only alpha search. The single decision hypothesis is risk allocation,
not a new candidate source: keep the exp-20260620-005 raw SEC Companyfacts
supplier-financing plus debt-relief candidate source, scoring, top-1/day
selection, next-open entry, 10-trading-day exit, and cooldown fixed, then scale
paper notional down only when PIT same-ticker 20d volatility and 20d dollar
liquidity indicate the trade can dominate drawdown.

No production code, shared adapter, live/default orders, ranking, exits,
LLM/news path, or watchlist behavior is changed. A numeric pass is only a
default-off replay lead until a shared historical/daily helper reproduces the
same notional envelope. No JavaScript is used.
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

import exp_20260620_005_supplier_financing_debt_relief_intersection as prior  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260620-007"
STEM = "supplier_financing_debt_relief_risk_scaled_notional"
TRIAL_FAMILY = "supplier_financing_debt_relief_risk_allocation"
TRIAL_VARIANT_ID = "supplier_financing_debt_relief_vol_liquidity_risk_scaled_notional_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_007_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

# A one-way live-realistic paper risk envelope: never upsize, only downsize
# trades whose own PIT volatility/liquidity implies larger drawdown impact.
TARGET_REALIZED_VOL_20D = 0.0275
LIQUIDITY_FULL_SIZE_ADV20 = 1_000_000_000.0
MIN_VOL_SCALAR = 0.40
MIN_LIQUIDITY_SCALAR = 0.50
MIN_TOTAL_SCALAR = 0.35
MAX_TOTAL_SCALAR = 1.00

PREDICTION = {
    "success_probability": 0.32,
    "expected_ev_delta": 1.10,
    "expected_pnl_delta": 18_000.0,
    "main_failure_modes": [
        "EV edge diluted by downsizing",
        "old_thin still breaches drawdown",
        "accepted_distribution_comparator_not_beaten",
        "risk scalar is just late/mid winner preservation",
    ],
    "confidence_reason": (
        "The immediately prior fixed Companyfacts cross-statement source "
        "improved EV/PnL in all three canonical windows and beat accepted "
        "candidate-pool comparators, failing only drawdown drift. This test "
        "changes only paper notional using PIT volatility and liquidity fields "
        "already present on each selected trade."
    ),
    "recorded_at": "2026-06-20T07:08:03+00:00",
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
            "candidate_avg_dollar_volume_20d from the same PIT OHLCV snapshot "
            "used by exp-20260620-005"
        ),
        "volatility_source": (
            "candidate_realized_vol_20d from the same PIT OHLCV snapshot used "
            "by exp-20260620-005"
        ),
        "max_position_notional_usd": BASE_NOTIONAL_USD,
        "min_position_notional_usd": round(BASE_NOTIONAL_USD * MIN_TOTAL_SCALAR, 2),
    },
    "parity_note": (
        "This experiment changes no production code. A numeric pass is only a "
        "replay lead until one shared default-off helper computes the same PIT "
        "Companyfacts candidate source and the same PIT volatility/liquidity "
        "notional scalar in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "risk_allocation: the exp-20260620-005 supplier-financing plus "
        "debt-relief free-data candidate source contains real replacement "
        "value, but its old_thin drawdown comes from oversized volatile/"
        "less-liquid overlay legs. A one-way PIT volatility/liquidity notional "
        "cap may preserve the edge while making the execution envelope credible."
    ),
    "2_history_check": {
        "exp-20260620-005": (
            "Same candidate source improved all three canonical windows and "
            "beat accepted candidate-pool comparators, but was rejected only "
            "for drawdown drift +0.0156 versus the +0.005 guardrail."
        ),
        "exp-20260617-001": (
            "Standalone DPO extension was positive but drawdown-failed; this "
            "run does not change DPO thresholds or fields."
        ),
        "exp-20260616-029": (
            "Standalone debt-burden relief was positive in late/mid but "
            "unstable; this run keeps exp-005's intersection fixed."
        ),
        "novelty_gate": (
            "Novelty warned on Companyfacts neighbors. Override axis is the "
            "new risk-allocation envelope on a fixed high-positive/drawdown-"
            "failed source, not another Companyfacts field or threshold sweep."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two EV-"
        "improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and "
        "accepted compression/distribution candidate-pool comparators must be "
        "beaten. Positive replay is not promoted without shared daily/"
        "historical parity."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_007_supplier_financing_debt_relief_risk_scaled_notional.py"
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
            "vol_at_or_below_target" if realized_vol <= TARGET_REALIZED_VOL_20D
            else "vol_above_target"
        )

    if adv20 is None:
        liquidity_scalar = MIN_LIQUIDITY_SCALAR
        liquidity_reason = "missing_adv20"
    else:
        liquidity_scalar = min(1.0, math.sqrt(adv20 / LIQUIDITY_FULL_SIZE_ADV20))
        liquidity_scalar = max(MIN_LIQUIDITY_SCALAR, liquidity_scalar)
        liquidity_reason = (
            "adv_at_or_above_full_size" if adv20 >= LIQUIDITY_FULL_SIZE_ADV20
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
            "full_size" if scalar >= 0.999
            else "mild_downsize" if scalar >= 0.75
            else "moderate_downsize" if scalar >= 0.50
            else "floor_downsize"
        )

        row = deepcopy(trade)
        row["source"] = "SUPPLIER_FINANCING_DEBT_RELIEF_RISK_SCALED_PAPER"
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

    affected_count = sum(1 for row in adjusted if float(row["risk_notional_scalar"]) < 0.999)
    return adjusted, {
        "rule_version": RULE_VERSION,
        "source": "selected_exp_20260620_005_trades_with_pit_vol_liquidity_notional_scalar",
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
            key: round(float(value), 2) for key, value in sorted(original_pnl_by_bucket.items())
        },
        "adjusted_pnl_by_bucket": {
            key: round(float(value), 2) for key, value in sorted(adjusted_pnl_by_bucket.items())
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
        "positive_replay_lead_not_promoted_supplier_financing_debt_relief_risk_scaled_notional"
        if gate["passed"]
        else "rejected_supplier_financing_debt_relief_risk_scaled_notional"
    )
    return gate


def _configure_framework() -> None:
    prior._configure_framework()


def _build_payload() -> dict[str, Any]:
    _configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = prior.base.framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(prior.base.framework.get_universe())
    sector_entries_all = prior.base.framework._load_sector_entries()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    risk_scaling_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    quality_index_summary_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in prior.base.framework.WINDOWS.items():
        print(f"[{label}] core baseline and risk-scaled supplier-financing/debt-relief replay")
        before_result = prior.base.framework.shadow._run_baseline(universe, cfg)
        before = prior.base.framework.overlay_helper._metrics(before_result)
        snapshot = prior.base._load_window_snapshot(cfg=cfg, eligible_tickers=set(universe))
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        quality_index, quality_summary = prior._build_quality_index([])
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_ticker_count": len(sector_entries),
            "source": _repo_rel(prior.base.framework.WAREHOUSE),
        }
        quality_index_summary_by_window[label] = quality_summary
        candidates, context_scan = prior._candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
            quality_index=quality_index,
        )
        selected_trades, filtered_candidates = prior.base.framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        adjusted_trades, risk_scan = _apply_risk_scaled_notional(selected_trades)
        overlay = prior.base.framework.sleeve._overlay_from_paper_trades(
            before_result, adjusted_trades
        )
        after = prior.base.framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = prior.base.framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = adjusted_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_scan_by_window[label] = context_scan
        risk_scaling_scan_by_window[label] = risk_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(adjusted_trades),
            "raw_candidate_count": len(candidates),
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
    failed_reasons = gate4["failed_reasons"]
    if gate4["passed"]:
        interpretation = (
            "The fixed supplier-financing plus debt-relief source cleared the "
            "numeric three-window replay screen after PIT volatility/liquidity "
            "notional scaling, but remains only a default-off replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "Rejected. The PIT volatility/liquidity notional scalar did not "
            f"clear Gate 4 (failed: {', '.join(failed_reasons) or 'none'}). "
            "The prior economic edge did not survive a simple live-realistic "
            "risk envelope strongly enough for retention."
        )
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": failed_reasons,
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
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
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_companyfacts_risk_allocation",
        "new_evidence_type": "pit_volatility_liquidity_notional_envelope_on_fixed_companyfacts_source",
        "nearby_prior_experiments": [
            "exp-20260620-005",
            "exp-20260617-001",
            "exp-20260616-029",
        ],
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": "medium",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": prior.base.framework.WINDOWS,
            "baseline_result_file": (
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "baseline_metrics": before_metrics,
            "entry_semantics": "signal close known before next-session open paper entry",
            "exit_semantics": f"{HOLD_DAYS}-trading-day close exit",
            "costs": "same overlay cost model as accepted candidate-pool sleeves",
        },
        "parameters": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "fixed_prior_candidate_source": "exp-20260620-005",
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
                "raw SEC Companyfacts accounts-payable facts",
                "raw SEC Companyfacts quarterly COGS",
                "raw SEC Companyfacts gross debt instant facts",
                "raw SEC Companyfacts annual revenue facts",
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
                "source is fixed from exp-20260620-005; only paper notional is "
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
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "quality_index_summary_by_window": quality_index_summary_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "risk_scaling_scan_by_window": risk_scaling_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(failed_reasons),
        "next_evidence_needed": (
            "If numeric positive, build a shared default-off historical/daily "
            "helper before retention. If rejected, do not sweep the scalar "
            "levels on the frozen windows; seek supplier/payment-term "
            "provenance, covenant availability, or closed forward replacement "
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
                "Do not retry by sweeping DPO extension, debt/revenue relief, "
                "volatility targets, ADV targets, scalar floors, price guards, "
                "top-N, hold days, cooldown, or notional on these frozen windows."
            ),
            "new_evidence_required": (
                "Need supplier/payment-term provenance, covenant/refinancing "
                "context, or closed forward replacement-value rows before "
                "revisiting this Companyfacts cross-statement/risk family."
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
            f"# {EXPERIMENT_ID} Supplier Financing Debt Relief Risk-Scaled Notional",
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
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
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
