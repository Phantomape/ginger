"""exp-20260608-016: accumulation-base breakout candidate pool.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: liquid sector-known stocks that show ticker-level
accumulation volume balance during a base, then break above the prior 20-day
high with volume and a close near the high become top-1 next-open default-off
paper candidates with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260606_015_low_vol_20d_high_breakout_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-016"
STEM = "accumulation_base_breakout"
TRIAL_FAMILY = "ticker_accumulation_base_breakout_candidate_pool"
TRIAL_VARIANT_ID = "ticker_accumulation_base_breakout_top1_next_open_10d_v1"
CHANGED_VARIABLE = "ticker_accumulation_base_breakout_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_016_{STEM}.json"
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
ACCUMULATION_LOOKBACK_DAYS = 20
BASE_RANGE_LOOKBACK_DAYS = 20
PRIOR_HIGH_LOOKBACK_DAYS = 20
MIN_UP_VOLUME_SHARE_20D = 0.56
MIN_OBV_SLOPE_20D = 0.0
MIN_OBV_NET_VOLUME_RATIO_20D = 0.030
MAX_BASE_RANGE20_PCT = 0.260
MAX_BASE_REALIZED_VOL_20D = 0.070
MIN_SIGNAL_BREAKOUT_PCT = 0.001
MIN_SIGNAL_RETURN = 0.002
MIN_CLOSE_LOCATION = 0.70
MIN_VOLUME_RATIO_20D = 1.15
MIN_RET20_EXCESS_SPY = 0.000
MIN_RET60_EXCESS_SPY = -0.020
MIN_RET5 = -0.025
MAX_RET5 = 0.110
MAX_RET20 = 0.280
MAX_SIGNAL_RANGE_PCT = 0.140

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "ohlcv_momentum_relabeling",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
        "target_sample_too_small",
        "nearby_compression_overlap",
    ],
    "confidence_reason": (
        "Prior free-OHLCV adapter wins came from production-visible candidate "
        "pools, but raw momentum and many ETF/proxy variants failed. This tests "
        "ticker-level accumulation volume balance as a materially different "
        "discriminator from range compression or market volume breadth."
    ),
    "recorded_at": "2026-06-08T15:06:36+00:00",
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
        "require a shared default-off adapter that computes the same "
        "sector-known liquid stock universe, ticker-level accumulation volume "
        "balance, OBV proxy fields, signal-day 20-day-high breakout, "
        "close-location, volume confirmation, SPY-relative trend guards, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, and concentration controls in "
        "both historical replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _range_pct(row: dict[str, Any]) -> float | None:
    high = framework._value(row, "High")
    low = framework._value(row, "Low")
    close = framework._value(row, "Close")
    if high is None or low is None or close is None or close <= 0:
        return None
    if high < low:
        return None
    return (high - low) / close


def _median_range_pct(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
) -> float | None:
    if idx < lookback:
        return None
    values = [_range_pct(row) for row in rows[idx - lookback : idx]]
    if any(value is None for value in values):
        return None
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _prior_high(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
) -> float | None:
    if idx < lookback:
        return None
    highs = [framework._value(row, "High") for row in rows[idx - lookback : idx]]
    if any(value is None for value in highs):
        return None
    return max(float(value) for value in highs if value is not None)


def _base_range_pct(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
) -> float | None:
    if idx < lookback:
        return None
    highs = [framework._value(row, "High") for row in rows[idx - lookback : idx]]
    lows = [framework._value(row, "Low") for row in rows[idx - lookback : idx]]
    anchor_close = framework._value(rows[idx - 1], "Close")
    if any(value is None for value in [*highs, *lows, anchor_close]):
        return None
    assert anchor_close is not None
    if anchor_close <= 0:
        return None
    high = max(float(value) for value in highs if value is not None)
    low = min(float(value) for value in lows if value is not None)
    if high < low:
        return None
    return (high - low) / anchor_close


def _accumulation_stats(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
) -> dict[str, float] | None:
    if idx < lookback + 1:
        return None
    up_volume = 0.0
    down_volume = 0.0
    total_volume = 0.0
    obv_balance = 0.0
    up_days = 0
    down_days = 0
    for offset in range(idx - lookback + 1, idx):
        close = framework._value(rows[offset], "Close")
        prior_close = framework._value(rows[offset - 1], "Close")
        volume = framework._value(rows[offset], "Volume")
        if close is None or prior_close is None or volume is None:
            return None
        volume = float(volume)
        if volume < 0:
            return None
        total_volume += volume
        if close > prior_close:
            up_volume += volume
            obv_balance += volume
            up_days += 1
        elif close < prior_close:
            down_volume += volume
            obv_balance -= volume
            down_days += 1
    if total_volume <= 0:
        return None
    return {
        "up_volume_share": up_volume / total_volume,
        "down_volume_share": down_volume / total_volume,
        "obv_net_volume_ratio": obv_balance / total_volume,
        "up_day_fraction": up_days / max(1, up_days + down_days),
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 60 or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    signal_range_pct = _range_pct(rows[idx])
    prior_high = _prior_high(rows, idx, PRIOR_HIGH_LOOKBACK_DAYS)
    base_range20_pct = _base_range_pct(rows, idx, BASE_RANGE_LOOKBACK_DAYS)
    accumulation = _accumulation_stats(rows, idx, ACCUMULATION_LOOKBACK_DAYS)
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        signal_range_pct,
        prior_high,
        base_range20_pct,
        accumulation,
        signal_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_range_pct is not None
    assert prior_high is not None
    assert base_range20_pct is not None
    assert accumulation is not None
    assert signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    if prior_high <= 0:
        return None

    breakout_pct = close / prior_high - 1.0
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    up_volume_share = accumulation["up_volume_share"]
    obv_net_volume_ratio = accumulation["obv_net_volume_ratio"]
    up_day_fraction = accumulation["up_day_fraction"]
    if up_volume_share < MIN_UP_VOLUME_SHARE_20D:
        return None
    if obv_net_volume_ratio < MIN_OBV_NET_VOLUME_RATIO_20D:
        return None
    if obv_net_volume_ratio < MIN_OBV_SLOPE_20D:
        return None
    if base_range20_pct > MAX_BASE_RANGE20_PCT:
        return None
    if realized_vol20 > MAX_BASE_REALIZED_VOL_20D:
        return None
    if breakout_pct < MIN_SIGNAL_BREAKOUT_PCT:
        return None
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    if signal_range_pct > MAX_SIGNAL_RANGE_PCT:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if ret20 > MAX_RET20:
        return None

    sector_meta = sector_entries[ticker]
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        1.15 * breakout_pct
        + 1.30 * ret20_excess_spy
        + 0.45 * ret60_excess_spy
        + 1.20 * signal_return
        + 0.85 * up_volume_share
        + 0.75 * obv_net_volume_ratio
        + 0.35 * close_location
        + 0.12 * min(volume_ratio, 4.0)
        + 0.04 * liquidity_score
        - 0.55 * base_range20_pct
        - 0.75 * realized_vol20
        - 0.25 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "ACCUMULATION_BASE_BREAKOUT_PAPER",
        "candidate_score": round(score, 6),
        "candidate_prior_high_20d": round(prior_high, 6),
        "candidate_breakout_pct": round(breakout_pct, 6),
        "candidate_signal_range_pct": round(signal_range_pct, 6),
        "candidate_base_range20_pct": round(base_range20_pct, 6),
        "candidate_up_volume_share_20d": round(up_volume_share, 6),
        "candidate_obv_net_volume_ratio_20d": round(obv_net_volume_ratio, 6),
        "candidate_up_day_fraction_20d": round(up_day_fraction, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_raw_accumulation_base_candidates": 0,
        "raw_accumulation_base_candidates": 0,
    }
    for signal_date in dates:
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
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
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_up_volume_share_20d"]),
                -float(row["candidate_breakout_pct"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_accumulation_base_candidates"] += 1
        scan["raw_accumulation_base_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_breakout_pct": day_rows[0]["candidate_breakout_pct"],
                "top_candidate_up_volume_share_20d": day_rows[0][
                    "candidate_up_volume_share_20d"
                ],
                "top_candidate_obv_net_volume_ratio_20d": day_rows[0][
                    "candidate_obv_net_volume_ratio_20d"
                ],
                "top_candidate_ret20_excess_spy": day_rows[0][
                    "candidate_ret20_excess_spy"
                ],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_up_volume_share_20d"]),
            -float(row["candidate_breakout_pct"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "accumulation_lookback_days": ACCUMULATION_LOOKBACK_DAYS,
            "base_range_lookback_days": BASE_RANGE_LOOKBACK_DAYS,
            "prior_high_lookback_days": PRIOR_HIGH_LOOKBACK_DAYS,
            "min_up_volume_share_20d": MIN_UP_VOLUME_SHARE_20D,
            "min_obv_slope_20d": MIN_OBV_SLOPE_20D,
            "min_obv_net_volume_ratio_20d": MIN_OBV_NET_VOLUME_RATIO_20D,
            "max_base_range20_pct": MAX_BASE_RANGE20_PCT,
            "max_base_realized_vol_20d": MAX_BASE_REALIZED_VOL_20D,
            "min_signal_breakout_pct": MIN_SIGNAL_BREAKOUT_PCT,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_signal_range_pct": MAX_SIGNAL_RANGE_PCT,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_ret20": MAX_RET20,
        }
    )
    return candidates, day_contexts, scan


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
        "positive_replay_lead_not_promoted_accumulation_base_breakout"
        if gate["passed"]
        else "rejected_accumulation_base_breakout_candidate_pool"
    )
    return gate


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


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Ticker-level accumulation-base breakouts with positive "
                "up-volume balance before a volume-confirmed high close may "
                "expand the default-off candidate pool beyond range-compression "
                "and broad market breadth signals."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": "new_production_visible_ohlcv_accumulation_volume_field",
            "nearby_prior_experiments": [
                "exp-20260526-014",
                "exp-20260606-015",
                "exp-20260608-012",
                "exp-20260608-013",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that the up-volume/OBV "
                "balance field is still a broad OHLCV momentum or liquidity "
                "relabel after next-open costs, or that it overlaps too much "
                "with the already accepted compression/VCP/volume-breadth "
                "routes. Do not answer by sweeping up-volume share, OBV ratio, "
                "breakout pct, hold-day, cooldown, or notional thresholds on "
                "these same windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new evidence such as forward "
                "replacement-value rows, a production-visible catalyst/flow "
                "provenance layer, or a PIT order-flow/ownership field that is "
                "not derivable from daily OHLCV. Pure accumulation-volume "
                "threshold retunes should stay frozen."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The accumulation-volume field selected a large broad "
                    "sample and looked directionally useful in late_strong and "
                    "mid_weak, but old_thin lost EV/PnL and the overlay raised "
                    "max drawdown by 1.72pp. That means the up-volume/OBV "
                    "proxy mostly amplified pro-cyclical breakout exposure "
                    "instead of separating durable accumulation from generic "
                    "momentum after next-open execution costs."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping accumulation lookback, up-volume "
                    "share, OBV ratio, breakout pct, close-location, volume, "
                    "ret5/ret20, top-N, hold-day, cooldown, or paper notional "
                    "thresholds on these frozen windows."
                ),
                "new_evidence_required": (
                    "Next useful evidence would be a shared default-off helper "
                    "that reproduces this exact historical replay and daily "
                    "snapshot semantics, closed forward replacement-value rows, "
                    "or an orthogonal PIT flow/catalyst field. Live activation "
                    "would need a separate activation-envelope Gate 1-4."
                ),
            },
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
            "accumulation_lookback_days": ACCUMULATION_LOOKBACK_DAYS,
            "base_range_lookback_days": BASE_RANGE_LOOKBACK_DAYS,
            "prior_high_lookback_days": PRIOR_HIGH_LOOKBACK_DAYS,
            "min_up_volume_share_20d": MIN_UP_VOLUME_SHARE_20D,
            "min_obv_slope_20d": MIN_OBV_SLOPE_20D,
            "min_obv_net_volume_ratio_20d": MIN_OBV_NET_VOLUME_RATIO_20D,
            "max_base_range20_pct": MAX_BASE_RANGE20_PCT,
            "max_base_realized_vol_20d": MAX_BASE_REALIZED_VOL_20D,
            "min_signal_breakout_pct": MIN_SIGNAL_BREAKOUT_PCT,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_signal_range_pct": MAX_SIGNAL_RANGE_PCT,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_ret20": MAX_RET20,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: ticker-level up-volume balance and OBV proxy "
            "inside a base may identify accumulation before a volume-confirmed "
            "20-day-high breakout."
        ),
        "2_history_check": {
            "exp-20260526-014": (
                "Volume-breadth breakout was promoted as a market-breadth "
                "helper; this run tests ticker-level accumulation balance, not "
                "market up-volume breadth."
            ),
            "exp-20260606-015": (
                "Low-volatility 20-day high breakout was rejected because "
                "window robustness/drawdown failed; this run adds explicit "
                "up-volume/OBV accumulation evidence before breakout."
            ),
            "exp-20260608-012/013": (
                "Narrow-range compression breakout was accepted through a "
                "shared helper; this run is not a threshold retune and must be "
                "treated only as a separate replay scout unless a shared helper "
                "later reproduces it."
            ),
            "recent broad proxy failures": (
                "Commodity/ETF, IWM breadth, low-deployment stock, and industry "
                "volume-breadth neighbors recently failed; this run avoids those "
                "proxy labels and only uses ticker-level accumulation structure."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_016_accumulation_base_breakout.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The ticker-level accumulation-base breakout source cleared Gate 4 as "
        "a replay-only/default-off lead, but no production surface was "
        "promoted. A shared parity adapter is required before use."
        if payload["gate4"]["passed"]
        else (
            "The ticker-level accumulation-base breakout source did not clear "
            "Gate 4. Do not promote or locally retune this OHLCV accumulation "
            "family on the frozen windows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
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
                days=scan.get("days_with_raw_accumulation_base_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accumulation-Base Breakout Candidate Pool",
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
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
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
                "accumulation_base_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_accumulation_base_candidates"
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


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(framework._safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    _patch_framework()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
