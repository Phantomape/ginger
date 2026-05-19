"""exp-20260516-041: remaining negative ticker core adaptation scout.

Replay-only follow-up to the TSM medium-term adaptation experiment.

This script does not promote any shared policy. It runs independent
per-ticker core long risk-scalar sweeps for the remaining previously deferred
negative tickers (V, DDOG, ISRG), while keeping entries, ranking, exits,
targets, universe, heat, slots, LLM, and news behavior locked.

Singleton negative tickers from the current accepted stack are recorded in the
baseline audit, but they are not scalar-tuned because one-trade ticker tuning is
too fragile to justify a parameter experiment.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260516-041"
EXPERIMENT_SLUG = "remaining_ticker_core_adaptation"
MULTIPLIER_KEY = "ticker_core_risk_multiplier_applied"
TARGET_TICKERS = ["V", "DDOG", "ISRG"]
EXCLUDED_TICKERS = {"TSM"}
TARGET_STRATEGIES = {"trend_long", "breakout_long"}
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [1.0, 0.75, 0.50, 0.25, 0.0]
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 2
MIN_AFFECTED_WINDOW_COUNT = 2
MIN_TRADE_COUNT_SUM = 58
HORIZONS = [1, 3, 5, 10]
FAST_TARGET_MIN_PROFIT_NET = 0.01

CURRENT_TARGET_TICKER = ""
CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
CANDIDATE_SIGNALS: list[dict[str, Any]] = []

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    return original


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    return original


def _target_signal(sig: dict[str, Any]) -> bool:
    return (
        str(sig.get("ticker") or "").upper() == CURRENT_TARGET_TICKER
        and sig.get("strategy") in TARGET_STRATEGIES
    )


def _candidate_record(sig: dict[str, Any]) -> dict[str, Any]:
    sizing = sig.get("sizing") or {}
    return {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "shares_to_buy": sizing.get("shares_to_buy"),
        "entry_price": sizing.get("entry_price") or sig.get("entry_price"),
        "stop_price": sig.get("stop_price"),
        "target_price": sig.get("target_price"),
        "target_mult_used": sig.get("target_mult_used"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "confidence_score": sig.get("confidence_score"),
        "regime_exit_bucket": sig.get("regime_exit_bucket"),
        "regime_exit_score": sig.get("regime_exit_score"),
        "days_to_earnings": sig.get("days_to_earnings"),
        "gap_vulnerability_pct": sig.get("gap_vulnerability_pct"),
        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
        "rs60_top_quintile_state": sig.get("rs60_top_quintile_state"),
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
        "price_vs_200ma_pct": sig.get("price_vs_200ma_pct"),
        "price_vs_200ma_extension_state": sig.get("price_vs_200ma_extension_state"),
        "sizing_multipliers": {
            key: value
            for key, value in sizing.items()
            if key.endswith("_applied") and value not in (None, 1.0)
        },
    }


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    new_shares = int(math.floor(shares * scalar))
    if new_shares >= shares:
        return sizing

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    position_value = entry * new_shares
    risk_amount = net_risk_per_share * new_shares
    out = dict(sizing)
    out["ticker_core_target_ticker"] = CURRENT_TARGET_TICKER
    out["ticker_core_baseline_shares"] = shares
    out["ticker_core_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(position_value, 2)
    out["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    out["risk_amount_usd"] = round(risk_amount, 2)
    out["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out: list[dict[str, Any]] = []
        for sig in sized:
            if _target_signal(sig):
                CANDIDATE_SIGNALS.append(_candidate_record(sig))
            sizing = sig.get("sizing") or {}
            if _target_signal(sig) and sizing.get("shares_to_buy"):
                adjusted = _scale_sizing(
                    sizing,
                    CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "risk_multiplier": CURRENT_RISK_MULTIPLIER,
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted.get("shares_to_buy"),
                            "entry_price": sizing.get("entry_price")
                            or sig.get("entry_price"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "confidence_score": sig.get("confidence_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "signal_day_ticker_green_candle": sig.get(
                                "signal_day_ticker_green_candle"
                            ),
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                            "gap_vulnerability_pct": sig.get(
                                "gap_vulnerability_pct"
                            ),
                            "days_to_earnings": sig.get("days_to_earnings"),
                        }
                    )
                    sig = {**sig, "sizing": adjusted}
            out.append(sig)
        return out

    return wrapped


def _load_ohlcv_rows(snapshot: str, ticker: str) -> list[dict[str, Any]]:
    path = base.REPO_ROOT / snapshot
    payload = json.loads(path.read_text(encoding="utf-8"))
    table = ((payload.get("ohlcv") or {}).get(ticker)) or {}
    if isinstance(table, list):
        rows: list[dict[str, Any]] = []
        for row in table:
            try:
                rows.append(
                    {
                        "date": str(row["Date"])[:10],
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return rows

    dates = table.get("Date") or []
    rows: list[dict[str, Any]] = []
    for idx, date in enumerate(dates):
        try:
            rows.append(
                {
                    "date": str(date)[:10],
                    "open": float(table["Open"][idx]),
                    "high": float(table["High"][idx]),
                    "low": float(table["Low"][idx]),
                    "close": float(table["Close"][idx]),
                }
            )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    return rows


def _net_return(exit_price: float, entry_price: float) -> float | None:
    if entry_price <= 0:
        return None
    return round(
        (exit_price / entry_price) - 1.0 - base.portfolio_engine.ROUND_TRIP_COST_PCT,
        6,
    )


def _diagnose_trade(
    label: str,
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    entry_date = str(trade.get("entry_date") or "")[:10]
    exit_date = str(trade.get("exit_date") or "")[:10]
    idx_by_date = {row["date"]: idx for idx, row in enumerate(rows)}
    entry_idx = idx_by_date.get(entry_date)
    exit_idx = idx_by_date.get(exit_date)
    entry_price = float(trade.get("entry_price") or 0.0)
    out = {
        "window": label,
        "trade_key": base._trade_key(trade),
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "shares": trade.get("shares"),
        "pnl": trade.get("pnl"),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "target_mult_used": trade.get("target_mult_used"),
        "sizing_multipliers": trade.get("sizing_multipliers"),
        "diagnostic_available": entry_idx is not None,
    }
    if entry_idx is None:
        return out

    entry_row = rows[entry_idx]
    out["signal_day_open_close_return_pct"] = (
        round((entry_row["close"] / entry_row["open"]) - 1.0, 6)
        if entry_row["open"]
        else None
    )

    horizon_returns = {}
    for horizon in HORIZONS:
        horizon_idx = min(entry_idx + horizon, len(rows) - 1)
        horizon_returns[f"{horizon}d_net_return_pct"] = _net_return(
            rows[horizon_idx]["close"],
            entry_price,
        )
    out["horizon_returns"] = horizon_returns

    last_idx = exit_idx if exit_idx is not None else min(entry_idx + max(HORIZONS), len(rows) - 1)
    path = rows[entry_idx : last_idx + 1]
    if path:
        max_high = max(row["high"] for row in path)
        min_low = min(row["low"] for row in path)
        max_close = max(row["close"] for row in path)
        out["mfe_high_net_pct"] = _net_return(max_high, entry_price)
        out["mae_low_net_pct"] = _net_return(min_low, entry_price)
        out["max_close_net_pct_before_exit"] = _net_return(max_close, entry_price)
        out["profit_available_before_exit"] = (
            isinstance(out["max_close_net_pct_before_exit"], (int, float))
            and out["max_close_net_pct_before_exit"] > 0
        )
        out["fast_target_candidate_before_exit"] = (
            isinstance(out["max_close_net_pct_before_exit"], (int, float))
            and out["max_close_net_pct_before_exit"] >= FAST_TARGET_MIN_PROFIT_NET
        )
    return out


def _build_lifecycle_diagnostic(
    ticker: str,
    before_runs: dict[str, dict[str, Any]],
    identity_candidates: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    trades: list[dict[str, Any]] = []
    for label, run in before_runs.items():
        rows = _load_ohlcv_rows(WINDOWS[label]["snapshot"], ticker)
        for trade in run["trades"]:
            if str(trade.get("ticker") or "").upper() == ticker:
                trades.append(_diagnose_trade(label, trade, rows))

    horizon_summary = {}
    for horizon in HORIZONS:
        key = f"{horizon}d_net_return_pct"
        values = [
            trade.get("horizon_returns", {}).get(key)
            for trade in trades
            if isinstance(trade.get("horizon_returns", {}).get(key), (int, float))
        ]
        horizon_summary[key] = {
            "count": len(values),
            "positive_count": sum(1 for value in values if value > 0),
            "avg_net_return_pct": round(sum(values) / len(values), 6)
            if values
            else None,
            "min_net_return_pct": min(values) if values else None,
            "max_net_return_pct": max(values) if values else None,
        }

    fast_candidates = [
        trade for trade in trades if trade.get("fast_target_candidate_before_exit")
    ]
    short_positive_count = sum(
        1
        for trade in trades
        if any(
            isinstance(value, (int, float)) and value > 0
            for value in (trade.get("horizon_returns") or {}).values()
        )
    )
    return {
        "status": "observed_only",
        "ticker": ticker,
        "trade_count": len(trades),
        "win_count": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0),
        "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "horizon_summary": horizon_summary,
        "short_positive_trade_count": short_positive_count,
        "profit_available_before_exit_count": sum(
            1 for trade in trades if trade.get("profit_available_before_exit")
        ),
        "fast_target_candidate_count": len(fast_candidates),
        "fast_target_supported": len(fast_candidates) >= 2,
        "branch_recommendation": (
            "consider_fast_target_only_with_new_evidence"
            if len(fast_candidates) >= 2
            else "prioritize_core_risk_budget_review"
        ),
        "candidate_signals_by_window": identity_candidates,
        "trades": trades,
    }


def _baseline_ticker_audit(before_runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "win_count": 0, "total_pnl": 0.0, "windows": set()}
    )
    for label, run in before_runs.items():
        for trade in run["trades"]:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            row = stats[ticker]
            row["trade_count"] += 1
            row["win_count"] += 1 if pnl > 0 else 0
            row["total_pnl"] += pnl
            row["windows"].add(label)
    rows = [
        {
            "ticker": ticker,
            "trade_count": row["trade_count"],
            "win_count": row["win_count"],
            "total_pnl": round(row["total_pnl"], 2),
            "windows": sorted(row["windows"]),
        }
        for ticker, row in stats.items()
    ]
    return sorted(rows, key=lambda row: (row["total_pnl"], row["ticker"]))


def _candidate_payload(
    ticker: str,
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    global CURRENT_TARGET_TICKER, CURRENT_RISK_MULTIPLIER, CANDIDATE_SIGNALS
    CURRENT_TARGET_TICKER = ticker
    CURRENT_RISK_MULTIPLIER = multiplier

    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}
    candidate_signals: dict[str, list[dict[str, Any]]] = {}

    for label in base.WINDOWS:
        CANDIDATE_SIGNALS = []
        variant = base._run_window(label, variant=True)
        candidate_signals[label] = list(CANDIDATE_SIGNALS)
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    adjusted_count = sum(len(rows) for rows in adjustments.values())
    affected_window_count = sum(1 for rows in adjustments.values() if rows)
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = (
        max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    convergence_passed = all(
        bool(row.get("converged")) for row in after_metrics.values()
    )
    sample_guard_passed = (
        adjusted_count >= MIN_AFFECTED_SIGNAL_COUNT
        and affected_window_count >= MIN_AFFECTED_WINDOW_COUNT
    )
    passed = (
        not math.isclose(multiplier, BASELINE_RISK_MULTIPLIER)
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and drawdown_guardrail_passed
        and convergence_passed
        and aggregate_after["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
        and aggregate_after["survival_rate_min"] >= 0.05
        and sample_guard_passed
    )
    return {
        "ticker": ticker,
        "risk_multiplier": multiplier,
        "is_identity_control": math.isclose(multiplier, BASELINE_RISK_MULTIPLIER),
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "adjusted_signal_count": adjusted_count,
            "affected_window_count": affected_window_count,
            "min_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "min_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "sample_guard_passed": sample_guard_passed,
            "trade_count_sum_after": aggregate_after["trade_count_sum"],
            "min_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "trade_count_guard_passed": (
                aggregate_after["trade_count_sum"] >= MIN_TRADE_COUNT_SUM
            ),
            "convergence_passed": convergence_passed,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "adjustments": adjustments,
        "changed_trades": changed_trades,
        "sizing_attribution": sizing_attribution,
        "candidate_signals": candidate_signals,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row["passed"]]
    pool = passed if passed else [row for row in candidates if not row["is_identity_control"]]
    return max(
        pool,
        key=lambda row: (
            1 if row["passed"] else 0,
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"].get("max_drawdown_worse") or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": row["ticker"],
            "risk_multiplier": row["risk_multiplier"],
            "is_identity_control": row["is_identity_control"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "adjusted_signal_count": row["gate4"]["adjusted_signal_count"],
            "affected_window_count": row["gate4"]["affected_window_count"],
            "trade_count_sum_after": row["gate4"]["trade_count_sum_after"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "sample_guard_passed": row["gate4"]["sample_guard_passed"],
            "drawdown_guardrail_passed": row["gate4"]["drawdown_guardrail_passed"],
        }
        for row in candidates
    ]


def _ticker_result(
    ticker: str,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidates = [
        _candidate_payload(ticker, multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    identity = next(row for row in candidates if row["is_identity_control"])
    selected = _select_candidate(candidates)
    lifecycle = _build_lifecycle_diagnostic(
        ticker,
        before_runs,
        identity["candidate_signals"],
    )
    return {
        "ticker": ticker,
        "decision": (
            "accepted_for_single_ticker_promotion_review"
            if selected["passed"]
            else "rejected_or_watch_only"
        ),
        "selected_risk_multiplier": selected["risk_multiplier"],
        "selected": selected,
        "sweep_summary": _sweep_summary(candidates),
        "lifecycle_diagnostic": lifecycle,
        "identity_control": {
            "expected_value_score_delta": identity["expected_value_score_delta"],
            "total_pnl_delta": identity["total_pnl_delta"],
            "trade_count_delta": identity["delta_metrics"]["aggregate_delta"][
                "trade_count_sum"
            ],
            "metrics_unchanged": (
                math.isclose(identity["expected_value_score_delta"], 0.0)
                and math.isclose(identity["total_pnl_delta"], 0.0)
                and identity["delta_metrics"]["aggregate_delta"]["trade_count_sum"] == 0
            ),
        },
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Ticker | Decision | Selected | dEV | dPnL | Improved | Regressed | Affected | Windows | Fast target? |",
        "|---|---|---:|---:|---:|---|---|---:|---:|---|",
    ]
    for ticker, result in payload["ticker_results"].items():
        selected = result["selected"]
        lifecycle = result["lifecycle_diagnostic"]
        rows.append(
            "| {ticker} | {decision} | {mult:.2f} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {fast} |".format(
                ticker=ticker,
                decision=result["decision"],
                mult=selected["risk_multiplier"],
                dev=selected["expected_value_score_delta"],
                dpnl=selected["total_pnl_delta"],
                improved=", ".join(selected["gate4"]["improved_windows"]) or "-",
                regressed=", ".join(selected["gate4"]["regressed_windows"]) or "-",
                affected=selected["gate4"]["adjusted_signal_count"],
                windows=selected["gate4"]["affected_window_count"],
                fast=lifecycle["fast_target_supported"],
            )
        )

    audit_rows = [
        "| Ticker | Trades | Wins | PnL | Windows | Sweep status |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in payload["negative_ticker_audit"]:
        if row["ticker"] in EXCLUDED_TICKERS:
            status = "excluded_current_policy"
        elif row["ticker"] in TARGET_TICKERS:
            status = "exact_sweep"
        elif row["trade_count"] <= 1:
            status = "observed_only_singleton"
        else:
            status = "observed_only"
        audit_rows.append(
            "| {ticker} | {trades} | {wins} | ${pnl:,.2f} | {windows} | {status} |".format(
                ticker=row["ticker"],
                trades=row["trade_count"],
                wins=row["win_count"],
                pnl=row["total_pnl"],
                windows=", ".join(row["windows"]),
                status=status,
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Remaining Ticker Core Adaptation",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Per-ticker scalar results",
            "",
            *rows,
            "",
            "## Baseline negative ticker audit",
            "",
            *audit_rows,
            "",
            "Production impact: replay-only scout. No shared policy was changed.",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = (
        base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    )
    ticket_path = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    base._upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


def run() -> dict[str, Any]:
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown

    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    baseline_aggregate = base._aggregate(before_metrics)
    ticker_audit = _baseline_ticker_audit(before_runs)
    negative_ticker_audit = [row for row in ticker_audit if row["total_pnl"] < 0]

    ticker_results = {
        ticker: _ticker_result(ticker, before_runs) for ticker in TARGET_TICKERS
    }
    accepted = [
        result
        for result in ticker_results.values()
        if result["decision"] == "accepted_for_single_ticker_promotion_review"
    ]
    best = max(
        ticker_results.values(),
        key=lambda result: (
            1 if result["selected"]["passed"] else 0,
            result["selected"]["expected_value_score_delta"],
            result["selected"]["total_pnl_delta"],
        ),
    )
    status = (
        "accepted_candidates_for_ordered_single_ticker_review"
        if accepted
        else "rejected_watch_only"
    )
    decision = status
    interpretation = (
        "At least one remaining ticker cleared the replay scout for a separate single-ticker promotion review; do not promote multiple ticker scalars together."
        if accepted
        else "The remaining ticker-level scalar sweeps did not clear the promotion gate; keep them as attribution/watch-only evidence."
    )

    singleton_watch = [
        row
        for row in negative_ticker_audit
        if row["ticker"] not in TARGET_TICKERS
        and row["ticker"] not in EXCLUDED_TICKERS
        and row["trade_count"] <= 1
    ]
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "The remaining negative core long tickers may be structurally "
            "mis-sized in the current medium-term model. If true, independent "
            "ticker-specific post-sizing risk scalars should improve aggregate "
            "EV without changing entries, exits, ranking, targets, slots, heat, "
            "LLM, or news behavior."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "independent_remaining_ticker_core_risk_multiplier",
        "single_causal_variable": (
            "For each subtest, only one target ticker's existing core long "
            "post-sizing risk scalar changes; no multi-ticker scalar is tested "
            "as a promotion candidate."
        ),
        "parameters": {
            "target_tickers": TARGET_TICKERS,
            "excluded_tickers": sorted(EXCLUDED_TICKERS),
            "target_strategies": sorted(TARGET_STRATEGIES),
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "fast_target_min_profit_net": FAST_TARGET_MIN_PROFIT_NET,
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "minimum_trade_count_sum": MIN_TRADE_COUNT_SUM,
            "singleton_negative_tickers_observed_only": singleton_watch,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all non-target ticker sizing multipliers",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: remaining negative ticker residuals may need "
                "TSM-style risk-budget review."
            ),
            "2_history_check": {
                "exp-20260516-039": (
                    "TSM passed a ticker-specific 0.25x core long risk scalar "
                    "and was promoted separately."
                ),
                "exp-20260516-012": (
                    "A broader semiconductor haircut was sample-thin; this run "
                    "does not generalize sector rules."
                ),
                "current_audit": (
                    "Current accepted stack negative tickers are recorded in "
                    "negative_ticker_audit; singleton losers are not scalar-tuned."
                ),
            },
            "3_single_causal_variable": (
                "Each ticker subtest changes only that ticker's post-sizing "
                "core risk multiplier."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV and PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "windows, max drawdown drift <=0.5pp, trade_count_sum >=58, "
                "affected target signals >=2 across >=2 windows, and survival >=5%."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_041_remaining_ticker_core_adaptation.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": baseline_aggregate,
            "baseline_artifact": (
                "data/experiments/exp-20260516-039/"
                "tsm_core_adaptation.json after shared-policy promotion"
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine ticker",
                "risk_engine strategy",
                "portfolio_engine shares_to_buy",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": baseline_aggregate["survival_rate_min"],
            "passed": baseline_aggregate["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": bool(accepted),
            "accepted_tickers": [result["ticker"] for result in accepted],
            "best_ticker": best["ticker"],
            "best_selected_multiplier": best["selected_risk_multiplier"],
            "best_expected_value_score_delta": best["selected"][
                "expected_value_score_delta"
            ],
            "best_total_pnl_delta": best["selected"]["total_pnl_delta"],
        },
        "before_metrics": before_metrics,
        "baseline_ticker_audit": ticker_audit,
        "negative_ticker_audit": negative_ticker_audit,
        "ticker_results": ticker_results,
        "expected_value_score_delta": best["selected"]["expected_value_score_delta"],
        "total_pnl_delta": best["selected"]["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "No LLM behavior changed; this is deterministic ticker-level "
                "risk-budget attribution."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "Any accepted ticker must be promoted in a separate follow-up "
                "as one shared constant and one shared portfolio_engine sizing "
                "branch, with focused tests and fresh canonical replay."
            ),
        },
        "why_not_other_changes": (
            "This run does not tune singleton negative tickers and does not "
            "test a combined multi-ticker scalar, because both would create "
            "fragile attribution and overfitting risk."
        ),
        "known_risks": [
            "Ticker-specific rules are fragile and should remain rare.",
            "One-window negative evidence is not enough for promotion.",
            "Zero-risk variants can free slots and create replacement trades.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "Promote at most one accepted ticker in a separate experiment, or "
            "wait for forward evidence / a broader production-visible mechanism "
            "for rejected or one-window names."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_041_remaining_ticker_core_adaptation.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


if __name__ == "__main__":
    result = run()
    _persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "accepted_tickers": result["gate4"]["accepted_tickers"],
                "best_ticker": result["gate4"]["best_ticker"],
                "best_selected_multiplier": result["gate4"][
                    "best_selected_multiplier"
                ],
                "best_expected_value_score_delta": result["gate4"][
                    "best_expected_value_score_delta"
                ],
                "best_total_pnl_delta": result["gate4"]["best_total_pnl_delta"],
                "negative_ticker_audit": result["negative_ticker_audit"],
                "ticker_summary": {
                    ticker: {
                        "decision": row["decision"],
                        "selected_risk_multiplier": row[
                            "selected_risk_multiplier"
                        ],
                        "expected_value_score_delta": row["selected"][
                            "expected_value_score_delta"
                        ],
                        "total_pnl_delta": row["selected"]["total_pnl_delta"],
                        "improved_windows": row["selected"]["gate4"][
                            "improved_windows"
                        ],
                        "regressed_windows": row["selected"]["gate4"][
                            "regressed_windows"
                        ],
                        "adjusted_signal_count": row["selected"]["gate4"][
                            "adjusted_signal_count"
                        ],
                        "affected_window_count": row["selected"]["gate4"][
                            "affected_window_count"
                        ],
                        "fast_target_supported": row["lifecycle_diagnostic"][
                            "fast_target_supported"
                        ],
                    }
                    for ticker, row in result["ticker_results"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
