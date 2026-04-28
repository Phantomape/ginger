"""exp-20260427-034 state-qualified Industrials trend risk sleeve.

Hypothesis:
    The rejected broad `trend_long | Industrials` restoration failed because it
    reopened weak-window pollution. Restore only a tiny 0.10x sleeve when both
    SPY/QQQ are strongly extended above their moving averages, leaving all other
    Industrials trend candidates at the current 0x risk.

This runner is experiment-only. It monkeypatches signal annotation and sizing
in-process and does not change production strategy code.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402
import signal_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260427-034"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260427_034_state_qualified_industrials_trend.json"

STATE_MIN_INDEX_PCT_FROM_MA = 0.10
RESTORED_MULTIPLIER = 0.10

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _zero_sizing(sig: dict) -> dict:
    sizing = dict(sig.get("sizing") or {})
    sizing.update({
        "risk_pct": 0.0,
        "risk_amount_usd": 0.0,
        "shares_to_buy": 0,
        "position_value_usd": 0.0,
        "position_pct_of_portfolio": 0.0,
        "trend_industrials_state_gate_applied": 0.0,
    })
    return {**sig, "sizing": sizing}


@contextmanager
def _state_qualified_industrials_patch(enabled: bool):
    original_generate = signal_engine.generate_signals
    original_size = portfolio_engine.size_signals
    original_multiplier = portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER

    def generate_with_state(*args, **kwargs):
        market_context = kwargs.get("market_context") or {}
        spy_pct = market_context.get("spy_pct_from_ma")
        qqq_pct = market_context.get("qqq_pct_from_ma")
        min_index_pct = None
        state_ok = False
        if spy_pct is not None and qqq_pct is not None:
            min_index_pct = min(spy_pct, qqq_pct)
            state_ok = min_index_pct >= STATE_MIN_INDEX_PCT_FROM_MA
        signals = original_generate(*args, **kwargs)
        if not enabled:
            return signals
        return [
            {
                **sig,
                "min_index_pct_from_ma": min_index_pct,
                "trend_industrials_state_qualified": state_ok,
            }
            for sig in signals
        ]

    def size_with_state(signals, portfolio_value, risk_pct=None):
        if not enabled:
            return original_size(signals, portfolio_value, risk_pct=risk_pct)

        portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = RESTORED_MULTIPLIER
        try:
            sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        finally:
            portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = original_multiplier

        out = []
        for sig in sized:
            is_industrials_trend = (
                sig.get("strategy") == "trend_long"
                and sig.get("sector") == "Industrials"
            )
            if is_industrials_trend and not sig.get("trend_industrials_state_qualified"):
                out.append(_zero_sizing(sig))
            else:
                out.append(sig)
        return out

    signal_engine.generate_signals = generate_with_state
    portfolio_engine.size_signals = size_with_state
    portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = (
        RESTORED_MULTIPLIER if enabled else original_multiplier
    )
    try:
        yield
    finally:
        signal_engine.generate_signals = original_generate
        portfolio_engine.size_signals = original_size
        portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = original_multiplier


def _run_window(universe: list[str], cfg: dict, enabled: bool) -> dict:
    with _state_qualified_industrials_patch(enabled):
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        )
        return engine.run()


def _targeted_trades(result: dict) -> list[dict]:
    trades = []
    for trade in result.get("trades", []):
        sizing = trade.get("sizing_multipliers") or {}
        if sizing.get("trend_industrials_risk_multiplier_applied") == RESTORED_MULTIPLIER:
            trades.append({
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "return_pct": trade.get("return_pct"),
                "exit_reason": trade.get("exit_reason"),
                "actual_risk_pct": trade.get("actual_risk_pct"),
                "sizing_multipliers": sizing,
            })
    return trades


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, enabled=False)
        candidate = _run_window(universe, cfg, enabled=True)
        before = _metrics(baseline)
        after = _metrics(candidate)
        targeted = _targeted_trades(candidate)
        row = {
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": _delta(after, before),
            "targeted_trade_count": len(targeted),
            "targeted_trade_pnl": round(
                sum(float(t.get("pnl") or 0.0) for t in targeted),
                2,
            ),
            "targeted_trades": targeted,
        }
        print(
            f"[{label}] EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} | PnL {before['total_pnl']} -> "
            f"{after['total_pnl']} | targeted={len(targeted)}"
        )
        rows.append(row)

    ev_delta_sum = round(
        sum(row["delta_metrics"]["expected_value_score"] for row in rows),
        6,
    )
    pnl_delta_sum = round(sum(row["delta_metrics"]["total_pnl"] for row in rows), 2)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Trend Industrials restoration can be alpha-positive only in an "
            "extremely risk-on tape; restore 0.10x risk when min(SPY, QQQ) "
            "pct_from_ma is at least 10%, otherwise keep the current 0x rule."
        ),
        "change_type": "capital_allocation_shadow",
        "parameters": {
            "single_causal_variable": "state-qualified trend Industrials risk restoration",
            "baseline_multiplier": 0.0,
            "candidate_multiplier": RESTORED_MULTIPLIER,
            "state_min_index_pct_from_ma": STATE_MIN_INDEX_PCT_FROM_MA,
            "unchanged": [
                "entries",
                "exits",
                "LLM/news replay",
                "follow-through add-ons",
                "scarce-slot breakout routing",
                "all non-Industrials sizing rules",
            ],
        },
        "windows": WINDOWS,
        "results": rows,
        "summary": {
            "expected_value_score_delta_sum": ev_delta_sum,
            "total_pnl_delta_sum": pnl_delta_sum,
            "windows_improved": sum(
                1 for row in rows
                if row["delta_metrics"]["expected_value_score"] > 0
            ),
            "windows_regressed": sum(
                1 for row in rows
                if row["delta_metrics"]["expected_value_score"] < 0
            ),
            "max_drawdown_delta_max": max(
                row["delta_metrics"]["max_drawdown_pct"] for row in rows
            ),
            "targeted_trade_count": sum(row["targeted_trade_count"] for row in rows),
            "targeted_trade_pnl": round(sum(row["targeted_trade_pnl"] for row in rows), 2),
        },
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
