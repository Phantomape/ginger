"""exp-20260526-019: VBB same-day core-activity confirmation scout.

This alpha search tests one production-visible confirmation field on top of the
accepted default-off volume-breadth breakout paper adapter from exp-20260526-014:
selected VBB paper trades receive a fixed 1.10x paper-notional support only
when the canonical core engine also entered at least one trade on the same
signal date.

The experiment is replay-only/default-off unless it passes Gate 4 and is later
promoted through the shared VBB adapter. It does not change core signals,
ranking, sizing, exits, LLM/news, watchlists, or orders. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260526_014_volume_breadth_shared_adapter as exp014  # noqa: E402


EXPERIMENT_ID = "exp-20260526-019"
STEM = "vbb_core_activity_confirmation"
TRIAL_FAMILY = "volume_breadth_breakout_core_activity_confirmation"
CHANGED_VARIABLE = "vbb_selected_trade_same_day_core_activity_notional_support"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

NOTIONAL_SUPPORT_SCALAR = 1.10
MIN_ADJUSTED_TRADES = 10
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


def _configure() -> tuple[Any, Any]:
    exp014._configure_prior_module()
    return exp014.prior.base, exp014.prior.ohlcv_helper


def _scale_trade(trade: dict[str, Any], scalar: float) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    notional = float(trade.get("paper_notional_usd") or 10_000.0)
    pnl = float(trade.get("pnl") or 0.0)
    return {
        **trade,
        "paper_notional_usd": base._round(notional * scalar, 2),
        "pnl": base._round(pnl * scalar, 2),
        "core_activity_support_scalar": scalar,
        "core_activity_support_rule_version": "vbb_same_day_core_activity_support_v1",
    }


def _incremental_trade(trade: dict[str, Any], scalar: float) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    increment = scalar - 1.0
    notional = float(trade.get("paper_notional_usd") or 10_000.0)
    pnl = float(trade.get("pnl") or 0.0)
    return {
        **trade,
        "paper_notional_usd": base._round(notional * increment, 2),
        "pnl": base._round(pnl * increment, 2),
        "core_activity_support_increment": base._round(increment, 4),
        "core_activity_support_rule_version": "vbb_same_day_core_activity_support_v1",
    }


def _apply_support(
    selected_trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    after_trades: list[dict[str, Any]] = []
    adjusted_increments: list[dict[str, Any]] = []
    unadjusted: list[dict[str, Any]] = []
    for trade in selected_trades:
        if bool(trade.get("same_day_ab_overlap")):
            after_trades.append(_scale_trade(trade, NOTIONAL_SUPPORT_SCALAR))
            adjusted_increments.append(_incremental_trade(trade, NOTIONAL_SUPPORT_SCALAR))
        else:
            after_trades.append(trade)
            unadjusted.append(trade)
    return after_trades, adjusted_increments, unadjusted


def _build_payload() -> dict[str, Any]:
    base, shadow = _BASE_SHADOW
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    universe = sorted(base.get_universe())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_vbb_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    adjusted_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    unadjusted_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    core_activity_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] exp014 VBB baseline and same-day core activity support")
        before_result = shadow._run_baseline(universe, cfg)
        core_metrics[label] = base.overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        candidates = exp014._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        before_trades, filtered_candidates = base._select_paper_trades(snapshot, candidates)
        after_trades, adjusted_increments, unadjusted = _apply_support(before_trades)

        before_overlay = base._overlay_from_paper_trades(before_result, before_trades)
        after_overlay = base._overlay_from_paper_trades(before_result, after_trades)
        before = base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        after = base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        before_vbb_trades_by_window[label] = before_trades
        adjusted_trades_by_window[label] = adjusted_increments
        unadjusted_trades_by_window[label] = unadjusted
        core_activity_audit[label] = {
            "before_vbb_trade_count": len(before_trades),
            "adjusted_trade_count": len(adjusted_increments),
            "unadjusted_trade_count": len(unadjusted),
            "adjusted_source_pnl": base._round(
                sum(float(row.get("pnl") or 0.0) / (NOTIONAL_SUPPORT_SCALAR - 1.0) for row in adjusted_increments),
                2,
            ),
            "incremental_pnl": base._round(
                sum(float(row.get("pnl") or 0.0) for row in adjusted_increments),
                2,
            ),
            "adjusted_dates": [row.get("signal_date") for row in adjusted_increments],
            "adjusted_tickers": sorted({str(row.get("ticker") or "") for row in adjusted_increments}),
            "raw_candidate_count": len(candidates),
            "filtered_candidate_sample_count": len(filtered_candidates[:200]),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(adjusted_increments),
            "raw_candidate_count": len(candidates),
            "raw_candidate_days": len({row["date"] for row in candidates}),
            "overlay_total_pnl": after_overlay["overlay_total_pnl"],
            "overlay_day_count": after_overlay["overlay_day_count"],
        }

    aggregate = base._aggregate(window_rows)
    target_summary = base._target_trade_summary(adjusted_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive_vs_exp014")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive_vs_exp014")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_exp014")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_exp014")
    if target_summary["total_trade_count"] < MIN_ADJUSTED_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "accepted_vbb_same_day_core_activity_support"
        if gate4_passed
        else "rejected_vbb_same_day_core_activity_support"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted VOLUME_BREADTH_BREAKOUT_PAPER source may have better "
            "replacement value when the canonical core strategy is also active "
            "on the same signal date; same-day core activity is a production-visible "
            "confirmation field, not a new OHLCV threshold."
        ),
        "change_type": "paper_notional_support_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "same_day_core_activity_110_notional_support_v1",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260526-013",
            "exp-20260526-014",
            "exp-20260526-017",
            "exp-20260526-010",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_core_activity_replacement_value_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "before_reference": "accepted exp-20260526-014 shared VBB paper adapter",
            "execution_model": (
                "Before uses the accepted exp014 VBB paper overlay. After uses the "
                "same selected VBB paper trades, but applies a fixed 1.10x paper "
                "notional only to selected VBB rows whose signal date also has a "
                "canonical core entry. Entry remains next open and exit remains "
                "10 trading days later."
            ),
        },
        "parameters": {
            "before_adapter": "exp-20260526-014 VOLUME_BREADTH_BREAKOUT_PAPER",
            "notional_support_scalar": NOTIONAL_SUPPORT_SCALAR,
            "support_condition": "same_day_ab_overlap == true",
            "paper_notional_usd": 10_000.0,
            "hold_days": 10,
            "locked_variables": [
                "VBB candidate definition",
                "VBB top-1 selection",
                "VBB breadth thresholds",
                "VBB breakout thresholds",
                "next-open entry",
                "10-trading-day close exit",
                "core universe",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation / candidate_pool: VBB paper entries may deserve "
                "more notional when the core engine is also finding same-day alpha, "
                "which would make activation more replacement-value aware."
            ),
            "2_history_check": {
                "accepted_vbb": (
                    "exp-20260526-014 accepted the shared default-off VBB paper "
                    "adapter: EV +0.7124 and PnL +$13,225.50 vs core, 3/3 windows."
                ),
                "recent_nearby": (
                    "exp-20260526-017 rejected IWM>SPY confirmation versus exp014. "
                    "exp-20260526-010 rejected same-date core activity confirmation "
                    "for sector-leadership paper, but not for the accepted VBB source."
                ),
                "data_edge_note": (
                    "A low-extension VBB support idea was checked first but matched "
                    "only one VBB trade across all windows, so it was abandoned as "
                    "sample-blocked before strategy logic changes."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows, before=exp014 VBB adapter, "
                "after=1.10x same-day-core-activity VBB paper support; require "
                "positive aggregate EV/PnL, no EV/PnL-regressed window, >=10 "
                "adjusted trades across all windows, drawdown drift <=0.5pp, "
                "survival >=5%, and concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260526_019_vbb_core_activity_confirmation.py"
            ),
        },
        "gate1": {
            "baseline_artifact": "data/experiments/exp-20260526-014/volume_breadth_shared_adapter.json",
            "before_metrics_are_exp014_vbb_adapter": True,
            "core_metrics": core_metrics,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "selected exp014 VBB paper trade signal_date",
                "selected exp014 VBB paper trade same_day_ab_overlap",
                "canonical baseline entries by signal_date",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "core_survival_min": base._round(min_survival, 6),
            "core_survival_unchanged": True,
            "candidate_filter_added_to_live_core": False,
            "note": "Default-off paper notional support only; no core filter was added.",
        },
        "gate4": {
            "passed": gate4_passed,
            "failed_reasons": failed,
            "aggregate": aggregate,
            "target_trade_summary": target_summary,
            "concentration_passed": concentration_passed,
            "drawdown_guard": {
                "max_allowed_worse": MAX_DRAWDOWN_WORSE,
                "observed_max_delta": aggregate["max_drawdown_delta_max"],
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "aggregate": aggregate,
            "by_window": OrderedDict(
                (label, window_rows[label]["delta"]) for label in base.WINDOWS
            ),
        },
        "before_vbb_trades_by_window": before_vbb_trades_by_window,
        "target_trades_by_window": adjusted_trades_by_window,
        "unadjusted_trades_by_window": unadjusted_trades_by_window,
        "core_activity_audit": core_activity_audit,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": None if gate4_passed else "; ".join(failed),
        "interpretation": (
            "Accepted: same-day core activity improves the accepted VBB adapter."
            if gate4_passed
            else (
                "Rejected: same-day core activity did not improve the accepted "
                "VBB adapter robustly; mid_weak and old_thin regressed, so this "
                "field should not become a VBB notional support rule on the frozen "
                "sample."
            )
        ),
        "next_retry_requires": [
            "new_forward_vbb_closed_outcomes",
            "materially_different_replacement_value_field",
            "not_a_nearby_core_activity_scalar_retry",
        ],
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    base, _shadow = _BASE_SHADOW
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["core_activity_audit"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{adjusted}/{before_count} | ${incremental:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                adjusted=audit["adjusted_trade_count"],
                before_count=audit["before_vbb_trade_count"],
                incremental=audit["incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VBB Same-Day Core-Activity Confirmation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: on top of the accepted exp-20260526-014 VBB "
                "paper adapter, selected VBB paper trades get 1.10x paper-notional "
                "support only when the canonical core engine also entered at least "
                "one trade on the same signal date."
            ),
            "",
            "## Three-Window Result Versus Exp014",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs exp014: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs exp014: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- adjusted trades: `{payload['gate4']['target_trade_summary']['total_trade_count']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Core Activity Audit",
            "",
            "```json",
            json.dumps(payload["core_activity_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only/default-off paper scout. No shared policy, production "
                "adapter, run adapter, backtester adapter, watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base, _shadow = _BASE_SHADOW
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "VBB same-day core activity confirmation",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
            "owner": "alpha-search",
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    base, _shadow = _BASE_SHADOW
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "core_activity_audit": payload["core_activity_audit"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


_BASE_SHADOW = _configure()

if __name__ == "__main__":
    raise SystemExit(main())
