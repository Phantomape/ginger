"""exp-20260428-031: second add-on after cap promotion.

This re-validates the previously promising day-5 second follow-through add-on
after the production stack changed to a 50% day-2 add-on and a 40% initial cap.
Only the second-add-on policy changes in this replay.
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


EXPERIMENT_ID = "exp-20260428-031"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_031_second_addon_after_cap_promotion.json"

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

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
SECOND_ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "SECOND_ADDON_ENABLED": True,
    "SECOND_ADDON_CHECKPOINT_DAYS": 5,
    "SECOND_ADDON_MIN_UNREALIZED_PCT": 0.05,
    "SECOND_ADDON_MIN_RS_VS_SPY": 0.0,
    "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.35,
    "SECOND_ADDON_MAX_POSITION_PCT": 0.60,
}


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    addon_attr = result.get("addon_attribution") or {}
    second_events = [
        event for event in addon_attr.get("events", [])
        if event.get("addon_number") == 2
    ]
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "addon_scheduled": addon_attr.get("scheduled"),
        "addon_executed": addon_attr.get("executed"),
        "second_addon_executed": sum(
            1 for event in second_events if event.get("status") == "executed"
        ),
    }


def _run_window(universe: list[str], cfg: dict, config: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    return engine.run()


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
        before = _metrics(_run_window(universe, cfg, BASE_CONFIG))
        after = _metrics(_run_window(universe, cfg, SECOND_ADDON_CONFIG))
        delta = _delta(after, before)
        rows.append({
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": delta,
        })
        print(
            f"[{label}] EV {before['expected_value_score']} -> {after['expected_value_score']} | "
            f"PnL {before['total_pnl']} -> {after['total_pnl']} | "
            f"second_addons={after['second_addon_executed']}"
        )

    ev_delta_sum = round(sum(row["delta_metrics"]["expected_value_score"] for row in rows), 6)
    pnl_delta_sum = round(sum(row["delta_metrics"]["total_pnl"] for row in rows), 2)
    baseline_pnl_sum = round(sum(row["before_metrics"]["total_pnl"] for row in rows), 2)
    max_drawdown_delta_max = max(row["delta_metrics"]["max_drawdown_pct"] for row in rows)
    summary = {
        "expected_value_score_delta_sum": ev_delta_sum,
        "total_pnl_delta_sum": pnl_delta_sum,
        "baseline_total_pnl_sum": baseline_pnl_sum,
        "total_pnl_delta_pct": round(pnl_delta_sum / baseline_pnl_sum, 6),
        "windows_improved": sum(1 for row in rows if row["delta_metrics"]["expected_value_score"] > 0),
        "windows_regressed": sum(1 for row in rows if row["delta_metrics"]["expected_value_score"] < 0),
        "max_drawdown_delta_max": max_drawdown_delta_max,
        "second_addon_executed": sum(row["after_metrics"]["second_addon_executed"] for row in rows),
    }

    accepted = (
        summary["windows_regressed"] == 0
        and (
            summary["total_pnl_delta_pct"] > 0.05
            or any(row["delta_metrics"]["sharpe_daily"] > 0.1 for row in rows)
            or summary["expected_value_score_delta_sum"] > 0.1
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "After the accepted 50% day-2 add-on and 40% initial cap, a day-5 "
            "second follow-through add-on might now clear materiality by adding "
            "risk only to positions that keep working."
        ),
        "change_type": "alpha_search_lifecycle_capital_allocation",
        "parameters": {
            "single_causal_variable": "enable second follow-through add-on policy",
            "baseline": {"SECOND_ADDON_ENABLED": False},
            "candidate": SECOND_ADDON_CONFIG,
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "rows": rows,
        "summary": summary,
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited, so this deterministic "
                "lifecycle alpha was tested instead."
            ),
        },
        "rejection_reason": None if accepted else (
            "The second add-on did not clear fixed-window Gate 4 after the cap "
            "promotion; do not promote without forward/paper evidence or a new "
            "orthogonal confirmation signal."
        ),
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
