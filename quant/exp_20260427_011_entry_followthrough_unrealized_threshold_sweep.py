"""Real replay sweep for strict day-2 follow-through add-on strength.

The accepted-stack defaults stay unchanged. This experiment changes one
research variable only: the minimum day-2 unrealized return required before
scheduling the default-off 25% add-on.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260427-011"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with weaker follow-through",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
ADDON_BASE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
    "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": False,
}
THRESHOLDS = [0.02, 0.03, 0.04, 0.05]

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260427_011_entry_followthrough_unrealized_threshold_sweep.json",
)


def _run_window(universe: list[str], cfg: dict, config: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _metrics(result: dict) -> dict:
    addon = result.get("addon_attribution", {})
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "survival_rate": result.get("survival_rate"),
        "addon": {
            "scheduled": addon.get("scheduled"),
            "executed": addon.get("executed"),
            "skipped": addon.get("skipped"),
            "checkpoint_rejected": addon.get("checkpoint_rejected"),
        },
    }


def _delta(after: dict, before: dict) -> dict:
    fields = [
        "expected_value_score",
        "sharpe",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
    ]
    out = {}
    for field in fields:
        a = after.get(field)
        b = before.get(field)
        out[field] = (
            round(a - b, 6)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else None
        )
    return out


def _addon_config(threshold: float) -> dict:
    return {
        **ADDON_BASE_CONFIG,
        "ADDON_MIN_UNREALIZED_PCT": threshold,
    }


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Strict day-2 follow-through add-ons may have better production "
            "materiality if the absolute unrealized-return threshold is "
            "tightened above the current +2% research candidate."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": "ADDON_MIN_UNREALIZED_PCT threshold sweep",
        "parameters": {
            "base_config": BASE_CONFIG,
            "fixed_addon_config": ADDON_BASE_CONFIG,
            "thresholds": THRESHOLDS,
        },
        "windows": {},
        "aggregate": {},
    }

    aggregate = {
        str(threshold): {
            "ev_delta_vs_no_addon_sum": 0.0,
            "pnl_delta_vs_no_addon_sum": 0.0,
            "ev_delta_vs_2pct_sum": 0.0,
            "pnl_delta_vs_2pct_sum": 0.0,
            "windows_improved_vs_no_addon": 0,
            "windows_regressed_vs_2pct": 0,
            "executed_addons": 0,
        }
        for threshold in THRESHOLDS
    }

    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, BASE_CONFIG)
        baseline_metrics = _metrics(baseline)
        threshold_results = {}

        for threshold in THRESHOLDS:
            result = _run_window(universe, cfg, _addon_config(threshold))
            threshold_results[str(threshold)] = {
                "metrics": _metrics(result),
                "addon_events": result.get("addon_attribution", {}).get("events", []),
            }

        normal_metrics = threshold_results["0.02"]["metrics"]
        for threshold in THRESHOLDS:
            key = str(threshold)
            metrics = threshold_results[key]["metrics"]
            delta_vs_no_addon = _delta(metrics, baseline_metrics)
            delta_vs_2pct = _delta(metrics, normal_metrics)
            threshold_results[key]["delta_vs_no_addon"] = delta_vs_no_addon
            threshold_results[key]["delta_vs_2pct"] = delta_vs_2pct

            agg = aggregate[key]
            ev_base = delta_vs_no_addon.get("expected_value_score") or 0.0
            pnl_base = delta_vs_no_addon.get("total_pnl") or 0.0
            ev_normal = delta_vs_2pct.get("expected_value_score") or 0.0
            pnl_normal = delta_vs_2pct.get("total_pnl") or 0.0
            agg["ev_delta_vs_no_addon_sum"] += ev_base
            agg["pnl_delta_vs_no_addon_sum"] += pnl_base
            agg["ev_delta_vs_2pct_sum"] += ev_normal
            agg["pnl_delta_vs_2pct_sum"] += pnl_normal
            agg["windows_improved_vs_no_addon"] += 1 if ev_base > 0 else 0
            agg["windows_regressed_vs_2pct"] += 1 if ev_normal < 0 else 0
            agg["executed_addons"] += metrics["addon"]["executed"] or 0

        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
            "baseline": baseline_metrics,
            "threshold_results": threshold_results,
        }

    for key, agg in aggregate.items():
        for numeric_key in [
            "ev_delta_vs_no_addon_sum",
            "pnl_delta_vs_no_addon_sum",
            "ev_delta_vs_2pct_sum",
            "pnl_delta_vs_2pct_sum",
        ]:
            agg[numeric_key] = round(agg[numeric_key], 6)

    candidates = sorted(
        aggregate.items(),
        key=lambda item: (
            item[1]["windows_regressed_vs_2pct"] == 0,
            item[1]["ev_delta_vs_2pct_sum"],
            item[1]["ev_delta_vs_no_addon_sum"],
        ),
        reverse=True,
    )
    best_threshold, best_agg = candidates[0]
    results["aggregate"] = aggregate
    results["best_threshold"] = float(best_threshold)
    results["decision"] = (
        "accepted_candidate_not_promoted"
        if (
            best_agg["windows_improved_vs_no_addon"] == len(WINDOWS)
            and best_agg["windows_regressed_vs_2pct"] == 0
            and best_agg["ev_delta_vs_2pct_sum"] > 0
            and best_agg["pnl_delta_vs_2pct_sum"] > 0
        )
        else "rejected"
    )
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "The add-on path remains default-off research. Promotion requires "
        "material Gate 4 strength versus the accepted no-add-on production stack."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "aggregate": results["aggregate"],
        "best_threshold": results["best_threshold"],
        "decision": results["decision"],
        "wrote": OUT_JSON,
    }, indent=2))
    for label, rec in results["windows"].items():
        baseline = rec["baseline"]
        parts = []
        for threshold in THRESHOLDS:
            metrics = rec["threshold_results"][str(threshold)]["metrics"]
            parts.append(
                f"{threshold:.0%}: EV {metrics['expected_value_score']} "
                f"PnL {metrics['total_pnl']} add-ons {metrics['addon']['executed']}"
            )
        print(
            f"{label}: base EV {baseline['expected_value_score']} "
            f"PnL {baseline['total_pnl']} | " + " | ".join(parts)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
