"""exp-20260426-012 checkpoint cap-room semantics for follow-through add-ons.

The trigger and size stay fixed from exp-20260426-011:
day-2 unrealized >= +2%, RS vs SPY > 0, add 25% of original shares.

Only the scheduling semantics change: the strict variant requires real cap room
on the checkpoint day before scheduling an add-on for the next open.
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

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}

ADDON_BASE = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_UNREALIZED_PCT": 0.02,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
}

ADDON_CHECKPOINT_CAP_ROOM = {
    **ADDON_BASE,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": True,
}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_012_entry_followthrough_cap_room_results.json",
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
        "addons_checkpoint_rejected": addon.get("checkpoint_rejected"),
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


def _summary(results_by_window: dict, variant_name: str, baseline_name: str) -> dict:
    ev_improved = 0
    material_regressions = 0
    ev_delta_sum = 0.0
    pnl_delta_sum = 0.0
    max_dd_worsening = 0.0
    for rec in results_by_window.values():
        before = rec[baseline_name]
        after = rec[variant_name]
        if (after.get("expected_value_score") or 0) > (before.get("expected_value_score") or 0):
            ev_improved += 1
        b_ev = before.get("expected_value_score") or 0
        a_ev = after.get("expected_value_score") or 0
        if b_ev > 0 and (b_ev - a_ev) / b_ev > 0.05:
            material_regressions += 1
        delta = _delta(after, before)
        ev_delta_sum += delta.get("expected_value_score") or 0.0
        pnl_delta_sum += delta.get("total_pnl") or 0.0
        max_dd_worsening = max(max_dd_worsening, delta.get("max_drawdown_pct") or 0.0)
    return {
        "ev_improved_windows": ev_improved,
        "material_regression_windows": material_regressions,
        "ev_delta_sum": round(ev_delta_sum, 6),
        "pnl_delta_sum": round(pnl_delta_sum, 2),
        "max_drawdown_worsening": round(max_dd_worsening, 6),
    }


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": "exp-20260426-012",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hypothesis": (
            "Requiring real cap room on the checkpoint day may remove noisy "
            "unexecutable follow-through add-ons and improve the strict 25% "
            "add-on candidate's EV/risk tradeoff."
        ),
        "single_causal_variable": "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM",
        "fixed_parameters": ADDON_BASE,
        "windows": {},
    }

    for label, cfg in WINDOWS.items():
        baseline_result = _run_window(universe, cfg, BASE_CONFIG)
        addon_result = _run_window(universe, cfg, ADDON_BASE)
        cap_room_result = _run_window(universe, cfg, ADDON_CHECKPOINT_CAP_ROOM)
        baseline = _metrics(baseline_result)
        addon = _metrics(addon_result)
        cap_room = _metrics(cap_room_result)
        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "baseline": baseline,
            "addon_25pct": addon,
            "addon_25pct_checkpoint_cap_room": cap_room,
            "delta_vs_baseline": {
                "addon_25pct": _delta(addon, baseline),
                "addon_25pct_checkpoint_cap_room": _delta(cap_room, baseline),
            },
            "delta_vs_addon_25pct": _delta(cap_room, addon),
            "checkpoint_rejected_events": [
                e for e in cap_room_result.get("addon_attribution", {}).get("events", [])
                if str(e.get("status", "")).startswith("rejected_checkpoint_")
            ],
        }

    results["summary_vs_baseline"] = {
        "addon_25pct": _summary(results["windows"], "addon_25pct", "baseline"),
        "addon_25pct_checkpoint_cap_room": _summary(
            results["windows"],
            "addon_25pct_checkpoint_cap_room",
            "baseline",
        ),
    }
    results["summary_vs_addon_25pct"] = _summary(
        results["windows"],
        "addon_25pct_checkpoint_cap_room",
        "addon_25pct",
    )
    cap_summary = results["summary_vs_baseline"]["addon_25pct_checkpoint_cap_room"]
    plain_summary = results["summary_vs_baseline"]["addon_25pct"]
    if (
        cap_summary["ev_improved_windows"] >= 2
        and cap_summary["material_regression_windows"] == 0
        and cap_summary["ev_delta_sum"] >= plain_summary["ev_delta_sum"]
    ):
        decision = "accepted_candidate"
    else:
        decision = "rejected_variant"
    results["decision"] = decision
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "This tests cap-room semantics only; production add-ons remain default-off."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "summary_vs_baseline": results["summary_vs_baseline"],
        "summary_vs_addon_25pct": results["summary_vs_addon_25pct"],
        "decision": results["decision"],
    }, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
