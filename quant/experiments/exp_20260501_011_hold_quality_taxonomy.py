"""Observed-only hold-quality loss taxonomy for exp-20260501-011.

This script reads an existing BacktestEngine result and writes a machine-readable
audit artifact. It does not change strategy behavior.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


EXPERIMENT_ID = "exp-20260501-011"
BASELINE_PATH = Path("data/backtest_results_20260430.json")
OUTPUT_PATH = Path(
    "data/experiments/exp-20260501-011/"
    "exp_20260501_011_hold_quality_taxonomy.json"
)


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _hold_days(trade: dict) -> int | None:
    entry = trade.get("entry_date")
    exit_ = trade.get("exit_date")
    if not entry or not exit_:
        return None
    return (_parse_date(exit_) - _parse_date(entry)).days


def _pnl_r(trade: dict) -> float | None:
    initial_risk = trade.get("initial_risk_pct")
    pnl_pct = trade.get("pnl_pct_net")
    if not initial_risk:
        return None
    return round(float(pnl_pct) / float(initial_risk), 4)


def _summary(rows: list[dict]) -> dict:
    return {
        "count": len(rows),
        "pnl_sum": round(sum(float(row.get("pnl") or 0.0) for row in rows), 2),
        "avg_pnl": round(sum(float(row.get("pnl") or 0.0) for row in rows) / len(rows), 2)
        if rows
        else None,
        "tickers": sorted({row.get("ticker") for row in rows if row.get("ticker")}),
        "strategy_counts": dict(Counter(row.get("strategy") for row in rows)),
        "sector_counts": dict(Counter(row.get("sector") for row in rows)),
        "entry_date_counts": dict(Counter(row.get("entry_date") for row in rows)),
    }


def _family_stats(trades: list[dict], predicates: dict[str, callable]) -> dict:
    stats = {}
    for name, predicate in predicates.items():
        hits = [trade for trade in trades if predicate(trade)]
        losses = [trade for trade in hits if float(trade.get("pnl") or 0.0) < 0]
        winners = [trade for trade in hits if float(trade.get("pnl") or 0.0) > 0]
        loss_abs = round(-sum(float(row.get("pnl") or 0.0) for row in losses), 2)
        winner_pnl = round(sum(float(row.get("pnl") or 0.0) for row in winners), 2)
        stats[name] = {
            "hit_count": len(hits),
            "loss_count": len(losses),
            "winner_collateral_count": len(winners),
            "loss_pnl_abs": loss_abs,
            "winner_collateral_pnl": winner_pnl,
            "collateral_to_loss_abs": round(winner_pnl / loss_abs, 4) if loss_abs else None,
            "naive_filter_net_after_collateral": round(loss_abs - winner_pnl, 2),
            "loss_summary": _summary(losses),
            "winner_collateral_summary": _summary(winners),
        }
    return stats


def main() -> None:
    result = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    trades = result.get("trades") or []

    enriched = []
    for trade in trades:
        row = dict(trade)
        row["hold_days"] = _hold_days(trade)
        row["pnl_r"] = _pnl_r(trade)
        row["is_loss"] = float(trade.get("pnl") or 0.0) < 0
        enriched.append(row)

    by_entry_date = defaultdict(list)
    for trade in enriched:
        by_entry_date[trade.get("entry_date")].append(trade)
    clustered_loss_dates = {
        entry_date
        for entry_date, rows in by_entry_date.items()
        if sum(1 for row in rows if row["is_loss"]) >= 2
        and not any(float(row.get("pnl") or 0.0) > 0 for row in rows)
    }

    predicates = {
        "stopped_without_addon": lambda t: t["is_loss"]
        and t.get("exit_reason") == "stop"
        and int(t.get("addon_count") or 0) == 0,
        "same_day_stopout": lambda t: t["is_loss"]
        and t.get("exit_reason") == "stop"
        and t.get("hold_days") == 0,
        "clustered_entry_date_loss": lambda t: bool(t.get("entry_date") in clustered_loss_dates),
        "wide_initial_stop_loss": lambda t: t["is_loss"]
        and float(t.get("initial_risk_pct") or 0.0) >= 0.05,
        "energy_stopout_cluster": lambda t: t["is_loss"]
        and t.get("sector") == "Energy"
        and t.get("exit_reason") == "stop",
    }
    family_stats = _family_stats(enriched, predicates)

    losses = [trade for trade in enriched if trade["is_loss"]]
    loss_rows = [
        {
            "ticker": row.get("ticker"),
            "strategy": row.get("strategy"),
            "sector": row.get("sector"),
            "entry_date": row.get("entry_date"),
            "exit_date": row.get("exit_date"),
            "hold_days": row.get("hold_days"),
            "pnl": row.get("pnl"),
            "pnl_pct_net": row.get("pnl_pct_net"),
            "pnl_r": row.get("pnl_r"),
            "initial_risk_pct": row.get("initial_risk_pct"),
            "exit_reason": row.get("exit_reason"),
            "addon_count": row.get("addon_count"),
            "matching_families": [
                name for name, predicate in predicates.items() if predicate(row)
            ],
        }
        for row in losses
    ]

    future_candidates = []
    for name, stats in family_stats.items():
        if stats["loss_count"] >= 2 and (stats["collateral_to_loss_abs"] or 0.0) <= 0.25:
            future_candidates.append(
                {
                    "candidate": name,
                    "why": "Repeated in the primary window with low measured winner collateral.",
                    "not_a_rule_yet": True,
                    "next_test_shape": (
                        "Default-off shadow replay with an orthogonal market/event "
                        "discriminator; do not add a direct filter from this sample."
                    ),
                    "loss_count": stats["loss_count"],
                    "loss_pnl_abs": stats["loss_pnl_abs"],
                    "winner_collateral_count": stats["winner_collateral_count"],
                    "winner_collateral_pnl": stats["winner_collateral_pnl"],
                }
            )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": "bad trade hold-quality taxonomy",
        "strategy_behavior_changed": False,
        "source_result": str(BASELINE_PATH).replace("\\", "/"),
        "window": result.get("period") or {"start": "2025-10-23", "end": "2026-04-21"},
        "baseline_metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "total_pnl": result.get("total_pnl"),
            "win_rate": result.get("win_rate"),
            "trade_count": result.get("total_trades"),
            "survival_rate": result.get("survival_rate"),
        },
        "history_guardrails": {
            "does_not_add_filter": True,
            "does_not_modify_production_strategy": True,
            "does_not_treat_1_to_3_trades_as_rule": True,
            "checks_winner_collateral": True,
        },
        "family_definitions": {
            "stopped_without_addon": "Losing stop exits with no executed add-on.",
            "same_day_stopout": "Losing stop exits on the entry date.",
            "clustered_entry_date_loss": "Entry dates with at least two losers and no winners.",
            "wide_initial_stop_loss": "Losing trades whose initial risk distance is at least 5%.",
            "energy_stopout_cluster": "Energy-sector losing stop exits in the primary window.",
        },
        "aggregate": {
            "trade_count": len(enriched),
            "loss_count": len(losses),
            "win_count": len(enriched) - len(losses),
            "loss_pnl_abs": round(-sum(float(row.get("pnl") or 0.0) for row in losses), 2),
            "winner_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in enriched if not row["is_loss"]),
                2,
            ),
            "clustered_loss_dates": sorted(clustered_loss_dates),
        },
        "family_stats": family_stats,
        "loss_rows": loss_rows,
        "future_test_candidates": future_candidates,
        "interpretation": [
            "The primary window has only four losing trades, so this is an audit sample, not a rule basis.",
            "All four losses are stop exits with no add-on; three are a same-entry-date loss cluster on 2026-01-06.",
            "The cleanest next test is a shadow replay for clustered entry-date adverse state, not a direct stop/no-add-on filter.",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
