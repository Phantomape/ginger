"""exp-20260609-008: low-turnover RS consolidation candidate pool.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: liquid sector-known stocks with persistent
SPY-relative strength that pause on controlled range and unusually low
turnover become top-1 next-open default-off paper candidates with a fixed
10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import exp_20260608_016_accumulation_base_breakout as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-008"
STEM = "low_turnover_rs_consolidation"
TRIAL_FAMILY = "low_turnover_rs_consolidation_candidate_pool"
TRIAL_VARIANT_ID = "low_turnover_rs_consolidation_top1_next_open_10d_v1"
CHANGED_VARIABLE = "low_turnover_rs_consolidation_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_008_{STEM}.json"
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
MIN_AVG_DOLLAR_VOLUME_20D = 75_000_000.0
PRIOR_HIGH_LOOKBACK_DAYS = 20
RANGE_LOOKBACK_DAYS = 20
REFERENCE_RANGE_LOOKBACK_DAYS = 60
MIN_SIGNAL_RANGE_PCT = 0.004
MAX_SIGNAL_RANGE_PCT = 0.035
MAX_SIGNAL_RANGE_TO_MEDIAN20_RATIO = 0.95
MAX_SIGNAL_RANGE_TO_MEDIAN60_RATIO = 0.90
MIN_SIGNAL_RETURN = -0.012
MAX_SIGNAL_RETURN = 0.018
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.35
MAX_VOLUME_RATIO_20D = 0.90
MIN_DISTANCE_TO_20D_HIGH = -0.120
MAX_DISTANCE_TO_20D_HIGH = 0.020
MIN_RET20_EXCESS_SPY = 0.035
MIN_RET60_EXCESS_SPY = 0.020
MIN_RET5 = -0.040
MAX_RET5 = 0.050
MAX_RET20 = 0.280
MAX_REALIZED_VOL_20D = 0.075

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

EXCLUDED_TICKERS = previous.EXCLUDED_TICKERS

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "quiet_consolidation_near_neighbor",
        "stale_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_compression_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The free-OHLCV candidate-pool lane has one small accepted compression "
        "source, but accumulation and quiet high-volume variants recently "
        "failed; this tests the opposite low-turnover holding-pressure "
        "morphology with strict comparator gates."
    ),
    "recorded_at": "2026-06-09T07:17:33+00:00",
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
        "sector-known liquid stock universe, signal-day controlled-range "
        "field, low-turnover field, SPY-relative trend guards, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, accepted compression comparator, "
        "and concentration controls in both historical replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
    "target_trade_count": 44,
}


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
    valid = [float(value) for value in highs if value is not None]
    return max(valid) if valid else None


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
    if idx < REFERENCE_RANGE_LOOKBACK_DAYS or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    signal_range_pct = _range_pct(rows[idx])
    median_range20_pct = _median_range_pct(rows, idx, RANGE_LOOKBACK_DAYS)
    median_range60_pct = _median_range_pct(rows, idx, REFERENCE_RANGE_LOOKBACK_DAYS)
    prior_high = _prior_high(rows, idx, PRIOR_HIGH_LOOKBACK_DAYS)
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
        median_range20_pct,
        median_range60_pct,
        prior_high,
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
    assert median_range20_pct is not None
    assert median_range60_pct is not None
    assert prior_high is not None
    assert signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    if prior_high <= 0 or median_range20_pct <= 0 or median_range60_pct <= 0:
        return None

    range_to_median20 = signal_range_pct / median_range20_pct
    range_to_median60 = signal_range_pct / median_range60_pct
    distance_to_high = close / prior_high - 1.0
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_range_pct < MIN_SIGNAL_RANGE_PCT:
        return None
    if signal_range_pct > MAX_SIGNAL_RANGE_PCT:
        return None
    if range_to_median20 > MAX_SIGNAL_RANGE_TO_MEDIAN20_RATIO:
        return None
    if range_to_median60 > MAX_SIGNAL_RANGE_TO_MEDIAN60_RATIO:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    if volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    if distance_to_high < MIN_DISTANCE_TO_20D_HIGH:
        return None
    if distance_to_high > MAX_DISTANCE_TO_20D_HIGH:
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
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    controlled_range_score = max(0.0, 1.0 - range_to_median20)
    volume_dryup_score = max(
        0.0,
        (MAX_VOLUME_RATIO_20D - volume_ratio)
        / max(MAX_VOLUME_RATIO_20D - MIN_VOLUME_RATIO_20D, 0.001),
    )
    near_high_score = 1.0 - min(abs(distance_to_high), 0.060) / 0.060
    score = (
        0.65 * volume_dryup_score
        + 0.45 * controlled_range_score
        + 0.34 * close_location
        + 1.35 * ret20_excess_spy
        + 0.65 * ret60_excess_spy
        + 0.25 * near_high_score
        + 0.04 * liquidity_score
        - 0.45 * abs(signal_return)
        - 0.35 * max(ret5, 0.0)
        - 0.70 * realized_vol20
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "LOW_TURNOVER_RS_CONSOLIDATION_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_range_pct": round(signal_range_pct, 6),
        "candidate_median_range20_pct": round(median_range20_pct, 6),
        "candidate_median_range60_pct": round(median_range60_pct, 6),
        "candidate_range_to_median20": round(range_to_median20, 6),
        "candidate_range_to_median60": round(range_to_median60, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_controlled_range_score": round(controlled_range_score, 6),
        "candidate_volume_dryup_score": round(volume_dryup_score, 6),
        "candidate_prior_high_20d": round(prior_high, 6),
        "candidate_distance_to_20d_high": round(distance_to_high, 6),
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
        "days_with_raw_low_turnover_rs_candidates": 0,
        "raw_low_turnover_rs_candidates": 0,
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
                -float(row["candidate_volume_dryup_score"]),
                -float(row["candidate_controlled_range_score"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_low_turnover_rs_candidates"] += 1
        scan["raw_low_turnover_rs_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_volume_dryup_score": day_rows[0][
                    "candidate_volume_dryup_score"
                ],
                "top_candidate_controlled_range_score": day_rows[0][
                    "candidate_controlled_range_score"
                ],
                "top_candidate_range_to_median20": day_rows[0][
                    "candidate_range_to_median20"
                ],
                "top_candidate_distance_to_20d_high": day_rows[0][
                    "candidate_distance_to_20d_high"
                ],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_volume_dryup_score"]),
            -float(row["candidate_controlled_range_score"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "prior_high_lookback_days": PRIOR_HIGH_LOOKBACK_DAYS,
            "range_lookback_days": RANGE_LOOKBACK_DAYS,
            "reference_range_lookback_days": REFERENCE_RANGE_LOOKBACK_DAYS,
            "min_signal_range_pct": MIN_SIGNAL_RANGE_PCT,
            "max_signal_range_pct": MAX_SIGNAL_RANGE_PCT,
            "max_signal_range_to_median20_ratio": (
                MAX_SIGNAL_RANGE_TO_MEDIAN20_RATIO
            ),
            "max_signal_range_to_median60_ratio": (
                MAX_SIGNAL_RANGE_TO_MEDIAN60_RATIO
            ),
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "min_distance_to_20d_high": MIN_DISTANCE_TO_20D_HIGH,
            "max_distance_to_20d_high": MAX_DISTANCE_TO_20D_HIGH,
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
        "positive_replay_lead_not_promoted_low_turnover_rs_consolidation"
        if gate["passed"]
        else "rejected_low_turnover_rs_consolidation_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Liquid sector-known stocks with persistent SPY-relative "
                "strength that pause on unusually low turnover and controlled "
                "range may represent quiet institutional holding pressure, "
                "expanding the default-off candidate pool without adding "
                "noisy tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_ohlcv_low_turnover_rs_consolidation_field"
            ),
            "nearby_prior_experiments": [
                "exp-20260608-012",
                "exp-20260608-013",
                "exp-20260608-016",
                "exp-20260608-017",
                "exp-20260609-002",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that low turnover during "
                "relative-strength pauses is stale momentum or passive "
                "liquidity absence, not hidden demand. Do not answer by "
                "sweeping range, volume, distance-to-high, ret5/ret20, "
                "hold-day, cooldown, or notional thresholds on these frozen "
                "windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new evidence such as forward "
                "replacement-value rows, same-day production-visible catalyst "
                "provenance, or a PIT flow/ownership field. Pure low-turnover "
                "RS-consolidation threshold retunes should stay frozen."
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
            "prior_high_lookback_days": PRIOR_HIGH_LOOKBACK_DAYS,
            "range_lookback_days": RANGE_LOOKBACK_DAYS,
            "reference_range_lookback_days": REFERENCE_RANGE_LOOKBACK_DAYS,
            "min_signal_range_pct": MIN_SIGNAL_RANGE_PCT,
            "max_signal_range_pct": MAX_SIGNAL_RANGE_PCT,
            "max_signal_range_to_median20_ratio": (
                MAX_SIGNAL_RANGE_TO_MEDIAN20_RATIO
            ),
            "max_signal_range_to_median60_ratio": (
                MAX_SIGNAL_RANGE_TO_MEDIAN60_RATIO
            ),
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "min_distance_to_20d_high": MIN_DISTANCE_TO_20D_HIGH,
            "max_distance_to_20d_high": MAX_DISTANCE_TO_20D_HIGH,
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
            "entry/candidate_pool: persistent RS stocks that hold trend on "
            "low turnover and controlled range may reflect supply drying up "
            "before continuation; this expands the candidate pool through a "
            "free, production-visible OHLCV field rather than adding random "
            "tickers."
        ),
        "2_history_check": {
            "exp-20260608-012/013": (
                "Compression-to-expansion was accepted; this run is not an "
                "expansion threshold retune because signal-day volume must be "
                "below normal and the rule must beat the accepted comparator."
            ),
            "exp-20260608-016": (
                "Accumulation-base breakout was rejected because old_thin "
                "regressed and drawdown worsened; this run avoids elevated "
                "volume breakout chasing."
            ),
            "exp-20260608-017": (
                "Quiet tight-range accumulation with elevated volume failed. "
                "This run tests the opposite turnover state: supply dry-up "
                "rather than absorption volume."
            ),
            "exp-20260609-002": (
                "Gap-and-hold demand was rejected; this rule is not a gap or "
                "event-day demand continuation variant."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the accepted "
            "exp-20260608-013 compression comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_008_low_turnover_rs_consolidation.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed low-turnover RS consolidation source passed the "
            "canonical three-window Gate 4 and beat the accepted compression "
            "comparator, so the supply-dry-up field may be adding replacement "
            "value distinct from signal-day expansion. It remains replay-only "
            "until a shared daily helper proves parity and forward rows prove "
            "replacement value."
            if passed
            else (
                "The fixed low-turnover RS consolidation source failed Gate 4 "
                "or did not beat the accepted compression comparator. The "
                "likely mechanism is stale momentum: low turnover can mean "
                "absence of demand rather than hidden accumulation after "
                "next-open execution and cooldown."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping signal range, range-to-median ratio, "
            "low-volume bounds, close-location, distance-to-high, ret5/ret20, "
            "top-N, hold-day, cooldown, or paper notional thresholds on these "
            "frozen windows."
        ),
        "new_evidence_required": (
            "Next useful evidence is forward replacement-value rows, a shared "
            "default-off helper that reproduces this exact replay and daily "
            "snapshot semantics, or an orthogonal PIT catalyst/flow field. Live "
            "activation would need a separate activation-envelope Gate 1-4."
        ),
    }
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if passed else "rejected"
    payload["interpretation"] = (
        "The low-turnover RS consolidation source cleared Gate 4 and beat the "
        "accepted compression comparator as a replay-only/default-off lead, "
        "but no production surface was promoted. A shared parity adapter is "
        "required before use."
        if passed
        else (
            "The low-turnover RS consolidation source did not clear Gate 4 or "
            "did not beat the accepted compression comparator. Do not promote "
            "or locally retune this OHLCV low-turnover consolidation family "
            "on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
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
                days=scan.get("days_with_raw_low_turnover_rs_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Low-Turnover RS Consolidation Candidate Pool",
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
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
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
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
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
                "low_turnover_rs_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_raw_low_turnover_rs_candidates"),
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


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
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
        "owner": "alpha-search-automation",
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
