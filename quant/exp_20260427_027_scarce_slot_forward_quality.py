"""exp-20260427-027: scarce-slot deferred-breakout forward-quality audit.

Single causal variable: no production behavior changes. This audit replays the
existing default-off one-slot breakout defer hook and measures the forward
returns of the candidates it would defer, using only fixed OHLCV snapshots.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from backtester import BacktestEngine

try:
    from data_layer import get_universe
except Exception:
    from filter import WATCHLIST

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260427-027"
HORIZONS = (5, 10, 20)

WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20251023_20260421.json"),
        "regime": "slow-melt bull / accepted-stack dominant tape",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20250423_20251022.json"),
        "regime": "rotation-heavy bull where accepted stack makes money but lags indexes",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"),
        "regime": "mixed-to-weak older tape with lower win rate",
    },
]


def compact_metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    scarce = result.get("scarce_slot_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "breakout_deferred": scarce.get("breakout_deferred", 0),
    }


def load_snapshot(path: str) -> dict[str, pd.DataFrame]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        frame = pd.DataFrame(rows)
        if frame.empty:
            continue
        frame["Date"] = pd.to_datetime(frame["Date"])
        frames[ticker.upper()] = frame.set_index("Date").sort_index()
    return frames


def run_window(universe: list[str], window: dict, defer_breakouts: bool) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 1 if defer_breakouts else None,
        },
        ohlcv_snapshot_path=window["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{window['label']} defer={defer_breakouts}: {result['error']}")
    return result


def forward_return(frames: dict[str, pd.DataFrame], event: dict, horizon: int):
    frame = frames.get((event.get("ticker") or "").upper())
    if frame is None or frame.empty:
        return None
    signal_date = pd.Timestamp(event["date"])
    locs = frame.index[frame.index > signal_date]
    if len(locs) <= horizon:
        return None
    entry_date = locs[0]
    exit_date = locs[horizon]
    entry_open = float(frame.loc[entry_date, "Open"])
    exit_close = float(frame.loc[exit_date, "Close"])
    if entry_open <= 0:
        return None
    return {
        "entry_date": str(entry_date.date()),
        "exit_date": str(exit_date.date()),
        "return_pct": round(exit_close / entry_open - 1.0, 6),
    }


def summarize_forward(events: list[dict]) -> dict:
    summary = {}
    for horizon in HORIZONS:
        values = [
            event[f"fwd_{horizon}d_return_pct"]
            for event in events
            if event.get(f"fwd_{horizon}d_return_pct") is not None
        ]
        if not values:
            summary[f"{horizon}d"] = {
                "count": 0,
                "avg_return_pct": None,
                "median_return_pct": None,
                "win_rate": None,
            }
            continue
        series = pd.Series(values)
        summary[f"{horizon}d"] = {
            "count": int(series.count()),
            "avg_return_pct": round(float(series.mean()), 6),
            "median_return_pct": round(float(series.median()), 6),
            "win_rate": round(float((series > 0).mean()), 4),
        }
    return summary


def metric_delta(after: dict, before: dict, key: str, ndigits: int = 4):
    return round((after.get(key) or 0) - (before.get(key) or 0), ndigits)


def main() -> None:
    universe = get_universe()
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "The modest scarce-slot breakout defer edge may be valid if the "
            "deferred breakout candidates themselves show weak forward quality; "
            "if they are strong, the edge is probably capacity timing and needs "
            "a different discriminator before production promotion."
        ),
        "single_causal_variable": "forward-quality audit of existing DEFER_BREAKOUT_WHEN_SLOTS_LTE=1 hook",
        "windows": WINDOWS,
        "metrics": {},
        "comparisons_vs_baseline": {},
        "deferred_forward_quality": {},
    }

    for window in WINDOWS:
        label = window["label"]
        frames = load_snapshot(window["snapshot"])
        baseline = run_window(universe, window, defer_breakouts=False)
        variant = run_window(universe, window, defer_breakouts=True)
        before = compact_metrics(baseline)
        after = compact_metrics(variant)
        artifact["metrics"][label] = {
            "baseline": before,
            "scarce_slot_breakout_defer": after,
        }
        artifact["comparisons_vs_baseline"][label] = {
            "expected_value_score_delta": metric_delta(after, before, "expected_value_score"),
            "total_pnl_delta": metric_delta(after, before, "total_pnl", 2),
            "sharpe_daily_delta": metric_delta(after, before, "sharpe_daily"),
            "max_drawdown_pct_delta": metric_delta(after, before, "max_drawdown_pct"),
            "win_rate_delta": metric_delta(after, before, "win_rate"),
            "trade_count_delta": (after.get("trade_count") or 0) - (before.get("trade_count") or 0),
            "breakout_deferred": after.get("breakout_deferred", 0),
        }

        events = []
        for event in (variant.get("scarce_slot_attribution") or {}).get("deferred_events", []):
            enriched = dict(event)
            for horizon in HORIZONS:
                fwd = forward_return(frames, event, horizon)
                enriched[f"fwd_{horizon}d_return_pct"] = (
                    fwd["return_pct"] if fwd else None
                )
                if fwd:
                    enriched[f"fwd_{horizon}d_entry_date"] = fwd["entry_date"]
                    enriched[f"fwd_{horizon}d_exit_date"] = fwd["exit_date"]
            events.append(enriched)
        artifact["deferred_forward_quality"][label] = {
            "summary": summarize_forward(events),
            "events": events,
        }

        print(
            f"{label}: EV {before['expected_value_score']} -> {after['expected_value_score']} "
            f"PnL {before['total_pnl']} -> {after['total_pnl']} "
            f"deferred={after.get('breakout_deferred', 0)} "
            f"fwd10={artifact['deferred_forward_quality'][label]['summary']['10d']}"
        )

    comparisons = artifact["comparisons_vs_baseline"]
    artifact["aggregate"] = {
        "windows_improved": sum(
            1 for item in comparisons.values()
            if item["expected_value_score_delta"] > 0
        ),
        "windows_regressed": sum(
            1 for item in comparisons.values()
            if item["expected_value_score_delta"] < 0
        ),
        "ev_delta_sum": round(
            sum(item["expected_value_score_delta"] for item in comparisons.values()),
            4,
        ),
        "pnl_delta_sum": round(
            sum(item["total_pnl_delta"] for item in comparisons.values()),
            2,
        ),
        "total_breakout_deferred": sum(
            item["breakout_deferred"] for item in comparisons.values()
        ),
        "decision": "observed_only",
    }

    out_path = os.path.join(ROOT, "data", f"{EXPERIMENT_ID}_scarce_slot_forward_quality.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
