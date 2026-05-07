"""Shadow replay for event-leader profit-ladder exits.

This experiment does not alter production or canonical backtest behavior.  It
keeps accepted core entries, sizing, ordering, and add-ons fixed, then replaces
only the exit path for already-entered trades that satisfy an event-leader proxy:

* the trade used the accepted SPY-relative leader sizing multiplier; and
* the entry occurred within three trading days of a price/volume re-rating event.

The proxy is intentionally auditable from OHLCV snapshots because historical
LLM/news semantic coverage is still sparse in the canonical windows.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ATR_STOP_MULT, ROUND_TRIP_COST_PCT  # noqa: E402
from fill_model import apply_slippage, SLIPPAGE_BPS_STOP, SLIPPAGE_BPS_TARGET  # noqa: E402


EXPERIMENT_ID = "exp-20260506-010"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "baseline": "data/experiments/exp-20260505-025/baseline_late_strong.json",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "baseline": "data/experiments/exp-20260505-025/baseline_mid_weak.json",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "baseline": "data/experiments/exp-20260505-025/baseline_old_thin.json",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

EVENT_LOOKBACK_DAYS = 3
EVENT_MIN_ABS_MOVE = 0.04
EVENT_MIN_VOLUME_RATIO = 1.30

VARIANTS = OrderedDict(
    [
        (
            "profit_floor_1r_0_25r",
            {
                "profit_floor_trigger_r": 1.0,
                "profit_floor_r": 0.25,
                "target_partial_fraction": 0.0,
                "trail_after_target_r": None,
            },
        ),
        (
            "target_half_trail_1_5r",
            {
                "profit_floor_trigger_r": None,
                "profit_floor_r": None,
                "target_partial_fraction": 0.50,
                "trail_after_target_r": 1.5,
            },
        ),
        (
            "profit_floor_plus_target_half_trail",
            {
                "profit_floor_trigger_r": 1.0,
                "profit_floor_r": 0.25,
                "target_partial_fraction": 0.50,
                "trail_after_target_r": 1.5,
            },
        ),
    ]
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "date": str(row.get("Date") or row.get("date"))[:10],
                    "open": float(row.get("Open") or row.get("open") or 0.0),
                    "high": float(row.get("High") or row.get("high") or 0.0),
                    "low": float(row.get("Low") or row.get("low") or 0.0),
                    "close": float(row.get("Close") or row.get("close") or 0.0),
                    "volume": float(row.get("Volume") or row.get("volume") or 0.0),
                }
            )
        out[str(ticker).upper()] = sorted(normalized, key=lambda item: item["date"])
    return out


def _row_index(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] == date_value:
            return idx
    return None


def _rows_from_entry(
    rows: list[dict[str, Any]],
    entry_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if entry_date <= row["date"] <= end_date
    ]


def _leader_trade(trade: dict[str, Any]) -> bool:
    multipliers = trade.get("sizing_multipliers") or {}
    return multipliers.get("spy_relative_leader_risk_on_multiplier_applied") is not None


def _event_repricing_proxy(
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    entry_idx = _row_index(rows, str(trade.get("entry_date") or "")[:10])
    if entry_idx is None or entry_idx <= 0:
        return {"qualified": False, "reason": "entry_row_missing"}

    best: dict[str, Any] | None = None
    start_idx = max(1, entry_idx - EVENT_LOOKBACK_DAYS)
    for idx in range(start_idx, entry_idx + 1):
        row = rows[idx]
        prev = rows[idx - 1]
        prev_close = prev["close"]
        if prev_close <= 0:
            continue
        close_return = row["close"] / prev_close - 1.0
        open_gap = row["open"] / prev_close - 1.0
        abs_move = max(abs(close_return), abs(open_gap))
        vol_window = rows[max(0, idx - 20):idx]
        avg_volume = (
            statistics.mean(item["volume"] for item in vol_window)
            if vol_window else 0.0
        )
        volume_ratio = row["volume"] / avg_volume if avg_volume > 0 else 0.0
        candidate = {
            "event_date": row["date"],
            "abs_move": abs_move,
            "close_return": close_return,
            "open_gap": open_gap,
            "volume_ratio": volume_ratio,
        }
        if best is None or (
            candidate["abs_move"],
            candidate["volume_ratio"],
        ) > (
            best["abs_move"],
            best["volume_ratio"],
        ):
            best = candidate

    if best is None:
        return {"qualified": False, "reason": "no_prior_price_event"}

    qualified = (
        best["abs_move"] >= EVENT_MIN_ABS_MOVE
        and best["volume_ratio"] >= EVENT_MIN_VOLUME_RATIO
    )
    return {
        **best,
        "qualified": qualified,
        "min_abs_move": EVENT_MIN_ABS_MOVE,
        "min_volume_ratio": EVENT_MIN_VOLUME_RATIO,
    }


def _qualifies(trade: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    event = _event_repricing_proxy(trade, rows)
    leader = _leader_trade(trade)
    return bool(leader and event.get("qualified")), {
        "spy_relative_leader": leader,
        "event_repricing_proxy": event,
    }


def _risk_per_share(trade: dict[str, Any]) -> float | None:
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    if not isinstance(entry, (int, float)) or not isinstance(stop, (int, float)):
        return None
    risk = float(entry) - float(stop)
    return risk if risk > 0 else None


def _sell_pnl(entry_price: float, exit_price: float, shares: int) -> float:
    cost = exit_price * ROUND_TRIP_COST_PCT * shares
    return (exit_price - entry_price) * shares - cost


def _stop_fill(raw_open: float, stop_price: float) -> tuple[float, float]:
    raw = raw_open if raw_open < stop_price else stop_price
    return apply_slippage(raw, SLIPPAGE_BPS_STOP, "sell"), raw


def _target_fill(raw_open: float, target_price: float) -> tuple[float, float]:
    raw = raw_open if raw_open >= target_price else target_price
    return apply_slippage(raw, SLIPPAGE_BPS_TARGET, "sell"), raw


def _mark_fill(raw_close: float) -> tuple[float, float]:
    return apply_slippage(raw_close, SLIPPAGE_BPS_TARGET, "sell"), raw_close


def _simulate_variant_trade(
    trade: dict[str, Any],
    rows: list[dict[str, Any]],
    end_date: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    entry_date = str(trade.get("entry_date") or "")[:10]
    entry_price = float(trade.get("entry_price") or 0.0)
    stop_price = float(trade.get("stop_price") or 0.0)
    shares = int(trade.get("shares") or 0)
    risk = _risk_per_share(trade)
    if entry_price <= 0 or stop_price <= 0 or shares <= 0 or risk is None:
        return {
            **trade,
            "pnl": float(trade.get("pnl") or 0.0),
            "variant_exit_reason": "not_simulated_missing_trade_fields",
        }

    active_rows = _rows_from_entry(rows, entry_date, end_date)
    if not active_rows:
        return {
            **trade,
            "pnl": float(trade.get("pnl") or 0.0),
            "variant_exit_reason": "not_simulated_missing_price_rows",
        }

    target_price = trade.get("target_price")
    if not isinstance(target_price, (int, float)) or target_price <= 0:
        if trade.get("exit_reason") == "target" and isinstance(
            trade.get("exit_raw_price"), (int, float)
        ):
            target_price = float(trade["exit_raw_price"])
        else:
            target_mult = trade.get("target_mult_used")
            if isinstance(target_mult, (int, float)) and target_mult > 0:
                atr = risk / ATR_STOP_MULT
                target_price = round(entry_price + float(target_mult) * atr, 2)
            else:
                target_price = 0.0

    remaining = shares
    realized = 0.0
    stop = stop_price
    high_water = entry_price
    target_active = target_price > 0
    trailing_active = False
    partial_events: list[dict[str, Any]] = []
    profit_floor_triggered = False

    trigger_r = variant.get("profit_floor_trigger_r")
    floor_r = variant.get("profit_floor_r")
    partial_fraction = float(variant.get("target_partial_fraction") or 0.0)
    trail_r = variant.get("trail_after_target_r")

    for row in active_rows:
        opn = row["open"]
        low = row["low"]
        high = row["high"]
        high_water = max(high_water, high)

        if trailing_active and trail_r is not None:
            stop = max(stop, high_water - float(trail_r) * risk)

        if low <= stop:
            exit_price, raw_exit = _stop_fill(opn, stop)
            realized += _sell_pnl(entry_price, exit_price, remaining)
            return {
                **trade,
                "exit_date": row["date"],
                "exit_price": round(exit_price, 2),
                "exit_raw_price": round(raw_exit, 4),
                "shares": shares,
                "pnl": round(realized, 2),
                "pnl_pct_net": round((realized / (entry_price * shares)), 6),
                "exit_reason": (
                    "event_leader_trailing_stop" if trailing_active
                    else "event_leader_profit_floor_stop"
                    if profit_floor_triggered
                    else "stop"
                ),
                "variant_partial_events": partial_events,
            }

        if (
            trigger_r is not None
            and floor_r is not None
            and not profit_floor_triggered
            and high >= entry_price + float(trigger_r) * risk
        ):
            stop = max(stop, entry_price + float(floor_r) * risk)
            profit_floor_triggered = True

        if target_active and target_price > 0 and high >= target_price:
            if partial_fraction <= 0:
                exit_price, raw_exit = _target_fill(opn, target_price)
                realized += _sell_pnl(entry_price, exit_price, remaining)
                return {
                    **trade,
                    "exit_date": row["date"],
                    "exit_price": round(exit_price, 2),
                    "exit_raw_price": round(raw_exit, 4),
                    "shares": shares,
                    "pnl": round(realized, 2),
                    "pnl_pct_net": round((realized / (entry_price * shares)), 6),
                    "exit_reason": "target",
                    "variant_partial_events": partial_events,
                }

            shares_to_sell = max(1, min(remaining, math.floor(shares * partial_fraction)))
            exit_price, raw_exit = _target_fill(opn, target_price)
            partial_pnl = _sell_pnl(entry_price, exit_price, shares_to_sell)
            realized += partial_pnl
            remaining -= shares_to_sell
            partial_events.append(
                {
                    "date": row["date"],
                    "reason": "event_leader_target_partial",
                    "shares_sold": shares_to_sell,
                    "exit_price": round(exit_price, 2),
                    "raw_exit": round(raw_exit, 4),
                    "pnl": round(partial_pnl, 2),
                }
            )
            target_active = False
            trailing_active = True
            stop = max(stop, target_price)
            if remaining <= 0:
                return {
                    **trade,
                    "exit_date": row["date"],
                    "exit_price": round(exit_price, 2),
                    "exit_raw_price": round(raw_exit, 4),
                    "shares": shares,
                    "pnl": round(realized, 2),
                    "pnl_pct_net": round((realized / (entry_price * shares)), 6),
                    "exit_reason": "target",
                    "variant_partial_events": partial_events,
                }

    last = active_rows[-1]
    exit_price, raw_exit = _mark_fill(last["close"])
    realized += _sell_pnl(entry_price, exit_price, remaining)
    return {
        **trade,
        "exit_date": last["date"],
        "exit_price": round(exit_price, 2),
        "exit_raw_price": round(raw_exit, 4),
        "shares": shares,
        "pnl": round(realized, 2),
        "pnl_pct_net": round((realized / (entry_price * shares)), 6),
        "exit_reason": (
            "event_leader_end_mark"
            if partial_events or profit_floor_triggered else "end_of_backtest"
        ),
        "variant_partial_events": partial_events,
    }


def _make_variant_trades(
    baseline: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    end_date: str,
    variant: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trades = []
    touched = []
    for trade in baseline.get("trades", []):
        ticker = str(trade.get("ticker") or "").upper()
        rows = snapshot.get(ticker, [])
        qualified, qualifier = _qualifies(trade, rows)
        if variant is None or not qualified:
            out = dict(trade)
        else:
            out = _simulate_variant_trade(dict(trade), rows, end_date, variant)
            out["event_leader_profit_ladder_applied"] = True
            out["event_leader_qualifier"] = qualifier
            touched.append(
                {
                    "ticker": ticker,
                    "strategy": trade.get("strategy"),
                    "sector": trade.get("sector"),
                    "entry_date": trade.get("entry_date"),
                    "baseline_exit_date": trade.get("exit_date"),
                    "variant_exit_date": out.get("exit_date"),
                    "baseline_exit_reason": trade.get("exit_reason"),
                    "variant_exit_reason": out.get("exit_reason"),
                    "baseline_pnl": round(float(trade.get("pnl") or 0.0), 2),
                    "variant_pnl": round(float(out.get("pnl") or 0.0), 2),
                    "pnl_delta": round(
                        float(out.get("pnl") or 0.0)
                        - float(trade.get("pnl") or 0.0),
                        2,
                    ),
                    "qualifier": qualifier,
                    "partial_events": out.get("variant_partial_events") or [],
                }
            )
        trades.append(out)
    return trades, touched


def _trade_price_on_date(
    trade: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    date_value: str,
) -> float | None:
    rows = snapshot.get(str(trade.get("ticker") or "").upper()) or []
    idx = _row_index(rows, date_value)
    return rows[idx]["close"] if idx is not None else None


def _all_window_dates(snapshot: dict[str, list[dict[str, Any]]], start: str, end: str) -> list[str]:
    spy_rows = snapshot.get("SPY") or []
    if spy_rows:
        return [row["date"] for row in spy_rows if start <= row["date"] <= end]
    dates = sorted({row["date"] for rows in snapshot.values() for row in rows})
    return [date for date in dates if start <= date <= end]


def _proxy_metrics(
    trades: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> dict[str, Any]:
    dates = _all_window_dates(snapshot, start, end)
    equity_curve = []
    for date_value in dates:
        equity = 100_000.0
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")[:10]
            exit_date = str(trade.get("exit_date") or "")[:10]
            if not entry_date or date_value < entry_date:
                continue
            if exit_date and date_value >= exit_date:
                equity += float(trade.get("pnl") or 0.0)
                continue
            close = _trade_price_on_date(trade, snapshot, date_value)
            if close is None:
                continue
            entry = float(trade.get("entry_price") or 0.0)
            shares = int(trade.get("shares") or 0)
            if entry > 0 and shares > 0:
                equity += (close - entry) * shares
        equity_curve.append((date_value, round(equity, 2)))

    returns = []
    prev = None
    for _, equity in equity_curve:
        if prev and prev > 0:
            returns.append(equity / prev - 1.0)
        prev = equity

    if returns and len(returns) > 1:
        mean = statistics.mean(returns)
        stdev = statistics.stdev(returns)
        sharpe_daily = (mean / stdev * math.sqrt(252)) if stdev > 0 else 0.0
    else:
        sharpe_daily = 0.0

    peak = None
    max_dd = 0.0
    for _, equity in equity_curve:
        peak = equity if peak is None else max(peak, equity)
        if peak and peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)

    total_pnl = sum(float(trade.get("pnl") or 0.0) for trade in trades)
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    total = len(trades)
    total_return_pct = total_pnl / 100_000.0
    return {
        "expected_value_score": round(total_return_pct * sharpe_daily, 4),
        "total_return_pct": round(total_return_pct, 4),
        "total_pnl": round(total_pnl, 2),
        "sharpe_daily": round(sharpe_daily, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "win_rate": round(wins / total, 4) if total else None,
        "trade_count": total,
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "expected_value_score",
        "total_return_pct",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
    )
    out = {}
    for field in fields:
        a = after.get(field)
        b = before.get(field)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out[field] = round(a - b, 6)
    return out


def _official_metric_view(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "total_pnl": result.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _analyze() -> dict[str, Any]:
    by_window: dict[str, Any] = OrderedDict()
    for label, spec in WINDOWS.items():
        baseline = _load_json(REPO_ROOT / spec["baseline"])
        snapshot = _load_snapshot(REPO_ROOT / spec["snapshot"])
        baseline_trades, baseline_touched = _make_variant_trades(
            baseline,
            snapshot,
            spec["end"],
            None,
        )
        before_proxy = _proxy_metrics(
            baseline_trades,
            snapshot,
            spec["start"],
            spec["end"],
        )
        variants = OrderedDict()
        for variant_name, variant_config in VARIANTS.items():
            variant_trades, touched = _make_variant_trades(
                baseline,
                snapshot,
                spec["end"],
                variant_config,
            )
            after_proxy = _proxy_metrics(
                variant_trades,
                snapshot,
                spec["start"],
                spec["end"],
            )
            variants[variant_name] = {
                "before_proxy_metrics": before_proxy,
                "after_proxy_metrics": after_proxy,
                "delta_proxy_metrics": _delta(after_proxy, before_proxy),
                "touched_trade_count": len(touched),
                "touched_pnl_delta": round(
                    sum(item["pnl_delta"] for item in touched),
                    2,
                ),
                "touched_trades": touched,
            }
        by_window[label] = {
            "official_baseline_metrics": _official_metric_view(baseline),
            "before_proxy_touched_count": len(baseline_touched),
            "variants": variants,
        }

    summaries = OrderedDict()
    for variant_name in VARIANTS:
        ev_delta_sum = 0.0
        pnl_delta_sum = 0.0
        ev_improved = 0
        pnl_improved = 0
        max_dd_delta = None
        sharpe_delta_max = None
        win_delta_min = None
        touched_count = 0
        touched_pnl_delta = 0.0
        by_window_summary = OrderedDict()
        for label, window_payload in by_window.items():
            row = window_payload["variants"][variant_name]
            delta = row["delta_proxy_metrics"]
            ev_delta = float(delta.get("expected_value_score") or 0.0)
            pnl_delta = float(delta.get("total_pnl") or 0.0)
            ev_delta_sum += ev_delta
            pnl_delta_sum += pnl_delta
            ev_improved += int(ev_delta > 0)
            pnl_improved += int(pnl_delta > 0)
            touched_count += int(row["touched_trade_count"])
            touched_pnl_delta += float(row["touched_pnl_delta"])
            dd_delta = delta.get("max_drawdown_pct")
            if isinstance(dd_delta, (int, float)):
                max_dd_delta = dd_delta if max_dd_delta is None else max(max_dd_delta, dd_delta)
            sharpe_delta = delta.get("sharpe_daily")
            if isinstance(sharpe_delta, (int, float)):
                sharpe_delta_max = (
                    sharpe_delta
                    if sharpe_delta_max is None
                    else max(sharpe_delta_max, sharpe_delta)
                )
            win_delta = delta.get("win_rate")
            if isinstance(win_delta, (int, float)):
                win_delta_min = win_delta if win_delta_min is None else min(win_delta_min, win_delta)
            by_window_summary[label] = {
                "delta_proxy_metrics": delta,
                "touched_trade_count": row["touched_trade_count"],
                "touched_pnl_delta": row["touched_pnl_delta"],
            }

        summaries[variant_name] = {
            "variant_config": VARIANTS[variant_name],
            "by_window": by_window_summary,
            "aggregate": {
                "expected_value_score_delta_sum": round(ev_delta_sum, 4),
                "total_pnl_delta_sum": round(pnl_delta_sum, 2),
                "ev_windows_improved": ev_improved,
                "pnl_windows_improved": pnl_improved,
                "max_drawdown_delta_max": max_dd_delta,
                "max_sharpe_daily_delta": sharpe_delta_max,
                "win_rate_delta_min": win_delta_min,
                "touched_trade_count": touched_count,
                "touched_pnl_delta_sum": round(touched_pnl_delta, 2),
            },
        }

    best_variant = max(
        summaries,
        key=lambda name: (
            summaries[name]["aggregate"]["expected_value_score_delta_sum"],
            summaries[name]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    return {
        "by_window": by_window,
        "summaries": summaries,
        "best_variant": best_variant,
    }


def main() -> int:
    analysis = _analyze()
    best_variant = analysis["best_variant"]
    best_summary = analysis["summaries"][best_variant]
    aggregate = best_summary["aggregate"]
    gate4_shadow_passed = (
        aggregate["ev_windows_improved"] >= 2
        and (
            aggregate["expected_value_score_delta_sum"] > 0
            or aggregate["total_pnl_delta_sum"] > 0
        )
        and (aggregate["win_rate_delta_min"] is None or aggregate["win_rate_delta_min"] >= 0)
    )

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": timestamp,
        "lane": "alpha_search",
        "status": "promising_shadow_only" if gate4_shadow_passed else "rejected_shadow",
        "decision": "shadow_only_not_production_promoted",
        "change_type": "exit_lifecycle_shadow_replay",
        "mechanism_family": "event_leader_profit_ladder",
        "hypothesis": (
            "SPY-relative leaders that enter immediately after an auditable "
            "price/volume re-rating event may need a lifecycle mode that protects "
            "early profits and lets the remaining position drift instead of forcing "
            "ordinary all-or-nothing target/stop exits."
        ),
        "alpha_hypothesis": {
            "category": "exit / lifecycle winner capture",
            "blocked_direct_event_semantics": (
                "Full historical LLM/news semantic coverage is still sparse, so this "
                "first replay uses a price/volume event-repricing proxy and records "
                "that limitation explicitly."
            ),
        },
        "historical_experiment_check": {
            "similar_failures_checked": {
                "simple_profit_protection": (
                    "Rejected broadly in the playbook; this narrows it to event "
                    "repricing plus accepted SPY-relative leaders."
                ),
                "broad_trailing_full_exit": (
                    "Rejected broadly; this is selected-trade lifecycle shadow only."
                ),
                "spy_leader_target_width": (
                    "exp-20260506-006 rejected wider full targets; this preserves "
                    "profit via floors/partials instead of only moving the target."
                ),
                "llm_soft_ranking": (
                    "Still sample-limited; no LLM decision boundary is changed."
                ),
            },
            "mechanism_insight_check": (
                "Does not repeat static baskets, broad target width, global trailing "
                "exits, or same-sample event threshold retuning."
            ),
        },
        "parameters": {
            "single_causal_variable": (
                "event-leader profit-ladder exit mode on fixed accepted entries"
            ),
            "event_leader_definition": {
                "spy_relative_leader": True,
                "event_lookback_trading_days": EVENT_LOOKBACK_DAYS,
                "event_min_abs_close_or_gap_move": EVENT_MIN_ABS_MOVE,
                "event_min_volume_ratio_vs_prior_20d": EVENT_MIN_VOLUME_RATIO,
            },
            "variants": VARIANTS,
            "best_variant": best_variant,
            "locked_variables": [
                "candidate universe",
                "signal generation",
                "entry filters",
                "entry ordering",
                "risk sizing",
                "position slots",
                "add-ons",
                "LLM/news gates",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            label: spec["state_note"]
            for label, spec in WINDOWS.items()
        },
        "results": analysis,
        "gate4_shadow": {
            "passed": gate4_shadow_passed,
            "basis": (
                "Fixed-entry shadow must improve proxy EV in at least two windows, "
                "avoid win-rate deterioration, and improve aggregate EV or PnL. "
                "Promotion still requires a real shared backtester/run adapter."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "promotion_requirement": (
                "If pursued, implement as a shared exit policy so run.py and "
                "backtester.py both surface the same event-leader state, partial, "
                "floor, and trailing semantics."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_note": (
                "This does not judge LLM value; sparse historical semantics are the "
                "reason for using an OHLCV event proxy."
            ),
        },
        "risk_of_change": (
            "The shadow holds some winners longer and may occupy slots in a full "
            "implementation; fixed-entry replay does not measure that opportunity cost."
        ),
        "next_action": (
            "Promote only to a real replay adapter if the shadow is strong enough; "
            "otherwise keep as a logged non-repeat."
        ),
    }

    exp_dir = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    result_path = exp_dir / "event_leader_profit_ladder.json"
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    artifact_path = (
        REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_event_leader_profit_ladder.md"
    )

    _write_json(result_path, payload)
    _write_json(log_path, payload)
    _write_json(
        ticket_path,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "best_variant": best_variant,
            "next_action": payload["next_action"],
        },
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("w", encoding="utf-8") as handle:
        handle.write(f"# {EXPERIMENT_ID}: Event-Leader Profit Ladder\n\n")
        handle.write(f"- Status: `{payload['status']}`\n")
        handle.write(f"- Best variant: `{best_variant}`\n")
        handle.write(
            "- Aggregate proxy EV delta: "
            f"`{aggregate['expected_value_score_delta_sum']}`\n"
        )
        handle.write(
            "- Aggregate proxy PnL delta: "
            f"`{aggregate['total_pnl_delta_sum']}`\n"
        )
        handle.write(
            "- Touched trades: "
            f"`{aggregate['touched_trade_count']}`\n"
        )
        handle.write("\nThis is fixed-entry shadow evidence only; it does not model slot reuse.\n")

    _append_jsonl(
        REPO_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "change_type": "exit_lifecycle_shadow_replay",
            "hypothesis": payload["hypothesis"],
            "date_range": payload["date_range"],
            "parameters": payload["parameters"],
            "market_regime_summary": payload["market_regime_summary"],
            "before_metrics": "see docs/experiments/logs/exp-20260506-010.json",
            "after_metrics": "see docs/experiments/logs/exp-20260506-010.json",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "decision": payload["status"],
            "production_impact": payload["production_impact"],
        },
    )

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": best_variant,
        "aggregate": aggregate,
        "result_path": str(result_path),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
