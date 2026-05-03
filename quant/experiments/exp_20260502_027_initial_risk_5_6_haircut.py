"""exp-20260502-027 initial-risk 5-6% sizing haircut.

Alpha search only. Current accepted-stack trade attribution shows the 5-6%
initial stop-distance bucket has poor realized quality across the fixed
windows. This tests one production-visible sizing variable without changing
entry generation, ranking, exits, add-ons, universe, or LLM/news replay.
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


EXPERIMENT_ID = "exp-20260502-027"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "initial_risk_5_6_haircut.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

RISK_MIN = 0.05
RISK_MAX = 0.06
BASE_MULTIPLIER = 1.0
VARIANTS = {
    "risk_5_6pct_0x": 0.0,
    "risk_5_6pct_0_25x": 0.25,
    "risk_5_6pct_0_50x": 0.50,
}


@contextmanager
def _initial_risk_multiplier(multiplier: float):
    original_compute_position_size = pe.compute_position_size

    def patched_compute_position_size(
        portfolio_value,
        entry_price,
        stop_price,
        risk_pct=pe.RISK_PER_TRADE_PCT,
        max_position_pct=pe.MAX_POSITION_PCT,
    ):
        adjusted_risk_pct = risk_pct
        if entry_price and stop_price and entry_price > 0:
            initial_risk_pct = (entry_price - stop_price) / entry_price
            if RISK_MIN <= initial_risk_pct < RISK_MAX:
                adjusted_risk_pct = risk_pct * multiplier
        return original_compute_position_size(
            portfolio_value,
            entry_price,
            stop_price,
            risk_pct=adjusted_risk_pct,
            max_position_pct=max_position_pct,
        )

    pe.compute_position_size = patched_compute_position_size
    try:
        yield
    finally:
        pe.compute_position_size = original_compute_position_size


def _run_backtest(window: dict, multiplier: float) -> dict:
    with _initial_risk_multiplier(multiplier):
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


def _risk_bucket_trade_stats(result: dict) -> dict:
    trades = result.get("trades") or []
    selected = [
        trade for trade in trades
        if RISK_MIN <= base._num(trade.get("initial_risk_pct"), -1.0) < RISK_MAX
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
    metrics["initial_risk_5_6pct"] = _risk_bucket_trade_stats(result)
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
                    base._num(after.get("total_pnl"))
                    - base._num(before.get("total_pnl")),
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
                    base._num(after.get("trade_count"))
                    - base._num(before.get("trade_count"))
                ),
                "survival_rate": base._round(
                    base._num(after.get("survival_rate"))
                    - base._num(before.get("survival_rate")),
                    4,
                ),
                "risk_bucket_pnl": base._round(
                    base._num(after["initial_risk_5_6pct"].get("total_pnl"))
                    - base._num(before["initial_risk_5_6pct"].get("total_pnl")),
                    2,
                ),
                "risk_bucket_trade_count": int(
                    base._num(after["initial_risk_5_6pct"].get("trade_count"))
                    - base._num(before["initial_risk_5_6pct"].get("trade_count"))
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
        deltas[variant] = {
            "by_window": by_label,
            "baseline_expected_value_score_sum": baseline_agg["expected_value_score_sum"],
            "variant_expected_value_score_sum": variant_agg["expected_value_score_sum"],
            "expected_value_score_delta_sum": base._round(
                variant_agg["expected_value_score_sum"]
                - baseline_agg["expected_value_score_sum"],
                4,
            ),
            "expected_value_score_delta_pct": base._round(
                (
                    variant_agg["expected_value_score_sum"]
                    - baseline_agg["expected_value_score_sum"]
                )
                / baseline_agg["expected_value_score_sum"],
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
        "status": "accepted" if gate4_passed else "rejected",
        "decision": "accepted" if gate4_passed else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_initial_risk_width",
        "hypothesis": (
            "Signals whose initial stop distance is 5-6% are a repeat fragile "
            "risk-width pocket, so applying only a sizing haircut there may "
            "improve EV without changing entries, ranking, exits, or LLM/news."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain outcome-join sparse; "
            "this tests a deterministic production-visible sizing feature instead."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "notes": (
                "This touches stop-width, a previously dangerous family. It is "
                "not a trend-only 5-7% retry or SPY-leader wide-stop retry; it "
                "tests the current accepted stack's cross-sleeve 5-6% bucket once."
            ),
        },
        "parameters": {
            "single_causal_variable": "initial_risk_5_6pct_sizing_multiplier",
            "risk_bucket": {"min_inclusive": RISK_MIN, "max_exclusive": RISK_MAX},
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
            "Accepted only if the best initial-risk haircut improves EV in at "
            "least two windows without EV regression and passes one standard "
            "Gate 4 materiality criterion."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, implement the multiplier in shared "
                "portfolio_engine.py/constants.py so run.py and backtester.py "
                "consume the same sizing logic."
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "rejection_reason": (
            None
            if gate4_passed
            else "No tested 5-6% initial-risk sizing multiplier passed Gate 4."
        ),
        "next_retry_requires": [
            "Do not retry nearby stop-width-only buckets without event/news or lifecycle evidence.",
            "A valid retry needs an orthogonal discriminator explaining which 5-6% risk trades deserve less capital.",
        ],
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
        "title": "Initial-risk 5-6% sizing haircut",
        "summary": payload["hypothesis"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "next_action": (
            "Promote only through shared portfolio sizing."
            if payload["gate4_passed"]
            else "Do not promote; record as rejected stop-width-only alpha."
        ),
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    print(
        f"{EXPERIMENT_ID} {payload['status']} best={payload['best_variant']} "
        f"gate4={payload['gate4_passed']}"
    )
    print(json.dumps(payload["delta_metrics"][payload["best_variant"]], indent=2))


if __name__ == "__main__":
    main()
