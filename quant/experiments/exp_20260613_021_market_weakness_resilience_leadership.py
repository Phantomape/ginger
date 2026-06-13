"""exp-20260613-021: market-weakness resilience leadership candidate pool.

Replay-only alpha search. It tests one free-OHLCV candidate source: liquid,
sector-known, non-ETF stocks with meaningful SPY beta that hold up on a
beta-adjusted basis during multi-day SPY/QQQ weakness.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve = framework.sleeve
get_universe = framework.get_universe

EXPERIMENT_ID = "exp-20260613-021"
STEM = "market_weakness_resilience_leadership"
TRIAL_FAMILY = "market_weakness_resilience_leadership_candidate_pool"
TRIAL_VARIANT_ID = "market_weakness_resilience_leadership_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MARKET_LOOKBACK_DAYS = 5
BETA_LOOKBACK_DAYS = 60
MIN_BETA_OBSERVATIONS = 45
MIN_SPY_BETA = 0.70
MAX_SPY_BETA = 2.30
MAX_SPY_5D_RETURN = -0.015
MAX_QQQ_5D_RETURN = -0.020
MAX_SPY_SIGNAL_RETURN = 0.010
MIN_SPY_SIGNAL_RETURN = -0.040
MIN_NEGATIVE_SPY_DAYS_5D = 2
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET5 = -0.005
MAX_RET5 = 0.140
MIN_BETA_ADJUSTED_RET5 = 0.025
MIN_RET20_EXCESS_SPY = 0.020
MIN_RET60_EXCESS_SPY = 0.030
MIN_SIGNAL_RETURN = -0.015
MAX_SIGNAL_RETURN = 0.060
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.35
MAX_VOLUME_RATIO_20D = 3.20
MAX_REALIZED_VOL_20D = 0.100

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

WINDOWS = framework.WINDOWS

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "momentum_relabel",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_comparator_not_beaten",
        "market_weakness_sample_too_small",
    ],
    "confidence_reason": (
        "Resilience during multi-day market weakness is a distinct selection "
        "axis from rejected thrust, compression, and single-day pressure "
        "sources. Requiring meaningful SPY beta tries to avoid simply buying "
        "low-beta defensive laggards, but the field may still relabel crowded "
        "relative-strength momentum."
    ),
    "recorded_at": "2026-06-13T16:22:35Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
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
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing OHLCV, SPY/QQQ pair, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "SPY/QQQ weakness context, prior SPY beta, beta-adjusted 5d resilience, "
        "liquidity gates, same-ticker core-overlap exclusion, cooldown, "
        "next-open paper entry, 10-trading-day exit, costs, and concentration "
        "controls in both historical replay and the daily production snapshot."
    ),
}

ACCEPTED_COMPARATORS = {
    "exp-20260608-013_narrow_range_compression": {
        "aggregate_expected_value_delta": 0.1608,
        "aggregate_pnl_delta": 2248.98,
        "note": "accepted shared default-off narrow-range compression breakout adapter",
    },
    "exp-20260611-007_distribution_day_absorption": {
        "aggregate_expected_value_delta": 0.5286,
        "aggregate_pnl_delta": 10432.91,
        "note": "accepted shared distribution-day absorption adapter",
    },
    "exp-20260611-005_lagged_consensus_allocator": {
        "aggregate_expected_value_delta": 2.1849,
        "aggregate_pnl_delta": 40397.21,
        "note": "accepted shared allocator source extension",
    },
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool alpha: high-beta liquid leaders that remain positive "
        "on a beta-adjusted 5d basis during SPY/QQQ weakness may indicate "
        "idiosyncratic demand rather than generic defensive exposure."
    ),
    "2_history_check": {
        "exp-20260605-033": (
            "Rejected single-day cross-section pressure resilience in all three "
            "windows. This run changes the field to multi-day SPY/QQQ weakness "
            "plus prior beta-adjusted resilience and requires meaningful beta."
        ),
        "exp-20260611-019": (
            "Rejected distribution-pressure low-beta defensive leadership. This "
            "run explicitly excludes low-beta defensive behavior by requiring "
            "SPY beta >= 0.70."
        ),
        "exp-20260613-016": (
            "Rejected overnight absorption leadership. This run avoids "
            "overnight/intraday decomposition."
        ),
        "exp-20260613-019": (
            "Rejected post-thrust pause/reclaim. This run uses market weakness "
            "resilience, not a post-thrust price-action retry."
        ),
        "exp-20260613-020": (
            "Rejected seasoned first-seen leadership due drawdown drift. This "
            "run does not use warehouse first-seen age or listing proxy fields."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least 20 paper trades "
        "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, and "
        "concentration pass. Replay-only positives are leads until shared "
        "daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_021_market_weakness_resilience_leadership.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


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
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
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
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG


def _sample_stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


def _paired_returns(
    *,
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    indices: dict[str, dict[str, int]],
    end_idx_inclusive: int,
    lookback: int,
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    spy_index = indices.get("SPY", {})
    start_idx = max(1, end_idx_inclusive - lookback + 1)
    for day_idx in range(start_idx, end_idx_inclusive + 1):
        day = str(rows[day_idx].get("Date") or rows[day_idx].get("date") or "")[:10]
        spy_idx = spy_index.get(day)
        if spy_idx is None or spy_idx < 1:
            continue
        stock_ret = framework._daily_return(rows, day_idx)
        spy_ret = framework._daily_return(spy_rows, spy_idx)
        if stock_ret is None or spy_ret is None:
            continue
        pairs.append((float(stock_ret), float(spy_ret)))
    return pairs


def _beta_to_spy(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < MIN_BETA_OBSERVATIONS:
        return None
    stock_values = [pair[0] for pair in pairs]
    spy_values = [pair[1] for pair in pairs]
    stock_mean = sum(stock_values) / len(stock_values)
    spy_mean = sum(spy_values) / len(spy_values)
    spy_variance = sum((value - spy_mean) ** 2 for value in spy_values)
    if spy_variance <= 1e-10:
        return None
    covariance = sum(
        (stock_value - stock_mean) * (spy_value - spy_mean)
        for stock_value, spy_value in zip(stock_values, spy_values)
    )
    beta = covariance / spy_variance
    if beta < MIN_SPY_BETA or beta > MAX_SPY_BETA:
        return None
    return beta


def _negative_day_count(rows: list[dict[str, Any]], idx: int, lookback: int) -> int | None:
    if idx < lookback:
        return None
    count = 0
    for day_idx in range(idx - lookback + 1, idx + 1):
        day_return = framework._daily_return(rows, day_idx)
        if day_return is None:
            return None
        if day_return < 0.0:
            count += 1
    return count


def _market_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None or spy_idx < 20 or qqq_idx < 20:
        return None
    spy_ret5 = framework._ret(spy_rows, spy_idx, MARKET_LOOKBACK_DAYS)
    qqq_ret5 = framework._ret(qqq_rows, qqq_idx, MARKET_LOOKBACK_DAYS)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    qqq_ret20 = framework._ret(qqq_rows, qqq_idx, 20)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    qqq_signal_return = framework._daily_return(qqq_rows, qqq_idx)
    negative_spy_days = _negative_day_count(spy_rows, spy_idx, MARKET_LOOKBACK_DAYS)
    if None in (
        spy_ret5,
        qqq_ret5,
        spy_ret20,
        qqq_ret20,
        spy_signal_return,
        qqq_signal_return,
        negative_spy_days,
    ):
        return None
    market_weak = float(spy_ret5) <= MAX_SPY_5D_RETURN or float(qqq_ret5) <= MAX_QQQ_5D_RETURN
    if not market_weak:
        return None
    if float(spy_signal_return) > MAX_SPY_SIGNAL_RETURN:
        return None
    if float(spy_signal_return) < MIN_SPY_SIGNAL_RETURN:
        return None
    if int(negative_spy_days) < MIN_NEGATIVE_SPY_DAYS_5D:
        return None
    weakness_score = abs(min(float(spy_ret5), float(qqq_ret5), 0.0))
    return {
        "date": signal_date,
        "spy_ret5": round(float(spy_ret5), 6),
        "qqq_ret5": round(float(qqq_ret5), 6),
        "spy_ret20": round(float(spy_ret20), 6),
        "qqq_ret20": round(float(qqq_ret20), 6),
        "spy_signal_return": round(float(spy_signal_return), 6),
        "qqq_signal_return": round(float(qqq_signal_return), 6),
        "negative_spy_days_5d": int(negative_spy_days),
        "weakness_score": round(weakness_score, 6),
        "rule_version": RULE_VERSION,
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    market_context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < max(BETA_LOOKBACK_DAYS + 1, 61) or spy_idx < 61 or qqq_idx < 61:
        return None

    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    beta_pairs = _paired_returns(
        rows=rows,
        spy_rows=spy_rows,
        indices=indices,
        end_idx_inclusive=idx - 1,
        lookback=BETA_LOOKBACK_DAYS,
    )
    beta = _beta_to_spy(beta_pairs)
    if beta is None:
        return None

    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret5 = framework._ret(spy_rows, spy_idx, 5)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    qqq_ret5 = framework._ret(qqq_rows, qqq_idx, 5)
    if None in (ret5, ret20, ret60, spy_ret5, spy_ret20, spy_ret60, qqq_ret5):
        return None
    ret5 = float(ret5)
    ret20 = float(ret20)
    ret60 = float(ret60)
    spy_ret5 = float(spy_ret5)
    spy_ret20 = float(spy_ret20)
    spy_ret60 = float(spy_ret60)
    qqq_ret5 = float(qqq_ret5)
    beta_adjusted_ret5 = ret5 - beta * spy_ret5
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    qqq_relative_ret5 = ret5 - qqq_ret5
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if beta_adjusted_ret5 < MIN_BETA_ADJUSTED_RET5:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None

    signal_return = framework._daily_return(rows, idx)
    if signal_return is None or signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    volume_ratio = framework._volume_ratio(rows, idx)
    if volume_ratio is None or volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    residual_returns = [stock_ret - beta * spy_ret for stock_ret, spy_ret in beta_pairs[-20:]]
    residual_vol_20d = _sample_stdev(residual_returns)
    if residual_vol_20d is None:
        return None

    weakness_score = float(market_context["weakness_score"])
    score = (
        1.60 * beta_adjusted_ret5
        + 0.75 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.22 * float(close_location)
        + 0.10 * weakness_score
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.55 * float(realized_vol)
        - 0.35 * residual_vol_20d
        - 0.35 * max(float(signal_return) - 0.030, 0.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "MARKET_WEAKNESS_RESILIENCE_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "market_context": market_context,
        "spy_beta_60d_prior": round(beta, 6),
        "ret5": round(ret5, 6),
        "ret20": round(ret20, 6),
        "ret60": round(ret60, 6),
        "spy_ret5": round(spy_ret5, 6),
        "spy_ret20": round(spy_ret20, 6),
        "spy_ret60": round(spy_ret60, 6),
        "qqq_ret5": round(qqq_ret5, 6),
        "beta_adjusted_ret5": round(beta_adjusted_ret5, 6),
        "qqq_relative_ret5": round(qqq_relative_ret5, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "signal_return": round(float(signal_return), 6),
        "signal_close_location": round(float(close_location), 6),
        "signal_volume_ratio_20d": round(float(volume_ratio), 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "realized_vol_20d": round(float(realized_vol), 6),
        "residual_vol_20d": round(residual_vol_20d, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    market_contexts: dict[str, dict[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    scan: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "market_weakness_days": 0,
        "raw_candidate_count": 0,
        "sector_known_loaded_tickers": len(sector_entries),
    }
    for signal_date in dates:
        context = _market_context(snapshot=snapshot, indices=indices, signal_date=signal_date)
        if context is None:
            continue
        market_contexts[signal_date] = context
        scan["market_weakness_days"] += 1
        for ticker in sector_entries:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                market_context=context,
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
            -float(row["beta_adjusted_ret5"]),
            -float(row["ret20_excess_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan["raw_candidate_count"] = len(candidates)
    return candidates, market_contexts, scan


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
    passed = not failed
    promotion_blockers = []
    if passed and not comparator_readout["exp-20260611-007_distribution_day_absorption"]["passed"]:
        promotion_blockers.append("accepted_distribution_absorption_comparator_not_beaten")
    if passed and not comparator_readout["exp-20260611-005_lagged_consensus_allocator"]["passed"]:
        promotion_blockers.append("accepted_allocator_comparator_not_beaten")
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_market_weakness_resilience"
            if passed
            else "rejected_market_weakness_resilience_leadership_candidate_pool"
        ),
        "failed_reasons": failed,
        "promotion_blockers": promotion_blockers,
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

    universe = get_universe()
    sector_entries = framework._load_sector_entries()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    market_contexts_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and market-weakness resilience replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(set(snapshot).intersection(sector_entries)),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        candidates, market_contexts, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
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
        market_contexts_by_window[label] = market_contexts
        scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "market_weakness_day_count": scan["market_weakness_days"],
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
    status = "observed_only" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"] or gate4["promotion_blockers"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    if gate4["passed"]:
        reflection = {
            "why_result_happened": (
                "The beta-adjusted resilience field found market-weakness "
                "replacement value without changing production behavior. It is "
                "only a replay lead because no shared daily helper exists."
            ),
            "realized_failure_mode": "none_numeric_gate4_passed",
            "forbidden_near_neighbor_retry": (
                "Do not retune beta, weakness, volume, hold, cooldown, or top-N "
                "on the same frozen windows. Promotion requires shared helper "
                "and forward replacement-value evidence."
            ),
            "new_evidence_required": (
                "Shared default-off helper, daily snapshot parity, and closed "
                "forward replacement rows during real market weakness."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "The field likely still relabeled relative-strength momentum "
                "during short pullbacks. Requiring meaningful beta avoided the "
                "low-beta defensive retry, but the selected rows did not clear "
                "the full three-window EV/PnL/drawdown/sample standard."
            ),
            "realized_failure_mode": "market_weakness_resilience_generic_momentum_relabel",
            "forbidden_near_neighbor_retry": (
                "Do not retry nearby SPY/QQQ weakness, beta, 5d resilience, "
                "volume, hold-day, notional, cooldown, or top-N threshold "
                "variants on these frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs a materially new PIT flow or relation "
                "field, such as options/borrow/ownership confirmation or "
                "closed forward replacement rows from a shared daily helper."
            ),
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_scout",
        "mechanism_family": "production_visible_free_ohlcv_market_weakness_resilience",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260605-033",
            "exp-20260611-019",
            "exp-20260613-016",
            "exp-20260613-019",
            "exp-20260613-020",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_beta_adjusted_market_weakness_resilience_field",
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
                "Signal uses only close-of-day OHLCV available on signal date. "
                "Market weakness and beta-adjusted resilience are known after "
                "the signal close. Paper entry is next available open with "
                "existing entry slippage; exit is the close 10 trading days "
                "after signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "market_lookback_days": MARKET_LOOKBACK_DAYS,
            "beta_lookback_days": BETA_LOOKBACK_DAYS,
            "min_spy_beta": MIN_SPY_BETA,
            "max_spy_beta": MAX_SPY_BETA,
            "max_spy_5d_return": MAX_SPY_5D_RETURN,
            "max_qqq_5d_return": MAX_QQQ_5D_RETURN,
            "min_beta_adjusted_ret5": MIN_BETA_ADJUSTED_RET5,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
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
                "QQQ daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/status",
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
                "No new core filter or entry rule was added. The market-weakness "
                "resilience source is additive replay-only paper, so core signals "
                "generated/survived are unchanged from baseline."
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
        "market_contexts_by_window": market_contexts_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The market-weakness resilience source cleared numeric Gate 4 as a "
            "replay-only lead, but no production surface was promoted."
            if gate4["passed"]
            else (
                "The market-weakness resilience source did not clear Gate 4. "
                "Do not promote or retry nearby SPY/QQQ weakness resilience "
                "threshold variants on the same frozen windows."
            )
        ),
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
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Weak days | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | ${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | {dd:+.4f} | {weak} | {raw} | {trades} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                delta_ev=row["delta"]["expected_value_score"],
                before_pnl=row["before"]["total_pnl"],
                after_pnl=row["after"]["total_pnl"],
                delta_pnl=row["delta"]["total_pnl"],
                dd=row["delta"]["max_drawdown_pct"],
                weak=row["market_weakness_day_count"],
                raw=row["raw_candidate_count"],
                trades=row["target_trade_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Market-Weakness Resilience Leadership",
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
            "- Promotion blockers: `{}`".format(
                ", ".join(payload["gate4"].get("promotion_blockers") or []) or "none"
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
                "market_weakness_day_count": payload["scan_by_window"][label][
                    "market_weakness_days"
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
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
            _repo_rel(EXPERIMENT_LOG): framework._sha256(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON): framework._sha256(REGISTRY_JSON),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
