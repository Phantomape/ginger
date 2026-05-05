"""exp-20260504-039 SEC governance/procedural event overlay replay.

This alpha-search experiment freezes the strongest residual SEC 8-K semantic
cells from exp-20260504-023 and tests them as one fixed-notional event sleeve.
It does not tune reaction thresholds, change the core A/B stack, or alter
production orders. If the sleeve clears the three-window gate, a shared
trade-enabled event adapter is still required before any promotion.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
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


EXP_ID = "exp-20260504-039"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "sec_governance_procedural_overlay.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_governance_procedural_overlay_20260504.md"
)

INITIAL_CAPITAL = 100_000.0
EVENT_NOTIONAL = 10_000.0
MAX_EVENT_POSITIONS = 1
HOLD_DAYS = 10
TARGET_CATEGORY = "other_sec_filing"
TARGET_CELLS = {
    ("shareholder_vote", "negative_excess_0_to_minus_2pct"),
    ("charter_or_securities_change", "positive_excess_0_to_2pct"),
    ("exhibit_only", "negative_excess_0_to_minus_2pct"),
    ("exhibit_only", "positive_excess_0_to_2pct"),
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe(val) for val in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def semantic_subcategory(row: dict[str, Any]) -> str:
    items = {str(item) for item in row.get("eight_k_item_codes") or []}
    if "5.07" in items:
        return "shareholder_vote"
    if items & {"5.03", "3.02", "3.03"}:
        return "charter_or_securities_change"
    if items == {"9.01"}:
        return "exhibit_only"
    return "misc_other"


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


def _candidate_events() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    groups = load_event_groups(SEC_EVENTS_PATH)
    snapshots = {label: _load_snapshot(REPO_ROOT / window["snapshot"]) for label, window in WINDOWS.items()}
    prices = _merge_snapshots(snapshots)
    candidates: list[dict[str, Any]] = []
    evaluated_count = 0
    covered_count = 0

    for label, window in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot["SPY"]
        for group in groups:
            event_date = str(group.get("usable_trade_date") or "")[:10]
            if not (window["start"] <= event_date <= window["end"]):
                continue
            evaluated_count += 1
            row = evaluate_group(group, snapshot, spy_rows, label)
            if row.get("price_status") == "covered":
                covered_count += 1
            horizon = (row.get("horizons") or {}).get(f"{HOLD_DAYS}d") or {}
            semantic = semantic_subcategory(row)
            cell = (semantic, str(row.get("reaction_bucket") or ""))
            if (
                row.get("price_status") == "covered"
                and row.get("filing_category") == TARGET_CATEGORY
                and cell in TARGET_CELLS
                and horizon.get("status") == "valid"
            ):
                enriched = dict(row)
                enriched["semantic_subcategory"] = semantic
                enriched["target_cell"] = f"{semantic}|{row.get('reaction_bucket')}"
                candidates.append(enriched)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in sorted(
        candidates,
        key=lambda item: (
            item["entry_date"],
            item["target_cell"],
            item["reaction_excess_return"],
            item["ticker"],
        ),
    ):
        key = (str(row["ticker"]), str(row["entry_date"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    coverage = {
        "sec_event_group_count": len(groups),
        "evaluated_window_event_count": evaluated_count,
        "price_covered_count": covered_count,
        "price_coverage_rate": _round(covered_count / evaluated_count, 4) if evaluated_count else None,
        "raw_candidate_count": len(candidates),
        "deduped_candidate_count": len(deduped),
        "candidate_by_cell": dict(Counter(row["target_cell"] for row in deduped)),
        "candidate_by_window": dict(Counter(row["window"] for row in deduped)),
        "source": _repo_rel(SEC_EVENTS_PATH),
    }
    return deduped, prices, coverage


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
    rows.sort(key=lambda item: (item["entry_date"], item["target_cell"], item["reaction_excess_return"], item["ticker"]))
    for row in rows:
        entry_date = str(row["entry_date"])[:10]
        active_exits = [exit_date for exit_date in active_exits if exit_date >= entry_date]
        if len(active_exits) >= MAX_EVENT_POSITIONS:
            skipped.append(
                {
                    "ticker": row["ticker"],
                    "entry_date": entry_date,
                    "target_cell": row["target_cell"],
                    "reason": "slot_full",
                }
            )
            continue
        horizon = row["horizons"][f"{HOLD_DAYS}d"]
        exit_date = str(horizon["end_date"])[:10]
        entry_row = _row_on(prices, row["ticker"], entry_date)
        exit_row = _row_on(prices, row["ticker"], exit_date)
        if not entry_row or not exit_row or not entry_row.get("open") or not exit_row.get("close"):
            skipped.append(
                {
                    "ticker": row["ticker"],
                    "entry_date": entry_date,
                    "target_cell": row["target_cell"],
                    "reason": "missing_price",
                }
            )
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
                "semantic_subcategory": row.get("semantic_subcategory"),
                "target_cell": row.get("target_cell"),
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
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_window[str(trade["window"])].append(trade)
        by_cell[str(trade["target_cell"])].append(trade)
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
        "by_cell": {
            cell: {
                "trade_count": len(rows),
                "total_pnl": round(sum(float(row["pnl"]) for row in rows), 2),
                "win_rate": round(sum(1 for row in rows if float(row["pnl"]) > 0) / len(rows), 4) if rows else None,
                "avg_net_return_pct": _round(statistics.mean([row["net_return_pct"] for row in rows]), 6) if rows else None,
            }
            for cell, rows in sorted(by_cell.items())
        },
    }


def build_payload() -> dict[str, Any]:
    universe = get_universe()
    candidates, prices, coverage = _candidate_events()
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
        "windows_sharpe_gate": sum(1 for label in WINDOWS if gate_by_window[label]["passes_sharpe"]),
        "windows_trade_count_win_rate_gate": sum(1 for label in WINDOWS if gate_by_window[label]["passes_trade_count"]),
    }
    aggregate["ev_delta_sum"] = round(aggregate["overlay_ev_sum"] - aggregate["baseline_ev_sum"], 4)
    aggregate["ev_delta_pct"] = round(aggregate["ev_delta_sum"] / aggregate["baseline_ev_sum"], 6) if aggregate["baseline_ev_sum"] else None
    aggregate["pnl_delta"] = round(aggregate["overlay_pnl_sum"] - aggregate["baseline_pnl_sum"], 2)
    aggregate["pnl_delta_pct"] = round(aggregate["pnl_delta"] / aggregate["baseline_pnl_sum"], 6) if aggregate["baseline_pnl_sum"] else None

    material = (
        aggregate["windows_ev_regressed"] == 0
        and (
            aggregate["windows_material_ev_or_pnl"] >= 2
            or aggregate["windows_sharpe_gate"] >= 2
            or aggregate["windows_trade_count_win_rate_gate"] >= 2
        )
    )
    sample_positive = aggregate["windows_ev_improved"] >= 2 and aggregate["windows_ev_regressed"] == 0
    if material:
        status = "accepted_requires_followup"
        decision = "accepted_requires_trade_enabled_sleeve_parity"
        rationale = (
            "The SEC governance/procedural event overlay cleared the fixed-window materiality gate, "
            "but cannot be enabled until a shared production/backtest event-sleeve adapter exists."
        )
    elif sample_positive:
        status = "rejected"
        decision = "positive_sample_not_material_no_promotion"
        rationale = (
            "The governance/procedural overlay improved the majority read without EV regression, "
            "but the lift was below material Gate 4 thresholds."
        )
    else:
        status = "rejected"
        decision = "rejected_overlay_no_stable_alpha"
        rationale = (
            "The governance/procedural overlay did not improve the fixed windows enough to justify "
            "promotion or additional production complexity."
        )

    return {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "mechanism_family": "sec_governance_procedural_event_overlay",
        "change_type": "non_ohlcv_event_sleeve_alpha_search",
        "hypothesis": (
            "Residual SEC 8-K governance/procedural filings with mild market reactions may capture "
            "temporary uncertainty absorption that can add portfolio value as a small satellite sleeve."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension_event_sleeve",
            "entry_or_ranking": "entry",
            "why_this_now": (
                "LLM soft-ranking is sample-limited. This tests a PIT-safe semantic event basket "
                "from exp-20260504-023 instead of adding noisy tickers or retuning price thresholds."
            ),
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260504-022": "broad residual other-filing mild-negative branch was shadow-promising but slot-thin",
                "exp-20260504-023": "semantic decomposition found the fixed governance/procedural cells used here",
                "exp-20260504-026": "leadership-change event sleeve was rejected",
                "exp-20260504-034": "Form 4 satellite overlay was positive but immaterial",
                "exp-20260504-037": "FD/Other Event negative-reaction overlay was positive but immaterial",
            },
            "why_not_simple_repeat": (
                "This is a portfolio overlay test of a frozen semantic allowlist. It does not rerun the broad "
                "other-filing bucket, tune reaction thresholds, or promote a direct core-slot replacement."
            ),
            "mechanism_insight_guardrails": [
                "No LLM outputs are used.",
                "No reaction threshold, notional, capacity, or holding-period sweep is performed.",
                "No production entry, ranking, sizing, or order path changes.",
            ],
        },
        "parameters": {
            "single_causal_variable": "fixed SEC governance/procedural semantic cell allowlist as a 10k satellite overlay",
            "filing_category": TARGET_CATEGORY,
            "target_cells": sorted([{"semantic": semantic, "reaction_bucket": bucket} for semantic, bucket in TARGET_CELLS], key=lambda item: (item["semantic"], item["reaction_bucket"])),
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
                "event notional",
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
            "sharpe_windows": aggregate["windows_sharpe_gate"],
            "trade_count_win_rate_windows": aggregate["windows_trade_count_win_rate_gate"],
        },
        "coverage": coverage,
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
            "why_not_llm": "Production-aligned LLM soft-ranking remains sparse; this path uses PIT-safe SEC metadata instead.",
        },
        "decision_rationale": rationale,
        "rejection_reason": None if status != "rejected" else rationale,
        "next_action": (
            "Do not promote. A valid retry needs a broader closed forward sample, LLM semantic grading, "
            "or material three-window lift with a shared event-sleeve adapter."
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
        "# SEC Governance/Procedural Event Overlay",
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
        "| Window | Baseline EV | Overlay EV | Delta EV | Baseline PnL | Overlay PnL | Event PnL | Event Trades | Win rate |",
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
            f"- Candidate count: `{payload['coverage']['deduped_candidate_count']}`",
            f"- Selected trades: `{summary['trade_count']}`",
            f"- Event PnL: `{summary['total_pnl']}`",
            f"- Event win rate: `{_fmt_pct(summary['win_rate'])}`",
            (
                f"- Top absolute event contribution: `{concentration['ticker']}` "
                f"{concentration['pnl']} ({_fmt_pct(concentration['share_of_abs_pnl'])} of abs event PnL)"
            ),
            "",
            "## Cell Summary",
            "",
            "| Cell | Trades | PnL | Win rate | Avg net return |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for cell, row in summary["by_cell"].items():
        lines.append(
            f"| {cell} | {row['trade_count']} | {row['total_pnl']} | "
            f"{_fmt_pct(row['win_rate'])} | {_fmt_pct(row['avg_net_return_pct'])} |"
        )
    lines.extend(
        [
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
            "title": "SEC governance/procedural overlay replay",
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
