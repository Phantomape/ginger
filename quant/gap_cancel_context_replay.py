"""Shadow replay for context-aware gap-cancel relaxation.

Observation only. This monkeypatches backtester.should_cancel_gap in-process so
we can test a narrow continuation-gap hypothesis without changing production
strategy constants.
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

from gap_cancel_threshold_sweep import _compact_result, _load_universe  # noqa: E402


def _scalar(value):
    try:
        return float(value.item() if hasattr(value, "item") else value)
    except Exception:
        return None


def _context_for_signal(sig, today, ohlcv_all):
    ticker = sig.get("ticker")
    df = ohlcv_all.get(ticker) if ohlcv_all is not None else None
    if df is None or today is None:
        return {}
    prior = df.loc[:today]
    if prior is None or len(prior) < 6:
        return {}

    close = _scalar(prior.iloc[-1].get("Close"))
    close_5 = _scalar(prior.iloc[-6].get("Close"))
    high_252 = max(
        (_scalar(row.get("High")) or 0)
        for _, row in prior.tail(252).iterrows()
    )
    if close is None or close_5 is None or close_5 == 0:
        prior_5d = None
    else:
        prior_5d = (close / close_5) - 1

    return {
        "prior_5d_return_pct": prior_5d,
        "pct_from_252d_high": ((close / high_252) - 1) if close and high_252 else None,
    }


def make_context_gap_cancel_predicate(
    base_threshold=0.015,
    relaxed_threshold=0.05,
    min_prior_5d_return=0.20,
    max_pct_from_252d_high=-0.05,
):
    """Allow only strong continuation-looking gaps between base and relaxed caps."""
    stats = {
        "base_cancel_count": 0,
        "context_relaxed_count": 0,
        "context_rejected_count": 0,
    }

    def should_cancel(fill_price, signal_entry, sig=None, today=None, ohlcv_all=None):
        if not fill_price or not signal_entry:
            return False
        gap_pct = (float(fill_price) / float(signal_entry)) - 1
        if gap_pct <= base_threshold:
            return False
        stats["base_cancel_count"] += 1
        if gap_pct > relaxed_threshold:
            stats["context_rejected_count"] += 1
            return True

        context = _context_for_signal(sig or {}, today, ohlcv_all)
        prior_5d = context.get("prior_5d_return_pct")
        pct_from_high = context.get("pct_from_252d_high")
        if (
            prior_5d is not None
            and pct_from_high is not None
            and prior_5d >= min_prior_5d_return
            and pct_from_high <= max_pct_from_252d_high
        ):
            stats["context_relaxed_count"] += 1
            return False

        stats["context_rejected_count"] += 1
        return True

    should_cancel.stats = stats
    return should_cancel


def run_context_replay(
    start,
    end,
    snapshot_path,
    base_threshold=0.015,
    relaxed_threshold=0.05,
    min_prior_5d_return=0.20,
    max_pct_from_252d_high=-0.05,
    replay_llm=False,
    replay_news=False,
    regime_aware_exit=False,
):
    import backtester
    from backtester import BacktestEngine

    universe = _load_universe()
    original_predicate = backtester.should_cancel_gap
    rows = []
    try:
        # Baseline.
        baseline_engine = BacktestEngine(
            universe,
            start=start,
            end=end,
            config={"REGIME_AWARE_EXIT": regime_aware_exit},
            replay_llm=replay_llm,
            replay_news=replay_news,
            ohlcv_snapshot_path=snapshot_path,
        )
        baseline = baseline_engine.run()
        rows.append({"variant": "baseline", **_compact_result(baseline)})

        predicate = make_context_gap_cancel_predicate(
            base_threshold=base_threshold,
            relaxed_threshold=relaxed_threshold,
            min_prior_5d_return=min_prior_5d_return,
            max_pct_from_252d_high=max_pct_from_252d_high,
        )
        backtester.should_cancel_gap = predicate
        context_engine = BacktestEngine(
            universe,
            start=start,
            end=end,
            config={"REGIME_AWARE_EXIT": regime_aware_exit},
            replay_llm=replay_llm,
            replay_news=replay_news,
            ohlcv_snapshot_path=snapshot_path,
        )
        context_result = context_engine.run()
        rows.append({
            "variant": "context_relaxed",
            "context_rule": {
                "base_threshold": base_threshold,
                "relaxed_threshold": relaxed_threshold,
                "min_prior_5d_return": min_prior_5d_return,
                "max_pct_from_252d_high": max_pct_from_252d_high,
                **predicate.stats,
            },
            **_compact_result(context_result),
        })
    finally:
        backtester.should_cancel_gap = original_predicate

    if len(rows) == 2:
        base = rows[0]
        for row in rows[1:]:
            row["expected_value_score_delta_vs_baseline"] = round(
                (row.get("expected_value_score") or 0)
                - (base.get("expected_value_score") or 0),
                6,
            )
            row["total_pnl_delta_vs_baseline"] = round(
                (row.get("total_pnl") or 0) - (base.get("total_pnl") or 0),
                2,
            )

    return {
        "replay_type": "context_gap_cancel_relaxation",
        "is_tradable_change": False,
        "note": "Shadow replay only; production gap cancel logic is not changed.",
        "start": start,
        "end": end,
        "snapshot_path": os.path.abspath(snapshot_path) if snapshot_path else None,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--ohlcv-snapshot", required=True)
    parser.add_argument("--base-threshold", type=float, default=0.015)
    parser.add_argument("--relaxed-threshold", type=float, default=0.05)
    parser.add_argument("--min-prior-5d-return", type=float, default=0.20)
    parser.add_argument("--max-pct-from-252d-high", type=float, default=-0.05)
    parser.add_argument("--replay-llm", action="store_true")
    parser.add_argument("--replay-news", action="store_true")
    parser.add_argument("--regime-aware-exit", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    result = run_context_replay(
        args.start,
        args.end,
        args.ohlcv_snapshot,
        base_threshold=args.base_threshold,
        relaxed_threshold=args.relaxed_threshold,
        min_prior_5d_return=args.min_prior_5d_return,
        max_pct_from_252d_high=args.max_pct_from_252d_high,
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
