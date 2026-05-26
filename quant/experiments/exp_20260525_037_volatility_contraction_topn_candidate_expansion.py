"""exp-20260525-037: VCP QQQ-confirmed top-N candidate expansion.

This replay-only experiment starts from exp-20260525-022 and tests whether
the QQQ-confirmed volatility-contraction alpha has breadth beyond the daily
top-1 candidate. The only changed variable is the number of eligible same-day
VCP candidates admitted into the fixed-notional paper sleeve.

No shared adapter, live/default orders, core ranking, sizing, exits, LLM, news,
or universe logic is changed here. No JavaScript is used.
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
import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow  # noqa: E402


EXPERIMENT_ID = "exp-20260525-037"
STEM = "volatility_contraction_topn_candidate_expansion"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "vcp_qqq_confirmed_daily_topn_candidate_count"
TOPN_RULE_VERSION = "vcp_qqq_confirmed_topn_equal_notional_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SOURCE_EXP022_REL = (
    "data/experiments/exp-20260525-022/"
    "volatility_contraction_qqq_confirmed_sleeve.json"
)

VARIANTS: "OrderedDict[str, int]" = OrderedDict(
    [
        ("top2_equal_notional", 2),
        ("top3_equal_notional", 3),
    ]
)
SANITY_VARIANT = "top1_replay_sanity"
EXP022_MIN_EV_LIFT = 0.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
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
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
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


def _load_committed_exp022() -> dict[str, Any]:
    try:
        raw = subprocess.run(
            ["git", "show", f"HEAD:{SOURCE_EXP022_REL}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return {
            "source": "git_HEAD",
            "path": SOURCE_EXP022_REL,
            "payload": json.loads(raw),
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        path = REPO_ROOT / SOURCE_EXP022_REL
        return {
            "source": "working_tree_fallback",
            "path": SOURCE_EXP022_REL,
            "payload": json.loads(path.read_text(encoding="utf-8")),
        }


def _rank_candidates_by_date(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranks: Counter[str] = Counter()
    ranked: list[dict[str, Any]] = []
    for row in candidates:
        date = str(row.get("date") or "")
        ranks[date] += 1
        ranked.append(
            {
                **row,
                "vcp_topn_rule_version": TOPN_RULE_VERSION,
                "vcp_candidate_rank_on_signal_date": ranks[date],
                "known_at": "after_signal_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
    return ranked


def _select_topn_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    *,
    max_paper_trades_per_day: int,
    variant: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        enriched = {
            **row,
            "topn_variant": variant,
            "max_paper_trades_per_day": int(max_paper_trades_per_day),
        }
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**enriched, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= max_paper_trades_per_day:
            filtered.append({**enriched, "filter_reason": "daily_topn_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, enriched)
        if trade is None:
            filtered.append({**enriched, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(
            {
                **trade,
                "topn_variant": variant,
                "max_paper_trades_per_day": int(max_paper_trades_per_day),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
        used_date_counts[date] += 1
    return selected, filtered


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
        "dates_with_at_least_3_candidates": sum(1 for value in by_date.values() if value >= 3),
    }


def _variant_gate(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    target_windows: list[str],
    min_survival: float,
    exp022_comparison: dict[str, Any],
) -> dict[str, Any]:
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if not exp022_comparison["beats_exp022_ev_by_min_5pct"]:
        failed.append("did_not_beat_exp022_aggregate_ev_by_5pct")
    if exp022_comparison["windows_ev_regressed_vs_exp022"]:
        failed.append("window_ev_regression_vs_exp022")
    if exp022_comparison["windows_pnl_regressed_vs_exp022"]:
        failed.append("window_pnl_regression_vs_exp022")
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive_vs_core")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive_vs_core")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    return {
        "passed": not failed,
        "failed_reasons": failed,
        "passed_vs_core": (
            aggregate["expected_value_score_delta_sum"] > 0
            and aggregate["total_pnl_delta_sum"] > 0
        ),
        "promotion_grade_vs_exp022": (
            exp022_comparison["beats_exp022_ev_by_min_5pct"]
            and not exp022_comparison["windows_ev_regressed_vs_exp022"]
            and not exp022_comparison["windows_pnl_regressed_vs_exp022"]
        ),
        "beats_exp022_ev_by_min_5pct": exp022_comparison[
            "beats_exp022_ev_by_min_5pct"
        ],
        "no_ev_or_pnl_window_regression_vs_exp022": (
            not exp022_comparison["windows_ev_regressed_vs_exp022"]
            and not exp022_comparison["windows_pnl_regressed_vs_exp022"]
        ),
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _compare_to_exp022(
    source_exp022: dict[str, Any],
    variant_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source = source_exp022["payload"]
    source_by_window = source["delta_metrics"]["by_window"]
    source_aggregate = source["delta_metrics"]["aggregate"]
    source_ev = float(source_aggregate["expected_value_score_delta_sum"])
    source_pnl = float(source_aggregate["total_pnl_delta_sum"])
    variant_ev = sum(row["delta"]["expected_value_score"] for row in variant_rows.values())
    variant_pnl = sum(row["delta"]["total_pnl"] for row in variant_rows.values())
    windows_ev_regressed: list[str] = []
    windows_pnl_regressed: list[str] = []
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label, row in variant_rows.items():
        source_delta = source_by_window[label]
        ev_delta = float(row["delta"]["expected_value_score"])
        pnl_delta = float(row["delta"]["total_pnl"])
        source_window_ev = float(source_delta["expected_value_score"])
        source_window_pnl = float(source_delta["total_pnl"])
        if ev_delta < source_window_ev:
            windows_ev_regressed.append(label)
        if pnl_delta < source_window_pnl:
            windows_pnl_regressed.append(label)
        by_window[label] = {
            "variant_ev_delta": base._round(ev_delta, 6),
            "exp022_ev_delta": base._round(source_window_ev, 6),
            "ev_delta_vs_exp022": base._round(ev_delta - source_window_ev, 6),
            "variant_pnl_delta": base._round(pnl_delta, 2),
            "exp022_pnl_delta": base._round(source_window_pnl, 2),
            "pnl_delta_vs_exp022": base._round(pnl_delta - source_window_pnl, 2),
        }
    return {
        "source": source_exp022["source"],
        "comparison_artifact": source_exp022["path"],
        "source_exp022_overlay_ev_delta_sum": base._round(source_ev, 6),
        "source_exp022_overlay_pnl_delta_sum": base._round(source_pnl, 2),
        "variant_overlay_ev_delta_sum": base._round(variant_ev, 6),
        "variant_overlay_pnl_delta_sum": base._round(variant_pnl, 2),
        "overlay_ev_delta_vs_exp022_sum": base._round(variant_ev - source_ev, 6),
        "overlay_pnl_delta_vs_exp022_sum": base._round(variant_pnl - source_pnl, 2),
        "overlay_ev_lift_pct_vs_exp022": base._round(
            (variant_ev - source_ev) / source_ev, 6
        )
        if source_ev
        else None,
        "beats_exp022_ev_by_min_5pct": variant_ev >= source_ev * (1 + EXP022_MIN_EV_LIFT),
        "exp022_min_ev_lift": EXP022_MIN_EV_LIFT,
        "windows_ev_regressed_vs_exp022": windows_ev_regressed,
        "windows_pnl_regressed_vs_exp022": windows_pnl_regressed,
        "by_window": by_window,
    }


def _evaluate_variant(
    *,
    variant: str,
    max_paper_trades_per_day: int,
    before_results: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, list[dict[str, Any]]]],
    ranked_candidates_by_window: dict[str, list[dict[str, Any]]],
    min_survival: float,
    source_exp022: dict[str, Any],
) -> dict[str, Any]:
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for label in base.WINDOWS:
        selected_trades, filtered_candidates = _select_topn_paper_trades(
            snapshots[label],
            ranked_candidates_by_window[label],
            max_paper_trades_per_day=max_paper_trades_per_day,
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
    exp022_comparison = _compare_to_exp022(source_exp022, window_rows)
    gate4 = _variant_gate(
        aggregate=aggregate,
        target_summary=target_summary,
        target_windows=target_windows,
        min_survival=min_survival,
        exp022_comparison=exp022_comparison,
    )

    return {
        "variant": variant,
        "max_paper_trades_per_day": max_paper_trades_per_day,
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
        "source_exp022_comparison": exp022_comparison,
        "gate4": gate4,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
    }


def _choose_best_variant(variant_results: dict[str, dict[str, Any]]) -> str:
    return max(
        VARIANTS,
        key=lambda name: (
            1 if variant_results[name]["gate4"]["passed"] else 0,
            float(
                variant_results[name]["source_exp022_comparison"][
                    "overlay_ev_delta_vs_exp022_sum"
                ]
                or 0.0
            ),
            float(variant_results[name]["expected_value_score_delta"] or 0.0),
        ),
    )


def _build_payload() -> dict[str, Any]:
    _configure_base_module()
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_exp022 = _load_committed_exp022()
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
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = volatility_shadow._run_baseline(universe, cfg)
        before = base.overlay_helper._metrics(before_result)
        snapshot = volatility_shadow._load_snapshot(cfg["snapshot"])
        candidates = qqq_source._candidate_rows_for_window(
            snapshot, cfg, universe, before_result
        )
        ranked = _rank_candidates_by_date(candidates)
        before_results[label] = before_result
        before_metrics[label] = before
        snapshots[label] = snapshot
        ranked_candidates_by_window[label] = ranked
        raw_candidate_counts[label] = len(ranked)
        candidate_day_counts[label] = len({row["date"] for row in ranked})
        candidate_rank_audit[label] = _candidate_rank_summary(ranked)

    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    variant_results: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    variant_results[SANITY_VARIANT] = _evaluate_variant(
        variant=SANITY_VARIANT,
        max_paper_trades_per_day=1,
        before_results=before_results,
        before_metrics=before_metrics,
        snapshots=snapshots,
        ranked_candidates_by_window=ranked_candidates_by_window,
        min_survival=min_survival,
        source_exp022=source_exp022,
    )
    for variant, max_per_day in VARIANTS.items():
        variant_results[variant] = _evaluate_variant(
            variant=variant,
            max_paper_trades_per_day=max_per_day,
            before_results=before_results,
            before_metrics=before_metrics,
            snapshots=snapshots,
            ranked_candidates_by_window=ranked_candidates_by_window,
            min_survival=min_survival,
            source_exp022=source_exp022,
        )

    best_variant = _choose_best_variant(variant_results)
    best = variant_results[best_variant]
    accepted_variants = [
        name for name in VARIANTS if variant_results[name]["gate4"]["passed"]
    ]
    decision = (
        "promising_replay_only_vcp_topn_candidate_expansion"
        if accepted_variants
        else "rejected_vcp_topn_candidate_expansion"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The exp-20260525-022 QQQ-confirmed volatility-contraction alpha may "
            "have candidate breadth beyond the daily top-1 name. Expanding to "
            "top-2 or top-3 eligible candidates should improve aggregate EV over "
            "exp-022 without creating window regression or concentration drift if "
            "the signal is genuinely broad."
        ),
        "change_type": "vcp_qqq_confirmed_topn_candidate_expansion_replay",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 6,
        "nearby_prior_experiments": [
            "exp-20260525-020",
            "exp-20260525-022",
            "exp-20260525-024",
            "exp-20260525-027",
            "exp-20260525-030",
            "exp-20260525-032",
            "exp-20260525-033",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "vcp_qqq_confirmed_candidate_breadth_replay",
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
            "source_exp022_comparison": {
                "experiment_id": "exp-20260525-022",
                "artifact_source": source_exp022["source"],
                "artifact_path": source_exp022["path"],
            },
            "paper_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "variants": dict(VARIANTS),
            "sanity_variant": {SANITY_VARIANT: 1},
            "rule_version": TOPN_RULE_VERSION,
            "shadow_entry_filters": {
                "short_atr_days": volatility_shadow.SHORT_ATR_DAYS,
                "long_atr_days": volatility_shadow.LONG_ATR_DAYS,
                "max_short_to_long_atr_ratio": volatility_shadow.MAX_SHORT_TO_LONG_ATR_RATIO,
                "breakout_close_above_prior_n_day_high": volatility_shadow.BREAKOUT_LOOKBACK_DAYS,
                "close_above_n_day_moving_average": volatility_shadow.MA_DAYS,
                "candidate_day_rs_vs_spy_min": volatility_shadow.MIN_CANDIDATE_RS_VS_SPY,
                "min_candidate_day_dollar_volume": volatility_shadow.MIN_DOLLAR_VOLUME,
                "market_confirmation": "QQQ 20d return > SPY 20d return",
            },
            "selection_rank": [
                "signal_date",
                "short_to_long_atr_ratio asc",
                "candidate_day_rs_vs_spy desc",
                "dollar_volume desc",
                "ticker asc",
            ],
            "locked_variables": [
                "core universe",
                "VCP compression and breakout definition",
                "QQQ/SPY confirmation",
                "paper notional per trade",
                "hold days",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "must_compare_to": ["core", "exp-20260525-022"],
                "primary_baseline": "exp-20260525-022",
                "exp022_min_aggregate_ev_lift": EXP022_MIN_EV_LIFT,
                "no_window_ev_or_pnl_regression_vs_exp022": True,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: QQQ-confirmed VCP may have profitable "
                "breadth beyond the daily rank-1 candidate."
            ),
            "2_history_check": {
                "exp-20260525-022": (
                    "Accepted replay-only lead: top-1 QQQ-confirmed VCP improved "
                    "3/3 windows by +1.2493 EV / +$23,409.56."
                ),
                "exp-20260525-027": (
                    "Pocket-pivot support was weaker than exp-022 and should remain "
                    "metadata, not a replacement gate."
                ),
                "exp-20260525-030": (
                    "Event-context presence was positive vs core but weaker than "
                    "exp-022, so it should remain attribution only."
                ),
                "exp-20260525-032": (
                    "Volume dry-up was positive vs core but weaker than exp-022, "
                    "with mid_weak and old_thin regressions."
                ),
                "exp-20260525-033": (
                    "Parallel dossier/catalyst-quality work already occupied the "
                    "planned ID and is not part of this experiment."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows. A variant must beat "
                "exp-022 aggregate EV by at least 5%, have no EV or PnL regression "
                "versus exp-022 in any window, keep >=20 selected paper trades "
                "across all 3 windows, keep drawdown drift <=0.5pp, and pass "
                "single-ticker / HHI concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260525_037_volatility_contraction_topn_candidate_expansion.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{base._repo_rel(OUT_JSON)}#before_metrics",
            "source_exp022_artifact": source_exp022["path"],
            "source_exp022_artifact_source": source_exp022["source"],
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Close/Volume rows",
                "SPY and QQQ OHLCV Close rows for market confirmation",
                "computed qqq_gt_spy20 market confirmation",
                "VCP rank on signal date",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
            "note": (
                "The top-N field is computed from same-day sorted VCP candidates "
                "after QQQ confirmation. It is known after the signal-date close "
                "and before next-open paper entry."
            ),
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": base._round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or core entry rule was added. This is an additive "
                "default-off paper candidate-pool expansion, so core survival is "
                "unchanged from the baseline replay."
            ),
        },
        "gate4": {
            "passed": bool(accepted_variants),
            "accepted_variants": accepted_variants,
            "best_variant": best_variant,
            "best_variant_gate": best["gate4"],
            "best_variant_source_exp022_comparison": best["source_exp022_comparison"],
        },
        "before_metrics": before_metrics,
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "candidate_rank_audit": candidate_rank_audit,
        "qqq_market_gate_audit": qqq_source.MARKET_GATE_AUDIT,
        "variant_results": variant_results,
        "best_variant": best_variant,
        "accepted_variants": accepted_variants,
        "expected_value_score_delta": best["expected_value_score_delta"],
        "total_pnl_delta": best["total_pnl_delta"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": bool(accepted_variants),
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": bool(accepted_variants),
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "promotion_requirement": (
                "The accepted top-2 variant is promoted only into the shared "
                "default-off paper adapter with parity tests. It remains observe-only "
                "and cannot create live/default orders."
                if accepted_variants
                else (
                    "Only a variant that clears Gate 4 versus exp-022 may be promoted "
                    "into the shared default-off paper adapter with parity tests."
                )
            ),
        },
        "why_not_other_changes": (
            "Did not add another hard filter after pocket-pivot, event-context, "
            "and volume dry-up underperformed exp-022. This tests breadth of the "
            "same free-OHLCV alpha surface instead of adding noise tickers or "
            "retuning thresholds."
        ),
        "interpretation": (
            "The top-2 expansion variant beat exp-022 under the replay gate and "
            "is promoted into the shared default-off paper adapter with parity "
            "tests. It remains observe-only and cannot create live/default orders."
            if accepted_variants
            else (
                "The top-N expansion did not beat exp-022 under the required "
                "three-window gate. Do not promote it as a filter or adapter "
                "change; use the rank-breadth attribution to decide whether a "
                "more selective rank-2/rank-3 support feature is worth testing."
            )
        ),
        "rejection_reason": None
        if accepted_variants
        else "; ".join(best["gate4"]["failed_reasons"]),
        "next_evidence_needed": (
            "If rejected, inspect rank-2/rank-3 attribution by window and ticker "
            "before testing a narrower rank-depth support field. If accepted, "
            "collect closed forward replacement-value rows from the shared "
            "default-off volatility-contraction adapter before any live/default "
            "trade adapter."
        ),
        "related_files": [
            base._repo_rel(Path(__file__)),
            "quant/volatility_contraction_paper_sleeve.py",
            "quant/test_volatility_contraction_topn_paper_adapter.py",
            "docs/production_backtest_parity.md",
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
            SOURCE_EXP022_REL,
        ],
        "anti_js": "No JavaScript was used.",
    }


def _variant_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Variant | Gate | EV d vs core | PnL d vs core | EV d vs exp022 | PnL d vs exp022 | Trades | Windows | Max +share | HHI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, result in payload["variant_results"].items():
        comparison = result["source_exp022_comparison"]
        summary = result["target_trade_summary"]
        rows.append(
            "| {variant} | {gate} | {ev:+.4f} | ${pnl:+,.2f} | {evx:+.4f} | "
            "${pnlx:+,.2f} | {trades} | {windows} | {share} | {hhi} |".format(
                variant=variant,
                gate="PASS" if result["gate4"]["passed"] else "fail",
                ev=float(result["expected_value_score_delta"] or 0.0),
                pnl=float(result["total_pnl_delta"] or 0.0),
                evx=float(comparison["overlay_ev_delta_vs_exp022_sum"] or 0.0),
                pnlx=float(comparison["overlay_pnl_delta_vs_exp022_sum"] or 0.0),
                trades=summary["total_trade_count"],
                windows=len(summary["windows_with_target_trades"]),
                share=summary["max_single_positive_pnl_share"],
                hhi=summary["positive_pnl_hhi"],
            )
        )
    return rows


def _window_table(payload: dict[str, Any], variant: str) -> list[str]:
    result = payload["variant_results"][variant]
    rows = [
        "| Window | Variant EV d | Exp022 EV d | dEV vs exp022 | Variant PnL d | Exp022 PnL d | dPnL vs exp022 | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        comparison = result["source_exp022_comparison"]["by_window"][label]
        rows.append(
            "| {label} | {vev:+.4f} | {sev:+.4f} | {dev:+.4f} | "
            "${vpnl:+,.2f} | ${spnl:+,.2f} | ${dpnl:+,.2f} | {trades} |".format(
                label=label,
                vev=float(comparison["variant_ev_delta"] or 0.0),
                sev=float(comparison["exp022_ev_delta"] or 0.0),
                dev=float(comparison["ev_delta_vs_exp022"] or 0.0),
                vpnl=float(comparison["variant_pnl_delta"] or 0.0),
                spnl=float(comparison["exp022_pnl_delta"] or 0.0),
                dpnl=float(comparison["pnl_delta_vs_exp022"] or 0.0),
                trades=len(result["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_report(payload: dict[str, Any]) -> str:
    best_variant = payload["best_variant"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VCP Top-N Candidate Expansion",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: starting from exp-20260525-022, expand the "
                "QQQ-confirmed VCP same-day paper queue from top-1 to top-2/top-3 "
                "eligible candidates while keeping $10k notional, next-open entry, "
                "and 10-trading-day hold fixed."
            ),
            "",
            "## Variant Summary",
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
            "title": "VCP top-N candidate expansion",
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
    best = payload["variant_results"][payload["best_variant"]]
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "accepted_variants": payload["accepted_variants"],
                    "best_variant": payload["best_variant"],
                    "expected_value_score_delta": best["expected_value_score_delta"],
                    "total_pnl_delta": best["total_pnl_delta"],
                    "source_exp022_comparison": best["source_exp022_comparison"],
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
