"""exp-20260620-002: uranium/nuclear relation with core-flow confirmation.

Replay-only alpha search. The single decision hypothesis is that the fixed
uranium producer to nuclear candidate-pool relation from exp-20260620-001
only has replacement value when the same signal date already has production
core A/B entry flow, excluding same-ticker overlap.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260620_001_uranium_nuclear_relation_leadership as relation


framework = relation.framework
base = relation.base

EXPERIMENT_ID = "exp-20260620-002"
STEM = "uranium_nuclear_core_flow_confirmation"
TRIAL_FAMILY = "uranium_nuclear_core_flow_confirmation_candidate_pool"
TRIAL_VARIANT_ID = "uranium_nuclear_core_flow_top1_next_open_10d_v1"
CHANGED_VARIABLE = "uranium_nuclear_core_flow_confirmed_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = relation.REPO_ROOT
BASELINE_RESULT_JSON = relation.BASELINE_RESULT_JSON
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_002_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = relation.EXPERIMENT_LOG
REGISTRY_JSON = relation.REGISTRY_JSON

BASE_NOTIONAL_USD = relation.BASE_NOTIONAL_USD
HOLD_DAYS = relation.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = relation.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = relation.SAME_TICKER_COOLDOWN_DAYS

MARKET_PROXY_TICKER = relation.MARKET_PROXY_TICKER
URANIUM_ANCHOR_TICKERS = relation.URANIUM_ANCHOR_TICKERS
NUCLEAR_CANDIDATE_TICKERS = relation.NUCLEAR_CANDIDATE_TICKERS

COMPRESSION_COMPARATOR = relation.COMPRESSION_COMPARATOR
DISTRIBUTION_COMPARATOR = relation.DISTRIBUTION_COMPARATOR

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "target_sample_too_small",
        "window_regression",
        "accepted_comparator_not_beaten",
        "theme_beta_not_repaired",
    ],
    "confidence_reason": (
        "exp-20260620-001 had positive aggregate but failed late_strong/"
        "concentration; accepted 52-week and industry-flow helpers show "
        "core-flow confirmation can filter theme beta. Risk is sample "
        "thinning and same-family overfit."
    ),
    "recorded_at": "2026-06-20T01:09:59+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
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
    "uses_llm": False,
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "uses_core_ab_entry_flow": True,
    "uses_uranium_nuclear_relation": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $8 and ADV20 >= $25M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing anchor/candidate OHLCV, failed uranium anchor breadth, "
            "missing same-day core A/B flow, same-ticker core overlap, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "uranium anchor breadth, fixed nuclear candidate universe, liquid "
        "constructive candidate gates, same-day core-flow confirmation, "
        "same-ticker core-overlap exclusion, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: the fixed uranium producer to nuclear candidate-pool "
        "relation from exp-20260620-001 may only have replacement value when "
        "the same signal date already has production core A/B entry flow, "
        "because core flow marks a broader deployable risk appetite day while "
        "excluding same-ticker overlap prevents double-counting an existing "
        "core pick."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate warned on prior core-flow confirmation families; "
            "the override records a new evidence axis: same-day production "
            "core-entry flow confirmation plus same-ticker core-overlap "
            "exclusion applied to the fixed uranium/nuclear relation, with no "
            "anchor/candidate list, threshold, top-N, hold, cooldown, or "
            "notional retune."
        ),
        "exp-20260620-001": (
            "Rejected the naked uranium/nuclear relation. Aggregate EV/PnL "
            "was positive, but late_strong regressed and concentration/"
            "accepted-comparator checks failed. This run keeps the fixed "
            "relation and adds only core-flow provenance."
        ),
        "exp-20260608-008": (
            "Accepted shared industry-stable core-flow adapter, showing that "
            "same-day core-flow confirmation can be production-visible when "
            "implemented in a shared helper. This run is not promoted because "
            "it is only a replay scout."
        ),
        "exp-20260610-008": (
            "Accepted 52-week high proximity full-stack helper used core-flow "
            "confirmation and same-ticker overlap exclusion. This run tests "
            "whether that provenance idea repairs a different uranium/nuclear "
            "relation family."
        ),
        "exp-20260619-021": (
            "Rejected rate-relief growth leadership. This run does not use "
            "macro duration proxies or QQQ-vs-SPY growth context."
        ),
    },
    "3_attribution_scope": (
        "Only same-day core A/B entry-flow confirmation and same-ticker "
        "core-overlap exclusion are new. Uranium anchors, nuclear candidate "
        "tickers, thresholds, notional, hold days, top-N, cooldown, costs, and "
        "baseline protocol remain fixed from exp-20260620-001."
    ),
    "4_success_criteria": (
        "Gate 4 across the docs/backtesting.md canonical three windows must "
        "improve aggregate expected_value_score and PnL without unacceptable "
        "drawdown, sample, survival, or concentration degradation. A positive "
        "private replay remains a lead only until shared-helper parity exists."
    ),
    "5_reproducibility": (
        "Runner, artifact, card, log, manifest, ticket, command, and "
        "before/after three-window metrics are written under exp-20260620-002."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _configure_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._configure_sleeve_globals()


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(NUCLEAR_CANDIDATE_TICKERS) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["fixed_candidate_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    context_sample: list[dict[str, Any]] = []

    for signal_date in window_dates:
        ab_entries = core_entries_by_date.get(signal_date, [])
        if not ab_entries:
            scan["days_without_core_flow"] += 1
            continue
        scan["core_flow_days"] += 1
        context = relation._anchor_context(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            scan["failed_anchor_context_days"] += 1
            continue
        scan["anchor_context_pass_days"] += 1
        if len(context_sample) < 5:
            context_sample.append(
                {
                    "date": signal_date,
                    "same_day_ab_entry_count": len(ab_entries),
                    **context,
                }
            )
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            confirm = relation._candidate_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if confirm is None:
                scan["failed_candidate_confirmation"] += 1
                continue
            scan["raw_candidates_before_core_overlap_filter"] += 1
            same_ticker_overlap = any(
                str(trade.get("ticker") or "").upper() == ticker for trade in ab_entries
            )
            if same_ticker_overlap:
                scan["raw_candidates_excluded_same_ticker_core_overlap"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "URANIUM_NUCLEAR_CORE_FLOW_CONFIRMATION_PAPER",
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "signal_date_ohlcv_close_and_core_entry_log_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": True,
                    "same_ticker_ab_overlap": False,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_core_ab_entry_flow": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **context,
                    **confirm,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_ret5"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(candidates)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    scan["context_sample"] = context_sample
    return candidates, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "anchor_tickers": list(URANIUM_ANCHOR_TICKERS),
        "candidate_tickers": list(NUCLEAR_CANDIDATE_TICKERS),
        "core_flow_confirmation_required": True,
        "same_ticker_core_overlap_excluded": True,
        "min_anchor_count": relation.MIN_ANCHOR_COUNT,
        "min_anchor_ret20_excess_spy": relation.MIN_ANCHOR_RET20_EXCESS_SPY,
        "min_candidate_ret20_excess_spy": relation.MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_avg_dollar_volume_20d": relation.MIN_AVG_DOLLAR_VOLUME_20D,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_uranium_nuclear_core_flow_confirmation"
        if gate["passed"]
        else "rejected_uranium_nuclear_core_flow_confirmation_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and uranium/nuclear core-flow replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        core_entries_by_date = framework.shadow._baseline_entries(before_result)
        snapshot = relation._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(universe),
        )
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "market_proxy_present": MARKET_PROXY_TICKER in snapshot,
            "anchors_present": {
                ticker: ticker in snapshot for ticker in URANIUM_ANCHOR_TICKERS
            },
            "candidates_present": {
                ticker: ticker in snapshot for ticker in NUCLEAR_CANDIDATE_TICKERS
            },
        }
        candidates, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
            core_entries_by_date=core_entries_by_date,
        )
        selected_trades, filtered_candidates = framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_scan_by_window[label] = context_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    rejection_reason = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "implementation_mode": "private_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_uranium_nuclear_candidate_pool",
        "new_evidence_type": "free_ohlcv_core_entry_flow_confirmation",
        "nearby_prior_experiments": [
            "exp-20260620-001",
            "exp-20260608-008",
            "exp-20260610-008",
            "exp-20260619-021",
        ],
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": "high",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "anchor_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "core_flow_source": "same-window baseline result via shadow._baseline_entries",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Uranium anchor and candidate stock features are computed from "
                "OHLCV rows with Date <= signal_date. Core-flow confirmation "
                "comes from same-window core baseline entries already known for "
                "that signal date. Paper entry is the next available open with "
                "existing entry slippage; exit is the close 10 trading days "
                "after the signal with target-side sell slippage and "
                "ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "core_flow_confirmation_required": True,
            "same_ticker_core_overlap_excluded": True,
            "anchor_tickers": list(URANIUM_ANCHOR_TICKERS),
            "candidate_tickers": list(NUCLEAR_CANDIDATE_TICKERS),
            "min_anchor_count": relation.MIN_ANCHOR_COUNT,
            "min_anchor_ret20_excess_spy": relation.MIN_ANCHOR_RET20_EXCESS_SPY,
            "min_anchor_ret5": relation.MIN_ANCHOR_RET5,
            "min_anchor_close_location": relation.MIN_ANCHOR_CLOSE_LOCATION,
            "min_spy_ret20": relation.MIN_SPY_RET20,
            "min_price": relation.MIN_PRICE,
            "min_avg_dollar_volume_20d": relation.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_candidate_ret20_excess_spy": relation.MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret5": relation.MIN_CANDIDATE_RET5,
            "min_candidate_close_location": relation.MIN_CANDIDATE_CLOSE_LOCATION,
            "min_signal_return": relation.MIN_SIGNAL_RETURN,
            "max_signal_return": relation.MAX_SIGNAL_RETURN,
            "max_realized_vol_20d": relation.MAX_REALIZED_VOL_20D,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(BASELINE_RESULT_JSON),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "baseline core entries by same signal date",
                "uranium anchor OHLCV Date/Open/High/Low/Close/Volume",
                "nuclear candidate OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV Date/Open/High/Low/Close/Volume",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
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
                "source is additive default-off paper, so core signals "
                "generated/survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The uranium/nuclear core-flow confirmation source cleared Gate 4 "
            "as a replay-only/default-off lead, but no production surface was "
            "promoted."
            if gate4["passed"]
            else (
                "The uranium/nuclear core-flow confirmation source did not "
                "clear Gate 4 (failed: "
                + (", ".join(gate4["failed_reasons"]) or "none")
                + "). Do not promote or tune this fixed relation bundle on "
                "the same frozen windows."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "A retry needs materially different PIT nuclear demand/supply "
            "evidence, such as contract awards, utility procurement, reactor "
            "approval events, ownership/flow confirmation beyond same-day core "
            "entries, or closed forward replacement rows. Do not sweep anchor "
            "lookbacks, candidate thresholds, top-N, hold, cooldown, or "
            "notional on these frozen windows."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "Gate 4 passed numerically, but this is replay-only because no "
                "shared daily/backtest helper exists."
                if gate4["passed"]
                else (
                    "Rejected. Adding same-day core A/B entry-flow "
                    "confirmation to the fixed uranium/nuclear relation "
                    "either removed too much sample or still did not create "
                    "robust replacement value versus accepted compression/"
                    "distribution candidate-pool comparators after next-open "
                    "execution, costs, cooldown, and concentration checks "
                    "(failed: {}). The evidence suggests the static relation "
                    "still behaves like crowded theme beta rather than a "
                    "distinct deployable spillover."
                ).format(", ".join(gate4["failed_reasons"]) or "none")
            ),
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
                "Do not retry by sweeping uranium anchor count/ret20/ret5/"
                "close-location thresholds, fixed candidate list, RS/volume/"
                "vol guards, core-flow day definitions, top-N, hold days, "
                "cooldown, or notional on these frozen windows."
            ),
            "new_evidence_required": (
                "Need PIT event/procurement/flow/ownership evidence beyond "
                "same-day core entries or closed forward replacement-value "
                "rows before revisiting uranium to nuclear relation leadership."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Core days | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {core} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                core=scan.get("core_flow_days", 0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Uranium Nuclear Core-Flow Confirmation",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
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
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "core_flow_days": payload["context_scan_by_window"][label].get("core_flow_days"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
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
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
