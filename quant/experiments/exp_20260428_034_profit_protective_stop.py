"""exp-20260428-034 lifecycle profit-protective stop sweep.

Alpha search. Tests one exit/lifecycle variable: after a position has reached
at least +3% MFE, should the simulated stop be raised to breakeven or a small
profit lock? Entries, sizing, candidate ordering, gap cancels, add-ons, targets,
LLM/news replay, and earnings remain locked.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-034"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_034_profit_protective_stop.json"

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
    ("baseline_no_profit_protect", None),
    ("protect_breakeven_after_3pct_mfe", 0.00),
    ("protect_1pct_after_3pct_mfe", 0.01),
    ("protect_2pct_after_3pct_mfe", 0.02),
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
        "tail_loss_share": result.get("tail_loss_share"),
        "addon_executed": addon.get("executed"),
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


def _run_window(universe: list[str], cfg: dict, protect_stop_pct: float | None) -> dict:
    config = {"REGIME_AWARE_EXIT": True}
    if protect_stop_pct is not None:
        config.update({
            "PROFIT_PROTECT_ENABLED": True,
            "PROFIT_PROTECT_TRIGGER_PCT": 0.03,
            "PROFIT_PROTECT_STOP_PCT": protect_stop_pct,
        })
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    trades = result.get("trades", [])
    return {
        "metrics": _metrics(result),
        "exit_reason_counts": dict(Counter(t.get("exit_reason") for t in trades)),
        "trades": trades,
    }


def _changed_trades(candidate: list[dict], baseline: list[dict]) -> list[dict]:
    base = {
        (t.get("ticker"), t.get("entry_date"), t.get("strategy")): t
        for t in baseline
    }
    rows = []
    for trade in candidate:
        key = (trade.get("ticker"), trade.get("entry_date"), trade.get("strategy"))
        old = base.get(key)
        if not old:
            continue
        if (
            old.get("exit_date") != trade.get("exit_date")
            or old.get("exit_reason") != trade.get("exit_reason")
            or old.get("pnl") != trade.get("pnl")
        ):
            rows.append({
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": trade.get("entry_date"),
                "baseline_exit_date": old.get("exit_date"),
                "candidate_exit_date": trade.get("exit_date"),
                "baseline_exit_reason": old.get("exit_reason"),
                "candidate_exit_reason": trade.get("exit_reason"),
                "baseline_pnl": old.get("pnl"),
                "candidate_pnl": trade.get("pnl"),
                "pnl_delta": (
                    round(trade.get("pnl", 0) - old.get("pnl", 0), 2)
                    if isinstance(trade.get("pnl"), (int, float))
                    and isinstance(old.get("pnl"), (int, float))
                    else None
                ),
            })
    return rows


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, stop_pct in VARIANTS.items():
            result = _run_window(universe, cfg, stop_pct)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "profit_protect_trigger_pct": None if stop_pct is None else 0.03,
                "profit_protect_stop_pct": stop_pct,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']}"
            )

    baseline_rows = {
        label: next(
            r for r in rows
            if r["window"] == label and r["variant"] == "baseline_no_profit_protect"
        )
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "exit_reason_counts": candidate["exit_reason_counts"],
                "changed_trades": _changed_trades(candidate["trades"], baseline["trades"]),
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
                "changed_trade_count": sum(
                    len(v["changed_trades"]) for v in by_window.values()
                ),
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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "exit_lifecycle_profit_protection",
        "hypothesis": (
            "A small protective stop after +3% MFE may prevent profit-decay "
            "losers without adding a new entry filter or weakening winner capture."
        ),
        "parameters": {
            "single_causal_variable": "post-entry profit-protective stop level",
            "baseline": "no profit-protective stop",
            "tested": {
                "trigger_mfe_pct": 0.03,
                "stop_pct_after_trigger": [0.00, 0.01, 0.02],
            },
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "position caps and heat",
                "candidate ordering",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "fixed/regime-aware target levels",
                "scarce-slot routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
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
                "Accepted because the best protective stop improved all fixed windows and passed Gate 4."
                if accepted else
                "Rejected because no protective-stop variant passed the fixed-window Gate 4 checks."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited; this tests deterministic "
                "lifecycle alpha instead."
            ),
        },
        "history_guardrails": {
            "not_weak_hold_early_exit": "requires prior +3% MFE, not day-count weakness",
            "not_addon_threshold_tuning": True,
            "not_gap_cancel_tuning": True,
            "not_candidate_ordering": True,
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "Profit protection either truncated winners or failed to improve most windows materially."
        ),
        "next_retry_requires": [
            "Do not retry nearby 0-2% protection stops after +3% MFE without new evidence.",
            "A valid retry needs an orthogonal adverse context such as failed reclaim or fresh negative event.",
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
