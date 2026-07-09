"""exp-20260706-006: deep-drawdown rebound with per-episode entry budget of one.

Replays the exp-20260706-003 policy bundle plus ``max_entries_per_episode=1``
(first stabilization day per episode only) over the merged pre-2023 archive +
warehouse QQQ series, and writes the episode-level artifact. The daily
default-off snapshot ships through run.py with the same BUDGET_CONFIG.

Reproduce:
  .venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260706_006_deep_drawdown_rebound_budget.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT = REPO_ROOT / "quant"
EXPERIMENTS = QUANT / "experiments"
for path in (QUANT, EXPERIMENTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from data_paths import DATA_ROOT, atomic_write_json  # noqa: E402
from deep_drawdown_rebound_paper_sleeve import (  # noqa: E402
    BUDGET_CONFIG,
    RULE_VERSION,
    load_index_history_rows,
    merge_bar_series,
    replay_deep_drawdown_rebound_trades,
)
from exp_20260706_003_deep_drawdown_rebound import (  # noqa: E402
    STANDARD_WINDOWS,
    _warehouse_rows,
    _window_slice,
)

EXPERIMENT_ID = "exp-20260706-006"
ARTIFACT_PATH = (
    DATA_ROOT
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260706_006_deep_drawdown_rebound_budget.json"
)


def main() -> int:
    ticker = str(BUDGET_CONFIG["ticker"]).upper()
    archive_rows = load_index_history_rows(ticker)
    if not archive_rows:
        print("[replay] pre-2023 archive missing; run exp-20260706-003 backfill", file=sys.stderr)
        return 2
    warehouse_rows, warehouse_path = _warehouse_rows(ticker)
    merged = merge_bar_series(archive_rows, warehouse_rows)
    result = replay_deep_drawdown_rebound_trades(merged, BUDGET_CONFIG)
    trades = result["trades"]

    spy = merge_bar_series(load_index_history_rows("SPY"), _warehouse_rows("SPY")[0])
    spy_close = {row["date"]: row["close"] for row in spy if row.get("close")}
    for trade in trades:
        entry_close = spy_close.get(trade.get("entry_date"))
        exit_close = spy_close.get(trade.get("exit_date"))
        if entry_close and exit_close:
            spy_ret = (float(exit_close) / float(entry_close)) - 1.0
            trade["spy_same_window_return_pct"] = round(spy_ret, 6)
            trade["excess_vs_spy_pct"] = round((trade.get("pnl_pct_net") or 0.0) - spy_ret, 6)

    closed = [t for t in trades if t.get("paper_status") == "closed"]
    excess = [t["excess_vs_spy_pct"] for t in closed if t.get("excess_vs_spy_pct") is not None]
    returns = [t["pnl_pct_net"] for t in closed if t.get("pnl_pct_net") is not None]
    mean = sum(returns) / len(returns) if returns else None
    stdev = None
    tstat = None
    if returns and len(returns) > 2 and mean is not None:
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        stdev = var**0.5
        if stdev > 0:
            tstat = mean / (stdev / len(returns) ** 0.5)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "baseline_experiment_id": "exp-20260706-003",
        "rule_version": RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "series": {
            "ticker": ticker,
            "archive_rows": len(archive_rows),
            "warehouse_rows": len(warehouse_rows),
            "warehouse_path": warehouse_path,
            "merged_rows": len(merged),
            "first_date": merged[0]["date"] if merged else None,
            "last_date": merged[-1]["date"] if merged else None,
        },
        "parameters": result["parameters"],
        "summary": result["summary"],
        "significance": {
            "mean_return_pct": round(mean, 6) if mean is not None else None,
            "stdev_return_pct": round(stdev, 6) if stdev is not None else None,
            "t_stat": round(tstat, 3) if tstat is not None else None,
            "note": (
                "Episode-level sample; t-stat < 2 means the replay alone cannot "
                "settle the verdict — settled forward rows from live episodes are "
                "the decisive evidence."
            ),
        },
        "spy_replacement": {
            "trades_with_spy_context": len(excess),
            "mean_excess_vs_spy_pct": round(sum(excess) / len(excess), 6) if excess else None,
            "positive_excess_count": sum(1 for e in excess if e > 0),
        },
        "standard_windows": {
            name: _window_slice(trades, start, end)
            for name, (start, end) in STANDARD_WINDOWS.items()
        },
        "trades": trades,
        "unresolved": result["unresolved"],
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(artifact, ARTIFACT_PATH)
    summary = result["summary"]
    print(
        f"[replay] budget=1: {summary['closed_trades']} closed trades across "
        f"{summary['distinct_episodes']} episodes; total pnl ${summary['total_pnl']}, "
        f"win rate {summary['win_rate']}, mean {summary['mean_return_pct']}, "
        f"t={artifact['significance']['t_stat']}"
    )
    print(f"[replay] artifact -> {ARTIFACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
