"""exp-20260426-011 add-on fraction sweep for entry follow-through.

This is a tightness check after exp-20260426-010. The trigger stays fixed:
day-2 unrealized >= +2% and RS vs SPY > 0. Only the add-on fraction changes.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict
from datetime import datetime


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


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

FRACTIONS = OrderedDict([
    ("addon_10pct", 0.10),
    ("addon_15pct", 0.15),
    ("addon_25pct", 0.25),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_011_entry_followthrough_addon_fraction_sweep.json",
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
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "addons_scheduled": addon.get("scheduled"),
        "addons_executed": addon.get("executed"),
        "addons_skipped": addon.get("skipped"),
    }


def _delta(after: dict, before: dict) -> dict:
    fields = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
    ]
    return {
        field: (
            round(after[field] - before[field], 6)
            if isinstance(after.get(field), (int, float))
            and isinstance(before.get(field), (int, float))
            else None
        )
        for field in fields
    }


def _addon_config(fraction: float) -> dict:
    return {
        "REGIME_AWARE_EXIT": True,
        "ADDON_ENABLED": True,
        "ADDON_CHECKPOINT_DAYS": 2,
        "ADDON_MIN_UNREALIZED_PCT": 0.02,
        "ADDON_MIN_RS_VS_SPY": 0.0,
        "ADDON_FRACTION_OF_ORIGINAL_SHARES": fraction,
    }


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": "exp-20260426-011",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hypothesis": (
            "The strict day-2 follow-through add-on may have a better "
            "risk/reward tradeoff at 10-15% than the prior 25% add-on."
        ),
        "single_causal_variable": "ADDON_FRACTION_OF_ORIGINAL_SHARES",
        "fixed_trigger": {
            "ADDON_CHECKPOINT_DAYS": 2,
            "ADDON_MIN_UNREALIZED_PCT": 0.02,
            "ADDON_MIN_RS_VS_SPY": 0.0,
        },
        "windows": {},
        "summary": {},
    }

    baselines = {}
    for label, cfg in WINDOWS.items():
        baselines[label] = _metrics(_run_window(universe, cfg, BASE_CONFIG))
        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "baseline": baselines[label],
            "variants": {},
        }

    for name, fraction in FRACTIONS.items():
        ev_improved = 0
        material_regressions = 0
        ev_delta_sum = 0.0
        pnl_delta_sum = 0.0
        max_dd_worsening = 0.0
        for label, cfg in WINDOWS.items():
            after = _metrics(_run_window(universe, cfg, _addon_config(fraction)))
            before = baselines[label]
            delta = _delta(after, before)
            results["windows"][label]["variants"][name] = {
                "fraction": fraction,
                "after_metrics": after,
                "delta_metrics": delta,
            }
            if (after.get("expected_value_score") or 0) > (before.get("expected_value_score") or 0):
                ev_improved += 1
            b_ev = before.get("expected_value_score") or 0
            a_ev = after.get("expected_value_score") or 0
            if b_ev > 0 and (b_ev - a_ev) / b_ev > 0.05:
                material_regressions += 1
            ev_delta_sum += delta.get("expected_value_score") or 0.0
            pnl_delta_sum += delta.get("total_pnl") or 0.0
            max_dd_worsening = max(max_dd_worsening, delta.get("max_drawdown_pct") or 0.0)

        results["summary"][name] = {
            "fraction": fraction,
            "ev_improved_windows": ev_improved,
            "material_regression_windows": material_regressions,
            "ev_delta_sum": round(ev_delta_sum, 6),
            "pnl_delta_sum": round(pnl_delta_sum, 2),
            "max_drawdown_worsening": round(max_dd_worsening, 6),
            "candidate_gate_passed": ev_improved >= 2 and material_regressions == 0,
        }

    passed = [
        (name, rec)
        for name, rec in results["summary"].items()
        if rec["candidate_gate_passed"]
    ]
    if passed:
        best_name, best = max(
            passed,
            key=lambda item: (item[1]["ev_delta_sum"], -item[1]["max_drawdown_worsening"]),
        )
        results["decision"] = "accepted_candidate"
        results["best_variant"] = best_name
        results["production_promotion"] = False
        results["production_promotion_reason"] = (
            "Fraction sweep is a follow-up tightness check; keep add-on default-off "
            "until a material production-promotion gate or forward sample clears."
        )
    else:
        results["decision"] = "rejected"
        results["best_variant"] = None
        results["production_promotion"] = False
        results["production_promotion_reason"] = "No fraction passed candidate gate."

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps(results["summary"], indent=2))
    print(f"decision: {results['decision']} best={results['best_variant']}")
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
