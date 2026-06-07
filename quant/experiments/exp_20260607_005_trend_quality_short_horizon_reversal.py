"""exp-20260607-005: trend-quality short-horizon reversal candidate pool.

Replay-only alpha search. It tests one broad, free-OHLCV candidate source:
liquid sector-known stocks that had a sharp three-day idiosyncratic selloff,
remain in an established trend, and reclaim strength on the signal day become
top-1 next-open default-off paper candidates with a fixed five-trading-day
hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260607-005"
STEM = "trend_quality_short_horizon_reversal"
TRIAL_FAMILY = "trend_quality_short_horizon_reversal_candidate_pool"
TRIAL_VARIANT_ID = "trend_quality_short_horizon_reversal_top1_5d_v1"
CHANGED_VARIABLE = "trend_quality_short_horizon_reversal_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260607_005_trend_quality_short_horizon_reversal.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SCRIPT_PATH = Path(__file__)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 5
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
SHORT_LOOKBACK_DAYS = 3
MID_TREND_DAYS = 50
LONG_TREND_DAYS = 100
PULLBACK_HIGH_DAYS = 20

MAX_RET3 = -0.030
MAX_RET3_EXCESS_SPY = -0.020
MIN_SIGNAL_RETURN = 0.004
MIN_SIGNAL_RELATIVE_VS_SPY = 0.006
MIN_CLOSE_LOCATION = 0.62
MIN_CLOSE_VS_SMA50 = 0.0
MIN_SMA50_VS_SMA100 = 0.0
MIN_RET20_EXCESS_SPY = -0.030
MIN_PULLBACK_FROM_20D_HIGH = -0.170
MAX_PULLBACK_FROM_20D_HIGH = -0.035
MIN_VOLUME_RATIO_20D = 0.45
MAX_VOLUME_RATIO_20D = 2.20
MAX_REALIZED_VOL_20D = 0.080

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "cost_sensitive_reversal",
        "concentration_failed",
        "sample_too_small",
    ],
    "confidence_reason": (
        "Short-horizon reversal is plausible but cost-sensitive. The fixed "
        "policy adds liquidity, 50/100-day trend quality, reclaim confirmation, "
        "and top-1/day selection to avoid naked loser-chasing and noisy ticker "
        "pool expansion."
    ),
    "recorded_at": "2026-06-07T03:11:42Z",
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
        "require a shared default-off adapter that computes the same broad "
        "warehouse liquid sector-known universe, three-day excess selloff, "
        "50/100-day trend quality, signal-day reclaim, next-open paper entry, "
        "five-trading-day exit, costs, cooldown, and concentration controls in "
        "both replay and daily production before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = framework._value(row, "Close")
        if close is None:
            return None
        values.append(close)
    return sum(values) / len(values)


def _prior_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        high = framework._value(row, "High")
        if high is None:
            return None
        values.append(high)
    return max(values) if values else None


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
    min_idx = max(LONG_TREND_DAYS, PULLBACK_HIGH_DAYS, 20, SHORT_LOOKBACK_DAYS)
    if idx is None or spy_idx is None or idx < min_idx or spy_idx < 20:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None

    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    ret3 = framework._ret(rows, idx, SHORT_LOOKBACK_DAYS)
    spy_ret3 = framework._ret(spy_rows, spy_idx, SHORT_LOOKBACK_DAYS)
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    close_location = framework._close_location(row)
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx)
    sma50 = _sma(rows, idx, MID_TREND_DAYS)
    sma100 = _sma(rows, idx, LONG_TREND_DAYS)
    prior_high = _prior_high(rows, idx, PULLBACK_HIGH_DAYS)
    required = [
        ret3,
        spy_ret3,
        signal_return,
        spy_signal_return,
        ret20,
        spy_ret20,
        close_location,
        volume_ratio,
        realized_vol20,
        sma50,
        sma100,
        prior_high,
    ]
    if any(value is None for value in required):
        return None

    assert ret3 is not None
    assert spy_ret3 is not None
    assert signal_return is not None
    assert spy_signal_return is not None
    assert ret20 is not None
    assert spy_ret20 is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert realized_vol20 is not None
    assert sma50 is not None
    assert sma100 is not None
    assert prior_high is not None

    ret3_excess_spy = ret3 - spy_ret3
    signal_relative_vs_spy = signal_return - spy_signal_return
    ret20_excess_spy = ret20 - spy_ret20
    close_vs_sma50 = close / sma50 - 1.0
    sma50_vs_sma100 = sma50 / sma100 - 1.0
    pullback_from_20d_high = close / prior_high - 1.0

    if ret3 > MAX_RET3:
        return None
    if ret3_excess_spy > MAX_RET3_EXCESS_SPY:
        return None
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if signal_relative_vs_spy < MIN_SIGNAL_RELATIVE_VS_SPY:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if close_vs_sma50 < MIN_CLOSE_VS_SMA50:
        return None
    if sma50_vs_sma100 < MIN_SMA50_VS_SMA100:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if pullback_from_20d_high < MIN_PULLBACK_FROM_20D_HIGH:
        return None
    if pullback_from_20d_high > MAX_PULLBACK_FROM_20D_HIGH:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None

    sector_meta = sector_entries[ticker]
    score = (
        2.8 * abs(ret3_excess_spy)
        + 1.7 * signal_relative_vs_spy
        + 1.2 * signal_return
        + 0.45 * close_location
        + 0.80 * close_vs_sma50
        + 0.65 * sma50_vs_sma100
        + 0.35 * ret20_excess_spy
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.70 * realized_vol20
        - 0.08 * abs(volume_ratio - 1.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "TREND_QUALITY_SHORT_HORIZON_REVERSAL_PAPER",
        "candidate_score": round(score, 6),
        "candidate_ret3": round(ret3, 6),
        "candidate_spy_ret3": round(spy_ret3, 6),
        "candidate_ret3_excess_spy": round(ret3_excess_spy, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_signal_relative_vs_spy": round(signal_relative_vs_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_close_vs_sma50": round(close_vs_sma50, 6),
        "candidate_sma50_vs_sma100": round(sma50_vs_sma100, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_pullback_from_20d_high": round(pullback_from_20d_high, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
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
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_with_raw_candidates": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()
    for signal_date in dates:
        day_rows: list[dict[str, Any]] = []
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
            day_rows.append(row)
            candidate_tickers.add(ticker)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                float(row["candidate_ret3_excess_spy"]),
                -float(row["candidate_signal_relative_vs_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        context_scan["days_with_raw_candidates"] += 1
        context_scan["raw_candidate_rows"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_ret3_excess_spy": day_rows[0]["candidate_ret3_excess_spy"],
                "top_signal_relative_vs_spy": day_rows[0][
                    "candidate_signal_relative_vs_spy"
                ],
                "top_pullback_from_20d_high": day_rows[0][
                    "candidate_pullback_from_20d_high"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            float(row["candidate_ret3_excess_spy"]),
            -float(row["candidate_signal_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    context_scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            "short_lookback_days": SHORT_LOOKBACK_DAYS,
            "mid_trend_days": MID_TREND_DAYS,
            "long_trend_days": LONG_TREND_DAYS,
            "pullback_high_days": PULLBACK_HIGH_DAYS,
            "max_ret3": MAX_RET3,
            "max_ret3_excess_spy": MAX_RET3_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_close_vs_sma50": MIN_CLOSE_VS_SMA50,
            "min_sma50_vs_sma100": MIN_SMA50_VS_SMA100,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_pullback_from_20d_high": MIN_PULLBACK_FROM_20D_HIGH,
            "max_pullback_from_20d_high": MAX_PULLBACK_FROM_20D_HIGH,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, context_scan


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
        "positive_replay_lead_not_promoted_trend_quality_short_horizon_reversal"
        if gate["passed"]
        else "rejected_trend_quality_short_horizon_reversal_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Liquid sector-known stocks that sell off sharply versus SPY "
                "over three days but remain in a 50/100-day uptrend and reclaim "
                "strength on the signal day may add short-horizon mean-reversion "
                "candidates without adding noisy tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": "free_ohlcv_trend_quality_reversal_candidate_source",
            "nearby_prior_experiments": [
                "exp-20260601-007",
                "exp-20260529-013",
                "exp-20260526-011",
                "exp-20260528-037",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "decision": gate4["decision"],
            "status": "accepted" if gate4["passed"] else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The trend-quality short-horizon reversal candidate source "
                "cleared Gate 4 as a replay-only/default-off lead, but no "
                "production surface was promoted."
                if gate4["passed"]
                else (
                    "The trend-quality short-horizon reversal candidate source "
                    "did not clear Gate 4. Do not promote it or answer by "
                    "retuning nearby ret3, trend, volume, hold-day, cooldown, "
                    "or notional thresholds on these frozen windows."
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that short-horizon reversal "
                "inside liquid trend names is either erased by costs/slippage or "
                "clusters in fragile drawdown regimes. A retry needs a materially "
                "new PIT field or forward replacement evidence, not parameter "
                "sweeps around the same OHLCV reversal definition."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source had enough sample size and passed concentration "
                    "checks, but the edge appeared only in mid_weak. late_strong "
                    "and old_thin both lost EV/PnL, and old_thin added 2.50pp of "
                    "drawdown, which means the ret3 excess selloff plus signal-day "
                    "reclaim still selects fragile rebounds rather than stable "
                    "replacement candidates after costs and slippage."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry this frozen sample by changing ret3, SPY-excess, "
                    "SMA50/SMA100, pullback, close-location, volume-ratio, "
                    "realized-volatility, hold-day, top-N, cooldown, or paper "
                    "notional thresholds."
                ),
                "new_evidence_required": (
                    "A retry requires independent PIT confirmation with adequate "
                    "historical coverage, such as borrow pressure, options "
                    "structure, ownership, or event/news context, or closed forward "
                    "replacement-value rows under a shared default-off adapter."
                ),
            },
            "next_evidence_needed": (
                "A valid retry needs independent context such as PIT news, "
                "borrow/options/ownership confirmation with adequate historical "
                "coverage, or closed forward replacement-value rows."
            ),
            "related_files": [
                _repo_rel(SCRIPT_PATH),
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
    )
    payload.setdefault("parameters", {}).clear()
    payload["parameters"].update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "short_lookback_days": SHORT_LOOKBACK_DAYS,
            "mid_trend_days": MID_TREND_DAYS,
            "long_trend_days": LONG_TREND_DAYS,
            "pullback_high_days": PULLBACK_HIGH_DAYS,
            "max_ret3": MAX_RET3,
            "max_ret3_excess_spy": MAX_RET3_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_close_vs_sma50": MIN_CLOSE_VS_SMA50,
            "min_sma50_vs_sma100": MIN_SMA50_VS_SMA100,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_pullback_from_20d_high": MIN_PULLBACK_FROM_20D_HIGH,
            "max_pullback_from_20d_high": MAX_PULLBACK_FROM_20D_HIGH,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history needed for ret3, SMA50/SMA100, 20-day high, ADV, "
        "and realized volatility. Paper entry is next available open with "
        "existing entry slippage; exit is the close five trading days after "
        "the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: trend-quality liquid names with a sharp "
            "three-day SPY-excess selloff and signal-day reclaim may mean "
            "revert over the next five trading days."
        ),
        "2_history_check": {
            "exp-20260601-007": (
                "Short-horizon reversal attribution was proposed/read-only, "
                "not a closed candidate-pool Gate 1-4 run."
            ),
            "exp-20260529-013 and exp-20260526-011": (
                "Pullback/RS variants were mixed or unresolved; this run uses "
                "a fixed trend-quality reversal and shorter hold, not a "
                "threshold sweep of that family."
            ),
            "exp-20260528-037": (
                "Ticker accumulation-quality breakout failed badly; this run "
                "does not chase breakouts, and requires prior selloff plus "
                "reclaim inside trend."
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
            "exp_20260607_005_trend_quality_short_horizon_reversal.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The trend-quality reversal "
        "candidate source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
    payload["context_alias"] = "reversal_candidate_day_contexts"
    payload["pressure_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Trend-Quality Short-Horizon Reversal",
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
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
        "aggregate_expected_value_delta": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"][
                    "by_window"
                ][label]["total_pnl"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(SCRIPT_PATH),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(SCRIPT_PATH): framework._sha256(SCRIPT_PATH),
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
