"""Real replay for strict day-2 follow-through add-on cap headroom.

This promotes the prior shadow-only cap-headroom audit into a BacktestEngine
configuration replay. Production defaults stay unchanged: add-ons remain
disabled unless the experiment config enables them.
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
from constants import MAX_POSITION_PCT as PRODUCTION_MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260427-012"

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
    "ADDON_MAX_POSITION_PCT": None,
    "ADDON_REQUIRE_CHECKPOINT_CAP_ROOM": False,
    "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": False,
}
CAP_HEADROOM_ADDON_CONFIG = {
    **NORMAL_ADDON_CONFIG,
    "ADDON_MAX_POSITION_PCT": 0.35,
}

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260427_012_entry_followthrough_addon_cap_real_replay.json",
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
            "max_position_pct": addon.get("max_position_pct"),
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


def _event_status_counts(result: dict) -> dict:
    counts: dict[str, int] = {}
    for event in result.get("addon_attribution", {}).get("events", []):
        status = event.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _executed_addon_keys(result: dict) -> set[tuple]:
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


def _newly_executed_events(normal_result: dict, headroom_result: dict) -> list[dict]:
    normal_keys = _executed_addon_keys(normal_result)
    trades = headroom_result.get("trades", [])
    rows = []
    for event in headroom_result.get("addon_attribution", {}).get("events", []):
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
            "Strict day-2 follow-through add-ons may be materially under-sized "
            "because the production 25% single-position cap blocks confirmed "
            "winner add-ons; an add-on-only 35% cap may unlock capital allocation "
            "alpha without changing entry, exit, ranking, LLM, or production defaults."
        ),
        "change_type": "capital_allocation",
        "single_causal_variable": "ADDON_MAX_POSITION_PCT for strict day2 follow-through add-ons",
        "parameters": {
            "production_max_position_pct": PRODUCTION_MAX_POSITION_PCT,
            "base_config": BASE_CONFIG,
            "normal_addon_config": NORMAL_ADDON_CONFIG,
            "cap_headroom_addon_config": CAP_HEADROOM_ADDON_CONFIG,
        },
        "windows": {},
        "aggregate": {
            "normal_vs_base_ev_delta_sum": 0.0,
            "normal_vs_base_pnl_delta_sum": 0.0,
            "headroom_vs_base_ev_delta_sum": 0.0,
            "headroom_vs_base_pnl_delta_sum": 0.0,
            "headroom_vs_normal_ev_delta_sum": 0.0,
            "headroom_vs_normal_pnl_delta_sum": 0.0,
            "headroom_vs_normal_maxdd_delta_max": 0.0,
            "windows_improved_vs_base": 0,
            "windows_improved_vs_normal": 0,
            "windows_regressed_vs_normal": 0,
            "newly_executed_count": 0,
        },
    }

    for label, cfg in WINDOWS.items():
        baseline = _run_window(universe, cfg, BASE_CONFIG)
        normal = _run_window(universe, cfg, NORMAL_ADDON_CONFIG)
        headroom = _run_window(universe, cfg, CAP_HEADROOM_ADDON_CONFIG)

        baseline_metrics = _metrics(baseline)
        normal_metrics = _metrics(normal)
        headroom_metrics = _metrics(headroom)
        normal_vs_base = _delta(normal_metrics, baseline_metrics)
        headroom_vs_base = _delta(headroom_metrics, baseline_metrics)
        headroom_vs_normal = _delta(headroom_metrics, normal_metrics)
        new_events = _newly_executed_events(normal, headroom)

        results["windows"][label] = {
            "date_range": {"start": cfg["start"], "end": cfg["end"]},
            "snapshot": cfg["snapshot"],
            "market_regime_summary": cfg["regime"],
            "baseline": baseline_metrics,
            "normal_25pct_addon": normal_metrics,
            "headroom_35pct_addon_cap": headroom_metrics,
            "normal_vs_base": normal_vs_base,
            "headroom_vs_base": headroom_vs_base,
            "headroom_vs_normal": headroom_vs_normal,
            "normal_status_counts": _event_status_counts(normal),
            "headroom_status_counts": _event_status_counts(headroom),
            "newly_executed_events": new_events,
        }

        agg = results["aggregate"]
        normal_ev = normal_vs_base.get("expected_value_score") or 0.0
        normal_pnl = normal_vs_base.get("total_pnl") or 0.0
        headroom_base_ev = headroom_vs_base.get("expected_value_score") or 0.0
        headroom_base_pnl = headroom_vs_base.get("total_pnl") or 0.0
        headroom_normal_ev = headroom_vs_normal.get("expected_value_score") or 0.0
        headroom_normal_pnl = headroom_vs_normal.get("total_pnl") or 0.0
        maxdd_delta = headroom_vs_normal.get("max_drawdown_pct") or 0.0

        agg["normal_vs_base_ev_delta_sum"] += normal_ev
        agg["normal_vs_base_pnl_delta_sum"] += normal_pnl
        agg["headroom_vs_base_ev_delta_sum"] += headroom_base_ev
        agg["headroom_vs_base_pnl_delta_sum"] += headroom_base_pnl
        agg["headroom_vs_normal_ev_delta_sum"] += headroom_normal_ev
        agg["headroom_vs_normal_pnl_delta_sum"] += headroom_normal_pnl
        agg["headroom_vs_normal_maxdd_delta_max"] = max(
            agg["headroom_vs_normal_maxdd_delta_max"],
            maxdd_delta,
        )
        agg["windows_improved_vs_base"] += 1 if headroom_base_ev > 0 else 0
        agg["windows_improved_vs_normal"] += 1 if headroom_normal_ev > 0 else 0
        agg["windows_regressed_vs_normal"] += 1 if headroom_normal_ev < 0 else 0
        agg["newly_executed_count"] += len(new_events)

    for key, value in list(results["aggregate"].items()):
        if isinstance(value, float):
            results["aggregate"][key] = round(value, 6)

    agg = results["aggregate"]
    results["decision"] = (
        "accepted_default_off_research_harness"
        if (
            agg["windows_improved_vs_base"] == len(WINDOWS)
            and agg["windows_improved_vs_normal"] == len(WINDOWS)
            and agg["windows_regressed_vs_normal"] == 0
            and agg["headroom_vs_normal_ev_delta_sum"] > 0
            and agg["headroom_vs_normal_pnl_delta_sum"] > 0
            and agg["headroom_vs_normal_maxdd_delta_max"] <= 0.005
        )
        else "rejected"
    )
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "Keep add-ons default-off. This validates a configurable research "
        "harness and positive cap-headroom candidate, not live promotion."
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
        print(
            f"{label}: base EV {rec['baseline']['expected_value_score']} | "
            f"normal EV {rec['normal_25pct_addon']['expected_value_score']} | "
            f"35% cap EV {rec['headroom_35pct_addon_cap']['expected_value_score']} | "
            f"new add-ons {len(rec['newly_executed_events'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
