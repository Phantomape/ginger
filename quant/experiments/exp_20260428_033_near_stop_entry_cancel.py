"""exp-20260428-033: near-stop next-open entry cancel.

Alpha search. The accepted 2% adverse next-open cancel removes entries that
open materially below the signal entry. This tests one orthogonal execution
quality discriminator: if the next open is still above the planned stop but has
already consumed most of the initial stop distance, the fill may have too little
remaining error budget to be worth taking.

Production defaults are unchanged unless the fixed-window Gate 4 result passes.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-033"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_033_near_stop_entry_cancel.json"

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
    ("baseline_current_cancel", None),
    ("near_stop_risk_remaining_le_15pct", 0.15),
    ("near_stop_risk_remaining_le_25pct", 0.25),
    ("near_stop_risk_remaining_le_35pct", 0.35),
    ("near_stop_risk_remaining_le_50pct", 0.50),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    addon = result.get("addon_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "addon_executed": addon.get("executed"),
        "entry_reason_counts": entry.get("reason_counts", {}),
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


def _run_window(universe: list[str], cfg: dict, risk_remaining_threshold: float | None) -> dict:
    original_classifier = bt.classify_entry_open_cancel

    def near_stop_classifier(
        fill_price,
        signal_entry,
        stop_price=None,
        upside_gap_cancel_pct=None,
        adverse_gap_cancel_pct=None,
    ):
        reason = original_classifier(
            fill_price,
            signal_entry,
            stop_price=stop_price,
            upside_gap_cancel_pct=upside_gap_cancel_pct,
            adverse_gap_cancel_pct=adverse_gap_cancel_pct,
        )
        if reason or risk_remaining_threshold is None:
            return reason
        if fill_price is None or signal_entry is None or stop_price is None:
            return None
        fill = float(fill_price)
        entry = float(signal_entry)
        stop = float(stop_price)
        planned_risk = entry - stop
        if planned_risk <= 0:
            return None
        risk_remaining = (fill - stop) / planned_risk
        if fill > stop and fill < entry and risk_remaining <= risk_remaining_threshold:
            return "adverse_gap_down_cancel"
        return None

    bt.classify_entry_open_cancel = near_stop_classifier
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
        bt.classify_entry_open_cancel = original_classifier

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
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
                "near_stop_risk_remaining_threshold": threshold,
                **result,
            })
            m = result["metrics"]
            reasons = m["entry_reason_counts"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} adverse_cancel={reasons.get('adverse_gap_down_cancel', 0)}"
            )

    baseline_rows = {
        label: next(
            row for row in rows
            if row["window"] == label and row["variant"] == "baseline_current_cancel"
        )
        for label in WINDOWS
    }

    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == "baseline_current_cancel":
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            before = baseline_rows[label]["metrics"]
            after = next(
                row["metrics"] for row in rows
                if row["window"] == label and row["variant"] == variant
            )
            by_window[label] = {
                "before": before,
                "after": after,
                "delta": _delta(after, before),
            }

        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "threshold": VARIANTS[variant],
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
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["windows_improved"] == 3
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "Next-open fills that remain above the planned stop but have already "
            "consumed most of the initial stop distance may be lower-quality "
            "entries; cancelling them could improve capital efficiency without "
            "changing signal generation or exits."
        ),
        "change_summary": (
            "Tested risk-distance-aware next-open entry cancellation thresholds "
            "across the fixed three OHLCV windows. Production defaults remain "
            "unchanged unless Gate 4 passes."
        ),
        "change_type": "alpha_search_entry_execution_quality",
        "component": "quant/experiments/exp_20260428_033_near_stop_entry_cancel.py",
        "parameters": {
            "single_causal_variable": "near-stop next-open entry cancel threshold",
            "baseline": {
                "CANCEL_GAP_PCT": 0.015,
                "ADVERSE_GAP_CANCEL_PCT": 0.02,
                "near_stop_risk_remaining_threshold": None,
            },
            "tested_thresholds": {
                name: value for name, value in VARIANTS.items()
                if name != "baseline_current_cancel"
            },
            "locked_variables": [
                "signal generation",
                "candidate ordering",
                "risk multipliers",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "all exits",
                "upside gap cancel threshold",
                "adverse gap cancel threshold",
                "day-2 add-on trigger and fraction",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline_rows[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            "best_threshold": best_summary["threshold"],
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
        },
        "delta_metrics": {
            "best_variant": best_variant,
            "best_threshold": best_summary["threshold"],
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted because the best near-stop cancel threshold improved all fixed windows and passed Gate 4."
                if accepted else
                "Rejected because no near-stop cancel threshold passed fixed-window Gate 4."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited; this tests a deterministic "
                "entry-execution alpha instead of waiting on LLM ranking data."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": None if accepted else (
            "Near-stop next-open cancellation did not improve entry quality robustly enough for promotion."
        ),
        "next_retry_requires": [
            "Do not retry nearby risk-distance thresholds without a new discriminator.",
            "A valid retry needs intraday reclaim evidence, fresh event context, or forward/paper evidence.",
            "Keep the accepted 2% adverse-gap cancel unchanged unless a separate replay passes all windows.",
        ],
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_threshold": payload["delta_metrics"]["best_threshold"],
        "best_aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
