"""exp-20260428-026 reduced-risk initial cap replay.

Experiment-only alpha search. The accepted 40% initial position cap increases
capital allocated to tight-stop winners, but positions already down-weighted by
existing quality/risk multipliers may not deserve the same concentration cap.

This runner changes one causal variable in replay only: the max initial
position cap used for non-zero reduced-risk signals. Entries, exits, risk
multipliers, add-ons, gap cancels, scarce-slot routing, LLM/news replay, and
earnings remain locked.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from constants import MAX_POSITION_PCT, ROUND_TRIP_COST_PCT, EXEC_LAG_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260428-026"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_026_reduced_risk_initial_cap.json"

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
    ("baseline_reduced_risk_cap_40", None),
    ("reduced_risk_cap_20", 0.20),
    ("reduced_risk_cap_25", 0.25),
    ("reduced_risk_cap_30", 0.30),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
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
    }


def _make_dynamic_cap_sizer(reduced_risk_cap: float):
    original = portfolio_engine.compute_position_size
    stats = {
        "reduced_risk_calls": 0,
        "reduced_risk_cap_bind_count": 0,
        "reduced_risk_requested_shares": 0,
        "reduced_risk_capped_shares": 0,
    }

    def patched(portfolio_value, entry_price, stop_price, risk_pct=portfolio_engine.RISK_PER_TRADE_PCT):
        result = original(portfolio_value, entry_price, stop_price, risk_pct=risk_pct)
        if not result or risk_pct is None or risk_pct <= 0:
            return result

        base_risk = portfolio_engine.RISK_PER_TRADE_PCT
        is_reduced_nonzero = 0 < float(risk_pct) < float(base_risk)
        if not is_reduced_nonzero:
            return result

        stats["reduced_risk_calls"] += 1
        current_shares = int(result.get("shares_to_buy") or 0)
        stats["reduced_risk_requested_shares"] += current_shares
        max_shares = max(1, math.floor(portfolio_value * reduced_risk_cap / entry_price))
        if current_shares > max_shares:
            stats["reduced_risk_cap_bind_count"] += 1
            result = dict(result)
            result["shares_to_buy"] = max_shares
            result["position_value_usd"] = round(max_shares * entry_price, 2)
            result["position_pct_of_portfolio"] = round(
                (max_shares * entry_price) / portfolio_value,
                4,
            )
            result["reduced_risk_initial_cap_applied"] = reduced_risk_cap
        stats["reduced_risk_capped_shares"] += int(result.get("shares_to_buy") or 0)
        return result

    return patched, stats


def _run_window(universe: list[str], cfg: dict, reduced_risk_cap: float | None) -> dict:
    cap_stats = None
    original = portfolio_engine.compute_position_size
    if reduced_risk_cap is not None:
        patched, cap_stats = _make_dynamic_cap_sizer(reduced_risk_cap)
        portfolio_engine.compute_position_size = patched
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
        portfolio_engine.compute_position_size = original

    if "error" in result:
        raise RuntimeError(result["error"])
    trades = result.get("trades") or []
    reduced_trades = [
        t for t in trades
        if 0 < float(t.get("actual_risk_pct") or 0) < float(t.get("base_risk_pct") or 0)
    ]
    return {
        "metrics": _metrics(result),
        "cap_stats": cap_stats or {},
        "reduced_risk_trade_count": len(reduced_trades),
        "reduced_risk_trade_pnl": round(
            sum(float(t.get("pnl") or 0.0) for t in reduced_trades),
            2,
        ),
        "reduced_risk_trades": [
            {
                "ticker": t.get("ticker"),
                "strategy": t.get("strategy"),
                "sector": t.get("sector"),
                "entry_date": t.get("entry_date"),
                "exit_date": t.get("exit_date"),
                "pnl": round(float(t.get("pnl") or 0.0), 2),
                "actual_risk_pct": t.get("actual_risk_pct"),
                "base_risk_pct": t.get("base_risk_pct"),
                "position_pct": (
                    round((float(t.get("entry_price") or 0) * int(t.get("shares") or 0)) / 100000.0, 4)
                    if t.get("entry_price") and t.get("shares") else None
                ),
            }
            for t in reduced_trades
        ],
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
        for variant, reduced_risk_cap in VARIANTS.items():
            result = _run_window(universe, cfg, reduced_risk_cap)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "reduced_risk_initial_cap_pct": (
                    MAX_POSITION_PCT if reduced_risk_cap is None else reduced_risk_cap
                ),
                **result,
            })
            metrics = result["metrics"]
            print(
                f"[{label} {variant}] EV={metrics['expected_value_score']} "
                f"PnL={metrics['total_pnl']} SharpeD={metrics['sharpe_daily']} "
                f"DD={metrics['max_drawdown_pct']} reduced_pnl={result['reduced_risk_trade_pnl']} "
                f"binds={(result['cap_stats'] or {}).get('reduced_risk_cap_bind_count')}"
            )

    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline_reduced_risk_cap_40"
            )
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "cap_stats": candidate["cap_stats"],
                "reduced_risk_trade_pnl": candidate["reduced_risk_trade_pnl"],
                "reduced_risk_trade_count": candidate["reduced_risk_trade_count"],
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
                "cap_bind_count_sum": sum(
                    int((v["cap_stats"] or {}).get("reduced_risk_cap_bind_count") or 0)
                    for v in by_window.values()
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
        )
        and best_agg["cap_bind_count_sum"] > 0
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "The accepted 40% initial cap should concentrate capital in full-risk "
            "or otherwise high-conviction entries, while positions already "
            "down-weighted by existing sizing multipliers may deserve a lower "
            "initial concentration cap."
        ),
        "change_type": "alpha_search_capital_allocation_quality_cap",
        "parameters": {
            "single_causal_variable": "reduced-risk initial position cap",
            "baseline_global_initial_cap_pct": MAX_POSITION_PCT,
            "tested_reduced_risk_initial_cap_pct": [0.20, 0.25, 0.30],
            "reduced_risk_definition": "0 < actual signal risk_pct < base risk_pct",
            "locked_variables": [
                "signal generation",
                "risk multiplier definitions",
                "all exits",
                "upside/adverse gap cancels",
                "day-2 add-on trigger/fraction/cap",
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
            label: next(
                r["metrics"] for r in rows
                if r["window"] == label and r["variant"] == "baseline_reduced_risk_cap_40"
            )
            for label in WINDOWS
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
                "Accepted because the best reduced-risk cap improved EV in all three fixed windows "
                "and passed materiality."
                if accepted else
                "Rejected because no reduced-risk cap variant passed the fixed-window Gate 4 checks."
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
                "capital-allocation alpha was tested instead."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "Reduced-risk cap tightening did not improve the accepted stack robustly enough "
            "to justify a production allocation rule."
        ),
        "next_retry_requires": [
            "Do not retry nearby reduced-risk cap values without new concentration evidence.",
            "A valid retry needs a more specific quality bucket than all non-zero reduced-risk signals.",
            "Do not use this to reopen global MAX_POSITION_PCT or ADDON_MAX_POSITION_PCT sweeps.",
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
