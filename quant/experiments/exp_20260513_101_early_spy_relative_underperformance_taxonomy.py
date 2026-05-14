"""Observed-only early SPY-relative underperformance loss taxonomy.

This experiment does not alter strategy behavior. It reruns the accepted core
stack over the canonical windows and measures one failure family: positions
whose first three available holding-session close return is negative and lags
SPY by at least three percentage points.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


EXPERIMENT_ID = "exp-20260513-101"
SLUG = "early_spy_relative_underperformance_taxonomy"

ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


OUT_PATH = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260513_101_{SLUG}.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

UNDERPERF_THRESHOLD = -0.03
EARLY_HOLDING_ROWS = 3
TAIL_N = 5


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    return _round(value)


def _load_snapshot_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("ohlcv", raw)
    return {str(ticker): list(values) for ticker, values in rows.items()}


def _metric_block(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"), 4
        ),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 6),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _rows_between(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows_by_ticker.get(ticker, [])
        if start <= str(row.get("Date")) <= end
    ]


def _price(row: dict[str, Any] | None, field: str) -> float | None:
    if row is None or row.get(field) is None:
        return None
    return float(row[field])


def _return(exit_price: float | None, entry_price: float | None) -> float | None:
    if exit_price is None or entry_price in (None, 0):
        return None
    return exit_price / entry_price - 1.0


def _spy_return(
    spy_rows: list[dict[str, Any]], entry_date: str, end_date: str, end_field: str
) -> float | None:
    entry_row = next((row for row in spy_rows if str(row.get("Date")) >= entry_date), None)
    end_candidates = [row for row in spy_rows if entry_date <= str(row.get("Date")) <= end_date]
    end_row = end_candidates[-1] if end_candidates else None
    return _return(_price(end_row, end_field), _price(entry_row, "Open"))


def _trade_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    winners = [row for row in rows if row["pnl"] > 0]
    losers = [row for row in rows if row["pnl"] < 0]
    pnl = sum(row["pnl"] for row in rows)
    return {
        "count": len(rows),
        "winner_count": len(winners),
        "loser_count": len(losers),
        "win_rate": _round(len(winners) / len(rows), 4) if rows else None,
        "total_pnl": _round(pnl, 2),
        "avg_pnl": _round(pnl / len(rows), 2) if rows else None,
        "loss_abs": _round(sum(abs(row["pnl"]) for row in losers), 2),
        "winner_pnl": _round(sum(row["pnl"] for row in winners), 2),
        "worst_pnl": _round(min((row["pnl"] for row in rows), default=0.0), 2),
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "Unknown")].append(row)
    return {
        name: _trade_summary(items)
        for name, items in sorted(
            grouped.items(), key=lambda item: sum(row["pnl"] for row in item[1])
        )
    }


def _annotate_trade(
    window: str,
    trade: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    entry_date = str(trade.get("entry_date"))
    exit_date = str(trade.get("exit_date"))
    ticker_rows = _rows_between(rows_by_ticker, str(trade.get("ticker")), entry_date, exit_date)
    spy_rows = rows_by_ticker.get("SPY", [])
    early_rows = ticker_rows[:EARLY_HOLDING_ROWS]
    early_end = str(early_rows[-1].get("Date")) if early_rows else exit_date

    entry_price = float(trade.get("entry_price") or 0.0)
    shares = int(trade.get("shares") or 0)
    notional = entry_price * shares
    early_ticker_return = _return(_price(early_rows[-1] if early_rows else None, "Close"), entry_price)
    early_spy_return = _spy_return(spy_rows, entry_date, early_end, "Close")
    early_excess = (
        early_ticker_return - early_spy_return
        if early_ticker_return is not None and early_spy_return is not None
        else None
    )
    full_spy_return = _spy_return(spy_rows, entry_date, exit_date, "Close")
    spy_replacement_pnl = (full_spy_return or 0.0) * notional
    pnl = float(trade.get("pnl") or 0.0)
    family = (
        early_ticker_return is not None
        and early_spy_return is not None
        and early_ticker_return < 0.0
        and early_excess is not None
        and early_excess <= UNDERPERF_THRESHOLD
    )

    return {
        "window": window,
        "trade_key": trade.get("trade_key"),
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector") or "Unknown",
        "entry_date": entry_date,
        "exit_date": exit_date,
        "exit_reason": trade.get("exit_reason"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "shares": shares,
        "notional": notional,
        "pnl": pnl,
        "pnl_pct_net": float(trade.get("pnl_pct_net") or 0.0),
        "actual_risk_pct": trade.get("actual_risk_pct"),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
        "early_rows_observed": len(early_rows),
        "early_end_date": early_end,
        "early_ticker_return_pct": early_ticker_return,
        "early_spy_return_pct": early_spy_return,
        "early_excess_vs_spy_pct": early_excess,
        "full_holding_spy_return_pct": full_spy_return,
        "spy_replacement_pnl_same_notional": spy_replacement_pnl,
        "spy_replacement_value_vs_actual_pnl": spy_replacement_pnl - pnl,
        "family_early_spy_relative_underperformance": family,
    }


def _add_same_day_context(trades: list[dict[str, Any]]) -> None:
    by_window_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_window_day[(trade["window"], trade["entry_date"])].append(trade)

    for group in by_window_day.values():
        winners = [trade for trade in group if trade["pnl"] > 0]
        winner_pnls = [trade["pnl"] for trade in winners]
        for trade in group:
            trade["same_day_accepted_trade_count"] = len(group)
            trade["same_day_accepted_winner_count"] = len(winners)
            trade["same_day_accepted_winner_pnl"] = sum(winner_pnls)
            trade["same_day_median_winner_pnl"] = median(winner_pnls) if winner_pnls else None


def _family_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    family = [row for row in rows if row["family_early_spy_relative_underperformance"]]
    family_bad = [row for row in family if row["pnl"] < 0]
    family_good = [row for row in family if row["pnl"] > 0]
    all_losers = [row for row in rows if row["pnl"] < 0]
    all_loss_abs = sum(abs(row["pnl"]) for row in all_losers)
    tail = sorted(all_losers, key=lambda row: row["pnl"])[: min(TAIL_N, len(all_losers))]
    tail_loss_abs = sum(abs(row["pnl"]) for row in tail)
    family_tail = [row for row in tail if row["family_early_spy_relative_underperformance"]]
    family_bad_loss_abs = sum(abs(row["pnl"]) for row in family_bad)
    collateral_pnl = sum(row["pnl"] for row in family_good)
    spy_replacement_pnl = sum(row["spy_replacement_pnl_same_notional"] for row in family_bad)
    actual_bad_pnl = sum(row["pnl"] for row in family_bad)
    same_day_winner_pnl = sum(row.get("same_day_accepted_winner_pnl") or 0.0 for row in family_bad)

    return {
        "definition": {
            "early_holding_rows": EARLY_HOLDING_ROWS,
            "condition": (
                "first three available holding-session close return < 0 and "
                "ticker return minus SPY return <= -3 percentage points"
            ),
            "underperformance_threshold_pct": UNDERPERF_THRESHOLD,
        },
        "appearance": {
            "family_trade_count": len(family),
            "total_trade_count": len(rows),
            "family_trade_share": _round(len(family) / len(rows), 4) if rows else None,
            "family_loser_count": len(family_bad),
            "total_loser_count": len(all_losers),
            "family_loser_share": _round(len(family_bad) / len(all_losers), 4)
            if all_losers
            else None,
        },
        "loss_contribution": {
            "family_bad_loss_abs": _round(family_bad_loss_abs, 2),
            "all_loss_abs": _round(all_loss_abs, 2),
            "share_of_all_loss_abs": _round(family_bad_loss_abs / all_loss_abs, 4)
            if all_loss_abs
            else None,
        },
        "tail_contribution": {
            "tail_n": len(tail),
            "tail_loss_abs": _round(tail_loss_abs, 2),
            "family_tail_count": len(family_tail),
            "family_tail_loss_abs": _round(sum(abs(row["pnl"]) for row in family_tail), 2),
            "share_of_tail_loss_abs": _round(
                sum(abs(row["pnl"]) for row in family_tail) / tail_loss_abs, 4
            )
            if tail_loss_abs
            else None,
            "tail_examples": [
                {
                    "window": row["window"],
                    "ticker": row["ticker"],
                    "strategy": row["strategy"],
                    "entry_date": row["entry_date"],
                    "exit_date": row["exit_date"],
                    "pnl": _round(row["pnl"], 2),
                    "early_excess_vs_spy_pct": _round(row["early_excess_vs_spy_pct"]),
                    "in_family": row["family_early_spy_relative_underperformance"],
                }
                for row in tail
            ],
        },
        "good_trade_collateral_risk": {
            "family_winner_count": len(family_good),
            "family_winner_pnl_collateral": _round(collateral_pnl, 2),
            "collateral_to_family_bad_loss_ratio": _round(collateral_pnl / family_bad_loss_abs, 4)
            if family_bad_loss_abs
            else None,
            "naive_filter_or_oracle_net_loss_saved_after_winner_collateral": _round(
                family_bad_loss_abs - collateral_pnl, 2
            ),
            "family_winner_examples": [
                {
                    "window": row["window"],
                    "ticker": row["ticker"],
                    "strategy": row["strategy"],
                    "entry_date": row["entry_date"],
                    "pnl": _round(row["pnl"], 2),
                    "early_excess_vs_spy_pct": _round(row["early_excess_vs_spy_pct"]),
                }
                for row in sorted(family_good, key=lambda item: item["pnl"], reverse=True)[:8]
            ],
        },
        "oracle_and_replacement_value": {
            "oracle_loss_saved_if_only_bad_family_removed": _round(family_bad_loss_abs, 2),
            "spy_replacement_pnl_for_bad_family_same_notional": _round(spy_replacement_pnl, 2),
            "spy_replacement_value_vs_actual_bad_family_pnl": _round(
                spy_replacement_pnl - actual_bad_pnl, 2
            ),
            "same_day_accepted_winner_pnl_available_for_bad_family": _round(
                same_day_winner_pnl, 2
            ),
            "bad_family_with_same_day_winner_count": sum(
                1 for row in family_bad if (row.get("same_day_accepted_winner_count") or 0) > 0
            ),
        },
        "by_window": _group(family, "window"),
        "by_strategy": _group(family, "strategy"),
        "by_sector": _group(family, "sector"),
        "worst_family_bad_trades": [
            {
                "window": row["window"],
                "ticker": row["ticker"],
                "strategy": row["strategy"],
                "sector": row["sector"],
                "entry_date": row["entry_date"],
                "exit_date": row["exit_date"],
                "pnl": _round(row["pnl"], 2),
                "pnl_pct_net": _round(row["pnl_pct_net"]),
                "early_ticker_return_pct": _round(row["early_ticker_return_pct"]),
                "early_spy_return_pct": _round(row["early_spy_return_pct"]),
                "early_excess_vs_spy_pct": _round(row["early_excess_vs_spy_pct"]),
                "spy_replacement_value_vs_actual_pnl": _round(
                    row["spy_replacement_value_vs_actual_pnl"], 2
                ),
                "same_day_accepted_winner_pnl": _round(
                    row.get("same_day_accepted_winner_pnl") or 0.0, 2
                ),
            }
            for row in sorted(family_bad, key=lambda item: item["pnl"])[:10]
        ],
    }


def _run_window(label: str, spec: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    snapshot = ROOT / spec["snapshot"]
    rows_by_ticker = _load_snapshot_rows(snapshot)
    engine = BacktestEngine(
        get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(snapshot),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} backtest failed: {result['error']}")
    trades = [
        _annotate_trade(label, trade, rows_by_ticker)
        for trade in result.get("trades", [])
    ]
    return result, trades


def build_artifact() -> dict[str, Any]:
    all_trades: list[dict[str, Any]] = []
    by_window: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        result, trades = _run_window(label, spec)
        all_trades.extend(trades)
        by_window[label] = {
            "window": spec,
            "metrics": _metric_block(result),
            "trade_summary": _trade_summary(trades),
            "family_summary": _family_summary(trades),
            "trades": trades,
        }

    _add_same_day_context(all_trades)
    for label in by_window:
        by_window[label]["family_summary"] = _family_summary(by_window[label]["trades"])

    aggregate_metrics = {
        "expected_value_score_sum": _round(
            sum(window["metrics"]["expected_value_score"] for window in by_window.values()), 4
        ),
        "total_pnl_sum": _round(
            sum(window["metrics"]["total_pnl"] for window in by_window.values()), 2
        ),
        "trade_count_sum": sum(
            int(window["metrics"]["trade_count"] or 0) for window in by_window.values()
        ),
        "signals_generated_sum": sum(
            int(window["metrics"]["signals_generated"] or 0) for window in by_window.values()
        ),
        "signals_survived_sum": sum(
            int(window["metrics"]["signals_survived"] or 0) for window in by_window.values()
        ),
        "max_drawdown_pct_max": _round(
            max(window["metrics"]["max_drawdown_pct"] for window in by_window.values()), 4
        ),
    }
    aggregate_metrics["survival_rate"] = _round(
        aggregate_metrics["signals_survived_sum"]
        / aggregate_metrics["signals_generated_sum"],
        4,
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": "loss_attribution",
        "status": "observed_only",
        "classification": "bad-trade/tail-loss taxonomy",
        "hypothesis": (
            "Accepted-stack bad trades may concentrate in an early post-entry "
            "SPY-relative underperformance family, where positions lose "
            "replacement value shortly after entry."
        ),
        "single_causal_variable": "early post-entry SPY-relative underperformance taxonomy",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "backtest_protocol": {
            "source": "docs/backtesting.md",
            "windows": WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            "strategy_logic_changed": False,
        },
        "historical_constraints_checked": [
            "exp-20260511-102 already covered broad oracle labels; this run isolates only early SPY-relative underperformance.",
            "exp-20260512-102 already covered late-window entry-day adverse sector tape; this run does not use sector tape as the causal variable.",
            "No filter, ranking, sizing, exit, threshold sweep, LLM boundary, or production adapter is changed.",
        ],
        "metrics": aggregate_metrics,
        "expected_value_score": aggregate_metrics["expected_value_score_sum"],
        "total_pnl": aggregate_metrics["total_pnl_sum"],
        "max_drawdown_pct": aggregate_metrics["max_drawdown_pct_max"],
        "survival_rate": aggregate_metrics["survival_rate"],
        "total_trades": aggregate_metrics["trade_count_sum"],
        "win_rate": _round(
            sum(1 for trade in all_trades if trade["pnl"] > 0) / len(all_trades), 4
        ),
        "aggregate": {
            "trade_summary": _trade_summary(all_trades),
            "family_summary": _family_summary(all_trades),
        },
        "by_window": by_window,
        "family_trades": [
            row
            for row in sorted(
                all_trades,
                key=lambda item: (not item["family_early_spy_relative_underperformance"], item["pnl"]),
            )
            if row["family_early_spy_relative_underperformance"]
        ],
        "future_test_implications": [
            "This is not an implementable filter because the family label uses future holding-period returns.",
            "A future alpha test would need a production-visible pre-entry proxy for early relative underperformance risk.",
            "The collateral section should be treated as the guardrail against converting this observed-only family into a broad rule.",
        ],
        "decision": "observed_only",
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
    }


def main() -> None:
    artifact = build_artifact()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(_safe(artifact), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "artifact": str(OUT_PATH.relative_to(ROOT)),
        "metrics": artifact["metrics"],
        "family_summary": artifact["aggregate"]["family_summary"],
    }
    print(json.dumps(_safe(summary), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
