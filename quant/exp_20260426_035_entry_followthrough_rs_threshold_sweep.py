"""exp-20260426-035 RS-threshold quality sweep for follow-through add-ons.

The add-on mechanism stays fixed:
day-2 unrealized >= +2%, add 25% of original shares, execution-day caps apply.

Only the relative-strength threshold versus SPY changes. This tests whether
the add-on alpha is improved by requiring clearer leadership, not just a
positive early mark-to-market.
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

RS_THRESHOLDS = OrderedDict([
    ("rs_gt_0pct", 0.0),
    ("rs_ge_0p5pct", 0.005),
    ("rs_ge_1pct", 0.01),
    ("rs_ge_2pct", 0.02),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_035_entry_followthrough_rs_threshold_sweep.json",
)


def _addon_config(rs_threshold: float) -> dict:
    return {
        "REGIME_AWARE_EXIT": True,
        "ADDON_ENABLED": True,
        "ADDON_CHECKPOINT_DAYS": 2,
        "ADDON_MIN_UNREALIZED_PCT": 0.02,
        "ADDON_MIN_RS_VS_SPY": rs_threshold,
        "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
        "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
    }


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


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": "exp-20260426-035",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hypothesis": (
            "Raising the day-2 follow-through add-on RS threshold may improve "
            "trigger quality by requiring clearer leadership versus SPY."
        ),
        "single_causal_variable": "ADDON_MIN_RS_VS_SPY",
        "fixed_parameters": {
            "ADDON_CHECKPOINT_DAYS": 2,
            "ADDON_MIN_UNREALIZED_PCT": 0.02,
            "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
            "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
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

    for name, threshold in RS_THRESHOLDS.items():
        ev_improved = 0
        material_regressions = 0
        ev_delta_sum = 0.0
        pnl_delta_sum = 0.0
        max_dd_worsening = 0.0
        executed_sum = 0
        for label, cfg in WINDOWS.items():
            result = _run_window(universe, cfg, _addon_config(threshold))
            after = _metrics(result)
            before = baselines[label]
            delta = _delta(after, before)
            results["windows"][label]["variants"][name] = {
                "rs_threshold": threshold,
                "after_metrics": after,
                "delta_metrics": delta,
                "events": result.get("addon_attribution", {}).get("events", []),
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
            executed_sum += after.get("addons_executed") or 0

        results["summary"][name] = {
            "rs_threshold": threshold,
            "ev_improved_windows": ev_improved,
            "material_regression_windows": material_regressions,
            "ev_delta_sum": round(ev_delta_sum, 6),
            "pnl_delta_sum": round(pnl_delta_sum, 2),
            "max_drawdown_worsening": round(max_dd_worsening, 6),
            "addons_executed_sum": executed_sum,
            "candidate_gate_passed": ev_improved >= 2 and material_regressions == 0,
        }

    current = results["summary"]["rs_gt_0pct"]
    passed = [
        (name, rec)
        for name, rec in results["summary"].items()
        if rec["candidate_gate_passed"]
    ]
    best_name, best = max(
        passed,
        key=lambda item: (item[1]["ev_delta_sum"], -item[1]["max_drawdown_worsening"]),
    )
    results["best_variant"] = best_name
    results["decision"] = (
        "accepted_variant"
        if best_name != "rs_gt_0pct" and best["ev_delta_sum"] > current["ev_delta_sum"]
        else "rejected_tightening"
    )
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "This is a trigger-quality sweep; add-ons remain default-off until a "
        "material production-promotion gate or forward sample clears."
    )

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
