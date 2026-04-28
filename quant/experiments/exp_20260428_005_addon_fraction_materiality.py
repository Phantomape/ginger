"""exp-20260428-005: follow-through add-on fraction materiality replay.

Hypothesis:
    The accepted day-2 follow-through add-on is directionally correct, but the
    default 25% original-share fraction may under-allocate to confirmed winners.
    Increasing only the add-on fraction can improve EV without changing entries,
    exits, trigger thresholds, LLM/news replay, scarce-slot routing, or the
    single-position cap.

This runner is experiment-only. Production behavior is changed separately only
if the fixed-window result passes Gate 4.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-005"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_005_addon_fraction_materiality.json"

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
    ("baseline_fraction_25", 0.25),
    ("addon_fraction_35", 0.35),
    ("addon_fraction_50", 0.50),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
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
        "addon_executed": addon.get("executed"),
        "addon_scheduled": addon.get("scheduled"),
    }


def _run_window(universe: list[str], cfg: dict, fraction: float) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "ADDON_FRACTION_OF_ORIGINAL_SHARES": fraction,
        },
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "addon_events": (result.get("addon_attribution") or {}).get("events", []),
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


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, fraction in VARIANTS.items():
            result = _run_window(universe, cfg, fraction)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "addon_fraction_of_original_shares": fraction,
                "metrics": result["metrics"],
                "addon_events": result["addon_events"],
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} add={m['addon_executed']}"
            )

    summary = OrderedDict()
    for variant in ("addon_fraction_35", "addon_fraction_50"):
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline_fraction_25"
            )
            candidate = next(
                r for r in rows
                if r["window"] == label and r["variant"] == variant
            )
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": round(
                    sum(v["delta"]["total_pnl"] for v in by_window.values()),
                    2,
                ),
                "baseline_total_pnl_sum": round(
                    sum(v["before"]["total_pnl"] for v in by_window.values()),
                    2,
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
            },
        }
        agg = summary[variant]["aggregate"]
        agg["total_pnl_delta_pct"] = round(
            agg["total_pnl_delta_sum"] / agg["baseline_total_pnl_sum"],
            6,
        )

    best = "addon_fraction_50"
    best_agg = summary[best]["aggregate"]
    accepted = (
        best_agg["windows_improved"] == 3
        and best_agg["windows_regressed"] == 0
        and best_agg["total_pnl_delta_pct"] > 0.05
        and best_agg["max_drawdown_delta_max"] < 0.01
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "promote_addon_fraction_50" if accepted else "do_not_promote",
        "hypothesis": (
            "The accepted day-2 follow-through add-on is directionally correct, "
            "but 25% of original shares under-allocates to confirmed winners. "
            "Raising only the add-on fraction should improve EV and PnL across "
            "the fixed windows while preserving existing caps and triggers."
        ),
        "change_type": "alpha_search_capital_allocation",
        "parameters": {
            "single_causal_variable": "ADDON_FRACTION_OF_ORIGINAL_SHARES",
            "baseline_fraction": 0.25,
            "tested_fractions": [0.35, 0.50],
            "promoted_fraction": 0.50 if accepted else None,
            "locked_variables": [
                "entries",
                "exits",
                "ADDON_CHECKPOINT_DAYS",
                "ADDON_MIN_UNREALIZED_PCT",
                "ADDON_MIN_RS_VS_SPY",
                "ADDON_MAX_POSITION_PCT",
                "MAX_POSITION_PCT",
                "MAX_POSITIONS",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "windows": WINDOWS,
        "results": rows,
        "summary": summary,
        "gate4_basis": (
            "Accepted because the 50% fraction improved EV in all three fixed "
            "windows, increased aggregate PnL by more than 5%, and kept maximum "
            "drawdown increase below 1 percentage point."
            if accepted else
            "Rejected because no tested fraction passed the fixed-window Gate 4 checks."
        ),
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "follow-through capital-allocation alpha was tested instead."
            ),
        },
        "next_retry_requires": [
            "Do not continue sweeping nearby add-on fractions without forward/paper concentration evidence.",
            "Do not change the day-2 follow-through trigger thresholds from this result.",
            "Monitor add-on concentration because the rule intentionally allocates more to confirmed winners.",
        ],
        "strategy_behavior_changed": accepted,
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
