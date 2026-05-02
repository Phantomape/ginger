"""
Signal-Level Backtester — replays historical OHLCV through the ACTUAL pipeline.

Unlike the previous simplified breakout heuristic, this backtester calls the
real signal_engine.generate_signals() + risk_engine.enrich_signals() + all
quant filter layers from run.py.  It assumes every signal that survives the
pipeline is executed at next-day open (with exec_lag), and tracks positions
using the signal's stop_price and target_price.

Strategy C (earnings) is excluded because historical earnings dates are
unreliable via yfinance.  Only Strategy A (trend) and B (breakout) are tested.

KNOWN PARITY GAP — news veto layer:
    Production (`run.py`) applies a T1-negative-news veto via filter.py
    (EVENT_KEYWORDS, T1_TITLE_KEYWORDS).  We have no historical news archive
    to replay, so signals that production rejected on news grounds will be
    accepted in backtest.  Empirically this inflates win rate / total return
    by an unknown but non-zero margin.  Treat backtest numbers as an
    OPTIMISTIC upper bound.  This caveat is also surfaced in the result dict
    under `result["caveats"]` and persisted to the saved JSON.

Usage:
    cd d:/Github/ginger
    python quant/backtester.py                        # default 6-month backtest
    python quant/backtester.py --start 2025-06-01 --end 2025-12-31
    python quant/backtester.py --sweep ATR_STOP_MULT 1.0 1.5 2.0
"""

import json
import logging
import math
import os
import sys
import tempfile
from datetime import datetime

import pandas as pd
import yfinance as yf
import yfinance.cache as yf_cache

logger = logging.getLogger(__name__)


PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "GIT_HTTP_PROXY",
    "GIT_HTTPS_PROXY",
)

# ── Defaults ────────────────────────────────────────────────────────────────

# Ensure quant/ is on sys.path before importing from constants (supports both
# `python quant/backtester.py` and `python -m quant.backtester` invocations).
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from constants import (
    MAX_POSITIONS,
    MAX_PER_SECTOR,
    ADVERSE_GAP_CANCEL_PCT,
    CANCEL_GAP_PCT,
    ATR_STOP_MULT,
    ATR_TARGET_MULT,
    ENABLED_STRATEGIES,
    BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
    BREAKOUT_RANK_BY_52W_HIGH,
    REGIME_AWARE_EXIT,
    MAX_POSITION_PCT,
    MAX_PORTFOLIO_HEAT,
    ADDON_ENABLED,
    ADDON_CHECKPOINT_DAYS,
    ADDON_MIN_UNREALIZED_PCT,
    ADDON_MIN_RS_VS_SPY,
    ADDON_FRACTION_OF_ORIGINAL_SHARES,
    ADDON_MAX_POSITION_PCT,
    ADDON_REQUIRE_CHECKPOINT_CAP_ROOM,
    ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH,
    SECOND_ADDON_ENABLED,
    SECOND_ADDON_CHECKPOINT_DAYS,
    SECOND_ADDON_MIN_UNREALIZED_PCT,
    SECOND_ADDON_MIN_RS_VS_SPY,
    SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES,
    SECOND_ADDON_MAX_POSITION_PCT,
    DEFER_BREAKOUT_WHEN_SLOTS_LTE,
    DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
    TRAILING_STOP_PCT,
)
from regime_exit import compute_regime_exit_profile
from production_parity import (
    TRAILING_PARTIAL_REDUCE_ENABLED,
    classify_entry_open_cancel,
    filter_entry_signal_candidates,
    partial_reduce_shares,
    plan_entry_candidates,
    production_trailing_stop_price,
    risk_pct_for_market_state,
    suggested_reduce_pct_for_rules,
)
from position_manager import compute_exit_levels, evaluate_exit_signals
from yfinance_bootstrap import configure_yfinance_runtime
from pilot_sleeve import (
    PILOT_SLEEVE_NAME,
    apply_pilot_sizing_policy,
    build_counterfactual_snapshots,
    mark_pilot_signals,
    pilot_governance_metadata,
    pilot_records_as_of,
    select_pilot_entry_candidates,
)
from candidate_competition_logger import compute_decision_outcome_attribution

DEFAULT_CONFIG = {
    "INITIAL_CAPITAL":     100_000.0,
    "MAX_POSITIONS":       MAX_POSITIONS,
    "MAX_POSITION_PCT":    MAX_POSITION_PCT,
    "MAX_PER_SECTOR":      MAX_PER_SECTOR,
    "ENABLED_STRATEGIES":  ENABLED_STRATEGIES,
    "BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH": BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
    "BREAKOUT_RANK_BY_52W_HIGH": BREAKOUT_RANK_BY_52W_HIGH,
    "LOOKBACK_CALENDAR_DAYS": 400,   # enough for 200-day MA + features
    "ATR_TARGET_MULT":     ATR_TARGET_MULT,  # target = entry + N × ATR
    "REGIME_AWARE_EXIT":   REGIME_AWARE_EXIT,  # smooth target width by entry-day regime strength
    # Trailing stop config (set TRAIL_TRIGGER_ATR_MULT=0 to disable, use fixed target)
    "TRAIL_TRIGGER_ATR_MULT": 0,     # activate trail when profit >= N × ATR (0=off)
    "TRAIL_OFFSET_ATR_MULT":  0,     # trailing stop = high_water - N × ATR
    "REPLAY_PARTIAL_REDUCES": True,  # replay production position-action policy
    "PRODUCTION_TRAILING_STOP_PCT": TRAILING_STOP_PCT,
    "TRAILING_PARTIAL_REDUCE_ENABLED": TRAILING_PARTIAL_REDUCE_ENABLED,
    "ADDON_ENABLED": ADDON_ENABLED,
    "ADDON_CHECKPOINT_DAYS": ADDON_CHECKPOINT_DAYS,
    "ADDON_MIN_UNREALIZED_PCT": ADDON_MIN_UNREALIZED_PCT,
    "ADDON_MIN_RS_VS_SPY": ADDON_MIN_RS_VS_SPY,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": ADDON_FRACTION_OF_ORIGINAL_SHARES,
    "ADDON_MAX_POSITION_PCT": ADDON_MAX_POSITION_PCT,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": ADDON_REQUIRE_CHECKPOINT_CAP_ROOM,
    "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH,
    "SECOND_ADDON_ENABLED": SECOND_ADDON_ENABLED,
    "SECOND_ADDON_CHECKPOINT_DAYS": SECOND_ADDON_CHECKPOINT_DAYS,
    "SECOND_ADDON_MIN_UNREALIZED_PCT": SECOND_ADDON_MIN_UNREALIZED_PCT,
    "SECOND_ADDON_MIN_RS_VS_SPY": SECOND_ADDON_MIN_RS_VS_SPY,
    "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES": SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES,
    "SECOND_ADDON_MAX_POSITION_PCT": SECOND_ADDON_MAX_POSITION_PCT,
    "DEFER_BREAKOUT_WHEN_SLOTS_LTE": DEFER_BREAKOUT_WHEN_SLOTS_LTE,
    "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
    "ADVERSE_GAP_CANCEL_PCT": ADVERSE_GAP_CANCEL_PCT,
}

EXIT_POLICY_ADVISORY_RULES = (
    "SIGNAL_TARGET",
    "PROFIT_TARGET",
    "PROFIT_LADDER_30",
    "PROFIT_LADDER_50",
    "TIME_STOP",
    "PENDING_REDUCE_EXIT_OVERRIDE",
)

EXIT_POLICY_SHADOW_RULES = tuple(
    rule for rule in EXIT_POLICY_ADVISORY_RULES
    if rule != "PENDING_REDUCE_EXIT_OVERRIDE"
)


def build_exit_policy_replay_bias(
    partial_reduce_enabled=True,
    trailing_partial_reduce_enabled=TRAILING_PARTIAL_REDUCE_ENABLED,
):
    """Describe production exit advice that the backtester does not execute."""
    return {
        "gap_present": True,
        "production_sources": [
            "trend_signals.compute_position_context",
            "position_manager.evaluate_exit_signals",
            "llm_advisor.get_investment_advice",
            "pending_actions.apply_pending_action_overrides",
        ],
        "backtester_execution_scope": [
            "stop_price full-position exit",
            "target_price full-position exit",
            "implemented shared partial-reduce replay hooks only",
        ],
        "production_advisory_actions_not_replayed": list(EXIT_POLICY_ADVISORY_RULES),
        "target_price_semantic_gap": {
            "backtester": (
                "Position.target_price is simulated as a hard full-position "
                "target exit when the intraday high reaches the level."
            ),
            "production": (
                "open_positions.target_price is read as signal_target_price "
                "and surfaces SIGNAL_TARGET as advisory reduce/review context "
                "for the LLM and daily workflow."
            ),
            "impact": (
                "Backtest target exits are not proof that production advisory "
                "SIGNAL_TARGET trims, ladders, or time stops add alpha."
            ),
        },
        "partial_reduce_replay_scope": {
            "replay_container_enabled": bool(partial_reduce_enabled),
            "trailing_partial_reduce_enabled": bool(
                trailing_partial_reduce_enabled
            ),
            "note": (
                "The default replay container is on for shared production "
                "position-action policies, but rejected pure trailing trims "
                "remain disabled by production_parity unless explicitly "
                "enabled for diagnostics."
            ),
        },
        "rejected_simple_replay": {
            "experiment_id": "exp-20260429-032",
            "tested_change": (
                "reinterpret target_price as SIGNAL_TARGET 33% partial reduce"
            ),
            "decision": "rejected",
            "reason": (
                "EV and PnL regressed in all three fixed windows; do not "
                "retry bare SIGNAL_TARGET trim variants without a complete "
                "shared lifecycle policy."
            ),
        },
        "recommended_next_step": (
            "Use exit_advisory_shadow_attribution before promoting any "
            "executable shared exit lifecycle."
        ),
    }


def build_pending_action_replay_bias(data_dir):
    """Describe the production pending-action ledger gap without using it."""
    path = os.path.join(data_dir, "pending_actions.json")
    payload = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            payload = None

    actions = []
    if isinstance(payload, dict) and isinstance(payload.get("pending_actions"), list):
        actions = payload.get("pending_actions") or []
    elif isinstance(payload, list):
        actions = payload

    open_actions = [
        action for action in actions
        if isinstance(action, dict) and action.get("status", "open") == "open"
    ]

    def _count_action(kind):
        return sum(
            1 for action in open_actions
            if str(action.get("action", "")).upper() == kind
        )

    return {
        "gap_present": True,
        "ledger_present": os.path.exists(path),
        "ledger_path": path if os.path.exists(path) else None,
        "ledger_updated_at": payload.get("updated_at") if isinstance(payload, dict) else None,
        "open_actions_count": len(open_actions),
        "open_reduce_actions_count": _count_action("REDUCE"),
        "open_exit_actions_count": _count_action("EXIT"),
        "historical_replay_enabled": False,
        "production_behavior": (
            "pending_actions.apply_pending_action_overrides can preserve "
            "unexecuted REDUCE/EXIT advice across daily runs."
        ),
        "backtester_behavior": (
            "canonical backtests do not replay the current pending_actions "
            "ledger because it is not a point-in-time historical account log."
        ),
        "next_step": (
            "Only promote this to replay after daily point-in-time action "
            "ledger snapshots exist and can be matched to simulated positions."
        ),
    }


def build_earnings_event_data_quality(earnings_snapshots, sim_dates):
    """Summarize earnings snapshot availability for Strategy C disclosure."""
    snapshots = earnings_snapshots or {}
    snapshot_dates = sorted(snapshots)

    def _date_key(value):
        if hasattr(value, "strftime"):
            return value.strftime("%Y%m%d")
        return str(value).replace("-", "")[:8]

    sim_date_keys = [_date_key(day) for day in (sim_dates or [])]
    exact_snapshot_dates = [
        date_key for date_key in sim_date_keys
        if date_key in snapshots
    ]
    walk_forward_dates = []
    for date_key in sim_date_keys:
        if any(snapshot_date <= date_key for snapshot_date in snapshot_dates):
            walk_forward_dates.append(date_key)

    row_count = 0
    eps_rows = 0
    surprise_rows = 0
    for snapshot in snapshots.values():
        if not isinstance(snapshot, dict):
            continue
        for item in snapshot.values():
            if not isinstance(item, dict):
                continue
            row_count += 1
            if item.get("eps_estimate") is not None:
                eps_rows += 1
            if (
                item.get("avg_historical_surprise_pct") is not None
                or bool(item.get("historical_surprise_pct"))
            ):
                surprise_rows += 1

    trading_days = len(sim_date_keys)
    has_snapshots = bool(snapshot_dates)
    return {
        "days_to_earnings_source": (
            "yfinance calendar plus walk-forward simulation date"
        ),
        "snapshot_archive_present": has_snapshots,
        "snapshot_count": len(snapshot_dates),
        "first_snapshot_date": snapshot_dates[0] if snapshot_dates else None,
        "last_snapshot_date": snapshot_dates[-1] if snapshot_dates else None,
        "exact_snapshot_coverage_fraction": (
            round(len(exact_snapshot_dates) / trading_days, 4)
            if trading_days else 0.0
        ),
        "walk_forward_snapshot_coverage_fraction": (
            round(len(walk_forward_dates) / trading_days, 4)
            if trading_days else 0.0
        ),
        "snapshot_rows_total": row_count,
        "snapshot_rows_with_eps_estimate": eps_rows,
        "snapshot_rows_with_surprise_history": surprise_rows,
        "eps_estimate": (
            "snapshot-backed when available; None before first snapshot or "
            "for uncovered tickers"
        ),
        "positive_surprise_history": (
            "derived from avg_historical_surprise_pct when snapshot-backed; "
            "None before first snapshot or for uncovered tickers"
        ),
        "confidence_cap_when_missing_snapshot": 0.83,
        "legacy_gap_resolved": has_snapshots,
        "remaining_gap": (
            "coverage/ticker-level sparsity, not an always-None field"
            if has_snapshots else
            "no earnings snapshots available in data_dir"
        ),
        "note": (
            "Do not describe Strategy C as days_to_earnings-only when "
            "snapshot_archive_present is true; use the coverage fields above."
        ),
    }


def build_exit_advisory_shadow_attribution(events, closed_trades):
    """Summarize production advisory exit rules without changing fills."""
    by_rule = {}
    for event in events:
        rule = event.get("rule")
        if not rule:
            continue
        bucket = by_rule.setdefault(rule, {
            "daily_triggers": 0,
            "unique_trades": set(),
            "first_trigger_trades": set(),
            "sample_events": [],
        })
        bucket["daily_triggers"] += 1
        trade_key = event.get("trade_key")
        if trade_key:
            bucket["unique_trades"].add(trade_key)
            if event.get("is_first_for_trade"):
                bucket["first_trigger_trades"].add(trade_key)
        if len(bucket["sample_events"]) < 10:
            bucket["sample_events"].append(event)

    for trade in closed_trades:
        trade_key = trade.get("trade_key")
        for rule in trade.get("exit_advisory_rules_seen", []):
            bucket = by_rule.setdefault(rule, {
                "daily_triggers": 0,
                "unique_trades": set(),
                "first_trigger_trades": set(),
                "sample_events": [],
            })
            outcome = bucket.setdefault("outcome", {
                "closed_trades": 0,
                "wins": 0,
                "pnl": 0.0,
                "exit_reasons": {},
            })
            outcome["closed_trades"] += 1
            pnl = float(trade.get("pnl", 0.0) or 0.0)
            outcome["pnl"] += pnl
            if pnl > 0:
                outcome["wins"] += 1
            exit_reason = trade.get("exit_reason", "unknown")
            outcome["exit_reasons"][exit_reason] = (
                outcome["exit_reasons"].get(exit_reason, 0) + 1
            )
            if trade_key:
                bucket["unique_trades"].add(trade_key)

    serializable = {}
    for rule, bucket in sorted(by_rule.items()):
        outcome = bucket.get("outcome", {
            "closed_trades": 0,
            "wins": 0,
            "pnl": 0.0,
            "exit_reasons": {},
        })
        closed_n = outcome["closed_trades"]
        serializable[rule] = {
            "daily_triggers": bucket["daily_triggers"],
            "unique_trades": len(bucket["unique_trades"]),
            "first_trigger_trades": len(bucket["first_trigger_trades"]),
            "outcome": {
                "closed_trades": closed_n,
                "wins": outcome["wins"],
                "win_rate": round(outcome["wins"] / closed_n, 4)
                if closed_n else None,
                "pnl": round(outcome["pnl"], 2),
                "avg_pnl": round(outcome["pnl"] / closed_n, 2)
                if closed_n else None,
                "exit_reasons": outcome["exit_reasons"],
            },
            "sample_events": bucket["sample_events"],
        }

    return {
        "enabled": True,
        "mode": "shadow_only_no_trade_execution",
        "rules_observed": sorted(serializable.keys()),
        "total_daily_triggers": len(events),
        "by_rule": serializable,
        "notes": [
            "Computed from production position_manager advisory rules using backtest positions and daily close.",
            "No fills, position sizes, stops, targets, or metrics are changed by this attribution.",
            "Use this to choose candidate exit lifecycle experiments; it is not counterfactual PnL.",
        ],
    }


def should_cancel_gap(fill_price, signal_entry, sig=None, today=None, ohlcv_all=None):
    """Return True when the next open is too far above signal entry.

    Extra arguments are accepted so shadow diagnostics can monkeypatch this
    function with context-aware predicates without changing production defaults.
    """
    return (
        classify_entry_open_cancel(
            fill_price,
            signal_entry,
            upside_gap_cancel_pct=CANCEL_GAP_PCT,
            adverse_gap_cancel_pct=None,
        )
        == "gap_cancel"
    )


SIZING_MULTIPLIER_KEYS = (
    "tqs_risk_multiplier_applied",
    "risk_on_unmodified_risk_multiplier_applied",
    "trend_industrials_risk_multiplier_applied",
    "trend_financials_risk_multiplier_applied",
    "financials_sector_leader_risk_multiplier_applied",
    "trend_tech_tight_gap_risk_multiplier_applied",
    "trend_tech_gap_risk_multiplier_applied",
    "trend_tech_near_high_risk_multiplier_applied",
    "trend_tech_dte_risk_multiplier_applied",
    "breakout_industrials_gap_risk_multiplier_applied",
    "breakout_comms_near_high_risk_multiplier_applied",
    "breakout_comms_gap_risk_multiplier_applied",
    "breakout_financials_dte_risk_multiplier_applied",
    "breakout_tech_dte_risk_multiplier_applied",
    "breakout_healthcare_dte_risk_multiplier_applied",
    "trend_healthcare_dte_risk_multiplier_applied",
    "trend_consumer_near_high_dte_risk_multiplier_applied",
    "trend_commodities_near_high_risk_multiplier_applied",
)


def _extract_sizing_multipliers(sizing):
    """Return non-neutral sizing multipliers from a signal sizing payload."""
    if not sizing:
        return {}
    out = {}
    for key in SIZING_MULTIPLIER_KEYS:
        value = sizing.get(key)
        if value is not None and value != 1.0:
            out[key] = value
    return out


def _calendar_days_held(trade):
    try:
        entry = pd.Timestamp(trade.get("entry_date"))
        exit_ = pd.Timestamp(trade.get("exit_date"))
    except Exception:
        return None
    if pd.isna(entry) or pd.isna(exit_):
        return None
    return max(1, int((exit_ - entry).days) + 1)


def _build_capital_efficiency(closed, initial_capital, trading_days,
                              total_pnl, strategy_return_pct, max_positions):
    """Observation-only capital efficiency metrics for comparing alpha ideas."""
    total = len(closed)
    slot_days = sum(
        days for days in (_calendar_days_held(t) for t in closed)
        if days is not None
    )
    max_slot_days = trading_days * max_positions if trading_days and max_positions else 0
    return {
        "return_per_trade": (
            round(strategy_return_pct / total, 6) if total else None
        ),
        "pnl_per_trade_usd": round(total_pnl / total, 2) if total else None,
        "calendar_slot_days": slot_days,
        "avg_calendar_days_held": round(slot_days / total, 2) if total else None,
        "return_per_calendar_slot_day": (
            round(strategy_return_pct / slot_days, 8) if slot_days else None
        ),
        "pnl_per_calendar_slot_day_usd": (
            round(total_pnl / slot_days, 2) if slot_days else None
        ),
        "trade_count_per_100_trading_days": (
            round(total / trading_days * 100, 2) if trading_days else None
        ),
        "gross_slot_day_fraction": (
            round(slot_days / max_slot_days, 4) if max_slot_days else None
        ),
        "initial_capital": round(initial_capital, 2) if initial_capital else None,
        "note": "calendar_slot_days use inclusive calendar days, not trading days.",
    }


