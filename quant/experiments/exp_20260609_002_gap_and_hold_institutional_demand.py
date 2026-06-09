"""exp-20260609-002: gap-and-hold institutional-demand candidates.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: liquid sector-known stocks that gap up at the open,
hold the gap through the signal-day session, close near the high with volume,
and avoid recent overextension become top-1 next-open default-off paper
candidates with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_015_low_vol_20d_high_breakout_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-002"
STEM = "gap_and_hold_institutional_demand"
TRIAL_FAMILY = "gap_and_hold_institutional_demand_candidate_pool"
TRIAL_VARIANT_ID = "gap_and_hold_top1_next_open_10d_v1"
CHANGED_VARIABLE = "gap_and_hold_institutional_demand_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_002_{STEM}.json"
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
MIN_GAP_PCT = 0.022
MAX_GAP_PCT = 0.090
MIN_LOW_VS_PRIOR_CLOSE = -0.002
MIN_CLOSE_VS_OPEN = -0.001
MIN_SIGNAL_RETURN = 0.012
MAX_SIGNAL_RETURN = 0.115
MIN_CLOSE_LOCATION = 0.68
MIN_VOLUME_RATIO_20D = 1.15
MAX_VOLUME_RATIO_20D = 5.00
MIN_RET20_EXCESS_SPY = -0.020
MIN_RET60_EXCESS_SPY = -0.040
MIN_RET5 = -0.025
MAX_RET5 = 0.120
MAX_RET20 = 0.320
MAX_REALIZED_VOL_20D = 0.090

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
    "ARKK",
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GBTC",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "JNK",
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
        "old_thin_regression",
        "drawdown_drift",
        "ohlcv_momentum_relabeling",
        "accepted_compression_comparator_not_beaten",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Playbook favors production-visible default-off candidate-pool alpha, "
        "but broad OHLCV neighbors are crowded and often fail old_thin/drawdown. "
        "Gap-and-hold is a distinct event-absorption morphology using free "
        "decision-time OHLCV; likely failure is momentum relabeling."
    ),
    "recorded_at": "2026-06-09T02:04:44+00:00",
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
        "same signal-day gap, gap-hold, close-location, volume, liquidity, "
        "SPY-relative trend, same-ticker core-overlap exclusion, next-open "
        "paper entry, 10-trading-day exit, costs, cooldown, comparator, and "
        "concentration controls in both historical replay and daily production."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _gap_pct(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    open_price = framework._value(rows[idx], "Open")
    prior_close = framework._value(rows[idx - 1], "Close")
    if open_price is None or prior_close is None or prior_close <= 0:
        return None
    return open_price / prior_close - 1.0


def _low_vs_prior_close(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    low = framework._value(rows[idx], "Low")
    prior_close = framework._value(rows[idx - 1], "Close")
    if low is None or prior_close is None or prior_close <= 0:
        return None
    return low / prior_close - 1.0


def _close_vs_open(rows: list[dict[str, Any]], idx: int) -> float | None:
    open_price = framework._value(rows[idx], "Open")
    close = framework._value(rows[idx], "Close")
    if open_price is None or close is None or open_price <= 0:
        return None
    return close / open_price - 1.0


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
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    gap = _gap_pct(rows, idx)
    low_hold = _low_vs_prior_close(rows, idx)
    close_open = _close_vs_open(rows, idx)
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
        gap,
        low_hold,
        close_open,
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
    assert gap is not None
    assert low_hold is not None
    assert close_open is not None
    assert signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None

    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if gap < MIN_GAP_PCT or gap > MAX_GAP_PCT:
        return None
    if low_hold < MIN_LOW_VS_PRIOR_CLOSE:
        return None
    if close_open < MIN_CLOSE_VS_OPEN:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
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
    score = (
        1.80 * gap
        + 1.25 * signal_return
        + 0.80 * max(low_hold, 0.0)
        + 0.85 * max(close_open, 0.0)
        + 0.40 * close_location
        + 0.70 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.10 * min(volume_ratio, 3.5)
        + 0.04 * liquidity_score
        - 0.30 * max(ret5, 0.0)
        - 0.60 * realized_vol20
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "GAP_AND_HOLD_INSTITUTIONAL_DEMAND_PAPER",
        "candidate_score": round(score, 6),
        "candidate_gap_pct": round(gap, 6),
        "candidate_low_vs_prior_close_pct": round(low_hold, 6),
        "candidate_close_vs_open_pct": round(close_open, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
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
        "days_with_raw_gap_hold_candidates": 0,
        "raw_gap_hold_candidates": 0,
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
                -float(row["candidate_gap_pct"]),
                -float(row["candidate_close_vs_open_pct"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_gap_hold_candidates"] += 1
        scan["raw_gap_hold_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_gap_pct": top["candidate_gap_pct"],
                "top_candidate_low_vs_prior_close_pct": top[
                    "candidate_low_vs_prior_close_pct"
                ],
                "top_candidate_close_vs_open_pct": top["candidate_close_vs_open_pct"],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_gap_pct"]),
            -float(row["candidate_close_vs_open_pct"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_gap_pct": MIN_GAP_PCT,
            "max_gap_pct": MAX_GAP_PCT,
            "min_low_vs_prior_close": MIN_LOW_VS_PRIOR_CLOSE,
            "min_close_vs_open": MIN_CLOSE_VS_OPEN,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
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
        "positive_replay_lead_not_promoted_gap_and_hold_institutional_demand"
        if gate["passed"]
        else "rejected_gap_and_hold_institutional_demand_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Gap-and-hold liquid stock breakouts may identify institutional "
                "demand continuation candidates after signal-day event absorption "
                "without adding noisy tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_gap_hold_absorption_field",
            "nearby_prior_experiments": [
                "exp-20260426-044",
                "exp-20260606-003",
                "exp-20260606-004",
                "exp-20260606-010",
                "exp-20260606-015",
                "exp-20260608-012",
                "exp-20260609-001",
            ],
            "prior_trial_count": 7,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that gap-and-hold still "
                "relabels broad OHLCV momentum or event-day crowding rather than "
                "durable institutional demand. Do not answer by sweeping gap, "
                "hold, close-location, volume, ret5/ret20, top-N, hold-day, "
                "cooldown, or paper notional thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT event/flow provenance, a "
                "shared daily adapter that can collect forward replacement-value "
                "rows, or a different relation surface. Pure gap-and-hold "
                "threshold retunes should stay frozen."
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
            "min_gap_pct": MIN_GAP_PCT,
            "max_gap_pct": MAX_GAP_PCT,
            "min_low_vs_prior_close": MIN_LOW_VS_PRIOR_CLOSE,
            "min_close_vs_open": MIN_CLOSE_VS_OPEN,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
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
            "entry/candidate_pool: a positive signal-day gap that holds through "
            "the session with volume and a high close can represent event "
            "absorption and institutional demand, not just ticker noise."
        ),
        "2_history_check": {
            "exp-20260426-044": (
                "Older gap-and-hold continuation was shadow/observed-only, not "
                "current docs/backtesting.md three-window Gate 1-4 evidence."
            ),
            "exp-20260606-003/004": (
                "Broad 5-day winner and raw cross-sectional alpha-score pools "
                "failed robustness; this test uses a signal-day gap-hold event "
                "morphology rather than raw recent winners."
            ),
            "exp-20260606-010": (
                "Gap-down recovery improved aggregate but failed windows and "
                "drawdown; this is the opposite demand-continuation morphology."
            ),
            "exp-20260606-015": (
                "Low-vol 20d high breakout failed old_thin/drawdown, so this "
                "run must not be accepted unless it beats robust window and "
                "comparator gates."
            ),
            "exp-20260608-012/013": (
                "Narrow-range compression is the accepted broad OHLCV comparator "
                "(+0.1608 EV, +$2,248.98, 44 trades). This run must beat it."
            ),
            "exp-20260609-001": (
                "Pullback reclaim failed old_thin and compression comparator; "
                "this run is not a pullback-tail-state retry."
            ),
        },
        "3_single_policy_bundle": (
            "Only one decision hypothesis is tested: fixed gap-and-hold "
            "institutional-demand candidate selection with next-open paper "
            "entry and 10-trading-day close exit."
        ),
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the accepted "
            "exp-20260608-013 compression-breakout comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_002_gap_and_hold_institutional_demand.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if payload["gate4"]["passed"] else "rejected"
    )
    payload["interpretation"] = (
        "The gap-and-hold institutional-demand source cleared strict Gate 4 "
        "and beat the accepted compression comparator, but remains replay-only "
        "until a shared default-off adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The gap-and-hold institutional-demand source did not clear Gate 4 "
            "or did not beat the accepted compression comparator; do not "
            "promote or locally retune this OHLCV gap-hold family on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Gap-and-hold may still be an event-day momentum/crowding label. "
            "If it fails any canonical window or accepted compression "
            "comparator, the rule did not isolate durable institutional demand "
            "after next-open execution costs."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping gap, low-vs-prior-close hold, "
            "close-vs-open, close-location, volume, ret5/ret20, top-N, "
            "hold-day, cooldown, or paper-notional thresholds on these frozen "
            "windows."
        ),
        "new_evidence_required": (
            "Need materially new PIT event/flow/catalyst provenance or forward "
            "replacement-value rows before revisiting gap-hold continuation."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Gap-hold days | Trades |",
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
                days=scan.get("days_with_raw_gap_hold_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_compression_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Gap-And-Hold Institutional Demand",
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
                "gap_hold_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_raw_gap_hold_candidates"
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
