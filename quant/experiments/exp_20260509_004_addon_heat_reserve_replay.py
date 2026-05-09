"""Replay add-on heat reserve variants across the canonical windows.

This is an alpha-search harness only. It does not change production or
backtester defaults. The single causal variable is the amount of portfolio
heat reserved from new entries so accepted follow-through add-ons can still use
the unchanged hard 8% heat cap.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from backtester import BacktestEngine  # noqa: E402


EXP_ID = "exp-20260509-004"
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull where strategy profits but can lag indexes",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape with lower win rate",
    },
}
RESERVE_VARIANTS = {
    "reserve_0_5pct_heat": 0.005,
    "reserve_1_0pct_heat": 0.010,
    "reserve_1_5pct_heat": 0.015,
    "reserve_2_0pct_heat": 0.020,
}


def _get_universe():
    try:
        from data_layer import get_universe

        return get_universe()
    except Exception:
        from filter import WATCHLIST

        return list(WATCHLIST)


def _metric_block(result):
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (
            result.get("total_return_pct")
            if result.get("total_return_pct") is not None
            else benchmarks.get("strategy_total_return_pct")
        ),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _delta(after, before):
    out = {}
    for key, base_value in before.items():
        after_value = after.get(key)
        if isinstance(base_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - base_value, 6)
    return out


def _run_window(universe, window, reserve_pct=None):
    import portfolio_engine

    original_compute_heat = portfolio_engine.compute_portfolio_heat

    if reserve_pct is not None:

        def reserved_compute_heat(*args, **kwargs):
            heat = original_compute_heat(*args, **kwargs)
            if not heat:
                return heat
            adjusted = dict(heat)
            max_heat = adjusted.get("max_heat_pct")
            heat_pct = adjusted.get("portfolio_heat_pct")
            if isinstance(max_heat, (int, float)) and isinstance(heat_pct, (int, float)):
                entry_cap = max(0.0, float(max_heat) - float(reserve_pct))
                adjusted["entry_heat_reserved_for_addons_pct"] = round(float(reserve_pct), 6)
                adjusted["entry_heat_cap_pct"] = round(entry_cap, 6)
                adjusted["can_add_new_positions"] = heat_pct < entry_cap
                adjusted["heat_note"] = (
                    f"{adjusted.get('heat_note', '')} "
                    f"Entry cap reserves {reserve_pct * 100:.1f}pp for follow-through add-ons."
                ).strip()
            return adjusted

        portfolio_engine.compute_portfolio_heat = reserved_compute_heat

    try:
        engine = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
            },
            ohlcv_snapshot_path=str(ROOT / window["snapshot"]),
        )
        result = engine.run()
        if "error" in result:
            raise RuntimeError(result["error"])
        return _metric_block(result)
    finally:
        portfolio_engine.compute_portfolio_heat = original_compute_heat


def _pct_delta(delta, base):
    if not base:
        return None
    return round(delta / base, 6)


def main():
    logging.basicConfig(level=logging.WARNING)
    universe = _get_universe()
    baseline = {}
    for label, window in WINDOWS.items():
        baseline[label] = _run_window(universe, window)

    variants = {}
    for variant_name, reserve_pct in RESERVE_VARIANTS.items():
        metrics = {}
        deltas = {}
        for label, window in WINDOWS.items():
            metrics[label] = _run_window(universe, window, reserve_pct=reserve_pct)
            deltas[label] = _delta(metrics[label], baseline[label])

        aggregate_baseline_ev = sum((baseline[w].get("expected_value_score") or 0) for w in WINDOWS)
        aggregate_after_ev = sum((metrics[w].get("expected_value_score") or 0) for w in WINDOWS)
        aggregate_baseline_pnl = sum((baseline[w].get("total_pnl") or 0) for w in WINDOWS)
        aggregate_after_pnl = sum((metrics[w].get("total_pnl") or 0) for w in WINDOWS)
        ev_delta = round(aggregate_after_ev - aggregate_baseline_ev, 6)
        pnl_delta = round(aggregate_after_pnl - aggregate_baseline_pnl, 2)
        windows_ev_improved = sum(
            1 for w in WINDOWS if (deltas[w].get("expected_value_score") or 0) > 0
        )
        variants[variant_name] = {
            "reserve_pct": reserve_pct,
            "metrics": metrics,
            "delta_metrics": deltas,
            "aggregate": {
                "baseline_expected_value_score_sum": round(aggregate_baseline_ev, 6),
                "after_expected_value_score_sum": round(aggregate_after_ev, 6),
                "expected_value_score_delta_sum": ev_delta,
                "expected_value_score_delta_pct": _pct_delta(ev_delta, aggregate_baseline_ev),
                "baseline_total_pnl_sum": round(aggregate_baseline_pnl, 2),
                "after_total_pnl_sum": round(aggregate_after_pnl, 2),
                "total_pnl_delta_sum": pnl_delta,
                "total_pnl_delta_pct": _pct_delta(pnl_delta, aggregate_baseline_pnl),
                "windows_ev_improved": windows_ev_improved,
                "windows_ev_regressed": sum(
                    1 for w in WINDOWS if (deltas[w].get("expected_value_score") or 0) < 0
                ),
            },
        }

    best_name, best = max(
        variants.items(),
        key=lambda item: (
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_aggregate = best["aggregate"]
    gate4_passed = (
        best_aggregate["windows_ev_improved"] >= 2
        and (
            (best_aggregate["expected_value_score_delta_pct"] or 0) > 0.10
            or (best_aggregate["total_pnl_delta_pct"] or 0) > 0.05
            or any(
                (best["delta_metrics"][w].get("sharpe_daily") or 0) > 0.1
                for w in WINDOWS
            )
            or sum(
                1
                for w in WINDOWS
                if (best["delta_metrics"][w].get("max_drawdown_pct") or 0) < -0.01
            )
            >= 1
        )
    )

    payload = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "alpha_hypothesis_category": "capital_allocation_addon_reserve",
        "hypothesis": (
            "Preserving a small slice of the hard 8% portfolio heat cap for "
            "already-qualified follow-through add-ons may improve expected "
            "value by stopping lower-priority new entries earlier while still "
            "letting add-ons obey the unchanged hard heat cap."
        ),
        "change_type": "capital_allocation_entry_heat_reserve_replay",
        "single_causal_variable": "entry_heat_reserved_for_followthrough_addons_pct",
        "parameters": {
            "hard_portfolio_heat_cap_unchanged": 0.08,
            "reserve_variants": RESERVE_VARIANTS,
            "locked_variables": [
                "signal generation",
                "candidate ranking",
                "position sizing",
                "add-on trigger",
                "add-on fraction",
                "add-on position cap",
                "add-on hard heat cap",
                "stops and targets",
                "LLM/news replay",
                "universe",
            ],
        },
        "historical_experiment_check": {
            "exp-20260508-017": (
                "Raw add-on heat cap removal was positive but rejected as unsafe; "
                "this keeps the hard cap and reserves entry heat instead."
            ),
            "exp-20260508-018": "Same-day add-on ordering had no effect.",
            "exp-20260508-034": "Blanket staged entry reduced EV/PnL in all windows.",
            "exp-20260508-038": "Selective nonleader staged entry had zero coverage.",
        },
        "mechanism_insight_check": {
            "recent_ban_hit": False,
            "why_not_repeat": (
                "This is not heat-cap relaxation, same-day ordering, add-on cap tuning, "
                "or blanket staged entry. It changes only entry admission heat room."
            ),
            "priority_change": (
                "Add-on capital allocation remains a valid alpha branch because it has "
                "full OHLCV replay and does not depend on the blocked LLM/news samples."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["regime"] for label, window in WINDOWS.items()
        },
        "before_metrics": baseline,
        "variants": variants,
        "best_variant": best_name,
        "after_metrics": best["metrics"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best_aggregate["expected_value_score_delta_sum"],
        "gate4": {
            "passed": gate4_passed,
            "basis": "Three canonical windows; EV-first with Gate 4 materiality.",
            "best_variant": best_name,
            **copy.deepcopy(best_aggregate),
        },
        "decision": "accepted_for_shared_policy_followup" if gate4_passed else "rejected",
        "rejection_reason": (
            None
            if gate4_passed
            else "No tested entry-heat reserve cleared the three-window EV-first Gate 4 bar."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "promotion_requirement_if_positive": (
                "Move the entry heat admission threshold into shared production_parity "
                "policy, call it from both run.py and backtester.py, and add parity tests."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_no_llm_change": (
                "LLM soft-ranking remains sample-blocked; this alpha test uses fully "
                "replayable OHLCV/add-on mechanics."
            ),
        },
        "next_retry_requires": [
            "Do not retry nearby reserve thresholds if all variants are rejected.",
            "A valid retry needs a state-specific add-on value discriminator or forward add-on replacement evidence.",
            "Any positive promotion must be shared between production and backtest before default enablement.",
        ],
    }

    out_dir = ROOT / "data" / "experiments" / EXP_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "addon_heat_reserve_replay.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    log_dir = ROOT / "docs" / "experiments" / "logs"
    ticket_dir = ROOT / "docs" / "experiments" / "tickets"
    artifact_dir = ROOT / "docs" / "experiments" / "artifacts"
    log_dir.mkdir(parents=True, exist_ok=True)
    ticket_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{EXP_ID}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (ticket_dir / f"{EXP_ID}.json").write_text(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "title": "Add-on heat reserve replay",
                "decision": payload["decision"],
                "best_variant": best_name,
                "gate4": payload["gate4"],
                "next_action": (
                    "Implement shared policy only if accepted; otherwise avoid nearby reserves."
                ),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    lines = [
        f"# {EXP_ID} Add-on Heat Reserve Replay",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best_name}`",
        "",
        "| Window | Before EV | After EV | EV Delta | Before PnL | After PnL | PnL Delta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = baseline[label]
        after = best["metrics"][label]
        delta = best["delta_metrics"][label]
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} | "
            f"{delta.get('expected_value_score', 0):+.4f} | "
            f"${before['total_pnl']:,.2f} | ${after['total_pnl']:,.2f} | "
            f"${delta.get('total_pnl', 0):+,.2f} |"
        )
    lines.extend(
        [
            "",
            "The hard 8% portfolio heat cap remains unchanged. Only new-entry",
            "admission is shadow-lowered by the reserve amount; add-ons still use",
            "the unchanged hard cap in the cap calculation.",
        ]
    )
    (artifact_dir / f"{EXP_ID}_addon_heat_reserve_replay.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))
    print(out_path)


if __name__ == "__main__":
    main()
