"""Observed-only audit for wide-stop accepted-stack losses.

This script changes no strategy behavior. It measures one pre-entry failure
family: trades with a stop distance of at least 5% that still stopped out at a
loss, then estimates likely winner collateral for any future pre-entry rule.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260427-008"
OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260427_008_wide_stop_distance_audit.json")
WIDE_STOP_DISTANCE_PCT_MIN = 0.05

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with weaker follow-through",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape",
    }),
])

CONFIG = {"REGIME_AWARE_EXIT": True}


def _round(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if isinstance(value, (int, float)) else None


def _stop_distance_pct(trade: dict) -> float | None:
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    if isinstance(entry, (int, float)) and isinstance(stop, (int, float)) and entry > 0:
        return (entry - stop) / entry
    risk = trade.get("initial_risk_pct")
    return risk if isinstance(risk, (int, float)) else None


def _trade_row(trade: dict, window: str) -> dict:
    stop_distance = _stop_distance_pct(trade)
    pnl = trade.get("pnl") or 0.0
    is_wide = isinstance(stop_distance, (int, float)) and stop_distance >= WIDE_STOP_DISTANCE_PCT_MIN
    return {
        "window": window,
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": trade.get("entry_price"),
        "stop_price": trade.get("stop_price"),
        "exit_price": trade.get("exit_price"),
        "stop_distance_pct": _round(stop_distance),
        "target_mult_used": trade.get("target_mult_used"),
        "pnl": round(pnl, 2),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "wide_stop": is_wide,
        "family_match": is_wide and pnl <= 0 and trade.get("exit_reason") == "stop",
        "winner_collateral_match": is_wide and pnl > 0,
    }


def _summary(rows: list[dict]) -> dict:
    pnls = [row["pnl"] for row in rows if isinstance(row.get("pnl"), (int, float))]
    stop_distances = [
        row["stop_distance_pct"]
        for row in rows
        if isinstance(row.get("stop_distance_pct"), (int, float))
    ]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "avg_stop_distance_pct": _round(mean(stop_distances)) if stop_distances else None,
        "median_stop_distance_pct": _round(median(stop_distances)) if stop_distances else None,
        "strategy_counts": dict(sorted(Counter(row.get("strategy") or "unknown" for row in rows).items())),
        "sector_counts": dict(sorted(Counter(row.get("sector") or "unknown" for row in rows).items())),
        "window_counts": dict(sorted(Counter(row.get("window") or "unknown" for row in rows).items())),
    }


def _run_window(label: str, cfg: dict, universe: list[str]) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    rows = [_trade_row(trade, label) for trade in result.get("trades", [])]
    family_rows = [row for row in rows if row["family_match"]]
    collateral_rows = [row for row in rows if row["winner_collateral_match"]]
    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe": result.get("sharpe"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_pnl": result.get("total_pnl"),
            "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
            "survival_rate": result.get("survival_rate"),
        },
        "trade_count": len(rows),
        "wide_stop_trade_count": sum(1 for row in rows if row["wide_stop"]),
        "family_summary": _summary(family_rows),
        "winner_collateral_summary": _summary(collateral_rows),
        "family_rows": sorted(family_rows, key=lambda row: (row["ticker"] or "", row["entry_date"] or "")),
        "winner_collateral_rows": sorted(
            collateral_rows,
            key=lambda row: (-(row.get("pnl") or 0.0), row["ticker"] or ""),
        ),
    }


def _aggregate(windows: OrderedDict[str, dict]) -> dict:
    family_rows = []
    collateral_rows = []
    for payload in windows.values():
        family_rows.extend(payload["family_rows"])
        collateral_rows.extend(payload["winner_collateral_rows"])
    bad_abs = abs(sum(row.get("pnl") or 0.0 for row in family_rows))
    collateral_pnl = sum(row.get("pnl") or 0.0 for row in collateral_rows)
    collateral_ratio = collateral_pnl / bad_abs if bad_abs > 0 else None
    by_window = defaultdict(lambda: {"family_count": 0, "family_pnl_sum": 0.0, "winner_collateral_count": 0, "winner_collateral_pnl_sum": 0.0})
    for row in family_rows:
        bucket = by_window[row["window"]]
        bucket["family_count"] += 1
        bucket["family_pnl_sum"] += row.get("pnl") or 0.0
    for row in collateral_rows:
        bucket = by_window[row["window"]]
        bucket["winner_collateral_count"] += 1
        bucket["winner_collateral_pnl_sum"] += row.get("pnl") or 0.0
    return {
        "family_definition": {
            "name": "wide_stop_distance_stopout",
            "stop_distance_pct_min": WIDE_STOP_DISTANCE_PCT_MIN,
            "bad_trade_condition": "pnl <= 0 and exit_reason == stop",
            "collateral_condition": "pnl > 0 and stop_distance_pct >= threshold",
        },
        "occurrence_count": len(family_rows),
        "family_pnl_sum": round(sum(row.get("pnl") or 0.0 for row in family_rows), 2),
        "winner_collateral_count": len(collateral_rows),
        "winner_collateral_pnl_sum": round(collateral_pnl, 2),
        "winner_collateral_to_bad_pnl_abs_ratio": _round(collateral_ratio, 4),
        "windows_with_family": sorted({row["window"] for row in family_rows}),
        "by_window": {
            window: {
                "family_count": values["family_count"],
                "family_pnl_sum": round(values["family_pnl_sum"], 2),
                "winner_collateral_count": values["winner_collateral_count"],
                "winner_collateral_pnl_sum": round(values["winner_collateral_pnl_sum"], 2),
            }
            for window, values in sorted(by_window.items())
        },
        "family_summary": _summary(family_rows),
        "winner_collateral_summary": _summary(collateral_rows),
        "decision_hint": "High winner collateral; do not convert wide stop distance into a direct pre-entry filter or broad sizing haircut.",
    }


def main() -> int:
    universe = get_universe()
    windows = OrderedDict()
    for label, cfg in WINDOWS.items():
        windows[label] = _run_window(label, cfg, universe)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "change_type": "failure_taxonomy",
        "single_causal_variable": "wide stop-distance bad-trade taxonomy",
        "strategy_behavior_changed": False,
        "filters_added": False,
        "config": CONFIG,
        "thresholds": {
            "wide_stop_distance_pct_min": WIDE_STOP_DISTANCE_PCT_MIN,
        },
        "historical_constraints_checked": [
            "Not a repeat of today's exp-20260427-004 early_flush_no_reclaim observed-only audit.",
            "Not a low-MFE price-only lifecycle exit replay; exp-20260426-053 rejected that family due winner truncation.",
            "Not a weak-hold day-5/day-10 exit; playbook rejects nearby weak-hold and sector-confirmed variants.",
            "Not a gap-down, near-target giveback, or sector-relative breakdown audit already covered on 2026-04-26.",
        ],
        "windows": windows,
        "aggregate": _aggregate(windows),
        "notes": [
            "Observed-only audit; no strategy logic changed.",
            "Winner collateral is intentionally measured as all profitable wide-stop trades because any pre-entry wide-stop rule would likely touch them.",
            "High collateral means this family is explanatory, not directly actionable as a filter.",
        ],
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": os.path.relpath(OUT_JSON, REPO_ROOT),
        "aggregate": payload["aggregate"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
