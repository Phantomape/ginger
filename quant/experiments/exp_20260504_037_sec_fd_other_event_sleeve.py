"""exp-20260504-037 FD/Other Event negative-reaction sleeve replay.

This alpha-search experiment freezes one SEC metadata branch:
`fd_or_other_event + negative_excess_le_minus_2pct`.  It does not tune reaction
thresholds, add tickers, or change core A/B strategy behavior.  The question is
whether this distinct SEC event family has enough portfolio-level value as a
small satellite sleeve after costs and capacity.
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


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260503_051_sec_filing_reaction_drift import (  # noqa: E402
    SEC_EVENTS_PATH,
    WINDOWS,
    _load_snapshot,
    evaluate_group,
    load_event_groups,
)


EXP_ID = "exp-20260504-037"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "sec_fd_other_event_sleeve.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = REPO_ROOT / "docs" / "non_ohlcv_data_audit" / "sec_fd_other_event_sleeve_20260504.md"

INITIAL_CAPITAL = 100_000.0
EVENT_NOTIONAL = 10_000.0
MAX_EVENT_POSITIONS = 1
HOLD_DAYS = 10
TARGET_CATEGORY = "fd_or_other_event"
TARGET_REACTION_BUCKET = "negative_excess_le_minus_2pct"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe(val) for val in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value).replace("\\", "/")


def _merge_snapshots(snapshots: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for snapshot in snapshots.values():
        for ticker, rows in snapshot.items():
            for row in rows:
                by_ticker_date[str(ticker).upper()][str(row["date"])[:10]] = dict(row)
    return {
        ticker: sorted(rows.values(), key=lambda item: item["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _row_on(prices: dict[str, list[dict[str, Any]]], ticker: str, date_value: str) -> dict[str, Any] | None:
    for row in prices.get(str(ticker).upper(), []):
        if row["date"] == date_value:
            return row
    return None


def _trading_days(prices: dict[str, list[dict[str, Any]]], start: str, end: str) -> list[str]:
    return [
        row["date"]
        for row in prices.get("SPY", [])
        if start <= str(row["date"]) <= end
    ]


def _daily_sharpe(curve: list[tuple[str, float]]) -> float | None:
    returns = []
    for (_, prev), (_, cur) in zip(curve, curve[1:]):
        if prev > 0:
            returns.append(cur / prev - 1.0)
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
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return round(max_dd, 4)


def _pnl_from_trade(trade: dict[str, Any]) -> float:
    for key in ("profit_loss", "pnl", "realized_pnl"):
        value = _round(trade.get(key), 8)
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
        "converged": bool((result.get("convergence") or {}).get("converged")),
        "winning_trades": sum(1 for trade in trades if _pnl_from_trade(trade) > 0),
    }


def _combined_metrics(
    result: dict[str, Any],
    event_curve: list[dict[str, Any]],
    event_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    core_curve = [(str(day), float(equity)) for day, equity in result.get("equity_curve", [])]
    event_pnl_by_day = {row["date"]: float(row["event_pnl"]) for row in event_curve}
    combined_curve = [
        (day, round(core_equity + event_pnl_by_day.get(day, 0.0), 2))
        for day, core_equity in core_curve
    ]
    final_equity = combined_curve[-1][1] if combined_curve else INITIAL_CAPITAL
    total_pnl = final_equity - INITIAL_CAPITAL
    total_return = total_pnl / INITIAL_CAPITAL
    sharpe = _daily_sharpe(combined_curve)
    core_trades = list(result.get("trades") or [])
    core_wins = sum(1 for trade in core_trades if _pnl_from_trade(trade) > 0)
    event_wins = sum(1 for trade in event_trades if float(trade.get("pnl") or 0.0) > 0)
    trade_count = len(core_trades) + len(event_trades)
    return {
        "expected_value_score": round(total_return * sharpe, 4) if sharpe is not None else None,
        "sharpe_daily": sharpe,
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_return, 4),
        "max_drawdown_pct": _max_drawdown(combined_curve),
        "win_rate": round((core_wins + event_wins) / trade_count, 4) if trade_count else None,
        "trade_count": trade_count,
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
        "winning_trades": core_wins + event_wins,
        "core_trade_count": len(core_trades),
        "event_trade_count": len(event_trades),
        "event_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in event_trades), 2),
        "combined_equity_curve": combined_curve,
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
    )
    return {key: _round((after.get(key) or 0.0) - (before.get(key) or 0.0), 6) for key in keys}


def _gate4(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_ev = float(before.get("expected_value_score") or 0.0)
    after_ev = float(after.get("expected_value_score") or 0.0)
    before_pnl = float(before.get("total_pnl") or 0.0)
    after_pnl = float(after.get("total_pnl") or 0.0)
    before_dd = float(before.get("max_drawdown_pct") or 0.0)
    after_dd = float(after.get("max_drawdown_pct") or 0.0)
    before_sharpe = float(before.get("sharpe_daily") or 0.0)
    after_sharpe = float(after.get("sharpe_daily") or 0.0)
    return {
        "ev_delta_pct": round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
        "pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
        "sharpe_daily_delta": round(after_sharpe - before_sharpe, 6),
        "drawdown_improvement_pct": round(before_dd - after_dd, 6),
        "trade_count_increased_with_win_rate_not_down": (
            (after.get("trade_count") or 0) > (before.get("trade_count") or 0)
            and (after.get("win_rate") or 0.0) >= (before.get("win_rate") or 0.0)
        ),
        "passes_material_ev": bool(before_ev and (after_ev - before_ev) / before_ev > 0.10),
        "passes_pnl": bool(before_pnl and (after_pnl - before_pnl) / before_pnl > 0.05),
        "passes_sharpe": after_sharpe - before_sharpe > 0.10,
        "passes_drawdown": before_dd - after_dd > 0.01,
        "passes_trade_count": (
            (after.get("trade_count") or 0) > (before.get("trade_count") or 0)
            and (after.get("win_rate") or 0.0) >= (before.get("win_rate") or 0.0)
        ),
    }


def _candidate_events() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    groups = load_event_groups(SEC_EVENTS_PATH)
    snapshots = {label: _load_snapshot(REPO_ROOT / window["snapshot"]) for label, window in WINDOWS.items()}
    prices = _merge_snapshots(snapshots)
    candidates: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot["SPY"]
        for group in groups:
            event_date = str(group.get("usable_trade_date") or "")[:10]
            if not (window["start"] <= event_date <= window["end"]):
                continue
            row = evaluate_group(group, snapshot, spy_rows, label)
            horizon = (row.get("horizons") or {}).get(f"{HOLD_DAYS}d") or {}
            if (
                row.get("price_status") == "covered"
                and row.get("filing_category") == TARGET_CATEGORY
                and row.get("reaction_bucket") == TARGET_REACTION_BUCKET
                and horizon.get("status") == "valid"
            ):
                candidates.append(row)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in sorted(candidates, key=lambda item: (item["entry_date"], item["reaction_excess_return"], item["ticker"])):
        key = (str(row["ticker"]), str(row["entry_date"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped, prices


def _select_trades(
    candidates: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    active_exits: list[str] = []
    rows = [
        row for row in candidates
        if start <= str(row.get("entry_date") or "")[:10] <= end
    ]
    rows.sort(key=lambda item: (item["entry_date"], item["reaction_excess_return"], item["ticker"]))
    for row in rows:
        entry_date = str(row["entry_date"])[:10]
        active_exits = [exit_date for exit_date in active_exits if exit_date >= entry_date]
        if len(active_exits) >= MAX_EVENT_POSITIONS:
            skipped.append({"ticker": row["ticker"], "entry_date": entry_date, "reason": "slot_full"})
            continue
        horizon = row["horizons"][f"{HOLD_DAYS}d"]
        exit_date = str(horizon["end_date"])[:10]
        entry_row = _row_on(prices, row["ticker"], entry_date)
        exit_row = _row_on(prices, row["ticker"], exit_date)
        if not entry_row or not exit_row or not entry_row.get("open") or not exit_row.get("close"):
            skipped.append({"ticker": row["ticker"], "entry_date": entry_date, "reason": "missing_price"})
            continue
        entry_open = float(entry_row["open"])
        exit_close = float(exit_row["close"])
        shares = EVENT_NOTIONAL / entry_open
        pnl = shares * exit_close - EVENT_NOTIONAL - EVENT_NOTIONAL * ROUND_TRIP_COST_PCT
        selected.append(
            {
                "ticker": row["ticker"],
                "window": row["window"],
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_open": round(entry_open, 4),
                "exit_close": round(exit_close, 4),
                "shares": shares,
                "notional": EVENT_NOTIONAL,
                "pnl": round(pnl, 2),
                "net_return_pct": round(pnl / EVENT_NOTIONAL, 6),
                "reaction_excess_return": row.get("reaction_excess_return"),
                "reaction_bucket": row.get("reaction_bucket"),
                "filing_count": row.get("filing_count"),
                "form_bases": row.get("form_bases"),
                "eight_k_item_codes": row.get("eight_k_item_codes"),
                "accession_numbers": row.get("accession_numbers"),
            }
        )
        active_exits.append(exit_date)
    return selected, skipped


def _event_curve(
    trades: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    *,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    entries_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exits_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        entries_by_day[trade["entry_date"]].append(trade)
        exits_by_day[trade["exit_date"]].append(trade)

    cash = INITIAL_CAPITAL
    active: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    for day in _trading_days(prices, start, end):
        for trade in entries_by_day.get(day, []):
            cash -= EVENT_NOTIONAL
            active.append(trade)
        for trade in exits_by_day.get(day, []):
            close = (_row_on(prices, trade["ticker"], day) or {}).get("close")
            if close is not None:
                cash += float(trade["shares"]) * float(close) - EVENT_NOTIONAL * ROUND_TRIP_COST_PCT
        if exits_by_day.get(day):
            exit_keys = {(trade["ticker"], trade["entry_date"], trade["exit_date"]) for trade in exits_by_day[day]}
            active = [
                trade for trade in active
                if (trade["ticker"], trade["entry_date"], trade["exit_date"]) not in exit_keys
            ]
        market_value = 0.0
        for trade in active:
            close = (_row_on(prices, trade["ticker"], day) or {}).get("close")
            if close is not None:
                market_value += float(trade["shares"]) * float(close)
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


def _trade_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_window[str(trade["window"])].append(trade)
    total_abs = sum(abs(float(trade["pnl"])) for trade in trades)
    top_abs = max(trades, key=lambda trade: abs(float(trade["pnl"])), default=None)
    return {
        "trade_count": len(trades),
        "total_pnl": round(sum(float(trade["pnl"]) for trade in trades), 2),
        "win_rate": round(sum(1 for trade in trades if float(trade["pnl"]) > 0) / len(trades), 4) if trades else None,
        "avg_net_return_pct": _round(statistics.mean([trade["net_return_pct"] for trade in trades]), 6) if trades else None,
        "top_abs_trade_concentration": {
            "ticker": top_abs.get("ticker") if top_abs else None,
            "pnl": top_abs.get("pnl") if top_abs else None,
            "share_of_abs_pnl": round(abs(float(top_abs["pnl"])) / total_abs, 4) if top_abs and total_abs else None,
        },
        "by_window": {
            label: {
                "trade_count": len(rows),
                "total_pnl": round(sum(float(row["pnl"]) for row in rows), 2),
                "win_rate": round(sum(1 for row in rows if float(row["pnl"]) > 0) / len(rows), 4) if rows else None,
                "avg_net_return_pct": _round(statistics.mean([row["net_return_pct"] for row in rows]), 6) if rows else None,
            }
            for label, rows in sorted(by_window.items())
        },
    }


def build_payload() -> dict[str, Any]:
    universe = get_universe()
    candidates, prices = _candidate_events()
    before: dict[str, dict[str, Any]] = {}
    after: dict[str, dict[str, Any]] = {}
    event_details: dict[str, Any] = {}
    all_event_trades: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        selected, skipped = _select_trades(candidates, prices, start=window["start"], end=window["end"])
        curve = _event_curve(selected, prices, start=window["start"], end=window["end"])
        before[label] = _core_metrics(result)
        after[label] = _combined_metrics(result, curve, selected)
        all_event_trades.extend(selected)
        event_details[label] = {
            "candidate_count": sum(1 for row in candidates if window["start"] <= str(row["entry_date"]) <= window["end"]),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": dict(Counter(row["reason"] for row in skipped)),
            "selected_trades": selected,
            "skipped_candidates": skipped,
            "event_equity_curve_tail": curve[-20:],
        }

    deltas = {label: _delta(before[label], after[label]) for label in WINDOWS}
    gate_by_window = {label: _gate4(before[label], after[label]) for label in WINDOWS}
    aggregate = {
        "baseline_ev_sum": round(sum(float(row["expected_value_score"] or 0.0) for row in before.values()), 4),
        "overlay_ev_sum": round(sum(float(row["expected_value_score"] or 0.0) for row in after.values()), 4),
        "baseline_pnl_sum": round(sum(float(row["total_pnl"] or 0.0) for row in before.values()), 2),
        "overlay_pnl_sum": round(sum(float(row["total_pnl"] or 0.0) for row in after.values()), 2),
        "windows_ev_improved": sum(1 for label in WINDOWS if (after[label]["expected_value_score"] or 0) > (before[label]["expected_value_score"] or 0)),
        "windows_ev_regressed": sum(1 for label in WINDOWS if (after[label]["expected_value_score"] or 0) < (before[label]["expected_value_score"] or 0)),
        "windows_material_ev_or_pnl": sum(
            1 for label in WINDOWS
            if gate_by_window[label]["passes_material_ev"] or gate_by_window[label]["passes_pnl"]
        ),
        "windows_trade_count_win_rate_gate": sum(1 for label in WINDOWS if gate_by_window[label]["passes_trade_count"]),
    }
    aggregate["ev_delta_sum"] = round(aggregate["overlay_ev_sum"] - aggregate["baseline_ev_sum"], 4)
    aggregate["ev_delta_pct"] = round(aggregate["ev_delta_sum"] / aggregate["baseline_ev_sum"], 6) if aggregate["baseline_ev_sum"] else None
    aggregate["pnl_delta"] = round(aggregate["overlay_pnl_sum"] - aggregate["baseline_pnl_sum"], 2)
    aggregate["pnl_delta_pct"] = round(aggregate["pnl_delta"] / aggregate["baseline_pnl_sum"], 6) if aggregate["baseline_pnl_sum"] else None

    material = aggregate["windows_material_ev_or_pnl"] >= 2 and aggregate["windows_ev_regressed"] == 0
    sample_positive = aggregate["windows_ev_improved"] >= 2 and aggregate["windows_ev_regressed"] == 0
    if material:
        status = "accepted_requires_followup"
        decision = "accepted_requires_trade_enabled_sleeve_parity"
        rationale = (
            "The FD/Other Event negative-reaction satellite overlay cleared material fixed-window checks, "
            "but cannot be enabled until a shared trade-enabled event-sleeve adapter exists in production and backtest."
        )
    elif sample_positive:
        status = "rejected"
        decision = "positive_sample_not_material_no_promotion"
        rationale = (
            "The FD/Other Event negative-reaction overlay improved the majority read without EV regression, "
            "but the effect was below material Gate 4 thresholds; keep it as observe-only event alpha."
        )
    else:
        status = "rejected"
        decision = "rejected_overlay_no_stable_alpha"
        rationale = (
            "The FD/Other Event negative-reaction overlay did not improve the fixed windows enough to justify "
            "promotion or additional production complexity."
        )

    return {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "mechanism_family": "sec_fd_other_event_negative_reaction_satellite_overlay",
        "change_type": "non_ohlcv_event_sleeve_alpha_search",
        "hypothesis": (
            "SEC 8-K FD/Other Event filings with a strong negative first reaction may capture temporary "
            "event uncertainty that mean-reverts over the next 10 trading days as a small satellite sleeve."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension_event_sleeve",
            "entry_or_ranking": "entry",
            "why_this_now": (
                "LLM soft-ranking is still sample-limited; this uses tracked PIT-safe SEC metadata and avoids "
                "recently rejected earnings/results, agreement/debt, leadership-change, residual other-filing, "
                "Form 4, macro ETF, add-on, and BEAR_SHALLOW surfaces."
            ),
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260504-015/026": "leadership-change negative-reaction branch was tested and sleeve-rejected",
                "exp-20260504-019": "agreement/debt branch was rejected",
                "exp-20260504-022/023": "residual other-filing mild-negative branch was shadow-only/sample-limited",
                "exp-20260504-028": "macro ETF ticker-list expansion was rejected",
                "exp-20260504-034": "Form 4 satellite overlay was positive but immaterial",
                "exp-20260504-036": "BEAR_SHALLOW risk-budget surface was immaterial",
            },
            "why_not_simple_repeat": (
                "This freezes a distinct SEC `fd_or_other_event` category from the tracked filing metadata; "
                "it is not a nearby reaction-threshold sweep or a retest of leadership/agreement/residual packets."
            ),
            "mechanism_insight_guardrails": [
                "No keyword or LLM semantic grading is used.",
                "No reaction threshold or holding-period sweep is performed.",
                "No production entry, ranking, sizing, or order path changes.",
            ],
        },
        "parameters": {
            "single_causal_variable": f"{TARGET_CATEGORY} + {TARGET_REACTION_BUCKET} as a 10k satellite overlay",
            "filing_category": TARGET_CATEGORY,
            "reaction_bucket": TARGET_REACTION_BUCKET,
            "hold_days": HOLD_DAYS,
            "event_notional": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry": "next trading-day open after first reaction day",
            "exit": "10 trading-day horizon close",
            "locked_variables": [
                "core A/B universe",
                "core signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "reaction thresholds",
                "holding period",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": deltas,
        "aggregate": aggregate,
        "gate4": {
            "rule": "EV first; material if EV >10%, Sharpe >0.1, DD -1pp, PnL >5%, or trade count rises with win rate not down",
            "by_window": gate_by_window,
            "material_windows": aggregate["windows_material_ev_or_pnl"],
            "trade_count_win_rate_windows": aggregate["windows_trade_count_win_rate_gate"],
        },
        "coverage": {
            "candidate_count": len(candidates),
            "candidate_by_window": dict(Counter(row["window"] for row in candidates)),
            "dedupe_key": "ticker + entry_date",
            "source": _repo_rel(SEC_EVENTS_PATH),
        },
        "event_details": event_details,
        "event_trade_summary": _trade_summary(all_event_trades),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_accepted": "trade-enabled sleeve adapter must be shared before production use",
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking remains blocked by sparse production-aligned outcome joins.",
        },
        "decision_rationale": rationale,
        "rejection_reason": None if status != "rejected" else rationale,
        "next_action": (
            "Do not promote. A valid retry needs forward event-queue samples, richer event semantics, "
            "or material three-window overlay lift with a shared trade-enabled adapter."
            if status == "rejected"
            else "Implement shared default-off trade-enabled sleeve parity before any live capital."
        ),
        "related_files": [
            _repo_rel(__file__),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(AUDIT_MD),
            _repo_rel(SEC_EVENTS_PATH),
        ],
    }


def _fmt_pct(value: Any) -> str:
    number = _round(value, 6)
    return "n/a" if number is None else f"{number * 100:.2f}%"


def build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# SEC FD/Other Event Sleeve Replay",
        "",
        f"Experiment: `{EXP_ID}`",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Trades | Win rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']} | {after['expected_value_score']} | "
            f"{delta['expected_value_score']} | {before['total_pnl']} | {after['total_pnl']} | "
            f"{after['event_pnl']} | {after['event_trade_count']} | {_fmt_pct(after['win_rate'])} |"
        )
    summary = payload["event_trade_summary"]
    concentration = summary["top_abs_trade_concentration"]
    lines.extend(
        [
            "",
            "## Event Sleeve",
            "",
            f"- Candidate count: `{payload['coverage']['candidate_count']}`",
            f"- Selected trades: `{summary['trade_count']}`",
            f"- Event PnL: `{summary['total_pnl']}`",
            f"- Event win rate: `{_fmt_pct(summary['win_rate'])}`",
            (
                f"- Top absolute event contribution: `{concentration['ticker']}` "
                f"{concentration['pnl']} ({_fmt_pct(concentration['share_of_abs_pnl'])} of abs event PnL)"
            ),
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "title": "SEC FD/Other Event sleeve replay",
            "summary": payload["decision_rationale"],
            "aggregate": payload["aggregate"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(AUDIT_MD, build_report(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "coverage": payload["coverage"],
                "event_trade_summary": payload["event_trade_summary"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
