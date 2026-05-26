"""exp-20260526-017: VBB IWM market-participation confirmation scout.

This alpha search tests one orthogonal free-OHLCV field on top of the accepted
default-off volume-breadth breakout paper adapter from exp-20260526-014:
selected VBB paper trades keep notional only when IWM 20-day close-to-close
return is greater than SPY's 20-day return on the signal date.

The experiment is replay-only/default-off. It does not change the shared VBB
adapter, core signals, ranking, sizing, exits, LLM/news, watchlists, or orders.
No JavaScript is used.
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


EXPERIMENT_ID = "exp-20260526-017"
STEM = "vbb_iwm_market_confirmation"
TRIAL_FAMILY = "volume_breadth_breakout_market_participation_confirmation"
CHANGED_VARIABLE = "vbb_selected_trade_iwm20_gt_spy20_notional_gate"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOOKBACK_DAYS = 20
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


def _configure() -> tuple[Any, Any]:
    exp014._configure_prior_module()
    return exp014.prior.base, exp014.prior.ohlcv_helper


def _close_return(
    rows: list[dict[str, Any]],
    idx: int | None,
    days: int = LOOKBACK_DAYS,
) -> float | None:
    if idx is None or idx < days:
        return None
    base, shadow = _BASE_SHADOW
    start = shadow._value(rows[idx - days], "Close")
    end = shadow._value(rows[idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _market_context(
    snapshot: dict[str, list[dict[str, Any]]],
    signal_date: str,
) -> dict[str, Any]:
    base, shadow = _BASE_SHADOW
    spy_rows = shadow._series(snapshot, "SPY")
    iwm_rows = shadow._series(snapshot, "IWM")
    spy_idx = shadow._row_index(spy_rows).get(signal_date)
    iwm_idx = shadow._row_index(iwm_rows).get(signal_date)
    spy_ret20 = _close_return(spy_rows, spy_idx)
    iwm_ret20 = _close_return(iwm_rows, iwm_idx)
    passed = spy_ret20 is not None and iwm_ret20 is not None and iwm_ret20 > spy_ret20
    return {
        "rule_version": "vbb_iwm20_gt_spy20_market_participation_v1",
        "lookback_trading_days": LOOKBACK_DAYS,
        "signal_date": signal_date,
        "spy_ret20": base._round(spy_ret20, 6),
        "iwm_ret20": base._round(iwm_ret20, 6),
        "iwm_minus_spy_ret20": base._round(
            None if spy_ret20 is None or iwm_ret20 is None else iwm_ret20 - spy_ret20,
            6,
        ),
        "passed": passed,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _split_confirmed_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    selected_trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    confirmed: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for trade in selected_trades:
        signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
        context = _market_context(snapshot, signal_date)
        row = {**trade, "iwm_market_participation_context": context}
        if context["passed"]:
            confirmed.append(row)
        else:
            removed.append({**row, "notional_gate_action": "paper_notional_zero"})
    return confirmed, removed


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
    before_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    removed_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    market_context_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] exp014 VBB baseline and IWM confirmation replay")
        before_result = shadow._run_baseline(universe, cfg)
        core_metrics[label] = base.overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        candidates = exp014._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        before_trades, filtered_candidates = base._select_paper_trades(snapshot, candidates)
        confirmed_trades, removed_trades = _split_confirmed_trades(snapshot, before_trades)

        before_overlay = base._overlay_from_paper_trades(before_result, before_trades)
        after_overlay = base._overlay_from_paper_trades(before_result, confirmed_trades)
        before = base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        after = base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        before_trades_by_window[label] = before_trades
        target_trades_by_window[label] = confirmed_trades
        removed_trades_by_window[label] = removed_trades
        market_context_audit[label] = {
            "before_vbb_trade_count": len(before_trades),
            "confirmed_trade_count": len(confirmed_trades),
            "removed_trade_count": len(removed_trades),
            "confirmed_pnl": base._round(sum(float(row.get("pnl") or 0.0) for row in confirmed_trades), 2),
            "removed_pnl": base._round(sum(float(row.get("pnl") or 0.0) for row in removed_trades), 2),
            "confirmed_dates": [row.get("signal_date") for row in confirmed_trades],
            "removed_dates": [row.get("signal_date") for row in removed_trades],
            "raw_candidate_count": len(candidates),
            "filtered_candidate_sample_count": len(filtered_candidates[:200]),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(confirmed_trades),
            "raw_candidate_count": len(candidates),
            "raw_candidate_days": len({row["date"] for row in candidates}),
            "overlay_total_pnl": after_overlay["overlay_total_pnl"],
            "overlay_day_count": after_overlay["overlay_day_count"],
        }

    aggregate = base._aggregate(window_rows)
    target_summary = base._target_trade_summary(target_trades_by_window)
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
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
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
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "accepted_vbb_iwm_market_participation_confirmation"
        if gate4_passed
        else "rejected_vbb_iwm_market_participation_confirmation"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted VOLUME_BREADTH_BREAKOUT_PAPER source may have better "
            "risk-adjusted replacement value when same-date small-cap participation "
            "is confirmed by IWM 20-day momentum exceeding SPY 20-day momentum."
        ),
        "change_type": "market_participation_confirmation_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "iwm20_gt_spy20_selected_vbb_notional_gate_v1",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260526-013",
            "exp-20260526-014",
            "exp-20260526-015",
            "exp-20260526-016",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "orthogonal_free_ohlcv_market_participation_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "before_reference": "accepted exp-20260526-014 shared VBB paper adapter",
            "execution_model": (
                "Before uses the accepted exp014 VBB paper overlay. After uses the "
                "same selected VBB paper trades, but sets paper notional to zero "
                "when IWM 20d return is not greater than SPY 20d return on the "
                "signal date. Entry remains next open and exit remains 10 trading "
                "days later."
            ),
        },
        "parameters": {
            "lookback_trading_days": LOOKBACK_DAYS,
            "before_adapter": "exp-20260526-014 VOLUME_BREADTH_BREAKOUT_PAPER",
            "notional_gate": "keep selected VBB paper notional only if IWM20 > SPY20",
            "paper_notional_usd": 10_000.0,
            "hold_days": 10,
            "locked_variables": [
                "VBB candidate definition",
                "VBB top-1 selection",
                "VBB paper notional before gate",
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
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / capital allocation: accepted VBB paper trades "
                "may need small-cap participation confirmation; this uses free "
                "OHLCV and matches the playbook's breadth/internal-structure lane."
            ),
            "2_history_check": {
                "accepted_vbb": (
                    "exp-20260526-014 accepted the shared default-off VBB paper "
                    "adapter: EV +0.7124 and PnL +$13,225.50 vs core, 3/3 windows."
                ),
                "recent_nearby": (
                    "exp-20260526-015 sector breadth and exp-20260526-016 theme "
                    "density both rejected due window regressions; this does not "
                    "retune VBB thresholds, top-N, or candidate score."
                ),
                "blocked_field": (
                    "RSP equal-weight confirmation was considered first but is "
                    "absent from all three canonical OHLCV snapshots, so Gate 2 "
                    "for that field failed and it was not tested."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows, before=exp014 VBB adapter, "
                "after=IWM-confirmed selected VBB notional gate; require positive "
                "aggregate EV/PnL, no EV/PnL-regressed window, >=30 trades across "
                "all windows, drawdown drift <=0.5pp, survival >=5%, and "
                "concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260526_017_vbb_iwm_market_confirmation.py"
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
                "SPY OHLCV close rows",
                "IWM OHLCV close rows",
                "selected exp014 VBB paper trade signal_date",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "rsp_field_status": "blocked_not_tested_missing_from_canonical_snapshots",
            "passed": gate2["passed"],
        },
        "gate3": {
            "core_survival_min": base._round(min_survival, 6),
            "core_survival_unchanged": True,
            "candidate_filter_added_to_live_core": False,
            "note": "This is a default-off paper notional gate on selected VBB trades; no core filter was added.",
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
        "before_vbb_trades_by_window": before_trades_by_window,
        "target_trades_by_window": target_trades_by_window,
        "removed_trades_by_window": removed_trades_by_window,
        "market_context_audit": market_context_audit,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
            "Accepted: IWM participation improves the accepted VBB adapter."
            if gate4_passed
            else (
                "Rejected: IWM>SPY 20d confirmation removed useful late/mid VBB "
                "paper exposure and regressed EV/PnL versus the accepted exp014 "
                "adapter. Do not add this gate or retry nearby IWM/SPY thresholds "
                "on the frozen windows without new forward rows."
            )
        ),
        "next_retry_requires": [
            "new_forward_vbb_closed_outcomes",
            "materially_different_market_participation_field_available_in_snapshots",
            "not_a_nearby_iwm_spy_threshold_retune",
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Kept / Before Trades | Removed PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["market_context_audit"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{kept}/{before_count} | ${removed:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                kept=audit["confirmed_trade_count"],
                before_count=audit["before_vbb_trade_count"],
                removed=audit["removed_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VBB IWM Market-Participation Confirmation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: on top of the accepted exp-20260526-014 VBB "
                "paper adapter, keep selected paper notional only when IWM 20-day "
                "return is greater than SPY 20-day return on the signal date."
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
            f"- kept trades: `{payload['gate4']['target_trade_summary']['total_trade_count']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Market Context Audit",
            "",
            "```json",
            json.dumps(payload["market_context_audit"], indent=2, sort_keys=True),
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
            "title": "VBB IWM market-participation confirmation",
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
                    "market_context_audit": payload["market_context_audit"],
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
