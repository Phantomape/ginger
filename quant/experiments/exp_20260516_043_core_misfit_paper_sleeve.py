"""exp-20260516-043: core misfit negative-signal paper sleeve.

Replay-only experiment for the user hypothesis that tickers with persistent
negative core-long contribution may be useful as "do not buy" or inverse paper
signals. The core stack is locked; this script only measures counterfactual
paper surfaces sourced from real core entries and entry-loop candidate events.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base

from fill_model import (  # noqa: E402
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_STOP,
    SLIPPAGE_BPS_TARGET,
    apply_entry_fill,
    apply_slippage,
)
from constants import ADVERSE_GAP_CANCEL_PCT, CANCEL_GAP_PCT  # noqa: E402
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402
from production_parity import classify_entry_open_cancel  # noqa: E402


EXPERIMENT_ID = "exp-20260516-043"
EXPERIMENT_SLUG = "core_misfit_paper_sleeve"

PRIMARY_MISFIT_TICKERS = ["TSM", "ISRG", "V", "DDOG"]
TARGET_STRATEGIES = {"trend_long", "breakout_long"}
PAPER_DECISIONS = {"entered", "slot_sliced"}
HORIZONS = [1, 3, 5, 10]
MIN_PRIMARY_TRADES = 4
MIN_PRIMARY_WINDOWS = 2
MIN_FORWARD_PAPER_CLOSED_TRADES_FOR_LIVE_SHORT = 20

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


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


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

    rows: list[dict[str, Any]] = []
    dates = table.get("Date") or []
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


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {row["date"]: idx for idx, row in enumerate(rows)}


def _next_fill(
    rows: list[dict[str, Any]],
    signal_date: str,
    signal_entry: float | None,
    stop_price: float | None,
) -> dict[str, Any]:
    idx_by_date = _row_index(rows)
    signal_idx = idx_by_date.get(signal_date)
    if signal_idx is None:
        return {"status": "missing_signal_date"}
    for idx in range(signal_idx + 1, min(signal_idx + 4, len(rows))):
        row = rows[idx]
        raw_open = row["open"]
        entry_ref = signal_entry if signal_entry and signal_entry > 0 else raw_open
        cancel_reason = classify_entry_open_cancel(
            raw_open,
            entry_ref,
            stop_price=stop_price,
            upside_gap_cancel_pct=CANCEL_GAP_PCT,
            adverse_gap_cancel_pct=ADVERSE_GAP_CANCEL_PCT,
        )
        if cancel_reason in {
            "gap_cancel",
            "adverse_gap_down_cancel",
            "stop_breach_cancel",
        }:
            return {
                "status": cancel_reason,
                "fill_date": row["date"],
                "raw_open": round(raw_open, 4),
            }
        return {
            "status": "filled",
            "fill_date": row["date"],
            "fill_index": idx,
            "raw_open": round(raw_open, 4),
            "long_entry_price": apply_entry_fill(raw_open),
            "short_entry_price": apply_slippage(
                raw_open,
                SLIPPAGE_BPS_ENTRY,
                "sell",
            ),
        }
    return {"status": "no_future_fill"}


def _long_return(entry_price: float, exit_raw_close: float) -> float:
    exit_price = apply_slippage(exit_raw_close, SLIPPAGE_BPS_TARGET, "sell")
    return (exit_price - entry_price) / entry_price - ROUND_TRIP_COST_PCT


def _short_return(entry_price: float, cover_raw_close: float) -> float:
    cover_price = apply_slippage(cover_raw_close, SLIPPAGE_BPS_STOP, "buy")
    return (entry_price - cover_price) / entry_price - ROUND_TRIP_COST_PCT


def _pnl_from_return(entry_price: float, shares: int, net_return: float) -> float:
    return entry_price * shares * net_return


def _horizon_returns(
    rows: list[dict[str, Any]],
    fill_index: int,
    long_entry_price: float,
    short_entry_price: float,
    shares: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in HORIZONS:
        horizon_idx = min(fill_index + horizon, len(rows) - 1)
        row = rows[horizon_idx]
        long_ret = _long_return(long_entry_price, row["close"])
        short_ret = _short_return(short_entry_price, row["close"])
        out[str(horizon)] = {
            "exit_date": row["date"],
            "long_net_return_pct": _round(long_ret),
            "long_pnl": round(_pnl_from_return(long_entry_price, shares, long_ret), 2),
            "inverse_short_net_return_pct": _round(short_ret),
            "inverse_short_pnl": round(
                _pnl_from_return(short_entry_price, shares, short_ret),
                2,
            ),
        }
    return out


def _actual_inverse_exit(trade: dict[str, Any]) -> dict[str, Any] | None:
    shares = _as_int(trade.get("shares"))
    if shares <= 0:
        return None
    entry_open = _as_float(trade.get("entry_open_price"))
    exit_raw = _as_float(trade.get("exit_raw_price"))
    if entry_open is not None and exit_raw is not None:
        entry_short = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "sell")
        cover_price = apply_slippage(exit_raw, SLIPPAGE_BPS_STOP, "buy")
    else:
        entry_short = _as_float(trade.get("entry_price"))
        cover_price = _as_float(trade.get("exit_price"))
    if not entry_short or not cover_price:
        return None
    net_return = (entry_short - cover_price) / entry_short - ROUND_TRIP_COST_PCT
    pnl = (entry_short * shares) * net_return
    return {
        "entry_short_price": round(entry_short, 4),
        "cover_price": round(cover_price, 4),
        "inverse_actual_exit_net_return_pct": _round(net_return),
        "inverse_actual_exit_pnl": round(pnl, 2),
    }


def _run_window_with_candidates(label: str) -> dict[str, Any]:
    spec = WINDOWS[label]
    engine = base.BacktestEngine(
        base.get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} candidate replay failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "entry_candidate_events": result.get("entry_candidate_events") or [],
        "sizing_rule_signal_attribution": result.get("sizing_rule_signal_attribution")
        or {},
        "sizing_rule_trade_attribution": result.get("sizing_rule_trade_attribution")
        or {},
    }


def _baseline_ticker_audit(runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "win_count": 0, "total_pnl": 0.0, "windows": set()}
    )
    for label, run in runs.items():
        for trade in run["trades"]:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            row = stats[ticker]
            row["trade_count"] += 1
            row["win_count"] += 1 if pnl > 0 else 0
            row["total_pnl"] += pnl
            row["windows"].add(label)
    return sorted(
        [
            {
                "ticker": ticker,
                "trade_count": row["trade_count"],
                "win_count": row["win_count"],
                "total_pnl": round(row["total_pnl"], 2),
                "windows": sorted(row["windows"]),
            }
            for ticker, row in stats.items()
        ],
        key=lambda row: (row["total_pnl"], row["ticker"]),
    )


def _trade_record(
    label: str,
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = str(trade.get("entry_date") or "")[:10]
    shares = _as_int(trade.get("shares"))
    idx_by_date = _row_index(rows)
    entry_idx = idx_by_date.get(entry_date)
    entry_price = _as_float(trade.get("entry_price"))
    entry_open = _as_float(trade.get("entry_open_price"))
    if entry_open is not None:
        short_entry = apply_slippage(entry_open, SLIPPAGE_BPS_ENTRY, "sell")
    else:
        short_entry = entry_price
    horizon = {}
    if entry_idx is not None and entry_price and short_entry and shares > 0:
        horizon = _horizon_returns(rows, entry_idx, entry_price, short_entry, shares)
    inverse = _actual_inverse_exit(trade) or {}
    pnl = float(trade.get("pnl") or 0.0)
    return {
        "window": label,
        "trade_key": trade.get("trade_key") or base._trade_key(trade),
        "ticker": ticker,
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": trade.get("entry_price"),
        "entry_open_price": trade.get("entry_open_price"),
        "exit_price": trade.get("exit_price"),
        "exit_raw_price": trade.get("exit_raw_price"),
        "shares": shares,
        "pnl": round(pnl, 2),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "no_trade_avoided_pnl": round(-pnl, 2),
        "sizing_multipliers": trade.get("sizing_multipliers"),
        "horizon": horizon,
        **inverse,
    }


def _candidate_record(
    label: str,
    event: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot = event.get("signal_snapshot") or {}
    sizing = snapshot.get("sizing") or {}
    signal_date = str(event.get("date") or "")[:10]
    shares = _as_int((event.get("details") or {}).get("shares"))
    if shares <= 0:
        shares = _as_int(sizing.get("shares_to_buy"))
    signal_entry = _as_float(snapshot.get("entry_price"))
    stop_price = _as_float(snapshot.get("stop_price"))
    fill = _next_fill(rows, signal_date, signal_entry, stop_price)
    horizon = {}
    if (
        fill.get("status") == "filled"
        and shares > 0
        and fill.get("fill_index") is not None
        and fill.get("long_entry_price")
        and fill.get("short_entry_price")
    ):
        horizon = _horizon_returns(
            rows,
            int(fill["fill_index"]),
            float(fill["long_entry_price"]),
            float(fill["short_entry_price"]),
            shares,
        )
    return {
        "window": label,
        "signal_date": signal_date,
        "ticker": str(event.get("ticker") or "").upper(),
        "strategy": event.get("strategy"),
        "decision": event.get("decision"),
        "candidate_rank": event.get("candidate_rank"),
        "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
        "shares": shares,
        "entry_price": signal_entry,
        "stop_price": stop_price,
        "target_price": _as_float(snapshot.get("target_price")),
        "trade_quality_score": _as_float(snapshot.get("trade_quality_score")),
        "confidence_score": _as_float(snapshot.get("confidence_score")),
        "target_mult_used": _as_float(snapshot.get("target_mult_used")),
        "risk_multipliers": sizing.get("risk_multipliers") or {},
        "fill": fill,
        "horizon": horizon,
    }


def _collect_surfaces(
    baseline_runs: dict[str, dict[str, Any]],
    candidate_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ticker_audit = _baseline_ticker_audit(baseline_runs)
    negative_tickers = [
        row["ticker"] for row in ticker_audit if float(row.get("total_pnl") or 0.0) < 0
    ]
    tracked_tickers = sorted(set(PRIMARY_MISFIT_TICKERS) | set(negative_tickers))

    trades: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for label, run in baseline_runs.items():
        rows_by_ticker = {
            ticker: _load_ohlcv_rows(WINDOWS[label]["snapshot"], ticker)
            for ticker in tracked_tickers
        }
        for trade in run["trades"]:
            ticker = str(trade.get("ticker") or "").upper()
            if ticker not in tracked_tickers:
                continue
            if trade.get("strategy") not in TARGET_STRATEGIES:
                continue
            trades.append(_trade_record(label, trade, rows_by_ticker.get(ticker, [])))

    for label, run in candidate_runs.items():
        rows_cache: dict[str, list[dict[str, Any]]] = {}
        for event in run["entry_candidate_events"]:
            ticker = str(event.get("ticker") or "").upper()
            if ticker not in tracked_tickers:
                continue
            if event.get("strategy") not in TARGET_STRATEGIES:
                continue
            if event.get("decision") not in PAPER_DECISIONS:
                continue
            snapshot = event.get("signal_snapshot") or {}
            sizing = snapshot.get("sizing") or {}
            if _as_int((event.get("details") or {}).get("shares")) <= 0 and _as_int(
                sizing.get("shares_to_buy")
            ) <= 0:
                continue
            rows = rows_cache.setdefault(
                ticker,
                _load_ohlcv_rows(WINDOWS[label]["snapshot"], ticker),
            )
            candidates.append(_candidate_record(label, event, rows))

    return {
        "tracked_tickers": tracked_tickers,
        "negative_tickers": negative_tickers,
        "baseline_ticker_audit": ticker_audit,
        "actual_trade_records": trades,
        "paper_candidate_records": candidates,
    }


def _empty_horizon_summary() -> dict[str, dict[str, Any]]:
    return {
        str(horizon): {
            "fast_long_pnl": 0.0,
            "fast_long_positive_count": 0,
            "fast_long_avg_return_pct": None,
            "fast_long_worst_return_pct": None,
            "inverse_short_pnl": 0.0,
            "inverse_short_positive_count": 0,
            "inverse_short_avg_return_pct": None,
            "inverse_short_worst_return_pct": None,
            "_fast_returns": [],
            "_short_returns": [],
        }
        for horizon in HORIZONS
    }


def _finalize_horizon_summary(summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon, row in summary.items():
        fast_returns = row.pop("_fast_returns")
        short_returns = row.pop("_short_returns")
        row["fast_long_pnl"] = round(float(row["fast_long_pnl"]), 2)
        row["inverse_short_pnl"] = round(float(row["inverse_short_pnl"]), 2)
        row["fast_long_avg_return_pct"] = (
            round(sum(fast_returns) / len(fast_returns), 6) if fast_returns else None
        )
        row["fast_long_worst_return_pct"] = min(fast_returns) if fast_returns else None
        row["inverse_short_avg_return_pct"] = (
            round(sum(short_returns) / len(short_returns), 6)
            if short_returns
            else None
        )
        row["inverse_short_worst_return_pct"] = (
            min(short_returns) if short_returns else None
        )
        out[horizon] = row
    return out


def _summarize_actual(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "trade_count": len(records),
        "windows": sorted({row["window"] for row in records}),
        "tickers": sorted({row["ticker"] for row in records}),
        "actual_core_pnl": round(sum(float(row.get("pnl") or 0.0) for row in records), 2),
        "actual_win_count": sum(1 for row in records if float(row.get("pnl") or 0.0) > 0),
        "no_trade_avoided_pnl": round(
            sum(float(row.get("no_trade_avoided_pnl") or 0.0) for row in records),
            2,
        ),
        "inverse_actual_exit_pnl": round(
            sum(float(row.get("inverse_actual_exit_pnl") or 0.0) for row in records),
            2,
        ),
        "inverse_actual_exit_positive_count": sum(
            1 for row in records if float(row.get("inverse_actual_exit_pnl") or 0.0) > 0
        ),
        "by_window": {},
        "by_ticker": {},
        "horizon": _empty_horizon_summary(),
    }
    for row in records:
        window = row["window"]
        ticker = row["ticker"]
        win = summary["by_window"].setdefault(
            window,
            {"trade_count": 0, "actual_core_pnl": 0.0, "no_trade_avoided_pnl": 0.0},
        )
        win["trade_count"] += 1
        win["actual_core_pnl"] += float(row.get("pnl") or 0.0)
        win["no_trade_avoided_pnl"] += float(row.get("no_trade_avoided_pnl") or 0.0)
        tick = summary["by_ticker"].setdefault(
            ticker,
            {
                "trade_count": 0,
                "windows": set(),
                "actual_core_pnl": 0.0,
                "no_trade_avoided_pnl": 0.0,
                "inverse_actual_exit_pnl": 0.0,
            },
        )
        tick["trade_count"] += 1
        tick["windows"].add(window)
        tick["actual_core_pnl"] += float(row.get("pnl") or 0.0)
        tick["no_trade_avoided_pnl"] += float(row.get("no_trade_avoided_pnl") or 0.0)
        tick["inverse_actual_exit_pnl"] += float(
            row.get("inverse_actual_exit_pnl") or 0.0
        )
        for horizon, values in (row.get("horizon") or {}).items():
            bucket = summary["horizon"][horizon]
            long_pnl = float(values.get("long_pnl") or 0.0)
            short_pnl = float(values.get("inverse_short_pnl") or 0.0)
            long_ret = values.get("long_net_return_pct")
            short_ret = values.get("inverse_short_net_return_pct")
            bucket["fast_long_pnl"] += long_pnl
            bucket["inverse_short_pnl"] += short_pnl
            bucket["fast_long_positive_count"] += 1 if long_pnl > 0 else 0
            bucket["inverse_short_positive_count"] += 1 if short_pnl > 0 else 0
            if isinstance(long_ret, (int, float)):
                bucket["_fast_returns"].append(long_ret)
            if isinstance(short_ret, (int, float)):
                bucket["_short_returns"].append(short_ret)
    for row in summary["by_window"].values():
        row["actual_core_pnl"] = round(row["actual_core_pnl"], 2)
        row["no_trade_avoided_pnl"] = round(row["no_trade_avoided_pnl"], 2)
    for row in summary["by_ticker"].values():
        row["windows"] = sorted(row["windows"])
        row["actual_core_pnl"] = round(row["actual_core_pnl"], 2)
        row["no_trade_avoided_pnl"] = round(row["no_trade_avoided_pnl"], 2)
        row["inverse_actual_exit_pnl"] = round(row["inverse_actual_exit_pnl"], 2)
    summary["horizon"] = _finalize_horizon_summary(summary["horizon"])
    return summary


def _summarize_candidates(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "candidate_count": len(records),
        "filled_count": sum(1 for row in records if row.get("fill", {}).get("status") == "filled"),
        "entered_count": sum(1 for row in records if row.get("decision") == "entered"),
        "slot_sliced_count": sum(1 for row in records if row.get("decision") == "slot_sliced"),
        "windows": sorted({row["window"] for row in records}),
        "tickers": sorted({row["ticker"] for row in records}),
        "by_ticker": {},
        "by_fill_status": {},
        "horizon": _empty_horizon_summary(),
    }
    for row in records:
        ticker = row["ticker"]
        status = row.get("fill", {}).get("status") or "unknown"
        summary["by_fill_status"][status] = summary["by_fill_status"].get(status, 0) + 1
        tick = summary["by_ticker"].setdefault(
            ticker,
            {
                "candidate_count": 0,
                "filled_count": 0,
                "entered_count": 0,
                "slot_sliced_count": 0,
                "windows": set(),
                "horizon": _empty_horizon_summary(),
            },
        )
        tick["candidate_count"] += 1
        tick["filled_count"] += 1 if status == "filled" else 0
        tick["entered_count"] += 1 if row.get("decision") == "entered" else 0
        tick["slot_sliced_count"] += 1 if row.get("decision") == "slot_sliced" else 0
        tick["windows"].add(row["window"])
        for horizon, values in (row.get("horizon") or {}).items():
            for target in (summary["horizon"][horizon], tick["horizon"][horizon]):
                long_pnl = float(values.get("long_pnl") or 0.0)
                short_pnl = float(values.get("inverse_short_pnl") or 0.0)
                long_ret = values.get("long_net_return_pct")
                short_ret = values.get("inverse_short_net_return_pct")
                target["fast_long_pnl"] += long_pnl
                target["inverse_short_pnl"] += short_pnl
                target["fast_long_positive_count"] += 1 if long_pnl > 0 else 0
                target["inverse_short_positive_count"] += 1 if short_pnl > 0 else 0
                if isinstance(long_ret, (int, float)):
                    target["_fast_returns"].append(long_ret)
                if isinstance(short_ret, (int, float)):
                    target["_short_returns"].append(short_ret)
    for row in summary["by_ticker"].values():
        row["windows"] = sorted(row["windows"])
        row["horizon"] = _finalize_horizon_summary(row["horizon"])
    summary["horizon"] = _finalize_horizon_summary(summary["horizon"])
    return summary


def _filter_records(records: list[dict[str, Any]], tickers: set[str]) -> list[dict[str, Any]]:
    return [row for row in records if row.get("ticker") in tickers]


def _identity_control(
    baseline_metrics: dict[str, dict[str, Any]],
    candidate_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    deltas = {
        label: base._delta(candidate_metrics[label], baseline_metrics[label])
        for label in baseline_metrics
    }
    nonzero = []
    for label, row in deltas.items():
        for key, value in row.items():
            if isinstance(value, (int, float)) and not math.isclose(value, 0.0, abs_tol=1e-9):
                nonzero.append({"window": label, "metric": key, "delta": value})
    return {"passed": not nonzero, "deltas": deltas, "nonzero_deltas": nonzero}


def _build_decision(
    primary_actual: dict[str, Any],
    primary_candidates: dict[str, Any],
    identity: dict[str, Any],
) -> dict[str, Any]:
    actual_windows = len(primary_actual["windows"])
    no_trade_by_window = primary_actual["by_window"]
    no_trade_positive_windows = [
        label
        for label, row in no_trade_by_window.items()
        if float(row.get("no_trade_avoided_pnl") or 0.0) > 0
    ]
    paper_tracking_passed = (
        identity["passed"]
        and primary_actual["trade_count"] >= MIN_PRIMARY_TRADES
        and actual_windows >= MIN_PRIMARY_WINDOWS
        and primary_actual["no_trade_avoided_pnl"] > 0
        and len(no_trade_positive_windows) >= MIN_PRIMARY_WINDOWS
    )
    inverse_actual_supported = (
        paper_tracking_passed
        and primary_actual["inverse_actual_exit_pnl"] > 0
        and primary_actual["inverse_actual_exit_positive_count"]
        >= max(2, primary_actual["trade_count"] // 2)
    )
    candidate_inverse_windows = len(primary_candidates["windows"])
    inverse_paper_only_supported = (
        inverse_actual_supported
        and candidate_inverse_windows >= MIN_PRIMARY_WINDOWS
        and any(
            row["inverse_short_pnl"] > 0
            for row in primary_candidates["horizon"].values()
        )
    )
    fast_long_supported = (
        paper_tracking_passed
        and any(
            row["fast_long_pnl"] > 0
            and row["fast_long_positive_count"] >= 2
            for row in primary_actual["horizon"].values()
        )
    )
    live_short_rejected_reason = (
        "inverse paper evidence is historical-only and lacks closed forward "
        f"paper outcomes >= {MIN_FORWARD_PAPER_CLOSED_TRADES_FOR_LIVE_SHORT}"
    )
    return {
        "paper_tracking_passed": paper_tracking_passed,
        "no_trade_positive_windows": no_trade_positive_windows,
        "inverse_actual_supported": inverse_actual_supported,
        "inverse_paper_only_supported": inverse_paper_only_supported,
        "fast_long_supported": fast_long_supported,
        "live_short_promotable": False,
        "live_short_rejected_reason": live_short_rejected_reason,
        "decision": (
            "accepted_default_off_core_misfit_paper_sleeve"
            if paper_tracking_passed
            else "rejected_no_paper_sleeve_edge"
        ),
        "interpretation": (
            "Treat the cohort as negative-for-core and track it in a default-off "
            "paper sleeve. Do not promote live shorts; use inverse outcomes only "
            "as a forward attribution surface."
            if paper_tracking_passed
            else "The cohort did not clear even the paper tracking gate."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    primary = payload["paper_surfaces"]["primary_misfit_actual"]
    candidate = payload["paper_surfaces"]["primary_misfit_candidates"]
    rows = [
        "| Ticker | Trades | Core PnL | No-trade value | Inverse actual-exit PnL | Windows |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for ticker, row in sorted(primary["by_ticker"].items()):
        rows.append(
            "| {ticker} | {trades} | ${pnl:,.2f} | ${avoid:,.2f} | ${inv:,.2f} | {windows} |".format(
                ticker=ticker,
                trades=row["trade_count"],
                pnl=row["actual_core_pnl"],
                avoid=row["no_trade_avoided_pnl"],
                inv=row["inverse_actual_exit_pnl"],
                windows=", ".join(row["windows"]),
            )
        )

    horizon_rows = [
        "| Horizon | Actual fast-long PnL | Actual inverse-short PnL | Candidate fast-long PnL | Candidate inverse-short PnL |",
        "|---|---:|---:|---:|---:|",
    ]
    for horizon in [str(value) for value in HORIZONS]:
        actual_h = primary["horizon"][horizon]
        candidate_h = candidate["horizon"][horizon]
        horizon_rows.append(
            "| {h}d | ${af:,.2f} | ${ai:,.2f} | ${cf:,.2f} | ${ci:,.2f} |".format(
                h=horizon,
                af=actual_h["fast_long_pnl"],
                ai=actual_h["inverse_short_pnl"],
                cf=candidate_h["fast_long_pnl"],
                ci=candidate_h["inverse_short_pnl"],
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Misfit Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Core replay metrics are intentionally unchanged. This experiment only copies real core misfit entries and entry-loop candidates into paper-only no-trade, fast-long, and inverse-short attribution surfaces.",
            "",
            *rows,
            "",
            *horizon_rows,
            "",
            f"Primary candidate events: {candidate['candidate_count']} total, {candidate['filled_count']} fillable, {candidate['entered_count']} entered, {candidate['slot_sliced_count']} slot-sliced.",
            "",
            "Production impact: replay-only/default-off paper tracking. No live shorting, no core exclusion, no entry/exit/ranking/sizing change.",
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
    log_path = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
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
        "decision": payload["decision"],
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

    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_runs = {
        label: base._run_window(label, variant=False) for label in base.WINDOWS
    }
    candidate_runs = {label: _run_window_with_candidates(label) for label in WINDOWS}
    baseline_metrics = {label: run["metrics"] for label, run in baseline_runs.items()}
    candidate_metrics = {label: run["metrics"] for label, run in candidate_runs.items()}
    identity = _identity_control(baseline_metrics, candidate_metrics)
    baseline_aggregate = base._aggregate(baseline_metrics)

    surfaces = _collect_surfaces(baseline_runs, candidate_runs)
    primary_tickers = set(PRIMARY_MISFIT_TICKERS)
    observed_negative_tickers = set(surfaces["negative_tickers"])
    primary_actual_records = _filter_records(
        surfaces["actual_trade_records"],
        primary_tickers,
    )
    primary_candidate_records = _filter_records(
        surfaces["paper_candidate_records"],
        primary_tickers,
    )
    observed_negative_actual_records = _filter_records(
        surfaces["actual_trade_records"],
        observed_negative_tickers,
    )
    observed_negative_candidate_records = _filter_records(
        surfaces["paper_candidate_records"],
        observed_negative_tickers,
    )

    primary_actual = _summarize_actual(primary_actual_records)
    primary_candidates = _summarize_candidates(primary_candidate_records)
    observed_negative_actual = _summarize_actual(observed_negative_actual_records)
    observed_negative_candidates = _summarize_candidates(
        observed_negative_candidate_records
    )
    decision = _build_decision(primary_actual, primary_candidates, identity)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision["decision"],
        "decision": decision["decision"],
        "hypothesis": (
            "Persistent ticker-level losers in the accepted core long stack may "
            "be negative-for-core signals. They should first be isolated into a "
            "default-off paper sleeve that measures no-trade value, fast-long "
            "rescue value, and inverse-short paper value without changing core."
        ),
        "change_type": "paper_sleeve_attribution",
        "changed_variable": "core_misfit_signal_paper_sleeve",
        "single_causal_variable": (
            "Only the observe-only paper attribution surface is added; core "
            "entry, exit, ranking, target, stop, sizing, heat, slots, LLM, and "
            "news behavior are locked."
        ),
        "parameters": {
            "primary_misfit_tickers": PRIMARY_MISFIT_TICKERS,
            "target_strategies": sorted(TARGET_STRATEGIES),
            "paper_decisions": sorted(PAPER_DECISIONS),
            "horizons_trading_days": HORIZONS,
            "minimum_primary_trades": MIN_PRIMARY_TRADES,
            "minimum_primary_windows": MIN_PRIMARY_WINDOWS,
            "minimum_forward_closed_paper_trades_for_live_short": (
                MIN_FORWARD_PAPER_CLOSED_TRADES_FOR_LIVE_SHORT
            ),
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "slippage_bps": {
                "entry": SLIPPAGE_BPS_ENTRY,
                "target_exit": SLIPPAGE_BPS_TARGET,
                "short_cover": SLIPPAGE_BPS_STOP,
            },
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all production sizing multipliers",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "live order generation",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool/risk allocation: misfit ticker core long "
                "signals may be useful as default-off negative-for-core paper "
                "signals, not automatically as live shorts."
            ),
            "2_history_check": {
                "exp-20260516-039": (
                    "TSM passed only a 0.25x core risk scalar; 0.0x failed and "
                    "fast-target rescue was unsupported."
                ),
                "exp-20260516-042": (
                    "ISRG passed only a 0.25x core risk scalar; 0.0x failed "
                    "and fast-target rescue was unsupported."
                ),
                "exp-20260516-041": (
                    "V/DDOG zero-risk variants improved only old_thin and "
                    "remained watch-only."
                ),
            },
            "3_single_causal_variable": "core_misfit_signal_paper_sleeve",
            "4_acceptance_standard": (
                "Baseline and candidate-event replay metrics must be identical; "
                "paper tracking requires positive no-trade avoided value on "
                f">={MIN_PRIMARY_TRADES} primary trades across >={MIN_PRIMARY_WINDOWS} "
                "windows. Live shorting is rejected until closed forward paper "
                "outcomes mature."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_043_core_misfit_paper_sleeve.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "include_entry_candidate_events": True,
            },
        },
        "gate1": {
            "baseline_metrics": baseline_metrics,
            "baseline_aggregate": baseline_aggregate,
            "baseline_artifact": (
                "data/experiments/exp-20260516-042/isrg_core_adaptation.json"
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "BacktestEngine trades entry_open_price",
                "BacktestEngine trades exit_raw_price",
                "entry_candidate_events signal_snapshot",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": baseline_aggregate["survival_rate_min"],
            "passed": baseline_aggregate["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": decision["paper_tracking_passed"],
            "core_metrics_unchanged": identity["passed"],
            "identity_control": identity,
            "primary_trade_count": primary_actual["trade_count"],
            "primary_window_count": len(primary_actual["windows"]),
            "primary_no_trade_avoided_pnl": primary_actual["no_trade_avoided_pnl"],
            "inverse_paper_only_supported": decision["inverse_paper_only_supported"],
            "fast_long_supported": decision["fast_long_supported"],
            "live_short_promotable": decision["live_short_promotable"],
            "live_short_rejected_reason": decision["live_short_rejected_reason"],
        },
        "before_metrics": baseline_metrics,
        "after_metrics": candidate_metrics,
        "delta_metrics": {
            "identity_control": identity,
            "aggregate_before": baseline_aggregate,
            "aggregate_after": base._aggregate(candidate_metrics),
            "aggregate_delta": base._aggregate_delta(
                base._aggregate(candidate_metrics),
                baseline_aggregate,
            ),
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "baseline_ticker_audit": surfaces["baseline_ticker_audit"],
        "negative_tickers": surfaces["negative_tickers"],
        "paper_surfaces": {
            "primary_misfit_actual": primary_actual,
            "primary_misfit_candidates": primary_candidates,
            "observed_negative_actual": observed_negative_actual,
            "observed_negative_candidates": observed_negative_candidates,
            "actual_trade_records": surfaces["actual_trade_records"],
            "paper_candidate_records": surfaces["paper_candidate_records"],
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "No LLM behavior changed; the sleeve uses deterministic replay "
                "events and OHLCV fills."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "promotion_requirement": (
                "A production-visible paper ledger can be added only as "
                "observe-only tracking. Live shorting or core exclusion requires "
                "a separate shared adapter, forward paper outcomes, and a new "
                "Gate 1-4 experiment."
            ),
        },
        "why_not_other_changes": (
            "Direct core exclusion and live inverse trading were not promoted "
            "because prior TSM/ISRG 0.0x variants failed and historical negative "
            "long contribution is not automatically short alpha."
        ),
        "known_risks": [
            "Ticker-level negative evidence is sample-thin and can overfit.",
            "Inverse paper returns ignore borrow availability and short locate costs.",
            "Candidate-event paper outcomes include slot-sliced signals that did not compete for core capital in the accepted stack.",
        ],
        "interpretation": decision["interpretation"],
        "rejection_reason": (
            None
            if decision["paper_tracking_passed"]
            else "No-trade avoided value did not pass the paper tracking gate."
        ),
        "next_evidence_needed": (
            "Add a production-visible default-off paper ledger for this sleeve, "
            "collect closed forward no-trade/inverse outcomes, and only then "
            "test live core exclusion or short-side execution as separate "
            "single-variable experiments."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_043_core_misfit_paper_sleeve.py",
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
                "core_metrics_unchanged": result["gate4"]["core_metrics_unchanged"],
                "primary_trade_count": result["gate4"]["primary_trade_count"],
                "primary_no_trade_avoided_pnl": result["gate4"][
                    "primary_no_trade_avoided_pnl"
                ],
                "inverse_paper_only_supported": result["gate4"][
                    "inverse_paper_only_supported"
                ],
                "fast_long_supported": result["gate4"]["fast_long_supported"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
