"""exp-20260526-015: sector-breadth confirmed breakout paper sleeve.

This alpha search tests one new free-OHLCV candidate-pool field: same-sector
up-volume breadth on the signal date. It is intentionally replay-only and
default-off paper. Core entries, exits, ranking, sizing, LLM/news, and live
orders are unchanged.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_volatility_contraction_breakout_shadow as ohlcv_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260526-015"
STEM = "sector_breadth_breakout_sleeve"
TRIAL_FAMILY = "sector_breadth_confirmed_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "sector_breadth_confirmed_breakout_top1_v1"
RULE_VERSION = "sector_breadth_confirmed_breakout_v1"
MARKET_BREADTH_RULE_VERSION = "volume_breadth_thrust_confirmed_breakout_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BREAKOUT_LOOKBACK_DAYS = 20
MOVING_AVERAGE_DAYS = 50
VOLUME_LOOKBACK_DAYS = 20
MIN_DOLLAR_VOLUME = 40_000_000.0
MIN_CANDIDATE_VOLUME_RATIO_20 = 1.25
MIN_SECTOR_ELIGIBLE_TICKERS = 5
MIN_SECTOR_UP_VOLUME_FRACTION = 0.20
MIN_SECTOR_MARKET_UP_FRACTION = 0.60
MIN_SECTOR_ABOVE_50D_FRACTION = 0.50
MIN_MARKET_ELIGIBLE_TICKERS = 30
MIN_MARKET_UP_VOLUME_FRACTION = 0.12
MIN_MARKET_UP_FRACTION = 0.52
MIN_MARKET_ABOVE_50D_FRACTION = 0.45
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

SECTOR_BREADTH_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = ohlcv_helper
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(ohlcv_helper, name):
            setattr(ohlcv_helper, name, None)


def _avg(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if isinstance(value, (int, float))]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start = ohlcv_helper._value(rows[start_idx], "Close")
    end = ohlcv_helper._value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _prior_high(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, "High") for row in rows[idx - days:idx]]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return max(clean)


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, key) for row in rows[idx - days:idx]]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return _avg(clean)


def _empty_context(date: str, sector: str) -> dict[str, Any]:
    return {
        "asof_date": date,
        "sector": sector,
        "passed": False,
        "status": "missing_sector_context",
        "eligible_ticker_count": 0,
        "up_volume_spike_count": 0,
        "positive_day_count": 0,
        "above_50d_count": 0,
        "sector_up_volume_fraction": None,
        "sector_market_up_fraction": None,
        "sector_above_50d_fraction": None,
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _passes_context(
    eligible: int,
    up_volume_spike: int,
    positive_day: int,
    above_50d: int,
    *,
    min_eligible: int,
    min_up_volume: float,
    min_market_up: float,
    min_above_50d: float,
) -> tuple[bool, dict[str, float | int | None]]:
    up_fraction = up_volume_spike / eligible if eligible else None
    market_up_fraction = positive_day / eligible if eligible else None
    above_50d_fraction = above_50d / eligible if eligible else None
    passed = (
        eligible >= min_eligible
        and up_fraction is not None
        and market_up_fraction is not None
        and above_50d_fraction is not None
        and up_fraction >= min_up_volume
        and market_up_fraction >= min_market_up
        and above_50d_fraction >= min_above_50d
    )
    return passed, {
        "eligible_ticker_count": eligible,
        "up_volume_spike_count": up_volume_spike,
        "positive_day_count": positive_day,
        "above_50d_count": above_50d,
        "up_volume_fraction": base._round(up_fraction, 6),
        "market_up_fraction": base._round(market_up_fraction, 6),
        "above_50d_fraction": base._round(above_50d_fraction, 6),
    }


def _daily_participation(
    snapshot: dict[str, list[dict[str, Any]]],
    date: str,
    tickers: list[str],
) -> dict[str, int]:
    eligible = 0
    up_volume_spike = 0
    positive_day = 0
    above_50d = 0
    for ticker in tickers:
        rows = ohlcv_helper._series(snapshot, ticker)
        idx = ohlcv_helper._row_index(rows).get(date)
        if idx is None or idx < MOVING_AVERAGE_DAYS or idx <= 0:
            continue
        close = ohlcv_helper._value(rows[idx], "Close")
        prev_close = ohlcv_helper._value(rows[idx - 1], "Close")
        volume = ohlcv_helper._value(rows[idx], "Volume")
        avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
        ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
        if not close or not prev_close or not volume or not avg_volume or not ma50:
            continue
        eligible += 1
        volume_ratio = volume / avg_volume if avg_volume else 0.0
        if close > prev_close:
            positive_day += 1
        if close > ma50:
            above_50d += 1
        if close > prev_close and volume_ratio >= MIN_CANDIDATE_VOLUME_RATIO_20:
            up_volume_spike += 1
    return {
        "eligible": eligible,
        "up_volume_spike": up_volume_spike,
        "positive_day": positive_day,
        "above_50d": above_50d,
    }


def _breadth_contexts_by_date(
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    universe: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    tickers = sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS))
    by_sector: dict[str, list[str]] = {}
    for ticker in tickers:
        sector = ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown")
        if sector in {"Unknown", "ETF", "Commodities"}:
            continue
        by_sector.setdefault(sector, []).append(ticker)

    market_contexts: dict[str, dict[str, Any]] = {}
    sector_contexts: dict[str, dict[str, dict[str, Any]]] = {}
    for date in dates:
        market_counts = _daily_participation(snapshot, date, tickers)
        market_passed, market_metrics = _passes_context(
            market_counts["eligible"],
            market_counts["up_volume_spike"],
            market_counts["positive_day"],
            market_counts["above_50d"],
            min_eligible=MIN_MARKET_ELIGIBLE_TICKERS,
            min_up_volume=MIN_MARKET_UP_VOLUME_FRACTION,
            min_market_up=MIN_MARKET_UP_FRACTION,
            min_above_50d=MIN_MARKET_ABOVE_50D_FRACTION,
        )
        market_contexts[date] = {
            "asof_date": date,
            "passed": market_passed,
            "status": "passed" if market_passed else "failed",
            "eligible_ticker_count": market_metrics["eligible_ticker_count"],
            "up_volume_spike_count": market_metrics["up_volume_spike_count"],
            "positive_day_count": market_metrics["positive_day_count"],
            "above_50d_count": market_metrics["above_50d_count"],
            "volume_breadth_fraction": market_metrics["up_volume_fraction"],
            "market_up_fraction": market_metrics["market_up_fraction"],
            "above_50d_fraction": market_metrics["above_50d_fraction"],
            "rule_version": MARKET_BREADTH_RULE_VERSION,
        }
        sector_contexts[date] = {}
        for sector, sector_tickers in by_sector.items():
            counts = _daily_participation(snapshot, date, sector_tickers)
            passed, metrics = _passes_context(
                counts["eligible"],
                counts["up_volume_spike"],
                counts["positive_day"],
                counts["above_50d"],
                min_eligible=MIN_SECTOR_ELIGIBLE_TICKERS,
                min_up_volume=MIN_SECTOR_UP_VOLUME_FRACTION,
                min_market_up=MIN_SECTOR_MARKET_UP_FRACTION,
                min_above_50d=MIN_SECTOR_ABOVE_50D_FRACTION,
            )
            sector_contexts[date][sector] = {
                "asof_date": date,
                "sector": sector,
                "passed": passed,
                "status": "passed" if passed else "failed",
                "eligible_ticker_count": metrics["eligible_ticker_count"],
                "up_volume_spike_count": metrics["up_volume_spike_count"],
                "positive_day_count": metrics["positive_day_count"],
                "above_50d_count": metrics["above_50d_count"],
                "sector_up_volume_fraction": metrics["up_volume_fraction"],
                "sector_market_up_fraction": metrics["market_up_fraction"],
                "sector_above_50d_fraction": metrics["above_50d_fraction"],
                "rule_version": RULE_VERSION,
                "known_at": "after_signal_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
    return market_contexts, sector_contexts


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    market_contexts, sector_contexts = _breadth_contexts_by_date(snapshot, dates, universe)
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_index = ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    raw_breakouts = 0
    sector_pass_dates = set()
    sector_pass_not_market_dates = set()

    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        sector = ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown")
        if sector in {"Unknown", "ETF", "Commodities"}:
            continue
        rows = ohlcv_helper._series(snapshot, ticker)
        idx_by_date = ohlcv_helper._row_index(rows)
        for date in dates:
            sector_context = sector_contexts.get(date, {}).get(sector) or _empty_context(date, sector)
            if sector_context.get("passed") is not True:
                continue
            market_context = market_contexts.get(date) or {}
            sector_pass_dates.add(date)
            if market_context.get("passed") is not True:
                sector_pass_not_market_dates.add(date)
            idx = idx_by_date.get(date)
            spy_idx = spy_index.get(date)
            if idx is None or spy_idx is None or idx < MOVING_AVERAGE_DAYS or spy_idx < 1:
                continue
            close = ohlcv_helper._value(rows[idx], "Close")
            volume = ohlcv_helper._value(rows[idx], "Volume")
            if not close or not volume:
                continue
            dollar_volume = close * volume
            if dollar_volume < MIN_DOLLAR_VOLUME:
                continue
            prior_high = _prior_high(rows, idx, BREAKOUT_LOOKBACK_DAYS)
            ma50 = _prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
            avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
            if not prior_high or not ma50 or not avg_volume:
                continue
            volume_ratio = volume / avg_volume if avg_volume else None
            if volume_ratio is None or volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20:
                continue
            if close <= prior_high or close <= ma50:
                continue
            candidate_ret = _close_return(rows, idx - 1, idx)
            spy_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
            if candidate_ret is None or spy_ret is None:
                continue
            rs_vs_spy = candidate_ret - spy_ret
            if rs_vs_spy <= 0:
                continue
            raw_breakouts += 1
            ab_entries = entries_by_date.get(date, [])
            sector_up = float(sector_context.get("sector_up_volume_fraction") or 0.0)
            sector_market_up = float(sector_context.get("sector_market_up_fraction") or 0.0)
            sector_above50 = float(sector_context.get("sector_above_50d_fraction") or 0.0)
            score = (
                max(rs_vs_spy, 0.0) * 7.0
                + min(max(volume_ratio - 1.0, 0.0), 3.0)
                + max((close / prior_high) - 1.0, 0.0) * 3.0
                + sector_up
                + sector_market_up * 0.5
                + sector_above50 * 0.25
            )
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": sector,
                    "strategy": "sector_breadth_breakout",
                    "close": base._round(close, 4),
                    "breakout_above_prior_20d_high_pct": base._round((close / prior_high) - 1.0, 6),
                    "pct_above_50d_ma": base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": base._round(candidate_ret, 6),
                    "candidate_day_spy_return": base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": base._round(rs_vs_spy, 6),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "dollar_volume": base._round(dollar_volume, 2),
                    "sector_breadth_score": base._round(score, 6),
                    "sector_breadth_context": sector_context,
                    "market_volume_breadth_context": market_context,
                    "market_breadth_already_passed": bool(market_context.get("passed")),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_ohlcv",
                    "sector_breadth_rule_version": RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
            )

    label = next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    SECTOR_BREADTH_AUDIT[label] = {
        "candidate_source_tickers": len(
            set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)
        ),
        "trading_days": len(dates),
        "sector_breadth_pass_days": len(sector_pass_dates),
        "sector_breadth_pass_not_market_breadth_days": len(sector_pass_not_market_dates),
        "raw_liquid_sector_breadth_breakout_hits": raw_breakouts,
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "market_breadth_overlap_candidates": sum(
            1 for row in candidates if row.get("market_breadth_already_passed")
        ),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["sector_breadth_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_sector_breadth_breakout_sleeve"
        if gate4_passed
        else "rejected_sector_breadth_breakout_sleeve"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Sector-level up-volume breadth may capture narrow rotation leadership "
        "that a market-wide breadth field can miss. The single tested variable "
        "is a default-off top-1 paper breakout source keyed on same-sector "
        "participation, using only free daily OHLCV."
    )
    payload["change_type"] = "sector_breadth_confirmed_breakout_default_off_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 0
    payload["mechanism_family"] = "free_ohlcv_sector_internal_structure_candidate_pool"
    payload["trial_variant_id"] = "sector_breadth_breakout_top1_v1"
    payload["nearby_prior_experiments"] = [
        "exp-20260525-916",
        "exp-20260525-029",
        "exp-20260526-010",
        "exp-20260526-013",
        "exp-20260526-014",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = "free_ohlcv_sector_up_volume_breadth_internal_structure_field"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-OHLCV sector-breadth confirmed breakout source",
        "breakout_close_above_prior_n_day_high": BREAKOUT_LOOKBACK_DAYS,
        "close_above_prior_n_day_moving_average": MOVING_AVERAGE_DAYS,
        "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
        "min_candidate_volume_ratio_20": MIN_CANDIDATE_VOLUME_RATIO_20,
        "min_candidate_day_rs_vs_spy": 0.0,
        "sector_breadth_context": {
            "min_eligible_tickers": MIN_SECTOR_ELIGIBLE_TICKERS,
            "min_up_volume_spike_fraction": MIN_SECTOR_UP_VOLUME_FRACTION,
            "min_market_up_fraction": MIN_SECTOR_MARKET_UP_FRACTION,
            "min_above_50d_fraction": MIN_SECTOR_ABOVE_50D_FRACTION,
        },
        "market_breadth_context_logged_only": {
            "min_eligible_tickers": MIN_MARKET_ELIGIBLE_TICKERS,
            "min_up_volume_spike_fraction": MIN_MARKET_UP_VOLUME_FRACTION,
            "min_market_up_fraction": MIN_MARKET_UP_FRACTION,
            "min_above_50d_fraction": MIN_MARKET_ABOVE_50D_FRACTION,
        },
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "sector_breadth_score desc",
        "candidate_day_rs_vs_spy desc",
        "volume_ratio_20 desc",
        "dollar_volume desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
        "core universe membership",
        "core signal generation",
        "core ranking",
        "core position sizing",
        "core exits",
        "portfolio heat",
        "slot rules",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
        "accepted volume-breadth breakout adapter",
    ]
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool: sector-level up-volume breadth can find cleaner "
            "rotation breakouts using free OHLCV. This fits the playbook's "
            "breadth/internal-structure data-edge direction."
        ),
        "2_history_check": {
            "sector_leadership": (
                "exp-20260525-916, exp-20260525-029, and exp-20260526-010 tested "
                "sector-leadership continuation/cooldown/core-activity slices. "
                "They did not use same-sector up-volume participation as the "
                "causal variable."
            ),
            "volume_breadth": (
                "exp-20260526-013/014 accepted market-wide volume-breadth breakout "
                "as a default-off adapter. This run does not retune those market "
                "thresholds; it logs overlap and tests sector participation."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=20 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_015_sector_breadth_breakout_sleeve.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker trailing 20/50-day OHLCV features",
        "same-date same-sector volume-ratio, positive-day, and above-50d breadth counts",
        "SPY OHLCV Close rows for signal-day relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "All candidate and sector breadth fields are derived from same-day or "
        "trailing OHLCV known after the signal-date close. Paper entry occurs "
        "at the next open; no LLM, hidden event, or future field is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate source is additive research, so core survival is unchanged."
    )
    payload["sector_breadth_audit"] = SECTOR_BREADTH_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, SEC semantics, and expectation-revision "
        "activation because current records remain PIT/sample-limited. Skipped "
        "VCP, market volume-breadth, pocket-pivot, gap, long-base, smooth, and "
        "pullback threshold retunes due recent rejections or playbook freezes. "
        "This tests one new sector-internal breadth field."
    )
    payload["interpretation"] = (
        "The sector-breadth confirmed breakout sleeve cleared Gate 4 as a "
        "replay-only lead, but no production/shared policy was promoted."
        if gate4_passed
        else (
            "The sector-breadth confirmed breakout sleeve did not clear Gate 4. "
            "Do not promote it or retry nearby sector-breadth thresholds on the "
            "same frozen windows without forward paper rows or an orthogonal "
            "source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, collect forward paper rows or add an orthogonal "
        "production-visible event/source confirmation; do not just retune "
        "sector breadth thresholds on the frozen sample."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper adapter, "
        "daily report exposure, forward replacement-value ledger, and parity tests "
        "before any live/default behavior changes."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Sector days | Tickers | Market-overlap cand. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["sector_breadth_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} | {tickers} | {overlap} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("raw_liquid_sector_breadth_breakout_hits"),
                days=audit.get("sector_breadth_pass_days"),
                tickers=audit.get("unique_candidate_tickers"),
                overlap=audit.get("market_breadth_overlap_candidates"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector-Breadth Confirmed Breakout Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "liquid breakout candidate per day only when same-sector "
                "up-volume breadth confirms participation."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Sector-Breadth Audit",
            "",
            "```json",
            json.dumps(payload["sector_breadth_audit"], indent=2, sort_keys=True),
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
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
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
            "title": "Sector-breadth confirmed breakout paper sleeve",
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
    _configure_base_module()
    base._candidate_rows_for_window = _candidate_rows_for_window
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "sector_breadth_audit": payload["sector_breadth_audit"],
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
