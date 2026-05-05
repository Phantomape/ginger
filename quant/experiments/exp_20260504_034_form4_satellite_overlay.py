"""Evaluate Form 4 as a bounded satellite overlay on the core strategy.

This alpha-search experiment does not tune the Form 4 event rule. It asks
whether the already frozen meaningful-purchase queue has enough portfolio-level
impact to justify promotion beyond default-off observation when it is added as
a separate 10k-notional overlay that does not consume A/B core slots.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    QUEUE_NAME,
    RULE_VERSION,
    aggregate_purchase_events,
    latest_form4_transactions_path,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXP_ID = "exp-20260504-034"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_satellite_overlay.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
AUDIT_MD = REPO_ROOT / "docs" / "experiments" / f"{EXP_ID}_form4_satellite_overlay.md"

INITIAL_CAPITAL = 100_000.0
EVENT_NOTIONAL = 10_000.0
MAX_EVENT_POSITIONS = 1
HOLD_DAYS = 10

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _load_price_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in WINDOWS.values():
        path = REPO_ROOT / window["snapshot"]
        payload = _json_load(path, {})
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                date_key = str(row["Date"])[:10]
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "open": _float_or_none(row.get("Open")),
                    "close": _float_or_none(row.get("Close")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _trading_days(prices: dict[str, list[dict[str, Any]]], start: str, end: str) -> list[str]:
    return [row["date"] for row in prices.get("SPY", []) if start <= row["date"] <= end]


def _close_on_or_before(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> float | None:
    rows = prices.get(str(ticker).upper())
    if not rows:
        return None
    last = None
    for row in rows:
        if row["date"] > date_value:
            break
        if row.get("close") is not None:
            last = row["close"]
    return last


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _load_form4_events(prices: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], Path | None]:
    path = latest_form4_transactions_path(REPO_ROOT / "data" / "non_ohlcv")
    if path is None:
        return [], None
    rows = load_form4_transaction_rows(path)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    events = [
        event
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    out = []
    for event in events:
        usable = str(event.get("usable_trade_date") or "")[:10]
        if not usable or not _window_name(usable):
            continue
        ticker = str(event.get("ticker") or "").upper()
        if ticker not in prices:
            out.append({**event, "window": _window_name(usable), "status": "missing_price_history"})
            continue
        out.append({**event, "window": _window_name(usable), "status": "event_ready"})
    return sorted(out, key=lambda row: (row.get("usable_trade_date") or "", row.get("ticker") or "")), path


def _candidate_trade(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    usable = str(event.get("usable_trade_date") or "")[:10]
    rows = prices.get(ticker)
    if not ticker or not usable or not rows:
        return {**event, "status": "missing_price_history"}
    start_idx = _first_index_on_or_after(rows, usable)
    if start_idx is None:
        return {**event, "status": "missing_entry_price"}
    exit_idx = start_idx + HOLD_DAYS
    if exit_idx >= len(rows):
        return {**event, "status": "missing_exit_price"}
    entry = rows[start_idx]
    exit_row = rows[exit_idx]
    if not entry.get("open") or not exit_row.get("close"):
        return {**event, "status": "missing_open_or_close"}
    gross_return = exit_row["close"] / entry["open"] - 1.0
    net_return = gross_return - ROUND_TRIP_COST_PCT
    return {
        **event,
        "status": "price_ready",
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(float(entry["open"]), 6),
        "exit_close": round(float(exit_row["close"]), 6),
        "gross_return_pct": round(gross_return * 100.0, 6),
        "net_return_pct": round(net_return * 100.0, 6),
        "notional": EVENT_NOTIONAL,
        "shares": EVENT_NOTIONAL / float(entry["open"]),
        "pnl": round(EVENT_NOTIONAL * net_return, 2),
    }


def _select_event_trades(
    candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row
        for row in candidates
        if start <= str(row.get("usable_trade_date") or "")[:10] <= end
    ]
    ready = [row for row in scoped if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            row["entry_date"],
            -float(row.get("total_purchase_value") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = [
        {
            "ticker": row.get("ticker"),
            "usable_trade_date": row.get("usable_trade_date"),
            "window": row.get("window"),
            "reason": row.get("status"),
        }
        for row in scoped
        if row.get("status") != "price_ready"
    ]
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = row["entry_date"]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= MAX_EVENT_POSITIONS:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "usable_trade_date": row.get("usable_trade_date"),
                    "entry_date": entry_date,
                    "window": row.get("window"),
                    "reason": "event_sleeve_capacity_full",
                    "active_tickers": [trade.get("ticker") for trade in active],
                }
            )
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _event_equity_curve(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    days = _trading_days(prices, start, end)
    entries_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exits_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        entries_by_day[trade["entry_date"]].append(trade)
        exits_by_day[trade["exit_date"]].append(trade)

    cash = INITIAL_CAPITAL
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in days:
        for trade in entries_by_day.get(day, []):
            cash -= EVENT_NOTIONAL
            active.append(trade)

        exiting = exits_by_day.get(day, [])
        for trade in exiting:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is None:
                continue
            cash += trade["shares"] * close - EVENT_NOTIONAL * ROUND_TRIP_COST_PCT
        if exiting:
            exit_keys = {
                (trade["ticker"], trade["entry_date"], trade["exit_date"])
                for trade in exiting
            }
            active = [
                trade
                for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"]) not in exit_keys
            ]

        market_value = 0.0
        for trade in active:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is not None:
                market_value += trade["shares"] * close
        equity = cash + market_value
        curve.append(
            {
                "date": day,
                "event_equity": round(equity, 2),
                "event_pnl": round(equity - INITIAL_CAPITAL, 2),
                "active_event_positions": len(active),
            }
        )
    return curve


def _daily_sharpe(curve: list[tuple[str, float]]) -> float | None:
    returns = []
    for (_, prev), (_, curr) in zip(curve, curve[1:]):
        if prev > 0:
            returns.append(curr / prev - 1.0)
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return round((sum(returns) / len(returns)) / stdev * math.sqrt(252), 2)


def _max_drawdown(curve: list[tuple[str, float]]) -> float:
    peak = 0.0
    max_dd = 0.0
    for _, equity in curve:
        if equity > peak:
            peak = equity
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return round(max_dd, 4)


def _pnl_from_trade(trade: dict[str, Any]) -> float:
    for key in ("profit_loss", "pnl", "realized_pnl"):
        value = _float_or_none(trade.get(key))
        if value is not None:
            return value
    return 0.0


def _core_metrics(result: dict[str, Any]) -> dict[str, Any]:
    trades = list(result.get("trades") or [])
    total_pnl = float(result.get("total_pnl") or 0.0)
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_pnl / INITIAL_CAPITAL, 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "vs_spy_pct": _round((result.get("benchmarks") or {}).get("strategy_vs_spy_pct"), 4),
        "vs_qqq_pct": _round((result.get("benchmarks") or {}).get("strategy_vs_qqq_pct"), 4),
        "winning_trades": sum(1 for trade in trades if _pnl_from_trade(trade) > 0),
    }


def _combined_metrics(
    result: dict[str, Any],
    event_curve: list[dict[str, Any]],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    core_curve = [
        (str(day), float(equity))
        for day, equity in result.get("equity_curve", [])
    ]
    event_by_day = {row["date"]: float(row["event_pnl"]) for row in event_curve}
    combined_curve = [
        (day, round(core_equity + event_by_day.get(day, 0.0), 2))
        for day, core_equity in core_curve
    ]
    final_equity = combined_curve[-1][1] if combined_curve else INITIAL_CAPITAL
    total_pnl = final_equity - INITIAL_CAPITAL
    total_return = total_pnl / INITIAL_CAPITAL
    sharpe = _daily_sharpe(combined_curve)
    expected_value = total_return * sharpe if sharpe is not None else None
    core_trades = list(result.get("trades") or [])
    wins = sum(1 for trade in core_trades if _pnl_from_trade(trade) > 0)
    wins += sum(1 for trade in event_trades if float(trade.get("pnl") or 0.0) > 0)
    trade_count = len(core_trades) + len(event_trades)
    benchmarks = result.get("benchmarks") or {}
    spy_ret = benchmarks.get("spy_buy_hold_return_pct")
    qqq_ret = benchmarks.get("qqq_buy_hold_return_pct")
    return {
        "expected_value_score": round(expected_value, 4) if expected_value is not None else None,
        "sharpe_daily": sharpe,
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return, 4),
        "max_drawdown_pct": _max_drawdown(combined_curve),
        "win_rate": round(wins / trade_count, 4) if trade_count else None,
        "trade_count": trade_count,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "vs_spy_pct": round(total_return - float(spy_ret), 4) if spy_ret is not None else None,
        "vs_qqq_pct": round(total_return - float(qqq_ret), 4) if qqq_ret is not None else None,
        "winning_trades": wins,
        "core_trade_count": len(core_trades),
        "event_trade_count": len(event_trades),
        "event_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in event_trades), 2),
        "combined_equity_curve": combined_curve,
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
    ]
    return {
        key: _round((after.get(key) or 0) - (before.get(key) or 0), 6)
        for key in keys
    }


def _gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    ev_before = float(before.get("expected_value_score") or 0.0)
    ev_after = float(after.get("expected_value_score") or 0.0)
    pnl_before = float(before.get("total_pnl") or 0.0)
    pnl_after = float(after.get("total_pnl") or 0.0)
    sharpe_delta = float(after.get("sharpe_daily") or 0.0) - float(before.get("sharpe_daily") or 0.0)
    drawdown_improvement = float(before.get("max_drawdown_pct") or 0.0) - float(after.get("max_drawdown_pct") or 0.0)
    win_rate_ok = float(after.get("win_rate") or 0.0) >= float(before.get("win_rate") or 0.0)
    trade_count_ok = int(after.get("trade_count") or 0) > int(before.get("trade_count") or 0) and win_rate_ok
    return {
        "ev_delta_pct": round((ev_after - ev_before) / ev_before, 6) if ev_before else None,
        "pnl_delta_pct": round((pnl_after - pnl_before) / pnl_before, 6) if pnl_before else None,
        "sharpe_daily_delta": round(sharpe_delta, 6),
        "drawdown_improvement_pct": round(drawdown_improvement, 6),
        "trade_count_increased_with_win_rate_not_down": trade_count_ok,
        "passes_material_ev": bool(ev_before and (ev_after - ev_before) / ev_before > 0.10),
        "passes_sharpe": sharpe_delta > 0.10,
        "passes_drawdown": drawdown_improvement > 0.01,
        "passes_pnl": bool(pnl_before and (pnl_after - pnl_before) / pnl_before > 0.05),
        "passes_trade_count": trade_count_ok,
    }


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _json_load(TICKET_JSON, {"experiment_id": EXP_ID})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "audit_report": _repo_rel(AUDIT_MD),
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_delta"],
                "next_action": payload["next_action"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _json_load(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    if not isinstance(registry, dict):
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update(
                {
                    "status": payload["status"],
                    "updated_at": payload["timestamp"],
                    "completed_at": payload["timestamp"],
                    "result": {
                        "decision": payload["decision"],
                        "aggregate_delta": payload["aggregate_delta"],
                        "log_file": _repo_rel(LOG_JSON),
                    },
                }
            )
            break
    else:
        experiments.append(
            {
                "experiment_id": EXP_ID,
                "title": "Form 4 satellite overlay",
                "status": payload["status"],
                "created_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "completed_at": payload["timestamp"],
                "lane": payload["lane"],
                "mechanism_family": payload["mechanism_family"],
                "result": {
                    "decision": payload["decision"],
                    "aggregate_delta": payload["aggregate_delta"],
                    "log_file": _repo_rel(LOG_JSON),
                },
            }
        )
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# Form 4 Satellite Overlay",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Results",
        "",
        "| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Trades | Win rate | Gate read |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["deltas"][label]
        gate = payload["gate4"]["by_window"][label]
        gate_read = "material" if gate["passes_material_ev"] or gate["passes_pnl"] else "sample-only"
        lines.append(
            f"| {label} | {before['expected_value_score']} | {after['expected_value_score']} | "
            f"{delta['expected_value_score']} | ${before['total_pnl']:,.2f} | "
            f"${after['total_pnl']:,.2f} | ${after['event_pnl']:,.2f} | "
            f"{before['trade_count']} -> {after['trade_count']} | "
            f"{before['win_rate']:.2%} -> {after['win_rate']:.2%} | {gate_read} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Next Action",
            "",
            payload["next_action"],
            "",
        ]
    )
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    universe = get_universe()
    prices = _load_price_map()
    events, event_file = _load_form4_events(prices)
    event_candidates = [_candidate_trade(event, prices) for event in events]

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    event_details: dict[str, dict[str, Any]] = {}
    core_results: dict[str, dict[str, Any]] = {}

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected, skipped = _select_event_trades(
            event_candidates,
            start=window["start"],
            end=window["end"],
        )
        event_curve = _event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(result)
        after_metrics[label] = _combined_metrics(result, event_curve, selected)
        core_results[label] = {
            "converged": bool((result.get("convergence") or {}).get("converged")),
            "known_biases": result.get("known_biases"),
            "ohlcv_source": (result.get("known_biases") or {}).get("ohlcv_source"),
        }
        event_details[label] = {
            "candidate_count": sum(
                1
                for row in event_candidates
                if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "price_ready_count": sum(
                1
                for row in event_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": dict(
                sorted(
                    {
                        reason: sum(1 for row in skipped if row["reason"] == reason)
                        for reason in {row["reason"] for row in skipped}
                    }.items()
                )
            ),
            "selected_trades": selected,
            "skipped_candidates": skipped,
            "event_equity_curve": event_curve,
        }

    deltas = {label: _delta(before_metrics[label], after_metrics[label]) for label in WINDOWS}
    gate_by_window = {label: _gate4(before_metrics[label], after_metrics[label]) for label in WINDOWS}
    aggregate = {
        "baseline_ev_sum": round(sum(float(row["expected_value_score"] or 0.0) for row in before_metrics.values()), 4),
        "overlay_ev_sum": round(sum(float(row["expected_value_score"] or 0.0) for row in after_metrics.values()), 4),
        "baseline_pnl_sum": round(sum(float(row["total_pnl"] or 0.0) for row in before_metrics.values()), 2),
        "overlay_pnl_sum": round(sum(float(row["total_pnl"] or 0.0) for row in after_metrics.values()), 2),
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if float(after_metrics[label]["expected_value_score"] or 0.0)
            > float(before_metrics[label]["expected_value_score"] or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if float(after_metrics[label]["expected_value_score"] or 0.0)
            < float(before_metrics[label]["expected_value_score"] or 0.0)
        ),
        "windows_trade_count_win_rate_gate": sum(
            1 for label in WINDOWS if gate_by_window[label]["passes_trade_count"]
        ),
        "windows_material_ev_or_pnl": sum(
            1
            for label in WINDOWS
            if gate_by_window[label]["passes_material_ev"] or gate_by_window[label]["passes_pnl"]
        ),
    }
    aggregate["ev_delta_sum"] = round(aggregate["overlay_ev_sum"] - aggregate["baseline_ev_sum"], 4)
    aggregate["ev_delta_pct"] = round(
        aggregate["ev_delta_sum"] / aggregate["baseline_ev_sum"], 6
    ) if aggregate["baseline_ev_sum"] else None
    aggregate["pnl_delta"] = round(aggregate["overlay_pnl_sum"] - aggregate["baseline_pnl_sum"], 2)
    aggregate["pnl_delta_pct"] = round(
        aggregate["pnl_delta"] / aggregate["baseline_pnl_sum"], 6
    ) if aggregate["baseline_pnl_sum"] else None

    material = aggregate["windows_material_ev_or_pnl"] >= 2 and aggregate["windows_ev_regressed"] == 0
    sample_positive = (
        aggregate["windows_ev_improved"] >= 2
        and aggregate["windows_trade_count_win_rate_gate"] >= 2
        and aggregate["windows_ev_regressed"] == 0
    )
    if material:
        decision = "accepted_requires_trade_enabled_sleeve_parity"
        status = "accepted_requires_followup"
        rationale = (
            "The Form 4 overlay cleared material EV/PnL checks in the majority of fixed windows. "
            "It still cannot be switched on without a shared trade-enabled production/backtest sleeve adapter."
        )
        next_action = (
            "Implement a shared trade-enabled Form 4 sleeve adapter with default-off config, "
            "then rerun the same three windows before enabling any live orders."
        )
    elif sample_positive:
        decision = "positive_sample_not_material_no_promotion"
        status = "rejected"
        rationale = (
            "The overlay added mostly profitable trades and did not regress EV in the majority read, "
            "but the EV/PnL lift was too small to justify adding live capital or complexity. "
            "Keep Form 4 in forward observation instead of promoting it."
        )
        next_action = (
            "Continue accumulating forward Form 4 paper-sleeve outcomes; retry promotion only after "
            "larger closed sample or a higher-capacity event discriminator appears."
        )
    else:
        decision = "rejected_overlay_no_stable_alpha"
        status = "rejected"
        rationale = (
            "The overlay did not improve the majority of fixed windows without regression, so it is not "
            "a production alpha candidate."
        )
        next_action = (
            "Do not retry Form 4 overlay capital allocation on the same sample; look for a different "
            "event source or wait for new forward outcomes."
        )

    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "form4_satellite_event_overlay",
        "change_type": "capital_overlay_experiment",
        "run_mode": "three_window_backtest_plus_form4_overlay",
        "hypothesis": (
            "A bounded Form 4 meaningful-purchase event stream may improve portfolio-level "
            "expected value when added as a separate 10k-notional, one-position satellite overlay "
            "that does not consume core A/B slots."
        ),
        "alpha_hypothesis": {
            "category": "capital_allocation / external event overlay",
            "text": "Use positive insider-purchase events as a small independent return sleeve rather than a core-slot replacement.",
            "why_this_not_llm": "LLM ranking remains sample-blocked; Form 4 has PIT-safe historical rows and fixed-window prices.",
        },
        "historical_experiment_check": {
            "exp-20260504-009": "Form 4 standalone sleeve was positive but not promoted because scarce-slot replacement was unanswered.",
            "exp-20260504-006": "Direct core-slot replacement evidence was too thin.",
            "exp-20260503-053": "Owner-role filters were rejected; this run does not retune owner roles.",
            "exp-20260504-032/033": "SEC/earnings filing-shock family has no fresh evidence; this run avoids that blocked path.",
            "why_not_repeat": (
                "This is a portfolio-level overlay-capital test using the frozen queue, not another Form 4 threshold, "
                "role, accepted-trade overlap, or scarce-core-slot replacement test."
            ),
        },
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "hold_days": HOLD_DAYS,
            "event_notional": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "core_initial_capital": INITIAL_CAPITAL,
            "overlay_semantics": "core unchanged plus Form 4 event PnL on same 100k reporting base",
            "selection_order": "entry_date asc, total_purchase_value desc on same day",
        },
        "single_causal_variable": "add frozen Form 4 event PnL as a bounded satellite overlay",
        "data_availability": {
            "form4_transaction_file": _repo_rel(event_file) if event_file else None,
            "raw_candidate_count": len(events),
            "price_ready_count": sum(1 for row in event_candidates if row.get("status") == "price_ready"),
            "candidate_tickers": sorted({str(row.get("ticker") or "").upper() for row in events if row.get("ticker")}),
            "pit_status": "uses Form 4 usable_trade_date and fixed OHLCV snapshots; no filing lookahead added",
            "windows": WINDOWS,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "deltas": deltas,
        "aggregate_delta": aggregate,
        "gate4": {
            "rule": "EV first; material if EV >10%, Sharpe >0.1, DD -1pp, PnL >5%, or trade count rises with win rate not down",
            "by_window": gate_by_window,
            "material_windows": aggregate["windows_material_ev_or_pnl"],
            "trade_count_win_rate_windows": aggregate["windows_trade_count_win_rate_gate"],
            "decision": decision,
        },
        "event_overlay": event_details,
        "core_run_audit": core_results,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": "LLM existence is not treated as the problem; this run avoids LLM because ranking replay sample remains too sparse.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_accepted": "trade-enabled sleeve adapter must be shared before production use",
        },
        "decision_rationale": rationale,
        "next_action": next_action,
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _update_ticket(payload)
    _update_registry(payload)
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate_delta"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
