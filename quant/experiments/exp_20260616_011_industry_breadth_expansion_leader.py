"""exp-20260616-011: industry breadth-expansion leader candidate pool.

Replay-only alpha search. The single decision hypothesis is that a liquid
leader inside an industry whose internal breadth is expanding can capture
synchronized sponsorship better than single-name momentum.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260613_027_industry_contraction_scarce_leader as prior  # noqa: E402


framework = prior.framework
shadow = prior.shadow
overlay_helper = prior.overlay_helper
sleeve = prior.sleeve
get_universe = prior.get_universe
persist_self_registered_result = prior.persist_self_registered_result

EXPERIMENT_ID = "exp-20260616-011"
STEM = "industry_breadth_expansion_leader"
TRIAL_FAMILY = "industry_breadth_expansion_leader_candidate_pool"
TRIAL_VARIANT_ID = "industry_breadth_expansion_leader_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_breadth_expansion_leader_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_011_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_INDUSTRY_LIQUID_MEMBERS = 5
MIN_CURRENT_ABOVE_SMA20_FRACTION = 0.62
MAX_PRIOR5_ABOVE_SMA20_FRACTION = 0.48
MIN_BREADTH_IMPROVEMENT = 0.16
MIN_INDUSTRY_POSITIVE_RET5_FRACTION = 0.60
MIN_INDUSTRY_MEDIAN_RET5 = 0.012
MIN_INDUSTRY_MEDIAN_RET20 = 0.0
MAX_INDUSTRY_MEDIAN_RET20 = 0.12
MIN_INDUSTRY_RET5_DISPERSION = 0.012

MIN_LEADER_RET5 = 0.0
MAX_LEADER_RET5 = 0.12
MIN_RET5_VS_INDUSTRY_MEDIAN = 0.0
MIN_RET20_VS_INDUSTRY_MEDIAN = 0.0
MIN_RET20_EXCESS_SPY = 0.01
MIN_RET60_EXCESS_SPY = -0.02
MIN_SIGNAL_RETURN = -0.01
MAX_SIGNAL_RETURN = 0.07
MIN_CLOSE_LOCATION = 0.55
MIN_SMA20_RATIO = 1.0
MIN_SMA50_RATIO = 0.98
MIN_VOLUME_RATIO_20D = 0.50
MAX_VOLUME_RATIO_20D = 3.50
MAX_REALIZED_VOL_20D = 0.095

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

WINDOWS = framework.WINDOWS

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_momentum_relabel",
        "window_regression",
        "accepted_relation_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Accepted relation alphas worked when industry or peer relation itself "
        "was the edge, while weak-cohort scarce leaders and generic OHLCV "
        "retunes failed; this tests the opposite relation, synchronized "
        "breadth expansion, using only PIT OHLCV and no production behavior "
        "change."
    ),
    "recorded_at": "2026-06-16T09:05:46+00:00",
}

ACCEPTED_COMPARATORS = {
    "exp-20260608-008_industry_stable_core_flow": {
        "aggregate_expected_value_delta": 0.1459,
        "aggregate_pnl_delta": 3731.54,
        "note": "accepted shared industry-stable core-flow adapter",
    },
    "exp-20260607-008_industry_relative_laggard_repair": {
        "aggregate_expected_value_delta": 0.2763,
        "aggregate_pnl_delta": 6208.99,
        "note": "accepted shared industry-relative laggard-repair adapter",
    },
    "exp-20260611-007_distribution_day_absorption": {
        "aggregate_expected_value_delta": 0.5286,
        "aggregate_pnl_delta": 10432.91,
        "note": "accepted shared distribution-day absorption adapter",
    },
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
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry",
        "portfolio_displacement": "none unless a later shared helper passes",
        "kill_switch": "trade_enabled remains false; no production changes",
        "failure_handling": "missing OHLCV, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "industry grouping, breadth-expansion context, leader gates, cooldown, "
        "next-open paper entry, 10-trading-day exit, costs, and concentration "
        "controls in both historical replay and daily production observation."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool alpha: when a PIT industry cohort shows internal "
        "breadth expansion and positive median short-term participation, a "
        "liquid leader in that cohort may capture synchronized sponsorship "
        "rather than generic single-name momentum."
    ),
    "2_history_check": {
        "exp-20260608-008": (
            "Accepted stable industry core-flow. This run does not retune that "
            "helper; it tests breadth expansion without a same-day core-flow "
            "anchor."
        ),
        "exp-20260607-008": (
            "Accepted industry-relative laggard repair. This run is the "
            "leader side of synchronized breadth expansion, not laggard repair."
        ),
        "exp-20260613-027": (
            "Rejected weak-industry scarce leader. This run tests the opposite "
            "relation: internal breadth broadening."
        ),
        "exp-20260614-028": (
            "Rejected multi-peer edge stability due old_thin/drawdown. This "
            "run uses industry breadth rather than peer-edge correlation."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least 20 paper trades "
        "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted relation comparators beaten. "
        "Replay-only positives are leads until shared daily/backtest parity "
        "exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260616_011_industry_breadth_expansion_leader.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _configure_globals() -> None:
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
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.OUT_DIR = OUT_DIR
    sleeve.OUT_JSON = OUT_JSON
    sleeve.LOG_JSON = LOG_JSON
    sleeve.TICKET_JSON = TICKET_JSON
    sleeve.CARD_MD = CARD_MD


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    return prior._sma(rows, idx, lookback)


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


def _industry_key(meta: dict[str, Any]) -> str:
    industry = str(meta.get("industry") or "").strip()
    sector = str(meta.get("sector") or "").strip()
    return industry or f"sector::{sector}"


def _industry_groups(
    sector_entries: dict[str, dict[str, Any]],
    available_tickers: set[str],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for ticker, meta in sector_entries.items():
        if ticker not in available_tickers:
            continue
        key = _industry_key(meta)
        if not key or key == "sector::":
            continue
        groups.setdefault(key, []).append(ticker)
    return {
        key: sorted(tickers)
        for key, tickers in groups.items()
        if len(tickers) >= MIN_INDUSTRY_LIQUID_MEMBERS
    }


def _member_features(
    *,
    rows: list[dict[str, Any]],
    idx: int,
    prior_idx: int,
) -> dict[str, Any] | None:
    close = framework._value(rows[idx], "Close")
    prior_close = framework._value(rows[prior_idx], "Close")
    if close is None or prior_close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    sma20 = _sma(rows, idx, 20)
    prior_sma20 = _sma(rows, prior_idx, 20)
    if None in (ret5, ret20, sma20, prior_sma20):
        return None
    return {
        "ret5": float(ret5),
        "ret20": float(ret20),
        "above_sma20": float(close) > float(sma20),
        "prior_above_sma20": float(prior_close) > float(prior_sma20),
    }


def _industry_contexts_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    industry_groups: dict[str, list[str]],
    signal_date: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    contexts: dict[str, dict[str, Any]] = {}
    scan = {
        "industry_groups_scanned": len(industry_groups),
        "industry_groups_with_liquid_members": 0,
        "industry_groups_passing_breadth_expansion": 0,
    }
    for key, tickers in industry_groups.items():
        members: list[dict[str, Any]] = []
        for ticker in tickers:
            rows = snapshot.get(ticker) or []
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None or idx < 65:
                continue
            features = _member_features(rows=rows, idx=idx, prior_idx=idx - 5)
            if features is not None:
                members.append(features)
        if len(members) < MIN_INDUSTRY_LIQUID_MEMBERS:
            continue
        scan["industry_groups_with_liquid_members"] += 1
        ret5_values = [row["ret5"] for row in members]
        ret20_values = [row["ret20"] for row in members]
        current_breadth = sum(1 for row in members if row["above_sma20"]) / len(members)
        prior_breadth = sum(1 for row in members if row["prior_above_sma20"]) / len(members)
        breadth_improvement = current_breadth - prior_breadth
        positive_ret5_fraction = sum(1 for value in ret5_values if value > 0.0) / len(ret5_values)
        median_ret5 = float(median(ret5_values))
        median_ret20 = float(median(ret20_values))
        dispersion = _stdev(ret5_values)
        if dispersion is None:
            continue
        passed = (
            current_breadth >= MIN_CURRENT_ABOVE_SMA20_FRACTION
            and prior_breadth <= MAX_PRIOR5_ABOVE_SMA20_FRACTION
            and breadth_improvement >= MIN_BREADTH_IMPROVEMENT
            and positive_ret5_fraction >= MIN_INDUSTRY_POSITIVE_RET5_FRACTION
            and median_ret5 >= MIN_INDUSTRY_MEDIAN_RET5
            and MIN_INDUSTRY_MEDIAN_RET20 <= median_ret20 <= MAX_INDUSTRY_MEDIAN_RET20
            and dispersion >= MIN_INDUSTRY_RET5_DISPERSION
        )
        if not passed:
            continue
        scan["industry_groups_passing_breadth_expansion"] += 1
        sector = sector_entries[tickers[0]].get("sector")
        contexts[key] = {
            "date": signal_date,
            "industry_key": key,
            "sector": sector,
            "liquid_member_count": len(members),
            "current_above_sma20_fraction": round(current_breadth, 6),
            "prior5_above_sma20_fraction": round(prior_breadth, 6),
            "breadth_improvement": round(breadth_improvement, 6),
            "positive_ret5_fraction": round(positive_ret5_fraction, 6),
            "industry_median_ret5": round(median_ret5, 6),
            "industry_median_ret20": round(median_ret20, 6),
            "industry_ret5_dispersion": round(dispersion, 6),
            "expansion_score": round(
                0.9 * breadth_improvement
                + 0.6 * median_ret5
                + 0.25 * positive_ret5_fraction
                + 0.15 * dispersion,
                6,
            ),
            "rule_version": RULE_VERSION,
        }
    return contexts, scan


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 65 or spy_idx < 65:
        return None
    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    signal_return = framework._daily_return(rows, idx)
    if None in (ret5, ret20, ret60, spy_ret20, spy_ret60, signal_return):
        return None
    ret5 = float(ret5)
    ret20 = float(ret20)
    ret60 = float(ret60)
    spy_ret20 = float(spy_ret20)
    spy_ret60 = float(spy_ret60)
    signal_return = float(signal_return)
    ret5_vs_industry = ret5 - float(context["industry_median_ret5"])
    ret20_vs_industry = ret20 - float(context["industry_median_ret20"])
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if not (MIN_LEADER_RET5 <= ret5 <= MAX_LEADER_RET5):
        return None
    if ret5_vs_industry < MIN_RET5_VS_INDUSTRY_MEDIAN:
        return None
    if ret20_vs_industry < MIN_RET20_VS_INDUSTRY_MEDIAN:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    sma20 = _sma(rows, idx, 20)
    sma50 = _sma(rows, idx, 50)
    if sma20 is None or sma50 is None or sma20 <= 0 or sma50 <= 0:
        return None
    sma20_ratio = float(close) / float(sma20)
    sma50_ratio = float(close) / float(sma50)
    if sma20_ratio < MIN_SMA20_RATIO or sma50_ratio < MIN_SMA50_RATIO:
        return None
    volume_ratio = framework._volume_ratio(rows, idx)
    if (
        volume_ratio is None
        or volume_ratio < MIN_VOLUME_RATIO_20D
        or volume_ratio > MAX_VOLUME_RATIO_20D
    ):
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    expansion_score = float(context["expansion_score"])
    score = (
        0.75 * expansion_score
        + 0.65 * ret20_excess_spy
        + 0.45 * ret5_vs_industry
        + 0.35 * ret20_vs_industry
        + 0.20 * ret60_excess_spy
        + 0.14 * float(close_location)
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.45 * float(realized_vol)
        - 0.25 * max(ret5 - 0.08, 0.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "INDUSTRY_BREADTH_EXPANSION_LEADER_PAPER",
        "candidate_score": round(score, 6),
        "industry_context": context,
        "industry_key": context["industry_key"],
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "ret5": round(ret5, 6),
        "ret20": round(ret20, 6),
        "ret60": round(ret60, 6),
        "industry_median_ret5": context["industry_median_ret5"],
        "industry_median_ret20": context["industry_median_ret20"],
        "ret5_vs_industry_median": round(ret5_vs_industry, 6),
        "ret20_vs_industry_median": round(ret20_vs_industry, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "signal_return": round(signal_return, 6),
        "close_location": round(float(close_location), 6),
        "sma20_ratio": round(sma20_ratio, 6),
        "sma50_ratio": round(sma50_ratio, 6),
        "avg_dollar_volume_20d": round(float(adv20), 2),
        "volume_ratio_20d": round(float(volume_ratio), 6),
        "realized_vol_20d": round(float(realized_vol), 6),
        "uses_free_ohlcv": True,
        "uses_llm": False,
        "trade_enabled": False,
        "rule_version": RULE_VERSION,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    industry_groups = _industry_groups(sector_entries, set(snapshot))
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    context_samples: list[dict[str, Any]] = []
    scan: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "industry_group_count": len(industry_groups),
        "industry_breadth_expansion_days": 0,
        "passed_industry_context_count": 0,
        "raw_candidate_count": 0,
        "sector_known_loaded_tickers": len(sector_entries),
    }
    for signal_date in dates:
        contexts, context_scan = _industry_contexts_for_day(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            industry_groups=industry_groups,
            signal_date=signal_date,
        )
        if not contexts:
            continue
        scan["industry_breadth_expansion_days"] += 1
        scan["passed_industry_context_count"] += len(contexts)
        scan.setdefault("industry_groups_with_liquid_members_total", 0)
        scan["industry_groups_with_liquid_members_total"] += context_scan[
            "industry_groups_with_liquid_members"
        ]
        if len(context_samples) < 200:
            context_samples.extend(list(contexts.values())[: max(0, 200 - len(context_samples))])
        for industry_key, context in contexts.items():
            for ticker in industry_groups.get(industry_key, []):
                row = _candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    context=context,
                )
                if row is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(ab_entries)
                row["same_day_ab_overlap"] = bool(ab_entries)
                row["same_ticker_ab_overlap"] = any(
                    trade.get("ticker") == ticker for trade in ab_entries
                )
                candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["ret20_excess_spy"]),
            -float(row["ret5_vs_industry_median"]),
            -float(row["avg_dollar_volume_20d"]),
            str(row.get("industry_key") or ""),
            row["ticker"],
        )
    )
    scan["raw_candidate_count"] = len(candidates)
    return candidates, context_samples, scan


def _comparator_readout(aggregate: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    observed_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    observed_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    for key, comparator in ACCEPTED_COMPARATORS.items():
        required_ev = float(comparator["aggregate_expected_value_delta"])
        required_pnl = float(comparator["aggregate_pnl_delta"])
        out[key] = {
            "note": comparator["note"],
            "required_ev_delta": required_ev,
            "required_pnl_delta": required_pnl,
            "observed_ev_delta": round(observed_ev, 6),
            "observed_pnl_delta": round(observed_pnl, 2),
            "passed": observed_ev >= required_ev and observed_pnl >= required_pnl,
        }
    return out


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    comparator_readout: dict[str, Any],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    for key, readout in comparator_readout.items():
        if not readout["passed"]:
            failed.append(f"{key}_not_beaten")
    return {
        "passed": not failed,
        "decision": (
            "positive_replay_lead_not_promoted_industry_breadth_expansion_leader"
            if not failed
            else "rejected_industry_breadth_expansion_leader_candidate_pool"
        ),
        "failed_reasons": failed,
        "accepted_comparator_checks": comparator_readout,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
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


def _build_payload() -> dict[str, Any]:
    _configure_globals()
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_samples_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and industry breadth-expansion replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=set(sector_entries))
        sector_entries_in_snapshot = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries_in_snapshot),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        candidates, context_samples, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries_in_snapshot,
        )
        selected_trades, filtered_candidates = framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_samples_by_window[label] = context_samples
        scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "industry_breadth_expansion_day_count": scan["industry_breadth_expansion_days"],
            "passed_industry_context_count": scan["passed_industry_context_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    comparator_readout = _comparator_readout(aggregate)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        comparator_readout=comparator_readout,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    if gate4["passed"]:
        reflection = {
            "why_result_happened": (
                "The breadth-expansion relation added multi-window replacement "
                "value, but this remains a replay lead because no shared daily "
                "helper or forward rows exist."
            ),
            "realized_failure_mode": "none_numeric_gate4_passed",
            "forbidden_near_neighbor_retry": (
                "Do not retune breadth-expansion fractions, SMA lookbacks, "
                "leader strength, volume, hold, cooldown, top-N, or notional "
                "on these frozen windows."
            ),
            "new_evidence_required": (
                "Promotion requires a shared default-off helper, daily snapshot "
                "parity, and closed forward replacement rows tagged with "
                "industry breadth-expansion state."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "Industry breadth expansion did not add enough replacement "
                "value after next-open execution and accepted relation "
                "comparators. The field likely still relabeled crowded "
                "industry momentum rather than a distinct relation edge."
            ),
            "realized_failure_mode": "industry_breadth_expansion_generic_momentum_relabel",
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping current/prior breadth fractions, "
                "SMA lookbacks, industry median return thresholds, leader "
                "strength thresholds, close-location, volume, hold-day, "
                "notional, cooldown, or top-N on these frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs materially new PIT flow/ownership/borrow/"
                "options evidence or forward replacement rows showing breadth "
                "expansion beats accepted industry relation helpers."
            ),
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "mechanism_family": "production_visible_free_ohlcv_relation_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260613-027",
            "exp-20260608-008",
            "exp-20260607-008",
            "exp-20260614-028",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_intra_industry_breadth_expansion_relation_field",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV and sector-map industry "
                "membership available on the signal date. Industry breadth "
                "expansion and leader features are known after the signal "
                "close. Paper entry is next available open; exit is the close "
                "10 trading days after signal with existing cost assumptions."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_industry_liquid_members": MIN_INDUSTRY_LIQUID_MEMBERS,
            "min_current_above_sma20_fraction": MIN_CURRENT_ABOVE_SMA20_FRACTION,
            "max_prior5_above_sma20_fraction": MAX_PRIOR5_ABOVE_SMA20_FRACTION,
            "min_breadth_improvement": MIN_BREADTH_IMPROVEMENT,
            "min_industry_positive_ret5_fraction": MIN_INDUSTRY_POSITIVE_RET5_FRACTION,
            "min_industry_median_ret5": MIN_INDUSTRY_MEDIAN_RET5,
            "min_industry_median_ret20": MIN_INDUSTRY_MEDIAN_RET20,
            "max_industry_median_ret20": MAX_INDUSTRY_MEDIAN_RET20,
            "min_industry_ret5_dispersion": MIN_INDUSTRY_RET5_DISPERSION,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "data/reference/broad_market_sector_map.json industry/sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "core_candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The industry "
                "breadth-expansion source is additive replay-only paper, so "
                "core signals generated/survived are unchanged."
            ),
        },
        "gate4": gate4,
        "accepted_comparators": ACCEPTED_COMPARATORS,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "scan_by_window": scan_by_window,
        "industry_context_samples_by_window": context_samples_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": reflection["why_result_happened"],
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": reflection,
        "negative_reflection": reflection["why_result_happened"] if not gate4["passed"] else None,
        "next_evidence_needed": reflection["new_evidence_required"],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Expansion days | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | ${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | {dd:+.4f} | {days} | {raw} | {trades} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                delta_ev=row["delta"]["expected_value_score"],
                before_pnl=row["before"]["total_pnl"],
                after_pnl=row["after"]["total_pnl"],
                delta_pnl=row["delta"]["total_pnl"],
                dd=row["delta"]["max_drawdown_pct"],
                days=row["industry_breadth_expansion_day_count"],
                raw=row["raw_candidate_count"],
                trades=row["target_trade_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Breadth-Expansion Leader",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4 Three-Window Readout",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
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
        "production_accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
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
                "pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "target_trade_count": payload["window_rows"][label]["target_trade_count"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "industry_breadth_expansion_day_count": payload["scan_by_window"][label][
                    "industry_breadth_expansion_days"
                ],
                "passed_industry_context_count": payload["scan_by_window"][label][
                    "passed_industry_context_count"
                ],
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": payload["pre_run_questions"],
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": bool(payload.get("gate4", {}).get("passed")),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
            _repo_rel(REGISTRY_JSON): framework._sha256(REGISTRY_JSON),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
