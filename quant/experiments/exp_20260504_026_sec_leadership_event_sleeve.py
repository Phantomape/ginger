"""exp-20260504-026 SEC leadership-change event-sleeve replay.

This is an alpha-search experiment, not a production strategy change. It
freezes the shadow-promising branch from the SEC filing reaction family:
leadership-change filings with an initial <= -2% excess reaction, then tests
whether a small fixed-notional sidecar sleeve survives capacity, costs, and
the canonical three-window evaluation.
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

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260503_051_sec_filing_reaction_drift import (  # noqa: E402
    SEC_EVENTS_PATH,
    WINDOWS,
    _compact_event,
    _load_snapshot,
    _safe_payload,
    _write_json,
    attach_slot_conflicts,
    evaluate_group,
    load_event_groups,
    run_baseline_windows,
)


EXPERIMENT_ID = "exp-20260504-026"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_leadership_event_sleeve.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REPORT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_leadership_event_sleeve_20260504_exp026.md"
)

INITIAL_CAPITAL = 100_000.0
EVENT_NOTIONAL = 10_000.0
MAX_EVENT_POSITIONS = 1
PRIMARY_HORIZON_KEY = "10d"
PRIMARY_REACTION_BUCKET = "negative_excess_le_minus_2pct"
PRIMARY_FILING_CATEGORY = "leadership_change"


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return round(value, digits)


def _row_by_date(price_map: dict[str, list[dict[str, Any]]], ticker: str, date_value: str) -> dict[str, Any] | None:
    for row in price_map.get(str(ticker).upper(), []):
        if row["date"] == date_value:
            return row
    return None


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _merge_snapshots(snapshots: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for snapshot in snapshots.values():
        for ticker, rows in snapshot.items():
            for row in rows:
                by_ticker_date[str(ticker).upper()][row["date"]] = dict(row)
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _max_drawdown(equity_curve: list[dict[str, Any]]) -> float | None:
    if not equity_curve:
        return None
    peak = equity_curve[0]["equity"]
    max_dd = 0.0
    for row in equity_curve:
        equity = row["equity"]
        if equity > peak:
            peak = equity
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return max_dd


def _daily_sharpe(equity_curve: list[dict[str, Any]]) -> float | None:
    returns: list[float] = []
    for prev, cur in zip(equity_curve, equity_curve[1:]):
        if prev["equity"] > 0:
            returns.append(cur["equity"] / prev["equity"] - 1.0)
    if len(returns) < 2:
        return None
    stdev = statistics.stdev(returns)
    if stdev <= 0:
        return None
    return statistics.mean(returns) / stdev * math.sqrt(252)


def _distribution(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        return {"count": 0, "avg": None, "median": None, "min": None, "max": None, "win_rate": None}
    return {
        "count": len(clean),
        "avg": _round(statistics.mean(clean)),
        "median": _round(statistics.median(clean)),
        "min": _round(min(clean)),
        "max": _round(max(clean)),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def _price_equity(
    realized_pnl: float,
    active: list[dict[str, Any]],
    price_map: dict[str, list[dict[str, Any]]],
    date_value: str,
) -> float:
    unrealized = 0.0
    for position in active:
        row = _row_by_date(price_map, position["ticker"], date_value)
        price = row.get("close") if row else position.get("last_price")
        if price:
            position["last_price"] = price
            unrealized += position["shares"] * float(price) - position["entry_notional"]
    return INITIAL_CAPITAL + realized_pnl + unrealized


def _collect_primary_candidates() -> tuple[
    dict[str, Any],
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
    list[dict[str, Any]],
]:
    universe = sorted(get_universe())
    baseline_metrics, baseline_trades = run_baseline_windows(universe)
    event_groups = load_event_groups(SEC_EVENTS_PATH)
    snapshots = {
        label: _load_snapshot(REPO_ROOT / cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }

    evaluated: list[dict[str, Any]] = []
    for label, cfg in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot.get("SPY") or []
        for event in event_groups:
            usable_date = event["usable_trade_date"]
            if cfg["start"] <= usable_date <= cfg["end"]:
                evaluated.append(evaluate_group(event, snapshot, spy_rows, label))

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    covered, slot_summary = attach_slot_conflicts(covered, baseline_trades, snapshots)
    primary_rows = [
        row
        for row in covered
        if row.get("filing_category") == PRIMARY_FILING_CATEGORY
        and row.get("reaction_bucket") == PRIMARY_REACTION_BUCKET
        and ((row.get("horizons") or {}).get(PRIMARY_HORIZON_KEY) or {}).get("status") == "valid"
    ]

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in sorted(
        primary_rows,
        key=lambda item: (
            item.get("entry_date") or "",
            item.get("reaction_excess_return") or 0,
            item.get("ticker") or "",
        ),
    ):
        key = (str(row.get("ticker") or ""), str(row.get("entry_date") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    coverage = {
        "sec_event_group_count": len(event_groups),
        "evaluated_window_event_count": len(evaluated),
        "price_covered_count": len(covered),
        "price_coverage_rate": _round(len(covered) / len(evaluated), 4) if evaluated else None,
        "primary_candidate_count": len(deduped),
        "primary_raw_valid_count": len(primary_rows),
        "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
        "slot_conflict_summary": slot_summary,
    }
    return baseline_metrics, _merge_snapshots(snapshots), coverage, deduped


def simulate_sleeve(
    candidates: list[dict[str, Any]],
    price_map: dict[str, list[dict[str, Any]]],
    *,
    event_notional: float = EVENT_NOTIONAL,
    max_positions: int = MAX_EVENT_POSITIONS,
    round_trip_cost_pct: float = ROUND_TRIP_COST_PCT,
) -> dict[str, Any]:
    trading_dates = [row["date"] for row in price_map.get("SPY", [])]
    candidates_by_entry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        entry_date = str(candidate.get("entry_date") or "")
        if entry_date:
            candidates_by_entry[entry_date].append(candidate)
    for rows in candidates_by_entry.values():
        rows.sort(key=lambda row: (row.get("reaction_excess_return") or 0, row.get("ticker") or ""))

    active: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    realized_pnl = 0.0
    equity_curve: list[dict[str, Any]] = []

    for date_value in trading_dates:
        day_candidates = candidates_by_entry.get(date_value) or []
        for candidate in day_candidates:
            if any(position["ticker"] == candidate["ticker"] for position in active):
                skipped.append({**_compact_event(candidate), "skip_reason": "ticker_already_active"})
                continue
            if len(active) >= max_positions:
                skipped.append({**_compact_event(candidate), "skip_reason": "slot_full"})
                continue

            horizon = (candidate.get("horizons") or {}).get(PRIMARY_HORIZON_KEY) or {}
            exit_date = str(horizon.get("end_date") or "")
            if not exit_date:
                skipped.append({**_compact_event(candidate), "skip_reason": "missing_exit_date"})
                continue

            ticker_rows = price_map.get(str(candidate.get("ticker") or "").upper()) or []
            entry_idx = _idx_on_or_after(ticker_rows, date_value)
            if entry_idx is None:
                skipped.append({**_compact_event(candidate), "skip_reason": "missing_entry_price"})
                continue
            entry_row = ticker_rows[entry_idx]
            entry_price = entry_row.get("open")
            if not entry_price or entry_price <= 0:
                skipped.append({**_compact_event(candidate), "skip_reason": "missing_entry_price"})
                continue
            exit_row = _row_by_date(price_map, candidate["ticker"], exit_date)
            if not exit_row or not exit_row.get("close"):
                skipped.append({**_compact_event(candidate), "skip_reason": "missing_exit_price"})
                continue

            active.append(
                {
                    **candidate,
                    "entry_price": float(entry_price),
                    "entry_notional": float(event_notional),
                    "shares": float(event_notional) / float(entry_price),
                    "planned_exit_date": exit_date,
                    "last_price": float(entry_price),
                }
            )

        remaining: list[dict[str, Any]] = []
        for position in active:
            if position["planned_exit_date"] != date_value:
                remaining.append(position)
                continue
            exit_row = _row_by_date(price_map, position["ticker"], date_value)
            exit_price = exit_row.get("close") if exit_row else None
            if not exit_price:
                remaining.append(position)
                continue
            gross_proceeds = position["shares"] * float(exit_price)
            net_proceeds = gross_proceeds * (1.0 - round_trip_cost_pct)
            pnl = net_proceeds - position["entry_notional"]
            gross_return = float(exit_price) / position["entry_price"] - 1.0
            net_return = net_proceeds / position["entry_notional"] - 1.0
            realized_pnl += pnl
            trades.append(
                {
                    "ticker": position["ticker"],
                    "window": position.get("window"),
                    "entry_date": position["entry_date"],
                    "exit_date": date_value,
                    "entry_price": _round(position["entry_price"], 4),
                    "exit_price": _round(float(exit_price), 4),
                    "entry_notional": _round(position["entry_notional"], 2),
                    "pnl": _round(pnl, 2),
                    "gross_return_pct": _round(gross_return),
                    "net_return_pct": _round(net_return),
                    "reaction_excess_return": position.get("reaction_excess_return"),
                    "forward_10d_excess_return": (
                        ((position.get("horizons") or {}).get(PRIMARY_HORIZON_KEY) or {}).get("excess_return")
                    ),
                    "same_day_core_trade_count": position.get("same_day_core_trade_count"),
                    "replacement_value_10d_excess_proxy": position.get("replacement_value_10d_excess_proxy"),
                }
            )
        active = remaining
        equity = _price_equity(realized_pnl, active, price_map, date_value)
        equity_curve.append(
            {
                "date": date_value,
                "equity": _round(equity, 2),
                "active_positions": len(active),
            }
        )

    final_equity = equity_curve[-1]["equity"] if equity_curve else INITIAL_CAPITAL
    total_return = final_equity / INITIAL_CAPITAL - 1.0
    sharpe = _daily_sharpe(equity_curve)
    max_dd = _max_drawdown(equity_curve)
    exposure_days = sum(1 for row in equity_curve if row["active_positions"] > 0)
    return {
        "initial_capital": INITIAL_CAPITAL,
        "event_notional": event_notional,
        "max_positions": max_positions,
        "horizon": PRIMARY_HORIZON_KEY,
        "round_trip_cost_pct": round_trip_cost_pct,
        "final_equity": _round(final_equity, 2),
        "total_pnl": _round(final_equity - INITIAL_CAPITAL, 2),
        "total_return_pct": _round(total_return),
        "sharpe_daily": _round(sharpe, 4),
        "expected_value_score": _round(total_return * sharpe if sharpe is not None else None),
        "max_drawdown_pct": _round(max_dd),
        "trade_count": len(trades),
        "win_rate": _round(sum(1 for trade in trades if trade["pnl"] > 0) / len(trades), 4) if trades else None,
        "exposure_days": exposure_days,
        "exposure_rate": _round(exposure_days / len(equity_curve), 4) if equity_curve else None,
        "skipped_count": len(skipped),
        "skipped_by_reason": dict(Counter(row["skip_reason"] for row in skipped)),
        "trade_summary": _summarize_trades(trades),
        "trades": trades,
        "skipped_events": skipped,
        "equity_curve_tail": equity_curve[-30:],
    }


def _summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_window[str(trade.get("window") or "unknown")].append(trade)
        by_ticker[str(trade.get("ticker") or "unknown")].append(trade)

    total_abs_pnl = sum(abs(float(trade["pnl"])) for trade in trades)
    top_abs = max(trades, key=lambda trade: abs(float(trade["pnl"])), default=None)
    return {
        "net_return_distribution": _distribution([float(trade["net_return_pct"]) for trade in trades]),
        "pnl_distribution": _distribution([float(trade["pnl"]) for trade in trades]),
        "top_abs_trade_concentration": {
            "ticker": top_abs.get("ticker") if top_abs else None,
            "pnl": top_abs.get("pnl") if top_abs else None,
            "share_of_abs_pnl": _round(abs(float(top_abs["pnl"])) / total_abs_pnl, 4) if top_abs and total_abs_pnl else None,
        },
        "by_window": {
            label: {
                "trade_count": len(rows),
                "total_pnl": _round(sum(float(row["pnl"]) for row in rows), 2),
                "win_rate": _round(sum(1 for row in rows if float(row["pnl"]) > 0) / len(rows), 4) if rows else None,
                "net_return_distribution": _distribution([float(row["net_return_pct"]) for row in rows]),
            }
            for label, rows in sorted(by_window.items())
        },
        "by_ticker": [
            {
                "ticker": ticker,
                "trade_count": len(rows),
                "total_pnl": _round(sum(float(row["pnl"]) for row in rows), 2),
            }
            for ticker, rows in sorted(
                by_ticker.items(),
                key=lambda item: sum(float(row["pnl"]) for row in item[1]),
                reverse=True,
            )
        ][:12],
    }


def _positive_window_count(sleeve: dict[str, Any]) -> int:
    count = 0
    for summary in (sleeve.get("trade_summary") or {}).get("by_window", {}).values():
        pnl = summary.get("total_pnl")
        if isinstance(pnl, (int, float)) and pnl > 0:
            count += 1
    return count


def _build_payload() -> dict[str, Any]:
    baseline_metrics, price_map, coverage, candidates = _collect_primary_candidates()
    sleeve = simulate_sleeve(candidates, price_map)
    positive_windows = _positive_window_count(sleeve)
    top_concentration = (sleeve.get("trade_summary") or {}).get("top_abs_trade_concentration") or {}

    gate_promising = (
        sleeve["trade_count"] >= 10
        and (sleeve["total_pnl"] or 0) > 0
        and positive_windows == len(WINDOWS)
        and (sleeve["max_drawdown_pct"] or 1) <= 0.05
        and (top_concentration.get("share_of_abs_pnl") or 1) <= 0.35
    )
    status = "sleeve_promising_not_promoted" if gate_promising else "sleeve_rejected"
    decision_rationale = (
        "The frozen leadership-change + negative-reaction branch remains positive in a fixed-notional "
        "portfolio sleeve across all three canonical windows, but it is not promoted because core "
        "replacement value and forward queue evidence are still required."
        if gate_promising
        else "The frozen leadership-change + negative-reaction branch did not survive the fixed-notional "
        "portfolio sleeve gate across the canonical windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "status": status,
        "decision": status,
        "mechanism_family": "sec_leadership_change_negative_reaction_alpha",
        "change_type": "default_off_event_sleeve_replay",
        "hypothesis": (
            "PIT-safe 8-K leadership-change filings whose first EOD reaction is <= -2% excess may identify "
            "overreaction/absorption rebounds that can make money as a small deterministic event sleeve."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension_event_sleeve",
            "why_this_now": (
                "LLM soft-ranking remains sample-limited, while exp-20260504-015 found this exact SEC branch "
                "positive in all three windows before portfolio capacity and costs."
            ),
            "blocked_alternatives": {
                "llm_soft_ranking": "insufficient production-aligned samples",
                "core_threshold_micro_tuning": "recent logs show high overfit risk and little remaining loss concentration",
                "raw_sec_negative_language": "already tested; replacement value remained inconclusive",
            },
        },
        "history_check": {
            "similar_experiments": {
                "exp-20260504-010": "negative-language SEC event sleeve was standalone-positive but not a core slot competitor",
                "exp-20260504-011": "SEC negative-reaction replacement value was inconclusive for promotion",
                "exp-20260504-015": "leadership-change negative-reaction branch was shadow-promising across 3 windows",
                "exp-20260504-018": "leadership-change static universe was shadow-promising but not promoted without PIT ledger",
                "exp-20260504-022": "other-filing mild-negative branch was sample-limited",
            },
            "why_not_simple_repeat": (
                "This freezes exp-20260504-015's branch and changes the test unit from per-event excess returns "
                "to a fixed-notional sleeve with capacity, costs, daily drawdown, and 3-window attribution."
            ),
            "mechanism_insight_guardrails": [
                "No nearby SEC reaction threshold tuning.",
                "No LLM semantic grader because the labeled sample remains thin.",
                "No promotion to core universe or production trading without replacement-value and forward evidence.",
            ],
        },
        "parameters": {
            "single_causal_variable": (
                "turn the fixed leadership_change + negative_excess_le_minus_2pct branch into a default-off event sleeve replay"
            ),
            "filing_category": PRIMARY_FILING_CATEGORY,
            "reaction_bucket": PRIMARY_REACTION_BUCKET,
            "horizon": PRIMARY_HORIZON_KEY,
            "event_notional": EVENT_NOTIONAL,
            "initial_capital": INITIAL_CAPITAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "entry": "next trading-day open after the reaction close, as computed by exp-20260503-051",
            "exit": "10d horizon end-date close from exp-20260503-051",
            "candidate_sort": "entry_date, most negative reaction_excess_return, ticker",
            "locked_variables": [
                "production universe",
                "core signal generation",
                "core filters",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": ["2025-04-23 -> 2025-10-22", "2024-10-02 -> 2025-04-22"],
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "expected_value_score_delta": 0.0,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_impact": "default_off_shadow_sleeve_only_no_strategy_logic_changed",
        },
        "gate4": {
            "core_strategy_passed": False,
            "basis": "No promoted strategy change; canonical core metrics are unchanged by design.",
            "sleeve_gate_promising": gate_promising,
            "sleeve_gate_requirements": {
                "trade_count_gte_10": sleeve["trade_count"] >= 10,
                "total_pnl_positive": (sleeve["total_pnl"] or 0) > 0,
                "positive_in_all_three_windows": positive_windows == len(WINDOWS),
                "max_drawdown_lte_5pct": (sleeve["max_drawdown_pct"] or 1) <= 0.05,
                "top_abs_trade_share_lte_35pct": (top_concentration.get("share_of_abs_pnl") or 1) <= 0.35,
            },
        },
        "coverage": coverage,
        "sleeve_metrics": sleeve,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "This alpha search deliberately avoids the current LLM soft-ranking data limit.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if gate_promising else decision_rationale,
        "next_action": (
            "Build a default-off forward queue / replacement-value harness for this branch before any production promotion."
            if gate_promising
            else "Do not promote this branch; a retry needs new forward queue evidence or richer event semantics."
        ),
        "related_files": [
            "quant/experiments/exp_20260504_026_sec_leadership_event_sleeve.py",
            "data/experiments/exp-20260504-026/sec_leadership_event_sleeve.json",
            "experiments/logs/exp-20260504-026.json",
            "experiments/tickets/exp-20260504-026.json",
            "docs/non_ohlcv_data_audit/sec_leadership_event_sleeve_20260504_exp026.md",
        ],
        "candidate_examples": [_compact_event(row) for row in candidates[:12]],
    }
    return _safe_payload(payload)


def _write_report(payload: dict[str, Any]) -> None:
    sleeve = payload["sleeve_metrics"]
    summary = sleeve["trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Leadership Event Sleeve",
        "",
        f"- decision: `{payload['decision']}`",
        f"- lane: `{payload['lane']}`",
        f"- sleeve PnL: {sleeve['total_pnl']}",
        f"- sleeve return: {sleeve['total_return_pct']}",
        f"- sleeve Sharpe daily: {sleeve['sharpe_daily']}",
        f"- sleeve max drawdown: {sleeve['max_drawdown_pct']}",
        f"- trades: {sleeve['trade_count']}",
        f"- win rate: {sleeve['win_rate']}",
        f"- production impact: `{payload['production_impact']['production_impact']}`",
        "",
        "## Window Summary",
        "",
        "| Window | Trades | Total PnL | Win rate | Avg net return |",
        "|---|---:|---:|---:|---:|",
    ]
    for window, data in summary["by_window"].items():
        dist = data["net_return_distribution"]
        lines.append(
            f"| {window} | {data['trade_count']} | {data['total_pnl']} | "
            f"{data['win_rate']} | {dist['avg']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "The experiment is replay-only and default-off. It does not change production entries, exits, "
            "ranking, sizing, universe membership, or backtester strategy logic.",
        ]
    )
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "title": "SEC leadership event sleeve replay",
        "summary": payload["decision_rationale"],
        "primary_metrics": {
            key: payload["sleeve_metrics"][key]
            for key in (
                "trade_count",
                "total_pnl",
                "total_return_pct",
                "sharpe_daily",
                "max_drawdown_pct",
                "win_rate",
                "expected_value_score",
            )
        },
        "next_action": payload["next_action"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_report(payload)


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "coverage": payload["coverage"],
                "sleeve": {
                    key: payload["sleeve_metrics"][key]
                    for key in (
                        "trade_count",
                        "total_pnl",
                        "total_return_pct",
                        "sharpe_daily",
                        "max_drawdown_pct",
                        "win_rate",
                        "expected_value_score",
                    )
                },
                "by_window": payload["sleeve_metrics"]["trade_summary"]["by_window"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
