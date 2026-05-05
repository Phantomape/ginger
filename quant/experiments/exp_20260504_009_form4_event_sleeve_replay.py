"""Default-off Form 4 event-sleeve replay.

This replay asks a narrow question: if the already-defined PIT-safe Form 4
forward queue were traded as a separate observe-only event sleeve, would it
earn standalone returns after fixed capacity, fixed notional, fixed holding
period, and transaction costs?

It does not alter the production signal path, core universe, Form 4 queue rule,
candidate ranking, sizing, exits, or any OHLCV entry threshold.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

if str(REPO_ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "quant"))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    QUEUE_NAME,
    RULE_VERSION,
    aggregate_purchase_events,
    latest_form4_transactions_path,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXP_ID = "exp-20260504-009"
OUT_DIR = DATA_DIR / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "form4_event_sleeve_replay.json"
LOG_JSON = DOCS_DIR / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = DOCS_DIR / "experiments" / "tickets" / f"{EXP_ID}.json"
EXPERIMENT_LOG = DOCS_DIR / "experiment_log.jsonl"
REGISTRY_JSON = DOCS_DIR / "experiment_registry.json"
AUDIT_MD = DOCS_DIR / "non_ohlcv_data_audit" / "form4_event_sleeve_replay_20260504.md"
BACKFILL_SUMMARY = DATA_DIR / "non_ohlcv" / "form4_backfill_summary_20241002_20260502.json"

SNAPSHOT_FILES = [
    DATA_DIR / "ohlcv_snapshot_20241002_20250422.json",
    DATA_DIR / "ohlcv_snapshot_20250423_20251022.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260421.json",
    DATA_DIR / "ohlcv_snapshot_20251023_20260501_with_pilot.json",
]
WINDOW_ORDER = ("old_thin", "mid_weak", "late_strong")
WINDOW_RANGES = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
}
BASELINE_METRICS = {
    "late_strong": {
        "expected_value_score": 3.4191,
        "total_return_pct": 0.7860,
        "total_pnl": 78600.33,
        "sharpe_daily": 4.35,
        "max_drawdown_pct": 0.0541,
        "win_rate": 0.7895,
        "trade_count": 19,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
        "vs_spy_pct": 0.7319,
        "vs_qqq_pct": 0.7280,
    },
    "mid_weak": {
        "expected_value_score": 1.4415,
        "total_return_pct": 0.5502,
        "total_pnl": 55015.08,
        "sharpe_daily": 2.62,
        "max_drawdown_pct": 0.0879,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
        "vs_spy_pct": 0.2958,
        "vs_qqq_pct": 0.2151,
    },
    "old_thin": {
        "expected_value_score": 0.3179,
        "total_return_pct": 0.2464,
        "total_pnl": 24642.07,
        "sharpe_daily": 1.29,
        "max_drawdown_pct": 0.0805,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 55,
        "survival_rate": 0.9167,
        "vs_spy_pct": 0.3137,
        "vs_qqq_pct": 0.3213,
    },
}

INITIAL_CAPITAL = 100_000.0
EVENT_NOTIONAL = 10_000.0
MAX_EVENT_POSITIONS = 1
PRIMARY_HOLD_DAYS = 10
DIAGNOSTIC_HOLD_DAYS = (20, 60)


def _load_json(path: Path, default: Any = None) -> Any:
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
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _load_price_map(snapshot_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for path in snapshot_paths:
        payload = _load_json(path, {})
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


def _window_name(value: str) -> str | None:
    for name, (start, end) in WINDOW_RANGES.items():
        if start <= value <= end:
            return name
    return None


def _trading_days(prices: dict[str, list[dict[str, Any]]], start: str, end: str) -> list[str]:
    return [row["date"] for row in prices.get("SPY", []) if start <= row["date"] <= end]


def _price_row(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> dict[str, Any] | None:
    rows = prices.get(str(ticker).upper())
    if not rows:
        return None
    for row in rows:
        if row["date"] == date_value:
            return row
    return None


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


def _candidate_trade(
    event: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
    hold_days: int,
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    usable = str(event.get("usable_trade_date") or "")[:10]
    rows = prices.get(ticker)
    if not ticker or not usable or not rows:
        return {**event, "status": "missing_price_history"}
    start_idx = _first_index_on_or_after(rows, usable)
    if start_idx is None:
        return {**event, "status": "missing_entry_price"}
    exit_idx = start_idx + hold_days
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
        "entry_open": entry["open"],
        "exit_close": exit_row["close"],
        "gross_return_pct": round(gross_return * 100.0, 6),
        "net_return_pct": round(net_return * 100.0, 6),
        "notional": EVENT_NOTIONAL,
        "shares": EVENT_NOTIONAL / entry["open"],
        "pnl": round(EVENT_NOTIONAL * net_return, 2),
    }


def _load_queue_events(prices: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    path = latest_form4_transactions_path(DATA_DIR / "non_ohlcv")
    if path is None:
        return []
    rows = load_form4_transaction_rows(path)
    start = min(start for start, _ in WINDOW_RANGES.values())
    end = max(end for _, end in WINDOW_RANGES.values())
    events = [
        event
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    out = []
    for event in events:
        usable = str(event.get("usable_trade_date") or "")[:10]
        out.append({
            **event,
            "window": _window_name(usable),
            "source_transaction_file": _repo_rel(path),
        })
    return sorted(out, key=lambda row: (row.get("usable_trade_date") or "", row.get("ticker") or ""))


def _select_trades(
    trade_candidates: list[dict[str, Any]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scoped = [
        row for row in trade_candidates
        if start <= str(row.get("usable_trade_date") or "")[:10] <= end
    ]
    price_ready = [row for row in scoped if row.get("status") == "price_ready"]
    price_ready.sort(
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
    for row in price_ready:
        entry_date = row["entry_date"]
        active = [trade for trade in active if trade["exit_date"] >= entry_date]
        if len(active) >= MAX_EVENT_POSITIONS:
            skipped.append({
                "ticker": row.get("ticker"),
                "usable_trade_date": row.get("usable_trade_date"),
                "entry_date": entry_date,
                "window": row.get("window"),
                "reason": "event_sleeve_capacity_full",
                "active_tickers": [trade.get("ticker") for trade in active],
            })
            continue
        selected.append(row)
        active.append(row)
    return selected, skipped


def _benchmark_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    start: str,
    end: str,
) -> float | None:
    rows = prices.get(ticker)
    if not rows:
        return None
    start_idx = _first_index_on_or_after(rows, start)
    if start_idx is None:
        return None
    end_rows = [row for row in rows if row["date"] <= end]
    if not end_rows:
        return None
    entry = rows[start_idx]
    exit_row = end_rows[-1]
    if not entry.get("open") or not exit_row.get("close"):
        return None
    return exit_row["close"] / entry["open"] - 1.0


def _equity_curve(
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
            exiting_keys = {(trade["ticker"], trade["entry_date"], trade["exit_date"]) for trade in exiting}
            active = [
                trade for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"]) not in exiting_keys
            ]

        market_value = 0.0
        for trade in active:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is not None:
                market_value += trade["shares"] * close
        equity = cash + market_value
        curve.append({
            "date": day,
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "equity": round(equity, 2),
            "active_positions": len(active),
        })
    return curve


def _sharpe_daily(curve: list[dict[str, Any]]) -> float | None:
    returns = []
    for prev, curr in zip(curve, curve[1:]):
        prev_eq = float(prev["equity"])
        curr_eq = float(curr["equity"])
        if prev_eq:
            returns.append(curr_eq / prev_eq - 1.0)
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if not stdev:
        return None
    return round((sum(returns) / len(returns)) / stdev * math.sqrt(252), 6)


def _max_drawdown(curve: list[dict[str, Any]]) -> float:
    peak = None
    max_dd = 0.0
    for row in curve:
        equity = float(row["equity"])
        if peak is None or equity > peak:
            peak = equity
        if peak:
            max_dd = min(max_dd, equity / peak - 1.0)
    return abs(max_dd)


def _summarize_replay(
    *,
    label: str,
    start: str,
    end: str,
    trade_candidates: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    hold_days: int,
) -> dict[str, Any]:
    selected, skipped = _select_trades(trade_candidates, start=start, end=end)
    curve = _equity_curve(selected, prices=prices, start=start, end=end)
    final_equity = float(curve[-1]["equity"]) if curve else INITIAL_CAPITAL
    total_pnl = final_equity - INITIAL_CAPITAL
    total_return = total_pnl / INITIAL_CAPITAL
    sharpe = _sharpe_daily(curve)
    max_dd = _max_drawdown(curve) if curve else 0.0
    pnls = [float(trade["pnl"]) for trade in selected]
    wins = [pnl for pnl in pnls if pnl > 0.0]
    candidates_in_window = [
        row for row in trade_candidates
        if start <= str(row.get("usable_trade_date") or "")[:10] <= end
    ]
    spy_return = _benchmark_return(prices, "SPY", start, end)
    qqq_return = _benchmark_return(prices, "QQQ", start, end)
    expected_value = total_return * sharpe if sharpe is not None else None
    return {
        "label": label,
        "date_range": {"start": start, "end": end},
        "hold_days": hold_days,
        "initial_capital": INITIAL_CAPITAL,
        "event_notional": EVENT_NOTIONAL,
        "max_event_positions": MAX_EVENT_POSITIONS,
        "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        "candidate_count": len(candidates_in_window),
        "signals_generated": len(candidates_in_window),
        "signals_survived": len(selected),
        "survival_rate": round(len(selected) / len(candidates_in_window), 6) if candidates_in_window else None,
        "trade_count": len(selected),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return, 8),
        "sharpe_daily": sharpe,
        "expected_value_score": round(expected_value, 8) if expected_value is not None else None,
        "max_drawdown_pct": round(max_dd, 8),
        "win_rate": round(len(wins) / len(selected), 6) if selected else None,
        "vs_spy_pct": round(total_return - spy_return, 8) if spy_return is not None else None,
        "vs_qqq_pct": round(total_return - qqq_return, 8) if qqq_return is not None else None,
        "spy_buy_hold_return_pct": round(spy_return, 8) if spy_return is not None else None,
        "qqq_buy_hold_return_pct": round(qqq_return, 8) if qqq_return is not None else None,
        "skip_reasons": dict(sorted({reason: sum(1 for row in skipped if row["reason"] == reason) for reason in {row["reason"] for row in skipped}}.items())),
        "trades": selected,
        "skipped_candidates": skipped,
        "equity_curve": curve,
    }


def _candidate_summary(events: list[dict[str, Any]], primary_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "queue_name": QUEUE_NAME,
        "rule_version": RULE_VERSION,
        "min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
        "raw_candidate_count": len(events),
        "primary_price_ready_count": sum(1 for row in primary_candidates if row.get("status") == "price_ready"),
        "tickers": sorted({str(row.get("ticker") or "") for row in events if row.get("ticker")}),
        "by_window": {
            window: {
                "candidate_count": sum(1 for row in events if row.get("window") == window),
                "price_ready_count": sum(1 for row in primary_candidates if row.get("window") == window and row.get("status") == "price_ready"),
            }
            for window in WINDOW_ORDER
        },
    }


def _append_experiment_log(row: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line and f'"experiment_id": "{EXP_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    if not isinstance(ticket, dict):
        ticket = {"experiment_id": EXP_ID}
    ticket.update({
        "status": payload["status"],
        "decision": payload["decision"],
        "completed_at": payload["timestamp"],
        "result": {
            "artifact": _repo_rel(OUT_JSON),
            "audit_report": _repo_rel(AUDIT_MD),
            "log": _repo_rel(LOG_JSON),
            "decision": payload["decision"],
            "aggregate_primary": payload["event_sleeve_replay"]["primary"]["aggregate"],
            "next_action": payload["next_action"],
        },
    })
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON, {"schema_version": 1, "experiments": []})
    experiments = registry.setdefault("experiments", [])
    for entry in experiments:
        if entry.get("experiment_id") == EXP_ID:
            entry.update({
                "status": payload["status"],
                "updated_at": payload["timestamp"],
                "completed_at": payload["timestamp"],
                "result": {
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "log_file": _repo_rel(LOG_JSON),
                    "reason": payload["decision_rationale"],
                },
            })
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _aggregate_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total_pnl = sum(row["total_pnl"] for row in rows.values())
    total_return = total_pnl / INITIAL_CAPITAL
    trade_count = sum(row["trade_count"] for row in rows.values())
    wins = 0
    for row in rows.values():
        wins += sum(1 for trade in row["trades"] if float(trade["pnl"]) > 0.0)
    avg_sharpe = statistics.mean(
        row["sharpe_daily"] for row in rows.values() if row.get("sharpe_daily") is not None
    )
    return {
        "total_pnl": round(total_pnl, 2),
        "total_return_pct_on_100k_base": round(total_return, 8),
        "trade_count": trade_count,
        "win_rate": round(wins / trade_count, 6) if trade_count else None,
        "avg_window_sharpe_daily": round(avg_sharpe, 6),
        "expected_value_score_proxy": round(total_return * avg_sharpe, 8),
        "positive_pnl_windows": sum(1 for row in rows.values() if row["total_pnl"] > 0),
        "window_count": len(rows),
    }


def _fmt_pct(value: Any, *, decimal_input: bool = True) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if decimal_input:
        number *= 100.0
    return f"{number:.2f}%"


def _write_report(payload: dict[str, Any]) -> None:
    primary = payload["event_sleeve_replay"]["primary"]
    lines = [
        "# Form 4 Event Sleeve Replay",
        "",
        f"- experiment_id: `{payload['experiment_id']}`",
        f"- timestamp: `{payload['timestamp']}`",
        f"- decision: `{payload['decision']}`",
        f"- production_impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Frozen Replay Config",
        "",
        f"- queue_rule: `{QUEUE_NAME} / {RULE_VERSION}`",
        f"- min_total_purchase_value: `${FORWARD_QUEUE_MIN_PURCHASE_VALUE:,.0f}`",
        f"- hold_days: `{PRIMARY_HOLD_DAYS}`",
        f"- max_event_positions: `{MAX_EVENT_POSITIONS}`",
        f"- event_notional: `${EVENT_NOTIONAL:,.0f}`",
        f"- initial_capital_base: `${INITIAL_CAPITAL:,.0f}`",
        f"- round_trip_cost_pct: `{ROUND_TRIP_COST_PCT}`",
        "",
        "## Primary 10d Results",
        "",
        "| Window | Candidates | Trades | PnL | Return | Sharpe | Max DD | Win rate | EV | vs SPY |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for window in WINDOW_ORDER:
        row = primary["by_window"][window]
        lines.append(
            f"| {window} | {row['candidate_count']} | {row['trade_count']} | "
            f"${row['total_pnl']:,.2f} | {_fmt_pct(row['total_return_pct'])} | "
            f"{row['sharpe_daily'] if row['sharpe_daily'] is not None else 'n/a'} | "
            f"{_fmt_pct(row['max_drawdown_pct'])} | {_fmt_pct(row['win_rate'])} | "
            f"{row['expected_value_score'] if row['expected_value_score'] is not None else 'n/a'} | "
            f"{_fmt_pct(row['vs_spy_pct'])} |"
        )
    agg = primary["aggregate"]
    lines.extend([
        "",
        "## Aggregate Read",
        "",
        f"- total_pnl: `${agg['total_pnl']:,.2f}`",
        f"- total_return_on_100k_base: `{_fmt_pct(agg['total_return_pct_on_100k_base'])}`",
        f"- trade_count: `{agg['trade_count']}`",
        f"- win_rate: `{_fmt_pct(agg['win_rate'])}`",
        f"- positive_pnl_windows: `{agg['positive_pnl_windows']}/{agg['window_count']}`",
        f"- expected_value_score_proxy: `{agg['expected_value_score_proxy']}`",
        "",
        "## Diagnostic Holds",
        "",
        "20d and 60d are diagnostics only; the decision uses the frozen 10d replay.",
        "",
        "| Hold | Aggregate PnL | Return | Trades | Positive windows | EV proxy |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for hold, diag in payload["event_sleeve_replay"]["diagnostic_holds"].items():
        row = diag["aggregate"]
        lines.append(
            f"| {hold}d | ${row['total_pnl']:,.2f} | "
            f"{_fmt_pct(row['total_return_pct_on_100k_base'])} | "
            f"{row['trade_count']} | {row['positive_pnl_windows']}/{row['window_count']} | "
            f"{row['expected_value_score_proxy']} |"
        )
    lines.extend([
        "",
        "## Decision",
        "",
        payload["decision_rationale"],
        "",
        "## Next Action",
        "",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = _load_price_map(SNAPSHOT_FILES)
    events = _load_queue_events(prices)
    primary_candidates = [_candidate_trade(event, prices, PRIMARY_HOLD_DAYS) for event in events]
    primary_by_window = {
        window: _summarize_replay(
            label=window,
            start=WINDOW_RANGES[window][0],
            end=WINDOW_RANGES[window][1],
            trade_candidates=primary_candidates,
            prices=prices,
            hold_days=PRIMARY_HOLD_DAYS,
        )
        for window in WINDOW_ORDER
    }
    diagnostic_holds = {}
    for hold_days in DIAGNOSTIC_HOLD_DAYS:
        candidates = [_candidate_trade(event, prices, hold_days) for event in events]
        by_window = {
            window: _summarize_replay(
                label=window,
                start=WINDOW_RANGES[window][0],
                end=WINDOW_RANGES[window][1],
                trade_candidates=candidates,
                prices=prices,
                hold_days=hold_days,
            )
            for window in WINDOW_ORDER
        }
        diagnostic_holds[str(hold_days)] = {
            "by_window": by_window,
            "aggregate": _aggregate_windows(by_window),
        }

    aggregate = _aggregate_windows(primary_by_window)
    positive_all_windows = aggregate["positive_pnl_windows"] == aggregate["window_count"]
    enough_trades = aggregate["trade_count"] >= 8
    if positive_all_windows and enough_trades:
        decision = "default_off_event_sleeve_positive_not_promoted"
        rationale = (
            "The frozen 10d Form 4 event sleeve made money in all three canonical windows "
            "with transaction costs and fixed capacity. It is still not a production candidate "
            "because the sample is small and this independent sleeve does not yet answer whether "
            "Form 4 should consume scarce A/B core slots."
        )
    else:
        decision = "shadow_only_event_sleeve_inconclusive"
        rationale = (
            "The frozen 10d Form 4 event sleeve did not clear enough multi-window/sample evidence "
            "to justify even a default-off sleeve promotion."
        )

    backfill = _load_json(BACKFILL_SUMMARY, {})
    return {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_discovery",
        "mechanism_family": "form4_standalone_external_event_source",
        "change_type": "form4_default_off_event_sleeve_replay",
        "hypothesis": (
            "A fixed-rule PIT-safe Form 4 event sleeve may earn positive standalone returns "
            "when replayed with fixed capacity, notional, holding period, and transaction costs "
            "across the three canonical windows."
        ),
        "historical_experiment_check": {
            "reusable_mechanisms": {
                "exp-20260503-052": ">=500k meaningful-purchase event definition and fixed 10d primary horizon",
                "exp-20260504-001": "default-off forward queue contract",
                "exp-20260504-005": "PIT-safe historical queue replay and candidate set",
                "exp-20260504-006": "slot-capacity audit showed core-slot replacement evidence is too thin",
                "pilot_sleeve_mechanism": "independent sleeve observation without contaminating core universe or A/B slots",
            },
            "why_not_repeat": (
                "This is not another threshold, owner-role, accepted-trade overlap, or slot replacement test. "
                "It converts the already-frozen queue into a fixed independent event-sleeve replay."
            ),
        },
        "non_ohlcv_data_source": "SEC Form 4 PIT-safe transaction rows",
        "single_causal_variable": "fixed Form 4 event sleeve replay",
        "parameters": {
            "queue_name": QUEUE_NAME,
            "rule_version": RULE_VERSION,
            "min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "primary_hold_days": PRIMARY_HOLD_DAYS,
            "diagnostic_hold_days": list(DIAGNOSTIC_HOLD_DAYS),
            "event_notional": EVENT_NOTIONAL,
            "initial_capital": INITIAL_CAPITAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "selection_order": "entry_date asc, total_purchase_value desc on same day",
        },
        "data_availability": {
            "transaction_file": _repo_rel(latest_form4_transactions_path(DATA_DIR / "non_ohlcv") or ""),
            "backfill_rows_written": backfill.get("rows_written"),
            "pit_safe_count": backfill.get("pit_safe_count"),
            "filings_seen": backfill.get("filings_seen"),
            "open_market_purchase_count": backfill.get("open_market_purchase_count"),
            "tickers_requested": backfill.get("tickers_requested"),
            "tickers_mapped": backfill.get("tickers_mapped"),
            "missing_cik_tickers": backfill.get("missing_cik_tickers"),
            "pit_status": "PIT-safe by usable_trade_date; no filing-date lookahead used",
        },
        "candidate_summary": _candidate_summary(events, primary_candidates),
        "baseline_metrics": BASELINE_METRICS,
        "after_metrics": BASELINE_METRICS,
        "expected_value_score_delta": {
            "late_strong": 0.0,
            "mid_weak": 0.0,
            "old_thin": 0.0,
            "production": 0.0,
        },
        "event_sleeve_replay": {
            "primary": {
                "hold_days": PRIMARY_HOLD_DAYS,
                "by_window": primary_by_window,
                "aggregate": aggregate,
            },
            "diagnostic_holds": diagnostic_holds,
        },
        "candidate_overlap_and_slot_value": {
            "overlap_note": "Independent event sleeve does not consume A/B core slots in this replay.",
            "source_slot_audit": "exp-20260504-006 found direct core-slot replacement evidence too thin.",
            "scarce_slot_opportunity_cost": "not charged to core in this event-sleeve replay; must be revisited before production promotion.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "production_impact": "default_off_shadow_event_sleeve_replay_only",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "gate4": {
            "applicable": False,
            "core_strategy_changed": False,
            "result": "not_applicable_default_off_independent_sleeve",
        },
        "decision_rationale": rationale,
        "next_action": (
            "Treat Form 4 as a positive default-off event-sleeve candidate. The next valid test is "
            "a shared event-sleeve harness with explicit capital allocation and forward queue reporting; "
            "do not wire it into core A/B ranking or scarce slots yet."
        ),
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
    primary = payload["event_sleeve_replay"]["primary"]
    compact = {
        "experiment_id": EXP_ID,
        "decision": payload["decision"],
        "primary_hold_days": PRIMARY_HOLD_DAYS,
        "aggregate": primary["aggregate"],
        "by_window": {
            window: {
                "pnl": primary["by_window"][window]["total_pnl"],
                "return": primary["by_window"][window]["total_return_pct"],
                "sharpe": primary["by_window"][window]["sharpe_daily"],
                "max_drawdown": primary["by_window"][window]["max_drawdown_pct"],
                "trades": primary["by_window"][window]["trade_count"],
                "win_rate": primary["by_window"][window]["win_rate"],
            }
            for window in WINDOW_ORDER
        },
        "output": _repo_rel(OUT_JSON),
        "audit": _repo_rel(AUDIT_MD),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
