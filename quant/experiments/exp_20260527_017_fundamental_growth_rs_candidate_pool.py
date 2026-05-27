"""exp-20260527-017: fundamental growth + RS candidate-pool scout.

Alpha search. This tests one free-data candidate-pool variable: production
universe stocks with a point-in-time SEC Companyfacts growth cue and top-quartile
OHLCV relative-strength proxy. The sleeve is replay-only/default-off paper,
enters at the next open, and exits after ten trading days.

Core entries, ranking, sizing, exits, LLM/news paths, watchlists, and orders are
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict, defaultdict
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


EXPERIMENT_ID = "exp-20260527-017"
STEM = "fundamental_growth_rs_candidate_pool"
TRIAL_FAMILY = "fundamental_growth_rs_default_off_candidate_pool"
CHANGED_VARIABLE = "fundamental_growth_rs_top1_next_open_10d_fixed_notional_sleeve_v1"
RULE_VERSION = "fundamental_growth_rs_candidate_pool_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

EPS_GROWTH_THRESHOLD = 0.25
REVENUE_GROWTH_THRESHOLD = 0.20
MIN_FUNDAMENTAL_POINTS = 1
MIN_RS_PROXY_SCORE = 0.75
MIN_AVAILABLE_RS_WINDOWS = 2
RS_WINDOWS = (20, 60, 120)
TREND_MA_DAYS = 50
VOLUME_LOOKBACK_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20 = 40_000_000.0
MIN_RET20_EXCESS_SPY = 0.0
MIN_SIGNAL_DAY_RS_VS_SPY = -0.015
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30
QUARTERLY_DURATION_MIN = 60
QUARTERLY_DURATION_MAX = 130

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

FUNDAMENTAL_RS_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
FACT_INDEX: "CompanyfactsGrowthIndex | None" = None


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


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values = [ohlcv_helper._value(row, key) for row in rows[idx - days:idx]]
    clean = [value for value in values if isinstance(value, (int, float))]
    if len(clean) < days:
        return None
    return _avg(clean)


def _percentile_rank(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1])
    count = len(ordered)
    if count <= 1:
        return {ticker: 1.0 for ticker, _ in ordered}
    return {ticker: round(idx / (count - 1), 6) for idx, (ticker, _) in enumerate(ordered)}


def _is_quarterly_fact(row: dict[str, Any]) -> bool:
    duration = _float(row.get("duration_days"))
    if duration is None:
        return False
    if duration < QUARTERLY_DURATION_MIN or duration > QUARTERLY_DURATION_MAX:
        return False
    return str(row.get("fp") or "").upper() in {"Q1", "Q2", "Q3", "Q4"}


def _fact_sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
    duration = _float(row.get("duration_days"))
    duration_proximity = -abs((duration or 999.0) - 91.0)
    form = str(row.get("form") or "").upper()
    form_priority = 1 if form == "10-Q" else 0
    return (
        str(row.get("end") or ""),
        str(row.get("filed") or "")[:10],
        form_priority,
        duration_proximity,
    )


def _load_companyfacts_rows(max_filed: str, tickers: list[str]) -> list[dict[str, Any]]:
    ticker_set = {ticker.upper() for ticker in tickers}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_companyfacts_selected_*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                ticker = str(row.get("ticker") or "").upper()
                filed = str(row.get("filed") or "")[:10]
                if ticker not in ticker_set or not filed or filed > max_filed:
                    continue
                key = (
                    ticker,
                    row.get("canonical"),
                    row.get("concept"),
                    row.get("unit"),
                    row.get("value"),
                    row.get("start"),
                    row.get("end"),
                    filed,
                    row.get("form"),
                    row.get("accession_number"),
                    row.get("duration_days"),
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


class CompanyfactsGrowthIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = str(raw.get("filed") or "")[:10]
            value = _float(raw.get("value"))
            if canonical not in {"eps_diluted", "eps_basic", "revenue"}:
                continue
            if not ticker or not filed or value is None or not _is_quarterly_fact(raw):
                continue
            row = {
                **raw,
                "ticker": ticker,
                "canonical": canonical,
                "filed": filed,
                "value": value,
                "fy_int": _int(raw.get("fy")),
                "fp_norm": str(raw.get("fp") or "").upper(),
            }
            by_key[(ticker, canonical)].append(row)
        for bucket in by_key.values():
            bucket.sort(key=_fact_sort_key)
        self.by_key = by_key

    def growth(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any]:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not rows:
            return {"canonical": canonical, "available": False, "status": "missing_current_quarter_fact"}
        current = rows[-1]
        fy = current.get("fy_int")
        fp = current.get("fp_norm")
        if fy is None or not fp:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_fiscal_period_key",
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
            }
        priors = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if row.get("fy_int") == fy - 1
            and row.get("fp_norm") == fp
            and str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not priors:
            return {
                "canonical": canonical,
                "available": False,
                "status": "missing_prior_year_same_quarter_fact",
                "current_filed": current.get("filed"),
                "current_period_end": current.get("end"),
                "current_value": base._round(current.get("value"), 6),
                "current_fp": fp,
                "current_fy": fy,
            }
        prior = sorted(priors, key=_fact_sort_key)[-1]
        current_value = _float(current.get("value"))
        prior_value = _float(prior.get("value"))
        if current_value is None or prior_value is None:
            status = "missing_current_or_prior_value"
            growth = None
        elif prior_value <= 0:
            status = "non_positive_prior_value"
            growth = None
        else:
            status = "ok"
            growth = current_value / prior_value - 1.0
        return {
            "canonical": canonical,
            "available": growth is not None,
            "status": status,
            "yoy_growth": base._round(growth, 6),
            "current_value": base._round(current_value, 6),
            "current_filed": current.get("filed"),
            "current_period_end": current.get("end"),
            "current_form": current.get("form"),
            "current_fp": fp,
            "current_fy": fy,
            "prior_value": base._round(prior_value, 6),
            "prior_filed": prior.get("filed"),
            "prior_period_end": prior.get("end"),
            "known_at": "SEC Companyfacts filed date <= signal_date",
        }


def _fundamental_context(index: CompanyfactsGrowthIndex, ticker: str, signal_date: str) -> dict[str, Any]:
    diluted = index.growth(ticker, "eps_diluted", signal_date)
    basic = index.growth(ticker, "eps_basic", signal_date)
    eps = diluted if diluted.get("available") else basic
    revenue = index.growth(ticker, "revenue", signal_date)
    eps_growth = _float(eps.get("yoy_growth"))
    revenue_growth = _float(revenue.get("yoy_growth"))
    eps_pass = eps_growth is not None and eps_growth >= EPS_GROWTH_THRESHOLD
    revenue_pass = revenue_growth is not None and revenue_growth >= REVENUE_GROWTH_THRESHOLD
    points = int(eps_pass) + int(revenue_pass)
    return {
        "fundamental_growth_rule_version": RULE_VERSION,
        "fundamental_growth_known_at": "SEC Companyfacts filed date <= signal_date",
        "fundamental_growth_trade_enabled": False,
        "fundamental_growth_alters_orders": False,
        "eps_growth_source": eps.get("canonical"),
        "eps_growth_status": eps.get("status"),
        "eps_yoy_growth": base._round(eps_growth, 6),
        "eps_growth_pass": eps_pass,
        "eps_current_filed": eps.get("current_filed"),
        "eps_current_period_end": eps.get("current_period_end"),
        "eps_prior_filed": eps.get("prior_filed"),
        "revenue_growth_status": revenue.get("status"),
        "revenue_yoy_growth": base._round(revenue_growth, 6),
        "revenue_growth_pass": revenue_pass,
        "revenue_current_filed": revenue.get("current_filed"),
        "revenue_current_period_end": revenue.get("current_period_end"),
        "revenue_prior_filed": revenue.get("prior_filed"),
        "fundamental_growth_pair_available": eps_growth is not None and revenue_growth is not None,
        "fundamental_growth_points_v1": points,
        "fundamental_growth_pass_v1": points >= MIN_FUNDAMENTAL_POINTS,
    }


def _rs_context_by_ticker(
    snapshot: dict[str, list[dict[str, Any]]],
    tickers: list[str],
    date: str,
) -> dict[str, dict[str, Any]]:
    spy_rows = ohlcv_helper._series(snapshot, "SPY")
    spy_idx = ohlcv_helper._row_index(spy_rows).get(date)
    if spy_idx is None:
        return {}
    benchmark_returns = {
        window: _close_return(spy_rows, spy_idx - window, spy_idx)
        for window in RS_WINDOWS
    }
    raw_by_window: dict[int, dict[str, float]] = {window: {} for window in RS_WINDOWS}
    row_inputs: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        rows = ohlcv_helper._series(snapshot, ticker)
        idx = ohlcv_helper._row_index(rows).get(date)
        if idx is None:
            continue
        row_inputs[ticker] = {"ticker": ticker, "asof_price_date": date}
        for window in RS_WINDOWS:
            ret = _close_return(rows, idx - window, idx)
            spy_ret = benchmark_returns.get(window)
            if ret is None or spy_ret is None:
                continue
            excess = ret - spy_ret
            raw_by_window[window][ticker] = excess
            row_inputs[ticker][f"ret_{window}d"] = base._round(ret, 6)
            row_inputs[ticker][f"spy_ret_{window}d"] = base._round(spy_ret, 6)
            row_inputs[ticker][f"excess_ret_{window}d_vs_spy"] = base._round(excess, 6)

    ranks_by_window = {window: _percentile_rank(values) for window, values in raw_by_window.items()}
    out: dict[str, dict[str, Any]] = {}
    for ticker, row in row_inputs.items():
        ranks = []
        for window in RS_WINDOWS:
            rank = ranks_by_window[window].get(ticker)
            row[f"rs_proxy_rank_pct_{window}d"] = rank
            if rank is not None:
                ranks.append(rank)
        score = sum(ranks) / len(ranks) if ranks else None
        out[ticker] = {
            **row,
            "rs_proxy_rule_version": RULE_VERSION,
            "rs_proxy_known_at": "daily OHLCV rows with date <= signal_date",
            "rs_proxy_trade_enabled": False,
            "rs_proxy_alters_orders": False,
            "rs_proxy_available_window_count": len(ranks),
            "rs_proxy_score_v1": base._round(score, 6),
            "rs_proxy_leader_threshold": MIN_RS_PROXY_SCORE,
            "rs_proxy_leader_pass_v1": score is not None and score >= MIN_RS_PROXY_SCORE,
        }
    return out


def _get_fact_index(candidate_tickers: list[str]) -> CompanyfactsGrowthIndex:
    global FACT_INDEX
    if FACT_INDEX is None:
        max_window_end = max(cfg["end"] for cfg in base.WINDOWS.values())
        FACT_INDEX = CompanyfactsGrowthIndex(
            _load_companyfacts_rows(max_filed=max_window_end, tickers=candidate_tickers)
        )
    return FACT_INDEX


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
    candidate_tickers = []
    for ticker in sorted(set(universe).intersection(snapshot).difference(EXCLUDED_TICKERS)):
        sector = ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown")
        if sector not in {"Unknown", "ETF", "Commodities"}:
            candidate_tickers.append(ticker)

    fact_index = _get_fact_index(candidate_tickers)
    candidates: list[dict[str, Any]] = []
    checked = 0
    fundamental_passed = 0
    rs_passed = 0
    trend_liquidity_passed = 0
    combined_passed = 0
    unique_fundamental_tickers: set[str] = set()

    for date in dates:
        rs_by_ticker = _rs_context_by_ticker(snapshot, candidate_tickers, date)
        for ticker in candidate_tickers:
            rows = ohlcv_helper._series(snapshot, ticker)
            idx = ohlcv_helper._row_index(rows).get(date)
            if idx is None or idx < max(TREND_MA_DAYS, VOLUME_LOOKBACK_DAYS, 60):
                continue
            close = ohlcv_helper._value(rows[idx], "Close")
            volume = ohlcv_helper._value(rows[idx], "Volume")
            if not close or not volume:
                continue
            checked += 1

            fundamental = _fundamental_context(fact_index, ticker, date)
            points = int(fundamental.get("fundamental_growth_points_v1") or 0)
            if points < MIN_FUNDAMENTAL_POINTS:
                continue
            fundamental_passed += 1
            unique_fundamental_tickers.add(ticker)

            rs = rs_by_ticker.get(ticker) or {}
            rs_score = _float(rs.get("rs_proxy_score_v1"))
            available_rs = int(rs.get("rs_proxy_available_window_count") or 0)
            if rs_score is None or rs_score < MIN_RS_PROXY_SCORE or available_rs < MIN_AVAILABLE_RS_WINDOWS:
                continue
            rs_passed += 1

            avg_volume = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Volume")
            avg_close = _prior_average(rows, idx, VOLUME_LOOKBACK_DAYS, "Close")
            ma50 = _prior_average(rows, idx, TREND_MA_DAYS, "Close")
            if not avg_volume or not avg_close or not ma50:
                continue
            avg_dollar_volume = avg_volume * avg_close
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20 or close <= ma50:
                continue
            trend_liquidity_passed += 1

            candidate_ret = _close_return(rows, idx - 1, idx)
            spy_rows = ohlcv_helper._series(snapshot, "SPY")
            spy_idx = ohlcv_helper._row_index(spy_rows).get(date)
            spy_ret = _close_return(spy_rows, spy_idx - 1, spy_idx) if spy_idx is not None else None
            ret20_excess = _float(rs.get("excess_ret_20d_vs_spy"))
            if candidate_ret is None or spy_ret is None or ret20_excess is None:
                continue
            signal_day_rs = candidate_ret - spy_ret
            if ret20_excess < MIN_RET20_EXCESS_SPY or signal_day_rs < MIN_SIGNAL_DAY_RS_VS_SPY:
                continue
            combined_passed += 1

            eps_growth = _float(fundamental.get("eps_yoy_growth")) or 0.0
            revenue_growth = _float(fundamental.get("revenue_yoy_growth")) or 0.0
            volume_ratio = float(volume) / float(avg_volume) if avg_volume else None
            score = (
                rs_score
                + 0.20 * points
                + min(max(eps_growth, 0.0), 2.0) * 0.06
                + min(max(revenue_growth, 0.0), 1.5) * 0.08
                + max(ret20_excess, 0.0) * 1.5
                + max(signal_day_rs, 0.0) * 2.0
                + min(max((volume_ratio or 1.0) - 1.0, 0.0), 2.0) * 0.04
            )
            ab_entries = entries_by_date.get(date, [])
            candidates.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown"),
                    "strategy": "fundamental_growth_rs_candidate_pool",
                    "close": base._round(close, 4),
                    "avg_dollar_volume_20": base._round(avg_dollar_volume, 2),
                    "volume_ratio_20": base._round(volume_ratio, 6),
                    "pct_above_50d_ma": base._round((close / ma50) - 1.0, 6),
                    "candidate_day_return": base._round(candidate_ret, 6),
                    "candidate_day_spy_return": base._round(spy_ret, 6),
                    "candidate_day_rs_vs_spy": base._round(signal_day_rs, 6),
                    "fundamental_growth_rs_score_v1": base._round(score, 6),
                    **fundamental,
                    **rs,
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    "source_universe": "current_production_universe_with_sec_companyfacts_and_ohlcv",
                    "known_at": "after_signal_date_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "alters_orders": False,
                    "rule_version": RULE_VERSION,
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
    FUNDAMENTAL_RS_AUDIT[label] = {
        "candidate_source_tickers": len(candidate_tickers),
        "trading_days": len(dates),
        "context_checked": checked,
        "fundamental_points_passed": fundamental_passed,
        "unique_fundamental_pass_tickers": len(unique_fundamental_tickers),
        "rs_proxy_passed": rs_passed,
        "trend_liquidity_passed": trend_liquidity_passed,
        "combined_raw_candidates": combined_passed,
        "raw_candidates": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "rule_version": RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["fundamental_growth_rs_score_v1"]),
            -float(row["rs_proxy_score_v1"]),
            -float(row["fundamental_growth_points_v1"]),
            -float(row["avg_dollar_volume_20"]),
            row["ticker"],
        )
    )
    return candidates


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_fundamental_growth_rs_candidate_pool"
        if gate4_passed
        else "rejected_fundamental_growth_rs_candidate_pool"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / entry: a stock with PIT SEC Companyfacts EPS or "
        "revenue growth and top-quartile OHLCV relative strength should be a "
        "higher-quality candidate-pool addition than broad price-pattern retreads. "
        "This fits the playbook preference for production-visible free-data "
        "candidate-pool alpha and avoids VCP/VBB/state-surface retunes."
    )
    payload["change_type"] = "fundamental_growth_rs_default_off_candidate_pool"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 3
    payload["nearby_prior_experiments"] = [
        "exp-20260527-013",
        "exp-20260527-015",
        "exp-20260527-016",
        "exp-20260527-902",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate_high"
    payload["new_evidence_type"] = "pit_sec_companyfacts_growth_plus_free_ohlcv_rs_candidate_pool_replay"
    payload["parameters"]["shadow_entry_filters"] = {
        "base_source": "new free-data fundamental-growth plus OHLCV-RS candidate source",
        "eps_growth_threshold": EPS_GROWTH_THRESHOLD,
        "revenue_growth_threshold": REVENUE_GROWTH_THRESHOLD,
        "min_fundamental_points": MIN_FUNDAMENTAL_POINTS,
        "rs_proxy_windows": list(RS_WINDOWS),
        "min_rs_proxy_score": MIN_RS_PROXY_SCORE,
        "min_available_rs_windows": MIN_AVAILABLE_RS_WINDOWS,
        "trend_ma_days": TREND_MA_DAYS,
        "volume_lookback_days": VOLUME_LOOKBACK_DAYS,
        "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_signal_day_rs_vs_spy": MIN_SIGNAL_DAY_RS_VS_SPY,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "fundamental_growth_rs_score_v1 desc",
        "rs_proxy_score_v1 desc",
        "fundamental_growth_points_v1 desc",
        "avg_dollar_volume_20 desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
        "core universe membership for baseline replay",
        "core signal generation",
        "core ranking",
        "core position sizing",
        "core exits",
        "portfolio heat",
        "slot rules",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
        "accepted VCP paper adapter",
        "accepted volume-breadth breakout paper adapter",
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
            "candidate_pool / entry alpha from PIT SEC Companyfacts growth plus "
            "OHLCV RS proxy. It follows the playbook's free-data, production-visible "
            "candidate-pool lane and avoids frozen VCP/VBB/state-surface retunes."
        ),
        "2_history_check": {
            "exp-20260527-015": (
                "Kova fundamental+RS proxy was observed only on accepted VCP paper "
                "trades; the strong bucket was positive but too sparse/concentrated "
                "for direct promotion. This run tests it as a standalone top-1 "
                "candidate source."
            ),
            "exp-20260527-013": (
                "RS-line new-high standalone OHLCV source was rejected due late/old "
                "risk regression; this adds an orthogonal SEC growth field."
            ),
            "exp-20260527-902": (
                "Intraday Kova readiness is data-limited. This run avoids intraday "
                "data and uses only available filed-date Companyfacts plus daily OHLCV."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260527_017_fundamental_growth_rs_candidate_pool.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
    ]
    payload["gate2"]["note"] = (
        "SEC growth rows are filtered by filed <= signal_date. RS, trend, "
        "liquidity, and returns use signal-date or trailing OHLCV only. Paper "
        "entry occurs at the next open; no LLM, news, hidden event field, or "
        "future bar is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The sleeve is additive "
        "default-off paper, so core survival is unchanged."
    )
    payload["fundamental_growth_rs_audit"] = FUNDAMENTAL_RS_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-revision alpha because recent "
        "records show sparse/non-actionable coverage. Skipped Kova intraday "
        "because readiness was blocked. Skipped VCP/VBB/state-surface threshold, "
        "top-N, rank-profile, and notional retunes per playbook freeze guidance."
    )
    payload["interpretation"] = (
        "The fundamental-growth plus RS candidate-pool sleeve cleared Gate 4 as "
        "a replay-only lead. It is still not a live-order change and would require "
        "a shared default-off adapter plus parity tests before promotion."
        if gate4_passed
        else (
            "The fundamental-growth plus RS candidate-pool sleeve did not clear "
            "Gate 4. Do not promote it or retry nearby SEC-growth/RS percentile "
            "thresholds on the same frozen windows without forward rows or a "
            "materially new source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, use forward default-off paper rows or a materially different "
        "production-visible source-quality field; do not just retune RS percentile "
        "or growth thresholds on this frozen sample."
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
        base._repo_rel(DOC_TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Days | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["fundamental_growth_rs_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {candidates} | {days} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                candidates=audit.get("raw_candidates"),
                days=audit.get("candidate_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Fundamental Growth + RS Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a default-off paper sleeve admits at most one "
                "current-production-universe ticker per day when PIT SEC "
                "Companyfacts growth and daily OHLCV RS proxy both pass."
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
            "## Candidate Audit",
            "",
            "```json",
            json.dumps(payload["fundamental_growth_rs_audit"], indent=2, sort_keys=True),
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
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Fundamental growth + RS candidate-pool scout",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)
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
                    "fundamental_growth_rs_audit": payload["fundamental_growth_rs_audit"],
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
