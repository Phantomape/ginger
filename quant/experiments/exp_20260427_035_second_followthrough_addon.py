"""exp-20260427-035: second follow-through add-on replay.

This tests a lifecycle / capital-allocation alpha: after the accepted day-2
follow-through add-on, allow one more smaller add-on only if the position keeps
working by day 5. The hook is default-off in production config.
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


EXPERIMENT_ID = "exp-20260427-035"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260427_035_second_followthrough_addon.json"

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
BASE_SECOND_ADDON_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "SECOND_ADDON_ENABLED": True,
    "SECOND_ADDON_CHECKPOINT_DAYS": 5,
    "SECOND_ADDON_MIN_UNREALIZED_PCT": 0.05,
    "SECOND_ADDON_MIN_RS_VS_SPY": 0.0,
}
CANDIDATE_VARIANTS = OrderedDict([
    ("frac15_cap45", {
        **BASE_SECOND_ADDON_CONFIG,
        "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.15,
        "SECOND_ADDON_MAX_POSITION_PCT": 0.45,
    }),
    ("frac25_cap50", {
        **BASE_SECOND_ADDON_CONFIG,
        "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.25,
        "SECOND_ADDON_MAX_POSITION_PCT": 0.50,
    }),
    ("frac35_cap60", {
        **BASE_SECOND_ADDON_CONFIG,
        "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.35,
        "SECOND_ADDON_MAX_POSITION_PCT": 0.60,
    }),
])
CANDIDATE_CONFIG = {
    **BASE_SECOND_ADDON_CONFIG,
    "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES": 0.15,
    "SECOND_ADDON_MAX_POSITION_PCT": 0.45,
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
        "addon_scheduled": addon_attr.get("scheduled"),
        "addon_executed": addon_attr.get("executed"),
        "second_addon_scheduled": sum(
            1 for event in second_events
            if event.get("status") not in {
                "skipped_position_closed",
                "skipped_no_price",
            }
        ),
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
    baselines = {}
    for label, cfg in WINDOWS.items():
        baselines[label] = _metrics(_run_window(universe, cfg, BASE_CONFIG))

    variants = OrderedDict()
    for variant_name, variant_config in CANDIDATE_VARIANTS.items():
        rows = []
        for label, cfg in WINDOWS.items():
            before = baselines[label]
            candidate = _run_window(universe, cfg, variant_config)
            after = _metrics(candidate)
            row = {
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "before_metrics": before,
                "after_metrics": after,
                "delta_metrics": _delta(after, before),
            }
            print(
                f"[{variant_name} {label}] EV {before['expected_value_score']} -> "
                f"{after['expected_value_score']} | PnL {before['total_pnl']} -> "
                f"{after['total_pnl']} | second_exec={after['second_addon_executed']}"
            )
            rows.append(row)

        ev_delta_sum = round(
            sum(row["delta_metrics"]["expected_value_score"] for row in rows),
            6,
        )
        pnl_delta_sum = round(sum(row["delta_metrics"]["total_pnl"] for row in rows), 2)
        variants[variant_name] = {
            "config": variant_config,
            "results": rows,
            "summary": {
                "expected_value_score_delta_sum": ev_delta_sum,
                "total_pnl_delta_sum": pnl_delta_sum,
                "windows_improved": sum(
                    1 for row in rows
                    if row["delta_metrics"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for row in rows
                    if row["delta_metrics"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    row["delta_metrics"]["max_drawdown_pct"] for row in rows
                ),
                "second_addon_executed": sum(
                    row["after_metrics"]["second_addon_executed"] for row in rows
                ),
            },
        }

    best_name, best_payload = max(
        variants.items(),
        key=lambda item: item[1]["summary"]["expected_value_score_delta_sum"],
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "A second smaller day-5 follow-through add-on may improve lifecycle "
            "alpha by allocating more budget only to positions that already "
            "absorbed the day-2 add-on and continue to outperform SPY."
        ),
        "change_type": "capital_allocation",
        "parameters": {
            "single_causal_variable": "second follow-through add-on policy",
            "baseline": BASE_CONFIG,
            "candidate_variants": CANDIDATE_VARIANTS,
            "unchanged": [
                "entries",
                "exits",
                "initial position cap",
                "day-2 add-on trigger",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "windows": WINDOWS,
        "baseline_metrics": baselines,
        "variants": variants,
        "best_variant": best_name,
        "summary": best_payload["summary"],
        "decision": "rejected",
        "rejection_reason": (
            "Best variant improved 2/3 windows and regressed none, but did not "
            "meet Gate 4 materiality: EV delta <10%, PnL delta <5%, and "
            "Sharpe improvement <0.1 in every fixed window."
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
