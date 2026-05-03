"""exp-20260503-003 non-commodity low-TQS breakout reactivation sweep.

Alpha search only. The accepted stack has changed materially since the older
non-commodity low-TQS breakout 0x rule was accepted. This script replays whether
restoring a small risk budget now recovers capital-efficient breakout alpha.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import portfolio_engine as pe  # noqa: E402
import exp_20260502_011_old_thin_slot_routing_alpha as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


VARIANTS = {
    "baseline_0x": 0.0,
    "low_tqs_breakout_0_10x": 0.10,
    "low_tqs_breakout_0_25x": 0.25,
    "low_tqs_breakout_0_50x": 0.50,
}


@contextmanager
def _low_tqs_breakout_multiplier(multiplier: float):
    original = pe.LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER
    pe.LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER = multiplier
    try:
        yield
    finally:
        pe.LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER = original


def _run_window(window: dict, multiplier: float) -> dict:
    with _low_tqs_breakout_multiplier(multiplier):
        return BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config=base.CONFIG,
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def main() -> int:
    payload = {}
    for variant, multiplier in VARIANTS.items():
        payload[variant] = {}
        for label, window in base.WINDOWS.items():
            payload[variant][label] = _metrics(_run_window(window, multiplier))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
