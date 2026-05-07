"""Run candidate-forward / candidate-selection / no-trade-attribution oracles for
the three canonical windows by injecting the news_attribution candidate pool into
known_biases (where oracle_diagnostics looks for it).

Observation-only diagnostic: uses future highs and is NOT tradable.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QUANT = REPO / "quant"
sys.path.insert(0, str(QUANT))

import oracle_diagnostics  # noqa: E402

BACKTEST_DIR = REPO / "data" / "experiments" / "oracle_standard_3window_20260501_220042"
OUT_DIR = REPO / "data" / "experiments" / "oracle_no_entry_restriction_3window"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WINDOWS = ["late_strong", "mid_weak", "old_thin"]


def _inject_candidate_pool(backtest: dict) -> dict:
    bt = copy.deepcopy(backtest)
    na = bt.get("news_attribution") or {}
    pool = na.get("candidate_tickers_by_date") or {}
    counts = na.get("candidate_signal_counts_by_date") or {}
    dates_covered = na.get("candidate_dates_covered") or []

    kb = bt.setdefault("known_biases", {})
    nv = kb.setdefault("news_veto_unreplayed", {})
    nv["candidate_tickers_by_date"] = dict(pool)
    nv["candidate_signal_counts_by_date"] = dict(counts)
    nv["candidate_dates_covered"] = list(dates_covered)
    return bt


def _summarize_window(window: str) -> dict:
    backtest_path = BACKTEST_DIR / f"{window}_backtest.json"
    with backtest_path.open(encoding="utf-8") as f:
        backtest = json.load(f)
    snapshot_path = oracle_diagnostics.infer_snapshot_path(backtest)
    if not snapshot_path:
        raise RuntimeError(f"{window}: no OHLCV snapshot path in known_biases")
    with Path(snapshot_path).open(encoding="utf-8") as f:
        snapshot = json.load(f)

    bt_with_pool = _inject_candidate_pool(backtest)

    perfect_exit = oracle_diagnostics.build_perfect_exit_oracle(
        bt_with_pool, snapshot
    )
    candidate_forward = oracle_diagnostics.build_candidate_forward_oracle(
        bt_with_pool, snapshot, horizon_days=20
    )
    candidate_selection = oracle_diagnostics.build_candidate_selection_oracle(
        bt_with_pool, snapshot, horizon_days=20
    )
    no_trade_attr = oracle_diagnostics.build_no_trade_attribution_oracle(
        bt_with_pool, snapshot, horizon_days=20
    )

    out = {
        "window": window,
        "period": backtest.get("period"),
        "snapshot": snapshot_path,
        "candidate_pool_dates": len(
            bt_with_pool["known_biases"]["news_veto_unreplayed"][
                "candidate_tickers_by_date"
            ]
        ),
        "candidate_pool_total_signals": sum(
            len(v)
            for v in bt_with_pool["known_biases"]["news_veto_unreplayed"][
                "candidate_tickers_by_date"
            ].values()
        ),
        "actual_strategy": {
            "total_pnl": backtest.get("total_pnl"),
            "total_trades": backtest.get("total_trades"),
            "win_rate": backtest.get("win_rate"),
        },
        "perfect_exit_oracle": perfect_exit,
        "candidate_forward_oracle": candidate_forward,
        "candidate_selection_oracle": candidate_selection,
        "no_trade_attribution_oracle": no_trade_attr,
    }

    out_path = OUT_DIR / f"{window}_oracle.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return out


def main():
    summary = {"windows": {}}
    agg = {
        "actual_pnl": 0.0,
        "perfect_exit_oracle_pnl": 0.0,
        "candidate_count": 0,
        "candidate_positive_count": 0,
        "candidate_returns": [],
        "candidate_top1_count": 0,
    }

    for window in WINDOWS:
        result = _summarize_window(window)
        cf = result["candidate_forward_oracle"]
        cs = result["candidate_selection_oracle"]
        pe = result["perfect_exit_oracle"]

        actual = float(result["actual_strategy"].get("total_pnl") or 0.0)
        agg["actual_pnl"] += actual
        agg["perfect_exit_oracle_pnl"] += float(pe.get("oracle_pnl") or 0.0)
        agg["candidate_count"] += int(cf.get("candidate_count") or 0)
        # Re-derive positive count and returns from candidate selection top1 stats
        for tk in cs.get("top_k_summary", {}).values() or []:
            pass
        # collect raw returns by re-reading the top opportunities not enough — pull from cf.top_candidate_opportunities
        top_opps = cf.get("top_candidate_opportunities") or []
        # We need full return distribution; re-read file:
        with (OUT_DIR / f"{window}_oracle.json").open(encoding="utf-8") as f:
            full = json.load(f)
        cf_full = full["candidate_forward_oracle"]
        # candidate_count + frac give positive count
        if cf_full.get("candidate_count"):
            pos_frac = cf_full.get("positive_candidate_fraction") or 0.0
            agg["candidate_positive_count"] += int(round(
                pos_frac * cf_full["candidate_count"]
            ))

        summary["windows"][window] = {
            "period": result["period"],
            "actual_pnl": actual,
            "actual_trades": result["actual_strategy"].get("total_trades"),
            "perfect_exit_oracle_pnl": pe.get("oracle_pnl"),
            "perfect_exit_capture_ratio": pe.get("capture_ratio"),
            "candidate_pool_dates": result["candidate_pool_dates"],
            "candidate_pool_total_signals": result["candidate_pool_total_signals"],
            "candidate_count": cf.get("candidate_count"),
            "positive_candidate_fraction": cf.get("positive_candidate_fraction"),
            "actual_trade_overlap_fraction": cf.get("actual_trade_overlap_fraction"),
            "avg_max_forward_return_pct": cf.get("avg_max_forward_return_pct"),
            "median_max_forward_return_pct": cf.get("median_max_forward_return_pct"),
            "best_max_forward_return_pct": cf.get("best_max_forward_return_pct"),
            "selection_top1_hit_fraction": cs.get("top1_actual_hit_fraction"),
            "selection_top_k_summary": cs.get("top_k_summary"),
            "missed_top1_avg_return_pct": cs.get("missed_top1_avg_max_forward_return_pct"),
        }

    summary["aggregate"] = {
        "actual_pnl": round(agg["actual_pnl"], 2),
        "perfect_exit_oracle_pnl": round(agg["perfect_exit_oracle_pnl"], 2),
        "candidate_count_total": agg["candidate_count"],
        "candidate_positive_count_total": agg["candidate_positive_count"],
    }

    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
