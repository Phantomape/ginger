"""exp-20260428-024 signal-day close-location entry cancel.

Experiment-only alpha search. This tests whether a trend/breakout signal that
does not close in the upper part of its own signal-day range is a weak execution
candidate. It keeps the existing next-open upside/adverse gap cancels intact and
adds only one temporary cancel predicate in-process.
"""

from __future__ import annotations

import inspect
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import ADVERSE_GAP_CANCEL_PCT, CANCEL_GAP_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from production_parity import classify_entry_open_cancel  # noqa: E402


EXPERIMENT_ID = "exp-20260428-024"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_024_signal_day_close_location_entry_cancel.json"

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

VARIANTS = OrderedDict([
    ("baseline_no_close_location_cancel", None),
    ("close_location_cancel_lt_50", 0.50),
    ("close_location_cancel_lt_60", 0.60),
    ("close_location_cancel_lt_70", 0.70),
])

_state = {
    "threshold": None,
    "cancel_count": 0,
    "cancel_events": [],
}


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


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _stack_context() -> tuple[dict | None, object | None, dict | None]:
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    sig = None
    today = None
    ohlcv_all = None
    while caller is not None:
        if sig is None and isinstance(caller.f_locals.get("sig"), dict):
            sig = caller.f_locals["sig"]
        if today is None and caller.f_locals.get("today") is not None:
            today = caller.f_locals["today"]
        if ohlcv_all is None and isinstance(caller.f_locals.get("ohlcv_all"), dict):
            ohlcv_all = caller.f_locals["ohlcv_all"]
        if sig is not None and today is not None and ohlcv_all is not None:
            break
        caller = caller.f_back
    return sig, today, ohlcv_all


def _signal_day_close_location(sig: dict | None, today, ohlcv_all: dict | None) -> float | None:
    if not sig or today is None or not ohlcv_all:
        return None
    ticker = str(sig.get("ticker") or "").upper()
    df = ohlcv_all.get(ticker)
    if df is None or today not in df.index:
        return None
    row = df.loc[today]
    high = float(row["High"])
    low = float(row["Low"])
    close = float(row["Close"])
    day_range = high - low
    if day_range <= 0:
        return None
    return (close - low) / day_range


def _patched_classifier(
    fill_price,
    signal_entry,
    stop_price=None,
    upside_gap_cancel_pct=None,
    adverse_gap_cancel_pct=ADVERSE_GAP_CANCEL_PCT,
):
    reason = classify_entry_open_cancel(
        fill_price,
        signal_entry,
        stop_price=stop_price,
        upside_gap_cancel_pct=upside_gap_cancel_pct,
        adverse_gap_cancel_pct=adverse_gap_cancel_pct,
    )
    if reason is not None:
        return reason

    threshold = _state["threshold"]
    if threshold is None:
        return None

    sig, today, ohlcv_all = _stack_context()
    close_location = _signal_day_close_location(sig, today, ohlcv_all)
    if close_location is None or close_location >= threshold:
        return None

    _state["cancel_count"] += 1
    _state["cancel_events"].append({
        "date": str(today.date()) if hasattr(today, "date") else str(today),
        "ticker": (sig.get("ticker") or "").upper() if sig else None,
        "strategy": sig.get("strategy") if sig else None,
        "sector": sig.get("sector") if sig else None,
        "threshold": threshold,
        "signal_day_close_location": round(float(close_location), 6),
        "fill_price": round(float(fill_price), 4),
        "signal_entry": round(float(signal_entry), 4),
    })
    # The backtester currently records only known cancel reasons. Return the
    # non-gap cancel bucket and keep exact attribution in cancel_events above.
    return "adverse_gap_down_cancel"


def _run_window(universe: list[str], cfg: dict, threshold: float | None) -> dict:
    _state["threshold"] = threshold
    _state["cancel_count"] = 0
    _state["cancel_events"] = []

    original_classifier = backtester.classify_entry_open_cancel
    backtester.classify_entry_open_cancel = _patched_classifier
    try:
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
        result = engine.run()
    finally:
        backtester.classify_entry_open_cancel = original_classifier

    if "error" in result:
        raise RuntimeError(result["error"])
    reason_counts = result.get("entry_execution_attribution", {}).get("reason_counts", {})
    return {
        "metrics": _metrics(result),
        "signal_day_close_location_cancel_count": int(_state["cancel_count"]),
        "signal_day_close_location_cancel_events": list(_state["cancel_events"]),
        "entry_reason_counts": reason_counts,
        "trades": result.get("trades", []),
    }


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, threshold in VARIANTS.items():
            result = _run_window(universe, cfg, threshold)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "min_signal_day_close_location": threshold,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} trades={m['trade_count']} "
                f"signal_close_cancels={result['signal_day_close_location_cancel_count']}"
            )

    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline_no_close_location_cancel"
            )
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "signal_day_close_location_cancel_count": (
                    candidate["signal_day_close_location_cancel_count"]
                ),
                "cancel_events": candidate["signal_day_close_location_cancel_events"],
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
                ),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(
                    v["delta"]["trade_count"] for v in by_window.values()
                ),
                "signal_day_close_location_cancel_count": sum(
                    v["signal_day_close_location_cancel_count"]
                    for v in by_window.values()
                ),
            },
        }

    best_variant, best = max(
        summary.items(),
        key=lambda item: item[1]["aggregate"]["expected_value_score_delta_sum"],
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "change_type": "entry_execution_signal_day_quality_screen",
        "single_causal_variable": "signal-day close-location entry cancel threshold",
        "hypothesis": (
            "Existing A/B signals that fail to close in the upper part of their "
            "own signal-day range may be weaker execution candidates; canceling "
            "those next-open entries could improve quality without changing "
            "signal generation, exits, sizing, add-ons, or LLM/news replay."
        ),
        "history_guardrails": {
            "not_llm_soft_ranking": True,
            "not_gap_threshold_sweep": True,
            "not_gap_context_exception": True,
            "not_addon_tuning": True,
            "production_strategy_changed": False,
        },
        "parameters": {
            "tested_min_signal_day_close_location": [0.50, 0.60, 0.70],
            "existing_gap_cancels_locked": {
                "CANCEL_GAP_PCT": CANCEL_GAP_PCT,
                "ADVERSE_GAP_CANCEL_PCT": ADVERSE_GAP_CANCEL_PCT,
            },
            "locked_variables": [
                "signal generation",
                "risk sizing",
                "all exits",
                "day-2 follow-through add-on settings",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "windows": WINDOWS,
        "rows": rows,
        "summary": summary,
        "best_variant": best_variant,
        "best_variant_summary": best,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = run_experiment()
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(OUT_JSON),
        "best_variant": result["best_variant"],
        "best_aggregate": result["best_variant_summary"]["aggregate"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
