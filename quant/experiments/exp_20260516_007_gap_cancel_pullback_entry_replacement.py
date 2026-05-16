"""exp-20260516-007: high-quality gap-cancel pullback replacement value.

This replay-only scout tests one causal variable: whether already-qualified
signals that were skipped only because the next open exceeded the upside gap
cancel threshold have positive replacement value when the system waits up to
three sessions for an open back inside the valid gap band.

No production behavior is changed here. A passing result would require a
shared execution policy used by both run.py and backtester.py before promotion.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260516-007"
EXPERIMENT_SLUG = "gap_cancel_pullback_entry_replacement"

MIN_TRADE_QUALITY_SCORE = 0.95
MAX_CANDIDATE_RANK = 1
PULLBACK_ENTRY_DAYS = 3
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_REPLACEMENT_TRADES = 3
MIN_REPLACEMENT_WINDOWS = 2
MAX_SINGLE_POSITIVE_PNL_SHARE = 0.65

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import exp_20260512_106_signal_day_sector_tape_risk as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import (  # noqa: E402
    SLIPPAGE_BPS_TARGET,
    apply_entry_fill,
    apply_slippage,
    apply_stop_fill,
    apply_target_fill,
)
from portfolio_engine import ROUND_TRIP_COST_PCT  # noqa: E402


def _dt(value: str):
    import pandas as pd

    return pd.Timestamp(value)


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _round(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, 6)
    return value


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _run_baseline_window(label: str) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    spec = base.WINDOWS[label]
    universe = [str(t).upper() for t in get_universe()]
    config = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config=config,
        ohlcv_snapshot_path=spec["snapshot"],
        include_pilot_sleeve=False,
        include_entry_candidate_events=True,
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{label} baseline failed: {result['error']}")
    ohlcv = engine._download_data()
    spy = ohlcv.get("SPY")
    if spy is None or spy.empty:
        raise RuntimeError(f"{label} missing SPY snapshot data")
    all_dates = [d for d in sorted(spy.index) if _dt(spec["start"]) <= d <= _dt(spec["end"])]
    return result, ohlcv, all_dates


def _baseline_overlap_intervals(trades: list[dict[str, Any]]) -> dict[str, list[tuple[Any, Any]]]:
    intervals: dict[str, list[tuple[Any, Any]]] = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        entry = trade.get("entry_date")
        exit_ = trade.get("exit_date")
        if not ticker or not entry or not exit_:
            continue
        intervals.setdefault(ticker, []).append((_dt(str(entry)), _dt(str(exit_))))
    return intervals


def _overlaps_baseline(
    intervals: dict[str, list[tuple[Any, Any]]],
    ticker: str,
    entry_date: Any,
    exit_date: Any | None = None,
) -> bool:
    end = exit_date or entry_date
    for start, finish in intervals.get(ticker, []):
        if start <= end and entry_date <= finish:
            return True
    return False


def _candidate_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for event in result.get("entry_candidate_events") or []:
        if event.get("decision") != "gap_cancel":
            continue
        snap = event.get("signal_snapshot") or {}
        tqs = snap.get("trade_quality_score")
        rank = event.get("candidate_rank")
        details = event.get("details") or {}
        if not isinstance(rank, int) or rank > MAX_CANDIDATE_RANK:
            continue
        if not _finite(tqs) or float(tqs) < MIN_TRADE_QUALITY_SCORE:
            continue
        if not details.get("fill_date"):
            continue
        sizing = snap.get("sizing") or {}
        if int(sizing.get("shares_to_buy") or 0) <= 0:
            continue
        if not (_finite(snap.get("entry_price")) and _finite(snap.get("stop_price"))):
            continue
        if not _finite(snap.get("target_price")):
            continue
        out.append(event)
    return out


def _simulate_pullback_trade(
    event: dict[str, Any],
    ohlcv: dict[str, Any],
    all_dates: list[Any],
    baseline_intervals: dict[str, list[tuple[Any, Any]]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    ticker = str(event.get("ticker") or "").upper()
    df = ohlcv.get(ticker)
    snap = event.get("signal_snapshot") or {}
    sizing = snap.get("sizing") or {}
    details = event.get("details") or {}
    if df is None or df.empty:
        return None, {"reason": "missing_ohlcv"}

    signal_entry = float(details.get("signal_entry") or snap.get("entry_price"))
    cancel_gap_pct = float(details.get("cancel_gap_pct") or 0.015)
    pullback_limit = signal_entry * (1.0 + cancel_gap_pct)
    cancel_fill_date = _dt(str(details["fill_date"]))
    stop_price = float(snap["stop_price"])
    target_price = float(snap["target_price"])
    shares = int(sizing.get("shares_to_buy") or 0)

    eligible_dates = [d for d in all_dates if d > cancel_fill_date]
    entry_date = None
    raw_entry_open = None
    for day in eligible_dates[:PULLBACK_ENTRY_DAYS]:
        if day not in df.index:
            continue
        row = df.loc[day]
        raw_open = float(row["Open"].item() if hasattr(row["Open"], "item") else row["Open"])
        if raw_open <= pullback_limit and raw_open > stop_price:
            entry_date = day
            raw_entry_open = raw_open
            break

    if entry_date is None or raw_entry_open is None:
        return None, {
            "reason": "no_pullback_open_within_window",
            "pullback_limit": round(pullback_limit, 4),
        }

    if _overlaps_baseline(baseline_intervals, ticker, entry_date):
        return None, {
            "reason": "baseline_same_ticker_overlap",
            "entry_date": str(entry_date.date()),
        }

    entry_price = round(apply_entry_fill(raw_entry_open), 2)
    exit_date = None
    exit_raw_price = None
    exit_price = None
    exit_reason = None
    for day in [d for d in all_dates if d > entry_date]:
        if day not in df.index:
            continue
        row = df.loc[day]
        opn = float(row["Open"].item() if hasattr(row["Open"], "item") else row["Open"])
        low = float(row["Low"].item() if hasattr(row["Low"], "item") else row["Low"])
        high = float(row["High"].item() if hasattr(row["High"], "item") else row["High"])
        if low <= stop_price:
            exit_raw_price = opn if opn < stop_price else stop_price
            exit_price = apply_stop_fill(opn, stop_price)
            exit_reason = "stop"
            exit_date = day
            break
        if high >= target_price:
            exit_raw_price = opn if opn >= target_price else target_price
            exit_price = apply_target_fill(opn, target_price)
            exit_reason = "target"
            exit_date = day
            break

    if exit_date is None:
        last_day = all_dates[-1]
        row = df.loc[last_day]
        raw_close = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
        exit_raw_price = raw_close
        exit_price = apply_slippage(raw_close, SLIPPAGE_BPS_TARGET, "sell")
        exit_reason = "end_of_backtest"
        exit_date = last_day

    if _overlaps_baseline(baseline_intervals, ticker, entry_date, exit_date):
        return None, {
            "reason": "baseline_same_ticker_overlap",
            "entry_date": str(entry_date.date()),
            "exit_date": str(exit_date.date()),
        }

    cost = exit_price * ROUND_TRIP_COST_PCT * shares
    pnl = (exit_price - entry_price) * shares - cost
    entry_slip = (entry_price - raw_entry_open) * shares
    exit_slip = (exit_raw_price - exit_price) * shares
    pnl_pct_net = ((exit_price - entry_price) / entry_price) - ROUND_TRIP_COST_PCT
    initial_risk_pct = (entry_price - stop_price) / entry_price if entry_price else None

    trade = {
        "trade_key": f"{ticker}:{entry_date.date()}:{entry_price:.4f}:gap_pullback",
        "ticker": ticker,
        "strategy": event.get("strategy", "unknown"),
        "sector": snap.get("sector", "Unknown"),
        "entry_price": entry_price,
        "entry_open_price": round(raw_entry_open, 4),
        "stop_price": round(stop_price, 4),
        "target_price": round(target_price, 4),
        "exit_price": round(exit_price, 2),
        "exit_raw_price": round(exit_raw_price, 4),
        "shares": shares,
        "pnl": round(pnl, 2),
        "pnl_pct_net": round(pnl_pct_net, 6),
        "initial_risk_pct": round(initial_risk_pct, 6) if initial_risk_pct else None,
        "slippage_cost": round(entry_slip + exit_slip, 2),
        "target_mult_used": snap.get("target_mult_used"),
        "regime_exit_bucket": snap.get("regime_exit_bucket"),
        "regime_exit_score": snap.get("regime_exit_score"),
        "sizing_multipliers": dict((sizing.get("risk_multipliers") or {})),
        "base_risk_pct": sizing.get("base_risk_pct"),
        "actual_risk_pct": sizing.get("risk_pct"),
        "addon_count": 0,
        "addon_shares": 0,
        "addon_cost": 0.0,
        "exit_reason": exit_reason,
        "entry_date": str(entry_date.date()),
        "exit_date": str(exit_date.date()),
        "replacement_origin": "gap_cancel_pullback_entry",
        "origin_signal_date": event.get("date"),
        "origin_cancel_fill_date": str(cancel_fill_date.date()),
        "origin_signal_entry": round(signal_entry, 4),
        "pullback_limit": round(pullback_limit, 4),
        "origin_candidate_rank": event.get("candidate_rank"),
        "origin_trade_quality_score": snap.get("trade_quality_score"),
    }
    return trade, {"reason": "entered", "trade_key": trade["trade_key"]}


def _overlay_pnl_by_date(
    trades: list[dict[str, Any]],
    ohlcv: dict[str, Any],
    all_dates: list[Any],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for day in all_dates:
        pnl = 0.0
        for trade in trades:
            ticker = str(trade["ticker"]).upper()
            entry_date = _dt(trade["entry_date"])
            exit_date = _dt(trade["exit_date"])
            if day < entry_date:
                continue
            if day >= exit_date:
                pnl += float(trade["pnl"])
                continue
            df = ohlcv.get(ticker)
            if df is not None and day in df.index:
                row = df.loc[day]
                close = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
                pnl += (close - float(trade["entry_price"])) * int(trade["shares"])
        out[str(day.date())] = round(pnl, 2)
    return out


def _max_drawdown(equity_curve: list[tuple[str, float]]) -> float:
    peak = 0.0
    max_dd = 0.0
    for _, equity in equity_curve:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return round(max_dd, 4)


def _sharpe_daily(equity_curve: list[tuple[str, float]]) -> float | None:
    if len(equity_curve) < 3:
        return None
    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1][1]
        cur = equity_curve[i][1]
        if prev > 0:
            returns.append((cur / prev) - 1.0)
    if len(returns) < 2:
        return None
    mean_r = sum(returns) / len(returns)
    var_r = sum((x - mean_r) ** 2 for x in returns) / (len(returns) - 1)
    std_r = math.sqrt(var_r) if var_r > 0 else 0.0
    return round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else None


def _trade_risk_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda t: (str(t.get("exit_date") or ""), str(t.get("ticker") or "")))
    pnl_pct_series = [
        float(t["pnl_pct_net"])
        for t in ordered
        if _finite(t.get("pnl_pct_net"))
    ]
    worst_trade_pct = round(min(pnl_pct_series), 6) if pnl_pct_series else None
    max_consecutive_losses = 0
    streak = 0
    for trade in ordered:
        if _finite(trade.get("pnl_pct_net")) and float(trade["pnl_pct_net"]) < 0:
            streak += 1
            max_consecutive_losses = max(max_consecutive_losses, streak)
        else:
            streak = 0
    losses_abs = sorted(
        [-float(t["pnl"]) for t in ordered if _finite(t.get("pnl")) and float(t["pnl"]) < 0],
        reverse=True,
    )
    if losses_abs:
        tail_count = max(1, math.ceil(len(losses_abs) * 0.2))
        tail_loss_share = round(sum(losses_abs[:tail_count]) / sum(losses_abs), 4)
    else:
        tail_loss_share = None
    return {
        "worst_trade_pct": worst_trade_pct,
        "max_consecutive_losses": max_consecutive_losses,
        "tail_loss_share": tail_loss_share,
    }


def _combined_metrics(
    baseline: dict[str, Any],
    replacement_trades: list[dict[str, Any]],
    ohlcv: dict[str, Any],
    all_dates: list[Any],
) -> dict[str, Any]:
    overlay = _overlay_pnl_by_date(replacement_trades, ohlcv, all_dates)
    combined_equity = []
    for date, equity in baseline.get("equity_curve") or []:
        combined_equity.append((date, round(float(equity) + overlay.get(date, 0.0), 2)))

    trades = list(baseline.get("trades") or []) + replacement_trades
    total = len(trades)
    wins = [t for t in trades if float(t.get("pnl") or 0.0) > 0]
    losses = [t for t in trades if float(t.get("pnl") or 0.0) <= 0]
    total_pnl = round(sum(float(t.get("pnl") or 0.0) for t in trades), 2)
    sharpe = _sharpe_daily(combined_equity)
    total_return_pct = round(total_pnl / 100000.0, 4)
    risk = _trade_risk_metrics(trades)
    return {
        "expected_value_score": (
            round(total_return_pct * sharpe, 4) if sharpe is not None else None
        ),
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "sharpe_daily": sharpe,
        "max_drawdown_pct": _max_drawdown(combined_equity),
        "win_rate": round(len(wins) / total, 4) if total else 0.0,
        "trade_count": total,
        "signals_generated": baseline.get("signals_generated"),
        "signals_survived": baseline.get("signals_survived"),
        "survival_rate": baseline.get("survival_rate"),
        "wins": len(wins),
        "losses": len(losses),
        **risk,
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = set(after) | set(before)
    out: dict[str, Any] = {}
    for key in keys:
        if isinstance(after.get(key), (int, float)) and isinstance(before.get(key), (int, float)):
            out[key] = _round(after[key] - before[key])
    return out


def _aggregate(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            6,
        ),
        "total_pnl_sum": round(sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()), 2),
        "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in metrics.values())),
        "signals_generated_sum": int(
            sum(int(row.get("signals_generated") or 0) for row in metrics.values())
        ),
        "signals_survived_sum": int(
            sum(int(row.get("signals_survived") or 0) for row in metrics.values())
        ),
        "max_drawdown_pct_max": round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            6,
        ),
        "survival_rate_min": round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            6,
        ),
    }


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in after.items():
        if isinstance(value, (int, float)) and isinstance(before.get(key), (int, float)):
            out[key] = _round(value - before[key])
    return out


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_SLUG}",
        "",
        f"- decision: `{payload['decision']}`",
        f"- hypothesis: {payload['hypothesis']}",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- replacement_trades: `{payload['selection']['replacement_trade_count']}`",
        f"- aggregate_ev_delta: `{payload['delta_metrics']['aggregate']['expected_value_score_sum']}`",
        f"- aggregate_pnl_delta: `${payload['delta_metrics']['aggregate']['total_pnl_sum']:,.2f}`",
        "",
        "## Three-Window Metrics",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | After DD | Repl Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:.4f} | {count} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=after["max_drawdown_pct"],
                count=payload["replacement_attribution"][label]["trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Replay-only paper scout. No shared policy, backtester adapter, or run adapter was changed.",
            "",
            "```text",
            "production_impact:",
            "  shared_policy_changed: false",
            "  backtester_adapter_changed: false",
            "  run_adapter_changed: false",
            "  replay_only: true",
            "  parity_test_added: false",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    by_window_delta: dict[str, dict[str, Any]] = {}
    replacement_attribution: dict[str, dict[str, Any]] = {}
    skipped_attribution: dict[str, Any] = {}

    for label in base.WINDOWS:
        baseline, ohlcv, all_dates = _run_baseline_window(label)
        before_metrics[label] = base._metrics(baseline)
        intervals = _baseline_overlap_intervals(baseline.get("trades") or [])
        candidates = _candidate_events(baseline)
        replacements = []
        skipped = []
        for event in candidates:
            trade, status = _simulate_pullback_trade(event, ohlcv, all_dates, intervals)
            record = {
                "date": event.get("date"),
                "ticker": event.get("ticker"),
                "strategy": event.get("strategy"),
                "decision": event.get("decision"),
                "candidate_rank": event.get("candidate_rank"),
                "status": status,
            }
            if trade is None:
                skipped.append(record)
            else:
                replacements.append(trade)
                intervals.setdefault(str(trade["ticker"]).upper(), []).append(
                    (_dt(trade["entry_date"]), _dt(trade["exit_date"]))
                )
        after_metrics[label] = _combined_metrics(baseline, replacements, ohlcv, all_dates)
        by_window_delta[label] = _delta(after_metrics[label], before_metrics[label])
        wins = [t for t in replacements if float(t.get("pnl") or 0.0) > 0]
        losses = [t for t in replacements if float(t.get("pnl") or 0.0) <= 0]
        replacement_attribution[label] = {
            "candidate_count": len(candidates),
            "trade_count": len(replacements),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(replacements), 4) if replacements else 0.0,
            "total_pnl": round(sum(float(t.get("pnl") or 0.0) for t in replacements), 2),
            "tickers": sorted({str(t.get("ticker") or "").upper() for t in replacements}),
            "trades": replacements,
        }
        skipped_attribution[label] = {
            "skipped_count": len(skipped),
            "skipped": skipped,
        }

    aggregate_before = _aggregate(before_metrics)
    aggregate_after = _aggregate(after_metrics)
    aggregate_delta = _aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    ]
    replacement_trades = [
        trade
        for row in replacement_attribution.values()
        for trade in row["trades"]
    ]
    positive_pnls = [float(t["pnl"]) for t in replacement_trades if float(t.get("pnl") or 0.0) > 0]
    total_positive_pnl = sum(positive_pnls)
    max_single_positive_share = (
        round(max(positive_pnls) / total_positive_pnl, 4)
        if positive_pnls and total_positive_pnl > 0
        else None
    )
    replacement_windows = [
        label
        for label, row in replacement_attribution.items()
        if int(row["trade_count"]) > 0
    ]
    max_drawdown_worse = max(
        after_metrics[label]["max_drawdown_pct"] - before_metrics[label]["max_drawdown_pct"]
        for label in base.WINDOWS
    )
    sample_guard_passed = (
        len(replacement_trades) >= MIN_REPLACEMENT_TRADES
        and len(replacement_windows) >= MIN_REPLACEMENT_WINDOWS
        and (
            max_single_positive_share is None
            or max_single_positive_share <= MAX_SINGLE_POSITIVE_PNL_SHARE
        )
    )
    gate4 = {
        "passed": bool(
            aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(improved) >= 2
            and not regressed
            and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
            and aggregate_after["survival_rate_min"] >= 0.05
            and len(replacement_trades) > 0
            and sample_guard_passed
        ),
        "reasons": {
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0,
            "at_least_two_windows_improved": len(improved) >= 2,
            "no_window_regressed": not regressed,
            "drawdown_delta_within_limit": max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "survival_rate_ok": aggregate_after["survival_rate_min"] >= 0.05,
            "replacement_trades_present": len(replacement_trades) > 0,
            "sample_guard_passed": sample_guard_passed,
        },
        "improved_windows": improved,
        "regressed_windows": regressed,
        "max_drawdown_worse": round(max_drawdown_worse, 6),
        "sample_guard": {
            "min_replacement_trades": MIN_REPLACEMENT_TRADES,
            "actual_replacement_trades": len(replacement_trades),
            "min_replacement_windows": MIN_REPLACEMENT_WINDOWS,
            "actual_replacement_windows": len(replacement_windows),
            "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE,
            "actual_max_single_positive_pnl_share": max_single_positive_share,
        },
    }

    decision = (
        "promising_replay_only_gap_cancel_pullback_entry"
        if gate4["passed"]
        else "rejected_gap_cancel_pullback_entry"
    )
    rejection_reason = None
    if not gate4["passed"]:
        rejection_reason = (
            "Gate 4 failed for the delayed pullback entry replacement-value scout; "
            "see gate4.reasons and replacement_attribution."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_slug": EXPERIMENT_SLUG,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Some high-quality core candidates currently have zero contribution only because the next open breaches the upside gap-cancel threshold. "
            "Keeping only those already-qualified rank-1/TQS>=0.95 gap-canceled candidates on a three-session pullback watch may add positive replacement value without changing the raw candidate pool."
        ),
        "alpha_hypothesis_category": "entry_execution_replacement_value",
        "change_type": "entry_execution_replay_scout",
        "changed_variable": "gap_cancel_pullback_entry_enabled",
        "single_causal_variable": (
            "Enable a replay-only delayed pullback entry for rank-1 TQS>=0.95 upside gap-canceled candidates; all signals, ranking, sizing, stops, targets, and exits remain fixed."
        ),
        "parameters": {
            "min_trade_quality_score": MIN_TRADE_QUALITY_SCORE,
            "max_candidate_rank": MAX_CANDIDATE_RANK,
            "pullback_entry_days": PULLBACK_ENTRY_DAYS,
            "entry_trigger": (
                "first post-cancel open within the next 3 trading days that is <= signal_entry * (1 + cancel_gap_pct) and > stop_price"
            ),
            "shares_stop_target_source": "original sized signal snapshot from entry_candidate_events",
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "sample_guard": {
                "min_replacement_trades": MIN_REPLACEMENT_TRADES,
                "min_replacement_windows": MIN_REPLACEMENT_WINDOWS,
                "max_single_positive_pnl_share": MAX_SINGLE_POSITIVE_PNL_SHARE,
            },
            "locked_variables": [
                "core universe",
                "signal generation",
                "candidate ranking",
                "original position sizing",
                "stops and targets",
                "exit model",
                "LLM/news replay",
                "portfolio heat",
                "accepted core sizing stack",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "recent_gap_or_exec_related": [
                "exp-20260515-038 rejected broad exec-lag R:R allocation because old_thin regressed.",
                "exp-20260515-039 tested breakout-only exec-lag R:R allocation rather than gap-cancel replacement.",
                "Recent green momentum / gap-vulnerability branches were allocation or state scouts, not delayed execution replacement-value tests for canceled candidates.",
            ],
            "why_this_is_not_a_nearby_retry": (
                "This experiment does not change gap thresholds, R:R scalars, ranking, or filters. It evaluates a missing execution path for already-qualified candidates with observed gap-cancel decisions."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry: high-quality rank-1 gap-canceled core signals may still work if entered only after the open returns to the original acceptable gap band."
            ),
            "2_prior_similar_experiments": (
                "No direct delayed pullback entry replacement-value scout was found. Nearby exec-lag/R:R and gap-state allocation scouts did not test canceled-candidate conversion."
            ),
            "3_single_causal_variable": "gap_cancel_pullback_entry_enabled",
            "4_success_criteria": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, zero EV-regressed windows, max drawdown drift <= 0.5 pp, survival >= 5%, and sample guard pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260516_007_gap_cancel_pullback_entry_replacement.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "baseline": "current accepted core stack through exp-20260515-028",
            "after": "baseline metrics plus replay-only delayed-entry replacement trades using the same OHLCV snapshots",
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "computed in-memory from canonical snapshots",
            "known_biases": [
                "news_veto archive remains disclosed by canonical backtester",
                "delayed entry is replay-only until shared execution policy exists",
            ],
        },
        "gate2": gate2,
        "gate3": {
            "survival_rate_min_before": aggregate_before["survival_rate_min"],
            "survival_rate_min_after": aggregate_after["survival_rate_min"],
            "filter_added": False,
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate": aggregate_delta,
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "replacement_attribution": replacement_attribution,
        "skipped_attribution": skipped_attribution,
        "selection": {
            "candidate_count": sum(row["candidate_count"] for row in replacement_attribution.values()),
            "replacement_trade_count": len(replacement_trades),
            "replacement_windows": replacement_windows,
            "replacement_tickers": sorted({str(t.get("ticker") or "").upper() for t in replacement_trades}),
            "replacement_total_pnl": round(sum(float(t.get("pnl") or 0.0) for t in replacement_trades), 2),
            "max_single_positive_pnl_share": max_single_positive_share,
        },
        "risk_distribution": {
            "before": {
                label: {
                    "worst_trade_pct": before_metrics[label].get("worst_trade_pct"),
                    "max_consecutive_losses": before_metrics[label].get("max_consecutive_losses"),
                    "tail_loss_share": before_metrics[label].get("tail_loss_share"),
                }
                for label in base.WINDOWS
            },
            "after": {
                label: {
                    "worst_trade_pct": after_metrics[label].get("worst_trade_pct"),
                    "max_consecutive_losses": after_metrics[label].get("max_consecutive_losses"),
                    "tail_loss_share": after_metrics[label].get("tail_loss_share"),
                }
                for label in base.WINDOWS
            },
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": "LLM soft-ranking is not needed; this run uses deterministic entry decision logs.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "promotion_blocker_if_positive": (
                "Implement a shared gap-cancel watch/re-entry execution policy used by production and backtester, plus parity tests, before any live behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Ticker deletion, LLM soft-ranking, broad universe expansion, and nearby R:R/cap scalars either lose information or repeat recent weak branches. This tests the concrete no-contribution surface found in reverse attribution."
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, inspect whether gap-canceled names need intraday limit-fill modeling or should remain discarded. If promising, implement a shared production/backtest gap-cancel watch policy and rerun Gate 1-4."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }

    data_path = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    artifact_path = (
        REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )

    _write_json(data_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "decision": decision,
            "hypothesis": payload["hypothesis"],
            "changed_variable": payload["changed_variable"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "gate4_passed": gate4["passed"],
            "replacement_trade_count": len(replacement_trades),
            "next_action": payload["next_evidence_needed"],
        },
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_markdown(payload), encoding="utf-8")
    _upsert_jsonl(REPO_ROOT / "docs" / "experiment_log.jsonl", payload)

    print(json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True))
    return payload


if __name__ == "__main__":
    run()
