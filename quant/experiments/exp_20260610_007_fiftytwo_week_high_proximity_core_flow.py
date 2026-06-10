"""exp-20260610-007: 52-week-high proximity breakout core-flow candidate pool.

Replay-only alpha search. This tests one candidate-source variable: liquid,
sector-known common-stock-like tickers that, on the signal day, are pushing into
a fresh 52-week-high zone (close within 3% of the trailing 252-day high AND a
new >60-day-high breakout) with leadership and close/volume quality, admitted
only when the same signal date already has core A/B entry flow and excluding
same-ticker core overlap, before a top-1 next-open default-off paper entry with
a fixed 10-trading-day hold.

Mechanism: George & Hwang (2004) show nearness to the 52-week high predicts
cross-sectional returns through anchoring underreaction, distinct from and
dominating ordinary trailing-return momentum. Raw breakout/momentum pools have
repeatedly failed drawdown/tail and accepted-comparator checks here, so this
adds the accepted core-flow displacement anchor to measure independent
replacement value rather than pure beta.

To compute a true 52-week (252-trading-day) high, this runner extends the
candidate-snapshot lookback to load >= 252 prior trading days. This uses only
past, point-in-time data; it never reads future bars.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import exp_20260609_026_turn_of_month_liquid_leadership as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260610-007"
STEM = "fiftytwo_week_high_proximity_core_flow"
TRIAL_FAMILY = "fiftytwo_week_high_proximity_breakout_candidate_pool"
TRIAL_VARIANT_ID = "fiftytwo_week_high_proximity_core_flow_top1_next_open_10d_v1"
CHANGED_VARIABLE = "fiftytwo_week_high_proximity_core_flow_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_007_{STEM}.json"
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

MIN_TARGET_TRADES = previous.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = previous.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

EXCLUDED_TICKERS = previous.EXCLUDED_TICKERS

# 52-week-high proximity breakout candidate gates (fixed before run).
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 75_000_000.0
HIGH_252_LOOKBACK = 252
NEW_HIGH_BREAKOUT_LOOKBACK = 60
MIN_PROXIMITY_TO_52W_HIGH = 0.97  # close >= 97% of trailing 252-day high
MIN_RET20_EXCESS_SPY = 0.000  # SPY-relative leadership over 20 sessions
MIN_RET60_EXCESS_SPY = -0.020
MIN_SIGNAL_RETURN = 0.005
MIN_CLOSE_LOCATION = 0.60
MIN_VOLUME_RATIO_20D = 0.90
MAX_VOLUME_RATIO_20D = 3.50
MIN_RET5 = -0.020
MAX_RET5 = 0.120
MAX_REALIZED_VOL_20D = 0.080
# extended snapshot lookback so the 252-day high is always computable
SNAPSHOT_LOOKBACK_CALENDAR_DAYS = 470

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_CORE_FLOW_COMPARATOR = {
    "experiment_id": "exp-20260608-008",
    "decision": "accepted_industry_stable_core_flow_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1459,
    "total_pnl_delta_sum": 3731.54,
    "target_trade_count": 47,
}

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_momentum_not_anchoring_edge",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_compression_comparator_not_beaten",
        "thin_sample",
    ],
    "confidence_reason": (
        "52-week-high proximity is a recognized anomaly distinct from trailing "
        "momentum (George-Hwang 2004), not in the rejected/anti-repeat list, "
        "free-OHLCV PIT-safe, and uses the accepted core-flow displacement "
        "anchor; but broad breakout/momentum pools have repeatedly failed "
        "drawdown/tail and comparator checks here, so prior is low."
    ),
    "recorded_at": "2026-06-10T05:15:10+00:00",
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
        "require a shared default-off adapter that computes the same liquid "
        "sector-known universe, trailing 252-day-high proximity, 60-day new-high "
        "breakout, SPY-relative leadership, close/volume quality gates, same-day "
        "core A/B entry-flow confirmation, same-ticker core-overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, accepted "
        "compression/core-flow comparators, and concentration controls in both "
        "historical replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could "
        "change. The extended candidate-snapshot lookback only reads past, "
        "point-in-time bars and never future data."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "entry/candidate_pool: anchoring underreaction at the 52-week high "
        "(George-Hwang 2004) should make liquid sector-known stocks that push "
        "into a fresh 52-week-high zone (within 3% of the trailing 252-day high "
        "and breaking a new 60-day high) with SPY-relative leadership and strong "
        "close/volume quality continue after next-open entry, especially when "
        "the same day already shows core A/B entry flow. Uses only free OHLCV."
    ),
    "2_history_check": {
        "no_exact_prior_found": (
            "Search found compression, accumulation-base, low-vol high-breakout, "
            "and broad-winner continuation candidate pools, but no 52-week-high "
            "proximity (252-day-high) anchoring source gated by core flow."
        ),
        "nearby_breakout_trials": (
            "exp-20260606-015 low-vol 20d high breakout and exp-20260608-016 "
            "accumulation-base breakout were rejected/thin; exp-20260608-013 "
            "narrow-range compression breakout was accepted. Those use short "
            "(<=60 day) range/high references, not a true 52-week-high anchor."
        ),
        "accepted_comparators": (
            "This run must beat accepted compression exp-20260608-013 and the "
            "closest accepted core-flow relation exp-20260608-008 before any "
            "promotion pressure."
        ),
        "frozen_lanes_avoided": (
            "No LLM soft ranking, revision proxy, Form4 sparse retry, "
            "Companyfacts scalar mining, state-surface notional/profile retune, "
            "or turn-of-month/OPEX calendar threshold sweep is involved."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: liquid sector-known universe, close within 3% "
        "of the trailing 252-day high and a new 60-day-high breakout, "
        "SPY-relative 20-day leadership, signal-day return/close/volume quality, "
        "extension guards, same-day core A/B entry-flow confirmation, "
        "same-ticker core-overlap exclusion, top-1 next-open paper entry, "
        "10-day hold, cost, cooldown, and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "promotion lead if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and accepted "
        "compression plus core-flow comparators are beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_007_fiftytwo_week_high_proximity_core_flow.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_window_snapshot_deep(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Window snapshot with >= 252 trading days of lookback for a 52-week high.

    Identical to the framework loader except the start of the load window is
    pushed back far enough that the trailing 252-day high is computable for
    every signal date inside the canonical window. Only past bars are read.
    """
    start = framework._parse_date(cfg["start"]) - timedelta(
        days=SNAPSHOT_LOOKBACK_CALENDAR_DAYS
    )
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
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
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
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


