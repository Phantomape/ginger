"""Shadow audit for strict day-2 follow-through add-on upper bounds.

The research candidate stays fixed:
day-2 unrealized >= +2%, RS vs SPY > 0, add 25% of original shares.

This runner varies one trigger-quality variable: an upper bound on the same
day-2 unrealized return. Ticket scope forbids changing BacktestEngine, so this
is an event-stream audit rather than a full production-path counterfactual.
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


EXPERIMENT_ID = "exp-20260426-020"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull with Apr-2026 stress",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull / high-beta leadership",
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

UPPER_BOUNDS = OrderedDict([
    ("max_4pct", 0.04),
    ("max_5pct", 0.05),
    ("max_6pct", 0.06),
    ("max_7pct", 0.07),
    ("max_8pct", 0.08),
])

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_019_entry_followthrough_upper_bound_results.json",
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


def _matching_trade(trades: list[dict], event: dict) -> dict | None:
    fill_date = event.get("scheduled_fill_date")
    candidates = [
        trade for trade in trades
        if trade.get("ticker") == event.get("ticker")
        and trade.get("strategy") == event.get("strategy")
        and trade.get("addon_count", 0)
        and str(trade.get("exit_date", "")) >= str(fill_date)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda trade: str(trade.get("exit_date", "")))[0]


def _addon_forward_pnl(event: dict, trade: dict | None) -> float | None:
    if not trade or event.get("status") != "executed":
        return None
    shares = event.get("addon_shares")
    entry_fill = event.get("entry_fill")
    exit_price = trade.get("exit_price")
    if not all(isinstance(v, (int, float)) for v in [shares, entry_fill, exit_price]):
        return None
    return round((exit_price - entry_fill) * shares, 2)


def _annotated_events(addon_result: dict) -> list[dict]:
    trades = addon_result.get("trades", [])
    rows = []
    for event in addon_result.get("addon_attribution", {}).get("events", []):
        trade = _matching_trade(trades, event)
        rows.append({
            **event,
            "matched_exit_date": trade.get("exit_date") if trade else None,
            "matched_exit_reason": trade.get("exit_reason") if trade else None,
            "estimated_addon_forward_pnl": _addon_forward_pnl(event, trade),
        })
    return rows


def _summarize(items: list[dict]) -> dict:
    executed = [item for item in items if item.get("status") == "executed"]
    skipped = [item for item in items if str(item.get("status", "")).startswith("skipped_")]
    pnls = [
        item["estimated_addon_forward_pnl"] for item in executed
        if isinstance(item.get("estimated_addon_forward_pnl"), (int, float))
    ]
    return {
        "events": len(items),
        "executed": len(executed),
        "skipped": len(skipped),
        "estimated_forward_pnl_sum": round(sum(pnls), 2),
        "estimated_forward_pnl_avg": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "positive_forward_pnl_rate": (
            round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 4)
            if pnls else None
        ),
        "cap_or_heat_skips": sum(
            1 for item in skipped
            if "position_cap" in str(item.get("status"))
            or "portfolio_heat" in str(item.get("status"))
        ),
    }


def _variant_audit(events: list[dict], upper_bound: float) -> dict:
    retained = [
        event for event in events
        if isinstance(event.get("unrealized_pct"), (int, float))
        and event["unrealized_pct"] <= upper_bound
    ]
    excluded = [
        event for event in events
        if isinstance(event.get("unrealized_pct"), (int, float))
        and event["unrealized_pct"] > upper_bound
    ]
    all_summary = _summarize(events)
    retained_summary = _summarize(retained)
    excluded_summary = _summarize(excluded)
    all_pnl = all_summary["estimated_forward_pnl_sum"]
    retained_pnl = retained_summary["estimated_forward_pnl_sum"]
    return {
        "upper_bound": upper_bound,
        "retained_summary": retained_summary,
        "excluded_summary": excluded_summary,
        "retained_executed_fraction": (
            round(retained_summary["executed"] / all_summary["executed"], 4)
            if all_summary["executed"] else None
        ),
        "retained_estimated_pnl_fraction": (
            round(retained_pnl / all_pnl, 4) if all_pnl else None
        ),
        "estimated_pnl_delta_vs_normal_addon": round(retained_pnl - all_pnl, 2),
        "excluded_events": excluded,
    }


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": EXPERIMENT_ID,
        "artifact_name": "exp_20260426_019_entry_followthrough_upper_bound_results",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "For the strict day-2 follow-through add-on candidate, adding an "
            "upper bound on day-2 unrealized return may remove overextended "
            "chase add-ons and improve materiality."
        ),
        "change_type": "alpha_search_entry_followthrough_addon_trigger_quality",
        "single_causal_variable": "day2 unrealized return upper bound for strict follow-through add-on",
        "fixed_addon_config": ADDON_CONFIG,
        "upper_bounds_tested": UPPER_BOUNDS,
        "parity_warning": (
            "Shadow audit only. The shared BacktestEngine has no upper-bound "
            "config hook, and ticket scope forbids modifying it in this run."
        ),
        "windows": {},
        "aggregate_by_variant": {},
    }

    aggregate = {
        name: {
            "estimated_pnl_delta_vs_normal_addon": 0.0,
            "retained_executed": 0,
            "all_executed": 0,
            "retained_pnl": 0.0,
            "all_pnl": 0.0,
            "windows_with_exclusions": 0,
            "windows_with_negative_pnl_delta": 0,
        }
        for name in UPPER_BOUNDS
    }

    for label, cfg in WINDOWS.items():
        baseline_result = _run_window(universe, cfg, BASE_CONFIG)
        addon_result = _run_window(universe, cfg, ADDON_CONFIG)
        baseline = _metrics(baseline_result)
        addon = _metrics(addon_result)
        delta = _delta(addon, baseline)
        events = _annotated_events(addon_result)
        all_summary = _summarize(events)

        variant_results = {}
        for name, upper_bound in UPPER_BOUNDS.items():
            audit = _variant_audit(events, upper_bound)
            variant_results[name] = audit

            retained = audit["retained_summary"]
            agg = aggregate[name]
            agg["estimated_pnl_delta_vs_normal_addon"] += audit[
                "estimated_pnl_delta_vs_normal_addon"
            ]
            agg["retained_executed"] += retained["executed"]
            agg["all_executed"] += all_summary["executed"]
            agg["retained_pnl"] += retained["estimated_forward_pnl_sum"]
            agg["all_pnl"] += all_summary["estimated_forward_pnl_sum"]
            if audit["excluded_summary"]["events"]:
                agg["windows_with_exclusions"] += 1
            if audit["estimated_pnl_delta_vs_normal_addon"] < 0:
                agg["windows_with_negative_pnl_delta"] += 1

        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
            "baseline": baseline,
            "normal_25pct_addon": addon,
            "normal_25pct_delta_vs_baseline": delta,
            "normal_addon_event_summary": all_summary,
            "upper_bound_audit": variant_results,
            "events": events,
        }

    for name, agg in aggregate.items():
        all_pnl = agg["all_pnl"]
        retained_pnl = agg["retained_pnl"]
        all_executed = agg["all_executed"]
        retained_executed = agg["retained_executed"]
        results["aggregate_by_variant"][name] = {
            "estimated_pnl_delta_vs_normal_addon": round(
                agg["estimated_pnl_delta_vs_normal_addon"],
                2,
            ),
            "retained_executed": retained_executed,
            "all_executed": all_executed,
            "retained_executed_fraction": (
                round(retained_executed / all_executed, 4)
                if all_executed else None
            ),
            "retained_estimated_pnl": round(retained_pnl, 2),
            "all_estimated_pnl": round(all_pnl, 2),
            "retained_estimated_pnl_fraction": (
                round(retained_pnl / all_pnl, 4) if all_pnl else None
            ),
            "windows_with_exclusions": agg["windows_with_exclusions"],
            "windows_with_negative_pnl_delta": agg["windows_with_negative_pnl_delta"],
        }

    best_name, best_summary = max(
        results["aggregate_by_variant"].items(),
        key=lambda item: item[1]["estimated_pnl_delta_vs_normal_addon"],
    )
    results["best_variant"] = {"name": best_name, **best_summary}
    materiality_floor = round(best_summary["all_estimated_pnl"] * 0.05, 2)
    results["materiality_floor_usd"] = materiality_floor
    if best_summary["estimated_pnl_delta_vs_normal_addon"] > materiality_floor:
        decision = "candidate_needs_real_replay_hook"
    else:
        decision = "rejected_de_minimis_upper_bound_filter"
    results["decision"] = decision
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "No production promotion from event-stream audit. A real equity-curve "
        "replay hook would be required before any add-on trigger change."
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
