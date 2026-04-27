"""exp-20260426-005 shadow runner for reduced-risk Technology trend sleeve.

Hypothesis:
    The accepted stack's already-reduced-risk `trend_long | Technology` sleeve
    is still avoidable drag. Zeroing only that sleeve in shadow mode may
    improve the fixed windows more cleanly than the rejected broad trend
    de-risking families.

This runner does not edit shared production logic. It replays the real
backtester and temporarily wraps `portfolio_engine.size_signals()` inside this
process only.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260426_005_results.json")
TARGET_MULTIPLIER_KEYS = (
    "trend_tech_tight_gap_risk_multiplier_applied",
    "trend_tech_gap_risk_multiplier_applied",
    "trend_tech_near_high_risk_multiplier_applied",
    "trend_tech_dte_risk_multiplier_applied",
)


def _round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def _metric_snapshot(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
        "total_pnl": result.get("total_pnl"),
    }


def _delta(after: dict, before: dict, key: str):
    a = after.get(key)
    b = before.get(key)
    if a is None or b is None:
        return None
    return round(a - b, 6)


def _targeted_reduced_risk_signal(signal: dict) -> bool:
    if signal.get("strategy") != "trend_long":
        return False
    if signal.get("sector") != "Technology":
        return False
    sizing = signal.get("sizing") or {}
    for key in TARGET_MULTIPLIER_KEYS:
        multiplier = sizing.get(key)
        if multiplier is not None and 0 < float(multiplier) < 1:
            return True
    return False


def _zero_sizing(sizing: dict) -> dict:
    zeroed = dict(sizing)
    zeroed["risk_pct"] = 0.0
    zeroed["risk_amount_usd"] = 0.0
    zeroed["shares_to_buy"] = 0
    zeroed["position_value_usd"] = 0.0
    zeroed["position_pct_of_portfolio"] = 0.0
    zeroed["shadow_zeroed_reduced_risk_tech_trend"] = True
    return zeroed


@contextmanager
def _patched_size_signals():
    original = portfolio_engine.size_signals

    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        patched = []
        for signal in sized:
            if _targeted_reduced_risk_signal(signal):
                patched.append({**signal, "sizing": _zero_sizing(signal["sizing"])})
            else:
                patched.append(signal)
        return patched

    portfolio_engine.size_signals = wrapped
    try:
        yield
    finally:
        portfolio_engine.size_signals = original


def _run_window(universe: list[str], cfg: dict, shadow: bool) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    if shadow:
        with _patched_size_signals():
            return engine.run()
    return engine.run()


def _is_targeted_trade(trade: dict) -> bool:
    if trade.get("strategy") != "trend_long":
        return False
    if trade.get("sector") != "Technology":
        return False
    sizing_multipliers = trade.get("sizing_multipliers") or {}
    for key in (
        "trend_tech_tight_gap_risk_multiplier_applied",
        "trend_tech_gap_risk_multiplier_applied",
        "trend_tech_near_high_risk_multiplier_applied",
        "trend_tech_dte_risk_multiplier_applied",
    ):
        multiplier = sizing_multipliers.get(key)
        if multiplier is not None and 0 < float(multiplier) < 1:
            return True
    return False


def _trade_key(trade: dict) -> str:
    return "|".join([
        str(trade.get("ticker")),
        str(trade.get("entry_date")),
        str(trade.get("exit_date")),
        str(trade.get("strategy")),
    ])


def _window_summary(label: str, cfg: dict, baseline: dict, shadow: dict) -> dict:
    baseline_metrics = _metric_snapshot(baseline)
    shadow_metrics = _metric_snapshot(shadow)
    targeted_trades = [trade for trade in baseline.get("trades", []) if _is_targeted_trade(trade)]
    baseline_trade_keys = {_trade_key(trade) for trade in baseline.get("trades", [])}
    shadow_trade_keys = {_trade_key(trade) for trade in shadow.get("trades", [])}
    removed_trade_keys = sorted(baseline_trade_keys - shadow_trade_keys)

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": baseline_metrics,
        "shadow_metrics": shadow_metrics,
        "delta_metrics": {
            key: _delta(shadow_metrics, baseline_metrics, key)
            for key in baseline_metrics
        },
        "targeted_baseline_trade_count": len(targeted_trades),
        "targeted_baseline_trade_pnl_usd": round(
            sum(float(trade.get("pnl") or 0.0) for trade in targeted_trades),
            2,
        ),
        "targeted_baseline_trade_examples": [
            {
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": trade.get("pnl"),
                "actual_risk_pct": trade.get("actual_risk_pct"),
                "sizing_multipliers": trade.get("sizing_multipliers") or {},
            }
            for trade in targeted_trades[:5]
        ],
        "removed_trade_count": len(removed_trade_keys),
        "removed_trade_keys": removed_trade_keys[:10],
        "improved_primary_gate": bool(
            (_delta(shadow_metrics, baseline_metrics, "expected_value_score") or 0.0) > 0
        ),
    }


def _decision_support(window_summaries: list[dict]) -> dict:
    improved_ev_windows = [
        row["window"]
        for row in window_summaries
        if (row["delta_metrics"].get("expected_value_score") or 0.0) > 0
    ]
    improved_sharpe_windows = [
        row["window"]
        for row in window_summaries
        if (row["delta_metrics"].get("sharpe_daily") or 0.0) > 0
    ]
    materially_regressed_windows = [
        row["window"]
        for row in window_summaries
        if (row["delta_metrics"].get("expected_value_score") or 0.0) <= -0.05
    ]
    promote_candidate = (
        len(improved_ev_windows) >= 2
        and not materially_regressed_windows
    )
    return {
        "majority_ev_improved": len(improved_ev_windows) >= 2,
        "all_ev_improved": len(improved_ev_windows) == len(window_summaries),
        "improved_ev_windows": improved_ev_windows,
        "improved_sharpe_windows": improved_sharpe_windows,
        "materially_regressed_windows": materially_regressed_windows,
        "promote_candidate": promote_candidate,
        "why_not": (
            None
            if promote_candidate
            else (
                "Shadow zeroing improved some windows but caused a material EV regression in "
                f"{', '.join(materially_regressed_windows)}."
                if materially_regressed_windows
                else "Shadow zeroing did not improve expected_value_score in a majority of fixed windows."
            )
        ),
    }


def _root_result_from_window(summary: dict) -> dict:
    metrics = summary["shadow_metrics"]
    return {
        "period": f"{summary['start']} -> {summary['end']}",
        "total_trades": metrics["trade_count"],
        "win_rate": metrics["win_rate"],
        "total_pnl": metrics["total_pnl"],
        "sharpe": metrics["sharpe"],
        "sharpe_daily": metrics["sharpe_daily"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "survival_rate": metrics["survival_rate"],
        "expected_value_score": metrics["expected_value_score"],
        "benchmarks": {
            "strategy_total_return_pct": metrics["total_return_pct"],
        },
    }


def main() -> int:
    universe = get_universe()
    window_summaries = []
    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, shadow=False)
        shadow = _run_window(universe, cfg, shadow=True)
        summary = _window_summary(label, cfg, baseline, shadow)
        window_summaries.append(summary)
        print(
            f"[{label}] EV {summary['baseline_metrics']['expected_value_score']} -> "
            f"{summary['shadow_metrics']['expected_value_score']} | "
            f"targeted_trades={summary['targeted_baseline_trade_count']} "
            f"removed={summary['removed_trade_count']}"
        )

    decision_support = _decision_support(window_summaries)
    root = _root_result_from_window(next(
        summary for summary in window_summaries if summary["window"] == "old_thin"
    ))
    root["experiment_id"] = "exp-20260426-005"
    root["status"] = "shadow_mode"
    root["single_causal_variable"] = "trend_long Technology reduced_risk zero-risk sleeve"
    root["window_summaries"] = window_summaries
    root["decision_support"] = decision_support

    with open(OUT_JSON, "w", encoding="utf-8") as handle:
        json.dump(root, handle, indent=2)
        handle.write("\n")

    print(json.dumps({
        "experiment_id": "exp-20260426-005",
        "decision_support": decision_support,
    }, indent=2))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
