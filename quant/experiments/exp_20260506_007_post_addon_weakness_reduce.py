from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from quant.backtester import BacktestEngine  # noqa: E402

try:
    from quant.data_layer import get_universe  # noqa: E402
except Exception:  # pragma: no cover - CLI fallback parity
    from quant.filter import WATCHLIST  # noqa: E402

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260506-007"
OUTPUT = Path(
    "data/experiments/exp-20260506-007/"
    "exp_20260506_007_post_addon_weakness_reduce.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

VARIANT_CONFIG = {
    "POST_ADDON_WEAKNESS_REDUCE_ENABLED": True,
    "POST_ADDON_WEAKNESS_DAYS": 3,
    "POST_ADDON_WEAKNESS_MIN_RS_VS_SPY": 0.0,
    "POST_ADDON_WEAKNESS_REQUIRE_NEGATIVE_ADDON_RETURN": True,
}


def metric_view(result):
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
    }


def post_addon_weakness_events(result):
    events = (result.get("partial_reduce_attribution") or {}).get("events") or []
    return [
        event
        for event in events
        if event.get("exit_reason") == "partial_reduce_post_addon_weakness"
    ]


def run_window(universe, spec, config=None):
    engine = BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
            **(config or {}),
        },
        ohlcv_snapshot_path=spec["snapshot"],
    )
    return engine.run()


def delta(after, before):
    if after is None or before is None:
        return None
    return round(after - before, 6)


def pct_delta(after, before):
    if after is None or before in (None, 0):
        return None
    return round((after - before) / abs(before), 6)


def summarize_comparison(baseline, variant):
    before = metric_view(baseline)
    after = metric_view(variant)
    return {
        "before": before,
        "after": after,
        "delta": {
            "expected_value_score": delta(
                after["expected_value_score"],
                before["expected_value_score"],
            ),
            "expected_value_score_pct": pct_delta(
                after["expected_value_score"],
                before["expected_value_score"],
            ),
            "sharpe_daily": delta(after["sharpe_daily"], before["sharpe_daily"]),
            "max_drawdown_pct": delta(
                after["max_drawdown_pct"],
                before["max_drawdown_pct"],
            ),
            "total_pnl": delta(after["total_pnl"], before["total_pnl"]),
            "win_rate": delta(after["win_rate"], before["win_rate"]),
            "total_trades": delta(after["total_trades"], before["total_trades"]),
            "survival_rate": delta(after["survival_rate"], before["survival_rate"]),
        },
        "post_addon_weakness_reduce": {
            "scheduled_events": len(post_addon_weakness_events(variant)),
            "executed_events": sum(
                1
                for event in post_addon_weakness_events(variant)
                if event.get("status") == "executed"
            ),
            "events": post_addon_weakness_events(variant),
        },
    }


def main():
    logging.basicConfig(level=logging.WARNING)
    universe = get_universe()
    window_results = {}
    for name, spec in WINDOWS.items():
        baseline = run_window(universe, spec)
        variant = run_window(universe, spec, VARIANT_CONFIG)
        window_results[name] = summarize_comparison(baseline, variant)

    aggregate_before_ev = sum(
        row["before"]["expected_value_score"] for row in window_results.values()
    )
    aggregate_after_ev = sum(
        row["after"]["expected_value_score"] for row in window_results.values()
    )
    aggregate_before_pnl = sum(row["before"]["total_pnl"] for row in window_results.values())
    aggregate_after_pnl = sum(row["after"]["total_pnl"] for row in window_results.values())
    ev_improved_windows = sum(
        1
        for row in window_results.values()
        if row["delta"]["expected_value_score"] > 0
    )
    pnl_improved_windows = sum(
        1 for row in window_results.values() if row["delta"]["total_pnl"] > 0
    )
    total_executed_events = sum(
        row["post_addon_weakness_reduce"]["executed_events"]
        for row in window_results.values()
    )
    aggregate_ev_delta = round(aggregate_after_ev - aggregate_before_ev, 6)
    aggregate_ev_delta_pct = pct_delta(aggregate_after_ev, aggregate_before_ev)
    aggregate_pnl_delta = round(aggregate_after_pnl - aggregate_before_pnl, 2)

    accepted = (
        aggregate_ev_delta_pct is not None
        and aggregate_ev_delta_pct > 0.10
        and ev_improved_windows >= 2
        and aggregate_pnl_delta > 0
    )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "alpha_hypothesis": (
            "After an accepted follow-through add-on, day-3 loss of SPY-relative "
            "follow-through plus negative post-add-on return identifies capital that "
            "should be trimmed from the add-on sleeve only."
        ),
        "alpha_category": "exit/capital_allocation",
        "change_type": "exit_lifecycle_rule",
        "single_causal_variable": "post_addon_day3_weakness_reduce_addon_shares",
        "parameters": VARIANT_CONFIG,
        "date_ranges": {
            name: {"start": spec["start"], "end": spec["end"]}
            for name, spec in WINDOWS.items()
        },
        "snapshots": {name: spec["snapshot"] for name, spec in WINDOWS.items()},
        "history_guardrails": {
            "not_llm_soft_ranking": True,
            "not_static_universe_expansion": True,
            "not_target_width": True,
            "not_sector_cap": True,
            "not_slot_ranking": True,
            "not_addon_cap_or_checkpoint_gate": True,
            "prior_support": "exp-20260505-025 observed post-add-on deterioration family",
            "why_not_simple_repeat": (
                "This tests post-add-on lifecycle de-risking after capital is added; "
                "it does not retune the accepted day-2 add-on trigger/cap."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_condition": (
                "If accepted, move the trigger into production_parity.py and surface "
                "the same fields in production position-action generation before commit."
            ),
        },
        "window_results": window_results,
        "aggregate": {
            "before_expected_value_score_sum": round(aggregate_before_ev, 6),
            "after_expected_value_score_sum": round(aggregate_after_ev, 6),
            "expected_value_score_delta": aggregate_ev_delta,
            "expected_value_score_delta_pct": aggregate_ev_delta_pct,
            "before_total_pnl_sum": round(aggregate_before_pnl, 2),
            "after_total_pnl_sum": round(aggregate_after_pnl, 2),
            "total_pnl_delta": aggregate_pnl_delta,
            "ev_improved_windows": ev_improved_windows,
            "pnl_improved_windows": pnl_improved_windows,
            "post_addon_weakness_reduce_events_executed": total_executed_events,
        },
        "gate_4_verdict": {
            "accepted": accepted,
            "decision": "accepted" if accepted else "rejected",
            "rejection_reason": None
            if accepted
            else (
                "Did not clear +10% aggregate EV with majority-window improvement "
                "and positive aggregate PnL."
            ),
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": OUTPUT.as_posix(),
        "accepted": accepted,
        "aggregate_ev_delta": aggregate_ev_delta,
        "aggregate_ev_delta_pct": aggregate_ev_delta_pct,
        "aggregate_pnl_delta": aggregate_pnl_delta,
        "ev_improved_windows": ev_improved_windows,
        "post_addon_weakness_reduce_events_executed": total_executed_events,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
