"""exp-20260502-025 portfolio heat capacity sweep.

Alpha search only. Recent accepted changes increased SPY-relative leader
initial and first add-on capacity. This tests whether the shared portfolio heat
cap is now binding after those accepted sizing rules, without changing entry,
ranking, exits, universe, LLM/news replay, or add-on triggers.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = REPO_ROOT / "quant" / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as bt  # noqa: E402
import portfolio_engine as pe  # noqa: E402
import production_parity as pp  # noqa: E402
import exp_20260502_011_old_thin_slot_routing_alpha as base  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260502-025"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "portfolio_heat_capacity.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

BASE_HEAT = 0.08
VARIANTS = {
    "heat_cap_9pct": 0.09,
    "heat_cap_10pct": 0.10,
    "heat_cap_12pct": 0.12,
}


def _set_heat_cap(value: float) -> None:
    bt.MAX_PORTFOLIO_HEAT = value
    pe.MAX_PORTFOLIO_HEAT = value
    pp.MAX_PORTFOLIO_HEAT = value


def _run_backtest(window: dict, heat_cap: float) -> dict:
    original_bt = bt.MAX_PORTFOLIO_HEAT
    original_pe = pe.MAX_PORTFOLIO_HEAT
    original_pp = pp.MAX_PORTFOLIO_HEAT
    try:
        _set_heat_cap(heat_cap)
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
    finally:
        bt.MAX_PORTFOLIO_HEAT = original_bt
        pe.MAX_PORTFOLIO_HEAT = original_pe
        pp.MAX_PORTFOLIO_HEAT = original_pp


def _metrics(result: dict) -> dict:
    metrics = base._metrics(result)
    entry_attr = result.get("entry_execution_attribution") or {}
    metrics["entry_reason_counts"] = entry_attr.get("reason_counts") or {}
    metrics["portfolio_heat_cap_skips"] = (
        metrics["entry_reason_counts"].get("portfolio_heat_cap", 0)
        + metrics["entry_reason_counts"].get("add_on_portfolio_heat_cap", 0)
    )
    metrics["addon_count"] = sum(
        int(trade.get("addon_count") or 0)
        for trade in result.get("trades") or []
    )
    metrics["spy_leader_trade_count"] = sum(
        1
        for trade in result.get("trades") or []
        if (
            (trade.get("sizing_multipliers") or {}).get(
                "spy_relative_leader_risk_on_multiplier_applied",
                1.0,
            )
            > 1.0
        )
    )
    metrics["spy_leader_pnl"] = base._round(
        sum(
            base._num(trade.get("pnl"), 0.0)
            for trade in result.get("trades") or []
            if (
                (trade.get("sizing_multipliers") or {}).get(
                    "spy_relative_leader_risk_on_multiplier_applied",
                    1.0,
                )
                > 1.0
            )
        ),
        2,
    )
    return metrics


def _delta_metrics(baseline: dict, variants: dict) -> dict:
    deltas = {}
    baseline_agg = base._aggregate({
        label: baseline[label]["metrics"]
        for label in base.WINDOWS
    })
    for variant, by_window in variants.items():
        by_label = {}
        ev_improved = 0
        ev_regressed = 0
        pnl_improved = 0
        pnl_regressed = 0
        for label in base.WINDOWS:
            b = baseline[label]["metrics"]
            a = by_window[label]["metrics"]
            row = {
                "expected_value_score": base._round(
                    base._num(a.get("expected_value_score")) - base._num(b.get("expected_value_score")),
                    4,
                ),
                "sharpe_daily": base._round(
                    base._num(a.get("sharpe_daily")) - base._num(b.get("sharpe_daily")),
                    4,
                ),
                "total_pnl": base._round(
                    base._num(a.get("total_pnl")) - base._num(b.get("total_pnl")),
                    2,
                ),
                "total_return_pct": base._round(
                    base._num(a.get("total_return_pct")) - base._num(b.get("total_return_pct")),
                    4,
                ),
                "max_drawdown_pct": base._round(
                    base._num(a.get("max_drawdown_pct")) - base._num(b.get("max_drawdown_pct")),
                    4,
                ),
                "win_rate": base._round(
                    base._num(a.get("win_rate")) - base._num(b.get("win_rate")),
                    4,
                ),
                "trade_count": int(
                    base._num(a.get("trade_count")) - base._num(b.get("trade_count"))
                ),
                "survival_rate": base._round(
                    base._num(a.get("survival_rate")) - base._num(b.get("survival_rate")),
                    4,
                ),
                "portfolio_heat_cap_skips": int(
                    base._num(a.get("portfolio_heat_cap_skips"))
                    - base._num(b.get("portfolio_heat_cap_skips"))
                ),
                "addon_count": int(
                    base._num(a.get("addon_count")) - base._num(b.get("addon_count"))
                ),
                "spy_leader_trade_count": int(
                    base._num(a.get("spy_leader_trade_count"))
                    - base._num(b.get("spy_leader_trade_count"))
                ),
                "spy_leader_pnl": base._round(
                    base._num(a.get("spy_leader_pnl")) - base._num(b.get("spy_leader_pnl")),
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

        variant_agg = base._aggregate({
            label: by_window[label]["metrics"]
            for label in base.WINDOWS
        })
        aggregate_pnl_delta = base._round(
            variant_agg["total_pnl_sum"] - baseline_agg["total_pnl_sum"],
            2,
        )
        deltas[variant] = {
            "by_window": by_label,
            "baseline_expected_value_score_sum": baseline_agg["expected_value_score_sum"],
            "variant_expected_value_score_sum": variant_agg["expected_value_score_sum"],
            "expected_value_score_delta_sum": base._round(
                variant_agg["expected_value_score_sum"] - baseline_agg["expected_value_score_sum"],
                4,
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
            "max_drawdown_delta_max": max(
                row["max_drawdown_pct"] for row in by_label.values()
            ),
            "trade_count_delta_sum": sum(
                row["trade_count"] for row in by_label.values()
            ),
            "win_rate_delta_min": min(row["win_rate"] for row in by_label.values()),
            "sharpe_daily_delta_max": max(
                row["sharpe_daily"] for row in by_label.values()
            ),
            "portfolio_heat_cap_skip_delta_sum": sum(
                row["portfolio_heat_cap_skips"] for row in by_label.values()
            ),
            "addon_count_delta_sum": sum(
                row["addon_count"] for row in by_label.values()
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
            or delta["expected_value_score_delta_sum"]
            / delta["baseline_expected_value_score_sum"]
            > 0.10
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
        baseline_result = _run_backtest(window, BASE_HEAT)
        baseline[label] = {
            "window": window,
            "metrics": _metrics(baseline_result),
        }
        for name, heat_cap in VARIANTS.items():
            result = _run_backtest(window, heat_cap)
            variants[name][label] = {
                "window": window,
                "heat_cap": heat_cap,
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
    gate4 = _passes_gate4(deltas[best_variant])
    status = "accepted_for_production_review" if gate4 else "rejected"

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": "accepted" if gate4 else "rejected",
        "lane": "alpha_search",
        "change_type": "capital_allocation_portfolio_heat_capacity",
        "hypothesis": (
            "After accepted SPY-relative leader initial and first add-on capacity "
            "increases, the global portfolio heat cap may be the next binding "
            "capacity constraint; raising only that shared heat cap could improve "
            "capital deployment without changing entries, ranking, exits, or LLM/news."
        ),
        "alpha_hypothesis_category": "capital_allocation",
        "why_not_llm_soft_ranking": (
            "Production-aligned LLM ranking samples remain outcome-join sparse; "
            "this tests a deterministic shared risk-capacity variable instead."
        ),
        "mechanism_insight_check": {
            "near_repeat": "no",
            "notes": (
                "This is not another SPY leader multiplier/cap/add-on/target retry. "
                "It tests whether accepted allocation changes exposed the existing "
                "global heat cap as a binding portfolio-level capacity constraint."
            ),
        },
        "parameters": {
            "single_causal_variable": "MAX_PORTFOLIO_HEAT",
            "baseline": BASE_HEAT,
            "tested_values": VARIANTS,
            "best_variant": best_variant,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "all signal-level risk multipliers",
                "SPY-relative leader risk budget",
                "SPY-relative leader initial position cap",
                "follow-through add-on trigger and caps",
                "MAX_POSITIONS",
                "MAX_POSITION_PCT",
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
            label: window["state_note"]
            for label, window in base.WINDOWS.items()
        },
        "before_metrics": {
            label: baseline[label]["metrics"]
            for label in base.WINDOWS
        },
        "after_metrics": {
            variant: {
                label: variants[variant][label]["metrics"]
                for label in base.WINDOWS
            }
            for variant in variants
        },
        "delta_metrics": deltas,
        "best_variant": best_variant,
        "best_variant_gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, change only quant/constants.py MAX_PORTFOLIO_HEAT "
                "and rerun canonical windows because run.py/backtester.py both "
                "consume the shared constant."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "gate4_passed": gate4,
        "gate4_basis": (
            "Accepted only if the best heat-cap variant improves EV in at least "
            "two windows without EV regression and passes one standard Gate 4 "
            "materiality criterion."
        ),
        "rejection_reason": None if gate4 else (
            "No tested portfolio heat cap passed Gate 4 across the three "
            "canonical fixed windows."
        ),
        "next_retry_requires": [] if gate4 else [
            "Do not retry nearby global heat caps without forward concentration evidence.",
            "A valid retry needs a narrower production-shared capacity discriminator.",
            "Do not pair heat-cap changes with entry, add-on, or target changes.",
        ],
        "related_files": [
            "quant/experiments/exp_20260502_025_portfolio_heat_capacity.py",
            "data/experiments/exp-20260502-025/portfolio_heat_capacity.json",
            "docs/experiments/logs/exp-20260502-025.json",
            "docs/experiments/tickets/exp-20260502-025.json",
            "docs/experiment_log.jsonl",
        ],
    }


def main() -> int:
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
        "title": "Portfolio heat capacity sweep",
        "summary": payload["hypothesis"],
        "best_variant": payload["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "next_retry_requires": payload["next_retry_requires"],
    }
    TICKET_JSON.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")
    with (REPO_ROOT / "docs" / "experiment_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["best_variant"],
        "best_variant_gate4": payload["best_variant_gate4"],
        "delta_metrics": payload["delta_metrics"][payload["best_variant"]],
        "artifact": str(OUT_JSON),
        "log": str(LOG_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