def _trailing_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    highs = [framework._value(rows[i], "High") for i in range(idx - lookback + 1, idx + 1)]
    highs = [value for value in highs if value is not None]
    if len(highs) < lookback:
        return None
    return max(highs)


def _prior_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    highs = [framework._value(rows[i], "High") for i in range(idx - lookback, idx)]
    highs = [value for value in highs if value is not None]
    if len(highs) < lookback:
        return None
    return max(highs)


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
    if idx < HIGH_252_LOOKBACK or spy_idx < 65:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    high252 = _trailing_high(rows, idx, HIGH_252_LOOKBACK)
    prior60_high = _prior_high(rows, idx, NEW_HIGH_BREAKOUT_LOOKBACK)
    if high252 is None or prior60_high is None or high252 <= 0:
        return None
    proximity = close / high252
    if proximity < MIN_PROXIMITY_TO_52W_HIGH:
        return None
    # fresh breakout: close clears the prior 60-day high
    if close <= prior60_high:
        return None

    signal_return = framework._daily_return(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx)
    if None in (
        signal_return,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        close_location,
        volume_ratio,
        realized_vol20,
    ):
        return None

    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None

    # higher score = closer to/through the 52-week high, stronger leadership,
    # cleaner close, lower realized vol and less short-term overextension.
    proximity_edge = proximity - MIN_PROXIMITY_TO_52W_HIGH
    score = (
        2.20 * proximity_edge
        + 1.30 * ret20_excess_spy
        + 0.55 * ret60_excess_spy
        + 0.45 * signal_return
        + 0.35 * close_location
        - 0.90 * realized_vol20
        - 0.25 * max(ret5, 0.0)
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "FIFTYTWO_WEEK_HIGH_PROXIMITY_CORE_FLOW_PAPER",
        "candidate_score": round(score, 6),
        "candidate_close": round(close, 6),
        "candidate_high_252d": round(high252, 6),
        "candidate_proximity_to_52w_high": round(proximity, 6),
        "candidate_prior_60d_high": round(prior60_high, 6),
        "candidate_new_60d_high_breakout": True,
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
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
    all_dates = framework.shadow._trading_dates(snapshot)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "core_flow_days": 0,
        "days_with_raw_candidates": 0,
        "raw_candidates": 0,
        "raw_candidates_missing_core_flow": 0,
    }

    for signal_date in dates:
        ab_entries = entries_by_date.get(signal_date, [])
        # core-flow displacement anchor: require same-day core A/B entry flow
        if not ab_entries:
            continue
        scan["core_flow_days"] += 1
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
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = True
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_proximity_to_52w_high"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "same_day_ab_entry_count": len(ab_entries),
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_proximity_to_52w_high": day_rows[0][
                    "candidate_proximity_to_52w_high"
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
            -float(row["candidate_proximity_to_52w_high"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "high_252_lookback": HIGH_252_LOOKBACK,
            "new_high_breakout_lookback": NEW_HIGH_BREAKOUT_LOOKBACK,
            "min_proximity_to_52w_high": MIN_PROXIMITY_TO_52W_HIGH,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "core_flow_confirmation_required": True,
            "same_ticker_core_overlap_excluded": True,
            "snapshot_lookback_calendar_days": SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
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
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_CORE_FLOW_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_core_flow_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_CORE_FLOW_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_core_flow_pnl_not_beaten")
    gate["accepted_comparators"] = {
        "compression": ACCEPTED_COMPRESSION_COMPARATOR,
        "core_flow": ACCEPTED_CORE_FLOW_COMPARATOR,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fiftytwo_week_high_proximity_core_flow"
        if gate["passed"]
        else "rejected_fiftytwo_week_high_proximity_core_flow_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_ohlcv_fiftytwo_week_high_proximity_field"
            ),
            "nearby_prior_experiments": [
                "exp-20260608-013",
                "exp-20260608-008",
                "exp-20260606-015",
                "exp-20260608-016",
                "exp-20260609-027",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                "compression": ACCEPTED_COMPRESSION_COMPARATOR,
                "core_flow": ACCEPTED_CORE_FLOW_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that 52-week-high proximity "
                "breakout is generic liquid momentum/beta rather than a distinct "
                "anchoring-underreaction replacement-value pool after next-open "
                "execution, costs, cooldown, and same-ticker core-overlap "
                "exclusion, or its tail risk breaches the drawdown guard. Do not "
                "answer by sweeping proximity threshold, breakout lookback, "
                "ret20/ret60 thresholds, close-location, volume bounds, top-N, "
                "hold-day, cooldown, or notional on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new evidence beyond price-anchor "
                "geometry, such as a point-in-time fundamental/quality gate that "
                "separates durable 52-week-high leaders from exhausted ones, an "
                "options/borrow structure field, or forward daily-snapshot "
                "replacement value. Pure threshold retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "high_252_lookback": HIGH_252_LOOKBACK,
        "new_high_breakout_lookback": NEW_HIGH_BREAKOUT_LOOKBACK,
        "min_proximity_to_52w_high": MIN_PROXIMITY_TO_52W_HIGH,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
        "min_ret5": MIN_RET5,
        "max_ret5": MAX_RET5,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "core_flow_confirmation_required": True,
        "same_ticker_core_overlap_excluded": True,
        "snapshot_lookback_calendar_days": SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The 52-week-high proximity breakout core-flow bundle cleared the "
            "canonical three-window gates and beat the accepted "
            "compression/core-flow comparators, suggesting anchoring "
            "underreaction at the 52-week high added replacement value beyond "
            "generic liquid momentum. It remains only a replay lead because no "
            "shared daily adapter or production parity path was added."
            if passed
            else (
                "The 52-week-high proximity breakout core-flow bundle failed "
                "Gate 4. The result implies the 52-week-high anchor did not add "
                "enough distinct edge beyond liquid momentum/beta after next-open "
                "execution, costs, cooldown, and overlap/concentration controls, "
                "or its tail risk breached the drawdown guard. The useful lesson "
                "is to seek a fundamental/structural separator of durable vs "
                "exhausted 52-week-high leaders, not more price-geometry tuning."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping the 52-week proximity threshold, the "
            "252-day-high or 60-day breakout lookbacks, ret20/ret60 "
            "relative-strength thresholds, signal-day return, close-location, "
            "volume-ratio bounds, top-N, hold-day, cooldown, or paper notional "
            "on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The 52-week-high proximity breakout core-flow source passed as a "
        "replay-only promotion lead, but no production surface changed and a "
        "shared default-off parity adapter is required before use."
        if passed
        else (
            "The 52-week-high proximity breakout core-flow source was rejected; "
            "it did not establish a distinct free-OHLCV anchoring candidate-pool "
            "edge under the standard three-window protocol and accepted-comparator "
            "checks."
        )
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Core-flow days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {cf} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                cf=scan.get("core_flow_days", 0),
                days=scan.get("days_with_raw_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} 52-Week-High Proximity Breakout Core-Flow Candidate Pool",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
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
            "- Compression comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Core-flow comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_CORE_FLOW_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_CORE_FLOW_COMPARATOR["total_pnl_delta_sum"],
            ),
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
        "numeric_gate4_passed": payload["gate4"]["passed"],
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
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "core_flow_day_count": payload["context_scan_by_window"][label].get(
                    "core_flow_days"
                ),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
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
    framework._load_window_snapshot = _load_window_snapshot_deep
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
