"""exp-20260611-009: pocket-pivot accumulation leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: the "pocket pivot" volume signature (O'Neil /
Morales). On the signal day the stock is in an established uptrend (close above
a rising 50-day SMA) but has not yet broken out to a fresh 60-day high, prints
an up day that closes in the upper part of its range, and -- the distinct
field -- its signal-day volume exceeds the maximum DOWN-day volume of the prior
10 trading days. That volume signature is meant to flag stealth institutional
accumulation inside a base, before a new-high breakout.

It is distinct from the accepted 52-week-high proximity breakout
(exp-20260610-008, which requires a fresh high) and the accepted narrow-range
compression breakout (exp-20260608-013, which requires range
compression+expansion), and it is the opposite of "quiet low-volume
accumulation" because a pocket pivot requires a volume surge versus recent
down days.

It remains default-off paper only; no production path, shared adapter,
live/default order, ranking, sizing, exit, LLM/news, or watchlist behavior is
changed. No JavaScript was used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260611-009"
STEM = "pocket_pivot_accumulation_leadership"
TRIAL_FAMILY = "pocket_pivot_accumulation_leadership_candidate_pool"
TRIAL_VARIANT_ID = "pocket_pivot_accumulation_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "pocket_pivot_accumulation_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_009_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0

# Pocket-pivot core definition.
DOWN_VOLUME_LOOKBACK_DAYS = 10
MIN_POCKET_VOLUME_RATIO_VS_MAX_DOWN = 1.0
TREND_SMA_WINDOW = 50
TREND_SLOPE_LOOKBACK = 10
BASE_HIGH_LOOKBACK = 60
# Must be at or below the 60-day high (not a fresh breakout) yet within a
# constructive base, not deeply broken down.
MAX_RECLAIM_VS_60D_HIGH = 0.005
MIN_RECLAIM_VS_60D_HIGH = -0.18

MIN_CANDIDATE_SIGNAL_RETURN = 0.005
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.0
MIN_CANDIDATE_CLOSE_LOCATION = 0.60
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.90
MAX_CANDIDATE_RET5 = 0.12
MAX_CANDIDATE_RET20 = 0.35
MIN_CANDIDATE_RET20_EXCESS_SPY = 0.0
MIN_CANDIDATE_RET60 = 0.0
MAX_CANDIDATE_REALIZED_VOL_20 = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
    "target_trade_count": 44,
}

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "ohlcv_momentum_relabel",
        "accepted_compression_comparator_not_beaten",
        "old_thin_regression",
        "tail_concentration",
        "thin_sample",
    ],
    "confidence_reason": (
        "The pocket pivot (O'Neil/Morales) flags stealth institutional "
        "accumulation when signal-day up-volume exceeds the prior 10-day max "
        "down-volume inside an existing uptrend but before a new-high "
        "breakout. It is a distinct production-visible free-OHLCV volume "
        "signature, not a new-high breakout (exp-20260610-008), a range "
        "compression+expansion (exp-20260608-013), or quiet low-volume "
        "accumulation. Distribution-day absorption leadership "
        "(exp-20260611-007) shows institutional-flow OHLCV labels can add "
        "value, but most broad momentum relabels failed, so the main risk is "
        "that the volume signature only rediscovers momentum and fails to beat "
        "the accepted compression comparator after costs and concentration."
    ),
    "recorded_at": "2026-06-11T06:13:00+00:00",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain a replay lead until a shared default-off adapter computes the "
        "same pocket-pivot volume signature, uptrend/base position fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "controls in both historical replay and daily production."
    ),
}

BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _sma(rows: list[dict[str, Any]], idx: int, window: int) -> float | None:
    if idx < window - 1:
        return None
    closes = [framework._value(rows[pos], "Close") for pos in range(idx - window + 1, idx + 1)]
    if any(value is None for value in closes):
        return None
    valid = [float(value) for value in closes if value is not None]
    return sum(valid) / len(valid)


def _base_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    highs = [framework._value(rows[pos], "High") for pos in range(idx - lookback, idx)]
    if any(value is None for value in highs):
        return None
    valid = [float(value) for value in highs if value is not None]
    return max(valid) if valid else None


def _max_down_volume(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    best = 0.0
    for pos in range(idx - lookback, idx):
        daily = framework._daily_return(rows, pos)
        volume = framework._value(rows[pos], "Volume")
        if daily is None or volume is None:
            continue
        if daily < 0.0:
            best = max(best, float(volume))
    # 0.0 means no qualifying down day in the lookback: the pocket-pivot volume
    # test then passes for any positive signal-day volume.
    return best


def _pocket_pivot_candidate(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < (BASE_HIGH_LOOKBACK + 1) or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    # Signal-day character: an up day closing strong on real participation.
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    signal_volume = framework._value(rows[idx], "Volume")
    if signal_return is None or close_location is None or volume_ratio is None or signal_volume is None:
        return None
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None

    # Pocket-pivot volume signature: signal-day volume exceeds the prior
    # 10-day maximum down-day volume.
    max_down_volume = _max_down_volume(rows, idx, DOWN_VOLUME_LOOKBACK_DAYS)
    if max_down_volume is None:
        return None
    if max_down_volume > 0.0:
        pocket_volume_ratio = float(signal_volume) / float(max_down_volume)
    else:
        pocket_volume_ratio = float("inf")
    if pocket_volume_ratio < MIN_POCKET_VOLUME_RATIO_VS_MAX_DOWN:
        return None

    # Established uptrend, but inside a base (not a fresh 60-day-high breakout).
    sma_now = _sma(rows, idx, TREND_SMA_WINDOW)
    sma_prev = _sma(rows, idx - TREND_SLOPE_LOOKBACK, TREND_SMA_WINDOW)
    if sma_now is None or sma_prev is None:
        return None
    if not (close > sma_now and sma_now > sma_prev):
        return None
    base_high = _base_high(rows, idx, BASE_HIGH_LOOKBACK)
    if base_high is None or base_high <= 0:
        return None
    reclaim_vs_high = (float(close) / float(base_high)) - 1.0
    if reclaim_vs_high > MAX_RECLAIM_VS_60D_HIGH:
        return None
    if reclaim_vs_high < MIN_RECLAIM_VS_60D_HIGH:
        return None

    # Leadership and extension guards.
    spy_return = framework._daily_return(spy_rows, spy_idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    realized_vol = framework._realized_vol(rows, idx)
    required = [spy_return, ret5, ret20, ret60, spy_ret20, realized_vol]
    if any(value is None for value in required):
        return None
    assert spy_return is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert realized_vol is not None

    relative_vs_spy = float(signal_return) - float(spy_return)
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    if ret20 > MAX_CANDIDATE_RET20:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60 < MIN_CANDIDATE_RET60:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None

    sector_meta = sector_entries[ticker]
    pocket_strength = min(pocket_volume_ratio, 6.0) if math.isfinite(pocket_volume_ratio) else 6.0
    score = (
        1.8 * ret20_excess_spy
        + 1.2 * relative_vs_spy
        + 0.50 * close_location
        + 0.25 * math.log10(max(pocket_strength, 1.0) + 1.0)
        + 0.20 * min(max(reclaim_vs_high + 0.18, 0.0), 0.185)
        + 0.04 * math.log10(max(float(adv20), 1.0) / 1_000_000.0)
        - 0.60 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "POCKET_PIVOT_ACCUMULATION_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(float(signal_return), 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_ret5": round(float(ret5), 6),
        "candidate_ret20": round(float(ret20), 6),
        "candidate_ret60": round(float(ret60), 6),
        "candidate_spy_ret20": round(float(spy_ret20), 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_close_location": round(float(close_location), 6),
        "candidate_avg_dollar_volume_20d": round(float(adv20), 2),
        "candidate_volume_ratio_20d": round(float(volume_ratio), 6),
        "candidate_pocket_volume_ratio_vs_max_down": (
            round(float(pocket_volume_ratio), 6) if math.isfinite(pocket_volume_ratio) else None
        ),
        "candidate_pocket_no_down_day_in_lookback": max_down_volume <= 0.0,
        "candidate_realized_vol_20d": round(float(realized_vol), 6),
        "candidate_base_60d_high": round(float(base_high), 6),
        "candidate_reclaim_vs_60d_high": round(reclaim_vs_high, 6),
        "candidate_sma50": round(float(sma_now), 6),
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
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_with_raw_candidates": 0,
        "raw_pocket_pivot_candidates": 0,
        "pocket_no_down_day_count": 0,
        "down_volume_lookback_days": DOWN_VOLUME_LOOKBACK_DAYS,
        "min_pocket_volume_ratio_vs_max_down": MIN_POCKET_VOLUME_RATIO_VS_MAX_DOWN,
        "base_high_lookback": BASE_HIGH_LOOKBACK,
        "rule_version": RULE_VERSION,
    }
    for signal_date in dates:
        day_count = 0
        for ticker in sector_entries:
            row = _pocket_pivot_candidate(
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
            if row.get("candidate_pocket_no_down_day_in_lookback"):
                context_scan["pocket_no_down_day_count"] += 1
            day_count += 1
        if day_count:
            context_scan["days_with_raw_candidates"] += 1
            context_scan["raw_pocket_pivot_candidates"] += day_count
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    # No market precondition: contexts list is intentionally empty.
    return candidates, [], context_scan


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
    failed = list(gate.get("failed_reasons") or [])
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_compression_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_compression_pnl_not_beaten")
    passed = not failed
    gate.update(
        {
            "passed": passed,
            "decision": (
                "positive_replay_lead_not_promoted_pocket_pivot_accumulation_leadership"
                if passed
                else "rejected_pocket_pivot_accumulation_leadership_candidate_pool"
            ),
            "failed_reasons": failed,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        }
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    passed = bool(gate4["passed"])
    decision = gate4["decision"]
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    rationale = (
        "The pocket-pivot accumulation source beat Gate 4 and the accepted "
        "compression comparator numerically, but no shared daily/backtest "
        "helper was implemented, so this is only a replay lead."
        if passed
        else (
            "The pocket-pivot accumulation source did not clear Gate 4 or the "
            "accepted compression comparator. Do not promote or retry this "
            "fixed OHLCV pocket-pivot definition on the same frozen windows "
            "without materially new PIT flow or forward replacement-value data."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": decision,
            "hypothesis": (
                "Pocket-pivot accumulation leadership may identify liquid "
                "stocks in an uptrend where signal-day up-volume exceeds the "
                "prior 10-day maximum down-day volume before a new-high "
                "breakout, flagging stealth institutional accumulation and "
                "producing next-open 10-day replacement value."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260611-007",
                "exp-20260610-008",
                "exp-20260608-013",
                "exp-20260605-033",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_free_ohlcv_pocket_pivot_volume_signature",
            "prediction": {
                **PREDICTION,
                "actual_success": 1 if passed else 0,
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "brier_score": round((PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2, 6),
            },
            "calibration": {
                "predicted_success_probability": PREDICTION["success_probability"],
                "actual_gate4_passed": passed,
                "failure_modes_observed": gate4["failed_reasons"],
                "brier_score": round((PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2, 6),
            },
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": rationale,
            "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "next_evidence_needed": (
                "A retry needs materially new PIT flow evidence such as "
                "constituent fund-flow, options/borrow pressure, or closed "
                "forward replacement rows. Do not retune the down-volume "
                "lookback, pocket volume ratio, base-high distance, trend SMA, "
                "ret5/ret20, top-N, hold, cooldown, or notional on these frozen "
                "windows."
            ),
            "negative_reflection": {
                "why_result_happened": rationale,
                "near_neighbor_freeze": (
                    "Freeze pocket-pivot volume-signature / base-position "
                    "threshold variants on the canonical windows unless new PIT "
                    "flow or forward replacement-value evidence arrives."
                ),
            },
            "post_run_reflection": {
                "why_result_happened": rationale,
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping the down-volume lookback, pocket "
                    "volume ratio, base-high distance, trend SMA window/slope, "
                    "close-location, volume ratio, candidate ret5/ret20, top-N, "
                    "hold-day, cooldown, or paper notional on this frozen sample."
                ),
                "new_evidence_required": (
                    "Need a materially new PIT fund-flow/borrow/options field "
                    "or forward replacement rows proving the pocket-pivot label "
                    "is not ordinary momentum."
                ),
            },
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "down_volume_lookback_days": DOWN_VOLUME_LOOKBACK_DAYS,
            "min_pocket_volume_ratio_vs_max_down": MIN_POCKET_VOLUME_RATIO_VS_MAX_DOWN,
            "trend_sma_window": TREND_SMA_WINDOW,
            "trend_slope_lookback": TREND_SLOPE_LOOKBACK,
            "base_high_lookback": BASE_HIGH_LOOKBACK,
            "max_reclaim_vs_60d_high": MAX_RECLAIM_VS_60D_HIGH,
            "min_reclaim_vs_60d_high": MIN_RECLAIM_VS_60D_HIGH,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: a pocket-pivot volume signature (signal-day "
            "up-volume above the prior 10-day max down-volume) inside an uptrend "
            "but before a new-high breakout may flag stealth institutional "
            "accumulation that precedes next-open continuation."
        ),
        "2_history_check": {
            "exp-20260611-007": (
                "Distribution-day absorption leadership accepted, showing "
                "institutional-flow OHLCV labels can add replacement value; this "
                "tests a separate volume-signature field."
            ),
            "exp-20260610-008": (
                "52-week-high proximity breakout is accepted but requires a "
                "fresh high; pocket pivots fire inside the base before a "
                "breakout."
            ),
            "exp-20260608-013": (
                "Accepted compression breakout is the closest OHLCV comparator "
                "and must be beaten for retention."
            ),
            "exp-20260605-033": (
                "Cross-section pressure resilience framework reused for the "
                "replay-only default-off overlay harness."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md canonical windows. Aggregate EV/PnL must "
            "improve, no EV/PnL regression window, target sample >=20 across "
            "all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
            "concentration pass, and aggregate EV/PnL must beat accepted "
            "compression exp-20260608-013."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260611_009_pocket_pivot_accumulation_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. Pocket-pivot accumulation "
        "leadership is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
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
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {candidate_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                candidate_days=scan.get("days_with_raw_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_compression_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Pocket-Pivot Accumulation Leadership",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                comparator["expected_value_score_delta_sum"],
                comparator["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
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
                "candidate_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
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
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_PRICE = MIN_PRICE
    framework.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
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


def _update_ticket(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
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
                "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
                "accepted": False,
                "numeric_gate4_passed": log_record["numeric_gate4_passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
