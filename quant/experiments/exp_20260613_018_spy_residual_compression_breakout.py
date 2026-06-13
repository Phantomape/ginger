"""exp-20260613-018: SPY residual compression breakout candidate pool.

Replay-only alpha search. It tests one free-OHLCV candidate source: liquid,
sector-known stocks whose idiosyncratic return residual versus SPY compressed
over the prior window and then broke out on the signal day.

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
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260613-018"
STEM = "spy_residual_compression_breakout"
TRIAL_FAMILY = "spy_residual_compression_breakout_candidate_pool"
TRIAL_VARIANT_ID = "spy_residual_compression_breakout_candidate_source_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_018_{STEM}.json"
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

BETA_LOOKBACK_DAYS = 60
RESIDUAL_LONG_LOOKBACK_DAYS = 40
RESIDUAL_SHORT_LOOKBACK_DAYS = 10
MIN_BETA_OBSERVATIONS = 45
MIN_RESIDUAL_OBSERVATIONS = 32
MIN_BETA_TO_SPY = 0.15
MAX_BETA_TO_SPY = 2.50
MIN_PRIOR_RESIDUAL_VOL_40D = 0.010
MAX_SHORT_TO_LONG_RESIDUAL_VOL = 0.75
MIN_SIGNAL_RESIDUAL_RETURN = 0.004
MIN_SIGNAL_RESIDUAL_Z = 0.30

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = -0.015
MIN_RET60_EXCESS_SPY = -0.030
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MIN_SIGNAL_RETURN = -0.010
MAX_SIGNAL_RETURN = 0.050
MIN_VOLUME_RATIO_20D = 0.35
MAX_VOLUME_RATIO_20D = 3.00
MAX_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

WINDOWS = framework.WINDOWS

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_compression_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
        "generic_momentum_relabel",
    ],
    "confidence_reason": (
        "Accepted raw compression proves coiled OHLCV structures can work, "
        "while many tight-range and absorption neighbors failed. SPY residual "
        "compression is a materially different PIT field that may isolate "
        "stock-specific continuation, but it could still relabel momentum."
    ),
    "recorded_at": "2026-06-13T14:05:50Z",
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
        "failure_handling": "missing OHLCV, SPY pair, or next-open/exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "SPY beta, residual-vol compression, signal residual breakout, "
        "liquidity gates, same-ticker core overlap exclusion, cooldown, "
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
        "candidate_pool alpha: after removing market beta, residual volatility "
        "compression plus a positive signal-day residual breakout may identify "
        "stock-specific accumulation not captured by raw narrow-range compression."
    ),
    "2_history_check": {
        "exp-20260608-013": (
            "Accepted shared narrow-range compression breakout: aggregate EV "
            "+0.1608 and PnL +$2,248.98. This is the binding closest comparator."
        ),
        "exp-20260610-017": (
            "Rejected compression tail-state filter. This run does not filter "
            "the accepted helper; it tests a different residual-to-SPY field."
        ),
        "exp-20260608-017": (
            "Rejected quiet tight-range accumulation. This run does not rely on "
            "raw range quietness alone."
        ),
        "exp-20260609-004": (
            "Rejected high-volume thrust plus inside-day dry-up. This run avoids "
            "post-thrust volume-dryup retuning."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least 20 paper trades "
        "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and exp-20260608-013 aggregate EV/PnL comparator "
        "must be beaten. Positive replay-only output is a lead, not production "
        "acceptance, until shared parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_018_spy_residual_compression_breakout.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_sleeve_globals() -> None:
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


def _value(row: dict[str, Any], key: str) -> float | None:
    return framework._value(row, key)


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
    ticker: str,
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
    if beta < MIN_BETA_TO_SPY or beta > MAX_BETA_TO_SPY:
        return None
    return beta


def _residual_values(pairs: list[tuple[float, float]], beta: float) -> list[float]:
    return [stock_ret - beta * spy_ret for stock_ret, spy_ret in pairs]


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    required_idx = max(BETA_LOOKBACK_DAYS + 1, RESIDUAL_LONG_LOOKBACK_DAYS + 1, 61)
    if idx < required_idx or spy_idx < required_idx:
        return None

    row = rows[idx]
    close = _value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None

    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    beta_pairs = _paired_returns(
        rows=rows,
        spy_rows=spy_rows,
        indices=indices,
        ticker=ticker,
        end_idx_inclusive=idx - 1,
        lookback=BETA_LOOKBACK_DAYS,
    )
    beta = _beta_to_spy(beta_pairs)
    if beta is None:
        return None

    residual_pairs = _paired_returns(
        rows=rows,
        spy_rows=spy_rows,
        indices=indices,
        ticker=ticker,
        end_idx_inclusive=idx - 1,
        lookback=RESIDUAL_LONG_LOOKBACK_DAYS,
    )
    if len(residual_pairs) < MIN_RESIDUAL_OBSERVATIONS:
        return None
    residuals = _residual_values(residual_pairs, beta)
    if len(residuals) < RESIDUAL_SHORT_LOOKBACK_DAYS:
        return None

    long_vol = _sample_stdev(residuals)
    short_vol = _sample_stdev(residuals[-RESIDUAL_SHORT_LOOKBACK_DAYS:])
    if long_vol is None or short_vol is None or long_vol <= 0:
        return None
    residual_vol_ratio = short_vol / long_vol
    if long_vol < MIN_PRIOR_RESIDUAL_VOL_40D:
        return None
    if residual_vol_ratio > MAX_SHORT_TO_LONG_RESIDUAL_VOL:
        return None

    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    if signal_return is None or spy_signal_return is None:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None

    signal_residual_return = float(signal_return) - beta * float(spy_signal_return)
    signal_residual_z = signal_residual_return / max(short_vol, 1e-6)
    if signal_residual_return < MIN_SIGNAL_RESIDUAL_RETURN:
        return None
    if signal_residual_z < MIN_SIGNAL_RESIDUAL_Z:
        return None

    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None

    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    if None in (ret20, ret60, spy_ret20, spy_ret60):
        return None
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None

    volume_ratio = framework._volume_ratio(rows, idx)
    if volume_ratio is None:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None

    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    sector_meta = sector_entries[ticker]
    compression_bonus = max(0.0, 1.0 - residual_vol_ratio)
    score = (
        2.4 * signal_residual_return
        + 0.55 * compression_bonus
        + 0.65 * ret20_excess_spy
        + 0.20 * close_location
        + 0.03 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.55 * realized_vol
        - 0.35 * max(float(signal_return) - 0.030, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SPY_RESIDUAL_COMPRESSION_BREAKOUT_PAPER",
        "candidate_score": round(score, 6),
        "spy_beta_60d": round(beta, 6),
        "prior_residual_vol_10d": round(short_vol, 6),
        "prior_residual_vol_40d": round(long_vol, 6),
        "prior_residual_vol_10v40_ratio": round(residual_vol_ratio, 6),
        "signal_return": round(float(signal_return), 6),
        "spy_signal_return": round(float(spy_signal_return), 6),
        "signal_residual_return": round(signal_residual_return, 6),
        "signal_residual_z": round(signal_residual_z, 6),
        "ret20": round(float(ret20), 6),
        "spy_ret20": round(float(spy_ret20), 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60": round(float(ret60), 6),
        "spy_ret60": round(float(spy_ret60), 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "close_location": round(close_location, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio, 6),
        "realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": CHANGED_VARIABLE,
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
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "sector_known_loaded_tickers": len(sector_entries),
        "candidate_signal_days": 0,
        "raw_candidate_count": 0,
    }
    for signal_date in dates:
        daily_count = 0
        for ticker in sector_entries:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
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
            daily_count += 1
        if daily_count:
            scan["candidate_signal_days"] += 1
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["signal_residual_return"]),
            float(row["prior_residual_vol_10v40_ratio"]),
            -float(row["ret20_excess_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan["raw_candidate_count"] = len(candidates)
    return candidates, scan


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    filter_counts: Counter[str] = Counter()
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            reason = "missing_signal_date_position"
            filtered.append({**row, "filter_reason": reason})
            filter_counts[reason] += 1
            continue
        if row.get("same_ticker_ab_overlap"):
            reason = "same_ticker_core_overlap"
            filtered.append({**row, "filter_reason": reason})
            filter_counts[reason] += 1
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            reason = "daily_top1_limit"
            filtered.append({**row, "filter_reason": reason})
            filter_counts[reason] += 1
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            reason = "same_ticker_cooldown"
            filtered.append({**row, "filter_reason": reason})
            filter_counts[reason] += 1
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            reason = "missing_next_open_or_exit"
            filtered.append({**row, "filter_reason": reason})
            filter_counts[reason] += 1
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered, dict(sorted(filter_counts.items()))


def _comparator_readout(aggregate: dict[str, Any]) -> dict[str, Any]:
    ev_delta = float(aggregate.get("expected_value_score_delta_sum") or 0.0)
    pnl_delta = float(aggregate.get("total_pnl_delta_sum") or 0.0)
    return {
        name: {
            **row,
            "ev_delta_gap": round(ev_delta - row["aggregate_expected_value_delta"], 6),
            "pnl_delta_gap": round(pnl_delta - row["aggregate_pnl_delta"], 2),
            "beaten": (
                ev_delta > row["aggregate_expected_value_delta"]
                and pnl_delta > row["aggregate_pnl_delta"]
            ),
        }
        for name, row in ACCEPTED_COMPARATORS.items()
    }


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
    if not comparator_readout["exp-20260608-013_narrow_range_compression"]["beaten"]:
        failed.append("accepted_compression_comparator_not_beaten")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "observed_only_positive_replay_lead_spy_residual_compression"
            if passed
            else "rejected_spy_residual_compression_breakout_candidate_pool"
        ),
        "failed_reasons": failed,
        "promotion_blockers": ["replay_only_no_shared_daily_parity"] if passed else [],
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
        "accepted_comparator_readout": comparator_readout,
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
    _configure_sleeve_globals()
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    filter_counts_by_window: "OrderedDict[str, dict[str, int]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and SPY residual compression replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        eligible_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(eligible_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        candidates, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=eligible_sector_entries,
        )
        selected_trades, filtered_candidates, filter_counts = _select_paper_trades(
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
        scan_by_window[label] = scan
        filter_counts_by_window[label] = filter_counts
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_signal_days": scan["candidate_signal_days"],
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
        "failure_modes_observed": (
            gate4["failed_reasons"] or gate4.get("promotion_blockers", [])
        ),
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }

    if gate4["passed"]:
        reflection = {
            "why_result_happened": (
                "The residual-to-SPY compression field found replacement value "
                "outside raw narrow-range compression. It remains only a replay "
                "lead because no shared daily parity helper exists."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep beta lookback, residual-vol ratio, z-score, "
                "cooldown, hold days, or top-N on the same frozen windows. "
                "Next evidence must be shared-helper parity or forward rows."
            ),
            "new_evidence_required": (
                "Promotion needs a shared default-off helper, daily snapshot "
                "wiring, parity tests, and forward replacement-value rows."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "The residual compression field did not add robust replacement "
                "value beyond accepted raw compression. Any regression, "
                "drawdown drift, concentration issue, or comparator miss means "
                "the rule likely relabeled ordinary momentum or market beta "
                "rather than finding durable idiosyncratic accumulation."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry this family by only changing beta lookback, "
                "residual-vol ratio, signal residual threshold, cooldown, hold "
                "days, or daily top-N on the same frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs materially new PIT evidence, such as borrow/ETF "
                "flow, options-implied idiosyncratic pressure, or forward "
                "replacement-value rows from a shared helper."
            ),
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "free_ohlcv_spy_residual_compression_breakout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260608-013",
            "exp-20260610-017",
            "exp-20260608-017",
            "exp-20260609-004",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_spy_residual_field",
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
                "Signal uses only close-of-day OHLCV available on the signal "
                "date. SPY beta and residual compression use only prior bars; "
                "the signal-day residual is known after that close. Paper entry "
                "is next available open with existing entry slippage; exit is "
                "the close 10 trading days after signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "beta_lookback_days": BETA_LOOKBACK_DAYS,
            "residual_long_lookback_days": RESIDUAL_LONG_LOOKBACK_DAYS,
            "residual_short_lookback_days": RESIDUAL_SHORT_LOOKBACK_DAYS,
            "min_beta_observations": MIN_BETA_OBSERVATIONS,
            "min_residual_observations": MIN_RESIDUAL_OBSERVATIONS,
            "min_beta_to_spy": MIN_BETA_TO_SPY,
            "max_beta_to_spy": MAX_BETA_TO_SPY,
            "min_prior_residual_vol_40d": MIN_PRIOR_RESIDUAL_VOL_40D,
            "max_short_to_long_residual_vol": MAX_SHORT_TO_LONG_RESIDUAL_VOL,
            "min_signal_residual_return": MIN_SIGNAL_RESIDUAL_RETURN,
            "min_signal_residual_z": MIN_SIGNAL_RESIDUAL_Z,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
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
                "No new core filter or entry rule was added. The SPY residual "
                "compression source is additive default-off paper, so core "
                "signals generated/survived are unchanged from baseline."
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
        "filter_counts_by_window": filter_counts_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The SPY residual compression source cleared numeric Gate 4 as a "
            "replay-only lead, but no production surface was promoted."
            if gate4["passed"]
            else (
                "The SPY residual compression source did not clear Gate 4. Do "
                "not promote or retry this fixed residual-compression definition "
                "on the same frozen windows without materially new PIT evidence."
            )
        ),
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": reflection,
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Raw candidates | Max DD d |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | ${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | {trades} | {raw} | {dd:+.4f} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                delta_ev=row["delta"]["expected_value_score"],
                before_pnl=row["before"]["total_pnl"],
                after_pnl=row["after"]["total_pnl"],
                delta_pnl=row["delta"]["total_pnl"],
                trades=row["target_trade_count"],
                raw=row["raw_candidate_count"],
                dd=row["delta"]["max_drawdown_pct"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SPY Residual Compression Breakout",
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
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": payload["pre_run_questions"],
        "post_run_reflection": payload["post_run_reflection"],
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
