"""Replay macro ETF candidate-pool expansion variants.

Alpha-search experiment for exp-20260504-028. The snapshots already contain
macro / sector ETFs that are not in the production watchlist. This runner
tests whether adding those tickers to the candidate universe improves the
accepted core strategy across the canonical backtesting.md windows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXP_ID = "exp-20260504-028"

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

VARIANTS = {
    "baseline": [],
    "macro_all": ["TLT", "IEF", "UUP", "USO", "XLE", "XLP", "XLU", "XLV"],
    "xle_only": ["XLE"],
}


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    total_pnl = float(result.get("total_pnl") or 0.0)
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_pnl / 100_000.0, 4),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _run_window(base_universe: list[str], extra_tickers: list[str], window: dict[str, str]) -> dict[str, Any]:
    universe = sorted(set(base_universe) | set(extra_tickers))
    result = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=window["snapshot"],
    ).run()
    extra_trade_rows = [
        {
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": trade.get("pnl"),
        }
        for trade in result.get("trades", [])
        if trade.get("ticker") in set(extra_tickers)
    ]
    return {
        "metrics": _metrics(result),
        "extra_ticker_trades": extra_trade_rows,
        "entry_reason_counts": (
            result.get("entry_execution_attribution", {}).get("reason_counts", {})
        ),
    }


def main() -> int:
    base_universe = get_universe()
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "single_causal_variable": "candidate pool expansion with pre-existing macro ETF OHLCV snapshots",
        "windows": WINDOWS,
        "variants": {},
    }
    for variant, extra_tickers in VARIANTS.items():
        payload["variants"][variant] = {
            "extra_tickers": extra_tickers,
            "windows": {
                label: _run_window(base_universe, extra_tickers, window)
                for label, window in WINDOWS.items()
            },
        }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
