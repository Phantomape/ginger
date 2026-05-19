"""exp-20260516-001: core-confirmed-quality scarce-slot priority.

Tests one routing variable on the accepted core stack: when same-day candidates
survive all gates but available entry slots are scarce, keep the existing
production entry-planning rules and prefer candidates already tagged with the
accepted core-confirmed-quality state.

This is not a broad ranking retune, filter, sizing scalar, exit change,
candidate-pool expansion, LLM/news change, or Space/event-sleeve change.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260512_106_signal_day_sector_tape_risk as base
import production_parity


EXPERIMENT_ID = "exp-20260516-002"
EXPERIMENT_SLUG = "core_confirmed_slot_priority"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

ROUTING_EVENTS: list[dict[str, Any]] = []


def _signal_key(sig: dict[str, Any]) -> str:
    return "|".join(
        [
            str(sig.get("ticker") or ""),
            str(sig.get("strategy") or ""),
            str(sig.get("sector") or ""),
            str(round(float(sig.get("entry_price") or 0.0), 4)),
            str(round(float(sig.get("trade_quality_score") or 0.0), 4)),
        ]
    )


def _signal_summary(sig: dict[str, Any]) -> dict[str, Any]:
    sizing = sig.get("sizing") or {}
    return {
        "ticker": sig.get("ticker"),
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "entry_price": base._round(sig.get("entry_price")),
        "trade_quality_score": base._round(sig.get("trade_quality_score")),
        "confidence_score": base._round(sig.get("confidence_score")),
        "core_confirmed_quality_state": bool(sig.get("core_confirmed_quality_state")),
        "rs20_entry_state_leader": bool(sig.get("rs20_entry_state_leader")),
        "signal_day_ticker_green_candle": bool(sig.get("signal_day_ticker_green_candle")),
        "shares_to_buy": sizing.get("shares_to_buy"),
        "risk_pct": base._round(sizing.get("risk_pct")),
    }


def _prioritize_core_confirmed(planned: list[dict[str, Any]], slots: int) -> list[dict[str, Any]]:
    if slots <= 0 or len(planned) <= slots:
        return planned
    indexed = list(enumerate(planned))
    prioritized = [
        sig
        for _, sig in sorted(
            indexed,
            key=lambda item: (
                0 if item[1].get("core_confirmed_quality_state") else 1,
                item[0],
            ),
        )
    ]
    before_selected = planned[:slots]
    after_selected = prioritized[:slots]
    before_keys = {_signal_key(sig) for sig in before_selected}
    after_keys = {_signal_key(sig) for sig in after_selected}
    promoted = [
        _signal_summary(sig)
        for sig in after_selected
        if _signal_key(sig) not in before_keys and sig.get("core_confirmed_quality_state")
    ]
    demoted = [
        _signal_summary(sig)
        for sig in before_selected
        if _signal_key(sig) not in after_keys
    ]
    if promoted or demoted:
        ROUTING_EVENTS.append(
            {
                "available_slots": slots,
                "signals_after_deferral": len(planned),
                "selected_before": [_signal_summary(sig) for sig in before_selected],
                "selected_after": [_signal_summary(sig) for sig in after_selected],
                "promoted_core_confirmed": promoted,
                "demoted_candidates": demoted,
            }
        )
    return prioritized


def _core_confirmed_priority_plan(
    signals,
    open_positions,
    market_context=None,
    max_positions=base.backtester_module.MAX_POSITIONS,
    defer_breakout_when_slots_lte=base.backtester_module.DEFER_BREAKOUT_WHEN_SLOTS_LTE,
    defer_breakout_max_min_index_pct_from_ma=(
        base.backtester_module.DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA
    ),
    active_positions_count=None,
):
    """Mirror production_parity.plan_entry_candidates with one priority hook."""
    market_context = market_context or {}
    input_signals = list(signals or [])
    active_positions = (
        int(active_positions_count)
        if active_positions_count is not None
        else len(production_parity._positive_positions(open_positions))
    )
    slots = max(0, max_positions - active_positions)

    planned = list(input_signals)
    deferred_breakouts = []
    min_index_pct_from_ma = None
    state_ok = True
    if defer_breakout_max_min_index_pct_from_ma is not None:
        spy_pct = market_context.get("spy_pct_from_ma")
        qqq_pct = market_context.get("qqq_pct_from_ma")
        if spy_pct is not None and qqq_pct is not None:
            min_index_pct_from_ma = min(spy_pct, qqq_pct)
            state_ok = min_index_pct_from_ma <= defer_breakout_max_min_index_pct_from_ma
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

    signals_after_deferral = len(planned)
    prioritized = _prioritize_core_confirmed(planned, slots)
    slot_sliced = prioritized[slots:] if slots >= 0 else prioritized
    planned = prioritized[:slots]

    return planned, {
        "active_positions": active_positions,
        "max_positions": max_positions,
        "available_slots": slots,
        "signals_before_entry_plan": len(input_signals),
        "signals_after_deferral": signals_after_deferral,
        "signals_after_entry_plan": len(planned),
        "deferred_breakout_signals": deferred_breakouts,
        "slot_sliced_signals": slot_sliced,
        "defer_breakout_when_slots_lte": defer_breakout_when_slots_lte,
        "defer_breakout_max_min_index_pct_from_ma": (
            defer_breakout_max_min_index_pct_from_ma
        ),
        "min_index_pct_from_ma": min_index_pct_from_ma,
        "core_confirmed_quality_slot_priority": {
            "enabled": True,
            "only_when_slots_scarce": True,
            "priority_field": "core_confirmed_quality_state",
        },
    }


def _run_window(label: str, *, variant: bool) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    universe = base.get_universe()
    original_plan = base.backtester_module.plan_entry_candidates
    global ROUTING_EVENTS
    ROUTING_EVENTS = []

    if variant:
        base.backtester_module.plan_entry_candidates = _core_confirmed_priority_plan

    try:
        engine = base.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    finally:
        base.backtester_module.plan_entry_candidates = original_plan

    if result.get("error"):
        raise RuntimeError(f"{label} {'variant' if variant else 'baseline'} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "routing_events": list(ROUTING_EVENTS),
    }


def _changed_trades(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    return base._changed_trades(before, after)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Routing events |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {events} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                events=len(payload["routing_events"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core-Confirmed Slot Priority",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: when survived core candidates are slot-sliced, sort the same-day post-deferral candidate list so `core_confirmed_quality_state=True` candidates fill scarce slots first. No entry filter, sizing scalar, exit, candidate pool, LLM/news, or event-sleeve behavior changed.",
            "",
            *rows,
            "",
            "Production impact: replay-only scout. Positive promotion requires moving the same priority hook into shared `production_parity.plan_entry_candidates`, which both `backtester.py` and `run.py` already call, plus focused parity coverage.",
        ]
    )


def run() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    routing_events: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}

    for label in base.WINDOWS:
        baseline = _run_window(label, variant=False)
        variant = _run_window(label, variant=True)
        before_metrics[label] = baseline["metrics"]
        after_metrics[label] = variant["metrics"]
        routing_events[label] = variant["routing_events"]
        changed_trades[label] = _changed_trades(baseline["trades"], variant["trades"])

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
        if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
    ]
    routing_event_count = sum(len(rows) for rows in routing_events.values())
    promoted_count = sum(
        len(event.get("promoted_core_confirmed") or [])
        for rows in routing_events.values()
        for event in rows
    )
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    drawdown_guardrail_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and promoted_count > 0
        and drawdown_guardrail_passed
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_core_confirmed_slot_priority"
    )
    interpretation = (
        "Core-confirmed-quality scarce-slot priority improved the accepted core stack and should be promoted through shared production_parity with parity tests."
        if passed
        else "Core-confirmed-quality scarce-slot priority did not clear the canonical three-window gate; keep current slot routing."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted core-confirmed-quality state should not only receive a sizing top-up; "
            "when survived candidates compete for scarce same-day slots, routing those slots to "
            "core-confirmed candidates may improve fixed-candidate capital allocation without "
            "broad ranking or filtering."
        ),
        "change_type": "candidate_routing_shadow",
        "changed_variable": "core_confirmed_quality_slot_priority",
        "single_causal_variable": (
            "scarce-slot priority for candidates with core_confirmed_quality_state=True"
        ),
        "parameters": {
            "priority_field": "core_confirmed_quality_state",
            "priority_scope": "only after existing entry deferral and only when candidates exceed available core slots",
            "locked_variables": [
                "core universe",
                "signal generation",
                "entry filters",
                "breakout deferral semantics",
                "candidate sizing",
                "position caps",
                "portfolio heat",
                "stop and target logic",
                "follow-through add-ons",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": "fixed-candidate scarce-slot routing using the accepted core-confirmed-quality state",
            "2_history_check": {
                "exp-20260503-010": "global RS/TQS slot ranking failed; its next valid retry was a narrower same-day slot-sliced collision class.",
                "exp-20260515-028": "core-confirmed-quality sizing at 1.075x improved all three canonical windows; this tests routing, not another scalar.",
                "recent_failed_branches": "R:R, close-location, reversal, sector-thrust, gap-absorption, Space interactions, and LLM/options soft-ranking were rejected or data-limited.",
            },
            "3_single_causal_variable": "one scarce-slot priority key: core_confirmed_quality_state",
            "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, nonzero promoted candidate count, and max drawdown drift <= 0.5 pp.",
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
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
                "risk_engine core_confirmed_quality_state",
                "production_parity plan_entry_candidates available_slots / slot_sliced_signals",
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
            "routing_event_count": routing_event_count,
            "promoted_core_confirmed_count": promoted_count,
            "max_drawdown_worse": base._round(max_drawdown_worse),
            "drawdown_guardrail_passed": drawdown_guardrail_passed,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "routing_events": routing_events,
        "changed_trades": changed_trades,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": "LLM/options soft-ranking lacks sufficient closed attribution; this deterministic routing state is replayable on fixed OHLCV snapshots.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": "If accepted, implement in shared production_parity.plan_entry_candidates and add parity tests before production use.",
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": None
        if passed
        else "Do not retry broad slot ranking; a valid retry needs a different narrow collision state or forward slot-sliced attribution.",
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    artifact_path = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
    log_path = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = base.REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


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
                "routing_event_count": result["gate4"]["routing_event_count"],
                "promoted_core_confirmed_count": result["gate4"]["promoted_core_confirmed_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
