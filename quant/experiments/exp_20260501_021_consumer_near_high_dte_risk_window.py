"""exp-20260501-021 Consumer trend near-high DTE risk-window sweep.

Alpha search. The accepted stack already zeros a narrow Consumer Discretionary
trend pocket when it is near a 52-week high and 30-65 days from earnings. This
tests one causal variable: whether the same production-shared sizing sleeve
should cover a wider event-distance window. Entries, ranking, targets, slot
caps, add-ons, LLM/news replay, and all non-Consumer rules stay locked.
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


EXPERIMENT_ID = "exp-20260501-021"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "consumer_near_high_dte_risk_window.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

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

BASELINE = {
    "late_strong": {
        "expected_value_score": 2.7000,
        "sharpe_daily": 4.30,
        "total_pnl": 62788.03,
        "total_return_pct": 0.6279,
        "max_drawdown_pct": 0.0439,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
        "tail_loss_share": 0.5045,
    },
    "mid_weak": {
        "expected_value_score": 1.2036,
        "sharpe_daily": 2.58,
        "total_pnl": 46654.10,
        "total_return_pct": 0.4665,
        "max_drawdown_pct": 0.0799,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
        "tail_loss_share": 0.4839,
    },
    "old_thin": {
        "expected_value_score": 0.2563,
        "sharpe_daily": 1.27,
        "total_pnl": 20181.65,
        "total_return_pct": 0.2018,
        "max_drawdown_pct": 0.0688,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
        "tail_loss_share": 0.4234,
    },
}

VARIANTS = OrderedDict([
    ("consumer_near_high_dte_15_90", {"dte_min": 15, "dte_max": 90}),
    ("consumer_near_high_dte_0_90", {"dte_min": 0, "dte_max": 90}),
    ("consumer_near_high_dte_0_120", {"dte_min": 0, "dte_max": 120}),
])

PATCHED_MULTIPLIER = 0.0


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_val in before.items():
        after_val = after.get(key)
        out[key] = (
            round(after_val - before_val, 6)
            if isinstance(after_val, (int, float))
            and isinstance(before_val, (int, float))
            else None
        )
    return out


def _run_window(universe: list[str], window: dict) -> dict:
    result = BacktestEngine(
        universe=universe,
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _consumer_zero_trade_summary(result: dict) -> dict:
    rows = []
    for trade in result.get("trades", []):
        multipliers = trade.get("sizing_multipliers") or {}
        if multipliers.get("trend_consumer_near_high_dte_risk_multiplier_applied") == PATCHED_MULTIPLIER:
            rows.append({
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": trade.get("pnl"),
            })
    return {
        "trade_count": len(rows),
        "pnl": round(sum(float(t.get("pnl") or 0.0) for t in rows), 2),
        "trades": rows,
    }


def _candidate_signal_count(result: dict) -> int:
    attr = result.get("sizing_rule_signal_attribution") or {}
    rec = attr.get("trend_consumer_near_high_dte_risk_multiplier_applied") or {}
    return int(rec.get("seen") or 0)


def _run_variant(universe: list[str], params: dict) -> OrderedDict:
    original = {
        "min": portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_MIN,
        "max": portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_MAX,
        "mult": portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER,
    }
    portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_MIN = params["dte_min"]
    portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_MAX = params["dte_max"]
    portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER = PATCHED_MULTIPLIER
    try:
        rows = OrderedDict()
        for label, window in WINDOWS.items():
            result = _run_window(universe, window)
            metrics = _metrics(result)
            rows[label] = {
                "metrics": metrics,
                "delta": _delta(metrics, BASELINE[label]),
                "consumer_zero_signal_count": _candidate_signal_count(result),
                "consumer_zero_trades": _consumer_zero_trade_summary(result),
            }
            print(
                f"[{label}] {params['dte_min']}-{params['dte_max']} "
                f"EV={metrics['expected_value_score']} PnL={metrics['total_pnl']} "
                f"DD={metrics['max_drawdown_pct']} zero_sigs={rows[label]['consumer_zero_signal_count']}"
            )
        return rows
    finally:
        portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_MIN = original["min"]
        portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_MAX = original["max"]
        portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER = original["mult"]


def _aggregate(rows: OrderedDict) -> dict:
    pnl_delta = round(sum(r["delta"]["total_pnl"] for r in rows.values()), 2)
    baseline_pnl = round(sum(BASELINE[label]["total_pnl"] for label in WINDOWS), 2)
    return {
        "expected_value_score_delta_sum": round(
            sum(r["delta"]["expected_value_score"] for r in rows.values()), 6
        ),
        "baseline_expected_value_score_sum": round(
            sum(BASELINE[label]["expected_value_score"] for label in WINDOWS), 6
        ),
        "total_pnl_delta_sum": pnl_delta,
        "baseline_total_pnl_sum": baseline_pnl,
        "total_pnl_delta_pct": round(pnl_delta / baseline_pnl, 6),
        "ev_windows_improved": sum(
            1 for r in rows.values() if r["delta"]["expected_value_score"] > 0
        ),
        "ev_windows_regressed": sum(
            1 for r in rows.values() if r["delta"]["expected_value_score"] < 0
        ),
        "pnl_windows_improved": sum(
            1 for r in rows.values() if r["delta"]["total_pnl"] > 0
        ),
        "pnl_windows_regressed": sum(
            1 for r in rows.values() if r["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": round(
            max(r["delta"]["max_drawdown_pct"] for r in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(r["delta"]["trade_count"] for r in rows.values()),
        "win_rate_delta_min": round(min(r["delta"]["win_rate"] for r in rows.values()), 6),
        "consumer_zero_signal_count_sum": sum(
            r["consumer_zero_signal_count"] for r in rows.values()
        ),
    }


def _gate4_passed(aggregate: dict) -> bool:
    baseline_ev = aggregate["baseline_expected_value_score_sum"]
    ev_delta = aggregate["expected_value_score_delta_sum"]
    return (
        ev_delta > baseline_ev * 0.10
        or aggregate["total_pnl_delta_pct"] > 0.05
        or aggregate["max_drawdown_delta_max"] < -0.01
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)

    universe = sorted(get_universe())
    variants = OrderedDict()
    for name, params in VARIANTS.items():
        rows = _run_variant(universe, params)
        variants[name] = {
            "parameters": params,
            "by_window": rows,
            "aggregate": _aggregate(rows),
        }

    best_variant = max(
        variants,
        key=lambda name: variants[name]["aggregate"]["expected_value_score_delta_sum"],
    )
    best = variants[best_variant]
    accepted = _gate4_passed(best["aggregate"])
    status = "accepted" if accepted else "rejected"

    log = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": status,
        "lane": "alpha_search",
        "change_type": "capital_allocation_consumer_near_high_dte_window",
        "hypothesis": (
            "Consumer Discretionary trend signals near 52-week highs may carry "
            "event-distance fragility beyond the accepted 30-65 DTE pocket; "
            "widening only that risk-zero window could reduce weak-tape leakage "
            "without changing entries or exits."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "LLM ranking samples remain too thin; this tests an alternate deterministic "
            "allocation alpha using existing days_to_earnings and pct_from_52w_high fields."
        ),
        "parameters": {
            "single_causal_variable": "Consumer near-high trend DTE zero-risk window",
            "baseline": {
                "dte_min": 30,
                "dte_max": 65,
                "max_pullback_from_52w_high": portfolio_engine.TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK,
                "risk_multiplier": portfolio_engine.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER,
            },
            "tested_variants": VARIANTS,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all non-Consumer sizing multipliers",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
                "add-ons",
                "all target/stop exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": BASELINE,
        "after_metrics": variants,
        "best_variant": best_variant,
        "best_variant_gate4_passed": accepted,
        "gate4_basis": (
            "Accepted only if aggregate EV improves >10%, aggregate PnL improves >5%, "
            "drawdown drops >1pp, or trade count rises with no win-rate regression."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted later, change constants used by shared portfolio_engine "
                "so run.py and backtester.py execute the same sizing rule."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this experiment avoids that "
                "data constraint rather than weakening LLM."
            ),
        },
        "history_guardrails": {
            "not_risk_on_scalar_retry": True,
            "not_financials_target_retry": True,
            "not_ai_infra_universe_retry": True,
            "why_not_simple_repeat": (
                "This tests Consumer Discretionary event-distance sizing, not recent "
                "AI infra, Financials, Technology breakout, or risk_on scalar families."
            ),
        },
    }

    OUT_JSON.write_text(json.dumps(log, indent=2), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(log, indent=2), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "lane": "alpha_search",
        "summary": (
            f"{best_variant} aggregate EV delta "
            f"{best['aggregate']['expected_value_score_delta_sum']:+.4f}, "
            f"PnL delta {best['aggregate']['total_pnl_delta_sum']:+.2f}; "
            f"decision={status}."
        ),
        "next_action": (
            "Promote shared constants only if accepted; otherwise do not retry nearby "
            "Consumer near-high DTE windows without event/news evidence."
        ),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2), encoding="utf-8")
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(log, ensure_ascii=False) + "\n")
    with PLAYBOOK.open("a", encoding="utf-8") as fh:
        fh.write(
            "\n### 2026-05-01 mechanism update: Consumer near-high DTE risk window\n\n"
            f"Status: {status}.\n\n"
            f"Core conclusion: `{EXPERIMENT_ID}` tested whether the accepted "
            "Consumer Discretionary near-high trend event-risk haircut should cover "
            "a wider DTE window. "
            + (
                "It is promotable under the fixed-window gate.\n\n"
                if accepted
                else "It should not be promoted.\n\n"
            )
            + "Evidence: best variant `"
            + best_variant
            + "` produced aggregate EV delta `"
            + f"{best['aggregate']['expected_value_score_delta_sum']:+.4f}"
            + "` and aggregate PnL delta `$"
            + f"{best['aggregate']['total_pnl_delta_sum']:+,.2f}"
            + "`, with EV improving in `"
            + str(best["aggregate"]["ev_windows_improved"])
            + "` windows and regressing in `"
            + str(best["aggregate"]["ev_windows_regressed"])
            + "`.\n\n"
            "Mechanism insight: Consumer near-high event-distance widening is "
            "only useful if it changes realized allocations across multiple windows; "
            "otherwise the existing narrow 30-65 DTE pocket remains the cleaner "
            "shared sizing rule.\n\n"
            "Do not repeat: nearby Consumer near-high DTE window sweeps without "
            "event/news confirmation or a broader Consumer loss-family audit.\n"
        )

    print(json.dumps(ticket, indent=2))


if __name__ == "__main__":
    main()
