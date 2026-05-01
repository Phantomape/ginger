"""exp-20260501-004 gold trend position cap.

Alpha search. Test one capital-allocation variable: whether GLD/IAU
``trend_long`` positions should have a higher position cap than the global 40%
cap. This follows exp-20260501-003, where higher gold risk budgets were inert
because the current cap already bound the executed positions.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = REPO_ROOT / "quant" / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import portfolio_engine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import exp_20260501_003_gold_trend_risk_budget as prior  # noqa: E402


EXPERIMENT_ID = "exp-20260501-004"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "gold_trend_position_cap.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

BASELINE_CAP = 0.40
TESTED_CAPS = [0.45, 0.50]


def _patch_gold_cap(position_cap: float):
    original_size_signals = portfolio_engine.size_signals

    def _wrapped_size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            if (
                sig.get("strategy") != "trend_long"
                or sig.get("ticker") not in prior.GOLD_TICKERS
                or not sig.get("sizing")
            ):
                continue

            base_risk_pct = sig["sizing"].get("base_risk_pct")
            commodity_mult = sig["sizing"].get(
                "trend_commodities_near_high_risk_multiplier_applied",
                1.0,
            )
            if base_risk_pct is None:
                continue

            original_cap = portfolio_engine.MAX_POSITION_PCT
            try:
                portfolio_engine.MAX_POSITION_PCT = position_cap
                sizing = portfolio_engine.compute_position_size(
                    portfolio_value,
                    sig["entry_price"],
                    sig["stop_price"],
                    risk_pct=base_risk_pct * commodity_mult,
                )
            finally:
                portfolio_engine.MAX_POSITION_PCT = original_cap

            if not sizing:
                continue

            sizing["base_risk_pct"] = base_risk_pct
            sizing["trade_quality_score"] = sig["sizing"].get("trade_quality_score")
            sizing["trend_commodities_near_high_risk_multiplier_applied"] = (
                commodity_mult
            )
            sizing["gold_trend_position_cap_applied"] = position_cap
            sig["sizing"] = sizing
        return sized

    portfolio_engine.size_signals = _wrapped_size_signals
    return original_size_signals


def _run_variant(universe: list[str], position_cap: float) -> OrderedDict:
    original_size_signals = _patch_gold_cap(position_cap)
    try:
        rows = OrderedDict()
        for label, cfg in prior.WINDOWS.items():
            result = prior._run_window(universe, cfg)
            rows[label] = {
                "metrics": prior._metrics(result),
                "trades": result.get("trades", []),
            }
            m = rows[label]["metrics"]
            print(
                f"[{label}] gold_cap={position_cap:.0%} "
                f"EV={m['expected_value_score']} PnL={m['total_pnl']} "
                f"SharpeD={m['sharpe_daily']} gold_trades={m['gold_trend_trade_count']}"
            )
        return rows
    finally:
        portfolio_engine.size_signals = original_size_signals


def build_payload() -> dict:
    universe = get_universe()
    baseline = _run_variant(universe, BASELINE_CAP)
    variants = OrderedDict()
    for cap in TESTED_CAPS:
        rows = _run_variant(universe, cap)
        aggregate = prior._aggregate(baseline, rows)
        variants[f"gold_trend_cap_{int(cap * 100)}pct"] = {
            "position_cap": cap,
            "rows": rows,
            "aggregate": aggregate,
            "passes_gate4": prior._passes_gate4(aggregate),
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
        "change_type": "capital_allocation_gold_trend_position_cap",
        "hypothesis": (
            "GLD/IAU trend winners are capped by the global 40% position cap; "
            "a narrow higher cap may improve capital allocation without "
            "raising non-gold Commodity exposure."
        ),
        "parameters": {
            "single_causal_variable": "GLD/IAU trend_long position cap",
            "baseline_cap": BASELINE_CAP,
            "tested_caps": TESTED_CAPS,
            "best_variant": best_name,
            "gold_tickers": sorted(prior.GOLD_TICKERS),
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all risk multipliers",
                "global MAX_POSITION_PCT for non-gold signals",
                "MAX_POSITIONS",
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
            "primary": (
                f"{prior.WINDOWS['late_strong']['start']} -> "
                f"{prior.WINDOWS['late_strong']['end']}"
            ),
            "secondary": [
                f"{prior.WINDOWS['mid_weak']['start']} -> {prior.WINDOWS['mid_weak']['end']}",
                f"{prior.WINDOWS['old_thin']['start']} -> {prior.WINDOWS['old_thin']['end']}",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in prior.WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"] for label in prior.WINDOWS
        },
        "after_metrics": {
            name: {
                label: variant["rows"][label]["metrics"]
                for label in prior.WINDOWS
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
                "If promoted, implement a shared gold trend position cap in "
                "quant/constants.py and quant/portfolio_engine.py."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking sample remains insufficient, so this tests "
                "a deterministic capital-allocation alpha instead."
            ),
        },
        "history_guardrails": {
            "builds_on_exp_20260501_003_cap_inertness": True,
            "not_global_position_cap_retry": True,
            "not_gold_target_sweep": True,
            "why_not_simple_repeat": (
                "This changes only GLD/IAU trend cap after proving risk "
                "multiplier increases were cap-bound; it does not retune the "
                "global 40% cap or add more tickers."
            ),
        },
        "rejection_reason": None if accepted else (
            "No tested gold trend position cap passed Gate 4 across the fixed windows."
        ),
        "next_retry_requires": [
            "Do not continue nearby gold cap tuning without forward concentration evidence.",
            "A valid retry needs event/news or lifecycle context, not another cap scalar.",
            "If accepted, implement through shared portfolio policy before promotion.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_004_gold_trend_position_cap.py",
            "data/experiments/exp-20260501-004/gold_trend_position_cap.json",
            "docs/experiments/logs/exp-20260501-004.json",
            "docs/experiments/tickets/exp-20260501-004.json",
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
        "title": "Gold trend position cap",
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
