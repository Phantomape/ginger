"""Shadow replay for strict day-2 follow-through add-on cap headroom.

The add-on candidate stays fixed:
day-2 unrealized >= +2%, RS vs SPY > 0, add 25% of original shares.

This runner changes one variable only: the single-position cap used by the
add-on execution cap. Initial entries, exits, ranking, LLM, portfolio heat, and
production constants are left unchanged. The implementation uses a scoped
runtime patch of ``backtester.MAX_POSITION_PCT`` because ticket scope forbids
editing shared BacktestEngine code.
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

import backtester as backtester_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from constants import MAX_POSITION_PCT as PRODUCTION_MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260426-027"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / AI-beta continuation",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with crowding risk",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak macro tape",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "ADDON_ENABLED": True,
    "ADDON_CHECKPOINT_DAYS": 2,
    "ADDON_MIN_UNREALIZED_PCT": 0.02,
    "ADDON_MIN_RS_VS_SPY": 0.0,
    "ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
}

ADDON_ONLY_CAP_VARIANTS = OrderedDict([
    ("addon_cap_27_5pct", 0.275),
    ("addon_cap_30pct", 0.30),
    ("addon_cap_35pct", 0.35),
])

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_027_entry_followthrough_addon_cap_headroom_results.json",
)


def _run_window(universe: list[str], cfg: dict, config: dict, addon_cap: float | None = None) -> dict:
    old_cap = backtester_module.MAX_POSITION_PCT
    if addon_cap is not None:
        backtester_module.MAX_POSITION_PCT = addon_cap
    try:
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
    finally:
        backtester_module.MAX_POSITION_PCT = old_cap


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
        "addons_executed",
        "addons_skipped",
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


def _event_status_counts(result: dict) -> dict:
    counts: dict[str, int] = {}
    for event in result.get("addon_attribution", {}).get("events", []):
        status = event.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _executed_addon_trade_keys(result: dict) -> set[tuple]:
    keys = set()
    for event in result.get("addon_attribution", {}).get("events", []):
        if event.get("status") == "executed":
            keys.add((
                event.get("ticker"),
                event.get("strategy"),
                event.get("checkpoint_date"),
                event.get("scheduled_fill_date"),
            ))
    return keys


def _newly_executed_events(normal_result: dict, variant_result: dict) -> list[dict]:
    normal_keys = _executed_addon_trade_keys(normal_result)
    rows = []
    trades = variant_result.get("trades", [])
    for event in variant_result.get("addon_attribution", {}).get("events", []):
        key = (
            event.get("ticker"),
            event.get("strategy"),
            event.get("checkpoint_date"),
            event.get("scheduled_fill_date"),
        )
        if event.get("status") != "executed" or key in normal_keys:
            continue
        matching_trade = next(
            (
                trade for trade in trades
                if trade.get("ticker") == event.get("ticker")
                and trade.get("strategy") == event.get("strategy")
                and trade.get("addon_count", 0)
            ),
            None,
        )
        rows.append({
            **event,
            "matched_exit_date": matching_trade.get("exit_date") if matching_trade else None,
            "matched_exit_reason": matching_trade.get("exit_reason") if matching_trade else None,
            "matched_trade_pnl": matching_trade.get("pnl") if matching_trade else None,
        })
    return rows


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Strict day-2 follow-through add-ons may be under-executed by the "
            "existing single-position cap; add-on-only cap headroom may capture "
            "skipped confirmed-winner upside."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": "strict day2 follow-through add-on-only cap headroom",
        "fixed_addon_config": ADDON_CONFIG,
        "production_max_position_pct": PRODUCTION_MAX_POSITION_PCT,
        "addon_only_cap_variants": ADDON_ONLY_CAP_VARIANTS,
        "parity_warning": (
            "Shadow mode only. This locally patches backtester.MAX_POSITION_PCT "
            "around add-on replay runs; no production constants or shared "
            "strategy modules are modified."
        ),
        "windows": {},
        "aggregate_by_variant": {},
    }

    aggregate = {
        name: {
            "ev_delta_vs_normal_addon_sum": 0.0,
            "pnl_delta_vs_normal_addon_sum": 0.0,
            "maxdd_delta_vs_normal_addon_max": 0.0,
            "windows_improved_ev": 0,
            "windows_regressed_ev": 0,
            "newly_executed_count": 0,
        }
        for name in ADDON_ONLY_CAP_VARIANTS
    }

    for label, cfg in WINDOWS.items():
        baseline_result = _run_window(universe, cfg, BASE_CONFIG)
        normal_result = _run_window(universe, cfg, ADDON_CONFIG)
        baseline_metrics = _metrics(baseline_result)
        normal_metrics = _metrics(normal_result)

        window = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
            "baseline": baseline_metrics,
            "normal_25pct_addon": normal_metrics,
            "normal_25pct_delta_vs_baseline": _delta(normal_metrics, baseline_metrics),
            "normal_status_counts": _event_status_counts(normal_result),
            "variants": {},
        }

        for name, addon_cap in ADDON_ONLY_CAP_VARIANTS.items():
            variant_result = _run_window(universe, cfg, ADDON_CONFIG, addon_cap=addon_cap)
            variant_metrics = _metrics(variant_result)
            delta_vs_normal = _delta(variant_metrics, normal_metrics)
            new_events = _newly_executed_events(normal_result, variant_result)

            window["variants"][name] = {
                "addon_only_cap": addon_cap,
                "metrics": variant_metrics,
                "delta_vs_normal_25pct_addon": delta_vs_normal,
                "status_counts": _event_status_counts(variant_result),
                "newly_executed_events": new_events,
            }

            agg = aggregate[name]
            ev_delta = delta_vs_normal.get("expected_value_score") or 0.0
            pnl_delta = delta_vs_normal.get("total_pnl") or 0.0
            maxdd_delta = delta_vs_normal.get("max_drawdown_pct") or 0.0
            agg["ev_delta_vs_normal_addon_sum"] += ev_delta
            agg["pnl_delta_vs_normal_addon_sum"] += pnl_delta
            agg["maxdd_delta_vs_normal_addon_max"] = max(
                agg["maxdd_delta_vs_normal_addon_max"],
                maxdd_delta,
            )
            agg["windows_improved_ev"] += 1 if ev_delta > 0 else 0
            agg["windows_regressed_ev"] += 1 if ev_delta < 0 else 0
            agg["newly_executed_count"] += len(new_events)

        results["windows"][label] = window

    for name, agg in aggregate.items():
        results["aggregate_by_variant"][name] = {
            "ev_delta_vs_normal_addon_sum": round(agg["ev_delta_vs_normal_addon_sum"], 6),
            "pnl_delta_vs_normal_addon_sum": round(agg["pnl_delta_vs_normal_addon_sum"], 2),
            "maxdd_delta_vs_normal_addon_max": round(
                agg["maxdd_delta_vs_normal_addon_max"],
                6,
            ),
            "windows_improved_ev": agg["windows_improved_ev"],
            "windows_regressed_ev": agg["windows_regressed_ev"],
            "newly_executed_count": agg["newly_executed_count"],
        }

    best_name, best_summary = max(
        results["aggregate_by_variant"].items(),
        key=lambda item: (
            item[1]["windows_improved_ev"],
            item[1]["ev_delta_vs_normal_addon_sum"],
            item[1]["pnl_delta_vs_normal_addon_sum"],
        ),
    )
    results["best_variant"] = {"name": best_name, **best_summary}
    results["decision"] = (
        "candidate_needs_real_replay_review"
        if (
            best_summary["windows_improved_ev"] >= 2
            and best_summary["windows_regressed_ev"] == 0
            and best_summary["ev_delta_vs_normal_addon_sum"] > 0
            and best_summary["maxdd_delta_vs_normal_addon_max"] <= 0.005
        )
        else "rejected_unstable_or_immaterial_addon_headroom"
    )
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "Shadow-only result. Production promotion would require a reviewed "
        "BacktestEngine config hook and normal Gate 4 comparison."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "best_variant": results["best_variant"],
        "aggregate_by_variant": results["aggregate_by_variant"],
        "decision": results["decision"],
    }, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
