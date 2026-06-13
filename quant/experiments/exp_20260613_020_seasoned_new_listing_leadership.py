"""exp-20260613-020: seasoned new-listing leadership candidate pool.

Replay-only alpha search. It tests one free-OHLCV candidate source: liquid,
sector-known common stocks whose warehouse first-seen date is observable after
the left-censor boundary, have aged past the earliest listing-noise phase, and
show broad relative strength leadership.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
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

EXPERIMENT_ID = "exp-20260613-020"
STEM = "seasoned_new_listing_leadership"
TRIAL_FAMILY = "seasoned_new_listing_leadership_candidate_pool"
TRIAL_VARIANT_ID = "seasoned_new_listing_leadership_candidate_source_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_020_{STEM}.json"
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

MIN_FIRST_SEEN_AGE_TRADING_DAYS = 63
MAX_FIRST_SEEN_AGE_TRADING_DAYS = 504
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 20_000_000.0
MIN_RET20_EXCESS_SPY = -0.010
MIN_RET60_EXCESS_SPY = 0.050
MIN_CLOSE_VS_HIGH60 = -0.080
MIN_SIGNAL_CLOSE_LOCATION = 0.45
MIN_SIGNAL_RETURN = -0.020
MAX_SIGNAL_RETURN = 0.070
MIN_VOLUME_RATIO_20D = 0.25
MAX_VOLUME_RATIO_20D = 4.00
MAX_REALIZED_VOL_20D = 0.140
MAX_RET5 = 0.250
MIN_MA20_RATIO = 0.985
MIN_MA50_RATIO = 0.970
EXCLUDED_COMMON_SHARE_SUFFIXES = ("U", "W")

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
        "observable_first_seen_sample_too_small",
        "generic_momentum_relabel",
        "window_regression",
        "old_thin_listing_coverage_gap",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Static recent-listing/platform cohorts failed because they were hand "
        "lists with negative forward returns, but PIT warehouse first-seen age "
        "over a broad liquid universe is materially different and can expand "
        "the candidate pool without adding arbitrary noisy tickers. Risk is "
        "high because left-censor exclusion makes the sample sparse and the "
        "remaining signal may still relabel momentum."
    ),
    "recorded_at": "2026-06-13T15:26:30Z",
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
        "liquidity_source": "price >= $10 and ADV20 >= $20M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing OHLCV, SPY pair, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "warehouse first-seen left-censor exclusion, first-seen age, common-share "
        "shape, liquidity, relative-strength, moving-average, close-location, "
        "same-ticker core-overlap exclusion, cooldown, next-open paper entry, "
        "10-trading-day exit, costs, and concentration controls in both "
        "historical replay and the daily production snapshot."
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_date(value: str) -> datetime:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d")


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _patch_framework_globals() -> None:
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


def _common_share_shape(ticker: str) -> bool:
    ticker = str(ticker or "").upper()
    if not ticker.isalpha():
        return False
    if len(ticker) > 5:
        return False
    if ticker.endswith(EXCLUDED_COMMON_SHARE_SUFFIXES):
        return False
    return True


def _warehouse_first_seen_audit(sector_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    with sqlite3.connect(framework.WAREHOUSE) as con:
        rows = [
            (str(ticker).upper(), str(first)[:10], str(last)[:10], int(count))
            for ticker, first, last, count in con.execute(
                "select ticker, min(date), max(date), count(*) from ohlcv group by ticker"
            )
        ]
    first_by_ticker = {ticker: first for ticker, first, _last, _count in rows}
    boundary = min(first_by_ticker.values()) if first_by_ticker else None
    sector_known = sorted(ticker for ticker in sector_entries if ticker in first_by_ticker)
    observable = [
        ticker
        for ticker in sector_known
        if boundary is not None
        and first_by_ticker[ticker] > boundary
        and _common_share_shape(ticker)
    ]
    return {
        "source": _repo_rel(framework.WAREHOUSE),
        "warehouse_ticker_count": len(rows),
        "sector_known_ticker_count": len(sector_known),
        "global_first_seen_left_censor_boundary": boundary,
        "left_censored_sector_known_count": sum(
            1 for ticker in sector_known if first_by_ticker[ticker] == boundary
        ),
        "observable_post_boundary_common_share_count": len(observable),
        "observable_post_boundary_common_share_examples": observable[:40],
        "first_seen_tail_examples": sorted(
            (
                {
                    "ticker": ticker,
                    "first_seen": first,
                    "last_seen": last,
                    "row_count": count,
                }
                for ticker, first, last, count in rows
                if first != boundary and _common_share_shape(ticker)
            ),
            key=lambda row: (row["first_seen"], row["ticker"]),
        )[-40:],
    }


def _load_deep_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
    left_censor_boundary: str | None,
) -> dict[str, list[dict[str, Any]]]:
    if left_censor_boundary is None:
        start = _parse_date(cfg["start"]) - timedelta(days=760)
    else:
        start = _parse_date(left_censor_boundary)
    end = _parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(framework.WAREHOUSE) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, start.date().isoformat(), end.date().isoformat()]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _avg_close(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    values = [framework._value(row, "Close") for row in rows[idx - lookback + 1 : idx + 1]]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None) / len(values)


def _high_watermark(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    highs = [framework._value(row, "High") for row in rows[idx - lookback + 1 : idx + 1]]
    if any(value is None for value in highs):
        return None
    return max(float(value) for value in highs if value is not None)


def _age_bucket(age_trading_days: int) -> str:
    if age_trading_days < 126:
        return "post_earliest_phase_63_125d"
    if age_trading_days < 252:
        return "first_public_year_126_251d"
    return "second_public_year_252_504d"


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    left_censor_boundary: str | None,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 60 or spy_idx < 60:
        return None
    if not _common_share_shape(ticker):
        return None

    first_seen = shadow._date(rows[0])
    if left_censor_boundary is not None and first_seen <= left_censor_boundary:
        return None
    age_trading_days = idx
    if age_trading_days < MIN_FIRST_SEEN_AGE_TRADING_DAYS:
        return None
    if age_trading_days > MAX_FIRST_SEEN_AGE_TRADING_DAYS:
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
    if None in (ret5, ret20, ret60, spy_ret20, spy_ret60):
        return None
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if float(ret5) > MAX_RET5:
        return None

    signal_return = framework._daily_return(rows, idx)
    if signal_return is None:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None

    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None

    volume_ratio = framework._volume_ratio(rows, idx)
    if volume_ratio is None:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None

    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    ma20 = _avg_close(rows, idx, 20)
    ma50 = _avg_close(rows, idx, 50)
    if ma20 is None or ma20 <= 0 or ma50 is None or ma50 <= 0:
        return None
    ma20_ratio = close / ma20
    ma50_ratio = close / ma50
    if ma20_ratio < MIN_MA20_RATIO or ma50_ratio < MIN_MA50_RATIO:
        return None

    high60 = _high_watermark(rows, idx, 60)
    if high60 is None or high60 <= 0:
        return None
    close_vs_high60 = (close / high60) - 1.0
    if close_vs_high60 < MIN_CLOSE_VS_HIGH60:
        return None

    age_calendar_days = (_parse_date(signal_date) - _parse_date(first_seen)).days
    liquidity_score = min(math.log10(max(adv20, 1.0) / MIN_AVG_DOLLAR_VOLUME_20D), 2.0)
    age_midpoint = (MIN_FIRST_SEEN_AGE_TRADING_DAYS + MAX_FIRST_SEEN_AGE_TRADING_DAYS) / 2.0
    age_penalty = abs(age_trading_days - age_midpoint) / age_midpoint
    extension_penalty = max(0.0, float(ret5) - 0.08)
    volume_penalty = max(0.0, float(volume_ratio) - 2.0) * 0.05
    score = (
        1.35 * ret60_excess_spy
        + 0.70 * ret20_excess_spy
        + 0.35 * float(close_location)
        + 0.18 * (1.0 + close_vs_high60)
        + 0.08 * liquidity_score
        - 0.40 * float(realized_vol)
        - 0.12 * age_penalty
        - 0.30 * extension_penalty
        - volume_penalty
    )

    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SEASONED_NEW_LISTING_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "first_seen_date": first_seen,
        "first_seen_age_trading_days": age_trading_days,
        "first_seen_age_calendar_days": age_calendar_days,
        "first_seen_age_bucket": _age_bucket(age_trading_days),
        "left_censor_boundary_excluded": left_censor_boundary,
        "signal_return": round(signal_return, 6),
        "signal_close_location": round(close_location, 6),
        "signal_volume_ratio_20d": round(volume_ratio, 6),
        "ret5": round(float(ret5), 6),
        "ret20": round(float(ret20), 6),
        "ret60": round(float(ret60), 6),
        "spy_ret20": round(float(spy_ret20), 6),
        "spy_ret60": round(float(spy_ret60), 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "realized_vol_20d": round(realized_vol, 6),
        "ma20_ratio": round(ma20_ratio, 6),
        "ma50_ratio": round(ma50_ratio, 6),
        "close_vs_high60": round(close_vs_high60, 6),
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
    left_censor_boundary: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    eligible = {
        ticker: meta
        for ticker, meta in sector_entries.items()
        if ticker in snapshot and _common_share_shape(ticker)
    }
    first_seen_by_ticker = {
        ticker: shadow._date(snapshot[ticker][0])
        for ticker in eligible
        if snapshot.get(ticker)
    }
    observable = {
        ticker: meta
        for ticker, meta in eligible.items()
        if left_censor_boundary is None or first_seen_by_ticker.get(ticker, "") > left_censor_boundary
    }
    candidates: list[dict[str, Any]] = []
    audit: dict[str, Any] = {
        "scanned_trading_days": len(dates),
        "sector_known_common_share_tickers": len(eligible),
        "left_censored_common_share_tickers": len(eligible) - len(observable),
        "observable_post_boundary_common_share_tickers": len(observable),
        "candidate_counts_by_age_bucket": Counter(),
        "candidate_day_count": 0,
    }
    for signal_date in dates:
        for ticker in observable:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=observable,
                ticker=ticker,
                signal_date=signal_date,
                left_censor_boundary=left_censor_boundary,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            audit["candidate_counts_by_age_bucket"][row["first_seen_age_bucket"]] += 1
            candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["ret60_excess_spy"]),
            -float(row["ret20_excess_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    audit["candidate_counts_by_age_bucket"] = dict(audit["candidate_counts_by_age_bucket"])
    audit["candidate_day_count"] = len({row["date"] for row in candidates})
    return candidates, audit


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _comparator_checks(aggregate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ev_delta = float(aggregate.get("expected_value_score_delta_sum") or 0.0)
    pnl_delta = float(aggregate.get("total_pnl_delta_sum") or 0.0)
    checks: dict[str, dict[str, Any]] = {}
    for name, comparator in ACCEPTED_COMPARATORS.items():
        ev_required = float(comparator["aggregate_expected_value_delta"])
        pnl_required = float(comparator["aggregate_pnl_delta"])
        checks[name] = {
            "passed": ev_delta > ev_required and pnl_delta > pnl_required,
            "required_ev_delta": ev_required,
            "observed_ev_delta": _round(ev_delta, 6),
            "required_pnl_delta": pnl_required,
            "observed_pnl_delta": _round(pnl_delta, 2),
            "note": comparator["note"],
        }
    return checks


def _build_payload() -> dict[str, Any]:
    _patch_framework_globals()
    timestamp = _utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries_all = framework._load_sector_entries()
    first_seen_audit = _warehouse_first_seen_audit(sector_entries_all)
    left_censor_boundary = first_seen_audit["global_first_seen_left_censor_boundary"]

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    scan_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and seasoned new-listing leadership replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = _load_deep_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
            left_censor_boundary=left_censor_boundary,
        )
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "left_censor_boundary": left_censor_boundary,
        }
        candidates, scan_audit = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
            left_censor_boundary=left_censor_boundary,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
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
        scan_audit_by_window[label] = scan_audit
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "candidate_day_count": scan_audit["candidate_day_count"],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate4["accepted_comparator_checks"] = _comparator_checks(aggregate)
    if gate4["passed"] and not gate4["accepted_comparator_checks"][
        "exp-20260608-013_narrow_range_compression"
    ]["passed"]:
        gate4["passed"] = False
        gate4["failed_reasons"].append("accepted_compression_comparator_not_beaten")
    gate4["decision"] = (
        "positive_replay_lead_not_promoted_seasoned_new_listing_leadership"
        if gate4["passed"]
        else "rejected_seasoned_new_listing_leadership_candidate_pool"
    )

    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "accepted" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    if gate4["passed"]:
        reflection = {
            "why_result_happened": (
                "Observable newly added liquid common stocks that matured past "
                "the first 63 trading days retained enough post-listing relative "
                "strength to add replacement value across all canonical windows."
            ),
            "realized_failure_mode": "none_gate4_passed",
            "forbidden_near_neighbor_retry": (
                "Do not retune age, liquidity, ranking, notional, hold, or "
                "cooldown on the same frozen windows; promote only through a "
                "shared default-off helper and daily parity snapshot."
            ),
            "new_evidence_required": (
                "Promotion requires shared historical and daily helper parity, "
                "plus forward paper rows from the same first-seen-age source."
            ),
        }
    elif "target_sample_too_small" in gate4["failed_reasons"]:
        reflection = {
            "why_result_happened": (
                "The conservative left-censor exclusion avoided fake IPO-age "
                "knowledge but left too few liquid sector-known common-share "
                "candidates across the three windows. This data edge is not "
                "yet broad enough for a canonical candidate-pool alpha."
            ),
            "realized_failure_mode": "observable_first_seen_sample_too_small",
            "forbidden_near_neighbor_retry": (
                "Do not loosen this into boundary-first-seen pseudo-listing age "
                "or add arbitrary noisy tickers. A retry needs a real PIT listing "
                "or IPO date source, or a materially broader free candidate pool."
            ),
            "new_evidence_required": (
                "Add a free PIT listing-date/company metadata source, or use a "
                "different candidate-pool alpha with complete three-window coverage."
            ),
        }
    else:
        reflection = {
            "why_result_happened": (
                "The observable first-seen leadership field mostly selected "
                "crowded young momentum names. It produced enough candidates, "
                "but the 10-day replacement value did not clear the three-window "
                "Gate 4 drawdown, PnL, EV, and comparator standards."
            ),
            "realized_failure_mode": "generic_momentum_relabel_or_window_regression",
            "forbidden_near_neighbor_retry": (
                "Do not retry nearby age, RS, moving-average, close-location, "
                "ADV, hold-day, notional, or cooldown variants on the same "
                "frozen windows without a materially new PIT information field."
            ),
            "new_evidence_required": (
                "A retry needs an independent free data edge, such as true "
                "listing date, lockup/float change, revenue revision, or "
                "sponsorship confirmation, rather than OHLCV threshold nudges."
            ),
        }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Liquid common stocks newly observable in the warehouse may become "
            "more tradeable after the first 63 trading days, when early listing "
            "noise has settled but before the first-seen edge fully decays. A "
            "PIT first-seen age plus relative-strength leadership filter may "
            "expand the candidate pool without adding arbitrary noisy tickers."
        ),
        "change_type": "default_off_paper_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool_expansion",
        "nearby_prior_experiments": [
            "exp-20260502-008",
            "exp-20260613-016",
            "exp-20260613-018",
            "exp-20260613-019",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_warehouse_first_seen_age_plus_free_ohlcv_leadership_field",
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
                "Signal uses only close-of-day OHLCV and warehouse first-seen "
                "state observable on the signal date. Paper entry is next "
                "available open with existing entry slippage; exit is the close "
                "10 trading days after the signal with target-side sell slippage "
                "and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_first_seen_age_trading_days": MIN_FIRST_SEEN_AGE_TRADING_DAYS,
            "max_first_seen_age_trading_days": MAX_FIRST_SEEN_AGE_TRADING_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_close_vs_high60": MIN_CLOSE_VS_HIGH60,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "max_ret5": MAX_RET5,
            "min_ma20_ratio": MIN_MA20_RATIO,
            "min_ma50_ratio": MIN_MA50_RATIO,
            "excluded_common_share_suffixes": EXCLUDED_COMMON_SHARE_SUFFIXES,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool alpha: post-earliest-phase newly observable "
                "liquid common-share leaders may add replacement value without "
                "arbitrary noisy ticker expansion."
            ),
            "2_history_check": {
                "exp-20260502-008": (
                    "Observed-only static recent-listing/platform cohort failed "
                    "with negative forward returns. This run is different: PIT "
                    "warehouse first-seen age over the broad sector-known universe, "
                    "not a hand-picked static list."
                ),
                "exp-20260613-016": (
                    "Rejected overnight absorption leadership; this run does not "
                    "use overnight/intraday decomposition."
                ),
                "exp-20260613-018": (
                    "Rejected SPY residual compression breakout; this run uses "
                    "first-seen age plus leadership, not residual-vol compression."
                ),
                "exp-20260613-019": (
                    "Rejected post-thrust pause quality; this run avoids post-thrust "
                    "pause/reclaim threshold retuning."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
                "must be positive, no window EV/PnL regression, at least 20 paper "
                "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
                "concentration pass, and accepted compression comparator should be "
                "beaten for promotion. Positive replay-only output is a lead until "
                "shared parity exists."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260613_020_seasoned_new_listing_leadership.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "warehouse per-ticker first_seen date from ohlcv min(date)",
                "SPY daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate source "
                "is additive replay-only paper, so core signals and survival are "
                "unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "first_seen_audit": first_seen_audit,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "scan_audit_by_window": scan_audit_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The seasoned new-listing leadership candidate source cleared Gate 4 "
            "as a replay-only/default-off lead, but no production surface was promoted."
            if gate4["passed"]
            else (
                "The seasoned new-listing leadership candidate source did not clear "
                "Gate 4. Do not promote or retry nearby first-seen-age/RS threshold "
                "variants on the same frozen windows without materially new PIT evidence."
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=payload["scan_audit_by_window"][label]["candidate_day_count"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Seasoned New-Listing Leadership Candidate Pool",
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
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
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
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "candidate_day_count": payload["scan_audit_by_window"][label][
                    "candidate_day_count"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
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


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(OUT_JSON),
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
