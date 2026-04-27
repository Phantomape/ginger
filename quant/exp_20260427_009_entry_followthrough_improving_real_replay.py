"""Real replay for improving strict day-2 follow-through add-ons.

The existing research candidate is fixed:
day-2 unrealized >= +2%, RS vs SPY > 0, add 25% of original shares.

This experiment changes one variable only: require day-2 unrealized PnL and
day-2 RS vs SPY to both improve versus day 1 before scheduling the add-on.
The hook is default-off in BacktestEngine.
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


EXPERIMENT_ID = "exp-20260427-010"

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
NORMAL_ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_UNREALIZED_PCT": 0.02,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
    "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": False,
}
IMPROVING_ADDON_CONFIG = {
    **NORMAL_ADDON_CONFIG,
    "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": True,
}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260427_010_entry_followthrough_improving_real_replay.json",
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


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Strict day-2 follow-through add-ons improve when scheduled only "
            "if day-2 unrealized return and RS vs SPY both improve versus day 1."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": (
            "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH default-off trigger-quality hook"
        ),
        "parameters": {
            "base_config": BASE_CONFIG,
            "normal_addon_config": NORMAL_ADDON_CONFIG,
            "improving_addon_config": IMPROVING_ADDON_CONFIG,
        },
        "windows": {},
        "aggregate": {
            "improving_vs_normal_ev_delta_sum": 0.0,
            "improving_vs_normal_pnl_delta_sum": 0.0,
            "improving_vs_base_ev_delta_sum": 0.0,
            "improving_vs_base_pnl_delta_sum": 0.0,
            "windows_improved_vs_normal": 0,
            "windows_regressed_vs_normal": 0,
            "windows_improved_vs_base": 0,
            "normal_executed_addons": 0,
            "improving_executed_addons": 0,
        },
    }

    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, BASE_CONFIG)
        normal = _run_window(universe, cfg, NORMAL_ADDON_CONFIG)
        improving = _run_window(universe, cfg, IMPROVING_ADDON_CONFIG)
        before = _metrics(baseline)
        normal_metrics = _metrics(normal)
        after = _metrics(improving)
        delta_vs_normal = _delta(after, normal_metrics)
        delta_vs_base = _delta(after, before)

        agg = results["aggregate"]
        ev_vs_normal = delta_vs_normal.get("expected_value_score") or 0.0
        pnl_vs_normal = delta_vs_normal.get("total_pnl") or 0.0
        ev_vs_base = delta_vs_base.get("expected_value_score") or 0.0
        pnl_vs_base = delta_vs_base.get("total_pnl") or 0.0
        agg["improving_vs_normal_ev_delta_sum"] += ev_vs_normal
        agg["improving_vs_normal_pnl_delta_sum"] += pnl_vs_normal
        agg["improving_vs_base_ev_delta_sum"] += ev_vs_base
        agg["improving_vs_base_pnl_delta_sum"] += pnl_vs_base
        agg["windows_improved_vs_normal"] += 1 if ev_vs_normal > 0 else 0
        agg["windows_regressed_vs_normal"] += 1 if ev_vs_normal < 0 else 0
        agg["windows_improved_vs_base"] += 1 if ev_vs_base > 0 else 0
        agg["normal_executed_addons"] += normal_metrics["addon"]["executed"] or 0
        agg["improving_executed_addons"] += after["addon"]["executed"] or 0

        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
            "before_metrics": before,
            "normal_25pct_addon_metrics": normal_metrics,
            "after_metrics": after,
            "delta_vs_normal_25pct_addon": delta_vs_normal,
            "delta_vs_baseline": delta_vs_base,
            "improving_addon_events": improving.get("addon_attribution", {}).get("events", []),
        }

    for key in [
        "improving_vs_normal_ev_delta_sum",
        "improving_vs_normal_pnl_delta_sum",
        "improving_vs_base_ev_delta_sum",
        "improving_vs_base_pnl_delta_sum",
    ]:
        results["aggregate"][key] = round(results["aggregate"][key], 6)

    agg = results["aggregate"]
    results["decision"] = (
        "accepted_candidate_not_promoted"
        if (
            agg["windows_improved_vs_base"] >= 2
            and agg["windows_regressed_vs_normal"] == 0
            and agg["improving_vs_base_pnl_delta_sum"] > 0
        )
        else "rejected"
    )
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "Default-off hook only. Promotion would require material Gate 4 strength "
        "versus the no-add-on accepted stack, not just cleaner add-on attribution."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "aggregate": results["aggregate"],
        "decision": results["decision"],
        "wrote": OUT_JSON,
    }, indent=2))
    for label, rec in results["windows"].items():
        b = rec["before_metrics"]
        n = rec["normal_25pct_addon_metrics"]
        a = rec["after_metrics"]
        print(
            f"{label}: base EV {b['expected_value_score']} -> "
            f"normal {n['expected_value_score']} -> improving {a['expected_value_score']}; "
            f"base PnL {b['total_pnl']} -> improving {a['total_pnl']}; "
            f"addons {n['addon']['executed']} -> {a['addon']['executed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