def _update_sizing_rule_signal_attribution(acc, signals):
    """Track how often sizing rules touched candidate signals."""
    for sig in signals or []:
        sizing = sig.get("sizing") or {}
        base_risk = sizing.get("base_risk_pct")
        actual_risk = sizing.get("risk_pct")
        for key, multiplier in _extract_sizing_multipliers(sizing).items():
            rec = acc.setdefault(key, {
                "signals_seen": 0,
                "zero_risk_signals": 0,
                "reduced_risk_signals": 0,
                "risk_pct_before_sum": 0.0,
                "risk_pct_after_sum": 0.0,
                "risk_pct_reduced_sum": 0.0,
                "strategies": {},
                "sectors": {},
            })
            rec["signals_seen"] += 1
            if actual_risk == 0:
                rec["zero_risk_signals"] += 1
            elif multiplier < 1.0:
                rec["reduced_risk_signals"] += 1
            if base_risk is not None:
                rec["risk_pct_before_sum"] += base_risk
            if actual_risk is not None:
                rec["risk_pct_after_sum"] += actual_risk
            if base_risk is not None and actual_risk is not None:
                rec["risk_pct_reduced_sum"] += max(0.0, base_risk - actual_risk)
            strategy = sig.get("strategy", "unknown")
            sector = sig.get("sector", "Unknown")
            rec["strategies"][strategy] = rec["strategies"].get(strategy, 0) + 1
            rec["sectors"][sector] = rec["sectors"].get(sector, 0) + 1


def _finalize_sizing_rule_signal_attribution(acc):
    finalized = {}
    for key, rec in sorted((acc or {}).items()):
        signals_seen = rec.get("signals_seen", 0)
        risk_before = rec.get("risk_pct_before_sum", 0.0)
        risk_after = rec.get("risk_pct_after_sum", 0.0)
        finalized[key] = {
            "signals_seen": signals_seen,
            "zero_risk_signals": rec.get("zero_risk_signals", 0),
            "reduced_risk_signals": rec.get("reduced_risk_signals", 0),
            "avg_risk_pct_before": (
                round(risk_before / signals_seen, 6) if signals_seen else None
            ),
            "avg_risk_pct_after": (
                round(risk_after / signals_seen, 6) if signals_seen else None
            ),
            "risk_pct_reduced_sum": round(rec.get("risk_pct_reduced_sum", 0.0), 6),
            "strategies": dict(sorted(rec.get("strategies", {}).items())),
            "sectors": dict(sorted(rec.get("sectors", {}).items())),
        }
    return finalized


def _build_sizing_rule_trade_attribution(closed):
    """Observed outcomes for trades that carried non-neutral sizing rules."""
    acc = {}
    for trade in closed or []:
        for key, multiplier in (trade.get("sizing_multipliers") or {}).items():
            rec = acc.setdefault(key, {
                "trade_count": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl_usd": 0.0,
                "multipliers": {},
            })
            pnl = trade.get("pnl") or 0.0
            rec["trade_count"] += 1
            rec["wins"] += 1 if pnl > 0 else 0
            rec["losses"] += 1 if pnl <= 0 else 0
            rec["total_pnl_usd"] += pnl
            mkey = str(multiplier)
            rec["multipliers"][mkey] = rec["multipliers"].get(mkey, 0) + 1

    finalized = {}
    for key, rec in sorted(acc.items()):
        trade_count = rec["trade_count"]
        finalized[key] = {
            "trade_count": trade_count,
            "wins": rec["wins"],
            "losses": rec["losses"],
            "win_rate": round(rec["wins"] / trade_count, 4) if trade_count else None,
            "total_pnl_usd": round(rec["total_pnl_usd"], 2),
            "avg_pnl_usd": round(rec["total_pnl_usd"] / trade_count, 2) if trade_count else None,
            "multipliers": dict(sorted(rec["multipliers"].items())),
            "note": "Observed outcomes only; zero-risk signals do not become trades.",
        }
    return finalized


def _build_multi_window_robustness(results):
    """Summarize consistency across any list of backtest result dicts."""
    clean = [r for r in (results or []) if r and "error" not in r]
    evs = [r.get("expected_value_score") for r in clean
           if r.get("expected_value_score") is not None]
    returns = [
        (r.get("benchmarks") or {}).get("strategy_total_return_pct")
        for r in clean
        if (r.get("benchmarks") or {}).get("strategy_total_return_pct") is not None
    ]
    sharpes = [r.get("sharpe_daily") for r in clean if r.get("sharpe_daily") is not None]
    drawdowns = [r.get("max_drawdown_pct") for r in clean if r.get("max_drawdown_pct") is not None]

    def _median(xs):
        if not xs:
            return None
        ordered = sorted(xs)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2

    ev_positive = sum(1 for x in evs if x > 0)
    ret_positive = sum(1 for x in returns if x > 0)
    sharpe_positive = sum(1 for x in sharpes if x > 0)
    drawdown_breaks = sum(1 for x in drawdowns if x > 0.20)
    return {
        "windows": len(clean),
        "expected_value_score_positive_windows": ev_positive,
        "return_positive_windows": ret_positive,
        "sharpe_daily_positive_windows": sharpe_positive,
        "drawdown_guardrail_break_windows": drawdown_breaks,
        "expected_value_score_min": round(min(evs), 4) if evs else None,
        "expected_value_score_median": round(_median(evs), 4) if evs else None,
        "expected_value_score_max": round(max(evs), 4) if evs else None,
        "expected_value_score_spread": (
            round(max(evs) - min(evs), 4) if len(evs) >= 2 else None
        ),
        "worst_max_drawdown_pct": round(max(drawdowns), 4) if drawdowns else None,
        "robustness_score": ev_positive + ret_positive + sharpe_positive - drawdown_breaks,
        "note": "Higher score means more windows with positive EV/return/daily Sharpe; no gating verdict.",
    }


def _summarize_entry_decision_events(events):
    """Summarize why post-gate candidates did or did not become positions."""
    reason_counts = {}
    by_date = {}
    skipped = []
    for event in events or []:
        reason = event.get("decision") or "unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        date = event.get("date")
        if date:
            by_date.setdefault(date, {})
            by_date[date][reason] = by_date[date].get(reason, 0) + 1
        if reason != "entered":
            skipped.append(event)

    skipped.sort(
        key=lambda event: (
            event.get("date") or "",
            event.get("candidate_rank")
            if event.get("candidate_rank") is not None else 999999,
            event.get("ticker") or "",
        )
    )

    return {
        "candidate_events": len(events or []),
        "entered_count": reason_counts.get("entered", 0),
        "skipped_count": len(skipped),
        "reason_counts": dict(sorted(reason_counts.items())),
        "by_date": dict(sorted(by_date.items())),
        "sample_skips": skipped[:25],
        "notes": [
            "entry_execution_attribution is measurement-only; it does not change fills or signal ordering.",
            "slot_sliced means the candidate survived all gates but sat beyond available same-day position slots.",
            "gap_cancel and stop_breach_cancel explain candidates that reached next-day fill evaluation but were cancelled by execution safeguards.",
        ],
    }


