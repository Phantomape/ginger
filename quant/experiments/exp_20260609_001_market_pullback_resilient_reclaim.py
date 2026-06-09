"""exp-20260609-001: market-pullback resilient reclaim candidates.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: after SPY has just pulled back, liquid
sector-known stocks that stayed resilient and reclaimed a short prior high
become top-1 next-open default-off paper candidates with a fixed
10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_015_low_vol_20d_high_breakout_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-001"
STEM = "market_pullback_resilient_reclaim"
TRIAL_FAMILY = "market_pullback_resilient_reclaim_candidate_pool"
TRIAL_VARIANT_ID = "market_pullback_resilient_reclaim_top1_next_open_10d_v1"
CHANGED_VARIABLE = "market_pullback_resilient_reclaim_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_001_{STEM}.json"
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
PRIOR_HIGH_LOOKBACK_DAYS = 10

MAX_SPY_RET3 = -0.012
MAX_SPY_RET5 = -0.018
MIN_SPY_RET20 = -0.12
MAX_SPY_SIGNAL_RETURN = 0.012

MIN_CANDIDATE_SIGNAL_RETURN = -0.002
MIN_CANDIDATE_CLOSE_LOCATION = 0.66
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.80
MIN_CANDIDATE_RET3_EXCESS_SPY = 0.025
MIN_CANDIDATE_RET5_EXCESS_SPY = 0.030
MIN_CANDIDATE_RET20_EXCESS_SPY = 0.015
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.020
MIN_CANDIDATE_RECLAIM_VS_10D_HIGH = -0.004
MAX_CANDIDATE_RECLAIM_VS_10D_HIGH = 0.055
MIN_CANDIDATE_RET5 = -0.030
MAX_CANDIDATE_RET5 = 0.115
MAX_CANDIDATE_RET20 = 0.300
MAX_CANDIDATE_REALIZED_VOL_20D = 0.085

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
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_regression",
        "drawdown_drift",
        "ohlcv_momentum_relabeling",
        "accepted_compression_comparator_not_beaten",
        "target_sample_too_small",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Playbook favors production-visible default-off candidate-pool alpha, "
        "but broad momentum and stress-resilience neighbors failed. This tests "
        "a fixed tail-state entry where SPY pullback creates dispersion and "
        "only liquid stocks with relative resilience plus reclaim are selected."
    ),
    "recorded_at": "2026-06-09T01:03:47+00:00",
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
        "same SPY pullback state, liquid sector-known stock universe, "
        "relative-resilience fields, prior-high reclaim field, same-ticker "
        "core-overlap exclusion, next-open paper entry, 10-trading-day exit, "
        "costs, cooldown, comparator, and concentration controls in both "
        "historical replay and daily production."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _prior_high(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    highs = [framework._value(row, "High") for row in rows[idx - lookback : idx]]
    if any(value is None for value in highs):
        return None
    valid = [float(value) for value in highs if value is not None]
    return max(valid) if valid else None


def _spy_pullback_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if spy_idx is None or spy_idx < 60:
        return None
    spy_ret3 = framework._ret(spy_rows, spy_idx, 3)
    spy_ret5 = framework._ret(spy_rows, spy_idx, 5)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    spy_close_location = framework._close_location(spy_rows[spy_idx])
    if any(
        value is None
        for value in [
            spy_ret3,
            spy_ret5,
            spy_ret20,
            spy_ret60,
            spy_signal_return,
            spy_close_location,
        ]
    ):
        return None
    assert spy_ret3 is not None
    assert spy_ret5 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert spy_signal_return is not None
    assert spy_close_location is not None
    if spy_ret3 > MAX_SPY_RET3:
        return None
    if spy_ret5 > MAX_SPY_RET5:
        return None
    if spy_ret20 < MIN_SPY_RET20:
        return None
    if spy_signal_return > MAX_SPY_SIGNAL_RETURN:
        return None
    return {
        "spy_ret3": round(spy_ret3, 6),
        "spy_ret5": round(spy_ret5, 6),
        "spy_ret20": round(spy_ret20, 6),
        "spy_ret60": round(spy_ret60, 6),
        "spy_signal_day_return": round(spy_signal_return, 6),
        "spy_close_location": round(spy_close_location, 6),
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    spy_context: dict[str, Any],
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

    prior_high = _prior_high(rows, idx, PRIOR_HIGH_LOOKBACK_DAYS)
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret3 = framework._ret(rows, idx, 3)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret3 = framework._ret(spy_rows, spy_idx, 3)
    spy_ret5 = framework._ret(spy_rows, spy_idx, 5)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        prior_high,
        signal_return,
        close_location,
        volume_ratio,
        ret3,
        ret5,
        ret20,
        ret60,
        spy_ret3,
        spy_ret5,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert prior_high is not None
    assert signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret3 is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret3 is not None
    assert spy_ret5 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    if prior_high <= 0:
        return None

    reclaim_vs_10d_high = close / prior_high - 1.0
    ret3_excess_spy = ret3 - spy_ret3
    ret5_excess_spy = ret5 - spy_ret5
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60

    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if ret3_excess_spy < MIN_CANDIDATE_RET3_EXCESS_SPY:
        return None
    if ret5_excess_spy < MIN_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if reclaim_vs_10d_high < MIN_CANDIDATE_RECLAIM_VS_10D_HIGH:
        return None
    if reclaim_vs_10d_high > MAX_CANDIDATE_RECLAIM_VS_10D_HIGH:
        return None
    if ret5 < MIN_CANDIDATE_RET5 or ret5 > MAX_CANDIDATE_RET5:
        return None
    if ret20 > MAX_CANDIDATE_RET20:
        return None
    if realized_vol20 > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None

    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        1.60 * ret5_excess_spy
        + 1.10 * ret20_excess_spy
        + 0.60 * ret3_excess_spy
        + 0.35 * close_location
        + 0.20 * max(reclaim_vs_10d_high, 0.0)
        + 0.10 * min(volume_ratio, 3.0)
        + 0.04 * liquidity_score
        - 0.35 * max(ret5, 0.0)
        - 0.80 * realized_vol20
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "MARKET_PULLBACK_RESILIENT_RECLAIM_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_prior_10d_high": round(prior_high, 4),
        "candidate_reclaim_vs_10d_high": round(reclaim_vs_10d_high, 6),
        "candidate_ret3": round(ret3, 6),
        "candidate_ret3_excess_spy": round(ret3_excess_spy, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret5_excess_spy": round(ret5_excess_spy, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "spy_pullback_context": spy_context,
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
        "days_with_spy_pullback_context": 0,
        "days_with_raw_resilient_reclaim_candidates": 0,
        "raw_resilient_reclaim_candidates": 0,
    }
    for signal_date in dates:
        spy_context = _spy_pullback_context(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if spy_context is None:
            continue
        scan["days_with_spy_pullback_context"] += 1
        day_rows: list[dict[str, Any]] = []
        ab_entries = entries_by_date.get(signal_date, [])
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                spy_context=spy_context,
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
                -float(row["candidate_ret5_excess_spy"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_reclaim_vs_10d_high"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_resilient_reclaim_candidates"] += 1
        scan["raw_resilient_reclaim_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_ret5_excess_spy": day_rows[0][
                    "candidate_ret5_excess_spy"
                ],
                "top_candidate_ret20_excess_spy": day_rows[0][
                    "candidate_ret20_excess_spy"
                ],
                "top_candidate_reclaim_vs_10d_high": day_rows[0][
                    "candidate_reclaim_vs_10d_high"
                ],
                "spy_context": spy_context,
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret5_excess_spy"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_reclaim_vs_10d_high"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "max_spy_ret3": MAX_SPY_RET3,
            "max_spy_ret5": MAX_SPY_RET5,
            "min_spy_ret20": MIN_SPY_RET20,
            "max_spy_signal_return": MAX_SPY_SIGNAL_RETURN,
            "prior_high_lookback_days": PRIOR_HIGH_LOOKBACK_DAYS,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "min_candidate_ret3_excess_spy": MIN_CANDIDATE_RET3_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_reclaim_vs_10d_high": MIN_CANDIDATE_RECLAIM_VS_10D_HIGH,
            "max_candidate_reclaim_vs_10d_high": MAX_CANDIDATE_RECLAIM_VS_10D_HIGH,
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "max_candidate_ret20": MAX_CANDIDATE_RET20,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
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
        "positive_replay_lead_not_promoted_market_pullback_resilient_reclaim"
        if gate["passed"]
        else "rejected_market_pullback_resilient_reclaim_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Market-pullback resilient relative-strength stocks may expand "
                "the default-off candidate pool when SPY has just sold off but "
                "the stock reclaims a prior 10-day high with high close-location "
                "and bounded extension."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_tail_state_reclaim_field",
            "nearby_prior_experiments": [
                "exp-20260426-062",
                "exp-20260606-014",
                "exp-20260606-027",
                "exp-20260607-023",
                "exp-20260608-016",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate_high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that market-pullback "
                "resilience is still an OHLCV momentum relabeling or selects "
                "fragile stress rebounds that fail old_thin/drawdown/comparator "
                "guards. Do not answer by sweeping SPY pullback, reclaim, "
                "ret5/ret20 excess, volume, close-location, hold-day, cooldown, "
                "or paper notional thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT tail-state or flow/catalyst "
                "evidence, a different production-visible relation, or closed "
                "forward replacement-value rows. Pure OHLCV threshold retunes "
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
            "max_spy_ret3": MAX_SPY_RET3,
            "max_spy_ret5": MAX_SPY_RET5,
            "min_spy_ret20": MIN_SPY_RET20,
            "max_spy_signal_return": MAX_SPY_SIGNAL_RETURN,
            "prior_high_lookback_days": PRIOR_HIGH_LOOKBACK_DAYS,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "min_candidate_ret3_excess_spy": MIN_CANDIDATE_RET3_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_reclaim_vs_10d_high": MIN_CANDIDATE_RECLAIM_VS_10D_HIGH,
            "max_candidate_reclaim_vs_10d_high": MAX_CANDIDATE_RECLAIM_VS_10D_HIGH,
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "max_candidate_ret20": MAX_CANDIDATE_RET20,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: during short SPY pullbacks, stocks that "
            "hold relative strength and reclaim a prior high may represent "
            "institutional demand rather than noisy broad momentum."
        ),
        "2_history_check": {
            "exp-20260426-062": (
                "Older market-pullback resilience shadow work was observed-only; "
                "it did not provide a current Gate 1-4 production-visible "
                "candidate-pool verdict."
            ),
            "exp-20260606-014": (
                "Broad 5-day winner continuation stayed positive in aggregate "
                "but failed old_thin, drawdown, and accepted ETF comparator."
            ),
            "exp-20260606-027": (
                "Official macro-stress resilient stock leadership failed; the "
                "new test does not use official event labels and requires "
                "ticker-level reclaim after broad pullback."
            ),
            "exp-20260607-023": (
                "VIXY stress resilient stock leadership failed; this test uses "
                "SPY short-horizon pullback and relative reclaim rather than "
                "volatility-product stress labels."
            ),
            "exp-20260608-016": (
                "Accumulation-base breakout had positive aggregate but failed "
                "old_thin and drawdown, so this run adds an explicit market "
                "pullback tail-state rather than retuning accumulation."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the result beats the "
            "accepted exp-20260608-013 compression-breakout comparator."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_001_market_pullback_resilient_reclaim.py"
        ),
        "gate2_field_reality": (
            "Rule fields are signal-date OHLCV, SPY OHLCV, public sector map, "
            "and same-day core A/B overlap metadata. operator_inputs minimum "
            "fields were checked separately: 15 position rows, 0 missing "
            "entry_date, 0 missing target_price. The rule does not consume "
            "held-position entry_date or target_price."
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if payload["gate4"]["passed"] else "rejected"
    )
    payload["interpretation"] = (
        "The market-pullback resilient reclaim source cleared strict Gate 4 "
        "and beat the accepted compression comparator, but remains replay-only "
        "until a shared default-off adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The market-pullback resilient reclaim source did not clear Gate 4 "
            "or did not beat the accepted compression comparator; do not "
            "promote or locally retune this OHLCV tail-state family on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Market-pullback resilience can still be generic momentum under "
            "stress. If it fails a window or comparator, the source did not "
            "separate durable institutional demand from fragile rebound beta."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SPY pullback windows, reclaim distance, "
            "ret3/ret5/ret20 excess, close-location, volume, top-N, hold-day, "
            "cooldown, or paper notional thresholds on these frozen windows."
        ),
        "new_evidence_required": (
            "Need a materially new PIT tail-state/flow/catalyst field or "
            "forward replacement-value rows before revisiting."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Pullback days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {pullbacks} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                pullbacks=scan.get("days_with_spy_pullback_context", 0),
                days=scan.get("days_with_raw_resilient_reclaim_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_compression_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Market-Pullback Resilient Reclaim",
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
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                comparator["expected_value_score_delta_sum"],
                comparator["total_pnl_delta_sum"],
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
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
                "spy_pullback_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_spy_pullback_context"
                ),
                "resilient_reclaim_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_raw_resilient_reclaim_candidates"),
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
