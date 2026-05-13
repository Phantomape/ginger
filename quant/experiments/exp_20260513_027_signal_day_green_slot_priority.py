"""exp-20260513-027: signal-day green slot-priority scout.

Tests one production-visible ranking variable on the accepted core stack:
when same-day entry candidates compete for finite slots, prioritize candidates
whose own signal-day candle is green before slot slicing. This changes only the
slot-allocation order after existing entry filters, sizing, and scarce-slot
breakout deferral. It does not change entry rules, filters, sizing, exits,
targets, universe, LLM, news, or add-ons.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260513-027"
EXPERIMENT_SLUG = "signal_day_green_slot_priority"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = Path(__file__).resolve().parent
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import backtester as backtester_module  # noqa: E402
import production_parity  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import exp_20260512_106_signal_day_sector_tape_risk as base  # noqa: E402


SLOT_PRIORITY_AUDIT: list[dict[str, Any]] = []
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _positive_positions(open_positions: Any) -> list[dict[str, Any]]:
    return [
        p
        for p in (open_positions or {}).get("positions", [])
        if p.get("ticker") and (p.get("shares") or 0) > 0
    ]


def _core_signal_snapshot(sig: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "confidence_score": sig.get("confidence_score"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "signal_day_ticker_green_candle": sig.get("signal_day_ticker_green_candle"),
        "signal_day_ticker_open_close_return_pct": sig.get(
            "signal_day_ticker_open_close_return_pct"
        ),
        "shares_to_buy": (sig.get("sizing") or {}).get("shares_to_buy"),
        "entry_price": sig.get("entry_price"),
        "stop_price": sig.get("stop_price"),
        "target_price": sig.get("target_price"),
    }


def _make_green_slot_priority_plan(
    original: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
) -> Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        open_positions: dict[str, Any] | None,
        market_context: dict[str, Any] | None = None,
        max_positions: int = production_parity.MAX_POSITIONS,
        defer_breakout_when_slots_lte: int | None = production_parity.DEFER_BREAKOUT_WHEN_SLOTS_LTE,
        defer_breakout_max_min_index_pct_from_ma: float | None = production_parity.DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
        active_positions_count: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        market_context = market_context or {}
        input_signals = list(signals or [])
        active_positions = (
            int(active_positions_count)
            if active_positions_count is not None
            else len(_positive_positions(open_positions))
        )
        slots = max(0, max_positions - active_positions)

        planned = list(input_signals)
        deferred_breakouts: list[dict[str, Any]] = []
        min_index_pct_from_ma = None
        state_ok = True
        if defer_breakout_max_min_index_pct_from_ma is not None:
            spy_pct = market_context.get("spy_pct_from_ma")
            qqq_pct = market_context.get("qqq_pct_from_ma")
            if spy_pct is not None and qqq_pct is not None:
                min_index_pct_from_ma = min(spy_pct, qqq_pct)
                state_ok = (
                    min_index_pct_from_ma <= defer_breakout_max_min_index_pct_from_ma
                )
            else:
                state_ok = False

        if (
            defer_breakout_when_slots_lte is not None
            and slots <= defer_breakout_when_slots_lte
            and state_ok
        ):
            kept = []
            for sig in planned:
                if sig.get("strategy") == "breakout_long":
                    deferred_breakouts.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector", "Unknown"),
                            "available_slots": slots,
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "confidence_score": sig.get("confidence_score"),
                            "pct_from_52w_high": sig.get("pct_from_52w_high"),
                            "entry_price": sig.get("entry_price"),
                            "stop_price": sig.get("stop_price"),
                            "target_price": sig.get("target_price"),
                            "min_index_pct_from_ma": min_index_pct_from_ma,
                        }
                    )
                else:
                    kept.append(sig)
            planned = kept

        before_priority = list(planned)
        indexed = list(enumerate(planned))
        indexed.sort(
            key=lambda row: (
                1
                if row[1].get("signal_day_ticker_green_candle") is True
                else 0,
                -row[0],
            ),
            reverse=True,
        )
        planned = [sig for _, sig in indexed]
        signals_after_deferral = len(planned)
        slot_sliced = planned[slots:] if slots >= 0 else planned
        selected = planned[:slots]

        if len(before_priority) > slots and before_priority != planned:
            SLOT_PRIORITY_AUDIT.append(
                {
                    "available_slots": slots,
                    "signals_after_deferral": signals_after_deferral,
                    "before_order": [
                        _core_signal_snapshot(sig) for sig in before_priority
                    ],
                    "after_order": [_core_signal_snapshot(sig) for sig in planned],
                    "selected_after_priority": [
                        _core_signal_snapshot(sig) for sig in selected
                    ],
                    "slot_sliced_after_priority": [
                        _core_signal_snapshot(sig) for sig in slot_sliced
                    ],
                }
            )

        return selected, {
            "active_positions": active_positions,
            "max_positions": max_positions,
            "available_slots": slots,
            "signals_before_entry_plan": len(input_signals),
            "signals_after_deferral": signals_after_deferral,
            "signals_after_entry_plan": len(selected),
            "deferred_breakout_signals": deferred_breakouts,
            "slot_sliced_signals": slot_sliced,
            "defer_breakout_when_slots_lte": defer_breakout_when_slots_lte,
            "defer_breakout_max_min_index_pct_from_ma": (
                defer_breakout_max_min_index_pct_from_ma
            ),
            "min_index_pct_from_ma": min_index_pct_from_ma,
            "signal_day_green_slot_priority_enabled": True,
        }

    return wrapped


def _run_window(label: str, *, variant: bool) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = get_universe()
    original_plan = backtester_module.plan_entry_candidates

    global SLOT_PRIORITY_AUDIT
    SLOT_PRIORITY_AUDIT = []

    if variant:
        backtester_module.plan_entry_candidates = _make_green_slot_priority_plan(
            original_plan
        )
    try:
        result = BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        ).run()
    finally:
        backtester_module.plan_entry_candidates = original_plan

    if result.get("error"):
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "entry_execution_attribution": result.get("entry_execution_attribution") or {},
        "slot_priority_audit": list(SLOT_PRIORITY_AUDIT),
    }


def _priority_summary(audit_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {"by_window": {}, "total_reordered_days": 0}
    for label, rows in audit_by_window.items():
        selected_green = 0
        sliced_green = 0
        for row in rows:
            selected_green += sum(
                1
                for sig in row.get("selected_after_priority", [])
                if sig.get("signal_day_ticker_green_candle") is True
            )
            sliced_green += sum(
                1
                for sig in row.get("slot_sliced_after_priority", [])
                if sig.get("signal_day_ticker_green_candle") is True
            )
        out["by_window"][label] = {
            "reordered_days": len(rows),
            "selected_green_after_priority": selected_green,
            "sliced_green_after_priority": sliced_green,
        }
        out["total_reordered_days"] += len(rows)
    return out


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Trades | Reordered days |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        priority = payload["priority_summary"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {trades} | {reordered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                trades=after["trade_count"],
                reordered=priority["reordered_days"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Signal-Day Green Slot Priority",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: when entry candidates compete for finite same-day slots, prioritize already-qualified signals whose own signal-day candle is green before slot slicing. Existing scarce-slot breakout deferral, entry filters, sizing, exits, universe, LLM/news, and add-ons are unchanged.",
            "",
            *rows,
            "",
            "Production impact: replay-only scout. A positive result would require changing the shared `production_parity.plan_entry_candidates` helper and adding parity tests because both `backtester.py` and `run.py` call that helper.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {label: _run_window(label, variant=False) for label in base.WINDOWS}
    after_runs = {label: _run_window(label, variant=True) for label in base.WINDOWS}

    before_metrics = {label: row["metrics"] for label, row in before_runs.items()}
    after_metrics = {label: row["metrics"] for label, row in after_runs.items()}
    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in by_window_delta.values()
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    priority_audit = {
        label: after_runs[label]["slot_priority_audit"] for label in base.WINDOWS
    }
    priority_summary = _priority_summary(priority_audit)
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and drawdown_guardrail_passed
        and priority_summary["total_reordered_days"] > 0
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_signal_day_green_slot_priority"
    )
    interpretation = (
        "Signal-day green slot priority cleared the canonical three-window gate and requires shared plan-entry implementation before production use."
        if passed
        else "Signal-day green slot priority did not clear the canonical three-window gate; do not promote this ranking variable on the frozen windows."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted own-green signal-day state may have replacement value during same-day slot collisions: when finite slots force slicing, prioritize green-confirmed candidates instead of increasing broad risk."
        ),
        "change_type": "entry_ranking_scout",
        "changed_variable": "signal_day_green_slot_priority",
        "single_causal_variable": (
            "same-day slot slicing order: signal_day_ticker_green_candle true candidates before non-green candidates after existing scarce-slot breakout deferral"
        ),
        "parameters": {
            "priority_key": "signal_day_ticker_green_candle desc, original order stable",
            "priority_scope": "post-sizing plan_entry_candidates before slot slicing",
            "locked_variables": [
                "core universe",
                "entry filters",
                "signal generation",
                "risk sizing",
                "scarce-slot breakout deferral",
                "stop and target logic",
                "portfolio heat",
                "LLM/news replay",
                "pilot/event sleeves",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking / capital allocation: own-green state may improve scarce-slot replacement value without adding risk."
            ),
            "2_history_check": {
                "exp-20260513-007": (
                    "own-green 1.05x sizing is accepted; this tests whether the same state has slot-replacement value, not another sizing scalar."
                ),
                "exp-20260511-004": (
                    "all-signal 52-week proximity ranking was rejected; this uses the accepted own-green state and only affects finite-slot slicing."
                ),
                "exp-20260505-018": (
                    "breakout RS/confidence subsequence ranking was rejected; this does not alter breakout subsequence ranking keys."
                ),
                "exp-20260513-023": (
                    "green momentum deceleration sizing failed drawdown guardrail; this avoids adding risk."
                ),
                "exp-20260513-024": (
                    "green gap-cushion sizing was positive but drawdown-fragile; this tests replacement priority instead of more shares."
                ),
                "llm_soft_ranking": (
                    "LLM ranking data remains thin, so this run uses deterministic replayable fields."
                ),
            },
            "3_single_causal_variable": "signal_day_green_slot_priority",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max drawdown drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260513_027_signal_day_green_slot_priority.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "risk_engine signal_day_ticker_green_candle",
                "production_parity plan_entry_candidates slot_sliced_signals",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": aggregate_delta["signals_generated_sum"],
            "signals_survived_delta": aggregate_delta["signals_survived_sum"],
            "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
            "total_reordered_days": priority_summary["total_reordered_days"],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "changed_trades": {
            label: base._changed_trades(before_runs[label]["trades"], after_runs[label]["trades"])
            for label in base.WINDOWS
        },
        "priority_summary": priority_summary,
        "priority_audit": priority_audit,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "positive_result_requires_shared_policy": True,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else (
            "Use a different production-visible replacement-value state; do not promote own-green slot priority without forward collision evidence."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_027_signal_day_green_slot_priority.py",
            "data/experiments/exp-20260513-027/signal_day_green_slot_priority.json",
            "docs/experiments/logs/exp-20260513-027.json",
            "docs/experiments/tickets/exp-20260513-027.json",
            "docs/experiments/artifacts/exp-20260513-027_signal_day_green_slot_priority.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    base._upsert_jsonl(REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "max_drawdown_worse": result["gate4"]["max_drawdown_worse"],
                "total_reordered_days": result["gate4"]["total_reordered_days"],
                "priority_summary": result["priority_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
