"""Observed-only sleeve/state slot audit for exp-20260427-011.

This runner does not change signal generation, exits, sizing, or portfolio
rules. It replays the fixed OHLCV windows with the current default stack and
summarizes where realized scarce-slot value came from by strategy sleeve.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402

try:
    from data_layer import get_universe  # noqa: E402
except Exception:  # pragma: no cover - mirrors backtester CLI fallback
    from filter import WATCHLIST  # noqa: E402

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260427-011"
OUTPUT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260427_011_sleeve_state_slot_audit.json"
)

WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "accepted-stack dominant tape",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    },
]


def _safe_div(num, den):
    return round(num / den, 6) if den else None


def _inclusive_days(trade):
    start = datetime.fromisoformat(trade["entry_date"]).date()
    end = datetime.fromisoformat(trade["exit_date"]).date()
    return max((end - start).days + 1, 1)


def _active_before_entry(trades, entry_date):
    day = datetime.fromisoformat(entry_date).date()
    count = 0
    by_strategy = defaultdict(int)
    for trade in trades:
        start = datetime.fromisoformat(trade["entry_date"]).date()
        end = datetime.fromisoformat(trade["exit_date"]).date()
        if start < day <= end:
            count += 1
            by_strategy[trade.get("strategy", "unknown")] += 1
    return count, dict(sorted(by_strategy.items()))


def _summarize_trades(trades):
    total_pnl = sum(float(t.get("pnl", 0.0)) for t in trades)
    wins = [t for t in trades if float(t.get("pnl", 0.0)) > 0]
    slot_days = sum(_inclusive_days(t) for t in trades)
    addon_exec = sum(int(t.get("addon_count", 0) or 0) for t in trades)
    sectors = defaultdict(lambda: {"trade_count": 0, "pnl": 0.0})
    exits = defaultdict(int)
    for trade in trades:
        sector = trade.get("sector", "Unknown")
        sectors[sector]["trade_count"] += 1
        sectors[sector]["pnl"] += float(trade.get("pnl", 0.0))
        exits[trade.get("exit_reason", "unknown")] += 1

    return {
        "trade_count": len(trades),
        "wins": len(wins),
        "losses": len(trades) - len(wins),
        "win_rate": _safe_div(len(wins), len(trades)) or 0.0,
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": _safe_div(total_pnl, len(trades)),
        "avg_pnl_pct_net": _safe_div(
            sum(float(t.get("pnl_pct_net", 0.0)) for t in trades), len(trades)
        ),
        "calendar_slot_days": slot_days,
        "pnl_per_slot_day": _safe_div(total_pnl, slot_days),
        "avg_hold_days": _safe_div(slot_days, len(trades)),
        "addon_executions": addon_exec,
        "sector_pnl": {
            k: {
                "trade_count": v["trade_count"],
                "pnl": round(v["pnl"], 2),
            }
            for k, v in sorted(sectors.items())
        },
        "exit_reasons": dict(sorted(exits.items())),
    }


def _window_audit(result):
    trades = result.get("trades", [])
    annotated = []
    for trade in trades:
        active_before, active_by_strategy = _active_before_entry(
            trades, trade["entry_date"]
        )
        annotated.append(
            {
                **trade,
                "active_positions_before_entry": active_before,
                "active_by_strategy_before_entry": active_by_strategy,
                "scarce_slot_entry": active_before >= 4,
                "calendar_slot_days": _inclusive_days(trade),
            }
        )

    by_strategy = defaultdict(list)
    scarce_by_strategy = defaultdict(list)
    normal_by_strategy = defaultdict(list)
    for trade in annotated:
        strategy = trade.get("strategy", "unknown")
        by_strategy[strategy].append(trade)
        if trade["scarce_slot_entry"]:
            scarce_by_strategy[strategy].append(trade)
        else:
            normal_by_strategy[strategy].append(trade)

    sleeve_metrics = {
        strategy: _summarize_trades(items)
        for strategy, items in sorted(by_strategy.items())
    }
    scarce_metrics = {
        strategy: {
            "scarce_slot": _summarize_trades(scarce_by_strategy.get(strategy, [])),
            "non_scarce_slot": _summarize_trades(normal_by_strategy.get(strategy, [])),
        }
        for strategy in sorted(by_strategy)
    }
    pnl_total = sum(v["total_pnl"] for v in sleeve_metrics.values())
    slot_total = sum(v["calendar_slot_days"] for v in sleeve_metrics.values())
    for strategy, metrics in sleeve_metrics.items():
        metrics["pnl_share"] = _safe_div(metrics["total_pnl"], pnl_total)
        metrics["slot_day_share"] = _safe_div(metrics["calendar_slot_days"], slot_total)

    return {
        "window_metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "total_pnl": result.get("total_pnl"),
            "total_return_pct": (result.get("benchmarks") or {}).get(
                "strategy_total_return_pct"
            ),
            "sharpe_daily": result.get("sharpe_daily"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "win_rate": result.get("win_rate"),
            "trade_count": result.get("total_trades"),
            "survival_rate": result.get("survival_rate"),
            "spy_return_pct": (result.get("benchmarks") or {}).get(
                "spy_buy_hold_return_pct"
            ),
            "qqq_return_pct": (result.get("benchmarks") or {}).get(
                "qqq_buy_hold_return_pct"
            ),
        },
        "sleeve_metrics": sleeve_metrics,
        "scarce_slot_metrics": scarce_metrics,
        "top_scarce_slot_entries": [
            {
                "ticker": t.get("ticker"),
                "strategy": t.get("strategy"),
                "sector": t.get("sector"),
                "entry_date": t.get("entry_date"),
                "pnl": round(float(t.get("pnl", 0.0)), 2),
                "pnl_pct_net": t.get("pnl_pct_net"),
                "active_positions_before_entry": t["active_positions_before_entry"],
                "active_by_strategy_before_entry": t[
                    "active_by_strategy_before_entry"
                ],
                "exit_reason": t.get("exit_reason"),
            }
            for t in sorted(
                [x for x in annotated if x["scarce_slot_entry"]],
                key=lambda x: float(x.get("pnl", 0.0)),
                reverse=True,
            )[:10]
        ],
    }


def _derive_findings(windows):
    mid = windows["mid_weak"]["audit"]
    late = windows["late_strong"]["audit"]
    old = windows["old_thin"]["audit"]
    findings = []
    for strategy in sorted(mid["sleeve_metrics"]):
        mid_m = mid["sleeve_metrics"][strategy]
        late_m = late["sleeve_metrics"].get(strategy, {})
        old_m = old["sleeve_metrics"].get(strategy, {})
        findings.append(
            {
                "strategy": strategy,
                "mid_weak_pnl": mid_m.get("total_pnl"),
                "mid_weak_pnl_per_slot_day": mid_m.get("pnl_per_slot_day"),
                "mid_weak_win_rate": mid_m.get("win_rate"),
                "late_strong_pnl_per_slot_day": late_m.get("pnl_per_slot_day"),
                "old_thin_pnl_per_slot_day": old_m.get("pnl_per_slot_day"),
                "mid_weak_pnl_share": mid_m.get("pnl_share"),
                "mid_weak_slot_day_share": mid_m.get("slot_day_share"),
            }
        )

    future_testable = []
    if findings:
        best_mid = max(
            findings,
            key=lambda x: (
                x["mid_weak_pnl_per_slot_day"]
                if x["mid_weak_pnl_per_slot_day"] is not None
                else -10**9
            ),
        )
        worst_mid = min(
            findings,
            key=lambda x: (
                x["mid_weak_pnl_per_slot_day"]
                if x["mid_weak_pnl_per_slot_day"] is not None
                else 10**9
            ),
        )
        if best_mid["strategy"] != worst_mid["strategy"]:
            future_testable.append(
                "Audit supports a future conditional sleeve-routing experiment "
                f"only if state features explain why {best_mid['strategy']} "
                f"earns more per slot-day than {worst_mid['strategy']} in mid_weak."
            )

    return {
        "sleeve_state_findings": findings,
        "future_testable_hypotheses": future_testable,
        "production_ready": False,
        "production_ready_reason": (
            "Observed-only attribution map. It identifies candidate routing "
            "questions but does not test a counterfactual allocation rule."
        ),
    }


def main():
    universe = get_universe()
    windows = {}
    for spec in WINDOWS:
        engine = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True},
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
        windows[spec["label"]] = {
            "range": {"start": spec["start"], "end": spec["end"]},
            "snapshot": spec["snapshot"],
            "state_note": spec["state_note"],
            "audit": _window_audit(result),
        }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "lane": "alpha_discovery",
        "change_type": "capital_allocation",
        "single_causal_variable": "sleeve-state scarce-slot contribution map",
        "strategy_behavior_changed": False,
        "config": {
            "REGIME_AWARE_EXIT": True,
            "ADDON_ENABLED": "default_true_after_exp_20260427_013",
            "ADDON_MAX_POSITION_PCT": "default_0.35_after_exp_20260427_013",
        },
        "windows": windows,
        "derived": _derive_findings(windows),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(OUTPUT_PATH),
        "production_ready": artifact["derived"]["production_ready"],
        "future_testable_hypotheses": artifact["derived"][
            "future_testable_hypotheses"
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
