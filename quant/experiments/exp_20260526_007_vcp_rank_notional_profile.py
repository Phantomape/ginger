"""exp-20260526-007: VCP top-2 rank-notional profile.

This replay-only experiment starts from the accepted exp-20260525-037 top-2
QQQ-confirmed volatility-contraction paper sleeve and tests one capital
allocation variable: the rank-1/rank-2 paper-notional profile.

It does not change VCP compression, breakout, QQQ/SPY confirmation, top-2
candidate selection, hold days, exits, LLM/news, universe, or live/default
orders. No JavaScript is used.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter, OrderedDict
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

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve as qqq_source  # noqa: E402
import exp_20260525_037_volatility_contraction_topn_candidate_expansion as topn_source  # noqa: E402
import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow  # noqa: E402


EXPERIMENT_ID = "exp-20260526-007"
STEM = "vcp_rank_notional_profile"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "vcp_top2_rank_notional_profile"
RANK_NOTIONAL_RULE_VERSION = "vcp_top2_rank_notional_profile_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SOURCE_EXP037_REL = (
    "data/experiments/exp-20260525-037/"
    "volatility_contraction_topn_candidate_expansion.json"
)

SANITY_VARIANT = "top2_equal_notional_sanity"
PROFILES: "OrderedDict[str, list[float]]" = OrderedDict(
    [
        (SANITY_VARIANT, [1.00, 1.00]),
        ("rank2_075", [1.00, 0.75]),
        ("rank2_125", [1.00, 1.25]),
        ("rank1_090_rank2_110", [0.90, 1.10]),
    ]
)
EXP037_MIN_EV_LIFT = 0.05
MAX_PAPER_TRADES_PER_DAY = 2
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE_VS_EXP037 = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE_VS_EXP037
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = volatility_shadow

    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(volatility_shadow, name):
            setattr(volatility_shadow, name, None)


def _load_committed_exp037() -> dict[str, Any]:
    try:
        raw = subprocess.run(
            ["git", "show", f"HEAD:{SOURCE_EXP037_REL}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {
            "source": "git_HEAD",
            "path": SOURCE_EXP037_REL,
            "payload": json.loads(raw),
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        path = REPO_ROOT / SOURCE_EXP037_REL
        return {
            "source": "working_tree_fallback",
            "path": SOURCE_EXP037_REL,
            "payload": json.loads(path.read_text(encoding="utf-8")),
        }


def rank_notional_scalar(rank: Any, profile: list[float]) -> float:
    try:
        idx = int(rank) - 1
    except (TypeError, ValueError):
        return 1.0
    if idx < 0 or idx >= len(profile):
        return 1.0
    return float(profile[idx])


def _apply_rank_notional_profile(
    trade: dict[str, Any],
    *,
    profile: list[float],
    variant: str,
) -> dict[str, Any]:
    scalar = rank_notional_scalar(
        trade.get("vcp_candidate_rank_on_signal_date"),
        profile,
    )
    base_notional = float(base.BASE_NOTIONAL_USD)
    base_pnl = float(trade.get("pnl") or 0.0)
    return {
        **trade,
        "rank_notional_profile_variant": variant,
        "rank_notional_profile_rule_version": RANK_NOTIONAL_RULE_VERSION,
        "rank_notional_profile": [float(value) for value in profile],
        "rank_notional_scalar": base._round(scalar, 6),
        "base_paper_notional_usd": base_notional,
        "base_equal_notional_pnl": base._round(base_pnl, 2),
        "paper_notional_usd": base._round(base_notional * scalar, 2),
        "pnl": base._round(base_pnl * scalar, 2),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _select_profile_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    *,
    profile: list[float],
    variant: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        enriched = {
            **row,
            "rank_notional_profile_variant": variant,
            "rank_notional_profile_rule_version": RANK_NOTIONAL_RULE_VERSION,
            "rank_notional_profile": [float(value) for value in profile],
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        }
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**enriched, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**enriched, "filter_reason": "daily_top2_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, enriched)
        if trade is None:
            filtered.append({**enriched, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(
            _apply_rank_notional_profile(trade, profile=profile, variant=variant)
        )
        used_date_counts[date] += 1
    return selected, filtered


def _compare_to_exp037(
    source_exp037: dict[str, Any],
    variant_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = source_exp037["payload"]
    source_top2 = source["variant_results"]["top2_equal_notional"]
    source_by_window = source_top2["delta_metrics"]["by_window"]
    source_ev = float(source_top2["expected_value_score_delta"])
    source_pnl = float(source_top2["total_pnl_delta"])
    variant_ev = sum(row["delta"]["expected_value_score"] for row in variant_rows.values())
    variant_pnl = sum(row["delta"]["total_pnl"] for row in variant_rows.values())
    windows_ev_regressed: list[str] = []
    windows_pnl_regressed: list[str] = []
    max_drawdown_worse_vs_exp037 = -999.0
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label, row in variant_rows.items():
        source_delta = source_by_window[label]
        ev_delta = float(row["delta"]["expected_value_score"])
        pnl_delta = float(row["delta"]["total_pnl"])
        dd_delta = float(row["delta"]["max_drawdown_pct"])
        source_window_ev = float(source_delta["expected_value_score"])
        source_window_pnl = float(source_delta["total_pnl"])
        source_window_dd = float(source_delta["max_drawdown_pct"])
        dd_worse = dd_delta - source_window_dd
        max_drawdown_worse_vs_exp037 = max(max_drawdown_worse_vs_exp037, dd_worse)
        if ev_delta < source_window_ev:
            windows_ev_regressed.append(label)
        if pnl_delta < source_window_pnl:
            windows_pnl_regressed.append(label)
        by_window[label] = {
            "variant_ev_delta": base._round(ev_delta, 6),
            "exp037_ev_delta": base._round(source_window_ev, 6),
            "ev_delta_vs_exp037": base._round(ev_delta - source_window_ev, 6),
            "variant_pnl_delta": base._round(pnl_delta, 2),
            "exp037_pnl_delta": base._round(source_window_pnl, 2),
            "pnl_delta_vs_exp037": base._round(pnl_delta - source_window_pnl, 2),
            "variant_drawdown_delta": base._round(dd_delta, 6),
            "exp037_drawdown_delta": base._round(source_window_dd, 6),
            "drawdown_worse_vs_exp037": base._round(dd_worse, 6),
        }
    return {
        "source": source_exp037["source"],
        "comparison_artifact": source_exp037["path"],
        "source_exp037_ev_delta_sum": base._round(source_ev, 6),
        "source_exp037_pnl_delta_sum": base._round(source_pnl, 2),
        "variant_ev_delta_sum": base._round(variant_ev, 6),
        "variant_pnl_delta_sum": base._round(variant_pnl, 2),
        "ev_delta_vs_exp037_sum": base._round(variant_ev - source_ev, 6),
        "pnl_delta_vs_exp037_sum": base._round(variant_pnl - source_pnl, 2),
        "ev_lift_pct_vs_exp037": base._round((variant_ev - source_ev) / source_ev, 6)
        if source_ev
        else None,
        "beats_exp037_ev_by_min_5pct": variant_ev >= source_ev * (1 + EXP037_MIN_EV_LIFT),
        "exp037_min_ev_lift": EXP037_MIN_EV_LIFT,
        "windows_ev_regressed_vs_exp037": windows_ev_regressed,
        "windows_pnl_regressed_vs_exp037": windows_pnl_regressed,
        "max_drawdown_worse_vs_exp037": base._round(max_drawdown_worse_vs_exp037, 6),
        "max_drawdown_worse_vs_exp037_guardrail": MAX_DRAWDOWN_WORSE_VS_EXP037,
        "by_window": by_window,
    }


def _profile_gate(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    target_windows: list[str],
    exp037_comparison: dict[str, Any],
) -> dict[str, Any]:
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if not exp037_comparison["beats_exp037_ev_by_min_5pct"]:
        failed.append("did_not_beat_exp037_aggregate_ev_by_5pct")
    if exp037_comparison["windows_ev_regressed_vs_exp037"]:
        failed.append("window_ev_regression_vs_exp037")
    if exp037_comparison["windows_pnl_regressed_vs_exp037"]:
        failed.append("window_pnl_regression_vs_exp037")
    if (
        float(exp037_comparison["max_drawdown_worse_vs_exp037"])
        > MAX_DRAWDOWN_WORSE_VS_EXP037
    ):
        failed.append("drawdown_drift_vs_exp037_too_high")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    return {
        "passed": not failed,
        "failed_reasons": failed,
        "beats_exp037_ev_by_min_5pct": exp037_comparison[
            "beats_exp037_ev_by_min_5pct"
        ],
        "no_ev_or_pnl_window_regression_vs_exp037": (
            not exp037_comparison["windows_ev_regressed_vs_exp037"]
            and not exp037_comparison["windows_pnl_regressed_vs_exp037"]
        ),
        "max_drawdown_worse_vs_exp037": exp037_comparison[
            "max_drawdown_worse_vs_exp037"
        ],
        "max_drawdown_worse_vs_exp037_guardrail": MAX_DRAWDOWN_WORSE_VS_EXP037,
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "aggregate_ev_delta_vs_core": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": aggregate["total_pnl_delta_sum"],
    }


def _evaluate_profile(
    *,
    variant: str,
    profile: list[float],
    before_results: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, list[dict[str, Any]]]],
    ranked_candidates_by_window: dict[str, list[dict[str, Any]]],
    source_exp037: dict[str, Any],
) -> dict[str, Any]:
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for label in base.WINDOWS:
        selected_trades, filtered_candidates = _select_profile_paper_trades(
            snapshots[label],
            ranked_candidates_by_window[label],
            profile=profile,
            variant=variant,
        )
        overlay = base._overlay_from_paper_trades(before_results[label], selected_trades)
        after = base.overlay_helper._metrics_with_overlay(before_results[label], overlay)
        delta = base.overlay_helper._delta(after, before_metrics[label])
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        window_rows[label] = {
            "before": before_metrics[label],
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(ranked_candidates_by_window[label]),
            "raw_candidate_days": len(
                {row["date"] for row in ranked_candidates_by_window[label]}
            ),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = base._aggregate(window_rows)
    target_summary = base._target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    exp037_comparison = _compare_to_exp037(source_exp037, window_rows)
    gate4 = _profile_gate(
        aggregate=aggregate,
        target_summary=target_summary,
        target_windows=target_windows,
        exp037_comparison=exp037_comparison,
    )

    return {
        "variant": variant,
        "rank_notional_profile": [float(value) for value in profile],
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "source_exp037_comparison": exp037_comparison,
        "gate4": gate4,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
    }


def _choose_best_variant(profile_results: dict[str, dict[str, Any]]) -> str:
    candidates = [name for name in PROFILES if name != SANITY_VARIANT]
    return max(
        candidates,
        key=lambda name: (
            1 if profile_results[name]["gate4"]["passed"] else 0,
            float(
                profile_results[name]["source_exp037_comparison"][
                    "ev_delta_vs_exp037_sum"
                ]
                or 0.0
            ),
            float(profile_results[name]["expected_value_score_delta"] or 0.0),
        ),
    )


def _candidate_rank_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_rank: Counter[str] = Counter()
    by_date: Counter[str] = Counter()
    for row in candidates:
        by_rank[str(row.get("vcp_candidate_rank_on_signal_date"))] += 1
        by_date[str(row.get("date") or "")] += 1
    return {
        "candidate_count": len(candidates),
        "candidate_day_count": len(by_date),
        "rank_count": dict(sorted(by_rank.items(), key=lambda item: int(item[0]))),
        "max_candidates_on_signal_date": max(by_date.values()) if by_date else 0,
        "dates_with_at_least_2_candidates": sum(1 for value in by_date.values() if value >= 2),
    }


def _build_payload() -> dict[str, Any]:
    _configure_base_module()
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_exp037 = _load_committed_exp037()
    universe = sorted(base.get_universe())
    before_results: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    snapshots: "OrderedDict[str, dict[str, list[dict[str, Any]]]]" = OrderedDict()
    ranked_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_day_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_rank_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    qqq_source._configure_base_module()
    _configure_base_module()
    qqq_source.MARKET_GATE_AUDIT.clear()
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = volatility_shadow._run_baseline(universe, cfg)
        before = base.overlay_helper._metrics(before_result)
        snapshot = volatility_shadow._load_snapshot(cfg["snapshot"])
        candidates = qqq_source._candidate_rows_for_window(
            snapshot, cfg, universe, before_result
        )
        ranked = topn_source._rank_candidates_by_date(candidates)
        before_results[label] = before_result
        before_metrics[label] = before
        snapshots[label] = snapshot
        ranked_candidates_by_window[label] = ranked
        raw_candidate_counts[label] = len(ranked)
        candidate_day_counts[label] = len({row["date"] for row in ranked})
        candidate_rank_audit[label] = _candidate_rank_summary(ranked)

    profile_results: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for variant, profile in PROFILES.items():
        profile_results[variant] = _evaluate_profile(
            variant=variant,
            profile=profile,
            before_results=before_results,
            before_metrics=before_metrics,
            snapshots=snapshots,
            ranked_candidates_by_window=ranked_candidates_by_window,
            source_exp037=source_exp037,
        )

    accepted_variants = [
        name for name in PROFILES if name != SANITY_VARIANT and profile_results[name]["gate4"]["passed"]
    ]
    best_variant = _choose_best_variant(profile_results)
    best = profile_results[best_variant]
    decision = (
        "accepted_shared_paper_adapter_vcp_rank_notional_profile"
        if accepted_variants
        else "rejected_vcp_rank_notional_profile"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The exp-20260525-037 top-2 VCP alpha may have a better capital "
            "allocation profile than equal $10k/$10k notional. Because rank 2 "
            "added positive EV in all three windows while top-3 added noise, "
            "a rank-2 notional scalar may improve expected value without changing "
            "entry selection."
        ),
        "change_type": "vcp_top2_rank_notional_profile_replay",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 7,
        "nearby_prior_experiments": [
            "exp-20260525-022",
            "exp-20260525-027",
            "exp-20260525-030",
            "exp-20260525-032",
            "exp-20260525-037",
        ],
        "multiple_testing_risk_bucket": "moderate_high",
        "new_evidence_type": "vcp_top2_rank_capital_allocation_profile_replay",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on the signal date; "
                "paper entry is next available open with production entry slippage; "
                "exit is the close ten trading days after the signal with target-side "
                "sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "base_universe_count": len(universe),
            "source_exp037_comparison": {
                "experiment_id": "exp-20260525-037",
                "artifact_source": source_exp037["source"],
                "artifact_path": source_exp037["path"],
            },
            "base_paper_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "profiles": PROFILES,
            "rule_version": RANK_NOTIONAL_RULE_VERSION,
            "locked_variables": [
                "core universe",
                "VCP compression and breakout definition",
                "QQQ/SPY confirmation",
                "top-2 candidate count",
                "candidate ranking order",
                "hold days",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "must_compare_to": ["core", "exp-20260525-037"],
                "primary_baseline": "exp-20260525-037",
                "exp037_min_aggregate_ev_lift": EXP037_MIN_EV_LIFT,
                "no_window_ev_or_pnl_regression_vs_exp037": True,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse_vs_exp037": MAX_DRAWDOWN_WORSE_VS_EXP037,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: exp037 proved top-2 VCP breadth; rank-2 may "
                "deserve more or less notional than equal sizing."
            ),
            "2_history_check": {
                "exp-20260525-037": (
                    "Top-2 equal-notional passed vs exp022 by +0.8237 EV / "
                    "+$11,386.36, while top-3 failed due window regressions."
                ),
                "exp-20260525-032": (
                    "Dry-up filter lagged exp022, arguing against another hard "
                    "filter and for capital allocation on the accepted top-2 set."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows. A profile must beat "
                "exp037 aggregate EV by at least 5%, have no EV/PnL regression "
                "versus exp037 in any window, keep drawdown drift <=0.50pp versus "
                "exp037, and pass concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260526_007_vcp_rank_notional_profile.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{base._repo_rel(OUT_JSON)}#before_metrics",
            "source_exp037_artifact": source_exp037["path"],
            "source_exp037_artifact_source": source_exp037["source"],
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Close/Volume rows",
                "SPY and QQQ OHLCV Close rows for market confirmation",
                "computed qqq_gt_spy20 market confirmation",
                "VCP rank on signal date",
                "rank_notional_profile scalar",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
            "note": (
                "The profile uses only rank already known after signal-date close "
                "and before next-open paper entry. It does not ask production or "
                "LLM to infer hidden fields."
            ),
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": base._round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                4,
            ),
            "passed": True,
            "note": (
                "No new core filter, entry source, or paper candidate filter was "
                "added. Only paper notional allocation changes."
            ),
        },
        "gate4": {
            "passed": bool(accepted_variants),
            "accepted_variants": accepted_variants,
            "best_variant": best_variant,
            "best_variant_profile": best["rank_notional_profile"],
            "best_variant_gate": best["gate4"],
            "best_variant_source_exp037_comparison": best["source_exp037_comparison"],
        },
        "before_metrics": before_metrics,
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "candidate_rank_audit": candidate_rank_audit,
        "qqq_market_gate_audit": qqq_source.MARKET_GATE_AUDIT,
        "profile_results": profile_results,
        "best_variant": best_variant,
        "accepted_variants": accepted_variants,
        "expected_value_score_delta": best["expected_value_score_delta"],
        "total_pnl_delta": best["total_pnl_delta"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": bool(accepted_variants),
            "backtester_adapter_changed": False,
            "run_adapter_changed": bool(accepted_variants),
            "replay_only": not bool(accepted_variants),
            "parity_test_added": bool(accepted_variants),
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "promotion_requirement": (
                "An accepted profile may only update the shared default-off VCP "
                "paper adapter with parity tests. It remains observe-only and "
                "cannot create live/default orders."
            ),
        },
        "why_not_other_changes": (
            "Did not retry top-3, which already failed in exp037. Did not add "
            "another hard filter after pocket-pivot, event-context, and dry-up "
            "lagged exp022. This tests capital allocation on the accepted top-2 "
            "candidate set only."
        ),
        "interpretation": (
            "At least one rank-notional profile beat exp037 under the replay gate. "
            "Promote only the accepted default-off paper adapter profile with "
            "parity tests."
            if accepted_variants
            else (
                "No rank-notional profile beat exp037 under the required gate. "
                "Keep equal notional and do not promote a profile tweak."
            )
        ),
        "rejection_reason": None
        if accepted_variants
        else "; ".join(best["gate4"]["failed_reasons"]),
        "next_evidence_needed": (
            "If accepted, collect closed forward replacement-value rows for the "
            "profiled top-2 sleeve before any live/default trade adapter."
        ),
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
            "quant/volatility_contraction_paper_sleeve.py",
            "quant/test_volatility_contraction_topn_paper_adapter.py",
            "quant/test_vcp_rank_notional_profile.py",
            "docs/production_backtest_parity.md",
            SOURCE_EXP037_REL,
        ],
        "anti_js": "No JavaScript was used.",
    }


def _variant_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Variant | Profile | Gate | EV d vs core | PnL d vs core | EV d vs exp037 | PnL d vs exp037 | DD worse vs exp037 | Trades | Max +share | HHI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, result in payload["profile_results"].items():
        comparison = result["source_exp037_comparison"]
        summary = result["target_trade_summary"]
        rows.append(
            "| {variant} | `{profile}` | {gate} | {ev:+.4f} | ${pnl:+,.2f} | "
            "{evx:+.4f} | ${pnlx:+,.2f} | {dd:+.4f} | {trades} | {share} | {hhi} |".format(
                variant=variant,
                profile=result["rank_notional_profile"],
                gate="PASS" if result["gate4"]["passed"] else "fail",
                ev=float(result["expected_value_score_delta"] or 0.0),
                pnl=float(result["total_pnl_delta"] or 0.0),
                evx=float(comparison["ev_delta_vs_exp037_sum"] or 0.0),
                pnlx=float(comparison["pnl_delta_vs_exp037_sum"] or 0.0),
                dd=float(comparison["max_drawdown_worse_vs_exp037"] or 0.0),
                trades=summary["total_trade_count"],
                share=summary["max_single_positive_pnl_share"],
                hhi=summary["positive_pnl_hhi"],
            )
        )
    return rows


def _window_table(payload: dict[str, Any], variant: str) -> list[str]:
    result = payload["profile_results"][variant]
    rows = [
        "| Window | Variant EV d | Exp037 EV d | dEV vs exp037 | Variant PnL d | Exp037 PnL d | dPnL vs exp037 | DD worse vs exp037 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        comparison = result["source_exp037_comparison"]["by_window"][label]
        rows.append(
            "| {label} | {vev:+.4f} | {sev:+.4f} | {dev:+.4f} | "
            "${vpnl:+,.2f} | ${spnl:+,.2f} | ${dpnl:+,.2f} | {dd:+.4f} |".format(
                label=label,
                vev=float(comparison["variant_ev_delta"] or 0.0),
                sev=float(comparison["exp037_ev_delta"] or 0.0),
                dev=float(comparison["ev_delta_vs_exp037"] or 0.0),
                vpnl=float(comparison["variant_pnl_delta"] or 0.0),
                spnl=float(comparison["exp037_pnl_delta"] or 0.0),
                dpnl=float(comparison["pnl_delta_vs_exp037"] or 0.0),
                dd=float(comparison["drawdown_worse_vs_exp037"] or 0.0),
            )
        )
    return rows


def _build_report(payload: dict[str, Any]) -> str:
    best_variant = payload["best_variant"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VCP Top-2 Rank-Notional Profile",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: starting from exp-20260525-037 top-2 equal "
                "notional, test rank-1/rank-2 paper-notional profiles while "
                "keeping candidate selection and execution fixed."
            ),
            "",
            "## Profile Summary",
            "",
            *_variant_table(payload),
            "",
            f"## Best Variant: `{best_variant}`",
            "",
            *_window_table(payload, best_variant),
            "",
            "## Candidate Rank Audit",
            "",
            "```json",
            json.dumps(payload["candidate_rank_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            payload["interpretation"],
            "",
            (
                "No live/default orders, core entry, ranking, sizing, exits, "
                "LLM/news, or core universe behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "VCP top-2 rank-notional profile",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    best = payload["profile_results"][payload["best_variant"]]
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "accepted_variants": payload["accepted_variants"],
                    "best_variant": payload["best_variant"],
                    "best_profile": best["rank_notional_profile"],
                    "expected_value_score_delta": best["expected_value_score_delta"],
                    "total_pnl_delta": best["total_pnl_delta"],
                    "source_exp037_comparison": best["source_exp037_comparison"],
                    "gate4": best["gate4"],
                    "target_trade_summary": best["target_trade_summary"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
