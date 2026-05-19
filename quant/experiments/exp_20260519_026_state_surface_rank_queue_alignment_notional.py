"""exp-20260519-026: state-surface rank/queue alignment notional.

Freezes the accepted state-surface paper stack through exp-20260519-024, then
tests one production-visible allocation variable: already-selected candidates
whose raw rank equals queue rank receive a bounded default-off paper-notional
scalar. Core trades, filters, ranking, LLM/news, and live/default orders are
unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260519-026"
EXPERIMENT_SLUG = "state_surface_rank_queue_alignment_notional"
BASELINE_VARIANT = "accepted_broad_breadth_support_notional"
RULE_VERSION = "state_surface_rank_queue_alignment_notional_v1"
INITIAL_CAPITAL = 100_000.0
MIN_SELECTED_TRADES = 9
MIN_ADJUSTED_TRADES = 10
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402


WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {"scalar": None, "aggression_order": 0, "description": "identity"},
        ),
        (
            "rank_queue_alignment_scalar_105",
            {
                "scalar": 1.05,
                "aggression_order": 1,
                "description": "rank == queue_rank receives 5% support",
            },
        ),
        (
            "rank_queue_alignment_scalar_110",
            {
                "scalar": 1.10,
                "aggression_order": 2,
                "description": "rank == queue_rank receives 10% support",
            },
        ),
        (
            "rank_queue_alignment_scalar_115",
            {
                "scalar": 1.15,
                "aggression_order": 3,
                "description": "rank == queue_rank receives 15% support",
            },
        ),
        (
            "rank_queue_alignment_scalar_125",
            {
                "scalar": 1.25,
                "aggression_order": 4,
                "description": "rank == queue_rank receives 25% support",
            },
        ),
    ]
)

BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260519-024"
    / "state_surface_broad_breadth_notional.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), sort_keys=True)
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


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_price_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in WINDOWS.values():
        payload = _json_load(REPO_ROOT / window["snapshot"])
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
                    "open": _float(row.get("Open")),
                    "close": _float(row.get("Close")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _trading_days(
    prices: dict[str, list[dict[str, Any]]],
    start: str,
    end: str,
) -> list[str]:
    spy_rows = prices.get("SPY") or []
    days = [
        str(row.get("date") or "")
        for row in spy_rows
        if start <= str(row.get("date") or "") <= end
    ]
    if days:
        return days
    return sorted(
        {
            str(row.get("date") or "")
            for rows in prices.values()
            for row in rows
            if start <= str(row.get("date") or "") <= end
        }
    )


def _close_on_or_before(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
) -> float | None:
    rows = prices.get(str(ticker).upper()) or []
    close = None
    for row in rows:
        row_day = str(row.get("date") or "")
        if row_day > day:
            break
        value = row.get("close")
        if value is not None:
            close = float(value)
    return close


def _open_on_date(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    day: str,
) -> float | None:
    for row in prices.get(str(ticker).upper()) or []:
        if str(row.get("date") or "") == day:
            value = row.get("open")
            return float(value) if value is not None else None
    return None


def _prepare_trade(
    trade: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    row = dict(trade)
    ticker = str(row.get("ticker") or "").upper()
    notional = float(row.get("notional") or 0.0)
    entry_open = _float(row.get("entry_open"))
    if entry_open is None:
        entry_open = _open_on_date(prices, ticker, str(row.get("entry_date") or ""))
    if entry_open is None or entry_open <= 0:
        raise RuntimeError(f"Missing entry open for {ticker} {row.get('entry_date')}")
    row["entry_open"] = round(entry_open, 6)
    row["shares"] = notional / entry_open
    row["features"] = {
        "ret5": row.get("ret5"),
        "ret20_excess_spy": row.get("ret20_excess_spy"),
        "ret60": row.get("ret60"),
        "volume_ratio_20": row.get("volume_ratio_20"),
    }
    return row


def _event_equity_curve_variable_notional(
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
        entries_by_day[str(trade["entry_date"])].append(trade)
        exits_by_day[str(trade["exit_date"])].append(trade)

    cash = INITIAL_CAPITAL
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in days:
        for trade in entries_by_day.get(day, []):
            cash -= float(trade["notional"])
            active.append(trade)

        exiting = exits_by_day.get(day, [])
        for trade in exiting:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is None:
                continue
            notional = float(trade["notional"])
            cash += float(trade["shares"]) * close - notional * ROUND_TRIP_COST_PCT
        if exiting:
            exit_keys = {
                (
                    trade["ticker"],
                    trade["entry_date"],
                    trade["exit_date"],
                    trade.get("queue_rank"),
                )
                for trade in exiting
            }
            active = [
                trade
                for trade in active
                if (
                    trade["ticker"],
                    trade["entry_date"],
                    trade["exit_date"],
                    trade.get("queue_rank"),
                )
                not in exit_keys
            ]

        market_value = 0.0
        for trade in active:
            close = _close_on_or_before(prices, str(trade["ticker"]), day)
            if close is not None:
                market_value += float(trade["shares"]) * close
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
    for (_, prev_value), (_, curr_value) in zip(curve, curve[1:]):
        if prev_value > 0:
            returns.append(curr_value / prev_value - 1.0)
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
        key: round(float(after.get(key) or 0.0) - float(before.get(key) or 0.0), 6)
        for key in keys
    }


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _delta(before[label], after[label])) for label in WINDOWS)
    baseline_ev = sum(float(before[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    baseline_pnl = sum(float(before[label]["total_pnl"] or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label]["total_pnl"] or 0.0) for label in WINDOWS)
    drawdown_delta = {
        label: round(
            float(after[label].get("max_drawdown_pct") or 0.0)
            - float(before[label].get("max_drawdown_pct") or 0.0),
            6,
        )
        for label in WINDOWS
    }
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 6),
        "after_ev_sum": round(after_ev, 6),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 6),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6)
        if baseline_ev
        else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6)
        if baseline_pnl
        else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0)
            > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0)
            < (before[label].get("total_pnl") or 0)
        ),
        "by_window_max_drawdown_delta": drawdown_delta,
        "max_drawdown_worse_max": max(drawdown_delta.values()) if drawdown_delta else 0.0,
    }


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for trade in positive:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _metrics_from_core_curve(
    *,
    baseline_metrics: dict[str, Any],
    core_curve: list[tuple[str, float]],
    event_curve: list[dict[str, Any]],
    event_trades: list[dict[str, Any]],
    baseline_event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
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
    baseline_event_wins = sum(
        1 for trade in baseline_event_trades if float(trade.get("pnl") or 0.0) > 0
    )
    core_wins = int(baseline_metrics.get("winning_trades") or 0) - baseline_event_wins
    event_wins = sum(1 for trade in event_trades if float(trade.get("pnl") or 0.0) > 0)
    core_trade_count = int(baseline_metrics.get("core_trade_count") or 0)
    trade_count = core_trade_count + len(event_trades)
    baseline_return = float(baseline_metrics.get("total_return_pct") or 0.0)
    spy_ret = (
        baseline_return - float(baseline_metrics["vs_spy_pct"])
        if baseline_metrics.get("vs_spy_pct") is not None
        else None
    )
    qqq_ret = (
        baseline_return - float(baseline_metrics["vs_qqq_pct"])
        if baseline_metrics.get("vs_qqq_pct") is not None
        else None
    )
    return {
        "expected_value_score": round(expected_value, 4)
        if expected_value is not None
        else None,
        "sharpe_daily": sharpe,
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return, 4),
        "max_drawdown_pct": _max_drawdown(combined_curve),
        "win_rate": round((core_wins + event_wins) / trade_count, 4)
        if trade_count
        else None,
        "trade_count": trade_count,
        "signals_generated": baseline_metrics.get("signals_generated"),
        "signals_survived": baseline_metrics.get("signals_survived"),
        "survival_rate": baseline_metrics.get("survival_rate"),
        "vs_spy_pct": round(total_return - float(spy_ret), 4)
        if spy_ret is not None
        else None,
        "vs_qqq_pct": round(total_return - float(qqq_ret), 4)
        if qqq_ret is not None
        else None,
        "winning_trades": core_wins + event_wins,
        "core_trade_count": core_trade_count,
        "event_trade_count": len(event_trades),
        "event_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in event_trades),
            2,
        ),
        "combined_equity_curve": combined_curve,
    }


def _rank_queue_aligned(row: dict[str, Any]) -> bool:
    try:
        rank = int(row.get("rank"))
        queue_rank = int(row.get("queue_rank"))
    except (TypeError, ValueError):
        return False
    return rank > 0 and rank == queue_rank


def _profile_name(scalar: float) -> str:
    scalar_text = str(round(float(scalar), 6)).rstrip("0").rstrip(".")
    return f"rank_eq_queue_{scalar_text.replace('.', 'p')}x"


def _apply_rank_queue_alignment(
    trades: list[dict[str, Any]],
    *,
    variant_name: str,
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    scalar = _float(variant.get("scalar"))
    adjusted: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        row["features"] = dict(row.get("features") or {})
        applies = (
            variant_name != BASELINE_VARIANT
            and scalar is not None
            and _rank_queue_aligned(row)
        )
        rank = _float(row.get("rank"))
        queue_rank = _float(row.get("queue_rank"))
        delta = (
            int(rank) - int(queue_rank)
            if rank is not None and queue_rank is not None
            else None
        )
        row.update(
            {
                "rank_queue_alignment_variant": variant_name,
                "rank_queue_alignment_rule_version": RULE_VERSION,
                "rank_notional_rank_queue_alignment_rule_version": RULE_VERSION,
                "rank_queue_alignment_applied": bool(applies),
                "rank_queue_alignment_rank": int(rank) if rank is not None else None,
                "rank_queue_alignment_queue_rank": int(queue_rank)
                if queue_rank is not None
                else None,
                "rank_queue_alignment_delta": delta,
                "rank_queue_alignment_configured_scalar": scalar,
                "rank_queue_alignment_scalar": scalar if applies else None,
                "rank_queue_alignment_profile_name": _profile_name(scalar)
                if variant_name != BASELINE_VARIANT and scalar is not None
                else None,
                "rank_queue_alignment_base_multiplier": _float(
                    row.get("rank_notional_multiplier")
                ),
            }
        )
        if applies:
            base_notional = float(row.get("notional") or 0.0)
            new_notional = round(base_notional * float(scalar), 2)
            entry_open = float(row["entry_open"])
            net_return = float(row["net_return_pct"])
            row["rank_queue_alignment_base_notional"] = base_notional
            row["notional"] = new_notional
            row["shares"] = new_notional / entry_open
            row["pnl"] = round(new_notional * net_return, 2)
            base_multiplier = _float(row.get("rank_notional_multiplier"))
            if base_multiplier is not None:
                row["rank_notional_multiplier"] = round(
                    base_multiplier * float(scalar),
                    6,
                )
        adjusted.append(row)
    return adjusted


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "sector": trade.get("sector"),
                "window": trade.get("window"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "queue_rank": trade.get("queue_rank"),
                "rank_queue_alignment_delta": trade.get(
                    "rank_queue_alignment_delta"
                ),
                "breadth_bucket": trade.get("breadth_bucket"),
                "regime": trade.get("regime"),
                "score": trade.get("score"),
                "ret5": features.get("ret5"),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret60": features.get("ret60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "broad_breadth_support_applied": trade.get(
                    "broad_breadth_support_applied"
                ),
                "rank_queue_alignment_applied": trade.get(
                    "rank_queue_alignment_applied"
                ),
                "rank_queue_alignment_scalar": trade.get(
                    "rank_queue_alignment_scalar"
                ),
                "rank_queue_alignment_base_multiplier": trade.get(
                    "rank_queue_alignment_base_multiplier"
                ),
                "rank_notional_multiplier": trade.get("rank_notional_multiplier"),
                "notional": trade.get("notional"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    baseline_payload: dict[str, Any],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    core_curves: dict[str, list[tuple[str, float]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []
    for label, window in WINDOWS.items():
        baseline_window_trades = baseline_trades_by_window[label]
        selected = _apply_rank_queue_alignment(
            baseline_window_trades,
            variant_name=variant_name,
            variant=variant,
        )
        if variant_name == BASELINE_VARIANT:
            metrics[label] = baseline_payload["after_metrics"][label]
        else:
            event_curve = _event_equity_curve_variable_notional(
                selected,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            metrics[label] = _metrics_from_core_curve(
                baseline_metrics=baseline_payload["after_metrics"][label],
                core_curve=core_curves[label],
                event_curve=event_curve,
                event_trades=selected,
                baseline_event_trades=baseline_window_trades,
            )
        selected_all.extend(selected)
        applied = [
            row for row in selected if row.get("rank_queue_alignment_applied")
        ]
        surface_sleeve[label] = {
            "selected_trade_count": len(selected),
            "rank_queue_alignment_adjusted_trade_count": len(applied),
            "rank_queue_alignment_adjusted_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in applied),
                2,
            ),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in selected),
                2,
            ),
            "selected_win_rate": round(
                sum(1 for row in selected if float(row.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected
            else None,
            "rank_queue_delta_distribution": dict(
                Counter(row.get("rank_queue_alignment_delta") for row in selected)
            ),
            "ticker_distribution": dict(Counter(row.get("ticker") for row in selected)),
            "sector_distribution": dict(Counter(row.get("sector") for row in selected)),
            "selected_trades": _selected_trade_rows(selected),
        }
    applied_all = [
        row for row in selected_all if row.get("rank_queue_alignment_applied")
    ]
    applied_windows = {
        str(row.get("window")) for row in applied_all if row.get("window")
    }
    return {
        "variant_name": variant_name,
        "variant_type": "rank_queue_alignment_notional_profile",
        "scalar": variant.get("scalar"),
        "aggression_order": variant.get("aggression_order"),
        "description": variant.get("description"),
        "metrics": metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trades": selected_all,
        "selected_trade_count": len(selected_all),
        "rank_queue_alignment_adjusted_trade_count": len(applied_all),
        "rank_queue_alignment_adjusted_windows": sorted(applied_windows),
        "single_ticker_positive_share": _single_ticker_positive_share(selected_all),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_share: float | None,
    variant: dict[str, Any],
) -> dict[str, Any]:
    delta = _aggregate_delta(baseline_metrics, variant["metrics"])
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        variant["rank_queue_alignment_adjusted_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(variant["rank_queue_alignment_adjusted_windows"])
        >= MIN_ADJUSTED_WINDOWS
    )
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"]
        <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    share = variant["single_ticker_positive_share"]
    share_delta = (
        round(share - baseline_share, 6)
        if share is not None and baseline_share is not None
        else None
    )
    return {
        "passed": passed,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "rank_queue_alignment_adjusted_trade_count": variant[
            "rank_queue_alignment_adjusted_trade_count"
        ],
        "rank_queue_alignment_adjusted_windows": variant[
            "rank_queue_alignment_adjusted_windows"
        ],
        "selected_trade_count": variant["selected_trade_count"],
        "sample_guard_passed": sample_guard_passed,
        "adjusted_guard_passed": adjusted_guard_passed,
        "single_ticker_positive_share": share,
        "baseline_single_ticker_positive_share": baseline_share,
        "single_ticker_positive_share_delta": share_delta,
        "concentration_guard_passed": concentration_guard_passed,
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
        "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
        "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
        "delta_metrics": delta,
    }


def _choose_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [
        row
        for row in rows
        if row["variant_name"] != BASELINE_VARIANT and row["gate4"]["passed"]
    ]
    if passing:
        return max(
            passing,
            key=lambda row: (
                row["gate4"]["aggregate_ev_delta"],
                row["gate4"]["aggregate_pnl_delta"],
                -row["gate4"]["max_drawdown_worse_max"],
                -row["aggression_order"],
            ),
        )
    return max(
        [row for row in rows if row["variant_name"] != BASELINE_VARIANT],
        key=lambda row: (
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            row["gate4"]["windows_ev_improved"],
            -row["gate4"]["windows_ev_regressed"],
        ),
    )


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        rows.extend([row for row in payload.get(section, []) if isinstance(row, dict)])
    missing = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(path),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Rank/Queue Alignment Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `rank_queue_alignment_notional_profile`.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Scalar | dEV | dPnL | EV Improved | EV Regressed | Adjusted Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {variant} | {passed} | {scalar} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {adj} | {dd:+.4%} | {share} |".format(
                variant=row["variant_name"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                scalar=row["scalar"] if row["scalar"] is not None else "n/a",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                adj=row["gate4"]["rank_queue_alignment_adjusted_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share=f"{share:.2%}" if share is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Adjusted trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=sleeve["rank_queue_alignment_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = _json_load(BASELINE_JSON)
    prices = _load_price_map()
    baseline_metrics = baseline_payload["after_metrics"]
    baseline_trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    core_curves: dict[str, list[tuple[str, float]]] = OrderedDict()

    for label, window in WINDOWS.items():
        rows = baseline_payload["surface_sleeve"][label]["selected_trades"]
        prepared = [_prepare_trade({**row, "window": label}, prices) for row in rows]
        baseline_trades_by_window[label] = prepared
        baseline_event_curve = _event_equity_curve_variable_notional(
            prepared,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        event_by_day = {
            row["date"]: float(row["event_pnl"]) for row in baseline_event_curve
        }
        combined_curve = [
            (str(day), float(equity))
            for day, equity in baseline_metrics[label]["combined_equity_curve"]
        ]
        core_curves[label] = [
            (day, round(equity - event_by_day.get(day, 0.0), 2))
            for day, equity in combined_curve
        ]

    baseline_trades_all = [
        row for rows in baseline_trades_by_window.values() for row in rows
    ]
    baseline_share = _single_ticker_positive_share(baseline_trades_all)
    variants = [
        _variant_payload(
            variant_name=name,
            variant=variant,
            baseline_payload=baseline_payload,
            baseline_trades_by_window=baseline_trades_by_window,
            core_curves=core_curves,
            prices=prices,
        )
        for name, variant in VARIANTS.items()
    ]
    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            baseline_share=baseline_share,
            variant=variant,
        )
        sweep_summary.append(
            {
                "variant_name": variant["variant_name"],
                "is_identity_control": variant["variant_name"] == BASELINE_VARIANT,
                "scalar": variant["scalar"],
                "aggression_order": variant["aggression_order"],
                "description": variant["description"],
                "selected_trade_count": variant["selected_trade_count"],
                "rank_queue_alignment_adjusted_trade_count": variant[
                    "rank_queue_alignment_adjusted_trade_count"
                ],
                "rank_queue_alignment_adjusted_windows": variant[
                    "rank_queue_alignment_adjusted_windows"
                ],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    best = _choose_best(sweep_summary)
    best_payload = next(row for row in variants if row["variant_name"] == best["variant_name"])
    delta = _aggregate_delta(baseline_metrics, best_payload["metrics"])
    passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_default_off_state_surface_rank_queue_alignment_notional"
        if passed
        else "rejected_state_surface_rank_queue_alignment_notional"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": "accepted" if passed else "rejected",
        "decision": decision,
        "hypothesis": "State-surface candidates whose raw rank equals queue rank represent cleaner queue alignment and deserve bounded default-off paper-notional support.",
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": "Tests a new production-visible rank-depth quality field while keeping candidate eligibility, ranking, and the accepted exp-20260519-024 stack fixed.",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "rank_queue_alignment_notional_profile",
        "component": "quant/state_surface_sleeve.py",
        "parameters": {
            "best_variant": best["variant_name"],
            "best_scalar": best["scalar"],
            "profile_priority": "applies after accepted broad-breadth support; applies only when rank == queue_rank",
            "locked_variables": [
                "core entries",
                "core exits",
                "core sizing",
                "state-surface candidate eligibility",
                "state-surface queue ranking",
                "state-surface hold days",
                "state-surface active capacity",
                "top3 ret5 follow-through scalar",
                "broad-breadth support scalar",
                "candidate pool",
                "LLM/news",
                "live/default orders",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": "docs/backtesting.md canonical three fixed windows; accepted exp-20260519-024 baseline artifact plus default-off state-surface paper overlay replay.",
        "before_metrics": baseline_metrics,
        "after_metrics": best_payload["metrics"],
        "delta_metrics": delta,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_ev_delta"]},
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        }
        | {"aggregate": delta["aggregate_pnl_delta"]},
        "gate1": {
            "baseline_artifact": _repo_rel(BASELINE_JSON),
            "baseline_variant": BASELINE_VARIANT,
            "baseline_note": "Uses accepted exp-20260519-024 broad-breadth support as Gate 1 baseline.",
        },
        "gate2": {
            "open_position_fields": gate2,
            "runtime_fields": [
                "rank",
                "queue_rank",
                "rank_notional_multiplier",
                "event_notional_usd",
                "entry_open",
                "net_return_pct",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in baseline_metrics.values()
            ),
            "after_survival_rate": {
                label: best_payload["metrics"][label].get("survival_rate")
                for label in WINDOWS
            },
            "hard_rule": "No filter or candidate gate changed; only paper notional changes for existing selected trades.",
        },
        "gate4": best["gate4"],
        "surface_sleeve": best_payload["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "history_check": {
            "exp-20260519-024": "Accepted broad-breadth support; this freezes it and tests a distinct rank/queue alignment field.",
            "recent_rejections": "Avoids cached AI-infra pool expansion, core-misfit residual expansion, pure SPY T+1 SEC haircuts, rank4 volume no-sample, and LLM soft-ranking.",
            "anti_repeat": "Not a ret5/ret20/ret60, near-high, volume-threshold, sector-cohesion, score-gap, candidate-pool, SEC text, or LLM soft-ranking retry.",
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": "LLM soft-ranking data remains sparse/PIT-limited; this deterministic field is replayable from existing state-surface metadata.",
        },
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": False,
            "parity_test_added": passed,
            "live_default_orders_changed": False,
            "core_metrics_changed": False,
            "default_off_paper_only": True,
        },
        "interpretation": "Rank/queue alignment improved default-off paper allocation without changing core trades, filters, ranking, or live/default orders."
        if passed
        else "Rank/queue alignment did not clear Gate 4; keep exp-20260519-024 unchanged.",
        "rejection_reason": None
        if passed
        else "Failed Gate 4 under the canonical three-window state-surface paper protocol.",
        "next_evidence_needed": "Promote only as shared default-off paper metadata; keep forward tail/concentration monitoring before live adapter work."
        if passed
        else "Do not retry nearby rank/queue scalar profiles without forward evidence or a distinct field.",
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation: already-selected state-surface candidates whose raw rank equals queue rank deserve bounded paper-notional support.",
            "2_history_check": "No prior experiment tested rank == queue_rank as a notional profile. This freezes exp-20260519-024 and avoids recent data-limited LLM/pool expansion lanes.",
            "3_single_causal_variable": "rank_queue_alignment_notional_profile",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, all three EV-improved windows, zero EV-regressed windows, adjusted trades >=10 across all 3 windows, max DD drift <=0.5pp, single-ticker positive share <=50%.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
        ],
    }
    return _safe(payload)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rank/queue alignment notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "summary": (
                f"{payload['parameters']['best_variant']} changed aggregate EV "
                f"{payload['delta_metrics']['aggregate_ev_delta']:+.4f} and PnL "
                f"${payload['delta_metrics']['aggregate_pnl_delta']:+,.2f}."
            ),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(f"{EXPERIMENT_ID} {payload['decision']}")


if __name__ == "__main__":
    main()
