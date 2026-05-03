"""exp-20260503-001 trend Industrials reactivation sweep.

Alpha search only. The current accepted stack has accumulated several broad
allocation improvements since the older trend-Industrials 0x haircut was
accepted. This tests whether that zero-risk sleeve is now over-suppressing
tradable alpha, without changing entries, ranking, exits, add-ons, universe, or
LLM/news replay.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = REPO_ROOT / "quant" / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import portfolio_engine as pe  # noqa: E402
import exp_20260502_011_old_thin_slot_routing_alpha as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260503-001"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "trend_industrials_reactivation.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

BASE_MULTIPLIER = 0.0
VARIANTS = {
    "trend_industrials_0_25x": 0.25,
    "trend_industrials_0_50x": 0.50,
    "trend_industrials_1_00x": 1.00,
}


@contextmanager
def _trend_industrials_multiplier(multiplier: float):
    original = pe.TREND_INDUSTRIALS_RISK_MULTIPLIER
    pe.TREND_INDUSTRIALS_RISK_MULTIPLIER = multiplier
    try:
        yield
    finally:
        pe.TREND_INDUSTRIALS_RISK_MULTIPLIER = original


def _run_backtest(window: dict, multiplier: float) -> dict:
    with _trend_industrials_multiplier(multiplier):
        engine = BacktestEngine(
            get_universe(),
            start=window["start"],
            end=window["end"],
            config=base.CONFIG,
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        )
        return engine.run()


def _trend_industrials_trade_stats(result: dict) -> dict:
    selected = [
        trade for trade in result.get("trades") or []
        if trade.get("strategy") == "trend_long"
        and trade.get("sector") == "Industrials"
    ]
    return {
        "trade_count": len(selected),
        "wins": sum(1 for trade in selected if base._num(trade.get("pnl"), 0.0) > 0),
        "total_pnl": base._round(
            sum(base._num(trade.get("pnl"), 0.0) for trade in selected),
            2,
        ),
        "tickers": sorted({trade.get("ticker") for trade in selected if trade.get("ticker")}),
    }


def _metrics(result: dict) -> dict:
    metrics = base._metrics(result)
    metrics["trend_industrials"] = _trend_industrials_trade_stats(result)
    metrics["entry_reason_counts"] = (
        result.get("entry_execution_attribution") or {}
    ).get("reason_counts", {})
    metrics["sizing_rule_signal_attribution"] = (
        result.get("sizing_rule_signal_attribution") or {}
    ).get("trend_industrials_risk_multiplier_applied", {})
    metrics["sizing_rule_trade_attribution"] = (
        result.get("sizing_rule_trade_attribution") or {}
    ).get("trend_industrials_risk_multiplier_applied", {})
    return metrics


def _aggregate_metrics(by_window: dict) -> dict:
    return base._aggregate({
        label: row["metrics"]
        for label, row in by_window.items()
    })


def _delta_metrics(baseline: dict, variants: dict) -> dict:
    deltas = {}
    baseline_agg = _aggregate_metrics(baseline)
    for variant, by_window in variants.items():
        by_label = {}
        ev_improved = 0
        ev_regressed = 0
        pnl_improved = 0
        pnl_regressed = 0
        for label in base.WINDOWS:
            before = baseline[label]["metrics"]
            after = by_window[label]["metrics"]
            row = {
                "expected_value_score": base._round(
                    base._num(after.get("expected_value_score"))
                    - base._num(before.get("expected_value_score")),
                    4,
                ),
                "sharpe_daily": base._round(
                    base._num(after.get("sharpe_daily"))
                    - base._num(before.get("sharpe_daily")),
                    4,
                ),
                "total_pnl": base._round(
                    base._num(after.get("total_pnl")) - base._num(before.get("total_pnl")),
                    2,
                ),
                "total_return_pct": base._round(
                    base._num(after.get("total_return_pct"))
                    - base._num(before.get("total_return_pct")),
                    4,
                ),
                "max_drawdown_pct": base._round(
                    base._num(after.get("max_drawdown_pct"))
                    - base._num(before.get("max_drawdown_pct")),
                    4,
                ),
                "win_rate": base._round(
                    base._num(after.get("win_rate")) - base._num(before.get("win_rate")),
                    4,
                ),
                "trade_count": int(
                    base._num(after.get("trade_count")) - base._num(before.get("trade_count"))
                ),
                "survival_rate": base._round(
                    base._num(after.get("survival_rate"))
                    - base._num(before.get("survival_rate")),
                    4,
                ),
                "trend_industrials_trade_count": int(
                    base._num(after["trend_industrials"].get("trade_count"))
                    - base._num(before["trend_industrials"].get("trade_count"))
                ),
                "trend_industrials_pnl": base._round(
                    base._num(after["trend_industrials"].get("total_pnl"))
                    - base._num(before["trend_industrials"].get("total_pnl")),
                    2,
                ),
            }
            if row["expected_value_score"] > 0:
                ev_improved += 1
            if row["expected_value_score"] < 0:
                ev_regressed += 1
            if row["total_pnl"] > 0:
                pnl_improved += 1
            if row["total_pnl"] < 0:
                pnl_regressed += 1
            by_label[label] = row

        variant_agg = _aggregate_metrics(by_window)
        aggregate_pnl_delta = base._round(
            variant_agg["total_pnl_sum"] - baseline_agg["total_pnl_sum"],
            2,
        )
        aggregate_ev_delta = base._round(
            variant_agg["expected_value_score_sum"]
            - baseline_agg["expected_value_score_sum"],
            4,
        )
        deltas[variant] = {
            "by_window": by_label,
            "baseline_expected_value_score_sum": baseline_agg["expected_value_score_sum"],
            "variant_expected_value_score_sum": variant_agg["expected_value_score_sum"],
            "expected_value_score_delta_sum": aggregate_ev_delta,
            "expected_value_score_delta_pct": base._round(
                aggregate_ev_delta / baseline_agg["expected_value_score_sum"],
                6,
            ),
            "baseline_total_pnl_sum": baseline_agg["total_pnl_sum"],
            "variant_total_pnl_sum": variant_agg["total_pnl_sum"],
            "total_pnl_delta_sum": aggregate_pnl_delta,
            "total_pnl_delta_pct": base._round(
                aggregate_pnl_delta / baseline_agg["total_pnl_sum"],
                6,
            ),
            "ev_windows_improved": ev_improved,
            "ev_windows_regressed": ev_regressed,
            "pnl_windows_improved": pnl_improved,
            "pnl_windows_regressed": pnl_regressed,
            "max_drawdown_delta_max": max(row["max_drawdown_pct"] for row in by_label.values()),
            "trade_count_delta_sum": sum(row["trade_count"] for row in by_label.values()),
            "win_rate_delta_min": min(row["win_rate"] for row in by_label.values()),
            "sharpe_daily_delta_max": max(row["sharpe_daily"] for row in by_label.values()),
            "trend_industrials_trade_count_delta_sum": sum(
                row["trend_industrials_trade_count"] for row in by_label.values()
            ),
            "trend_industrials_pnl_delta_sum": base._round(
                sum(row["trend_industrials_pnl"] for row in by_label.values()),
                2,
            ),
        }
    return deltas


def _passes_gate4(delta: dict) -> bool:
    return bool(
        delta["ev_windows_improved"] >= 2
        and delta["ev_windows_regressed"] == 0
        and (
            delta["total_pnl_delta_pct"] > 0.05
            or delta["sharpe_daily_delta_max"] > 0.1
            or delta["max_drawdown_delta_max"] < -0.01
            or delta["expected_value_score_delta_pct"] > 0.10
            or (
                delta["trade_count_delta_sum"] > 0
                and delta["win_rate_delta_min"] >= 0
            )
        )
    )


def build_payload() -> dict:
    baseline = {}
    variants = {name: {} for name in VARIANTS}
    for label, window in base.WINDOWS.items():
        baseline_result = _run_backtest(window, BASE_MULTIPLIER)
        baseline[label] = {
            "window": window,
            "metrics": _metrics(baseline_result),
        }
        for variant, multiplier in VARIANTS.items():
            result = _run_backtest(window, multiplier)
            variants[variant][label] = {
                "window": window,
                "metrics": _metrics(result),
            }

    deltas = _delta_metrics(baseline, variants)
    best_variant = max(
        deltas,
        key=lambda name: (
            deltas[name]["expected_value_score_delta_sum"],
            deltas[name]["total_pnl_delta_sum"],
        ),
    )
    gate4_passed = _passes_gate4(deltas[best_variant])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_for_production_review" if gate4_passed else "rejected",
        "decision": "accepted" if gate4_passed else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_trend_industrials_reactivation",
        "hypothesis": (
            "The older 0x trend Industrials haircut may now be too conservative "
            "after the accepted SPY-relative leader, cap, and add-on allocation "
            "stack; restoring a small risk budget could recover capital-efficient "
            "trend alpha without changing entries or exits."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking remains outcome-join sparse; this "
            "tests a deterministic production-visible sizing variable instead."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "notes": (
                "This revalidates one old zero-risk sleeve after material accepted "
                "allocation-stack changes. It is not a nearby SPY leader multiplier, "
                "cap, heat, stop-width, target, gap, ranking, or universe expansion retry."
            ),
        },
        "parameters": {
            "single_causal_variable": "TREND_INDUSTRIALS_RISK_MULTIPLIER",
            "baseline": BASE_MULTIPLIER,
            "tested_values": VARIANTS,
            "best_variant": best_variant,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all other sizing rules",
                "SPY-relative leader risk budget and caps",
                "follow-through add-on trigger and caps",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "gap cancels",
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
            label: row["state_note"] for label, row in base.WINDOWS.items()
        },
        "before_metrics": {label: row["metrics"] for label, row in baseline.items()},
        "after_metrics": {
            variant: {label: row["metrics"] for label, row in by_window.items()}
            for variant, by_window in variants.items()
        },
        "delta_metrics": deltas,
        "best_variant": best_variant,
        "best_variant_gate4": gate4_passed,
        "gate4_passed": gate4_passed,
        "gate4_basis": (
            "Accepted only if the best reactivation improves EV in at least two "
            "windows without EV regression and passes one standard Gate 4 "
            "materiality criterion."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, change only quant/constants.py "
                "TREND_INDUSTRIALS_RISK_MULTIPLIER because run.py and "
                "backtester.py both consume portfolio_engine sizing."
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": (
            None
            if gate4_passed
            else "No tested trend Industrials reactivation multiplier passed Gate 4."
        ),
        "next_retry_requires": (
            []
            if gate4_passed
            else [
                "Do not retry nearby trend Industrials multipliers without forward evidence.",
                "A valid retry needs event/news context or a new lifecycle discriminator.",
            ]
        ),
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
        ],
    }


def main() -> None:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "title": "Trend Industrials reactivation sweep",
        "summary": payload["hypothesis"],
        "best_variant": payload["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "next_action": (
            "Promote only through shared constants."
            if payload["gate4_passed"]
            else "Do not promote; keep trend Industrials at 0x."
        ),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(
        f"{EXPERIMENT_ID} {payload['status']} best={payload['best_variant']} "
        f"gate4={payload['gate4_passed']}"
    )
    print(json.dumps(payload["delta_metrics"][payload["best_variant"]], indent=2))


if __name__ == "__main__":
    main()
