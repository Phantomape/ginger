"""exp-20260607-027: defensive sector rotation leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: when XLV, XLP, or XLU leads SPY and closes firm,
admit up to two liquid same-sector stock leaders that are already confirming
the rotation. This is intentionally not a laggard catch-up retest.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_029_sector_etf_lead_laggard_candidate_pool as base


EXPERIMENT_ID = "exp-20260607-027"
STEM = "defensive_sector_rotation_leadership"
TRIAL_FAMILY = "defensive_sector_rotation_leadership_candidate_pool"
TRIAL_VARIANT_ID = "defensive_sector_etf_stock_leadership_top2_next_open_10d_v1"
CHANGED_VARIABLE = "defensive_sector_rotation_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

framework = base.framework
REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_027_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 2
SAME_TICKER_COOLDOWN_DAYS = 10

DEFENSIVE_SECTOR_ETF_BY_SECTOR = {
    "Healthcare": "XLV",
    "Consumer Defensive": "XLP",
    "Utilities": "XLU",
}
DEFENSIVE_ETF_TICKERS = set(DEFENSIVE_SECTOR_ETF_BY_SECTOR.values())

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_ETF_SIGNAL_RETURN = 0.003
MIN_ETF_RELATIVE_VS_SPY = 0.004
MIN_ETF_CLOSE_LOCATION = 0.58
MIN_ETF_RET20_EXCESS_SPY = -0.015
MAX_SPY_SIGNAL_RETURN = 0.020
MIN_CANDIDATE_SIGNAL_RETURN = 0.004
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.006
MIN_CANDIDATE_RELATIVE_VS_ETF = 0.001
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.010
MIN_CANDIDATE_CLOSE_LOCATION = 0.65
MIN_CANDIDATE_VOLUME_RATIO = 0.90
MAX_CANDIDATE_RET5 = 0.120
MAX_CANDIDATE_REALIZED_VOL_20 = 0.080

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sector_etf_beta_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "defensive_rotation_too_sparse",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted macro and VIXY relief leadership show cross-asset state "
        "plus stock leadership can work, while sector ETF laggard and "
        "stress-resilience priors failed; this tests leaders in defensive "
        "rotation instead of laggards or broad stress."
    ),
    "recorded_at": "2026-06-07T23:05:31+00:00",
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
        "require a shared default-off adapter that computes the same XLV/XLP/"
        "XLU defensive-rotation context, same-sector stock leadership fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, top-N limit, and concentration "
        "controls in both replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = base.BASE_LOAD_WINDOW_SNAPSHOT
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | DEFENSIVE_ETF_TICKERS,
    )


def _defensive_contexts_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> list[dict[str, Any]]:
    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if spy_idx is None or spy_idx < 20:
        return []
    spy_return = framework._daily_return(spy_rows, spy_idx)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if spy_return is None or spy_ret20 is None:
        return []
    if spy_return > MAX_SPY_SIGNAL_RETURN:
        return []

    contexts: list[dict[str, Any]] = []
    for sector, etf in DEFENSIVE_SECTOR_ETF_BY_SECTOR.items():
        rows = snapshot.get(etf) or []
        idx = indices.get(etf, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        etf_return = framework._daily_return(rows, idx)
        etf_ret20 = framework._ret(rows, idx, 20)
        etf_close_location = framework._close_location(rows[idx])
        etf_volume_ratio = framework._volume_ratio(rows, idx) or 0.0
        if etf_return is None or etf_ret20 is None or etf_close_location is None:
            continue
        etf_relative_vs_spy = etf_return - spy_return
        etf_ret20_excess_spy = etf_ret20 - spy_ret20
        if etf_return < MIN_ETF_SIGNAL_RETURN:
            continue
        if etf_relative_vs_spy < MIN_ETF_RELATIVE_VS_SPY:
            continue
        if etf_close_location < MIN_ETF_CLOSE_LOCATION:
            continue
        if etf_ret20_excess_spy < MIN_ETF_RET20_EXCESS_SPY:
            continue
        contexts.append(
            {
                "date": signal_date,
                "sector": sector,
                "sector_etf_ticker": etf,
                "passed": True,
                "reason": "defensive_sector_rotation_passed",
                "sector_etf_signal_day_return": round(etf_return, 6),
                "spy_signal_day_return": round(spy_return, 6),
                "sector_etf_relative_vs_spy": round(etf_relative_vs_spy, 6),
                "sector_etf_ret20": round(etf_ret20, 6),
                "spy_ret20": round(spy_ret20, 6),
                "sector_etf_ret20_excess_spy": round(etf_ret20_excess_spy, 6),
                "sector_etf_close_location": round(etf_close_location, 6),
                "sector_etf_volume_ratio_20d": round(etf_volume_ratio, 6),
                "rule_version": RULE_VERSION,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
            }
        )
    return contexts


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in DEFENSIVE_ETF_TICKERS:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    if sector_meta.get("sector") != context["sector"]:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 20 or spy_idx < 20 or idx + HOLD_DAYS >= len(rows):
        return None
    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    if signal_return is None or spy_return is None:
        return None
    relative_vs_spy = signal_return - spy_return
    relative_vs_etf = signal_return - float(context["sector_etf_signal_day_return"])
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if relative_vs_etf < MIN_CANDIDATE_RELATIVE_VS_ETF:
        return None

    close_location = framework._close_location(row)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    realized_vol = framework._realized_vol(rows, idx)
    if (
        close_location is None
        or ret5 is None
        or ret20 is None
        or spy_ret20 is None
        or realized_vol is None
    ):
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO:
        return None

    score = (
        1.25 * float(context["sector_etf_relative_vs_spy"])
        + 1.75 * relative_vs_spy
        + 1.10 * relative_vs_etf
        + 0.55 * ret20_excess_spy
        + 0.35 * close_location
        + 0.030 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        + 0.020 * min(volume_ratio, 3.0)
        - 0.65 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "DEFENSIVE_SECTOR_ROTATION_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_sector_etf": round(relative_vs_etf, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "defensive_rotation_context": context,
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
    defensive_entries = {
        ticker: meta
        for ticker, meta in sector_entries.items()
        if meta.get("sector") in DEFENSIVE_SECTOR_ETF_BY_SECTOR
    }
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "defensive_rotation_days": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "candidate_universe_count": len(defensive_entries),
        "context_tickers": sorted(DEFENSIVE_ETF_TICKERS | {"SPY"}),
        "defensive_sectors": sorted(DEFENSIVE_SECTOR_ETF_BY_SECTOR),
    }
    for signal_date in dates:
        day_contexts = _defensive_contexts_for_day(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if not day_contexts:
            continue
        contexts.extend(day_contexts)
        context_scan["defensive_rotation_days"] += 1
        for context in day_contexts:
            for ticker in defensive_entries:
                row = _candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=defensive_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    context=context,
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
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_relative_vs_sector_etf"]),
            -float(row["candidate_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    context_scan["raw_candidate_rows"] = len(candidates)
    context_scan["unique_candidate_tickers"] = len({row["ticker"] for row in candidates})
    return candidates, contexts, context_scan


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
        "positive_replay_lead_not_promoted_defensive_sector_rotation_leadership"
        if gate["passed"]
        else "rejected_defensive_sector_rotation_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Defensive sector ETF rotation days where XLV/XLP/XLU lead "
                "SPY while same-sector liquid stocks also lead may identify "
                "durable defensive leadership candidates without using "
                "laggard catch-up."
            ),
            "change_type": "candidate_pool_paper_sleeve_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_defensive_sector_rotation_relation",
            "nearby_prior_experiments": [
                "exp-20260606-029",
                "exp-20260605-033",
                "exp-20260606-027",
                "exp-20260606-019",
                "exp-20260607-019",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "low",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "defensive_rotation_contexts_by_window": payload[
                "pressure_contexts_by_window"
            ],
            "defensive_rotation_context_samples_by_window": payload[
                "pressure_context_samples_by_window"
            ],
            "negative_reflection": (
                "If rejected, the likely reason is that defensive ETF "
                "rotation plus stock leadership is just same-day sector beta, "
                "already repriced before next-open entry, or too sparse "
                "outside late_strong. Do not retry by sweeping XLV/XLP/XLU "
                "return, close-location, leader, hold-day, cooldown, top-N, "
                "or notional thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. A "
                "retry after rejection needs a materially new defensive-flow, "
                "fundamental defensiveness, sector earnings, or forward "
                "replacement-value source."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "defensive_sector_etf_by_sector": DEFENSIVE_SECTOR_ETF_BY_SECTOR,
        "min_etf_signal_return": MIN_ETF_SIGNAL_RETURN,
        "min_etf_relative_vs_spy": MIN_ETF_RELATIVE_VS_SPY,
        "min_etf_close_location": MIN_ETF_CLOSE_LOCATION,
        "min_etf_ret20_excess_spy": MIN_ETF_RET20_EXCESS_SPY,
        "max_spy_signal_return": MAX_SPY_SIGNAL_RETURN,
        "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
        "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
        "min_candidate_relative_vs_etf": MIN_CANDIDATE_RELATIVE_VS_ETF,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
        "min_candidate_volume_ratio": MIN_CANDIDATE_VOLUME_RATIO,
        "max_candidate_ret5": MAX_CANDIDATE_RET5,
        "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
    }
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1 if payload["gate4"]["passed"] else 0,
        "actual_gate4_passed": payload["gate4"]["passed"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
        "brier_score": round(
            (
                PREDICTION["success_probability"]
                - (1.0 if payload["gate4"]["passed"] else 0.0)
            )
            ** 2,
            6,
        ),
    }
    payload["interpretation"] = (
        "The defensive-sector rotation leadership source cleared Gate 4 as a "
        "replay-only/default-off lead. No production surface was promoted; a "
        "shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The defensive-sector rotation leadership source did not clear "
            "Gate 4; do not promote or locally retune this relation on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    old_thin_delta = payload["delta_metrics"]["by_window"]["old_thin"]
    target_count = payload["target_trade_summary"]["total_trade_count"]
    why_result = (
        "The relation likely measured defensive sector beta rather than "
        "durable delayed leadership. Gate 4 observed {count} target trades; "
        "old_thin changed by {ev:+.4f} EV and ${pnl:+,.2f}. If rejected, the "
        "after-cost next-open edge was either already priced by the close, "
        "too thin outside selected rotations, or missing a more specific "
        "defensive-flow/fundamental catalyst."
    ).format(
        count=target_count,
        ev=old_thin_delta["expected_value_score"],
        pnl=old_thin_delta["total_pnl"],
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why_result,
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping XLV/XLP/XLU return, ETF close-location, "
            "sector membership, leader relative return, volume, volatility, "
            "hold-day, top-N, cooldown, or paper notional on the same frozen "
            "windows."
        ),
        "new_evidence_required": (
            "A retry requires a materially new PIT defensive-flow source, "
            "fundamental quality/stability relation, sector earnings revision "
            "source, or closed forward replacement-value rows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Rotation days | Trades |",
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
                days=scan.get("defensive_rotation_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Defensive Sector Rotation Leadership",
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
        "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
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
                "defensive_rotation_day_count": payload["context_scan_by_window"][
                    label
                ].get("defensive_rotation_days"),
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
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
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
    framework._load_window_snapshot = _load_window_snapshot
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
