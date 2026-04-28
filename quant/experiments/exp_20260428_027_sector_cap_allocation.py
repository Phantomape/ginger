"""exp-20260428-027 same-day sector cap allocation replay.

Experiment-only alpha search. The accepted stack has become more concentrated
after the 40% initial cap and 50% follow-through add-on. This tests whether the
same-day per-sector signal cap is now too tight or too loose for capturing
sector leadership clusters.

Only one causal variable changes in replay: MAX_PER_SECTOR. Entries, exits,
sizing constants, add-ons, gap cancels, scarce-slot routing, LLM/news replay,
and earnings remain locked.
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

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import MAX_PER_SECTOR  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-027"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_027_sector_cap_allocation.json"

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
    ("sector_cap_1", 1),
    ("baseline_sector_cap_2", 2),
    ("sector_cap_3", 3),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    execution = result.get("entry_execution_attribution") or {}
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
        "entry_reason_counts": execution.get("reason_counts", {}),
    }


def _sector_trade_summary(trades: list[dict]) -> dict:
    by_sector = {}
    for trade in trades:
        sector = trade.get("sector", "Unknown")
        rec = by_sector.setdefault(sector, {"trades": 0, "pnl": 0.0, "wins": 0})
        rec["trades"] += 1
        pnl = float(trade.get("pnl") or 0.0)
        rec["pnl"] += pnl
        if pnl > 0:
            rec["wins"] += 1
    return {
        sector: {
            "trades": rec["trades"],
            "pnl": round(rec["pnl"], 2),
            "win_rate": round(rec["wins"] / rec["trades"], 4) if rec["trades"] else None,
        }
        for sector, rec in sorted(by_sector.items())
    }


def _run_window(universe: list[str], cfg: dict, max_per_sector: int) -> dict:
    original = bt.MAX_PER_SECTOR
    bt.MAX_PER_SECTOR = max_per_sector
    try:
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        )
        result = engine.run()
    finally:
        bt.MAX_PER_SECTOR = original

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "sector_trade_summary": _sector_trade_summary(result.get("trades", [])),
        "trades": result.get("trades", []),
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
        for variant, max_per_sector in VARIANTS.items():
            result = _run_window(universe, cfg, max_per_sector)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "max_per_sector": max_per_sector,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} trades={m['trade_count']}"
            )

    baseline_rows = {
        label: next(
            r for r in rows
            if r["window"] == label and r["variant"] == "baseline_sector_cap_2"
        )
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in ("sector_cap_1", "sector_cap_3"):
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "before_sector_trade_summary": baseline["sector_trade_summary"],
                "after_sector_trade_summary": candidate["sector_trade_summary"],
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
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
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["windows_improved"] == 3
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "The current same-day per-sector cap may be mis-sized after recent "
            "capital-allocation improvements. Relaxing it could capture sector "
            "leadership clusters; tightening it could reduce correlated false "
            "breakouts."
        ),
        "change_type": "alpha_search_capital_allocation_sector_cap",
        "parameters": {
            "single_causal_variable": "MAX_PER_SECTOR",
            "baseline_max_per_sector": MAX_PER_SECTOR,
            "tested_max_per_sector": [1, 3],
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "initial position cap",
                "all exits",
                "upside/adverse gap cancels",
                "day-2 add-on settings",
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
        "before_metrics": {
            label: baseline_rows[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
        },
        "delta_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted because the best sector cap improved all fixed windows and passed Gate 4."
                if accepted else
                "Rejected because no sector-cap variant passed the fixed-window Gate 4 checks."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "portfolio allocation alpha was tested instead."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "Changing same-day sector breadth did not improve the accepted stack robustly enough."
        ),
        "next_retry_requires": [
            "Do not retry nearby global sector cap values without new sector-leadership evidence.",
            "A valid retry needs a state- or sleeve-specific sector allocation signal, not a global cap.",
            "Do not confuse this with residual sector pocket sizing rules already accepted or rejected.",
        ],
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
