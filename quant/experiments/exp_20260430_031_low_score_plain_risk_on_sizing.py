"""exp-20260430-031 low-score plain risk-on sizing sweep.

Alpha search. Test one capital-allocation variable: whether otherwise
unmodified risk-on signals with regime_exit_score < 0.10 deserve more than
the current 1.5x risk budget. Entry generation, filters, ranking, exits,
slot caps, add-ons, and LLM/news replay remain locked.
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


EXPERIMENT_ID = "exp-20260430-031"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "low_score_plain_risk_on_sizing.json"
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

BASELINE_MULTIPLIER = 1.5
TESTED_MULTIPLIERS = [1.8, 2.0]


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    risk_attr = result.get("sizing_rule_trade_attribution") or {}
    low_score_trade_count = 0
    low_score_trade_pnl = 0.0
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        applied = multipliers.get("risk_on_unmodified_risk_multiplier_applied")
        if applied == portfolio_engine.RISK_ON_UNMODIFIED_LOW_SCORE_RISK_MULTIPLIER:
            score = trade.get("regime_exit_score")
            if isinstance(score, (int, float)) and score < 0.10:
                low_score_trade_count += 1
                low_score_trade_pnl += float(trade.get("pnl") or 0.0)
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
        "low_score_plain_risk_on_trade_count": low_score_trade_count,
        "low_score_plain_risk_on_pnl": round(low_score_trade_pnl, 2),
        "risk_on_trade_attribution": risk_attr.get(
            "risk_on_unmodified_risk_multiplier_applied"
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


def _run_variant(universe: list[str], multiplier: float) -> OrderedDict:
    portfolio_engine.RISK_ON_UNMODIFIED_LOW_SCORE_RISK_MULTIPLIER = multiplier
    rows = OrderedDict()
    for label, cfg in WINDOWS.items():
        result = _run_window(universe, cfg)
        rows[label] = {
            "metrics": _metrics(result),
            "trades": result.get("trades", []),
        }
        m = rows[label]["metrics"]
        print(
            f"[{label}] low_score={multiplier} "
            f"EV={m['expected_value_score']} PnL={m['total_pnl']} "
            f"DD={m['max_drawdown_pct']} low_score_trades="
            f"{m['low_score_plain_risk_on_trade_count']}"
        )
    return rows


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(
        sum(deltas[label]["total_pnl"] for label in WINDOWS), 2
    )
    aggregate = {
        "by_window": deltas,
        "expected_value_score_delta_sum": round(
            sum(deltas[label]["expected_value_score"] for label in WINDOWS), 6
        ),
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": (
            round(total_pnl_delta / baseline_total_pnl, 6)
            if baseline_total_pnl else None
        ),
        "ev_windows_improved": sum(
            1 for label in WINDOWS
            if deltas[label]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for label in WINDOWS
            if deltas[label]["expected_value_score"] < 0
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
        "baseline_expected_value_score_sum": round(
            sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
            6,
        ),
    }
    ev_base = aggregate["baseline_expected_value_score_sum"]
    aggregate["expected_value_score_delta_pct"] = (
        round(aggregate["expected_value_score_delta_sum"] / ev_base, 6)
        if ev_base else None
    )
    return aggregate


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if (
        aggregate["expected_value_score_delta_pct"] is not None
        and aggregate["expected_value_score_delta_pct"] > 0.10
    ):
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.1:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if (
        aggregate["trade_count_delta_sum"] > 0
        and aggregate["win_rate_delta_min"] >= 0
    ):
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    original_multiplier = portfolio_engine.RISK_ON_UNMODIFIED_LOW_SCORE_RISK_MULTIPLIER
    try:
        baseline = _run_variant(universe, BASELINE_MULTIPLIER)
        variants = OrderedDict()
        for multiplier in TESTED_MULTIPLIERS:
            rows = _run_variant(universe, multiplier)
            aggregate = _aggregate(baseline, rows)
            variants[f"low_score_plain_{multiplier:.1f}x"] = {
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
            "change_type": "capital_allocation_low_score_plain_risk_on",
            "hypothesis": (
                "Otherwise unmodified risk-on signals with regime_exit_score "
                "< 0.10 are a stronger capital-allocation pocket than the "
                "current 1.5x budget captures."
            ),
            "parameters": {
                "single_causal_variable": (
                    "RISK_ON_UNMODIFIED_LOW_SCORE_RISK_MULTIPLIER for "
                    "plain risk-on signals with regime_exit_score < 0.10"
                ),
                "baseline_multiplier": BASELINE_MULTIPLIER,
                "tested_multipliers": TESTED_MULTIPLIERS,
                "best_variant": best_name,
                "locked_variables": [
                    "universe",
                    "signal generation",
                    "entry filters",
                    "candidate ranking",
                    "mid-score plain risk-on multiplier",
                    "high-score plain risk-on multiplier",
                    "all sector-specific risk multipliers",
                    "MAX_POSITIONS",
                    "MAX_POSITION_PCT",
                    "MAX_PORTFOLIO_HEAT",
                    "MAX_PER_SECTOR",
                    "gap cancels",
                    "first add-on trigger/fraction/cap",
                    "second add-ons",
                    "all exits",
                    "LLM/news replay",
                    "earnings strategy",
                ],
            },
            "date_range": {
                "primary": (
                    f"{WINDOWS['late_strong']['start']} -> "
                    f"{WINDOWS['late_strong']['end']}"
                ),
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
                    "If promoted, update quant/constants.py only; "
                    "portfolio_engine and run/backtester already consume the "
                    "shared constant."
                ),
            },
            "llm_metrics": {
                "used_llm": False,
                "blocker_relation": (
                    "LLM soft-ranking data remains insufficient, so this tests "
                    "a deterministic capital-allocation alpha instead."
                ),
            },
            "history_guardrails": {
                "not_high_score_plain_risk_on_retry": True,
                "not_mid_score_nearby_tuning": True,
                "not_sector_specific_residual_mining": True,
                "why_not_simple_repeat": (
                    "This isolates the low-score plain risk-on sleeve after "
                    "the current accepted stack; it does not touch the rejected "
                    "high-score generic multiplier or breadth-conditioned gate."
                ),
            },
            "rejection_reason": (
                None if accepted else
                "No tested low-score plain risk-on multiplier passed Gate 4 "
                "across the fixed windows."
            ),
            "next_retry_requires": [
                "Do not continue nearby low-score multiplier tuning without forward evidence.",
                "A valid retry needs a candidate-level event/news/lifecycle discriminator, not a larger scalar.",
                "If this passes and is promoted, keep it in shared constants so production/backtest stay aligned.",
            ],
            "related_files": [
                "quant/experiments/exp_20260430_031_low_score_plain_risk_on_sizing.py",
                "data/experiments/exp-20260430-031/low_score_plain_risk_on_sizing.json",
                "docs/experiments/logs/exp-20260430-031.json",
                "docs/experiments/tickets/exp-20260430-031.json",
            ],
        }
    finally:
        portfolio_engine.RISK_ON_UNMODIFIED_LOW_SCORE_RISK_MULTIPLIER = original_multiplier


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
        "title": "Low-score plain risk-on sizing",
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
