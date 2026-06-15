"""exp-20260613-027: industry contraction scarce leader candidate pool.

Replay-only alpha search. It tests one free-OHLCV relation source: when an
industry cohort is internally weak, admit the scarce liquid member that still
shows relative strength, high close location, and orderly volume.

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
from statistics import median
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

EXPERIMENT_ID = "exp-20260613-027"
STEM = "industry_contraction_scarce_leader"
TRIAL_FAMILY = "industry_contraction_scarce_leader_candidate_pool"
TRIAL_VARIANT_ID = "industry_contraction_scarce_leader_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_contraction_scarce_leader_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_027_{STEM}.json"
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

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_INDUSTRY_LIQUID_MEMBERS = 5
MIN_INDUSTRY_DOWN_FRACTION_5D = 0.55
MIN_INDUSTRY_BELOW_SMA20_FRACTION = 0.55
MAX_INDUSTRY_MEDIAN_RET5 = -0.006
MAX_INDUSTRY_MEDIAN_RET20 = 0.020
MAX_INDUSTRY_POSITIVE_RET5_FRACTION = 0.40
MIN_INDUSTRY_RET5_DISPERSION = 0.018

MIN_LEADER_RET5 = -0.005
MAX_LEADER_RET5 = 0.120
MIN_RET5_VS_INDUSTRY_MEDIAN = 0.040
MIN_RET20_VS_INDUSTRY_MEDIAN = 0.035
MIN_RET20_EXCESS_SPY = -0.005
MIN_RET60_EXCESS_SPY = 0.000
MIN_SIGNAL_RETURN = -0.015
MAX_SIGNAL_RETURN = 0.060
MIN_CLOSE_LOCATION = 0.55
MIN_SMA20_RATIO = 0.995
MIN_SMA50_RATIO = 0.970
MIN_VOLUME_RATIO_20D = 0.40
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
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "generic_momentum_relabel",
        "industry_leadership_retread",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Industry-relative relation alpha has accepted examples when the "
        "relation is the edge, but plain industry leadership and market "
        "weakness resilience failed. This tests a narrower scarcity relation "
        "inside weak cohorts using only PIT OHLCV and changes no production "
        "behavior."
    ),
    "recorded_at": "2026-06-13T19:08:22Z",
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
        "failure_handling": "missing OHLCV, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "industry grouping, contraction context, leader gates, same-ticker "
        "core-overlap exclusion, cooldown, next-open paper entry, 10-trading-"
        "day exit, costs, and concentration controls in both historical replay "
        "and the daily production snapshot."
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
        "candidate_pool alpha: when a PIT industry cohort is internally weak "
        "or below trend, a liquid member that still shows SPY-relative "
        "strength, high close location, and stable volume may represent scarce "
        "sponsorship rather than generic momentum."
    ),
    "2_history_check": {
        "exp-20260528-034": (
            "Rejected industry-leadership no-core-overlap; this run is not a "
            "plain industry leadership retry because the tested relation is "
            "industry contraction scarcity."
        ),
        "exp-20260528-035": (
            "Rejected industry leadership high close; this run uses a fixed "
            "weak-cohort context before considering close location."
        ),
        "exp-20260528-036": (
            "Rejected sector breadth market agreement; this run tests narrow "
            "intra-industry weakness, not broad breadth confirmation."
        ),
        "exp-20260613-021": (
            "Rejected market weakness beta-resilience. This run avoids SPY/QQQ "
            "weakness as the context and uses industry-local contraction."
        ),
        "exp-20260613-020": (
            "Rejected seasoned new listing leadership due drawdown/comparator "
            "risk. This run avoids first-seen age and listing proxies."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least 20 paper "
        "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "and concentration pass. Replay-only positives are leads until shared "
        "daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260613_027_industry_contraction_scarce_leader.py"
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


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = framework._value(row, "Close")
        if close is None:
            return None
        values.append(float(close))
    return sum(values) / len(values)


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
    return {key: sorted(tickers) for key, tickers in groups.items() if len(tickers) >= MIN_INDUSTRY_LIQUID_MEMBERS}


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


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
        "industry_groups_passing_contraction": 0,
    }
    for key, tickers in industry_groups.items():
        members: list[dict[str, Any]] = []
        for ticker in tickers:
            rows = snapshot.get(ticker) or []
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None or idx < 60:
                continue
            close = framework._value(rows[idx], "Close")
            if close is None or close < MIN_PRICE:
                continue
            adv20 = framework._avg_dollar_volume(rows, idx)
            if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
                continue
            ret5 = framework._ret(rows, idx, 5)
            ret20 = framework._ret(rows, idx, 20)
            sma20 = _sma(rows, idx, 20)
            sma50 = _sma(rows, idx, 50)
            if None in (ret5, ret20, sma20, sma50):
                continue
            members.append(
                {
                    "ticker": ticker,
                    "ret5": float(ret5),
                    "ret20": float(ret20),
                    "below_sma20": float(close) < float(sma20),
                    "below_sma50": float(close) < float(sma50),
                }
            )
        if len(members) < MIN_INDUSTRY_LIQUID_MEMBERS:
            continue
        scan["industry_groups_with_liquid_members"] += 1
        ret5_values = [row["ret5"] for row in members]
        ret20_values = [row["ret20"] for row in members]
        down_fraction = sum(1 for value in ret5_values if value < 0.0) / len(ret5_values)
        below_sma20_fraction = sum(1 for row in members if row["below_sma20"]) / len(members)
        below_sma50_fraction = sum(1 for row in members if row["below_sma50"]) / len(members)
        positive_ret5_fraction = sum(1 for value in ret5_values if value > 0.0) / len(ret5_values)
        median_ret5 = float(median(ret5_values))
        median_ret20 = float(median(ret20_values))
        dispersion = _stdev(ret5_values)
        if dispersion is None:
            continue
        contraction_passed = (
            (down_fraction >= MIN_INDUSTRY_DOWN_FRACTION_5D or below_sma20_fraction >= MIN_INDUSTRY_BELOW_SMA20_FRACTION)
            and median_ret5 <= MAX_INDUSTRY_MEDIAN_RET5
            and median_ret20 <= MAX_INDUSTRY_MEDIAN_RET20
            and positive_ret5_fraction <= MAX_INDUSTRY_POSITIVE_RET5_FRACTION
            and dispersion >= MIN_INDUSTRY_RET5_DISPERSION
        )
        if not contraction_passed:
            continue
        scan["industry_groups_passing_contraction"] += 1
        sector = sector_entries[tickers[0]].get("sector")
        contexts[key] = {
            "date": signal_date,
            "industry_key": key,
            "sector": sector,
            "liquid_member_count": len(members),
            "down_fraction_5d": round(down_fraction, 6),
            "below_sma20_fraction": round(below_sma20_fraction, 6),
            "below_sma50_fraction": round(below_sma50_fraction, 6),
            "positive_ret5_fraction": round(positive_ret5_fraction, 6),
            "industry_median_ret5": round(median_ret5, 6),
            "industry_median_ret20": round(median_ret20, 6),
            "industry_ret5_dispersion": round(dispersion, 6),
            "contraction_score": round(
                abs(min(median_ret5, 0.0))
                + 0.35 * down_fraction
                + 0.25 * below_sma20_fraction
                + 0.20 * dispersion,
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
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
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
    if ret5 < MIN_LEADER_RET5 or ret5 > MAX_LEADER_RET5:
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
    if volume_ratio is None or volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    contraction_score = float(context["contraction_score"])
    score = (
        1.45 * ret5_vs_industry
        + 0.85 * ret20_vs_industry
        + 0.55 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.22 * float(close_location)
        + 0.12 * contraction_score
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.55 * float(realized_vol)
        - 0.25 * max(ret5 - 0.080, 0.0)
        - 0.15 * max(float(volume_ratio) - 2.20, 0.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "INDUSTRY_CONTRACTION_SCARCE_LEADER_PAPER",
        "candidate_score": round(score, 6),
        "industry_context": context,
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
        "signal_close_location": round(float(close_location), 6),
        "signal_volume_ratio_20d": round(float(volume_ratio), 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "realized_vol_20d": round(float(realized_vol), 6),
        "sma20_ratio": round(sma20_ratio, 6),
        "sma50_ratio": round(sma50_ratio, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "industry_key": _industry_key(sector_meta),
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
        "industry_contraction_days": 0,
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
        scan["industry_contraction_days"] += 1
        scan["passed_industry_context_count"] += len(contexts)
        if len(context_samples) < 200:
            context_samples.extend(list(contexts.values())[: max(0, 200 - len(context_samples))])
        scan.setdefault("industry_groups_with_liquid_members_total", 0)
        scan["industry_groups_with_liquid_members_total"] += context_scan[
            "industry_groups_with_liquid_members"
        ]
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
            -float(row["ret5_vs_industry_median"]),
            -float(row["ret20_vs_industry_median"]),
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
    passed = not failed
    promotion_blockers = []
    if passed and not comparator_readout["exp-20260611-007_distribution_day_absorption"]["passed"]:
        promotion_blockers.append("accepted_distribution_absorption_comparator_not_beaten")
    if passed and not comparator_readout["exp-20260611-005_lagged_consensus_allocator"]["passed"]:
        promotion_blockers.append("accepted_allocator_comparator_not_beaten")
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_industry_contraction_scarce_leader"
            if passed
            else "rejected_industry_contraction_scarce_leader_candidate_pool"
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
        print(f"[{label}] core baseline and industry-contraction scarce-leader replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
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
            "industry_contraction_day_count": scan["industry_contraction_days"],
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
                "The industry-contraction scarcity relation found replacement "
                "value across the fixed windows without changing production. "
                "It is only a replay lead because no shared daily helper exists."
            ),
            "realized_failure_mode": "none_numeric_gate4_passed",
            "forbidden_near_neighbor_retry": (
                "Do not retune industry contraction, relative-strength, volume, "
                "hold, cooldown, top-N, or notional thresholds on these frozen "
                "windows. Promotion requires a shared helper and forward rows."
            ),
            "new_evidence_required": (
                "Shared default-off helper, daily snapshot parity, and closed "
                "forward replacement rows tagged with industry contraction state."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "The field likely still relabeled ordinary industry-relative "
                "momentum. Weak-cohort scarcity was not enough to overcome the "
                "existing accepted comparators and full three-window Gate 4."
            ),
            "realized_failure_mode": "industry_contraction_scarcity_generic_momentum_relabel",
            "forbidden_near_neighbor_retry": (
                "Do not retry nearby industry contraction, down-fraction, SMA, "
                "close-location, volume, hold-day, notional, cooldown, or top-N "
                "variants on these frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs a materially new PIT relation or flow field, "
                "such as borrow/options/ownership evidence or closed forward "
                "replacement rows from a shared daily helper."
            ),
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "mechanism_family": "production_visible_free_ohlcv_relation_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260528-034",
            "exp-20260528-035",
            "exp-20260528-036",
            "exp-20260613-021",
            "exp-20260613-020",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_intra_industry_contraction_scarcity_relation_field",
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
                "membership available on the signal date. Industry contraction "
                "and leader features are known after the signal close. Paper "
                "entry is next available open with existing entry slippage; "
                "exit is the close 10 trading days after signal with target-side "
                "sell slippage and ROUND_TRIP_COST_PCT."
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
            "min_industry_down_fraction_5d": MIN_INDUSTRY_DOWN_FRACTION_5D,
            "min_industry_below_sma20_fraction": MIN_INDUSTRY_BELOW_SMA20_FRACTION,
            "max_industry_median_ret5": MAX_INDUSTRY_MEDIAN_RET5,
            "max_industry_median_ret20": MAX_INDUSTRY_MEDIAN_RET20,
            "max_industry_positive_ret5_fraction": MAX_INDUSTRY_POSITIVE_RET5_FRACTION,
            "min_industry_ret5_dispersion": MIN_INDUSTRY_RET5_DISPERSION,
            "min_ret5_vs_industry_median": MIN_RET5_VS_INDUSTRY_MEDIAN,
            "min_ret20_vs_industry_median": MIN_RET20_VS_INDUSTRY_MEDIAN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_sma20_ratio": MIN_SMA20_RATIO,
            "min_sma50_ratio": MIN_SMA50_RATIO,
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
                "No new core filter or entry rule was added. The industry-"
                "contraction scarce-leader source is additive replay-only "
                "paper, so core signals generated/survived are unchanged."
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
        "interpretation": (
            "The industry-contraction scarce-leader source cleared numeric "
            "Gate 4 as a replay-only lead, but no production surface was promoted."
            if gate4["passed"]
            else (
                "The industry-contraction scarce-leader source did not clear "
                "Gate 4. Do not promote or retry nearby industry-contraction "
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Contraction days | Raw | Trades |",
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
                days=row["industry_contraction_day_count"],
                raw=row["raw_candidate_count"],
                trades=row["target_trade_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry-Contraction Scarce Leader",
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
                "industry_contraction_day_count": payload["scan_by_window"][label][
                    "industry_contraction_days"
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
