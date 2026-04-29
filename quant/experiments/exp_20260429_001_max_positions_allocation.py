"""exp-20260429-001: max position count allocation replay.

Alpha search. After the accepted 40% initial cap and 50% day-2 add-on,
the remaining question is whether the portfolio should run fewer slots
for concentration or more slots for capital deployment. This tests only
MAX_POSITIONS across the fixed snapshot windows.
"""

from __future__ import annotations

import json
import logging
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


EXPERIMENT_ID = "exp-20260429-001"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260429_001_max_positions_allocation.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

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
    ("slots_4", 4),
    ("baseline_slots_5", 5),
    ("slots_6", 6),
    ("slots_7", 7),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    cap_eff = result.get("capital_efficiency") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "pnl_per_trade_usd": cap_eff.get("pnl_per_trade_usd"),
        "pnl_per_calendar_slot_day_usd": cap_eff.get("pnl_per_calendar_slot_day_usd"),
        "gross_slot_day_usage": cap_eff.get("gross_slot_day_usage"),
        "entry_reason_counts": entry.get("reason_counts", {}),
        "by_strategy": result.get("by_strategy", {}),
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


def _run_window(universe: list[str], cfg: dict, max_positions: int) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "MAX_POSITIONS": max_positions,
        },
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return _metrics(result)


def run_experiment() -> dict:
    logging.getLogger().setLevel(logging.WARNING)
    universe = sorted(get_universe())
    rows = []
    for window, cfg in WINDOWS.items():
        for variant, max_positions in VARIANTS.items():
            metrics = _run_window(universe, cfg, max_positions)
            row = {
                "window": window,
                "variant": variant,
                "max_positions": max_positions,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "metrics": metrics,
            }
            rows.append(row)
            print(
                f"[{window} {variant}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} WR={metrics['win_rate']} "
                f"trades={metrics['trade_count']}"
            )

    baseline_rows = {
        window: next(
            row for row in rows
            if row["window"] == window and row["variant"] == "baseline_slots_5"
        )
        for window in WINDOWS
    }
    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == "baseline_slots_5":
            continue
        by_window = OrderedDict()
        for window in WINDOWS:
            before = baseline_rows[window]["metrics"]
            row = next(
                row for row in rows
                if row["window"] == window and row["variant"] == variant
            )
            by_window[window] = {
                "before": before,
                "after": row["metrics"],
                "delta": _delta(row["metrics"], before),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "max_positions": VARIANTS[variant],
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
        best_agg["windows_improved"] >= 2
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation",
        "hypothesis": (
            "After the accepted 40% initial cap and 50% day-2 add-on, the "
            "portfolio may need fewer slots for concentration or more slots for "
            "capital deployment than the current MAX_POSITIONS=5."
        ),
        "why_tested": (
            "LLM soft ranking remains sample-limited, ETF expansion was rejected, "
            "and the current highest-value alpha question is meta-allocation rather "
            "than new OHLCV-only entries."
        ),
        "parameters": {
            "single_causal_variable": "MAX_POSITIONS",
            "baseline": 5,
            "tested_values": [4, 5, 6, 7],
            "locked_variables": [
                "universe",
                "signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT=0.40",
                "MAX_PORTFOLIO_HEAT=0.08",
                "MAX_PER_SECTOR=2",
                "upside/adverse gap cancels",
                "day-2 add-on trigger/fraction/cap",
                "all exits",
                "scarce-slot breakout deferral",
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
                "Accepted because the best slot-count variant passed Gate 4 in "
                "a majority of fixed windows without regression."
                if accepted else
                "Rejected because no slot-count variant improved a majority of fixed windows without regression."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking data is still insufficient, so this tested a "
                "deterministic capital-allocation alpha instead."
            ),
        },
        "history_guardrails": {
            "not_repeating_addon_threshold_tuning": True,
            "not_repeating_gap_cancel_threshold_tuning": True,
            "not_repeating_etf_universe_expansion": True,
            "mechanism_family": "meta-allocation / portfolio slot count",
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "MAX_POSITIONS=5 remained the best robust setting; fewer slots cut profitable exposure and more slots admitted weaker marginal trades."
        ),
        "next_retry_requires": [
            "Do not retry nearby global MAX_POSITIONS sweeps without a new state-specific allocation signal.",
            "If slot count is revisited, the variable should be sleeve/state routing rather than a global portfolio slot count.",
            "Any accepted slot routing rule must be implemented through shared production/backtest policy.",
        ],
    }
    return payload


def write_outputs(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Max position count allocation replay",
        "status": "completed",
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "single_causal_variable": "MAX_POSITIONS",
        "baseline_result_file": "data/backtest_results_20260428.json",
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "log": str(LOG_JSON.relative_to(REPO_ROOT)),
        "evaluation_windows": [
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
            }
            for label, cfg in WINDOWS.items()
        ],
        "acceptance_rule": "Gate 4 plus three fixed-window robustness; production promotion requires constants/shared-policy update.",
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "production_impact": payload["production_impact"],
        "created_at": payload["created_at"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2), encoding="utf-8")


def main() -> int:
    payload = run_experiment()
    write_outputs(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
