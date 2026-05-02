"""exp-20260501-028 risk-on SPY-relative 10-day leader allocation.

Alpha search. Test one capital-allocation variable: the accepted otherwise
unmodified risk_on SPY-relative leader allocation may work better with a
shorter 10-day relative-strength lookback than the current 20-day lookback.
This changes only the leader lookback used by that shared allocation sleeve.
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

import risk_engine as re  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260501-028"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "risk_on_spy_10d_leader.json"
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
    ("spy_10d_relative_leader", 10),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    attr = result.get("sizing_rule_signal_attribution") or {}
    leader_attr = attr.get("spy_relative_leader_risk_on_multiplier_applied") or {}
    trade_attr = result.get("sizing_rule_trade_attribution") or {}
    leader_trades = trade_attr.get("spy_relative_leader_risk_on_multiplier_applied") or {}
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
        "spy_relative_leader_signals_resized": leader_attr.get("signals_resized", 0),
        "spy_relative_leader_trade_count": leader_trades.get("trade_count", 0),
        "spy_relative_leader_trade_pnl": leader_trades.get("total_pnl", 0.0),
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


def _patch_enrich_for_10d_leader():
    original = re.enrich_signals

    def patched(signals, features_dict, atr_target_mult=None):
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        spy_ret10 = (features_dict.get("SPY") or {}).get("momentum_10d_pct")
        if not isinstance(spy_ret10, (int, float)):
            return enriched
        for sig in enriched:
            ticker_ret10 = (features_dict.get(sig.get("ticker")) or {}).get("momentum_10d_pct")
            if not isinstance(ticker_ret10, (int, float)):
                continue
            rel_spy_ret10 = ticker_ret10 - spy_ret10
            sig["spy_ret10_pct"] = round(spy_ret10, 4)
            sig["ticker_ret10_minus_spy_pct"] = round(rel_spy_ret10, 4)
            sig["spy_relative_leader"] = rel_spy_ret10 > 0
            sig["spy_relative_leader_lookback_days"] = 10
        return enriched

    re.enrich_signals = patched
    return original


def _run_window(universe: list[str], cfg: dict, lookback: int | None) -> dict:
    original = None
    if lookback == 10:
        original = _patch_enrich_for_10d_leader()
    try:
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
    finally:
        if original is not None:
            re.enrich_signals = original
    if "error" in result:
        raise RuntimeError(result["error"])
    return {"metrics": _metrics(result), "trades": result.get("trades", [])}


def _aggregate(before: OrderedDict, after: OrderedDict) -> dict:
    deltas = OrderedDict(
        (label, _delta(after[label]["metrics"], before[label]["metrics"]))
        for label in WINDOWS
    )
    baseline_total_pnl = round(
        sum(before[label]["metrics"]["total_pnl"] for label in WINDOWS), 2
    )
    total_pnl_delta = round(sum(d["total_pnl"] for d in deltas.values()), 2)
    baseline_ev = round(
        sum(before[label]["metrics"]["expected_value_score"] for label in WINDOWS),
        6,
    )
    ev_delta = round(sum(d["expected_value_score"] for d in deltas.values()), 6)
    return {
        "by_window": deltas,
        "expected_value_score_delta_sum": ev_delta,
        "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6) if baseline_ev else None,
        "baseline_expected_value_score_sum": baseline_ev,
        "total_pnl_delta_sum": total_pnl_delta,
        "baseline_total_pnl_sum": baseline_total_pnl,
        "total_pnl_delta_pct": round(total_pnl_delta / baseline_total_pnl, 6) if baseline_total_pnl else None,
        "ev_windows_improved": sum(1 for d in deltas.values() if d["expected_value_score"] > 0),
        "ev_windows_regressed": sum(1 for d in deltas.values() if d["expected_value_score"] < 0),
        "pnl_windows_improved": sum(1 for d in deltas.values() if d["total_pnl"] > 0),
        "pnl_windows_regressed": sum(1 for d in deltas.values() if d["total_pnl"] < 0),
        "max_drawdown_delta_max": max(d["max_drawdown_pct"] for d in deltas.values()),
        "trade_count_delta_sum": sum(d["trade_count"] for d in deltas.values()),
        "win_rate_delta_min": min(d["win_rate"] for d in deltas.values()),
        "sharpe_daily_delta_max": max(d["sharpe_daily"] for d in deltas.values()),
        "spy_relative_leader_signals_resized_delta_sum": sum(
            d["spy_relative_leader_signals_resized"] for d in deltas.values()
        ),
    }


def _passes_gate4(aggregate: dict) -> bool:
    if aggregate["ev_windows_improved"] < 2 or aggregate["ev_windows_regressed"] > 0:
        return False
    if aggregate["expected_value_score_delta_pct"] and aggregate["expected_value_score_delta_pct"] > 0.10:
        return True
    if aggregate["total_pnl_delta_pct"] and aggregate["total_pnl_delta_pct"] > 0.05:
        return True
    if aggregate["sharpe_daily_delta_max"] > 0.10:
        return True
    if aggregate["max_drawdown_delta_max"] < -0.01:
        return True
    if aggregate["trade_count_delta_sum"] > 0 and aggregate["win_rate_delta_min"] >= 0:
        return True
    return False


def build_payload() -> dict:
    universe = get_universe()
    baseline = OrderedDict()
    for label, cfg in WINDOWS.items():
        baseline[label] = _run_window(universe, cfg, None)
        m = baseline[label]["metrics"]
        print(
            f"[{label} baseline] EV={m['expected_value_score']} "
            f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
            f"DD={m['max_drawdown_pct']} WR={m['win_rate']} trades={m['trade_count']}"
        )

    variants = OrderedDict()
    for variant, lookback in VARIANTS.items():
        rows = OrderedDict()
        for label, cfg in WINDOWS.items():
            rows[label] = _run_window(universe, cfg, lookback)
            m = rows[label]["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"resized={m['spy_relative_leader_signals_resized']}"
            )
        aggregate = _aggregate(baseline, rows)
        variants[variant] = {
            "lookback_days": lookback,
            "rows": rows,
            "aggregate": aggregate,
            "passes_gate4": _passes_gate4(aggregate),
        }

    best_variant, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["ev_windows_improved"],
            -item[1]["aggregate"]["ev_windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    accepted = best["passes_gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_candidate" if accepted else "rejected",
        "decision": "accepted_candidate" if accepted else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_risk_on_spy_relative_leader_lookback",
        "hypothesis": (
            "The accepted otherwise-unmodified risk_on SPY-relative leader "
            "allocation may work better with a shorter 10-day relative-strength "
            "lookback than the current 20-day lookback."
        ),
        "alpha_hypothesis_category": "capital_allocation_meta_routing",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain too thin, so this "
            "tests a deterministic relative-strength allocation signal instead."
        ),
        "parameters": {
            "single_causal_variable": "risk_on SPY-relative leader lookback days",
            "baseline": {
                "lookback_days": 20,
                "multiplier": 2.0,
            },
            "tested_variants": {
                name: {"lookback_days": variant["lookback_days"], "multiplier": 2.0}
                for name, variant in variants.items()
            },
            "selector": {
                "regime_exit_bucket": "risk_on",
                "other_sizing_rules": "none except risk_on_unmodified",
                "ticker_return_minus_spy_return": "> 0",
            },
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk_on SPY-relative leader multiplier",
                "all sector-specific haircuts/boosts",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all exits",
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
        "before_metrics": {label: baseline[label]["metrics"] for label in WINDOWS},
        "after_metrics": {
            name: {label: variant["rows"][label]["metrics"] for label in WINDOWS}
            for name, variant in variants.items()
        },
        "delta_metrics": {
            name: variant["aggregate"] for name, variant in variants.items()
        },
        "best_variant": best_variant,
        "best_variant_gate4": accepted,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, compute ticker-vs-SPY 10-day relative strength in "
                "shared risk_engine enrichment before using it in portfolio_engine."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this avoids that data "
                "constraint rather than weakening LLM."
            ),
        },
        "history_guardrails": {
            "not_spy_relative_multiplier_retry": True,
            "not_risk_on_laggard_retry": True,
            "not_tech_leader_recovery_retry": True,
            "why_not_simple_repeat": (
                "This keeps the accepted 2.0x risk budget fixed and tests only "
                "whether the relative-strength observation horizon should be 10 "
                "days instead of 20 days."
            ),
        },
        "rejection_reason": (
            None if accepted else
            "The 10-day SPY-relative leader lookback did not pass fixed-window Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby SPY-relative lookbacks without forward evidence.",
            "A valid retry needs event/news or lifecycle context, not another lookback sweep.",
            "If promoted, update shared enrichment and production-visible attribution together.",
        ],
        "related_files": [
            "quant/experiments/exp_20260501_028_risk_on_spy_10d_leader.py",
            "data/experiments/exp-20260501-028/risk_on_spy_10d_leader.json",
            "docs/experiments/logs/exp-20260501-028.json",
            "docs/experiments/tickets/exp-20260501-028.json",
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
        "title": "Risk-on 10d SPY leader",
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
