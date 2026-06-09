"""exp-20260609-004: post-thrust inside-day absorption candidates.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: after a liquid stock has a high-volume upside
thrust day, a tight inside/pause day near the prior high with volume dry-up
may indicate institutional absorption rather than a noisy gap chase.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260609_002_gap_and_hold_institutional_demand as base


framework = base.framework

EXPERIMENT_ID = "exp-20260609-004"
STEM = "post_thrust_inside_day_absorption"
TRIAL_FAMILY = "post_thrust_inside_day_absorption_candidate_pool"
TRIAL_VARIANT_ID = "post_thrust_inside_day_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "post_thrust_inside_day_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = base.MIN_AVG_DOLLAR_VOLUME_20D
MIN_PRIOR_THRUST_RETURN = 0.025
MAX_PRIOR_THRUST_RETURN = 0.105
MIN_PRIOR_CLOSE_LOCATION = 0.70
MIN_PRIOR_VOLUME_RATIO_20D = 1.10
MAX_PRIOR_VOLUME_RATIO_20D = 4.75
MIN_SIGNAL_CLOSE_VS_PRIOR_CLOSE = -0.025
MAX_SIGNAL_CLOSE_VS_PRIOR_CLOSE = 0.035
MAX_SIGNAL_RANGE_PCT = 0.060
MAX_SIGNAL_RANGE_TO_PRIOR_RANGE = 0.85
MAX_SIGNAL_HIGH_VS_PRIOR_HIGH = 0.015
MIN_SIGNAL_LOW_VS_PRIOR_LOW = -0.030
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MIN_SIGNAL_VOLUME_RATIO_20D = 0.35
MAX_SIGNAL_VOLUME_RATIO_20D = 1.20
MIN_RET20_EXCESS_SPY = -0.015
MIN_RET60_EXCESS_SPY = -0.035
MIN_RET5 = -0.025
MAX_RET5 = 0.140
MAX_RET20 = 0.380
MAX_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = base.ACCEPTED_COMPRESSION_COMPARATOR

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_regression",
        "drawdown_drift",
        "inside_day_relabels_stale_momentum",
        "target_sample_too_small",
        "accepted_compression_comparator_not_beaten",
    ],
    "confidence_reason": (
        "History shows compression and VCP-like structures can work, but recent "
        "gap-hold, breadth-confirmed gap-hold, and quiet accumulation neighbors "
        "failed. This test isolates a two-day thrust-then-dry-up absorption "
        "morphology using only PIT OHLCV, not a gap threshold retune."
    ),
    "recorded_at": "2026-06-09T04:08:10+00:00",
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
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain a replay lead until a shared default-off adapter computes the "
        "same prior-thrust, signal-day inside/pause, volume dry-up, "
        "SPY-relative trend, same-ticker core-overlap exclusion, next-open "
        "paper entry, 10-trading-day exit, costs, cooldown, comparator, and "
        "concentration controls in both historical replay and daily production."
    ),
}

BASE_GATE4 = base.BASE_GATE4
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD


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
    return (high - low) / close


def _close_vs_prior_close(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    close = framework._value(rows[idx], "Close")
    prior_close = framework._value(rows[idx - 1], "Close")
    if close is None or prior_close is None or prior_close <= 0:
        return None
    return close / prior_close - 1.0


def _high_vs_prior_high(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    high = framework._value(rows[idx], "High")
    prior_high = framework._value(rows[idx - 1], "High")
    if high is None or prior_high is None or prior_high <= 0:
        return None
    return high / prior_high - 1.0


def _low_vs_prior_low(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    low = framework._value(rows[idx], "Low")
    prior_low = framework._value(rows[idx - 1], "Low")
    if low is None or prior_low is None or prior_low <= 0:
        return None
    return low / prior_low - 1.0


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in base.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    prior_return = framework._daily_return(rows, idx - 1)
    prior_close_location = framework._close_location(rows[idx - 1])
    prior_volume_ratio = framework._volume_ratio(rows, idx - 1)
    prior_range = _range_pct(rows[idx - 1])
    signal_range = _range_pct(rows[idx])
    signal_close_vs_prior = _close_vs_prior_close(rows, idx)
    signal_high_vs_prior = _high_vs_prior_high(rows, idx)
    signal_low_vs_prior = _low_vs_prior_low(rows, idx)
    signal_close_location = framework._close_location(rows[idx])
    signal_volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        prior_return,
        prior_close_location,
        prior_volume_ratio,
        prior_range,
        signal_range,
        signal_close_vs_prior,
        signal_high_vs_prior,
        signal_low_vs_prior,
        signal_close_location,
        signal_volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert prior_return is not None
    assert prior_close_location is not None
    assert prior_volume_ratio is not None
    assert prior_range is not None
    assert signal_range is not None
    assert signal_close_vs_prior is not None
    assert signal_high_vs_prior is not None
    assert signal_low_vs_prior is not None
    assert signal_close_location is not None
    assert signal_volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None

    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    range_ratio = signal_range / prior_range if prior_range > 0 else None
    if range_ratio is None:
        return None

    if prior_return < MIN_PRIOR_THRUST_RETURN or prior_return > MAX_PRIOR_THRUST_RETURN:
        return None
    if prior_close_location < MIN_PRIOR_CLOSE_LOCATION:
        return None
    if (
        prior_volume_ratio < MIN_PRIOR_VOLUME_RATIO_20D
        or prior_volume_ratio > MAX_PRIOR_VOLUME_RATIO_20D
    ):
        return None
    if (
        signal_close_vs_prior < MIN_SIGNAL_CLOSE_VS_PRIOR_CLOSE
        or signal_close_vs_prior > MAX_SIGNAL_CLOSE_VS_PRIOR_CLOSE
    ):
        return None
    if signal_range > MAX_SIGNAL_RANGE_PCT:
        return None
    if range_ratio > MAX_SIGNAL_RANGE_TO_PRIOR_RANGE:
        return None
    if signal_high_vs_prior > MAX_SIGNAL_HIGH_VS_PRIOR_HIGH:
        return None
    if signal_low_vs_prior < MIN_SIGNAL_LOW_VS_PRIOR_LOW:
        return None
    if signal_close_location < MIN_SIGNAL_CLOSE_LOCATION:
        return None
    if (
        signal_volume_ratio < MIN_SIGNAL_VOLUME_RATIO_20D
        or signal_volume_ratio > MAX_SIGNAL_VOLUME_RATIO_20D
    ):
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if ret20 > MAX_RET20:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None

    sector_meta = sector_entries[ticker]
    dry_up = 1.0 - signal_volume_ratio
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        1.35 * prior_return
        + 0.85 * max(signal_close_vs_prior, 0.0)
        + 0.45 * signal_close_location
        + 0.70 * ret20_excess_spy
        + 0.30 * ret60_excess_spy
        + 0.20 * max(dry_up, -0.25)
        + 0.04 * liquidity_score
        - 0.35 * max(ret5, 0.0)
        - 0.55 * realized_vol20
        - 0.15 * range_ratio
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "POST_THRUST_INSIDE_DAY_ABSORPTION_PAPER",
        "candidate_score": round(score, 6),
        "candidate_prior_thrust_return": round(prior_return, 6),
        "candidate_prior_close_location": round(prior_close_location, 6),
        "candidate_prior_volume_ratio_20d": round(prior_volume_ratio, 6),
        "candidate_prior_range_pct": round(prior_range, 6),
        "candidate_signal_range_pct": round(signal_range, 6),
        "candidate_signal_range_to_prior_range": round(range_ratio, 6),
        "candidate_signal_close_vs_prior_close": round(signal_close_vs_prior, 6),
        "candidate_signal_high_vs_prior_high": round(signal_high_vs_prior, 6),
        "candidate_signal_low_vs_prior_low": round(signal_low_vs_prior, 6),
        "candidate_signal_close_location": round(signal_close_location, 6),
        "candidate_signal_volume_ratio_20d": round(signal_volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
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
        "days_with_raw_post_thrust_inside_day_candidates": 0,
        "raw_post_thrust_inside_day_candidates": 0,
    }
    for signal_date in dates:
        day_rows: list[dict[str, Any]] = []
        ab_entries = entries_by_date.get(signal_date, [])
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
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            if row["same_ticker_ab_overlap"]:
                continue
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_prior_thrust_return"]),
                -float(row["candidate_ret20_excess_spy"]),
                float(row["candidate_signal_range_to_prior_range"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_post_thrust_inside_day_candidates"] += 1
        scan["raw_post_thrust_inside_day_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_prior_thrust_return": top[
                    "candidate_prior_thrust_return"
                ],
                "top_candidate_signal_range_to_prior_range": top[
                    "candidate_signal_range_to_prior_range"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_prior_thrust_return"]),
            -float(row["candidate_ret20_excess_spy"]),
            float(row["candidate_signal_range_to_prior_range"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_prior_thrust_return": MIN_PRIOR_THRUST_RETURN,
            "max_prior_thrust_return": MAX_PRIOR_THRUST_RETURN,
            "min_prior_close_location": MIN_PRIOR_CLOSE_LOCATION,
            "min_prior_volume_ratio_20d": MIN_PRIOR_VOLUME_RATIO_20D,
            "max_prior_volume_ratio_20d": MAX_PRIOR_VOLUME_RATIO_20D,
            "min_signal_close_vs_prior_close": MIN_SIGNAL_CLOSE_VS_PRIOR_CLOSE,
            "max_signal_close_vs_prior_close": MAX_SIGNAL_CLOSE_VS_PRIOR_CLOSE,
            "max_signal_range_pct": MAX_SIGNAL_RANGE_PCT,
            "max_signal_range_to_prior_range": MAX_SIGNAL_RANGE_TO_PRIOR_RANGE,
            "max_signal_high_vs_prior_high": MAX_SIGNAL_HIGH_VS_PRIOR_HIGH,
            "min_signal_low_vs_prior_low": MIN_SIGNAL_LOW_VS_PRIOR_LOW,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_volume_ratio_20d": MIN_SIGNAL_VOLUME_RATIO_20D,
            "max_signal_volume_ratio_20d": MAX_SIGNAL_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_ret20": MAX_RET20,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
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
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_post_thrust_inside_day_absorption"
        if gate["passed"]
        else "rejected_post_thrust_inside_day_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "A high-volume upside thrust followed by a tight inside/pause "
                "day near the prior high with volume dry-up may mark "
                "institutional absorption and add a cleaner free-OHLCV "
                "candidate source than raw gap or same-day compression chases."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_ohlcv_post_thrust_inside_day_absorption"
            ),
            "nearby_prior_experiments": [
                "exp-20260426-057",
                "exp-20260608-013",
                "exp-20260608-017",
                "exp-20260609-002",
                "exp-20260609-003",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate_high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that the inside/pause day "
                "after a thrust either arrives too late in stale momentum or "
                "does not add replacement value beyond accepted compression. "
                "Do not answer by sweeping prior-return, range, volume, "
                "hold-day, cooldown, or notional thresholds on these frozen "
                "windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence such as forward "
                "order-flow/catalyst provenance, a relation layer, or live "
                "replacement-value rows. Pure two-day OHLCV threshold retunes "
                "should stay frozen."
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
            "min_prior_thrust_return": MIN_PRIOR_THRUST_RETURN,
            "max_prior_thrust_return": MAX_PRIOR_THRUST_RETURN,
            "min_prior_close_location": MIN_PRIOR_CLOSE_LOCATION,
            "min_prior_volume_ratio_20d": MIN_PRIOR_VOLUME_RATIO_20D,
            "max_prior_volume_ratio_20d": MAX_PRIOR_VOLUME_RATIO_20D,
            "min_signal_close_vs_prior_close": MIN_SIGNAL_CLOSE_VS_PRIOR_CLOSE,
            "max_signal_close_vs_prior_close": MAX_SIGNAL_CLOSE_VS_PRIOR_CLOSE,
            "max_signal_range_pct": MAX_SIGNAL_RANGE_PCT,
            "max_signal_range_to_prior_range": MAX_SIGNAL_RANGE_TO_PRIOR_RANGE,
            "max_signal_high_vs_prior_high": MAX_SIGNAL_HIGH_VS_PRIOR_HIGH,
            "min_signal_low_vs_prior_low": MIN_SIGNAL_LOW_VS_PRIOR_LOW,
            "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
            "min_signal_volume_ratio_20d": MIN_SIGNAL_VOLUME_RATIO_20D,
            "max_signal_volume_ratio_20d": MAX_SIGNAL_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_ret20": MAX_RET20,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: a high-volume upside thrust followed by a "
            "tight, non-chasing inside/pause day with volume dry-up may reveal "
            "absorption before continuation."
        ),
        "2_history_check": {
            "exp-20260426-057": (
                "Older inside-day compression was an earlier lead, not current "
                "Gate 1-4 evidence for this post-thrust pause morphology."
            ),
            "exp-20260608-013": (
                "Accepted narrow-range compression is the comparator; this run "
                "must beat its +0.1608 EV and +$2,248.98 PnL replacement value."
            ),
            "exp-20260608-017": (
                "Quiet tight-range accumulation failed aggregate EV/PnL, but "
                "did not require a prior high-volume thrust day."
            ),
            "exp-20260609-002/003": (
                "Gap-and-hold variants had positive but non-robust replacement "
                "value; this avoids gap-chase fields and tests a two-day "
                "thrust-then-dry-up shape."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL beat baseline and the accepted compression "
            "comparator, no EV/PnL regression window, target sample >=20 across "
            "all 3 windows, survival >=5%, drawdown drift <=0.5pp, and "
            "concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_004_post_thrust_inside_day_absorption.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The post-thrust inside-day absorption candidate source cleared Gate 4 "
        "as a replay-only/default-off lead, but no production surface was "
        "promoted. A shared parity adapter is required before use."
        if payload["gate4"]["passed"]
        else (
            "The post-thrust inside-day absorption candidate source did not "
            "clear Gate 4; do not promote or locally retune this two-day OHLCV "
            "family on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The two-day absorption shape produced a large enough sample but "
            "lost replacement value in late_strong and old_thin, while "
            "mid_weak was the only improving window. That pattern indicates "
            "the prior-thrust pause mostly relabeled stale OHLCV momentum and "
            "added drawdown rather than isolating durable institutional "
            "absorption after next-open execution costs."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "target trades {}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping prior-thrust return, prior close "
            "location, signal range, inside-day high/low tolerance, volume "
            "dry-up, ret5/ret20, top-N, hold-day, cooldown, or paper-notional "
            "thresholds on these frozen windows."
        ),
        "new_evidence_required": (
            "Need materially new PIT evidence such as catalyst/order-flow "
            "provenance, relation data, or closed forward replacement-value "
            "rows before revisiting post-thrust inside-day continuation."
        ),
    }
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Absorption days | Trades |",
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
                days=scan.get("days_with_raw_post_thrust_inside_day_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Thrust Inside-Day Absorption",
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
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
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
                "absorption_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_post_thrust_inside_day_candidates"
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


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