def _load_saved_quant_signal_tickers(data_dir, date_str):
    """Return saved production quant-signal tickers for a date when present."""
    path = os.path.join(data_dir, f"quant_signals_{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    signals = payload.get("signals")
    if not isinstance(signals, list):
        return []
    tickers = []
    for item in signals:
        if not isinstance(item, dict):
            continue
        ticker = item.get("ticker")
        if isinstance(ticker, str) and ticker.strip():
            tickers.append(ticker.strip().upper())
    return tickers


def _build_news_context_alignment(
    data_dir,
    candidate_dates_covered,
    candidate_tickers_by_date,
    candidate_signal_counts_by_date,
    candidate_days_total,
    candidate_signals_total,
):
    """Audit whether archived-news coverage overlaps saved production candidates."""
    covered_dates = list(candidate_dates_covered or [])
    candidate_tickers_by_date = dict(candidate_tickers_by_date or {})
    candidate_signal_counts_by_date = dict(candidate_signal_counts_by_date or {})

    queue = []
    for date_str in covered_dates:
        backtest_tickers = [
            t.strip().upper()
            for t in candidate_tickers_by_date.get(date_str, [])
            if isinstance(t, str) and t.strip()
        ]
        production_tickers = _load_saved_quant_signal_tickers(data_dir, date_str)
        quant_file_exists = production_tickers is not None
        production_tickers = production_tickers or []
        overlap = [t for t in backtest_tickers if t in set(production_tickers)]

        if not quant_file_exists:
            alignment_status = "production_quant_missing"
        elif not production_tickers:
            alignment_status = "production_quant_empty"
        elif overlap:
            alignment_status = "aligned"
        else:
            alignment_status = "production_quant_mismatch"

        queue.append({
            "date": date_str,
            "candidate_signal_count": int(candidate_signal_counts_by_date.get(date_str, 0) or 0),
            "backtest_candidate_tickers": backtest_tickers,
            "production_quant_tickers": production_tickers,
            "overlap_tickers": overlap,
            "production_quant_exists": quant_file_exists,
            "alignment_status": alignment_status,
        })

    queue.sort(
        key=lambda item: (
            item["alignment_status"] != "aligned",
            -item["candidate_signal_count"],
            item["date"],
        )
    )

    aligned_days = sum(1 for item in queue if item["alignment_status"] == "aligned")
    aligned_signals = sum(len(item["overlap_tickers"]) for item in queue)
    production_quant_empty_days = sum(
        1 for item in queue if item["alignment_status"] == "production_quant_empty"
    )
    production_quant_missing_days = sum(
        1 for item in queue if item["alignment_status"] == "production_quant_missing"
    )
    production_quant_mismatch_days = sum(
        1 for item in queue if item["alignment_status"] == "production_quant_mismatch"
    )

    return {
        "covered_candidate_days": len(queue),
        "aligned_days": aligned_days,
        "aligned_signals": aligned_signals,
        "production_quant_empty_days": production_quant_empty_days,
        "production_quant_missing_days": production_quant_missing_days,
        "production_quant_mismatch_days": production_quant_mismatch_days,
        "production_aligned_candidate_day_fraction_of_total": (
            round(aligned_days / candidate_days_total, 4) if candidate_days_total else 0.0
        ),
        "production_aligned_candidate_day_fraction_of_covered": (
            round(aligned_days / len(queue), 4) if queue else 0.0
        ),
        "production_aligned_candidate_signal_fraction_of_total": (
            round(aligned_signals / candidate_signals_total, 4)
            if candidate_signals_total else 0.0
        ),
        "notes": [
            "aligned means saved production quant_signals for the same date share at least one ticker with the backtest pre-news candidate set.",
            "production_quant_empty means a news archive exists, but the saved production quant_signals file had zero candidates that day.",
            "production_quant_missing means a news archive exists, but no saved production quant_signals file exists for candidate-set comparability.",
            "production_quant_mismatch means both sides had candidates, but none of the saved production tickers overlap the backtest pre-news candidate set.",
            "Use this subset when judging archive-backed news hypotheses; headline archive coverage can overstate usable sample size.",
        ],
        "queue": queue,
    }


def _open_positions_cash_populated():
    """Check whether data/open_positions.json has a non-null cash_usd field.

    Used by BacktestEngine.run() integrity diagnostics. Returning False surfaces
    a known phantom-field condition (CLAUDE3.md §三.2) without mutating any
    decision logic — pure reporting.
    """
    try:
        path = os.path.join(_script_dir, "..", "data", "open_positions.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("cash_usd") is not None
    except Exception:
        return False


class Position:
    """Track a single open backtested position."""

    __slots__ = ("ticker", "entry_price", "entry_open_price", "stop_price",
                 "target_price", "shares", "entry_date", "strategy", "sector",
                 "high_water", "atr", "trailing_active", "target_mult_used",
                 "regime_exit_bucket", "regime_exit_score",
                 "sizing_multipliers", "base_risk_pct", "actual_risk_pct",
                 "original_shares", "addon_done", "addon_count",
                 "addon_shares", "addon_cost", "exit_advisory_rules_seen",
                 "exit_advisory_first_seen", "sleeve", "pilot_decision_id",
                 "pilot_snapshot", "pilot_signal_date")

    def __init__(self, ticker, entry_price, stop_price, target_price,
                 shares, entry_date, strategy, sector="Unknown",
                 entry_open_price=None, atr=None, target_mult_used=None,
                 regime_exit_bucket=None, regime_exit_score=None,
                 sizing_multipliers=None, base_risk_pct=None,
                 actual_risk_pct=None, sleeve="core", pilot_decision_id=None,
                 pilot_snapshot=None, pilot_signal_date=None):
        self.ticker           = ticker
        self.entry_price      = entry_price               # post-slippage fill
        self.entry_open_price = entry_open_price or entry_price
        self.stop_price       = stop_price
        self.target_price     = target_price
        self.shares           = shares
        self.entry_date       = entry_date
        self.strategy         = strategy
        self.sector           = sector
        self.high_water       = entry_price               # tracks highest price seen
        self.atr              = atr or ((entry_price - stop_price) / ATR_STOP_MULT
                                        if stop_price and entry_price > stop_price else None)
        self.trailing_active  = False
        self.target_mult_used = target_mult_used
        self.regime_exit_bucket = regime_exit_bucket
        self.regime_exit_score = regime_exit_score
        self.sizing_multipliers = sizing_multipliers or {}
        self.base_risk_pct = base_risk_pct
        self.actual_risk_pct = actual_risk_pct
        self.original_shares = shares
        self.addon_done = False
        self.addon_count = 0
        self.addon_shares = 0
        self.addon_cost = 0.0
        self.exit_advisory_rules_seen = set()
        self.exit_advisory_first_seen = {}
        self.sleeve = sleeve or "core"
        self.pilot_decision_id = pilot_decision_id
        self.pilot_snapshot = pilot_snapshot
        self.pilot_signal_date = pilot_signal_date


class BacktestEngine:
    """
    Walk-forward backtester using the real signal pipeline.

    Args:
        universe   (list[str]): Ticker symbols to test
        start      (str):       Start date YYYY-MM-DD
        end        (str):       End date YYYY-MM-DD
        config     (dict):      Override any key in DEFAULT_CONFIG
    """

    def __init__(self, universe, start=None, end=None, config=None,
                 replay_llm=False, replay_news=False, data_dir=None,
                 ohlcv_snapshot_path=None, save_ohlcv_snapshot_path=None,
                 include_pilot_sleeve=False):
        self.universe    = universe
        self.config      = {**DEFAULT_CONFIG, **(config or {})}
        self.start       = pd.Timestamp(start) if start else None
        self.end         = pd.Timestamp(end)   if end   else None
        self.replay_llm  = bool(replay_llm)
        self.replay_news = bool(replay_news)
        self.include_pilot_sleeve = bool(include_pilot_sleeve)
        # Default data_dir = repo-root/data (one up from quant/).
        if data_dir is None:
            here = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.normpath(os.path.join(here, "..", "data"))
        self.data_dir    = data_dir
        self.ohlcv_snapshot_path = self._resolve_snapshot_path(ohlcv_snapshot_path)
        self.save_ohlcv_snapshot_path = self._resolve_snapshot_path(save_ohlcv_snapshot_path)
        self._sanitize_proxy_env()
        self._configure_yfinance_cache()
        # P-ERN: load all earnings snapshots once at init so _earnings_dict_for
        # can supplement eps_estimate / avg_historical_surprise_pct for C strategy.
        self._earnings_snapshots = self._load_earnings_snapshots()

    def _pilot_lookup_as_of(self, as_of):
        if not self.include_pilot_sleeve:
            return {}
        try:
            return pilot_records_as_of(str(pd.Timestamp(as_of).date()))
        except Exception as exc:
            logger.warning("Pilot sleeve registry replay unavailable for %s: %s", as_of, exc)
            return {}

    def _pilot_tickers_for_download(self):
        if not self.include_pilot_sleeve:
            return []
        as_of = self.end.date() if self.end is not None else datetime.now().date()
        return sorted(self._pilot_lookup_as_of(as_of))

    def _backtest_data_universe(self):
        return sorted(set(self.universe) | set(self._pilot_tickers_for_download()))

    def _sanitize_proxy_env(self):
        """Backward-compatible wrapper around the shared yfinance bootstrap."""
        configure_yfinance_runtime()

    def _configure_yfinance_cache(self):
        """Backward-compatible wrapper around the shared yfinance bootstrap."""
        configure_yfinance_runtime()

    def _resolve_snapshot_path(self, raw_path):
        """Resolve snapshot paths relative to the current working directory."""
        if not raw_path:
            return None
        return raw_path if os.path.isabs(raw_path) else os.path.abspath(raw_path)

    def _serialize_ohlcv_snapshot(self, ohlcv, download_start, download_end):
        """Convert OHLCV frames to a JSON-friendly payload."""
        payload = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "download_start": str(pd.Timestamp(download_start).date()),
                "download_end": str(pd.Timestamp(download_end).date()),
                "tickers": sorted(ohlcv.keys()),
            },
            "ohlcv": {},
        }
        for ticker, df in ohlcv.items():
            frame = df.copy()
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = frame.columns.get_level_values(0)
            frame = frame.sort_index()
            rows = []
            for idx, row in frame.iterrows():
                rows.append({
                    "Date": str(pd.Timestamp(idx).date()),
                    "Open": float(row["Open"]),
                    "High": float(row["High"]),
                    "Low": float(row["Low"]),
                    "Close": float(row["Close"]),
                    "Volume": float(row["Volume"]),
                })
            payload["ohlcv"][ticker] = rows
        return payload

    def _write_ohlcv_snapshot(self, ohlcv, path, download_start, download_end):
        """Persist a deterministic OHLCV snapshot for later reruns."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = self._serialize_ohlcv_snapshot(ohlcv, download_start, download_end)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Saved OHLCV snapshot -> %s", path)

    def _load_ohlcv_snapshot(self, path):
        """Load OHLCV frames from a previously saved snapshot JSON."""
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        raw = payload.get("ohlcv")
        if not isinstance(raw, dict):
            raise ValueError(f"Snapshot missing 'ohlcv' dict: {path}")

        ohlcv = {}
        for ticker, rows in raw.items():
            frame = pd.DataFrame(rows)
            if frame.empty:
                continue
            frame["Date"] = pd.to_datetime(frame["Date"])
            frame = frame.set_index("Date").sort_index()
            frame.index.name = None
            required = ["Open", "High", "Low", "Close", "Volume"]
            missing = [col for col in required if col not in frame.columns]
            if missing:
                raise ValueError(f"Snapshot {path} missing columns for {ticker}: {missing}")
            ohlcv[ticker] = frame[required]

        logger.info("Loaded OHLCV snapshot <- %s (%d tickers)", path, len(ohlcv))
        return ohlcv

    def _load_earnings_snapshots(self):
        """Load all data/earnings_snapshot_YYYYMMDD.json files (written by run.py P-ERN).

        Returns dict keyed by YYYYMMDD string → {ticker: earnings_data_dict}.
        Silently skips malformed files so missing data never crashes the backtest.
        """
        snaps = {}
        if not os.path.isdir(self.data_dir):
            return snaps
        for fname in os.listdir(self.data_dir):
            if not fname.startswith("earnings_snapshot_") or not fname.endswith(".json"):
                continue
            date_str = fname[len("earnings_snapshot_"):-len(".json")]
            if len(date_str) != 8 or not date_str.isdigit():
                continue
            path = os.path.join(self.data_dir, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                snaps[date_str] = data.get("earnings", {})
            except Exception as e:
                logger.debug(f"earnings snapshot {fname} skipped: {e}")
        if snaps:
            logger.info(f"Loaded {len(snaps)} earnings snapshots: "
                        f"{sorted(snaps)[:3]}{'...' if len(snaps) > 3 else ''}")
        return snaps

    def _download_earnings_calendar(self):
        """Per-ticker sorted list of earnings dates (past + upcoming).

        Used to derive a walk-forward `days_to_earnings` per simulated day —
        without this, the dte<=3 hard block in signal_engine never fires in
        backtest and earnings-window signals leak through (production
        rejected them; backtest accepts them, inflating survival rate).
        """
        import numpy as np
        cal = {}
        for ticker in self._backtest_data_universe():
            try:
                t = yf.Ticker(ticker)
                df = t.get_earnings_dates(limit=20)
                if df is None or df.empty:
                    cal[ticker] = []
                    continue
                # Index is timezone-aware datetime; normalize to date.
                dates = sorted({pd.Timestamp(d).normalize().date()
                                for d in df.index})
                cal[ticker] = dates
            except Exception as e:
                logger.debug(f"{ticker}: earnings calendar unavailable - {e}")
                cal[ticker] = []
        n_with = sum(1 for v in cal.values() if v)
        logger.info(f"Earnings calendar: {n_with}/{len(cal)} tickers populated")
        return cal

    def _earnings_dict_for(self, today, calendar_dates, ticker=None):
        """Build the earnings_data dict feature_layer expects, walked to `today`.

        `days_to_earnings` comes from the historical earnings calendar (always
        reconstructable). `eps_estimate` and `avg_historical_surprise_pct` come
        from the nearest available earnings snapshot written by run.py (P-ERN).
        Without a snapshot, both are None (confidence for C strategy capped at 0.83).
        """
        import numpy as np
        today_date = today.date() if hasattr(today, "date") else today
        future = [d for d in calendar_dates if d > today_date]
        base = {
            "next_earnings_date": None, "days_to_earnings": None,
            "eps_estimate": None, "eps_actual_last": None,
            "historical_surprise_pct": [],
            "avg_historical_surprise_pct": None,
        }
        if not future:
            return base
        nxt = future[0]
        try:
            dte = int(np.busday_count(today_date, nxt))
        except Exception:
            dte = None
        base["next_earnings_date"] = str(nxt)
        base["days_to_earnings"]   = dte

        # P-ERN: supplement with the most recent snapshot on or before today.
        if ticker and self._earnings_snapshots:
            today_str = today_date.strftime("%Y%m%d") if hasattr(today_date, "strftime") else str(today_date).replace("-", "")
            # Find the latest snapshot date that is ≤ today
            candidates = [d for d in self._earnings_snapshots if d <= today_str]
            if candidates:
                snap_date = max(candidates)
                snap = self._earnings_snapshots[snap_date].get(ticker, {})
                if snap.get("eps_estimate") is not None:
                    base["eps_estimate"] = snap["eps_estimate"]
                if snap.get("eps_actual_last") is not None:
                    base["eps_actual_last"] = snap["eps_actual_last"]
                if snap.get("avg_historical_surprise_pct") is not None:
                    base["avg_historical_surprise_pct"] = snap["avg_historical_surprise_pct"]
                if snap.get("historical_surprise_pct"):
                    base["historical_surprise_pct"] = snap["historical_surprise_pct"]
        return base

    def _download_data(self):
        """Download OHLCV for universe + SPY + QQQ."""
        all_tickers = list(set(self._backtest_data_universe() + ["SPY", "QQQ"]))
        lookback = self.config["LOOKBACK_CALENDAR_DAYS"]

        # Determine download range: we need lookback days BEFORE start
        if self.end:
            dl_end = self.end + pd.Timedelta(days=5)  # buffer for next-day fill
        else:
            dl_end = pd.Timestamp.now()

        if self.start:
            dl_start = self.start - pd.Timedelta(days=lookback)
        else:
            dl_start = dl_end - pd.Timedelta(days=lookback + 180)

        if self.ohlcv_snapshot_path:
            if not os.path.exists(self.ohlcv_snapshot_path):
                raise FileNotFoundError(
                    f"OHLCV snapshot not found: {self.ohlcv_snapshot_path}"
                )
            return self._load_ohlcv_snapshot(self.ohlcv_snapshot_path)

        logger.info(f"Downloading {len(all_tickers)} tickers: "
                    f"{dl_start.date()} → {dl_end.date()}")

        ohlcv = {}
        for ticker in all_tickers:
            try:
                df = yf.download(ticker, start=dl_start, end=dl_end,
                                 progress=False)
                if df is not None and not df.empty:
                    # Flatten multi-level columns if present
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    ohlcv[ticker] = df
                    logger.info(f"  {ticker}: {len(df)} rows")
                else:
                    logger.warning(f"  {ticker}: no data")
            except Exception as e:
                logger.warning(f"  {ticker}: download failed — {e}")

        if self.save_ohlcv_snapshot_path and ohlcv:
            self._write_ohlcv_snapshot(
                ohlcv,
                self.save_ohlcv_snapshot_path,
                dl_start,
                dl_end,
            )

        return ohlcv

    def run(self):
        """
        Execute the backtest.

        Returns:
            dict: {total_trades, wins, losses, win_rate, total_pnl, sharpe,
                   max_drawdown_pct, equity_curve, trades, signals_generated,
                   signals_survived, survival_rate}
        """
        from feature_layer    import compute_features
        from signal_engine    import generate_signals, rank_signals_for_allocation
        from risk_engine      import enrich_signals
        from portfolio_engine import (
            compute_portfolio_heat,
            size_signals,
            ROUND_TRIP_COST_PCT,
        )
        from regime           import compute_market_regime
        from fill_model       import (
            apply_entry_fill, apply_stop_fill, apply_target_fill,
            apply_slippage,   SLIPPAGE_BPS_STOP, SLIPPAGE_BPS_TARGET,
        )

        ohlcv_all = self._download_data()
        if not ohlcv_all:
            return {"error": "No data downloaded"}

        earnings_calendar = self._download_earnings_calendar()

        # Build unified trading-day index from SPY
        spy_df = ohlcv_all.get("SPY")
        if spy_df is None or spy_df.empty:
            return {"error": "SPY data unavailable — cannot determine trading days"}

        all_dates = sorted(spy_df.index)
        if self.start:
            sim_dates = [d for d in all_dates if d >= self.start]
        else:
            sim_dates = all_dates[-126:]  # default: last ~6 months
        if self.end:
            sim_dates = [d for d in sim_dates if d <= self.end]

        if len(sim_dates) < 2:
            return {"error": "Insufficient simulation dates"}

        logger.info(f"Simulating {len(sim_dates)} trading days: "
                    f"{sim_dates[0].date()} → {sim_dates[-1].date()}")

        # State
        capital       = self.config["INITIAL_CAPITAL"]
        equity        = capital
        positions     = []          # list[Position]
        closed        = []          # list[dict]
        equity_curve  = []
        total_signals_generated = 0
        total_signals_survived  = 0
        sizing_rule_signal_attribution = {}
        entry_decision_events = []
        pilot_replay_state = {
            "enabled": self.include_pilot_sleeve,
            "sleeve": PILOT_SLEEVE_NAME,
            "eligible_tickers": [],
            "eligible_days": 0,
            "signals_generated": 0,
            "signals_survived": 0,
            "entries": 0,
            "closed_trades": 0,
            "direct_pilot_pnl": 0.0,
            "cash_relative_pnl": 0.0,
            "replacement_value": None,
            "risk_adjusted_replacement_value_avg": None,
            "pending_counterfactual_outcomes": 0,
            "by_ticker": {},
            "decisions": [],
            "notes": [
                "PIT pilot replay is enabled only with --include-pilot-sleeve.",
                "Replay is in-memory and does not write data/pilot_competition_decisions.jsonl.",
            ],
        }
        pilot_eligible_tickers_seen = set()
        pilot_decision_snapshots_by_id = {}
        pilot_outcome_attributions = []

        # LLM replay bookkeeping (§4.2 attribution requirement).
        llm_dates_covered  = []
        llm_dates_missing  = []
        llm_signals_presented = 0
        llm_signals_vetoed    = 0
        llm_signals_passed    = 0
        llm_candidate_days_total   = 0
        llm_candidate_days_covered = 0
        llm_candidate_dates_covered = []
        llm_candidate_dates_missing = []
        llm_candidate_signal_counts_by_date = {}
        llm_candidate_tickers_by_date = {}
        # Per-strategy breakdown: {"trend_long": {"presented": n, "vetoed": m, "passed": p}}
        llm_signals_by_strategy: dict = {}

        # News replay bookkeeping (§6.1 parity gap — news veto).
        # When replay_news=True, T1-negative tickers are vetoed via news_replay.py.
        # When replay_news=False, the lists below track archive availability only.
        news_archive_dates_covered   = []
        news_archive_dates_missing   = []
        news_candidate_dates_covered = []
        news_candidate_dates_missing = []
        news_candidate_signal_counts_by_date = {}
        news_candidate_tickers_by_date = {}
        news_candidate_days_total     = 0
        news_candidate_signals_total  = 0
        news_signals_presented       = 0
        news_signals_vetoed          = 0
        news_signals_passed          = 0

        addon_enabled = bool(self.config.get("ADDON_ENABLED"))
        pending_addons = {}
        addon_events = []
        addon_scheduled_count = 0
        addon_executed_count = 0
        addon_skipped_count = 0
        addon_checkpoint_rejected_count = 0
        partial_reduce_enabled = bool(self.config.get("REPLAY_PARTIAL_REDUCES"))
        pending_partial_reduces = {}
        partial_reduce_events = []
        partial_reduce_scheduled_count = 0
        partial_reduce_executed_count = 0
        partial_reduce_skipped_count = 0
        exit_advisory_shadow_events = []
        scarce_slot_breakout_deferred_count = 0
        scarce_slot_deferred_events = []

        market_context_cache = {}

        def _market_context_for_day(asof_day):
            if asof_day is None:
                return {}
            cache_key = str(pd.Timestamp(asof_day).date())
            if cache_key in market_context_cache:
                return market_context_cache[cache_key]

            regime_ohlcv = {}
            for idx_ticker in ["SPY", "QQQ"]:
                df = ohlcv_all.get(idx_ticker)
                if df is not None:
                    regime_ohlcv[idx_ticker] = df.loc[:asof_day]

            regime_result = compute_market_regime(ohlcv_override=regime_ohlcv)
            market_context = {
                "market_regime": regime_result.get("regime", "UNKNOWN"),
                "spy_10d_return": regime_result.get("indices", {}).get("SPY", {}).get("momentum_10d_pct"),
                "qqq_10d_return": regime_result.get("indices", {}).get("QQQ", {}).get("momentum_10d_pct"),
                "spy_pct_from_ma": regime_result.get("indices", {}).get("SPY", {}).get("pct_from_ma"),
                "qqq_pct_from_ma": regime_result.get("indices", {}).get("QQQ", {}).get("pct_from_ma"),
            }
            market_context_cache[cache_key] = market_context
            return market_context

        def _scalar_price(row, column):
            value = row[column]
            return float(value.item() if hasattr(value, "item") else value)

        def _next_trade_date_for_ticker(ticker, after_day):
            df = ohlcv_all.get(ticker)
            if df is None:
                return None
            for nd in all_dates:
                if nd > after_day and nd in df.index:
                    return nd
            return None

        def _position_heat(pos, price):
            if not pos.stop_price or price <= pos.stop_price:
                return 0.0
            return pos.shares * (price - pos.stop_price)

        def _cap_addon_shares(
                pos,
                raw_open,
                requested_shares,
                current_prices,
                addon_position_cap=None):
            """Respect existing single-position and portfolio heat caps."""
            if requested_shares <= 0 or raw_open <= 0:
                return 0, "no_requested_shares"

            if addon_position_cap is None:
                addon_position_cap = self.config.get("ADDON_MAX_POSITION_PCT")
                if addon_position_cap is None:
                    addon_position_cap = MAX_POSITION_PCT
            max_total_shares = math.floor(equity * addon_position_cap / raw_open)
            cap_room = max_total_shares - pos.shares
            if cap_room <= 0:
                return 0, "position_cap"

            shares = min(requested_shares, cap_room)
            risk_per_share = max(0.0, raw_open - (pos.stop_price or raw_open))
            if risk_per_share <= 0:
                return shares, None

            current_heat_usd = 0.0
            for p in positions:
                px = current_prices.get(p.ticker)
                if px is not None:
                    current_heat_usd += _position_heat(p, px)
            heat_room_usd = max(0.0, equity * MAX_PORTFOLIO_HEAT - current_heat_usd)
            max_heat_shares = math.floor(heat_room_usd / risk_per_share)
            shares = min(shares, max_heat_shares)
            if shares <= 0:
                return 0, "portfolio_heat_cap"
            return shares, None

        def _record_entry_decision(today, sig, decision, slots, candidate_rank, details=None):
            details = details or {}
            entry_decision_events.append({
                "date": str(today.date()) if hasattr(today, "date") else str(today),
                "ticker": (sig.get("ticker") or "").upper(),
                "strategy": sig.get("strategy", "unknown"),
                "decision": decision,
                "candidate_rank": candidate_rank,
                "available_slots_at_entry_loop": slots,
                "details": details,
            })

        def _core_position_count():
            return sum(1 for p in positions if getattr(p, "sleeve", "core") == "core")

        def _open_positions_payload():
            return {
                "positions": [
                    {
                        "ticker": p.ticker,
                        "shares": p.shares,
                        "avg_cost": p.entry_price,
                        "entry_date": (
                            str(p.entry_date.date())
                            if hasattr(p.entry_date, "date")
                            else str(p.entry_date)
                        ),
                        "target_price": p.target_price,
                    }
                    for p in positions
                ]
            }

        def _simulate_counterfactual_trade(cf, signal_day, horizon_day):
            ticker = cf.get("ticker")
            if ticker == "CASH":
                return {
                    "type": cf.get("type"),
                    "ticker": "CASH",
                    "profit_loss": 0.0,
                    "planned_risk": 0.0,
                    "status": "cash_baseline",
                }

            df = ohlcv_all.get(ticker)
            shares = int(cf.get("shares_to_buy") or cf.get("shares") or 0)
            stop = cf.get("stop_price")
            target = cf.get("target_price")
            signal_entry = cf.get("entry_price")
            if df is None or shares <= 0 or not stop or not target or not signal_entry:
                return {
                    "type": cf.get("type"),
                    "ticker": ticker,
                    "profit_loss": None,
                    "planned_risk": cf.get("planned_risk"),
                    "status": "missing_counterfactual_inputs",
                }

            fill_date = None
            fill_price = None
            for nd in [d for d in all_dates if d > signal_day][:3]:
                if nd in df.index:
                    fill_row = df.loc[nd]
                    fill_price = _scalar_price(fill_row, "Open")
                    fill_date = nd
                    break
            if fill_price is None:
                return {
                    "type": cf.get("type"),
                    "ticker": ticker,
                    "profit_loss": None,
                    "planned_risk": cf.get("planned_risk"),
                    "status": "no_future_fill",
                }

            cancel_reason = classify_entry_open_cancel(
                fill_price,
                signal_entry,
                stop_price=stop,
                upside_gap_cancel_pct=CANCEL_GAP_PCT,
                adverse_gap_cancel_pct=self.config.get(
                    "ADVERSE_GAP_CANCEL_PCT",
                    ADVERSE_GAP_CANCEL_PCT,
                ),
            )
            if cancel_reason in {
                "gap_cancel",
                "adverse_gap_down_cancel",
                "stop_breach_cancel",
            }:
                return {
                    "type": cf.get("type"),
                    "ticker": ticker,
                    "profit_loss": 0.0,
                    "planned_risk": cf.get("planned_risk"),
                    "status": cancel_reason,
                    "fill_date": str(fill_date.date()),
                    "fill_price": round(fill_price, 4),
                }

            entry_fill = apply_entry_fill(fill_price)
            planned_risk = cf.get("planned_risk")
            if planned_risk is None and entry_fill > stop:
                planned_risk = round((entry_fill - stop) * shares, 6)

            exit_price = None
            exit_raw_price = None
            exit_reason = None
            exit_date = None
            for day in [d for d in all_dates if fill_date <= d <= horizon_day]:
                if day not in df.index:
                    continue
                row = df.loc[day]
                opn = _scalar_price(row, "Open")
                low = _scalar_price(row, "Low")
                high = _scalar_price(row, "High")
                if low <= stop:
                    exit_raw_price = opn if opn < stop else stop
                    exit_price = apply_stop_fill(opn, stop)
                    exit_reason = "stop"
                    exit_date = day
                    break
                if high >= target:
                    exit_raw_price = opn if opn >= target else target
                    exit_price = apply_target_fill(opn, target)
                    exit_reason = "target"
                    exit_date = day
                    break

            if exit_price is None:
                if horizon_day not in df.index:
                    return {
                        "type": cf.get("type"),
                        "ticker": ticker,
                        "profit_loss": None,
                        "planned_risk": planned_risk,
                        "status": "missing_horizon_price",
                    }
                row = df.loc[horizon_day]
                exit_raw_price = _scalar_price(row, "Close")
                exit_price = apply_slippage(
                    exit_raw_price,
                    SLIPPAGE_BPS_TARGET,
                    "sell",
                )
                exit_reason = "horizon_mark"
                exit_date = horizon_day

            cost = exit_price * ROUND_TRIP_COST_PCT * shares
            pnl = (exit_price - entry_fill) * shares - cost
            return {
                "type": cf.get("type"),
                "ticker": ticker,
                "profit_loss": round(pnl, 2),
                "planned_risk": planned_risk,
                "status": "closed",
                "entry_date": str(fill_date.date()),
                "exit_date": str(exit_date.date()),
                "entry_price": round(entry_fill, 2),
                "exit_price": round(exit_price, 2),
                "exit_reason": exit_reason,
                "shares": shares,
            }

        def _attach_pilot_attribution(pos, trade_record, pnl, exit_day):
            if getattr(pos, "sleeve", "core") != PILOT_SLEEVE_NAME:
                return
            snapshot = pos.pilot_snapshot
            if not snapshot:
                return
            counterfactual_outcomes = [
                _simulate_counterfactual_trade(
                    cf,
                    pos.pilot_signal_date or pos.entry_date,
                    exit_day,
                )
                for cf in snapshot.get("counterfactuals", [])
                if cf.get("ticker") != "CASH"
            ]
            pilot_risk = None
            if pos.entry_price and pos.stop_price and pos.entry_price > pos.stop_price:
                pilot_risk = round((pos.entry_price - pos.stop_price) * pos.original_shares, 6)
            outcome = {
                "decision_id": pos.pilot_decision_id,
                "sleeve": PILOT_SLEEVE_NAME,
                "pilot_ticker": pos.ticker,
                "pilot_pnl": round(pnl, 2),
                "pilot_risk": pilot_risk,
                "pilot_trade": {
                    "ticker": pos.ticker,
                    "strategy": pos.strategy,
                    "entry_date": str(pos.entry_date.date()),
                    "exit_date": str(exit_day.date()),
                    "entry_price": pos.entry_price,
                    "exit_price": trade_record.get("exit_price"),
                    "stop_price": pos.stop_price,
                    "shares": pos.shares,
                    "profit_loss": round(pnl, 2),
                    "planned_risk": pilot_risk,
                },
                "counterfactual_outcomes": counterfactual_outcomes,
            }
            attribution = compute_decision_outcome_attribution(snapshot, outcome)
            trade_record["pilot_attribution"] = attribution
            pilot_outcome_attributions.append(attribution)
            pilot_replay_state["decisions"].append({
                "decision_id": pos.pilot_decision_id,
                "date": str(exit_day.date()) if hasattr(exit_day, "date") else str(exit_day),
                "ticker": pos.ticker,
                "status": "closed",
                "pilot_pnl": round(pnl, 2),
                "replacement_value": attribution.get("replacement_value"),
                "replacement_value_status": attribution.get("replacement_value_status"),
            })

        def _finalize_pilot_replay_state():
            pilot_replay_state["eligible_tickers"] = sorted(pilot_eligible_tickers_seen)
            pilot_replay_state["closed_trades"] = len(pilot_outcome_attributions)

            direct_pnl = round(
                sum(item.get("pilot_pnl") or 0.0 for item in pilot_outcome_attributions),
                2,
            )
            pilot_replay_state["direct_pilot_pnl"] = direct_pnl
            pilot_replay_state["cash_relative_pnl"] = direct_pnl

            complete = [
                item for item in pilot_outcome_attributions
                if item.get("replacement_value_status") == "complete"
            ]
            pilot_replay_state["pending_counterfactual_outcomes"] = (
                len(pilot_outcome_attributions) - len(complete)
            )
            pilot_replay_state["replacement_value"] = (
                round(sum(item.get("replacement_value") or 0.0 for item in complete), 2)
                if complete
                else None
            )
            risk_adjusted_values = [
                item.get("risk_adjusted_replacement_value")
                for item in complete
                if item.get("risk_adjusted_replacement_value") is not None
            ]
            pilot_replay_state["risk_adjusted_replacement_value_avg"] = (
                round(sum(risk_adjusted_values) / len(risk_adjusted_values), 6)
                if risk_adjusted_values
                else None
            )

            by_ticker = {}
            for item in pilot_outcome_attributions:
                ticker = item.get("pilot_ticker") or "UNKNOWN"
                bucket = by_ticker.setdefault(
                    ticker,
                    {
                        "entries": 0,
                        "closed_trades": 0,
                        "direct_pilot_pnl": 0.0,
                        "cash_relative_pnl": 0.0,
                        "complete_replacement_outcomes": 0,
                        "pending_counterfactual_outcomes": 0,
                        "replacement_value": 0.0,
                        "risk_adjusted_replacement_value_sum": 0.0,
                        "risk_adjusted_replacement_value_count": 0,
                    },
                )
                bucket["closed_trades"] += 1
                bucket["direct_pilot_pnl"] += item.get("pilot_pnl") or 0.0
                bucket["cash_relative_pnl"] += item.get("cash_relative_pnl") or 0.0
                if item.get("replacement_value_status") == "complete":
                    bucket["complete_replacement_outcomes"] += 1
                    bucket["replacement_value"] += item.get("replacement_value") or 0.0
                else:
                    bucket["pending_counterfactual_outcomes"] += 1
                if item.get("risk_adjusted_replacement_value") is not None:
                    bucket["risk_adjusted_replacement_value_sum"] += item[
                        "risk_adjusted_replacement_value"
                    ]
                    bucket["risk_adjusted_replacement_value_count"] += 1

            for decision in pilot_replay_state["decisions"]:
                if decision.get("status") != "entered":
                    continue
                ticker = decision.get("ticker") or "UNKNOWN"
                bucket = by_ticker.setdefault(
                    ticker,
                    {
                        "entries": 0,
                        "closed_trades": 0,
                        "direct_pilot_pnl": 0.0,
                        "cash_relative_pnl": 0.0,
                        "complete_replacement_outcomes": 0,
                        "pending_counterfactual_outcomes": 0,
                        "replacement_value": 0.0,
                        "risk_adjusted_replacement_value_sum": 0.0,
                        "risk_adjusted_replacement_value_count": 0,
                    },
                )
                bucket["entries"] += 1

            for bucket in by_ticker.values():
                bucket["direct_pilot_pnl"] = round(bucket["direct_pilot_pnl"], 2)
                bucket["cash_relative_pnl"] = round(bucket["cash_relative_pnl"], 2)
                bucket["replacement_value"] = round(bucket["replacement_value"], 2)
                count = bucket["risk_adjusted_replacement_value_count"]
                bucket["risk_adjusted_replacement_value_avg"] = (
                    round(bucket["risk_adjusted_replacement_value_sum"] / count, 6)
                    if count
                    else None
                )
                bucket.pop("risk_adjusted_replacement_value_sum", None)

            pilot_replay_state["by_ticker"] = by_ticker
            return pilot_replay_state

        def _current_prices_for_positions(today, column):
            prices = {}
            for p in positions:
                df = ohlcv_all.get(p.ticker)
                if df is not None and today in df.index:
                    prices[p.ticker] = _scalar_price(df.loc[today], column)
            return prices

        def _execute_pending_addons(today):
            nonlocal addon_executed_count, addon_skipped_count
            date_key = str(today.date())
            todays_addons = pending_addons.pop(date_key, [])
            if not addon_enabled or not todays_addons:
                return

            current_prices = _current_prices_for_positions(today, "Open")

            for addon in todays_addons:
                pos = next((p for p in positions if p.ticker == addon["ticker"]), None)
                if pos is None:
                    addon_skipped_count += 1
                    addon_events.append({**addon, "status": "skipped_position_closed"})
                    continue

                df = ohlcv_all.get(pos.ticker)
                if df is None or today not in df.index:
                    addon_skipped_count += 1
                    addon_events.append({**addon, "status": "skipped_no_price"})
                    continue

                row = df.loc[today]
                raw_open = _scalar_price(row, "Open")
                requested = addon.get("requested_shares")
                if requested is None:
                    requested = math.floor(
                        pos.original_shares
                        * self.config.get("ADDON_FRACTION_OF_ORIGINAL_SHARES", 0.25)
                    )
                addon_shares, skip_reason = _cap_addon_shares(
                    pos,
                    raw_open,
                    requested,
                    current_prices,
                    addon_position_cap=addon.get("addon_position_cap"),
                )
                if addon_shares <= 0:
                    addon_skipped_count += 1
                    addon_events.append({
                        **addon,
                        "status": "skipped_" + (skip_reason or "zero_shares"),
                        "raw_open": round(raw_open, 4),
                        "requested_shares": requested,
                    })
                    continue

                entry_fill = apply_entry_fill(raw_open)
                old_shares = pos.shares
                new_shares = old_shares + addon_shares
                pos.entry_price = round(
                    ((pos.entry_price * old_shares) + (entry_fill * addon_shares))
                    / new_shares,
                    2,
                )
                pos.entry_open_price = round(
                    ((pos.entry_open_price * old_shares) + (raw_open * addon_shares))
                    / new_shares,
                    4,
                )
                pos.shares = new_shares
                pos.addon_count += 1
                max_addon_count = 2 if self.config.get("SECOND_ADDON_ENABLED") else 1
                pos.addon_done = pos.addon_count >= max_addon_count
                pos.addon_shares += addon_shares
                pos.addon_cost += entry_fill * addon_shares
                pos.high_water = max(pos.high_water, raw_open)
                addon_executed_count += 1
                addon_events.append({
                    **addon,
                    "status": "executed",
                    "raw_open": round(raw_open, 4),
                    "entry_fill": round(entry_fill, 4),
                    "requested_shares": requested,
                    "addon_shares": addon_shares,
                    "addon_number": addon.get("addon_number", pos.addon_count),
                    "new_total_shares": new_shares,
                    "new_avg_entry": pos.entry_price,
                })

        def _record_partial_reduce_trade(pos, shares_to_sell, raw_open, today, action):
            exit_price = apply_slippage(raw_open, SLIPPAGE_BPS_STOP, "sell")
            cost = exit_price * ROUND_TRIP_COST_PCT * shares_to_sell
            pnl = (exit_price - pos.entry_price) * shares_to_sell - cost
            entry_slip = (pos.entry_price - pos.entry_open_price) * shares_to_sell
            exit_slip = (raw_open - exit_price) * shares_to_sell
            pnl_pct_net = (
                (exit_price - pos.entry_price) / pos.entry_price
                - ROUND_TRIP_COST_PCT
            )
            initial_risk_pct = (
                ((pos.entry_price - pos.stop_price) / pos.entry_price)
                if pos.stop_price and pos.entry_price else None
            )
            closed.append({
                "ticker":           pos.ticker,
                "strategy":         pos.strategy,
                "sector":           pos.sector,
                "entry_price":      pos.entry_price,
                "entry_open_price": pos.entry_open_price,
                "stop_price":       pos.stop_price,
                "exit_price":       round(exit_price, 2),
                "exit_raw_price":   round(raw_open, 4),
                "shares":           shares_to_sell,
                "pnl":              round(pnl, 2),
                "pnl_pct_net":      round(pnl_pct_net, 6),
                "initial_risk_pct": round(initial_risk_pct, 6) if initial_risk_pct else None,
                "slippage_cost":    round(entry_slip + exit_slip, 2),
                "target_mult_used": pos.target_mult_used,
                "regime_exit_bucket": pos.regime_exit_bucket,
                "regime_exit_score": pos.regime_exit_score,
                "sizing_multipliers": dict(pos.sizing_multipliers),
                "base_risk_pct":    pos.base_risk_pct,
                "actual_risk_pct":  pos.actual_risk_pct,
                "addon_count":      pos.addon_count,
                "addon_shares":     pos.addon_shares,
                "addon_cost":       round(pos.addon_cost, 2),
                "exit_reason":      action.get("exit_reason", "partial_reduce_trailing_stop"),
                "entry_date":  str(pos.entry_date.date()) if hasattr(pos.entry_date, "date") else str(pos.entry_date),
                "exit_date":   str(today.date()) if hasattr(today, "date") else str(today),
            })
            return pnl, exit_price

        def _execute_pending_partial_reduces(today):
            nonlocal partial_reduce_executed_count, partial_reduce_skipped_count, equity
            date_key = str(today.date())
            todays_reduces = pending_partial_reduces.pop(date_key, [])
            if not partial_reduce_enabled or not todays_reduces:
                return

            for action in todays_reduces:
                pos = next((p for p in positions if p.ticker == action["ticker"]), None)
                if pos is None:
                    partial_reduce_skipped_count += 1
                    partial_reduce_events.append({**action, "status": "skipped_position_closed"})
                    continue

                df = ohlcv_all.get(pos.ticker)
                if df is None or today not in df.index:
                    partial_reduce_skipped_count += 1
                    partial_reduce_events.append({**action, "status": "skipped_no_price"})
                    continue

                row = df.loc[today]
                raw_open = _scalar_price(row, "Open")
                shares_to_sell = min(int(action.get("shares_to_sell") or 0), pos.shares)
                if shares_to_sell <= 0:
                    partial_reduce_skipped_count += 1
                    partial_reduce_events.append({
                        **action,
                        "status": "skipped_zero_shares",
                        "current_shares": pos.shares,
                    })
                    continue

                pnl, exit_price = _record_partial_reduce_trade(
                    pos, shares_to_sell, raw_open, today, action
                )
                equity += pnl
                pos.shares -= shares_to_sell
                partial_reduce_executed_count += 1
                partial_reduce_events.append({
                    **action,
                    "status": "executed",
                    "raw_open": round(raw_open, 4),
                    "exit_price": round(exit_price, 4),
                    "shares_sold": shares_to_sell,
                    "remaining_shares": pos.shares,
                    "realized_pnl": round(pnl, 2),
                })

        def _schedule_partial_reduces(today):
            nonlocal partial_reduce_scheduled_count
            if not partial_reduce_enabled:
                return

            stop_pct = self.config.get(
                "PRODUCTION_TRAILING_STOP_PCT",
                TRAILING_STOP_PCT,
            )
            for pos in positions:
                if getattr(pos, "sleeve", "core") != "core":
                    continue
                if pos.shares <= 0:
                    continue
                df = ohlcv_all.get(pos.ticker)
                if df is None or today not in df.index:
                    continue
                row = df.loc[today]
                high = _scalar_price(row, "High")
                close = _scalar_price(row, "Close")
                pos.high_water = max(pos.high_water, high)
                trailing_stop = production_trailing_stop_price(pos.high_water, stop_pct)
                if trailing_stop is None or close > trailing_stop:
                    continue
                fill_date = _next_trade_date_for_ticker(pos.ticker, today)
                if fill_date is None:
                    continue

                unrealized = (close - pos.entry_price) / pos.entry_price
                triggered_rules = [{"rule": "TRAILING_STOP", "urgency": "HIGH"}]
                reduce_pct = suggested_reduce_pct_for_rules(
                    triggered_rules,
                    unrealized,
                    trailing_partial_reduce_enabled=self.config.get(
                        "TRAILING_PARTIAL_REDUCE_ENABLED",
                        TRAILING_PARTIAL_REDUCE_ENABLED,
                    ),
                )
                shares_to_sell = partial_reduce_shares(pos.shares, reduce_pct)
                if shares_to_sell <= 0:
                    continue

                partial_reduce_scheduled_count += 1
                pending_partial_reduces.setdefault(str(fill_date.date()), []).append({
                    "ticker": pos.ticker,
                    "strategy": pos.strategy,
                    "sector": pos.sector,
                    "decision_mode": "code_trailing_partial_reduce",
                    "trigger_date": str(today.date()),
                    "scheduled_fill_date": str(fill_date.date()),
                    "exit_reason": "partial_reduce_trailing_stop",
                    "triggered_rule": "TRAILING_STOP",
                    "trailing_stop_pct": stop_pct,
                    "high_water": round(pos.high_water, 4),
                    "trailing_stop_price": trailing_stop,
                    "trigger_close": round(close, 4),
                    "unrealized_pnl_pct": round(unrealized, 6),
                    "reduce_pct": reduce_pct,
                    "shares_before": pos.shares,
                    "shares_to_sell": shares_to_sell,
                })

        def _record_exit_advisory_shadow(pos, today, df, close):
            entry_ts = pd.Timestamp(pos.entry_date)
            history = df.loc[(df.index >= entry_ts) & (df.index <= today)]
            if history.empty:
                high_since_entry = max(pos.high_water, close)
                days_held = 0
            else:
                high_since_entry = float(history["High"].max())
                days_held = max(len(history.index) - 1, 0)

            exit_levels = compute_exit_levels(
                pos.entry_price,
                atr=pos.atr,
                override_stop_price=pos.stop_price,
                current_price=close,
                signal_target_price=pos.target_price,
            )
            advisory = evaluate_exit_signals(
                close,
                pos.entry_price,
                exit_levels,
                high_water_mark=high_since_entry,
                legacy_basis=False,
                days_held=days_held,
            )
            trade_key = (
                f"{pos.ticker}:"
                f"{entry_ts.date() if hasattr(entry_ts, 'date') else entry_ts}:"
                f"{pos.entry_price:.4f}"
            )
            for triggered in advisory.get("triggered_rules", []):
                rule = triggered.get("rule")
                if rule not in EXIT_POLICY_SHADOW_RULES:
                    continue
                is_first = rule not in pos.exit_advisory_rules_seen
                if is_first:
                    pos.exit_advisory_first_seen[rule] = str(today.date())
                pos.exit_advisory_rules_seen.add(rule)
                exit_advisory_shadow_events.append({
                    "date": str(today.date()),
                    "ticker": pos.ticker,
                    "strategy": pos.strategy,
                    "sector": pos.sector,
                    "trade_key": trade_key,
                    "rule": rule,
                    "urgency": triggered.get("urgency"),
                    "is_first_for_trade": is_first,
                    "close": round(close, 4),
                    "entry_price": round(pos.entry_price, 4),
                    "unrealized_pct": round(
                        (close - pos.entry_price) / pos.entry_price, 6
                    ) if pos.entry_price else None,
                    "days_held": days_held,
                    "high_since_entry": round(high_since_entry, 4),
                })

        def _schedule_followthrough_addons(today):
            nonlocal addon_scheduled_count, addon_checkpoint_rejected_count
            if not addon_enabled:
                return

            spy_df = ohlcv_all.get("SPY")
            checkpoint_days = int(self.config.get("ADDON_CHECKPOINT_DAYS", 2))
            min_unrealized = self.config.get("ADDON_MIN_UNREALIZED_PCT", 0.02)
            min_rs = self.config.get("ADDON_MIN_RS_VS_SPY", 0.0)
            require_checkpoint_cap_room = bool(
                self.config.get("ADDON_REQUIRE_CHECKPOINT_CAP_ROOM")
            )
            require_improving_followthrough = bool(
                self.config.get("ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH")
            )
            second_addon_enabled = bool(self.config.get("SECOND_ADDON_ENABLED"))
            if spy_df is None:
                return

            for pos in positions:
                if getattr(pos, "sleeve", "core") != "core":
                    continue
                if pos.addon_done:
                    continue
                addon_number = pos.addon_count + 1
                if addon_number == 1:
                    active_checkpoint_days = checkpoint_days
                    active_min_unrealized = min_unrealized
                    active_min_rs = min_rs
                    active_fraction = self.config.get(
                        "ADDON_FRACTION_OF_ORIGINAL_SHARES",
                        0.25,
                    )
                elif second_addon_enabled and addon_number == 2:
                    active_checkpoint_days = int(
                        self.config.get("SECOND_ADDON_CHECKPOINT_DAYS", 5)
                    )
                    active_min_unrealized = self.config.get(
                        "SECOND_ADDON_MIN_UNREALIZED_PCT",
                        0.05,
                    )
                    active_min_rs = self.config.get("SECOND_ADDON_MIN_RS_VS_SPY", 0.0)
                    active_fraction = self.config.get(
                        "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES",
                        0.15,
                    )
                    active_position_cap = self.config.get(
                        "SECOND_ADDON_MAX_POSITION_PCT",
                        self.config.get("ADDON_MAX_POSITION_PCT"),
                    )
                else:
                    continue
                if addon_number == 1:
                    active_position_cap = self.config.get("ADDON_MAX_POSITION_PCT")
                df = ohlcv_all.get(pos.ticker)
                if df is None or today not in df.index:
                    continue
                try:
                    entry_idx = df.index.get_loc(pd.Timestamp(pos.entry_date))
                    today_idx = df.index.get_loc(today)
                    spy_entry_idx = spy_df.index.get_loc(pd.Timestamp(pos.entry_date))
                    spy_today_idx = spy_df.index.get_loc(today)
                except KeyError:
                    continue
                if today_idx - entry_idx != active_checkpoint_days:
                    continue

                close = _scalar_price(df.loc[today], "Close")
                entry_close = _scalar_price(df.iloc[entry_idx], "Close")
                spy_close = _scalar_price(spy_df.iloc[spy_today_idx], "Close")
                spy_entry_close = _scalar_price(spy_df.iloc[spy_entry_idx], "Close")
                if entry_close <= 0 or spy_entry_close <= 0:
                    continue

                unrealized = (close - pos.entry_price) / pos.entry_price
                ticker_ret = (close - entry_close) / entry_close
                spy_ret = (spy_close - spy_entry_close) / spy_entry_close
                rs_vs_spy = ticker_ret - spy_ret
                if unrealized < active_min_unrealized or rs_vs_spy <= active_min_rs:
                    continue

                followthrough_state = {}
                if require_improving_followthrough:
                    if checkpoint_days < 2 or today_idx - 1 < 0 or spy_today_idx - 1 < 0:
                        continue
                    day1_close = _scalar_price(df.iloc[today_idx - 1], "Close")
                    spy_day1_close = _scalar_price(spy_df.iloc[spy_today_idx - 1], "Close")
                    if day1_close <= 0 or spy_day1_close <= 0:
                        continue
                    day1_unrealized = (day1_close - pos.entry_price) / pos.entry_price
                    day1_ticker_ret = (day1_close - entry_close) / entry_close
                    day1_spy_ret = (spy_day1_close - spy_entry_close) / spy_entry_close
                    day1_rs_vs_spy = day1_ticker_ret - day1_spy_ret
                    unrealized_improved = unrealized > day1_unrealized
                    rs_improved = rs_vs_spy > day1_rs_vs_spy
                    followthrough_state = {
                        "day1_unrealized_pct": round(day1_unrealized, 6),
                        "day1_rs_vs_spy": round(day1_rs_vs_spy, 6),
                        "unrealized_improved": unrealized_improved,
                        "rs_improved": rs_improved,
                    }
                    if not (unrealized_improved and rs_improved):
                        addon_checkpoint_rejected_count += 1
                        addon_events.append({
                            "ticker": pos.ticker,
                            "strategy": pos.strategy,
                            "sector": pos.sector,
                            "checkpoint_date": str(today.date()),
                            "checkpoint_days": active_checkpoint_days,
                            "addon_number": addon_number,
                            "unrealized_pct": round(unrealized, 6),
                            "rs_vs_spy": round(rs_vs_spy, 6),
                            "original_shares": pos.original_shares,
                            **followthrough_state,
                            "status": "rejected_checkpoint_not_improving_followthrough",
                        })
                        continue

                requested = math.floor(pos.original_shares * active_fraction)
                checkpoint_candidate = {
                    "ticker": pos.ticker,
                    "strategy": pos.strategy,
                    "sector": pos.sector,
                    "checkpoint_date": str(today.date()),
                    "checkpoint_days": active_checkpoint_days,
                    "addon_number": addon_number,
                    "unrealized_pct": round(unrealized, 6),
                    "rs_vs_spy": round(rs_vs_spy, 6),
                    "original_shares": pos.original_shares,
                    **followthrough_state,
                }
                if require_checkpoint_cap_room:
                    checkpoint_prices = _current_prices_for_positions(today, "Close")
                    checkpoint_shares, skip_reason = _cap_addon_shares(
                        pos,
                        close,
                        requested,
                        checkpoint_prices,
                        addon_position_cap=active_position_cap,
                    )
                    if checkpoint_shares <= 0:
                        addon_checkpoint_rejected_count += 1
                        addon_events.append({
                            **checkpoint_candidate,
                            "status": "rejected_checkpoint_" + (skip_reason or "no_cap_room"),
                            "checkpoint_close": round(close, 4),
                            "requested_shares": requested,
                        })
                        continue

                fill_date = _next_trade_date_for_ticker(pos.ticker, today)
                if fill_date is None:
                    continue
                pos.addon_done = True
                addon_scheduled_count += 1
                pending_addons.setdefault(str(fill_date.date()), []).append({
                    **checkpoint_candidate,
                    "addon_position_cap": active_position_cap,
                    "requested_shares": requested,
                    "scheduled_fill_date": str(fill_date.date()),
                })

        for day_idx, today in enumerate(sim_dates):

            # News-archive presence check (§6.1 measurement instrumentation).
            _today_str = today.strftime("%Y%m%d")
            _news_archive_path = os.path.join(
                self.data_dir, f"clean_trade_news_{_today_str}.json")
            news_archive_present = os.path.exists(_news_archive_path)
            if news_archive_present:
                news_archive_dates_covered.append(_today_str)
            else:
                news_archive_dates_missing.append(_today_str)

            # ── 1. Check exits on today's prices ────────────────────────────
            _execute_pending_addons(today)
            _execute_pending_partial_reduces(today)
            positions = [p for p in positions if p.shares > 0]

            still_open = []
            for pos in positions:
                df = ohlcv_all.get(pos.ticker)
                if df is None or today not in df.index:
                    still_open.append(pos)
                    continue

                row = df.loc[today]
                opn  = float(row["Open"].item()  if hasattr(row["Open"],  "item") else row["Open"])
                low  = float(row["Low"].item()   if hasattr(row["Low"],   "item") else row["Low"])
                high = float(row["High"].item()  if hasattr(row["High"],  "item") else row["High"])
                close = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])

                exit_price    = None      # slippage-adjusted fill
                exit_raw_price = None     # theoretical trigger level (pre-slippage)
                exit_reason   = None

                _record_exit_advisory_shadow(pos, today, df, close)

                # Trailing stop logic: update high_water, check activation,
                # dynamically raise stop if trailing is active.
                trail_trigger = self.config.get("TRAIL_TRIGGER_ATR_MULT", 0)
                trail_offset  = self.config.get("TRAIL_OFFSET_ATR_MULT", 0)
                if trail_trigger > 0 and pos.atr:
                    pos.high_water = max(pos.high_water, high)
                    profit_in_atr = (pos.high_water - pos.entry_price) / pos.atr
                    if profit_in_atr >= trail_trigger:
                        pos.trailing_active = True
                        trail_stop = round(pos.high_water - trail_offset * pos.atr, 2)
                        # Only raise the stop, never lower it
                        if trail_stop > (pos.stop_price or 0):
                            pos.stop_price = trail_stop
                        # Remove fixed target — let the trail run
                        pos.target_price = None

                # Stop hit (gap-fill or intraday) — sell slippage on top.
                if pos.stop_price and low <= pos.stop_price:
                    exit_raw_price = opn if opn < pos.stop_price else pos.stop_price
                    exit_price     = apply_stop_fill(opn, pos.stop_price)
                    exit_reason    = "trailing_stop" if pos.trailing_active else "stop"
                # Target hit — gap-up uses Open (bonus), intraday uses target; slippage on top.
                elif pos.target_price and high >= pos.target_price:
                    exit_raw_price = opn if opn >= pos.target_price else pos.target_price
                    exit_price     = apply_target_fill(opn, pos.target_price)
                    exit_reason    = "target"

                if exit_price is not None:
                    cost = exit_price * ROUND_TRIP_COST_PCT * pos.shares
                    pnl  = (exit_price - pos.entry_price) * pos.shares - cost
                    equity += pnl
                    # Entry-side slippage dollars were already baked into
                    # pos.entry_price at open time, but the raw Open was stored
                    # on Position so we can surface total slippage_cost here.
                    entry_slip = (pos.entry_price - pos.entry_open_price) * pos.shares
                    exit_slip  = (exit_raw_price  - exit_price)           * pos.shares
                    pnl_pct_net = ((exit_price - pos.entry_price) / pos.entry_price
                                   - ROUND_TRIP_COST_PCT)
                    initial_risk_pct = (((pos.entry_price - pos.stop_price) / pos.entry_price)
                                        if pos.stop_price and pos.entry_price else None)
                    trade_record = {
                        "trade_key": (
                            f"{pos.ticker}:"
                            f"{pd.Timestamp(pos.entry_date).date()}:"
                            f"{pos.entry_price:.4f}"
                        ),
                        "ticker":           pos.ticker,
                        "strategy":         pos.strategy,
                        "sector":           pos.sector,
                        "entry_price":      pos.entry_price,
                        "entry_open_price": pos.entry_open_price,        # raw next-day Open
                        "stop_price":       pos.stop_price,
                        "exit_price":       round(exit_price, 2),        # after slippage
                        "exit_raw_price":   round(exit_raw_price, 4),    # pre-slippage trigger
                        "shares":           pos.shares,
                        "pnl":              round(pnl, 2),
                        "pnl_pct_net":      round(pnl_pct_net, 6),
                        "initial_risk_pct": round(initial_risk_pct, 6) if initial_risk_pct else None,
                        "slippage_cost":    round(entry_slip + exit_slip, 2),
                        "target_mult_used": pos.target_mult_used,
                        "regime_exit_bucket": pos.regime_exit_bucket,
                        "regime_exit_score": pos.regime_exit_score,
                        "sizing_multipliers": dict(pos.sizing_multipliers),
                        "base_risk_pct":    pos.base_risk_pct,
                        "actual_risk_pct":  pos.actual_risk_pct,
                        "addon_count":      pos.addon_count,
                        "addon_shares":     pos.addon_shares,
                        "addon_cost":       round(pos.addon_cost, 2),
                        "exit_reason":      exit_reason,
                        "exit_advisory_rules_seen": sorted(pos.exit_advisory_rules_seen),
                        "exit_advisory_first_seen": dict(pos.exit_advisory_first_seen),
                        "entry_date":  str(pos.entry_date.date()) if hasattr(pos.entry_date, "date") else str(pos.entry_date),
                        "exit_date":   str(today.date()) if hasattr(today, "date") else str(today),
                    }
                    if getattr(pos, "sleeve", "core") != "core":
                        trade_record["sleeve"] = pos.sleeve
                        trade_record["pilot_decision_id"] = pos.pilot_decision_id
                        _attach_pilot_attribution(pos, trade_record, pnl, today)
                    closed.append(trade_record)
                else:
                    still_open.append(pos)

            positions = still_open
            _schedule_partial_reduces(today)
            _schedule_followthrough_addons(today)

            # ── 2. Generate signals using the REAL pipeline ─────────────────
            # Core slots are counted separately from pilot sleeve positions.
            pilot_records_today = (
                self._pilot_lookup_as_of(today)
                if self.include_pilot_sleeve
                else {}
            )
            core_slots_full = _core_position_count() >= self.config["MAX_POSITIONS"]
            if core_slots_full and not pilot_records_today:
                equity_curve.append((str(today.date()), round(equity, 2)))
                continue

            # Compute features for each ticker using data up to today
            features_dict = {}
            for ticker in self.universe:
                df = ohlcv_all.get(ticker)
                if df is None:
                    continue
                # Slice up to today (inclusive) — no future data
                data_slice = df.loc[:today]
                if len(data_slice) < 21:
                    continue
                earn = self._earnings_dict_for(
                    today, earnings_calendar.get(ticker, []), ticker=ticker)
                features_dict[ticker] = compute_features(ticker, data_slice, earn)
            pilot_features_dict = {}
            if self.include_pilot_sleeve:
                if pilot_records_today:
                    pilot_replay_state["eligible_days"] += 1
                    pilot_eligible_tickers_seen.update(pilot_records_today)
                for ticker in sorted(pilot_records_today):
                    if ticker in features_dict:
                        pilot_features_dict[ticker] = features_dict[ticker]
                        continue
                    df = ohlcv_all.get(ticker)
                    if df is None:
                        continue
                    data_slice = df.loc[:today]
                    if len(data_slice) < 21:
                        continue
                    earn = self._earnings_dict_for(
                        today,
                        earnings_calendar.get(ticker, []),
                        ticker=ticker,
                    )
                    pilot_features_dict[ticker] = compute_features(
                        ticker,
                        data_slice,
                        earn,
                    )
            all_features_dict = {**features_dict, **pilot_features_dict}

            market_context = _market_context_for_day(today)
            regime_str = market_context.get("market_regime", "UNKNOWN")
            spy_pct = market_context.get("spy_pct_from_ma")
            qqq_pct = market_context.get("qqq_pct_from_ma")

            exit_profile = compute_regime_exit_profile(
                market_context,
                base_target_mult=self.config.get("ATR_TARGET_MULT"),
            )
            atr_target_mult = (
                exit_profile["target_mult"]
                if self.config.get("REGIME_AWARE_EXIT")
                else self.config.get("ATR_TARGET_MULT")
            )

            # Generate signals with explicit strategy selection so alpha experiments
            # can isolate a single sub-strategy without changing signal rules.
            signals = []
            if not core_slots_full:
                signals = generate_signals(
                    features_dict,
                    market_context=market_context,
                    enabled_strategies=self.config.get("ENABLED_STRATEGIES"),
                    breakout_max_pullback_from_52w_high=(
                        self.config.get("BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH")
                    ),
                )
            if self.config.get("BREAKOUT_RANK_BY_52W_HIGH"):
                signals = rank_signals_for_allocation(signals)
            total_signals_generated += len(signals)

            # Enrich with risk parameters
            signals = enrich_signals(signals, all_features_dict,
                                    atr_target_mult=atr_target_mult)
            if self.config.get("REGIME_AWARE_EXIT"):
                for s in signals:
                    s["target_mult_used"] = s.get(
                        "target_mult_used",
                        exit_profile["target_mult"],
                    )
                    s["regime_exit_bucket"] = exit_profile["bucket"]
                    s["regime_exit_score"] = exit_profile["score"]
            signals, entry_filter_audit = filter_entry_signal_candidates(
                signals,
                active_tickers={p.ticker for p in positions if p.ticker},
                market_regime=regime_str,
                spy_pct_from_ma=spy_pct,
                qqq_pct_from_ma=qqq_pct,
                max_per_sector=self.config.get("MAX_PER_SECTOR", MAX_PER_SECTOR),
            )

            risk_pct = risk_pct_for_market_state(
                regime_str,
                spy_pct_from_ma=spy_pct,
                qqq_pct_from_ma=qqq_pct,
            )

            current_prices = {
                ticker: feat["close"]
                for ticker, feat in all_features_dict.items()
                if feat and feat.get("close") is not None
            }
            open_positions = _open_positions_payload()
            portfolio_heat = compute_portfolio_heat(
                open_positions,
                current_prices,
                equity,
                features_dict=all_features_dict,
            )
            if portfolio_heat and not portfolio_heat.get("can_add_new_positions", False):
                signals = []
            else:
                signals = size_signals(
                    signals,
                    equity,
                    risk_pct=risk_pct,
                )
            _update_sizing_rule_signal_attribution(
                sizing_rule_signal_attribution,
                signals,
            )
            total_signals_survived += len(signals)

            # ── 2b. LLM gate replay (optional; off by default). ─────────────
            # When on, closes production/backtest parity for dates where
            # data/llm_prompt_resp_YYYYMMDD.json exists. See llm_replay.py.
            if self.replay_llm:
                from llm_replay import get_llm_decision_for_date, apply_llm_gate
                if signals:
                    _candidate_date_str = today.strftime("%Y%m%d")
                    llm_candidate_days_total += 1
                    llm_candidate_signal_counts_by_date[_candidate_date_str] = len(signals)
                    llm_candidate_tickers_by_date[_candidate_date_str] = [
                        (sig.get("ticker") or "").upper()
                        for sig in signals
                        if isinstance(sig.get("ticker"), str) and sig.get("ticker").strip()
                    ]
                decision = get_llm_decision_for_date(today, self.data_dir)
                if decision["file_present"]:
                    llm_dates_covered.append(decision["date_str"])
                    _pre_gate = list(signals)
                    if _pre_gate:
                        llm_candidate_days_covered += 1
                        llm_candidate_dates_covered.append(decision["date_str"])
                    signals, presented_n, vetoed_n = apply_llm_gate(signals, decision)
                    llm_signals_presented += presented_n
                    llm_signals_vetoed    += vetoed_n
                    llm_signals_passed    += len(signals)
                    # Per-strategy veto breakdown: compare pre/post gate signal lists.
                    _after_tickers = {(s.get("ticker") or "").upper() for s in signals}
                    for _s in _pre_gate:
                        _strat = _s.get("strategy", "unknown")
                        _rec = llm_signals_by_strategy.setdefault(
                            _strat, {"presented": 0, "vetoed": 0, "passed": 0})
                        _rec["presented"] += 1
                        if (_s.get("ticker") or "").upper() in _after_tickers:
                            _rec["passed"] += 1
                        else:
                            _rec["vetoed"] += 1
                else:
                    llm_dates_missing.append(decision["date_str"])
                    if signals:
                        llm_candidate_dates_missing.append(decision["date_str"])

            # Candidate-level archived-news coverage should only count real
            # pre-news candidates, not all trading days.
            if signals:
                news_candidate_days_total += 1
                news_candidate_signals_total += len(signals)
                news_candidate_signal_counts_by_date[_today_str] = len(signals)
                news_candidate_tickers_by_date[_today_str] = [
                    str(s.get("ticker")).strip().upper()
                    for s in signals
                    if isinstance(s.get("ticker"), str) and s.get("ticker").strip()
                ]
                if news_archive_present:
                    news_candidate_dates_covered.append(_today_str)
                else:
                    news_candidate_dates_missing.append(_today_str)

            # ── 2c. News T1-negative gate (optional; off by default). ────────
            # When on, vetoes signals for tickers with T1-negative headlines
            # in data/clean_trade_news_YYYYMMDD.json. Closes §6.1 parity gap
            # for dates where the archive exists. See news_replay.py.
            if self.replay_news:
                from news_replay import get_news_for_date, apply_news_gate
                news_dec = get_news_for_date(today, self.data_dir)
                if news_dec["file_present"]:
                    signals, presented_n, vetoed_n = apply_news_gate(signals, news_dec)
                    news_signals_presented += presented_n
                    news_signals_vetoed    += vetoed_n
                    news_signals_passed    += len(signals)

            pilot_signals = []
            if self.include_pilot_sleeve and pilot_records_today and pilot_features_dict:
                pilot_signals = generate_signals(
                    pilot_features_dict,
                    market_context=market_context,
                    enabled_strategies=self.config.get("ENABLED_STRATEGIES"),
                    breakout_max_pullback_from_52w_high=(
                        self.config.get("BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH")
                    ),
                )
                pilot_replay_state["signals_generated"] += len(pilot_signals)
                if self.config.get("BREAKOUT_RANK_BY_52W_HIGH"):
                    pilot_signals = rank_signals_for_allocation(pilot_signals)
                pilot_signals = enrich_signals(
                    pilot_signals,
                    all_features_dict,
                    atr_target_mult=atr_target_mult,
                )
                if self.config.get("REGIME_AWARE_EXIT"):
                    for s in pilot_signals:
                        s["target_mult_used"] = s.get(
                            "target_mult_used",
                            exit_profile["target_mult"],
                        )
                        s["regime_exit_bucket"] = exit_profile["bucket"]
                        s["regime_exit_score"] = exit_profile["score"]
                pilot_signals = mark_pilot_signals(
                    pilot_signals,
                    pilot_records_today,
                    metadata=pilot_governance_metadata(),
                )
                pilot_signals, _pilot_entry_filter_audit = filter_entry_signal_candidates(
                    pilot_signals,
                    active_tickers={p.ticker for p in positions if p.ticker},
                    market_regime=regime_str,
                    spy_pct_from_ma=spy_pct,
                    qqq_pct_from_ma=qqq_pct,
                    max_per_sector=self.config.get("MAX_PER_SECTOR", MAX_PER_SECTOR),
                )
                if portfolio_heat and not portfolio_heat.get("can_add_new_positions", False):
                    pilot_signals = []
                else:
                    pilot_signals = size_signals(
                        pilot_signals,
                        equity,
                        risk_pct=risk_pct,
                    )
                pilot_signals = apply_pilot_sizing_policy(
                    pilot_signals,
                    pilot_records_today,
                )
                pilot_replay_state["signals_survived"] += len(
                    [
                        sig for sig in pilot_signals
                        if (sig.get("sizing") or {}).get("shares_to_buy", 0) > 0
                    ]
                )

            # ── 3. Enter positions at next-day open ─────────────────────────
            signals, entry_plan = plan_entry_candidates(
                signals,
                None,
                market_context={
                    "spy_pct_from_ma": spy_pct,
                    "qqq_pct_from_ma": qqq_pct,
                },
                max_positions=self.config["MAX_POSITIONS"],
                defer_breakout_when_slots_lte=self.config.get(
                    "DEFER_BREAKOUT_WHEN_SLOTS_LTE"
                ),
                defer_breakout_max_min_index_pct_from_ma=self.config.get(
                    "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA"
                ),
                active_positions_count=_core_position_count(),
            )
            pilot_entry_plan = None
            pilot_decision_snapshots = []
            if self.include_pilot_sleeve and pilot_signals:
                pilot_signals, pilot_entry_plan = select_pilot_entry_candidates(
                    pilot_signals,
                    pilot_records_today,
                    open_positions=_open_positions_payload(),
                )
                pilot_decision_snapshots = build_counterfactual_snapshots(
                    pilot_signals,
                    core_signals=signals,
                    as_of=str(today.date()),
                    market_context=market_context,
                    portfolio_heat=portfolio_heat,
                    metadata=pilot_governance_metadata(),
                )
                for sig, snapshot in zip(pilot_signals, pilot_decision_snapshots):
                    pilot_decision_snapshots_by_id[snapshot["decision_id"]] = snapshot
                    sig.setdefault("pilot_sleeve", {})["decision_id"] = snapshot["decision_id"]
                    pilot_replay_state["decisions"].append(
                        {
                            "decision_id": snapshot["decision_id"],
                            "date": str(today.date()),
                            "ticker": snapshot.get("pilot_ticker"),
                            "status": "candidate_snapshot",
                            "counterfactuals": snapshot.get("counterfactuals", []),
                        }
                    )
            slots = entry_plan["available_slots"]
            for deferred in entry_plan["deferred_breakout_signals"]:
                scarce_slot_breakout_deferred_count += 1
                event = {
                    **deferred,
                    "date": str(today.date()) if hasattr(today, "date") else str(today),
                    "ticker": (deferred.get("ticker") or "").upper(),
                    "strategy": deferred.get("strategy", "unknown"),
                }
                scarce_slot_deferred_events.append(event)
                _record_entry_decision(
                    today,
                    deferred,
                    "scarce_slot_breakout_deferred",
                    slots,
                    None,
                    {
                        "active_positions": len(positions),
                        "defer_breakout_slots_lte": entry_plan.get(
                            "defer_breakout_when_slots_lte"
                        ),
                        "defer_breakout_max_min_index_pct_from_ma": entry_plan.get(
                            "defer_breakout_max_min_index_pct_from_ma"
                        ),
                        "min_index_pct_from_ma": entry_plan.get("min_index_pct_from_ma"),
                    },
                )
            for rank, sig in enumerate(
                    entry_plan["slot_sliced_signals"], start=slots + 1):
                _record_entry_decision(
                    today,
                    sig,
                    "slot_sliced",
                    slots,
                    rank,
                    {"signal_count": entry_plan.get("signals_after_deferral")},
                )
            for rank, sig in enumerate(signals, start=1):
                ticker = sig["ticker"]
                # Skip if already holding
                if any(p.ticker == ticker for p in positions):
                    _record_entry_decision(today, sig, "already_holding", slots, rank)
                    continue

                sizing = sig.get("sizing")
                if not sizing or not sizing.get("shares_to_buy"):
                    _record_entry_decision(
                        today,
                        sig,
                        "no_shares",
                        slots,
                        rank,
                        {
                            "has_sizing": bool(sizing),
                            "shares_to_buy": (sizing or {}).get("shares_to_buy"),
                            "risk_pct_before": (sizing or {}).get("risk_pct_before"),
                            "risk_pct_after": (sizing or {}).get("risk_pct_after"),
                            "risk_multipliers": _extract_sizing_multipliers(sizing),
                        },
                    )
                    continue

                shares = sizing["shares_to_buy"]
                stop   = sig.get("stop_price")
                target = sig.get("target_price")

                if not stop or not target:
                    _record_entry_decision(
                        today,
                        sig,
                        "missing_stop_or_target",
                        slots,
                        rank,
                        {"has_stop": bool(stop), "has_target": bool(target)},
                    )
                    continue

                # Fill at next-day open
                df = ohlcv_all.get(ticker)
                if df is None:
                    _record_entry_decision(today, sig, "missing_ohlcv", slots, rank)
                    continue

                future_dates = [d for d in all_dates if d > today]
                fill_price = None
                fill_date  = None
                for nd in future_dates[:3]:  # look ahead up to 3 days for fill
                    if nd in df.index:
                        fill_row = df.loc[nd]
                        fill_price = float(
                            fill_row["Open"].item()
                            if hasattr(fill_row["Open"], "item")
                            else fill_row["Open"]
                        )
                        fill_date = nd
                        break

                if fill_price is None:
                    _record_entry_decision(today, sig, "no_future_fill", slots, rank)
                    continue

                # Cancel if gap too large (> CANCEL_GAP_PCT above signal entry).
                # The gap check uses the RAW Open (not slippage-adjusted) so the
                # cancel boundary is determined by market conditions, not by our
                # own execution-cost assumptions.
                signal_entry = sig.get("entry_price", fill_price)
                cancel_reason = classify_entry_open_cancel(
                    fill_price,
                    signal_entry,
                    stop_price=stop,
                    upside_gap_cancel_pct=CANCEL_GAP_PCT,
                    adverse_gap_cancel_pct=self.config.get(
                        "ADVERSE_GAP_CANCEL_PCT",
                        ADVERSE_GAP_CANCEL_PCT,
                    ),
                )
                if cancel_reason in {"gap_cancel", "adverse_gap_down_cancel"}:
                    _record_entry_decision(
                        today,
                        sig,
                        cancel_reason,
                        slots,
                        rank,
                        {
                            "fill_date": str(fill_date.date()) if hasattr(fill_date, "date") else str(fill_date),
                            "fill_price": round(fill_price, 4),
                            "signal_entry": round(float(signal_entry), 4) if signal_entry else None,
                            "cancel_gap_pct": CANCEL_GAP_PCT,
                            "adverse_gap_cancel_pct": self.config.get(
                                "ADVERSE_GAP_CANCEL_PCT",
                                ADVERSE_GAP_CANCEL_PCT,
                            ),
                        },
                    )
                    continue

                # Symmetric cancel: if overnight gap-down pushes the fill at or below
                # the pre-computed stop, the position is already stopped-out on day 0.
                # No valid R:R remains — skip the entry entirely.
                if cancel_reason == "stop_breach_cancel":
                    _record_entry_decision(
                        today,
                        sig,
                        "stop_breach_cancel",
                        slots,
                        rank,
                        {
                            "fill_date": str(fill_date.date()) if hasattr(fill_date, "date") else str(fill_date),
                            "fill_price": round(fill_price, 4),
                            "stop_price": round(float(stop), 4) if stop else None,
                        },
                    )
                    continue

                entry_fill = apply_entry_fill(fill_price)   # buy-side slippage
                sizing = sig.get("sizing") or {}
                positions.append(Position(
                    ticker=ticker,
                    entry_price=round(entry_fill, 2),
                    entry_open_price=round(fill_price, 4),  # raw next-day Open
                    stop_price=stop,
                    target_price=target,
                    shares=shares,
                    entry_date=fill_date,
                    strategy=sig.get("strategy", "unknown"),
                    sector=sig.get("sector", "Unknown"),
                    target_mult_used=sig.get("target_mult_used"),
                    regime_exit_bucket=sig.get("regime_exit_bucket"),
                    regime_exit_score=sig.get("regime_exit_score"),
                    sizing_multipliers=_extract_sizing_multipliers(sizing),
                    base_risk_pct=sizing.get("base_risk_pct"),
                    actual_risk_pct=sizing.get("risk_pct"),
                ))
                _record_entry_decision(
                    today,
                    sig,
                    "entered",
                    slots,
                    rank,
                    {
                        "fill_date": str(fill_date.date()) if hasattr(fill_date, "date") else str(fill_date),
                        "fill_price": round(fill_price, 4),
                        "shares": shares,
                    },
                )

            for rank, sig in enumerate(pilot_signals, start=1):
                ticker = sig["ticker"]
                snapshot = (
                    pilot_decision_snapshots[rank - 1]
                    if rank - 1 < len(pilot_decision_snapshots)
                    else None
                )
                decision_id = (snapshot or {}).get("decision_id")
                sizing = sig.get("sizing")
                if any(
                    p.ticker == ticker and getattr(p, "sleeve", "core") == PILOT_SLEEVE_NAME
                    for p in positions
                ):
                    pilot_replay_state["decisions"].append({
                        "decision_id": decision_id,
                        "date": str(today.date()),
                        "ticker": ticker,
                        "status": "already_holding_pilot",
                    })
                    continue
                if not sizing or not sizing.get("shares_to_buy"):
                    pilot_replay_state["decisions"].append({
                        "decision_id": decision_id,
                        "date": str(today.date()),
                        "ticker": ticker,
                        "status": "no_shares",
                    })
                    continue

                shares = sizing["shares_to_buy"]
                stop = sig.get("stop_price")
                target = sig.get("target_price")
                if not stop or not target:
                    pilot_replay_state["decisions"].append({
                        "decision_id": decision_id,
                        "date": str(today.date()),
                        "ticker": ticker,
                        "status": "missing_stop_or_target",
                    })
                    continue

                df = ohlcv_all.get(ticker)
                if df is None:
                    pilot_replay_state["decisions"].append({
                        "decision_id": decision_id,
                        "date": str(today.date()),
                        "ticker": ticker,
                        "status": "missing_ohlcv",
                    })
                    continue

                fill_price = None
                fill_date = None
                for nd in [d for d in all_dates if d > today][:3]:
                    if nd in df.index:
                        fill_row = df.loc[nd]
                        fill_price = _scalar_price(fill_row, "Open")
                        fill_date = nd
                        break
                if fill_price is None:
                    pilot_replay_state["decisions"].append({
                        "decision_id": decision_id,
                        "date": str(today.date()),
                        "ticker": ticker,
                        "status": "no_future_fill",
                    })
                    continue

                signal_entry = sig.get("entry_price", fill_price)
                cancel_reason = classify_entry_open_cancel(
                    fill_price,
                    signal_entry,
                    stop_price=stop,
                    upside_gap_cancel_pct=CANCEL_GAP_PCT,
                    adverse_gap_cancel_pct=self.config.get(
                        "ADVERSE_GAP_CANCEL_PCT",
                        ADVERSE_GAP_CANCEL_PCT,
                    ),
                )
                if cancel_reason in {
                    "gap_cancel",
                    "adverse_gap_down_cancel",
                    "stop_breach_cancel",
                }:
                    pilot_replay_state["decisions"].append({
                        "decision_id": decision_id,
                        "date": str(today.date()),
                        "ticker": ticker,
                        "status": cancel_reason,
                        "fill_date": str(fill_date.date()),
                        "fill_price": round(fill_price, 4),
                    })
                    continue

                entry_fill = apply_entry_fill(fill_price)
                positions.append(Position(
                    ticker=ticker,
                    entry_price=round(entry_fill, 2),
                    entry_open_price=round(fill_price, 4),
                    stop_price=stop,
                    target_price=target,
                    shares=shares,
                    entry_date=fill_date,
                    strategy=sig.get("strategy", "unknown"),
                    sector=sig.get("sector", "Unknown"),
                    target_mult_used=sig.get("target_mult_used"),
                    regime_exit_bucket=sig.get("regime_exit_bucket"),
                    regime_exit_score=sig.get("regime_exit_score"),
                    sizing_multipliers=_extract_sizing_multipliers(sizing),
                    base_risk_pct=sizing.get("base_risk_pct"),
                    actual_risk_pct=sizing.get("risk_pct"),
                    sleeve=PILOT_SLEEVE_NAME,
                    pilot_decision_id=decision_id,
                    pilot_snapshot=snapshot,
                    pilot_signal_date=today,
                ))
                pilot_replay_state["entries"] += 1
                pilot_replay_state["decisions"].append({
                    "decision_id": decision_id,
                    "date": str(today.date()),
                    "ticker": ticker,
                    "status": "entered",
                    "fill_date": str(fill_date.date()),
                    "fill_price": round(fill_price, 4),
                    "shares": shares,
                })

            # Mark-to-market equity
            mtm = capital
            for t in closed:
                mtm += t["pnl"]  # realized
            for pos in positions:
                df = ohlcv_all.get(pos.ticker)
                if df is not None and today in df.index:
                    row = df.loc[today]
                    cls = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
                    mtm += (cls - pos.entry_price) * pos.shares
                # If no price, unrealized = 0

            equity_curve.append((str(today.date()), round(mtm, 2)))

        # ── Force-close remaining positions at last day's close ─────────────
        last_day = sim_dates[-1]
        for pos in positions:
            df = ohlcv_all.get(pos.ticker)
            if df is not None and last_day in df.index:
                row = df.loc[last_day]
                raw_close  = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
                # Use target-side slippage budget (5 bps) — this is a mark-to-market
                # unwind, not an adverse stop, so the stop-impact model would be
                # too pessimistic.
                exit_price = apply_slippage(raw_close, SLIPPAGE_BPS_TARGET, "sell")
                exit_raw_price = raw_close
            else:
                exit_price = pos.entry_price     # flat — no price data
                exit_raw_price = pos.entry_price

            cost = exit_price * ROUND_TRIP_COST_PCT * pos.shares
            pnl  = (exit_price - pos.entry_price) * pos.shares - cost
            equity += pnl
            entry_slip = (pos.entry_price - pos.entry_open_price) * pos.shares
            exit_slip  = (exit_raw_price  - exit_price)           * pos.shares
            pnl_pct_net = ((exit_price - pos.entry_price) / pos.entry_price
                           - ROUND_TRIP_COST_PCT)
            initial_risk_pct = (((pos.entry_price - pos.stop_price) / pos.entry_price)
                                if pos.stop_price and pos.entry_price else None)
            trade_record = {
                "trade_key": (
                    f"{pos.ticker}:"
                    f"{pd.Timestamp(pos.entry_date).date()}:"
                    f"{pos.entry_price:.4f}"
                ),
                "ticker":           pos.ticker,
                "strategy":         pos.strategy,
                "sector":           pos.sector,
                "entry_price":      pos.entry_price,
                "entry_open_price": pos.entry_open_price,
                "stop_price":       pos.stop_price,
                "exit_price":       round(exit_price, 2),
                "exit_raw_price":   round(exit_raw_price, 4),
                "shares":           pos.shares,
                "pnl":              round(pnl, 2),
                "pnl_pct_net":      round(pnl_pct_net, 6),
                "initial_risk_pct": round(initial_risk_pct, 6) if initial_risk_pct else None,
                "slippage_cost":    round(entry_slip + exit_slip, 2),
                "target_mult_used": pos.target_mult_used,
                "regime_exit_bucket": pos.regime_exit_bucket,
                "regime_exit_score": pos.regime_exit_score,
                "sizing_multipliers": dict(pos.sizing_multipliers),
                "base_risk_pct":    pos.base_risk_pct,
                "actual_risk_pct":  pos.actual_risk_pct,
                "addon_count":      pos.addon_count,
                "addon_shares":     pos.addon_shares,
                "addon_cost":       round(pos.addon_cost, 2),
                "exit_reason":      "end_of_backtest",
                "exit_advisory_rules_seen": sorted(pos.exit_advisory_rules_seen),
                "exit_advisory_first_seen": dict(pos.exit_advisory_first_seen),
                "entry_date":  str(pos.entry_date.date()) if hasattr(pos.entry_date, "date") else str(pos.entry_date),
                "exit_date":   str(last_day.date()),
            }
            if getattr(pos, "sleeve", "core") != "core":
                trade_record["sleeve"] = pos.sleeve
                trade_record["pilot_decision_id"] = pos.pilot_decision_id
                _attach_pilot_attribution(pos, trade_record, pnl, last_day)
            closed.append(trade_record)

        # ── Compute metrics ─────────────────────────────────────────────────
        wins   = [t for t in closed if t["pnl"] > 0]
        losses = [t for t in closed if t["pnl"] <= 0]
        total  = len(closed)

        # Max drawdown from equity curve
        peak   = 0.0
        max_dd = 0.0
        for _, eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # LEGACY Sharpe: per-trade P&L × sqrt(30). Kept for historical
        # comparability against prior backtest_results_*.json files.
        # Known issues: dollar-denominated (not %), hand-picked sqrt(30) annualization,
        # no "flat day" dilution from equity curve. See CLAUDE3.md iteration v2.
        pnl_series = [t["pnl"] for t in closed]
        if len(pnl_series) >= 2:
            mean_pnl = sum(pnl_series) / len(pnl_series)
            var_pnl  = sum((x - mean_pnl) ** 2 for x in pnl_series) / (len(pnl_series) - 1)
            std_pnl  = math.sqrt(var_pnl) if var_pnl > 0 else 0
            sharpe_legacy = round((mean_pnl / std_pnl) * math.sqrt(30), 2) if std_pnl > 0 else None
        else:
            sharpe_legacy = None

        # DAILY Sharpe: equity-curve-based, annualized with sqrt(252).
        # Additive measurement — does NOT enter compute_convergence (that still
        # reads `sharpe`). This number is for humans to read alongside the
        # legacy value and form a trust verdict.
        equity_series = [eq for _, eq in equity_curve]
        sharpe_daily = None
        daily_returns = []
        if len(equity_series) >= 2:
            for i in range(1, len(equity_series)):
                prev = equity_series[i - 1]
                if prev > 0:
                    daily_returns.append((equity_series[i] / prev) - 1)
            if len(daily_returns) >= 2:
                mean_r = sum(daily_returns) / len(daily_returns)
                var_r  = sum((x - mean_r) ** 2 for x in daily_returns) / (len(daily_returns) - 1)
                std_r  = math.sqrt(var_r) if var_r > 0 else 0
                sharpe_daily = round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else None

        # Backwards-compatible: convergence.py + downstream readers continue to
        # use `sharpe` (legacy). `sharpe_daily` sits alongside for auditing.
        sharpe = sharpe_legacy

        survival_rate = (round(total_signals_survived / total_signals_generated, 4)
                         if total_signals_generated > 0 else 0)

        pnl_pct_series = [t.get("pnl_pct_net") for t in closed
                          if t.get("pnl_pct_net") is not None]
        worst_trade_pct = round(min(pnl_pct_series), 6) if pnl_pct_series else None

        max_consecutive_losses = 0
        current_loss_streak = 0
        for trade in closed:
            pnl_pct = trade.get("pnl_pct_net")
            if pnl_pct is not None and pnl_pct < 0:
                current_loss_streak += 1
                max_consecutive_losses = max(max_consecutive_losses, current_loss_streak)
            else:
                current_loss_streak = 0

        losses_abs = sorted(
            [-t["pnl"] for t in closed if t.get("pnl") is not None and t["pnl"] < 0],
            reverse=True,
        )
        total_loss_abs = sum(losses_abs)
        if total_loss_abs > 0:
            tail_count = max(1, math.ceil(len(losses_abs) * 0.2))
            tail_loss_share = round(sum(losses_abs[:tail_count]) / total_loss_abs, 4)
        else:
            tail_loss_share = None

        from strategy_attribution import aggregate_by_strategy
        by_strategy = aggregate_by_strategy([
            {**t, "pnl_usd": t["pnl"]} for t in closed
        ])
        total_pnl = sum(t["pnl"] for t in closed)

        # ── Benchmarks: SPY / QQQ buy-and-hold over the same window ──
        # The strategy's value is whatever it adds on top of free index exposure;
        # without this comparison a 20% return is impossible to evaluate.
        def _buy_hold(df, start_d, end_d):
            try:
                sliced = df.loc[start_d:end_d]
            except Exception:
                return None
            if sliced is None or len(sliced) < 2:
                return None
            try:
                return float(sliced["Close"].iloc[-1] / sliced["Close"].iloc[0] - 1)
            except Exception:
                return None

        spy_ret = _buy_hold(ohlcv_all.get("SPY"), sim_dates[0], sim_dates[-1])
        qqq_ret = _buy_hold(ohlcv_all.get("QQQ"), sim_dates[0], sim_dates[-1])
        strat_ret = total_pnl / self.config["INITIAL_CAPITAL"]
        benchmarks = {
            "spy_buy_hold_return_pct":   round(spy_ret, 4) if spy_ret is not None else None,
            "qqq_buy_hold_return_pct":   round(qqq_ret, 4) if qqq_ret is not None else None,
            "strategy_total_return_pct": round(strat_ret, 4),
            "strategy_vs_spy_pct":       (round(strat_ret - spy_ret, 4)
                                          if spy_ret is not None else None),
            "strategy_vs_qqq_pct":       (round(strat_ret - qqq_ret, 4)
                                          if qqq_ret is not None else None),
        }

        # Equity-curve integrity — guard against "right formula, wrong inputs".
        # `sharpe_daily` is only trustworthy if the equity curve is not mostly
        # flat (which would give an artificially low std denominator).
        EQUITY_FLAT_EPS = 1e-9
        equity_flat_days = sum(1 for r in daily_returns if abs(r) < EQUITY_FLAT_EPS)
        open_positions_cash_populated = _open_positions_cash_populated()
        equity_curve_integrity = {
            "cash_field_present_in_open_positions": open_positions_cash_populated,
            "risk_rules_enforced_in_backtest":      True,  # synthetic stop_price
            "equity_curve_len":                     len(equity_series),
            "trading_days":                         len(sim_dates),
            "equity_flat_days":                     equity_flat_days,
            "equity_flat_fraction": (round(equity_flat_days / len(daily_returns), 4)
                                     if daily_returns else None),
            "daily_returns_count":                  len(daily_returns),
        }

        # Structured disclosure of known measurement biases. Does NOT enter
        # compute_convergence — pure audit surface.
        trading_days_n  = len(sim_dates)
        llm_covered_n   = len(llm_dates_covered)
        llm_missing_n   = len(llm_dates_missing)
        coverage_frac   = (round(llm_covered_n / trading_days_n, 4)
                           if trading_days_n else 0.0)
        llm_candidate_signal_coverage_frac = (
            round(llm_signals_presented / total_signals_survived, 4)
            if total_signals_survived else 0.0
        )
        llm_candidate_day_coverage_frac = (
            round(llm_candidate_days_covered / llm_candidate_days_total, 4)
            if llm_candidate_days_total else 0.0
        )

        # News-archive coverage metrics.
        news_archive_covered_n = len(news_archive_dates_covered)
        news_archive_missing_n = len(news_archive_dates_missing)
        news_archive_coverage_frac = (
            round(news_archive_covered_n / trading_days_n, 4)
            if trading_days_n else 0.0
        )
        news_candidate_days_covered = len(news_candidate_dates_covered)
        news_candidate_day_coverage_frac = (
            round(news_candidate_days_covered / news_candidate_days_total, 4)
            if news_candidate_days_total else 0.0
        )
        news_candidate_signals_covered = sum(
            news_candidate_signal_counts_by_date.get(date_str, 0)
            for date_str in news_candidate_dates_covered
        )
        news_candidate_signal_coverage_frac = (
            round(news_candidate_signals_covered / news_candidate_signals_total, 4)
            if news_candidate_signals_total else 0.0
        )
        pilot_sleeve_replay = _finalize_pilot_replay_state()

        known_biases = {
            "ohlcv_source": {
                "snapshot_loaded": bool(self.ohlcv_snapshot_path),
                "snapshot_path": self.ohlcv_snapshot_path,
                "snapshot_written": bool(self.save_ohlcv_snapshot_path),
                "snapshot_write_path": self.save_ohlcv_snapshot_path,
            },
            "news_veto_unreplayed": {
                "archive_replay_enabled":    self.replay_news,
                "archive_coverage_fraction": news_archive_coverage_frac,
                "archive_dates_covered":     list(news_archive_dates_covered),
                "archive_dates_missing_n":   news_archive_missing_n,
            },
            "llm_gate_unreplayed": {
                "enabled":                          self.replay_llm,
                "coverage_fraction":                coverage_frac,
                "dates_covered":                    list(llm_dates_covered),
                "dates_missing_n":                  llm_missing_n,
                "candidate_day_coverage_fraction":  llm_candidate_day_coverage_frac,
                "candidate_days_covered":           llm_candidate_days_covered,
                "candidate_days_total":             llm_candidate_days_total,
                "candidate_dates_covered":          list(llm_candidate_dates_covered),
                "candidate_dates_missing":          list(llm_candidate_dates_missing),
                "candidate_signal_counts_by_date":  dict(llm_candidate_signal_counts_by_date),
                "candidate_tickers_by_date":        dict(llm_candidate_tickers_by_date),
                "candidate_signal_coverage_fraction": llm_candidate_signal_coverage_frac,
                "candidate_signals_covered":        llm_signals_presented,
                "candidate_signals_total":          total_signals_survived,
            },
            "exit_policy_unreplayed": build_exit_policy_replay_bias(
                partial_reduce_enabled=partial_reduce_enabled,
                trailing_partial_reduce_enabled=self.config.get(
                    "TRAILING_PARTIAL_REDUCE_ENABLED",
                    TRAILING_PARTIAL_REDUCE_ENABLED,
                ),
            ),
            "partial_reduce_replay": {
                "enabled": partial_reduce_enabled,
                "shared_policy": "production_parity.py",
                "default_behavior": (
                    "on_for_replay_container; pure_trailing_trims_disabled"
                ),
                "note": (
                    "Production position-action replay hooks are enabled by "
                    "default, but production_parity.py may return 0% for "
                    "advisory rules that have not been accepted for execution."
                ),
            },
            "pending_action_replay_unreplayed": build_pending_action_replay_bias(
                self.data_dir
            ),
            "pilot_sleeve_replay": {
                "enabled": self.include_pilot_sleeve,
                "mode": "point_in_time_in_memory",
                "default_core_only": not self.include_pilot_sleeve,
                "decision_log_written": False,
                "sleeve": PILOT_SLEEVE_NAME,
                "note": (
                    "Pilot sleeve replay uses universe_registry plus "
                    "universe_events for daily PIT eligibility and keeps "
                    "counterfactual decisions in memory so historical "
                    "backtests do not pollute the production append-only log."
                ),
            },
            "survivorship_bias_universe":  True,
            # Legacy placeholder overwritten below by live snapshot coverage.
            # Earnings strategy data quality: only days_to_earnings is historically
            # reconstructable from yfinance calendar. eps_estimate and
            # positive_surprise_history are always None in backtest (no snapshot
            # archive exists yet — see P-ERN in AGENTS.md §四). This means
            # earnings_event_long signals fire at reduced confidence (0.83 vs up
            # to 1.0 with surprise data) and without the positive_surprise_history
            # quality gate. Treat earnings_event_long metrics as a LOWER BOUND on
            # strategy quality until daily earnings snapshots are accumulated.
            "earnings_event_long_data_quality": {
                "days_to_earnings_source":        "yfinance calendar (reconstructable, ~accurate)",
                "eps_estimate":                   "always None — no snapshot archive",
                "positive_surprise_history":      "always None — no snapshot archive",
                "confidence_cap":                 0.83,
                "note": "earnings_event_long results reflect incomplete data; accumulate daily earnings snapshots (P-ERN) for accurate evaluation",
            },
            "notes": [
                "news veto lives in filter.py (EVENT_KEYWORDS + T1_TITLE_KEYWORDS); T1-negative replay via --replay-news (news_replay.py)",
                "LLM gate: production gates new_trade via llm_advisor; backtest replays only when --replay-llm is on AND llm_prompt_resp_YYYYMMDD.json exists",
                "Exit policy: production advisory SIGNAL_TARGET/ladder/time-stop actions are disclosed under exit_policy_unreplayed and are not executed by default backtests",
                "Trailing partial reduces: replay container is on by default, while pure trailing trims remain disabled by shared production policy",
                "data_layer.get_universe() reads current watchlist, not point-in-time",
                "earnings_event_long: runs with partial data (days_to_earnings only); eps_estimate and positive_surprise_history are None until P-ERN snapshots accumulate",
                "OHLCV is live-downloaded unless --ohlcv-snapshot is provided; small alpha deltas should not be promoted from non-deterministic vendor downloads",
            ],
        }
        # Refresh legacy earnings disclosure after the dict literal so older
        # comments/keys cannot keep reporting snapshot-backed fields as absent.
        known_biases["earnings_event_long_data_quality"] = (
            build_earnings_event_data_quality(
                self._earnings_snapshots,
                sim_dates,
            )
        )
        known_biases["notes"] = [
            note for note in known_biases["notes"]
            if not note.startswith("earnings_event_long: runs with partial data")
        ]
        known_biases["notes"].append(
                "Pending actions: production can preserve unexecuted REDUCE/EXIT "
                "through pending_actions.json; canonical backtests disclose but "
                "do not replay the current ledger"
            )
        known_biases["notes"].append(
            "Pilot sleeve replay: default backtests are core-only; "
            "--include-pilot-sleeve enables PIT AI_INFRA_PILOT replay with "
            "in-memory counterfactual attribution and no production log writes"
        )
        known_biases["notes"].append(
            "earnings_event_long: uses earnings snapshots when present; "
            "remaining bias is coverage/ticker sparsity, not always-missing "
            "eps/surprise fields"
        )
        capital_efficiency = _build_capital_efficiency(
            closed,
            self.config["INITIAL_CAPITAL"],
            len(sim_dates),
            total_pnl,
            strat_ret,
            self.config["MAX_POSITIONS"],
        )
        sizing_rule_signal_attribution = _finalize_sizing_rule_signal_attribution(
            sizing_rule_signal_attribution
        )
        sizing_rule_trade_attribution = _build_sizing_rule_trade_attribution(closed)

        from llm_backlog import build_llm_archive_backlog, build_llm_context_alignment

        llm_archive_backlog = build_llm_archive_backlog(
            self.data_dir,
            llm_candidate_dates_missing,
            llm_candidate_signal_counts_by_date,
        )
        llm_context_alignment = build_llm_context_alignment(
            self.data_dir,
            llm_candidate_dates_covered,
            llm_candidate_tickers_by_date,
            llm_candidate_signal_counts_by_date,
            llm_candidate_days_total,
            total_signals_survived,
        )
        known_biases["llm_gate_unreplayed"]["production_aligned_candidate_day_fraction"] = (
            llm_context_alignment.get("production_aligned_candidate_day_fraction_of_total")
        )
        known_biases["llm_gate_unreplayed"]["production_aligned_candidate_signal_fraction"] = (
            llm_context_alignment.get("production_aligned_candidate_signal_fraction_of_total")
        )

        effective_alignment_rows = [
            item for item in (llm_context_alignment.get("queue") or [])
            if item.get("ranking_status") == "ranking_eligible_aligned"
        ]
        effective_dates = [item.get("date") for item in effective_alignment_rows if item.get("date")]
        effective_presented = 0
        effective_passed = 0
        for item in effective_alignment_rows:
            overlap_tickers = [
                t.strip().upper()
                for t in (item.get("overlap_tickers") or [])
                if isinstance(t, str) and t.strip()
            ]
            if not overlap_tickers:
                continue
            from llm_replay import get_llm_decision_for_date
            decision = get_llm_decision_for_date(item["date"], self.data_dir)
            approved = {
                t.strip().upper()
                for t in (decision.get("approved_tickers") or [])
                if isinstance(t, str) and t.strip()
            }
            effective_presented += len(overlap_tickers)
            effective_passed += sum(1 for t in overlap_tickers if t in approved)
        effective_vetoed = effective_presented - effective_passed

        news_context_alignment = _build_news_context_alignment(
            self.data_dir,
            news_candidate_dates_covered,
            news_candidate_tickers_by_date,
            news_candidate_signal_counts_by_date,
            news_candidate_days_total,
            news_candidate_signals_total,
        )
        known_biases["news_veto_unreplayed"]["production_aligned_candidate_day_fraction"] = (
            news_context_alignment.get("production_aligned_candidate_day_fraction_of_total")
        )
        known_biases["news_veto_unreplayed"]["production_aligned_candidate_signal_fraction"] = (
            news_context_alignment.get("production_aligned_candidate_signal_fraction_of_total")
        )

        effective_news_rows = [
            item for item in (news_context_alignment.get("queue") or [])
            if item.get("alignment_status") == "aligned"
        ]
        effective_news_dates = [item.get("date") for item in effective_news_rows if item.get("date")]
        effective_news_presented = 0
        effective_news_vetoed = 0
        for item in effective_news_rows:
            overlap_tickers = {
                t.strip().upper()
                for t in (item.get("overlap_tickers") or [])
                if isinstance(t, str) and t.strip()
            }
            if not overlap_tickers:
                continue
            from news_replay import get_news_for_date
            news_dec = get_news_for_date(item["date"], self.data_dir)
            veto_set = {
                t.strip().upper()
                for t in (news_dec.get("t1_negative_tickers") or set())
                if isinstance(t, str) and t.strip()
            }
            effective_news_presented += len(overlap_tickers)
            effective_news_vetoed += sum(1 for t in overlap_tickers if t in veto_set)
        effective_news_passed = effective_news_presented - effective_news_vetoed

        # §4.2 LLM attribution bucket.
        llm_attribution = {
            "replay_enabled":                   self.replay_llm,
            "coverage_fraction":                coverage_frac,
            "trading_days":                     trading_days_n,
            "dates_covered":                    llm_covered_n,
            "dates_missing":                    llm_missing_n,
            "candidate_days_covered":           llm_candidate_days_covered,
            "candidate_days_total":             llm_candidate_days_total,
            "candidate_dates_covered":          list(llm_candidate_dates_covered),
            "candidate_dates_missing":          list(llm_candidate_dates_missing),
            "candidate_signal_counts_by_date":  dict(llm_candidate_signal_counts_by_date),
            "candidate_tickers_by_date":        dict(llm_candidate_tickers_by_date),
            "candidate_day_coverage_fraction":  llm_candidate_day_coverage_frac,
            "candidate_signals_covered":        llm_signals_presented,
            "candidate_signals_total":          total_signals_survived,
            "candidate_signal_coverage_fraction": llm_candidate_signal_coverage_frac,
            "context_alignment":                llm_context_alignment,
            "effective_attribution": {
                "effective_candidate_days": len(effective_dates),
                "effective_candidate_signals": llm_context_alignment.get(
                    "ranking_eligible_aligned_signals", 0
                ),
                "effective_candidate_dates": effective_dates,
                "effective_candidate_day_fraction_of_total": llm_context_alignment.get(
                    "ranking_eligible_candidate_day_fraction_of_total"
                ),
                "effective_candidate_signal_fraction_of_total": llm_context_alignment.get(
                    "ranking_eligible_candidate_signal_fraction_of_total"
                ),
                "signals_presented": effective_presented,
                "signals_vetoed_by_llm": effective_vetoed,
                "signals_passed_by_llm": effective_passed,
                "veto_rate": (
                    round(effective_vetoed / effective_presented, 4)
                    if effective_presented else None
                ),
                "notes": [
                    "effective_attribution keeps only production-aligned candidate overlap where archive_context says Task A was actually ranking-eligible.",
                    "Use this subset for soft-ranking alpha judgement; headline llm_attribution counts still include covered-but-empty or eligibility-unknown replay dates for compatibility.",
                ],
            },
            "signals_presented":                llm_signals_presented,
            "signals_vetoed_by_llm":            llm_signals_vetoed,
            "signals_passed_by_llm":            llm_signals_passed,
            "veto_rate":                        (round(llm_signals_vetoed / llm_signals_presented, 4)
                                                 if llm_signals_presented else None),
            "archive_backlog":                  llm_archive_backlog,
            "by_strategy": {
                strat: {
                    "presented": d["presented"],
                    "vetoed":    d["vetoed"],
                    "passed":    d["passed"],
                    "veto_rate": round(d["vetoed"] / d["presented"], 4)
                                 if d["presented"] else None,
                }
                for strat, d in llm_signals_by_strategy.items()
            },
            "notes": [
                "Counts include only days where llm_prompt_resp_YYYYMMDD.json was present.",
                "candidate_* metrics measure coverage over actual pre-LLM candidates, which is the relevant readiness gauge for LLM alpha experiments.",
                "LLM position_actions and pending_actions.json are not replayed by canonical backtests; see known_biases.pending_action_replay_unreplayed.",
                "by_strategy shows per-strategy veto breakdown to quantify LLM selectivity.",
            ],
        }

        # §4.2 news attribution bucket (parallel to llm_attribution).
        news_veto_rate = (round(news_signals_vetoed / news_signals_presented, 4)
                          if news_signals_presented else None)
        news_attribution = {
            "replay_enabled":              self.replay_news,
            "coverage_fraction":           news_archive_coverage_frac,
            "trading_days":                trading_days_n,
            "archive_dates_covered":       news_archive_covered_n,
            "archive_dates_missing":       news_archive_missing_n,
            "candidate_days_covered":      news_candidate_days_covered,
            "candidate_days_total":        news_candidate_days_total,
            "candidate_dates_covered":     list(news_candidate_dates_covered),
            "candidate_dates_missing":     list(news_candidate_dates_missing),
            "candidate_signal_counts_by_date": dict(news_candidate_signal_counts_by_date),
            "candidate_tickers_by_date":   dict(news_candidate_tickers_by_date),
            "candidate_day_coverage_fraction": news_candidate_day_coverage_frac,
            "candidate_signals_covered":   news_candidate_signals_covered,
            "candidate_signals_total":     news_candidate_signals_total,
            "candidate_signal_coverage_fraction": news_candidate_signal_coverage_frac,
            "context_alignment":           news_context_alignment,
            "effective_attribution": {
                "effective_candidate_days": len(effective_news_dates),
                "effective_candidate_signals": news_context_alignment.get("aligned_signals", 0),
                "effective_candidate_dates": effective_news_dates,
                "effective_candidate_day_fraction_of_total": news_context_alignment.get(
                    "production_aligned_candidate_day_fraction_of_total"
                ),
                "effective_candidate_signal_fraction_of_total": news_context_alignment.get(
                    "production_aligned_candidate_signal_fraction_of_total"
                ),
                "signals_presented": effective_news_presented,
                "signals_vetoed_by_news": effective_news_vetoed,
                "signals_passed_by_news": effective_news_passed,
                "veto_rate": (
                    round(effective_news_vetoed / effective_news_presented, 4)
                    if effective_news_presented else None
                ),
                "notes": [
                    "effective_attribution keeps only candidate overlap between saved production quant_signals and the backtest pre-news candidate set on archived-news dates.",
                    "Use this subset for archive-backed news hypotheses; headline news_attribution still includes covered dates that may have had empty or mismatched production candidates.",
                ],
            },
            "signals_presented":           news_signals_presented,
            "signals_vetoed_by_news":      news_signals_vetoed,
            "signals_passed_by_news":      news_signals_passed,
            "veto_rate":                   news_veto_rate,
            "notes": [
                "Counts include only days where clean_trade_news_YYYYMMDD.json was present AND replay_news=True.",
                "candidate_* metrics measure archive coverage over actual pre-news candidates, which is the relevant readiness gauge for archived-news alpha experiments.",
                "Veto criterion: ticker appears in T1-negative headline (earnings miss, guidance cut, bankruptcy, etc.).",
                "Conservative upper bound — production LLM may approve despite negative news if already priced in.",
            ],
        }

        addon_attribution = {
            "enabled": addon_enabled,
            "checkpoint_days": self.config.get("ADDON_CHECKPOINT_DAYS"),
            "min_unrealized_pct": self.config.get("ADDON_MIN_UNREALIZED_PCT"),
            "min_rs_vs_spy": self.config.get("ADDON_MIN_RS_VS_SPY"),
            "fraction_of_original_shares": self.config.get("ADDON_FRACTION_OF_ORIGINAL_SHARES"),
            "max_position_pct": self.config.get("ADDON_MAX_POSITION_PCT"),
            "require_checkpoint_cap_room": self.config.get("ADDON_REQUIRE_CHECKPOINT_CAP_ROOM"),
            "require_improving_followthrough": self.config.get("ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH"),
            "second_addon_enabled": self.config.get("SECOND_ADDON_ENABLED"),
            "second_addon_checkpoint_days": self.config.get("SECOND_ADDON_CHECKPOINT_DAYS"),
            "second_addon_min_unrealized_pct": self.config.get("SECOND_ADDON_MIN_UNREALIZED_PCT"),
            "second_addon_min_rs_vs_spy": self.config.get("SECOND_ADDON_MIN_RS_VS_SPY"),
            "second_addon_fraction_of_original_shares": self.config.get(
                "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES"
            ),
            "second_addon_max_position_pct": self.config.get("SECOND_ADDON_MAX_POSITION_PCT"),
            "scheduled": addon_scheduled_count,
            "executed": addon_executed_count,
            "skipped": addon_skipped_count,
            "checkpoint_rejected": addon_checkpoint_rejected_count,
            "events": addon_events,
            "notes": [
                "Strict day-2 follow-through add-on is enabled by default after exp-20260427-013.",
                "Add-on fills at next available ticker open after checkpoint using entry slippage.",
                "Incremental shares are capped by original-share fraction, single-position cap, and portfolio heat cap.",
            ],
        }
        partial_reduce_attribution = {
            "enabled": partial_reduce_enabled,
            "production_trailing_stop_pct": self.config.get(
                "PRODUCTION_TRAILING_STOP_PCT",
                TRAILING_STOP_PCT,
            ),
            "trailing_partial_reduce_enabled": self.config.get(
                "TRAILING_PARTIAL_REDUCE_ENABLED",
                TRAILING_PARTIAL_REDUCE_ENABLED,
            ),
            "scheduled": partial_reduce_scheduled_count,
            "executed": partial_reduce_executed_count,
            "skipped": partial_reduce_skipped_count,
            "events": partial_reduce_events,
            "notes": [
                "Default-on replay container for implemented shared production position-action policies.",
                "Trigger uses production high-water pct stop on daily close; fill uses next ticker open with stop-side slippage.",
                "Reduce percentage and share rounding come from production_parity.py.",
                "Pure trailing trims remain disabled by shared policy unless explicitly enabled for diagnostics.",
            ],
        }
        exit_advisory_shadow_attribution = build_exit_advisory_shadow_attribution(
            exit_advisory_shadow_events,
            closed,
        )
        scarce_slot_attribution = {
            "defer_breakout_when_slots_lte": self.config.get(
                "DEFER_BREAKOUT_WHEN_SLOTS_LTE"
            ),
            "defer_breakout_max_min_index_pct_from_ma": self.config.get(
                "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA"
            ),
            "breakout_deferred": scarce_slot_breakout_deferred_count,
            "deferred_events": scarce_slot_deferred_events,
            "notes": [
                "Conditional sleeve routing: defer breakout_long entries when only scarce slots remain.",
                "Optional market-state cap limits deferral to non-extended SPY/QQQ tapes.",
                "Deferred signals are recorded in entry_execution_attribution as scarce_slot_breakout_deferred.",
            ],
        }
        entry_execution_attribution = _summarize_entry_decision_events(
            entry_decision_events
        )

        result = {
            "period":              f"{sim_dates[0].date()} → {sim_dates[-1].date()}",
            "trading_days":        len(sim_dates),
            "total_trades":        total,
            "wins":                len(wins),
            "losses":              len(losses),
            "win_rate":            round(len(wins) / total, 4) if total else 0,
            "total_pnl":           round(total_pnl, 2),
            "sharpe":              sharpe,
            "sharpe_daily":        sharpe_daily,
            "sharpe_method":       "per_trade_sqrt30_legacy",
            "max_drawdown_pct":    round(max_dd, 4),
            "worst_trade_pct":     worst_trade_pct,
            "max_consecutive_losses": max_consecutive_losses,
            "tail_loss_share":     tail_loss_share,
            "capital_efficiency":  capital_efficiency,
            "sizing_rule_signal_attribution": sizing_rule_signal_attribution,
            "sizing_rule_trade_attribution": sizing_rule_trade_attribution,
            "signals_generated":   total_signals_generated,
            "signals_survived":    total_signals_survived,
            "survival_rate":       survival_rate,
            "by_strategy":         by_strategy,
            "benchmarks":          benchmarks,
            "known_biases":        known_biases,
            "llm_attribution":     llm_attribution,
            "news_attribution":    news_attribution,
            "addon_attribution":   addon_attribution,
            "partial_reduce_attribution": partial_reduce_attribution,
            "exit_advisory_shadow_attribution": exit_advisory_shadow_attribution,
            "scarce_slot_attribution": scarce_slot_attribution,
            "entry_execution_attribution": entry_execution_attribution,
            "pilot_sleeve_replay": pilot_sleeve_replay,
            "equity_curve_integrity": equity_curve_integrity,
            "caveats": (
                [
                    f"news_veto_replayed_on_{news_archive_covered_n}_of_{trading_days_n}_days: "
                    f"T1-negative veto active (coverage {news_archive_coverage_frac:.1%}). "
                    f"Remaining {news_archive_missing_n} days still optimistic."
                ]
                if self.replay_news else
                [
                    "news_veto_not_replayed: production filter.py T1-negative-news "
                    "veto has no historical archive; signals rejected by news in "
                    "live runs are still accepted here. Treat metrics as an "
                    "OPTIMISTIC upper bound.",
                ]
            )
            + [
                "exit_policy_unreplayed: production advisory SIGNAL_TARGET, "
                "profit-ladder, time-stop, and pending "
                "REDUCE/EXIT actions are disclosed but not executed by "
                "default backtests; target_price is a full-position simulated "
                "target exit in backtest."
            ]
            + (
                [
                    "pilot_sleeve_replay_enabled: PIT AI_INFRA_PILOT replay "
                    "ran in memory; it did not write "
                    "data/pilot_competition_decisions.jsonl."
                ]
                if self.include_pilot_sleeve
                else []
            ),
            "equity_curve":        equity_curve,
            "trades":              closed,
        }

        from convergence import compute_convergence, compute_expected_value_score
        result["expected_value_score"] = compute_expected_value_score(result)
        result["convergence"] = compute_convergence(result)
        result["single_window_quality"] = _build_multi_window_robustness([result])

        # v2 shadow verdict — what convergence WOULD say if we also required
        # sharpe_daily >= sharpe_min. Does not mutate the real verdict.
        from convergence import CRITERIA as _CRIT
        sharpe_daily_pass = (sharpe_daily is not None
                             and sharpe_daily >= _CRIT["sharpe_min"])
        result["converged_v2_shadow"] = {
            "sharpe_daily":                 sharpe_daily,
            "sharpe_daily_would_pass":      bool(sharpe_daily_pass),
            "converged_if_sharpe_daily":    bool(
                result["convergence"]["converged"] and sharpe_daily_pass),
        }
        return result

    def sweep(self, param_name, values):
        """
        Single-parameter sweep: varies a config key across values.

        Currently supports MAX_POSITIONS and INITIAL_CAPITAL.
        For signal engine parameters (ATR multipliers etc.), modify the
        source module constants before running — this backtester calls them
        directly rather than passing config overrides.

        Returns:
            list[dict]: One result dict per value
        """
        results = []
        for val in values:
            cfg = {**self.config, param_name: val}
            engine = BacktestEngine(
                self.universe,
                start=str(self.start.date()) if self.start else None,
                end=str(self.end.date()) if self.end else None,
                config=cfg,
                replay_llm=self.replay_llm,
                replay_news=self.replay_news,
                data_dir=self.data_dir,
                ohlcv_snapshot_path=self.ohlcv_snapshot_path,
                save_ohlcv_snapshot_path=self.save_ohlcv_snapshot_path,
                include_pilot_sleeve=self.include_pilot_sleeve,
            )
            result = engine.run()
            result["param_name"]  = param_name
            result["param_value"] = val
            results.append(result)
            logger.info(
                f"Sweep {param_name}={val}: trades={result.get('total_trades', 0)} "
                f"pnl={result.get('total_pnl', 0):.2f} sharpe={result.get('sharpe')}"
            )
        return results


# ── CLI ─────────────────────────────────────────────────────────────────────

def _print_results(results):
    """Pretty-print backtest results to console."""
    print("\n" + "=" * 60)
    print("  SIGNAL-LEVEL BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Period:            {results['period']}")
    print(f"  Trading days:      {results['trading_days']}")
    print(f"  Total trades:      {results['total_trades']}")
    print(f"  Wins / Losses:     {results['wins']} / {results['losses']}")
    print(f"  Win rate:          {results['win_rate']*100:.1f}%")
    print(f"  Total PnL:         ${results['total_pnl']:,.2f}")
    print(f"  Sharpe (legacy):   {results['sharpe']}")
    print(f"  Sharpe (daily):    {results.get('sharpe_daily')}")
    print(f"  EV score:          {results.get('expected_value_score')}")
    print(f"  Max drawdown:      {results['max_drawdown_pct']*100:.2f}%")
    worst_trade = results.get("worst_trade_pct")
    worst_trade_str = f"{worst_trade*100:.2f}%" if worst_trade is not None else "N/A"
    print(f"  Worst trade:       {worst_trade_str}")
    print(f"  Max loss streak:   {results.get('max_consecutive_losses')}")
    tail_loss = results.get("tail_loss_share")
    tail_loss_str = f"{tail_loss*100:.1f}%" if tail_loss is not None else "N/A"
    print(f"  Tail loss share:   {tail_loss_str}")
    print(f"  Signals generated: {results['signals_generated']}")
    print(f"  Signals survived:  {results['signals_survived']}")
    print(f"  Survival rate:     {results['survival_rate']*100:.1f}%")
    print("=" * 60)

    cap_eff = results.get("capital_efficiency") or {}
    if cap_eff:
        def _fmt_pct(v):
            return f"{v*100:+.4f}%" if v is not None else "N/A"
        def _fmt_usd(v):
            return f"${v:,.2f}" if v is not None else "N/A"
        print("\n  CAPITAL EFFICIENCY:")
        print(f"    return / trade:           {_fmt_pct(cap_eff.get('return_per_trade'))}")
        print(f"    pnl / trade:              {_fmt_usd(cap_eff.get('pnl_per_trade_usd'))}")
        print(f"    avg calendar days held:   {cap_eff.get('avg_calendar_days_held')}")
        print(f"    pnl / calendar slot-day:  {_fmt_usd(cap_eff.get('pnl_per_calendar_slot_day_usd'))}")
        gross = cap_eff.get("gross_slot_day_fraction")
        gross_str = f"{gross*100:.1f}%" if gross is not None else "N/A"
        print(f"    gross slot-day usage:     {gross_str}")

    rule_attr = results.get("sizing_rule_signal_attribution") or {}
    if rule_attr:
        print("\n  SIZING RULE SIGNAL ATTRIBUTION:")
        for key, rec in rule_attr.items():
            print(f"    {key}: seen={rec.get('signals_seen')} "
                  f"zero={rec.get('zero_risk_signals')} "
                  f"reduced={rec.get('reduced_risk_signals')} "
                  f"avg_risk {rec.get('avg_risk_pct_before')} -> "
                  f"{rec.get('avg_risk_pct_after')}")

    if results.get("by_strategy"):
        from strategy_attribution import format_attribution_table
        print("\n  PER-STRATEGY ATTRIBUTION:")
        print(format_attribution_table(results["by_strategy"]))

    if results.get("benchmarks"):
        b = results["benchmarks"]
        print("\n  BENCHMARKS (buy-and-hold same window):")
        def _fmt(v):
            return f"{v*100:+.2f}%" if v is not None else "  N/A"
        print(f"    SPY return:      {_fmt(b.get('spy_buy_hold_return_pct'))}")
        print(f"    QQQ return:      {_fmt(b.get('qqq_buy_hold_return_pct'))}")
        print(f"    Strategy return: {_fmt(b.get('strategy_total_return_pct'))}")
        print(f"    vs SPY:          {_fmt(b.get('strategy_vs_spy_pct'))}")
        print(f"    vs QQQ:          {_fmt(b.get('strategy_vs_qqq_pct'))}")

    pilot_replay = results.get("pilot_sleeve_replay") or {}
    if pilot_replay.get("enabled"):
        print("\n  PILOT SLEEVE REPLAY:")
        print(f"    sleeve:                  {pilot_replay.get('sleeve')}")
        print(f"    eligible tickers:        {pilot_replay.get('eligible_tickers')}")
        print(f"    eligible days:           {pilot_replay.get('eligible_days')}")
        print(f"    signals generated:       {pilot_replay.get('signals_generated')}")
        print(f"    signals survived:        {pilot_replay.get('signals_survived')}")
        print(f"    entries / closed:        "
              f"{pilot_replay.get('entries')} / {pilot_replay.get('closed_trades')}")
        print(f"    direct pilot pnl:        ${pilot_replay.get('direct_pilot_pnl'):,.2f}")
        print(f"    replacement value:       {pilot_replay.get('replacement_value')}")
        print(f"    risk-adjusted repl avg:  "
              f"{pilot_replay.get('risk_adjusted_replacement_value_avg')}")

    if results.get("convergence"):
        from convergence import format_convergence_report
        print("\n  CONVERGENCE:")
        print(format_convergence_report(results["convergence"]))

    shadow = results.get("converged_v2_shadow")
    if shadow:
        print("\n  V2 SHADOW (observation — does NOT change verdict above):")
        print(f"    sharpe_daily:              {shadow.get('sharpe_daily')}")
        print(f"    sharpe_daily would pass:   {shadow.get('sharpe_daily_would_pass')}")
        print(f"    converged if also gated:   {shadow.get('converged_if_sharpe_daily')}")

    llm_attr = results.get("llm_attribution")
    if llm_attr:
        print("\n  LLM ATTRIBUTION:")
        print(f"    replay_enabled:          {llm_attr.get('replay_enabled')}")
        print(f"    coverage:                "
              f"{llm_attr.get('dates_covered')}/{llm_attr.get('trading_days')} days "
              f"({(llm_attr.get('coverage_fraction') or 0)*100:.1f}%)")
        print(f"    candidate-day coverage:  "
              f"{llm_attr.get('candidate_days_covered')}/{llm_attr.get('candidate_days_total')} "
              f"({(llm_attr.get('candidate_day_coverage_fraction') or 0)*100:.1f}%)")
        print(f"    candidate-signal cover:  "
              f"{llm_attr.get('candidate_signals_covered')}/{llm_attr.get('candidate_signals_total')} "
              f"({(llm_attr.get('candidate_signal_coverage_fraction') or 0)*100:.1f}%)")
        candidate_missing = llm_attr.get("candidate_dates_missing") or []
        if candidate_missing:
            preview = ", ".join(candidate_missing[:5])
            suffix = " ..." if len(candidate_missing) > 5 else ""
            print(f"    missing candidate days:  {preview}{suffix}")
        backlog = llm_attr.get("archive_backlog") or {}
        if backlog.get("missing_candidate_days"):
            print(f"    raw-response backlog:    "
                  f"{backlog.get('raw_response_recoverable_days')}/{backlog.get('missing_candidate_days')} days")
            print(f"    prompt-ready backlog:    "
                  f"{backlog.get('prompt_ready_days')}/{backlog.get('missing_candidate_days')} days")
            print(f"    prompt-ineligible:       "
                  f"{backlog.get('prompt_ineligible_days')}/{backlog.get('missing_candidate_days')} days")
        alignment = llm_attr.get("context_alignment") or {}
        if alignment.get("covered_candidate_days"):
            print(f"    production-aligned:      "
                  f"{alignment.get('aligned_days')}/{llm_attr.get('candidate_days_total')} total "
                  f"({(alignment.get('production_aligned_candidate_day_fraction_of_total') or 0)*100:.1f}%)")
            print(f"    aligned within covered:  "
                  f"{alignment.get('aligned_days')}/{alignment.get('covered_candidate_days')} "
                  f"({(alignment.get('production_aligned_candidate_day_fraction_of_covered') or 0)*100:.1f}%)")
            print(f"    ranking-eligible:        "
                  f"{alignment.get('ranking_eligible_aligned_days')}/{llm_attr.get('candidate_days_total')} total "
                  f"({(alignment.get('ranking_eligible_candidate_day_fraction_of_total') or 0)*100:.1f}%)")
        effective = llm_attr.get("effective_attribution") or {}
        if effective.get("effective_candidate_days"):
            print(f"    effective sample days:   "
                  f"{effective.get('effective_candidate_days')}/{llm_attr.get('candidate_days_total')} total "
                  f"({(effective.get('effective_candidate_day_fraction_of_total') or 0)*100:.1f}%)")
            print(f"    effective sample sigs:   "
                  f"{effective.get('effective_candidate_signals')}/{llm_attr.get('candidate_signals_total')} total "
                  f"({(effective.get('effective_candidate_signal_fraction_of_total') or 0)*100:.1f}%)")
            print(f"    effective veto_rate:     {effective.get('veto_rate')}")
        print(f"    signals presented:       {llm_attr.get('signals_presented')}")
        print(f"    vetoed by LLM:           {llm_attr.get('signals_vetoed_by_llm')}")
        print(f"    passed by LLM:           {llm_attr.get('signals_passed_by_llm')}")
        print(f"    veto_rate:               {llm_attr.get('veto_rate')}")

    news_attr = results.get("news_attribution")
    if news_attr:
        print("\n  NEWS T1-NEGATIVE ATTRIBUTION:")
        print(f"    replay_enabled:          {news_attr.get('replay_enabled')}")
        print(f"    coverage:                "
              f"{news_attr.get('archive_dates_covered')}/{news_attr.get('trading_days')} days "
              f"({(news_attr.get('coverage_fraction') or 0)*100:.1f}%)")
        print(f"    candidate-day coverage:  "
              f"{news_attr.get('candidate_days_covered')}/{news_attr.get('candidate_days_total')} "
              f"({(news_attr.get('candidate_day_coverage_fraction') or 0)*100:.1f}%)")
        print(f"    candidate-signal cover:  "
              f"{news_attr.get('candidate_signals_covered')}/{news_attr.get('candidate_signals_total')} "
              f"({(news_attr.get('candidate_signal_coverage_fraction') or 0)*100:.1f}%)")
        alignment = news_attr.get("context_alignment") or {}
        if alignment.get("covered_candidate_days"):
            print(f"    production-aligned:      "
                  f"{alignment.get('aligned_days')}/{news_attr.get('candidate_days_total')} total "
                  f"({(alignment.get('production_aligned_candidate_day_fraction_of_total') or 0)*100:.1f}%)")
        effective = news_attr.get("effective_attribution") or {}
        if effective.get("effective_candidate_days"):
            print(f"    effective sample days:   "
                  f"{effective.get('effective_candidate_days')}/{news_attr.get('candidate_days_total')} total "
                  f"({(effective.get('effective_candidate_day_fraction_of_total') or 0)*100:.1f}%)")
            print(f"    effective sample sigs:   "
                  f"{effective.get('effective_candidate_signals')}/{news_attr.get('candidate_signals_total')} total "
                  f"({(effective.get('effective_candidate_signal_fraction_of_total') or 0)*100:.1f}%)")
            print(f"    effective veto_rate:     {effective.get('veto_rate')}")
        print(f"    signals presented:       {news_attr.get('signals_presented')}")
        print(f"    vetoed by news:          {news_attr.get('signals_vetoed_by_news')}")
        print(f"    passed by news:          {news_attr.get('signals_passed_by_news')}")
        print(f"    veto_rate:               {news_attr.get('veto_rate')}")

    integrity = results.get("equity_curve_integrity")
    if integrity:
        print("\n  EQUITY-CURVE INTEGRITY:")
        print(f"    cash_usd populated in open_positions: "
              f"{integrity.get('cash_field_present_in_open_positions')}")
        flat = integrity.get("equity_flat_fraction")
        flat_str = f"{flat*100:.1f}%" if flat is not None else "N/A"
        print(f"    flat-equity days fraction:            {flat_str}")
        print(f"    daily returns sampled:                "
              f"{integrity.get('daily_returns_count')}")

    if results.get("caveats"):
        print("\n  CAVEATS (parity gaps vs production):")
        for c in results["caveats"]:
            print(f"    - {c}")

    if results.get("trades"):
        print("\n  TRADE LOG:")
        print(f"  {'Ticker':<8} {'Strategy':<20} {'Entry':>8} {'Exit':>8} "
              f"{'PnL':>10} {'Reason':<12} {'Dates'}")
        print("  " + "-" * 90)
        for t in results["trades"]:
            print(f"  {t['ticker']:<8} {t['strategy']:<20} "
                  f"${t['entry_price']:>7.2f} ${t['exit_price']:>7.2f} "
                  f"${t['pnl']:>9.2f} {t['exit_reason']:<12} "
                  f"{t['entry_date']} → {t['exit_date']}")
    print()


def _build_stability_diagnostics(primary, secondary):
    """Structured cross-window comparison — observation only, no PASS/FAIL.

    Returns a dict with per-metric deltas and simple consistency booleans.
    Consumers (humans, future gating logic) decide how to act on it.
    """
    if not primary or not secondary or "error" in secondary:
        return None

    def _sub(a, b):
        if a is None or b is None:
            return None
        return round(a - b, 4)

    p_dd = primary.get("max_drawdown_pct")
    s_dd = secondary.get("max_drawdown_pct")
    p_ret = (primary.get("benchmarks") or {}).get("strategy_total_return_pct")
    s_ret = (secondary.get("benchmarks") or {}).get("strategy_total_return_pct")

    return {
        "stable_across_windows": {
            "expected_value_score_delta":  _sub(primary.get("expected_value_score"),
                                               secondary.get("expected_value_score")),
            "sharpe_legacy_delta":           _sub(primary.get("sharpe"),
                                                 secondary.get("sharpe")),
            "sharpe_daily_delta":            _sub(primary.get("sharpe_daily"),
                                                 secondary.get("sharpe_daily")),
            "max_drawdown_delta":            _sub(p_dd, s_dd),
            "drawdown_consistent": (p_dd is not None and s_dd is not None
                                    and abs(p_dd - s_dd) <= 0.05),
            "directionally_profitable_both": (p_ret is not None and s_ret is not None
                                              and p_ret > 0 and s_ret > 0),
            "primary_expected_value_score":  primary.get("expected_value_score"),
            "secondary_expected_value_score": secondary.get("expected_value_score"),
            "primary_sharpe_daily":          primary.get("sharpe_daily"),
            "secondary_sharpe_daily":        secondary.get("sharpe_daily"),
            "primary_return_pct":            p_ret,
            "secondary_return_pct":          s_ret,
        },
        "multi_window_robustness": _build_multi_window_robustness([primary, secondary]),
    }


def _print_diagnostics(diagnostics):
    """Pretty-print the stability diagnostics block."""
    if not diagnostics:
        return
    s = diagnostics.get("stable_across_windows") or {}
    print("\n" + "=" * 60)
    print("  CROSS-WINDOW STABILITY (observation only)")
    print("=" * 60)

    def _fmt(v):
        if v is None:
            return "N/A"
        return f"{v:+.4f}" if isinstance(v, float) else str(v)

    print(f"  primary EV score:        {_fmt(s.get('primary_expected_value_score'))}")
    print(f"  secondary EV score:      {_fmt(s.get('secondary_expected_value_score'))}")
    print(f"  Δ EV score:              {_fmt(s.get('expected_value_score_delta'))}")
    print(f"  primary sharpe_daily:    {_fmt(s.get('primary_sharpe_daily'))}")
    print(f"  secondary sharpe_daily:  {_fmt(s.get('secondary_sharpe_daily'))}")
    print(f"  Δ sharpe_legacy:         {_fmt(s.get('sharpe_legacy_delta'))}")
    print(f"  Δ sharpe_daily:          {_fmt(s.get('sharpe_daily_delta'))}")
    print(f"  Δ max_drawdown:          {_fmt(s.get('max_drawdown_delta'))}")
    print(f"  drawdown_consistent:     {s.get('drawdown_consistent')}")
    print(f"  profitable in both:      {s.get('directionally_profitable_both')}")
    r = diagnostics.get("multi_window_robustness") or {}
    if r:
        print(f"  robustness score:        {r.get('robustness_score')}")
        print(f"  EV positive windows:     "
              f"{r.get('expected_value_score_positive_windows')}/{r.get('windows')}")
        print(f"  EV score spread:         {_fmt(r.get('expected_value_score_spread'))}")
        print(f"  worst max drawdown:      {_fmt(r.get('worst_max_drawdown_pct'))}")
    print("=" * 60)


def main():
    import argparse

    # Ensure quant/ is on sys.path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Signal-level backtester")
    parser.add_argument("--start", type=str, default=None,
                        help="Start date YYYY-MM-DD (default: 6 months ago)")
    parser.add_argument("--end", type=str, default=None,
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--sweep", nargs="+", default=None,
                        help="Parameter sweep: PARAM_NAME val1 val2 ...")
    parser.add_argument("--no-secondary", action="store_true",
                        help="Skip the non-overlapping secondary-window diagnostic run")
    parser.add_argument("--replay-llm", action="store_true",
                        help="Apply LLM gate using data/llm_prompt_resp_YYYYMMDD.json "
                             "when the file exists (§6.1 parity fix). Default: off.")
    parser.add_argument("--replay-news", action="store_true",
                        help="Apply T1-negative news veto using "
                             "data/clean_trade_news_YYYYMMDD.json when the file exists. "
                             "Default: off.")
    parser.add_argument("--replay-partial-reduces",
                        action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Replay production position-action policy. Default: on.")
    parser.add_argument("--regime-aware-exit",
                        action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Use the entry-day regime exit profile to set ATR target width. Default: on.")
    parser.add_argument("--ohlcv-snapshot", type=str, default=None,
                        help="Load OHLCV from a saved snapshot JSON instead of live yfinance.")
    parser.add_argument("--save-ohlcv-snapshot", type=str, default=None,
                        help="Save downloaded OHLCV to a snapshot JSON for deterministic reruns.")
    parser.add_argument("--include-pilot-sleeve", action="store_true",
                        help="Enable point-in-time AI_INFRA_PILOT sleeve replay. "
                             "Default backtests remain core-only.")
    args = parser.parse_args()

    # Default: last 6 months
    if not args.start:
        args.start = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime("%Y-%m-%d")
    if not args.end:
        args.end = pd.Timestamp.now().strftime("%Y-%m-%d")

    # Universe from data_layer
    try:
        from data_layer import get_universe
        universe = get_universe()
    except Exception:
        from filter import WATCHLIST
        universe = list(WATCHLIST)

    cfg = {
        "REGIME_AWARE_EXIT": args.regime_aware_exit,
        "REPLAY_PARTIAL_REDUCES": args.replay_partial_reduces,
    }
    engine = BacktestEngine(universe, start=args.start, end=args.end,
                            config=cfg,
                            replay_llm=args.replay_llm,
                            replay_news=args.replay_news,
                            ohlcv_snapshot_path=args.ohlcv_snapshot,
                            save_ohlcv_snapshot_path=args.save_ohlcv_snapshot,
                            include_pilot_sleeve=args.include_pilot_sleeve)

    if args.sweep and len(args.sweep) >= 2:
        param_name = args.sweep[0]
        raw = [float(v) for v in args.sweep[1:]]
        values = [int(v) if v == int(v) else v for v in raw]
        results_list = engine.sweep(param_name, values)
        for r in results_list:
            print(f"\n--- {param_name} = {r['param_value']} ---")
            _print_results(r)
    else:
        results = engine.run()

        if "error" in results:
            print(f"ERROR: {results['error']}")
            sys.exit(1)

        _print_results(results)

        # Diagnostic: non-overlapping secondary window immediately preceding
        # the primary. Report-only — does NOT change convergence verdict.
        secondary = None
        diagnostics = None
        if not args.no_secondary:
            try:
                primary_start = pd.Timestamp(args.start)
                secondary_end = (primary_start - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                secondary_start = (primary_start - pd.Timedelta(days=183)).strftime("%Y-%m-%d")
                print(f"\n--- SECONDARY WINDOW DIAGNOSTIC: "
                      f"{secondary_start} → {secondary_end} ---")
                secondary_engine = BacktestEngine(
                    universe, start=secondary_start, end=secondary_end,
                    config=cfg,
                    replay_llm=args.replay_llm,
                    replay_news=args.replay_news,
                    ohlcv_snapshot_path=args.ohlcv_snapshot,
                    include_pilot_sleeve=args.include_pilot_sleeve)
                secondary = secondary_engine.run()
                if "error" in secondary:
                    print(f"  (secondary run failed: {secondary['error']})")
                    secondary = {"error": secondary["error"]}
                else:
                    _print_results(secondary)
                    diagnostics = _build_stability_diagnostics(results, secondary)
                    _print_diagnostics(diagnostics)
            except Exception as e:
                print(f"  (secondary run exception: {e})")
                secondary = {"error": str(e)}

        # Save results. Combined layout when secondary is present; flat when not
        # (preserves the historical shape consumed by downstream readers).
        out_path = os.path.join(script_dir, "..", "data",
                                f"backtest_results_{datetime.now().strftime('%Y%m%d')}.json")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

        primary_save = {k: v for k, v in results.items() if k != "equity_curve"}
        if secondary is not None:
            secondary_save = ({k: v for k, v in secondary.items() if k != "equity_curve"}
                              if "error" not in secondary else secondary)
            save_data = {
                **primary_save,                 # flat keys preserved for compat
                "primary":     primary_save,
                "secondary":   secondary_save,
                "diagnostics": diagnostics,
            }
        else:
            save_data = primary_save

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        print(f"Results saved → {out_path}")


if __name__ == "__main__":
    main()
