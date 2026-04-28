"""exp-20260428-006: follow-through add-on position-cap replay.

Hypothesis:
    After promoting the day-2 follow-through add-on fraction to 50%, the
    add-on-specific position cap may still clip confirmed winners. Raising only
    ADDON_MAX_POSITION_PCT can improve EV without changing entries, exits,
    add-on trigger thresholds, LLM/news replay, scarce-slot routing, or the
    initial-entry single-position cap.

This runner is experiment-only. Production defaults are changed separately only
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


EXPERIMENT_ID = "exp-20260428-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_006_addon_position_cap.json"

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
    ("baseline_addon_cap_35", 0.35),
    ("addon_cap_40", 0.40),
    ("addon_cap_45", 0.45),
    ("addon_cap_50", 0.50),
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
        "addon_skipped": addon.get("skipped"),
    }


def _addon_clip_summary(events: list[dict]) -> dict:
    executed = [e for e in events if e.get("status") == "executed"]
    requested = sum(int(e.get("requested_shares") or 0) for e in executed)
    filled = sum(int(e.get("addon_shares") or 0) for e in executed)
    clipped_events = [
        e for e in executed
        if int(e.get("addon_shares") or 0) < int(e.get("requested_shares") or 0)
    ]
    return {
        "executed_events": len(executed),
        "requested_shares": requested,
        "filled_addon_shares": filled,
        "clipped_event_count": len(clipped_events),
        "skipped_position_cap_count": sum(
            1 for e in events if e.get("status") == "skipped_position_cap"
        ),
        "skipped_portfolio_heat_cap_count": sum(
            1 for e in events if e.get("status") == "skipped_portfolio_heat_cap"
        ),
    }


def _run_window(universe: list[str], cfg: dict, addon_cap: float) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "ADDON_MAX_POSITION_PCT": addon_cap,
        },
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    events = (result.get("addon_attribution") or {}).get("events", [])
    return {
        "metrics": _metrics(result),
        "addon_clip_summary": _addon_clip_summary(events),
        "addon_events": events,
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
        for variant, addon_cap in VARIANTS.items():
            result = _run_window(universe, cfg, addon_cap)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "addon_max_position_pct": addon_cap,
                "metrics": result["metrics"],
                "addon_clip_summary": result["addon_clip_summary"],
                "addon_events": result["addon_events"],
            })
            m = result["metrics"]
            c = result["addon_clip_summary"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} add={m['addon_executed']} "
                f"filled={c['filled_addon_shares']}/{c['requested_shares']}"
            )

    summary = OrderedDict()
    for variant in ("addon_cap_40", "addon_cap_45", "addon_cap_50"):
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline_addon_cap_35"
            )
            candidate = next(
                r for r in rows
                if r["window"] == label and r["variant"] == variant
            )
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "before_addon_clip_summary": baseline["addon_clip_summary"],
                "after_addon_clip_summary": candidate["addon_clip_summary"],
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

    best_variant = max(
        summary,
        key=lambda name: (
            summary[name]["aggregate"]["windows_improved"],
            -summary[name]["aggregate"]["windows_regressed"],
            summary[name]["aggregate"]["expected_value_score_delta_sum"],
            summary[name]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = summary[best_variant]["aggregate"]
    accepted = (
        best_agg["windows_improved"] == 3
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["expected_value_score_delta_sum"] > 0.10
        )
        and best_agg["max_drawdown_delta_max"] < 0.01
    )
    promoted_cap = VARIANTS[best_variant] if accepted else None
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": (
            f"promote_addon_max_position_pct_{promoted_cap:.2f}"
            if accepted else
            "do_not_promote"
        ),
        "hypothesis": (
            "After promoting the day-2 follow-through add-on fraction to 50%, "
            "the add-on-specific position cap may still clip confirmed winners. "
            "Raising only ADDON_MAX_POSITION_PCT should improve EV without "
            "changing entries, exits, trigger thresholds, LLM/news replay, "
            "scarce-slot routing, or the initial-entry single-position cap."
        ),
        "change_type": "alpha_search_capital_allocation",
        "parameters": {
            "single_causal_variable": "ADDON_MAX_POSITION_PCT",
            "baseline_addon_max_position_pct": 0.35,
            "tested_addon_max_position_pct": [0.40, 0.45, 0.50],
            "promoted_addon_max_position_pct": promoted_cap,
            "locked_variables": [
                "entries",
                "exits",
                "ADDON_CHECKPOINT_DAYS",
                "ADDON_MIN_UNREALIZED_PCT",
                "ADDON_MIN_RS_VS_SPY",
                "ADDON_FRACTION_OF_ORIGINAL_SHARES",
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
        "best_variant": best_variant,
        "gate4_basis": (
            "Accepted because the best cap improved EV in all three fixed "
            "windows, passed the EV/PnL materiality gate, and kept maximum "
            "drawdown increase below 1 percentage point."
            if accepted else
            "Rejected because no tested add-on position cap passed the fixed-window Gate 4 checks."
        ),
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "follow-through capital-allocation alpha was tested instead."
            ),
        },
        "next_retry_requires": [
            "Do not continue nearby add-on cap sweeps without forward/paper concentration evidence.",
            "Do not change the day-2 follow-through trigger thresholds from this result.",
            "Any future add-on allocation work needs a new independent evidence source or concentration monitor.",
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
