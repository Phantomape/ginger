"""exp-20260501-003 gold trend risk budget.

Alpha search. Test one capital-allocation variable: whether GLD/IAU
``trend_long`` signals deserve a higher non-stacking risk budget after the
accepted gold-only 8 ATR target extension. Entries, exits, ranking, slots,
add-ons, LLM/news replay, and non-gold Commodity sizing remain locked.
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

import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260501-003"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "gold_trend_risk_budget.json"
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

GOLD_TICKERS = {"GLD", "IAU"}
BASELINE_MULTIPLIER = 1.5
TESTED_MULTIPLIERS = [1.8, 2.0]


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    gold_trades = [
        trade for trade in result.get("trades", [])
        if trade.get("strategy") == "trend_long"
        and trade.get("ticker") in GOLD_TICKERS
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
        "gold_trend_trade_count": len(gold_trades),
        "gold_trend_pnl": round(
            sum(float(t.get("pnl") or 0.0) for t in gold_trades),
            2,
        ),
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


def _run_window(universe: list[str], cfg: dict) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _patch_gold_risk(multiplier: float):
    original_size_signals = portfolio_engine.size_signals

    def _wrapped_size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if (
                sig.get("strategy") != "trend_long"
                or sig.get("ticker") not in GOLD_TICKERS
                or not sig.get("sizing")
            ):
                continue

            base_risk_pct = sig["sizing"].get("base_risk_pct")
            if base_risk_pct is None:
                continue

            sizing = portfolio_engine.compute_position_size(
                portfolio_value,
                sig["entry_price"],
                sig["stop_price"],
                risk_pct=base_risk_pct * multiplier,
            )
            if not sizing:
                continue

            sizing["base_risk_pct"] = base_risk_pct
            sizing["trade_quality_score"] = sig["sizing"].get("trade_quality_score")
            sizing["trend_commodities_near_high_risk_multiplier_applied"] = (
                sig["sizing"].get("trend_commodities_near_high_risk_multiplier_applied")
            )
            sizing["gold_trend_risk_multiplier_applied"] = multiplier
            sig["sizing"] = sizing
        return sized

    portfolio_engine.size_signals = _wrapped_size_signals
    return original_size_signals


def _run_variant(universe: list[str], multiplier: float) -> OrderedDict:
    original_size_signals = _patch_gold_risk(multiplier)
    try:
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            result = _run_window(universe, cfg)
            rows[label] = {
                "metrics": _metrics(result),
                "trades": result.get("trades", []),
            }
            m = rows[label]["metrics"]
            print(
                f"[{label}] gold_risk={multiplier} "
                f"EV={m['expected_value_score']} PnL={m['total_pnl']} "
                f"SharpeD={m['sharpe_daily']} gold_trades={m['gold_trend_trade_count']}"
            )
        return rows
    finally:
        portfolio_engine.size_signals = original_size_signals


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS),
        2,
    )
    total_pnl_delta = round(
        sum(deltas[label]["total_pnl"] for label in WINDOWS),
        2,
    )
    ev_base = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(
        sum(deltas[label]["expected_value_score"] for label in WINDOWS),
        6,
    )
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / ev_base, 6) if ev_base else None,
        "baseline_expected_value_score_sum": ev_base,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6)
        if baseline_total_pnl else None,
        "ev_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS if deltas[label]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for label in WINDOWS if deltas[label]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": max(
            deltas[label]["max_drawdown_pct"] for label in WINDOWS
        ),
        "trade_count_delta_sum": sum(deltas[label]["trade_count"] for label in WINDOWS),
        "win_rate_delta_min": min(deltas[label]["win_rate"] for label in WINDOWS),
        "sharpe_daily_delta_max": max(
            deltas[label]["sharpe_daily"] for label in WINDOWS
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.1:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    baseline = _run_variant(universe, BASELINE_MULTIPLIER)
    variants = OrderedDict()
    for multiplier in TESTED_MULTIPLIERS:
        rows = _run_variant(universe, multiplier)
        aggregate = _aggregate(baseline, rows)
        variants[f"gold_trend_{multiplier:.1f}x"] = {
            "multiplier": multiplier,
            "rows": rows,
            "aggregate": aggregate,
            "passes_gate4": _passes_gate4(aggregate),
        }

    best_name, best = max(
        variants.items(),
        key=lambda item: item[1]["aggregate"]["expected_value_score_delta_sum"],
    )
    accepted = best["passes_gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_gold_trend_risk_budget",
        "hypothesis": (
            "After the accepted GLD/IAU 8ATR target extension, gold ETF "
            "trend signals may deserve a higher non-stacking risk budget "
            "because the sleeve shows cleaner continuation than broad Commodities."
        ),
        "parameters": {
            "single_causal_variable": "GLD/IAU trend_long risk multiplier",
            "baseline_multiplier": BASELINE_MULTIPLIER,
            "tested_multipliers": TESTED_MULTIPLIERS,
            "best_variant": best_name,
            "gold_tickers": sorted(GOLD_TICKERS),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all non-gold sizing rules",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits including gold 8ATR target",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": f"{WINDOWS['late_strong']['start']} -> {WINDOWS['late_strong']['end']}",
            "secondary": [
                f"{WINDOWS['mid_weak']['start']} -> {WINDOWS['mid_weak']['end']}",
                f"{WINDOWS['old_thin']['start']} -> {WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            name: {
                label: variant["rows"][label]["metrics"]
                for label in WINDOWS
            }
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "best_variant": best_name,
        "best_variant_gate4": best["passes_gate4"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If promoted, add a shared gold trend sizing constant and "
                "condition to quant/constants.py and quant/portfolio_engine.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking sample remains insufficient, so this tests a "
                "deterministic capital-allocation alpha instead."
            ),
        },
        "history_guardrails": {
            "not_nearby_gold_target_sweep": True,
            "not_broad_commodity_final_budget_retry": True,
            "not_etf_universe_expansion": True,
            "why_not_simple_repeat": (
                "This changes risk budget only for already-selected GLD/IAU "
                "trend signals. It does not widen targets, add ETF candidates, "
                "or increase all Commodity exposure."
            ),
        },
        "rejection_reason": None if accepted else (
            "No tested gold trend risk multiplier passed Gate 4 across the fixed windows."
        ),
        "next_retry_requires": [
            "Do not continue nearby gold risk multipliers without forward evidence.",
            "A valid retry needs event/news or lifecycle context, not another scalar.",
            "If accepted, implement in shared portfolio policy before promotion.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_003_gold_trend_risk_budget.py",
            "data/experiments/exp-20260501-003/gold_trend_risk_budget.json",
            "docs/experiments/logs/exp-20260501-003.json",
            "docs/experiments/tickets/exp-20260501-003.json",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text, encoding="utf-8")
    LOG_JSON.write_text(text, encoding="utf-8")
    TICKET_JSON.write_text(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Gold trend risk budget",
        "summary": (
            f"Best {payload['best_variant']} "
            f"Gate4={payload['best_variant_gate4']}"
        ),
        "best_variant": payload["best_variant"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "production_impact": payload["production_impact"],
    }, indent=2), encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_gate4": payload["best_variant_gate4"],
        "best_delta": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
