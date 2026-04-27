"""Shadow sweep for CANCEL_GAP_PCT.

This runner does not change strategy code. It temporarily sets the imported
backtester.CANCEL_GAP_PCT module variable in-process, runs deterministic
backtests, and writes a compact comparison table.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load_universe():
    try:
        from data_layer import get_universe
        return get_universe()
    except Exception:
        from filter import WATCHLIST
        return list(WATCHLIST)


def _compact_result(result):
    entry_attr = result.get("entry_execution_attribution") or {}
    return {
        "period": result.get("period"),
        "total_trades": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "total_pnl": result.get("total_pnl"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "expected_value_score": result.get("expected_value_score"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "entry_reason_counts": entry_attr.get("reason_counts"),
        "entry_candidate_events": entry_attr.get("candidate_events"),
        "entry_skipped_count": entry_attr.get("skipped_count"),
    }


def run_gap_cancel_sweep(
    start,
    end,
    thresholds,
    snapshot_path=None,
    replay_llm=False,
    replay_news=False,
    regime_aware_exit=False,
):
    import backtester
    from backtester import BacktestEngine

    universe = _load_universe()
    original = backtester.CANCEL_GAP_PCT
    rows = []
    try:
        for threshold in thresholds:
            backtester.CANCEL_GAP_PCT = float(threshold)
            engine = BacktestEngine(
                universe,
                start=start,
                end=end,
                config={"REGIME_AWARE_EXIT": regime_aware_exit},
                replay_llm=replay_llm,
                replay_news=replay_news,
                ohlcv_snapshot_path=snapshot_path,
            )
            result = engine.run()
            row = {
                "cancel_gap_pct": float(threshold),
                **_compact_result(result),
            }
            if "error" in result:
                row["error"] = result["error"]
            rows.append(row)
    finally:
        backtester.CANCEL_GAP_PCT = original

    baseline = next((row for row in rows if row["cancel_gap_pct"] == thresholds[0]), None)
    if baseline and baseline.get("expected_value_score") is not None:
        base_ev = baseline.get("expected_value_score")
        base_pnl = baseline.get("total_pnl")
        for row in rows:
            if row.get("expected_value_score") is not None:
                row["expected_value_score_delta_vs_first"] = round(
                    row["expected_value_score"] - base_ev,
                    6,
                )
            if row.get("total_pnl") is not None and base_pnl is not None:
                row["total_pnl_delta_vs_first"] = round(row["total_pnl"] - base_pnl, 2)

    return {
        "sweep_type": "cancel_gap_pct_shadow",
        "is_tradable_change": False,
        "note": (
            "This temporarily mutates backtester.CANCEL_GAP_PCT in-process for "
            "measurement only. Promote nothing without multi-window validation."
        ),
        "start": start,
        "end": end,
        "snapshot_path": os.path.abspath(snapshot_path) if snapshot_path else None,
        "replay_llm": replay_llm,
        "replay_news": replay_news,
        "regime_aware_exit": regime_aware_exit,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.015, 0.02, 0.03])
    parser.add_argument("--ohlcv-snapshot")
    parser.add_argument("--replay-llm", action="store_true")
    parser.add_argument("--replay-news", action="store_true")
    parser.add_argument("--regime-aware-exit", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    result = run_gap_cancel_sweep(
        args.start,
        args.end,
        args.thresholds,
        snapshot_path=args.ohlcv_snapshot,
        replay_llm=args.replay_llm,
        replay_news=args.replay_news,
        regime_aware_exit=args.regime_aware_exit,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
