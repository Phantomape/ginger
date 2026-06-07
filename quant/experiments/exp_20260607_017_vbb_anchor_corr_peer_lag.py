"""exp-20260607-017: VBB-anchor rolling-correlation peer-lag scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: accepted volume-breadth breakout days are used as
fixed flow anchors, then same-sector laggards with high trailing correlation
and positive signal-day catch-up are replayed as top-1 next-open default-off
paper candidates with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_018_rolling_corr_peer_shock_lag_candidate_pool as previous
import volume_breadth_breakout_paper_sleeve as vbb


framework = previous.framework

EXPERIMENT_ID = "exp-20260607-017"
STEM = "vbb_anchor_corr_peer_lag"
TRIAL_FAMILY = "vbb_anchor_peer_lag"
TRIAL_VARIANT_ID = "vbb_anchor_rolling_corr_peer_lag_v1"
CHANGED_VARIABLE = "vbb_anchor_rolling_corr_peer_lag_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = previous.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = previous.MIN_AVG_DOLLAR_VOLUME_20D
CORR_LOOKBACK_DAYS = previous.CORR_LOOKBACK_DAYS
MIN_CORRELATION = previous.MIN_CORRELATION
MAX_VBB_ANCHORS_PER_DAY = 1
MAX_LAGGARD_CANDIDATES_PER_DAY = 300
MAX_RAW_ROWS_PER_DAY = 50

MIN_CANDIDATE_SIGNAL_RETURN = 0.0
MAX_CANDIDATE_SIGNAL_RETURN = previous.MAX_CANDIDATE_SIGNAL_RETURN
MIN_ANCHOR_SIGNAL_RETURN_GAP = 0.02
MIN_ANCHOR_RET20_GAP = 0.03
VBB_CONFIG = {
    **vbb.DEFAULT_CONFIG,
    "paper_notional_usd": BASE_NOTIONAL_USD,
    "trade_enabled": False,
}

MIN_TARGET_TRADES = previous.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = previous.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_GATE4 = previous.BASE_GATE4

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.2,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "generic_peer_lag_failure",
        "old_thin_regression",
        "drawdown_drift",
        "insufficient_vbb_anchor_days",
        "sector_relation_noise",
    ],
    "confidence_reason": (
        "VBB is an accepted production-visible breadth-flow source and "
        "core-flow peer shock showed relation edges can work; generic peer "
        "lag failed without flow confirmation, so the edge is plausible but "
        "low probability."
    ),
    "recorded_at": "2026-06-07T15:07:24+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same accepted "
        "VBB anchor source, sector-known liquid warehouse universe, trailing "
        "60-day correlation known before signal close, same-sector laggard "
        "candidate fields, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, and concentration controls in both replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _ret_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    lookback: int,
) -> float | None:
    rows = snapshot.get(ticker) or []
    idx = indices.get(ticker, {}).get(signal_date)
    if idx is None:
        return None
    return framework._ret(rows, idx, lookback)


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days : idx]:
        value = framework._value(row, key)
        if value is None:
            return None
        values.append(float(value))
    return sum(values) / len(values)


def _prior_high(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days : idx]:
        value = framework._value(row, "High")
        if value is None:
            return None
        values.append(float(value))
    return max(values)


def _vbb_close_location(
    *, close: float | None, high: float | None, low: float | None
) -> float | None:
    if close is None or high is None or low is None or high <= low:
        return None
    return max(0.0, min(1.0, (close - low) / (high - low)))


def _volume_breadth_context_fast(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, Any]:
    tickers = sorted(set(sector_entries).difference(vbb.EXCLUDED_TICKERS))
    eligible = 0
    up_volume_spike = 0
    positive_day = 0
    above_50d = 0
    ma_days = int(VBB_CONFIG["moving_average_days"])
    vol_days = int(VBB_CONFIG["volume_lookback_days"])

    for ticker in tickers:
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < ma_days or idx <= 0:
            continue
        close = framework._value(rows[idx], "Close")
        prev_close = framework._value(rows[idx - 1], "Close")
        volume = framework._value(rows[idx], "Volume")
        avg_volume = _prior_average(rows, idx, vol_days, "Volume")
        ma50 = _prior_average(rows, idx, ma_days, "Close")
        if not close or not prev_close or not volume or not avg_volume or not ma50:
            continue
        eligible += 1
        volume_ratio = volume / avg_volume if avg_volume else 0.0
        if close > prev_close:
            positive_day += 1
        if close > ma50:
            above_50d += 1
        if close > prev_close and volume_ratio >= float(
            VBB_CONFIG["min_candidate_volume_ratio_20"]
        ):
            up_volume_spike += 1

    volume_breadth = up_volume_spike / eligible if eligible else None
    market_up = positive_day / eligible if eligible else None
    above50 = above_50d / eligible if eligible else None
    passed = (
        eligible >= int(VBB_CONFIG["min_breadth_eligible_tickers"])
        and volume_breadth is not None
        and market_up is not None
        and above50 is not None
        and volume_breadth >= float(VBB_CONFIG["min_volume_breadth_fraction"])
        and market_up >= float(VBB_CONFIG["min_market_up_fraction"])
        and above50 >= float(VBB_CONFIG["min_above_50d_fraction"])
    )
    status = "passed" if passed else "failed"
    if eligible < int(VBB_CONFIG["min_breadth_eligible_tickers"]):
        status = "insufficient_eligible_tickers"
    return {
        "rule_version": vbb.BREADTH_RULE_VERSION,
        "asof_date": signal_date,
        "passed": passed,
        "status": status,
        "eligible_ticker_count": eligible,
        "candidate_source_ticker_count": len(tickers),
        "up_volume_spike_count": up_volume_spike,
        "positive_day_count": positive_day,
        "above_50d_count": above_50d,
        "volume_breadth_fraction": framework._round(volume_breadth, 6),
        "market_up_fraction": framework._round(market_up, 6),
        "above_50d_fraction": framework._round(above50, 6),
        "min_volume_breadth_fraction": float(VBB_CONFIG["min_volume_breadth_fraction"]),
        "min_market_up_fraction": float(VBB_CONFIG["min_market_up_fraction"]),
        "min_above_50d_fraction": float(VBB_CONFIG["min_above_50d_fraction"]),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _vbb_candidate_for_ticker_fast(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    breadth: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in vbb.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    ma_days = int(VBB_CONFIG["moving_average_days"])
    breakout_days = int(VBB_CONFIG["breakout_lookback_days"])
    volume_days = int(VBB_CONFIG["volume_lookback_days"])
    if idx is None or spy_idx is None or idx < ma_days or spy_idx < 1:
        return None
    close = framework._value(rows[idx], "Close")
    high = framework._value(rows[idx], "High")
    low = framework._value(rows[idx], "Low")
    volume = framework._value(rows[idx], "Volume")
    if not close or not volume:
        return None
    dollar_volume = close * volume
    if dollar_volume < float(VBB_CONFIG["min_dollar_volume"]):
        return None
    prior_high = _prior_high(rows, idx, breakout_days)
    ma50 = _prior_average(rows, idx, ma_days, "Close")
    avg_volume = _prior_average(rows, idx, volume_days, "Volume")
    if not prior_high or not ma50 or not avg_volume:
        return None
    volume_ratio = volume / avg_volume if avg_volume else None
    if volume_ratio is None or volume_ratio < float(
        VBB_CONFIG["min_candidate_volume_ratio_20"]
    ):
        return None
    if close <= prior_high or close <= ma50:
        return None
    candidate_ret = framework._daily_return(rows, idx)
    spy_ret = framework._daily_return(spy_rows, spy_idx)
    if candidate_ret is None or spy_ret is None:
        return None
    rs_vs_spy = candidate_ret - spy_ret
    if rs_vs_spy <= float(VBB_CONFIG["min_candidate_rs_vs_spy"]):
        return None
    score = (
        max(rs_vs_spy, 0.0) * 8.0
        + min(max(volume_ratio - 1.0, 0.0), 3.0)
        + max((close / prior_high) - 1.0, 0.0) * 3.0
    )
    meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "strategy": "volume_breadth_breakout",
        "close": framework._round(close, 4),
        "signal_day_high": framework._round(high, 4),
        "signal_day_low": framework._round(low, 4),
        "signal_day_close_location_value": framework._round(
            _vbb_close_location(close=close, high=high, low=low),
            6,
        ),
        "entry_price": framework._round(close, 4),
        "breakout_above_prior_20d_high_pct": framework._round(
            (close / prior_high) - 1.0,
            6,
        ),
        "pct_above_50d_ma": framework._round((close / ma50) - 1.0, 6),
        "candidate_day_return": framework._round(candidate_ret, 6),
        "candidate_day_spy_return": framework._round(spy_ret, 6),
        "candidate_day_rs_vs_spy": framework._round(rs_vs_spy, 6),
        "volume_ratio_20": framework._round(volume_ratio, 6),
        "dollar_volume": framework._round(dollar_volume, 2),
        "volume_breadth_score": framework._round(score, 6),
        "volume_breadth_context": dict(breadth),
        "rule_version": vbb.RULE_VERSION,
        "volume_breadth_rule_version": vbb.BREADTH_RULE_VERSION,
        "source_universe": "sector_known_warehouse_ohlcv",
        "same_day_core_entry_count": 0,
        "same_day_core_overlap": False,
        "same_ticker_core_overlap": False,
        "intended_notional": float(BASE_NOTIONAL_USD),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _anchor_rows_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    breadth = _volume_breadth_context_fast(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        signal_date=signal_date,
    )
    if breadth.get("passed") is not True:
        return [], breadth
    candidates = []
    for ticker in sorted(sector_entries):
        row = _vbb_candidate_for_ticker_fast(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            ticker=ticker,
            signal_date=signal_date,
            breadth=breadth,
        )
        if row is not None:
            candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["volume_breadth_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    anchors: list[dict[str, Any]] = []
    for candidate in candidates[:MAX_VBB_ANCHORS_PER_DAY]:
        ticker = str(candidate.get("ticker") or "").upper()
        meta = sector_entries.get(ticker)
        if not meta:
            continue
        anchors.append(
            {
                **candidate,
                "ticker": ticker,
                "anchor_sector": meta.get("sector"),
                "anchor_industry": meta.get("industry"),
            }
        )
    return anchors, breadth


def _laggard_rows_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
    sector: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ticker, meta in sector_entries.items():
        if meta.get("sector") != sector:
            continue
        row = previous._laggard_candidate_for_ticker(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            ticker=ticker,
            signal_date=signal_date,
        )
        if row is None:
            continue
        signal_return = float(row.get("candidate_signal_day_return") or 0.0)
        if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
            continue
        rows.append(row)
    rows.sort(
        key=lambda row: (
            -float(row["candidate_lag_quality_score"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return rows[:MAX_LAGGARD_CANDIDATES_PER_DAY]


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    all_dates = framework.shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(all_dates)}
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    anchor_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "vbb_passed_days": 0,
        "vbb_anchor_days": 0,
        "days_with_laggard_candidates": 0,
        "days_with_corr_pairs": 0,
        "raw_vbb_anchors": 0,
        "raw_laggard_candidates": 0,
        "raw_corr_pairs": 0,
        "max_vbb_anchors_per_day": MAX_VBB_ANCHORS_PER_DAY,
        "max_laggard_candidates_per_day": MAX_LAGGARD_CANDIDATES_PER_DAY,
        "correlation_lookback_days": CORR_LOOKBACK_DAYS,
        "min_correlation": MIN_CORRELATION,
    }

    for signal_date in dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < CORR_LOOKBACK_DAYS:
            continue
        prior_dates = all_dates[pos - CORR_LOOKBACK_DAYS : pos]
        anchors, breadth = _anchor_rows_for_day(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=signal_date,
        )
        if breadth.get("passed") is True:
            scan["vbb_passed_days"] += 1
        if not anchors:
            continue
        scan["vbb_anchor_days"] += 1
        scan["raw_vbb_anchors"] += len(anchors)

        day_rows: list[dict[str, Any]] = []
        for anchor in anchors:
            anchor_ticker = str(anchor["ticker"])
            anchor_sector = str(anchor.get("anchor_sector") or "")
            anchor_vector = previous._prior_return_vector_for_dates(
                snapshot=snapshot,
                indices=indices,
                ticker=anchor_ticker,
                prior_dates=prior_dates,
            )
            if anchor_vector is None:
                continue
            anchor_ret20 = _ret_for_ticker(
                snapshot=snapshot,
                indices=indices,
                ticker=anchor_ticker,
                signal_date=signal_date,
                lookback=20,
            )
            if anchor_ret20 is None:
                continue

            laggards = _laggard_rows_for_day(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                signal_date=signal_date,
                sector=anchor_sector,
            )
            if not laggards:
                continue
            scan["raw_laggard_candidates"] += len(laggards)
            scan["days_with_laggard_candidates"] += 1

            for laggard in laggards:
                ticker = str(laggard["ticker"])
                if ticker == anchor_ticker:
                    continue
                candidate_ret20 = float(laggard.get("candidate_ret20") or 0.0)
                signal_gap = float(anchor.get("candidate_day_return") or 0.0) - float(
                    laggard.get("candidate_signal_day_return") or 0.0
                )
                ret20_gap = anchor_ret20 - candidate_ret20
                if signal_gap < MIN_ANCHOR_SIGNAL_RETURN_GAP:
                    continue
                if ret20_gap < MIN_ANCHOR_RET20_GAP:
                    continue
                laggard_vector = previous._prior_return_vector_for_dates(
                    snapshot=snapshot,
                    indices=indices,
                    ticker=ticker,
                    prior_dates=prior_dates,
                )
                if laggard_vector is None:
                    continue
                corr = previous._pearson_corr(anchor_vector, laggard_vector)
                if corr is None or corr < MIN_CORRELATION:
                    continue
                same_industry = anchor.get("anchor_industry") == laggard.get("industry")
                score = (
                    1.80 * corr
                    + 1.40 * float(anchor.get("candidate_day_rs_vs_spy") or 0.0)
                    + 0.45 * min(float(anchor.get("volume_ratio_20") or 0.0), 5.0)
                    + 0.70 * float(laggard["candidate_lag_quality_score"])
                    + 0.30 * ret20_gap
                    + 0.20 * signal_gap
                    + (0.06 if same_industry else 0.0)
                )
                ab_entries = entries_by_date.get(signal_date, [])
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "VBB_ANCHOR_ROLLING_CORR_PEER_LAG_PAPER",
                        "candidate_score": round(score, 6),
                        "anchor_ticker": anchor_ticker,
                        "anchor_sector": anchor.get("anchor_sector"),
                        "anchor_industry": anchor.get("anchor_industry"),
                        "anchor_candidate_day_return": anchor.get("candidate_day_return"),
                        "anchor_candidate_day_rs_vs_spy": anchor.get(
                            "candidate_day_rs_vs_spy"
                        ),
                        "anchor_volume_ratio_20": anchor.get("volume_ratio_20"),
                        "anchor_volume_breadth_score": anchor.get(
                            "volume_breadth_score"
                        ),
                        "anchor_ret20": round(anchor_ret20, 6),
                        "anchor_signal_gap": round(signal_gap, 6),
                        "anchor_ret20_gap": round(ret20_gap, 6),
                        "rolling_corr_60d": round(corr, 6),
                        "same_sector_as_anchor": True,
                        "same_industry_as_anchor": bool(same_industry),
                        "vbb_breadth_context": anchor.get("volume_breadth_context"),
                        **laggard,
                        "same_day_ab_entry_count": len(ab_entries),
                        "same_day_ab_overlap": bool(ab_entries),
                        "same_ticker_ab_overlap": any(
                            trade.get("ticker") == ticker for trade in ab_entries
                        ),
                        "rule_version": RULE_VERSION,
                        "uses_free_ohlcv_only": True,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "known_at": (
                            "after_signal_day_close_before_next_open_paper_entry"
                        ),
                    }
                )

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["rolling_corr_60d"]),
                -float(row["anchor_ret20_gap"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("anchor_ticker") or ""),
                row["ticker"],
            )
        )
        day_rows = day_rows[:MAX_RAW_ROWS_PER_DAY]
        candidates.extend(day_rows)
        scan["days_with_corr_pairs"] += 1
        scan["raw_corr_pairs"] += len(day_rows)
        anchor_contexts.append(
            {
                "date": signal_date,
                "anchor_count": len(anchors),
                "top_anchor_ticker": day_rows[0]["anchor_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_rolling_corr_60d": day_rows[0]["rolling_corr_60d"],
                "top_anchor_ret20_gap": day_rows[0]["anchor_ret20_gap"],
                "top_candidate_signal_day_return": day_rows[0][
                    "candidate_signal_day_return"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["rolling_corr_60d"]),
            -float(row["anchor_ret20_gap"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("anchor_ticker") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_anchor_signal_return_gap": MIN_ANCHOR_SIGNAL_RETURN_GAP,
            "min_anchor_ret20_gap": MIN_ANCHOR_RET20_GAP,
            "vbb_rule_version": vbb.RULE_VERSION,
            "vbb_breadth_rule_version": vbb.BREADTH_RULE_VERSION,
            "vbb_thresholds_locked": True,
        }
    )
    return candidates, anchor_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_vbb_anchor_corr_peer_lag"
        if gate["passed"]
        else "rejected_vbb_anchor_corr_peer_lag_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Accepted volume-breadth breakout anchors may identify "
                "same-sector, high-correlation laggards that begin catching "
                "up after a broad participation day."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "relation_aware_free_ohlcv_candidate_pool",
            "new_evidence_type": (
                "accepted VBB breadth-flow anchor applied to rolling-correlation "
                "peer-lag relation"
            ),
            "nearby_prior_experiments": [
                "exp-20260526-014",
                "exp-20260606-018",
                "exp-20260606-024",
                "exp-20260607-008",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the most likely reason is that a VBB anchor "
                "already captures the same risk-on flow and same-sector "
                "laggards add delayed beta rather than independent edge. Do "
                "not answer by retuning VBB thresholds, correlation thresholds, "
                "top-N, hold days, cooldown, or notional on the frozen windows."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The VBB anchor already concentrates the breadth-flow edge "
                    "in the actual breakout ticker. Same-sector correlated "
                    "laggards added delayed beta exposure, which was not "
                    "independent enough to survive late_strong and old_thin "
                    "after costs and drawdown."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry this family by sweeping VBB thresholds, "
                    "rolling-correlation thresholds, same-sector versus "
                    "same-industry flags, top-N, hold days, cooldown, or "
                    "paper notional on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry needs a genuinely new relation source, such as "
                    "forward replacement-value rows showing VBB peers create "
                    "cash-slot value, or PIT supplier/customer/product-market "
                    "links that separate information transfer from broad beta."
                ),
            },
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before forward observation. Live "
                "activation would require closed forward replacement-value "
                "rows and a separate activation-envelope Gate 1-4."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "correlation_lookback_days": CORR_LOOKBACK_DAYS,
            "min_correlation": MIN_CORRELATION,
            "max_vbb_anchors_per_day": MAX_VBB_ANCHORS_PER_DAY,
            "max_laggard_candidates_per_day": MAX_LAGGARD_CANDIDATES_PER_DAY,
            "max_raw_rows_per_day": MAX_RAW_ROWS_PER_DAY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_anchor_signal_return_gap": MIN_ANCHOR_SIGNAL_RETURN_GAP,
            "min_anchor_ret20_gap": MIN_ANCHOR_RET20_GAP,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses accepted VBB candidate fields and close-of-day OHLCV "
        "available on the signal date plus 60 prior trading-day returns for "
        "correlation. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: accepted VBB flow days may transfer to "
            "same-sector correlated laggards that have started to catch up but "
            "remain behind the anchor."
        ),
        "2_history_check": {
            "exp-20260526-014": (
                "VBB was accepted as a production-visible default-off helper. "
                "This run uses its fixed candidate source as an anchor and does "
                "not retune VBB thresholds or support scalars."
            ),
            "exp-20260606-018": (
                "Generic rolling-correlation peer-shock lag improved aggregate "
                "but failed old_thin/drawdown. This run adds a different flow "
                "confirmation: accepted VBB anchor days."
            ),
            "exp-20260606-024": (
                "Core-flow confirmed peer-shock showed relation edges can work "
                "when a production-visible flow source filters the generic "
                "peer-lag pool."
            ),
            "exp-20260607-008": (
                "Industry-relative laggard repair was accepted. This run is not "
                "an industry threshold retune; it requires a same-day accepted "
                "VBB anchor plus rolling correlation."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes. A positive replay still "
            "requires shared adapter parity before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_017_vbb_anchor_corr_peer_lag.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted"
        if payload["gate4"]["passed"]
        else "rejected"
    )
    payload["interpretation"] = (
        "The VBB-anchor rolling-correlation peer-lag source cleared Gate 4 as "
        "a replay-only/default-off lead. No production surface was promoted; "
        "a shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The VBB-anchor rolling-correlation peer-lag source did not clear "
            "Gate 4; do not promote or locally retune this VBB-anchor "
            "peer-lag family on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | VBB days | Corr pairs | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {pairs} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("vbb_anchor_days", 0),
                pairs=scan.get("raw_corr_pairs", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VBB-Anchor Corr Peer-Lag",
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
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "relation_aware_free_ohlcv_candidate_pool",
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
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "vbb_anchor_day_count": payload["context_scan_by_window"][label].get(
                    "vbb_anchor_days"
                ),
                "corr_pair_count": payload["context_scan_by_window"][label].get(
                    "raw_corr_pairs"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
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
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
