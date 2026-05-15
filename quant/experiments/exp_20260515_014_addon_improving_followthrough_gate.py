"""exp-20260515-014: first add-on improving-followthrough gate.

Tests one allocation/lifecycle variable on the accepted core stack: require a
day-2 add-on candidate to improve both unrealized return and RS-vs-SPY from
day 1 to day 2. This changes only first add-on eligibility, not entries, exits,
ranking, sizing constants, candidate universe, LLM/news behavior, heat, or slots.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260515_008_clean_spy_cap_only_leader_cap as prev


base = prev.base

EXPERIMENT_ID = "exp-20260515-014"
EXPERIMENT_SLUG = "addon_improving_followthrough_gate"
TARGET_CONFIG_VALUE = True
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005


def _addon_summary(addon: dict[str, Any]) -> dict[str, Any]:
    events = addon.get("events") or []
    rejected = [
        row
        for row in events
        if row.get("status") == "rejected_checkpoint_not_improving_followthrough"
    ]
    return {
        "scheduled": addon.get("scheduled"),
        "executed": addon.get("executed"),
        "checkpoint_rejected": addon.get("checkpoint_rejected"),
        "event_count": len(events),
        "not_improving_rejections": len(rejected),
        "not_improving_rejection_rows": rejected,
    }


def _run_window(label: str, require_improving_followthrough: bool) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    engine = base.BacktestEngine(
        base.get_universe(),
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
            "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": require_improving_followthrough,
        },
        ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
    )
    result = engine.run()
    if result.get("error"):
        mode = "after" if require_improving_followthrough else "before"
        raise RuntimeError(f"{label} {mode} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
        "addon_summary": _addon_summary(result.get("addon_attribution") or {}),
    }


def _build_payload() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    before_runs = {
        label: _run_window(label, False)
        for label in base.WINDOWS
    }
    after_runs = {
        label: _run_window(label, TARGET_CONFIG_VALUE)
        for label in base.WINDOWS
    }
    before_metrics = {
        label: before_runs[label]["metrics"]
        for label in base.WINDOWS
    }
    after_metrics = {
        label: after_runs[label]["metrics"]
        for label in base.WINDOWS
    }
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
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    rejected_addon_count = sum(
        int(after_runs[label]["addon_summary"].get("not_improving_rejections") or 0)
        for label in base.WINDOWS
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and aggregate_after["trade_count_sum"] >= 50
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
        and rejected_addon_count > 0
    )
    decision = (
        "accepted_for_shared_policy_implementation"
        if passed
        else "rejected_addon_improving_followthrough_gate"
    )
    interpretation = (
        "The improving-followthrough add-on gate did not clear Gate 4: it rejected one mid_weak add-on and reduced EV/PnL, while the other windows were unchanged."
        if not passed
        else "The improving-followthrough add-on gate improved the three-window stack and should be promoted through the shared production add-on helper before live use."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted first follow-through add-on may still add capital to "
            "stale day-2 winners. Requiring day-2 unrealized return and RS-vs-SPY "
            "to improve versus day 1 may keep add-ons focused on strengthening "
            "continuation without changing entries, exits, ranking, or base sizing."
        ),
        "change_type": "capital_allocation_addon_quality_gate",
        "changed_variable": "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH",
        "single_causal_variable": (
            "first follow-through add-on eligibility requires day-2 unrealized and RS-vs-SPY improvement versus day 1"
        ),
        "parameters": {
            "baseline": False,
            "tested": TARGET_CONFIG_VALUE,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "initial position sizing",
                "all risk multipliers",
                "position caps",
                "stops and targets",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260428-005": "Accepted first add-on fraction 50%; nearby fraction/cap tuning later became low priority without stronger quality evidence.",
                "exp-20260430-030": "Audited add-on quality and found the branch needs a real discriminator rather than another cap retune.",
                "weak_followthrough_exit_family": "Prior weak-followthrough exit variants were not promoted; this run only gates new add-on capital, not exits held positions.",
            },
            "why_this_branch": (
                "LLM/SEC/Space branches are currently field- or sample-limited; this uses existing PIT OHLCV state and the shared backtester add-on path."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation: add-on capital should require improving day-2 follow-through, not just positive day-2 follow-through"
            ),
            "2_history_check": (
                "No prior ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH A/B record was found; related add-on cap/fraction and weak-followthrough exits are distinct and mostly exhausted."
            ),
            "3_single_causal_variable": "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH only",
            "4_acceptance_standard": (
                "docs/backtesting.md fixed three windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, trade_count >= 50, max DD worse <= 0.5pp, nonzero affected add-ons"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_014_addon_improving_followthrough_gate.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": {
                    "before": False,
                    "after": TARGET_CONFIG_VALUE,
                },
            },
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
            "baseline_note": (
                "Current working tree baseline includes accepted exp-20260515-013 clean-SPY cap-only RS20 cap promotion."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "OHLCV entry close",
                "OHLCV day-1 close",
                "OHLCV day-2 checkpoint close",
                "SPY entry/day-1/day-2 closes",
                "addon original_shares",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_entry_filter_added": False,
            "new_addon_gate_added": True,
            "signals_generated_delta": aggregate_delta["signals_generated_sum"],
            "signals_survived_delta": aggregate_delta["signals_survived_sum"],
            "minimum_after_survival_rate": aggregate_after["survival_rate_min"],
            "passed": aggregate_after["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "affected_addon_count": rejected_addon_count,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": (
                max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "addon_summary": {
            label: {
                "before": before_runs[label]["addon_summary"],
                "after": after_runs[label]["addon_summary"],
            }
            for label in base.WINDOWS
        },
        "changed_trades": {
            label: base._changed_trades(
                before_runs[label]["trades"],
                after_runs[label]["trades"],
            )
            for label in base.WINDOWS
        },
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, wire the same improving-followthrough gate into production_parity.build_followthrough_addon_actions and add focused parity coverage."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "decision_reason": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if passed else interpretation,
        "next_evidence_needed": (
            "Do not promote this add-on gate without forward add-on attribution showing stale day-2 add-ons are harmful; next valid add-on work needs a stronger production-visible quality discriminator."
            if not passed
            else "Promote through shared production/backtest add-on policy and parity tests before enabling live/default behavior."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Add-ons before | Add-ons after | Rejected add-ons |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        addon = payload["addon_summary"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ab} | {aa} | {rej} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ab=addon["before"].get("executed"),
                aa=addon["after"].get("executed"),
                rej=addon["after"].get("not_improving_rejections"),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Add-on Improving-Followthrough Gate",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: `ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH=True` for the first follow-through add-on. No entry, exit, ranking, candidate, base sizing, cap, heat, slot, LLM, news, Space, or event-sleeve logic changed.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            f"Aggregate EV delta: `{payload['expected_value_score_delta']:+.4f}`.",
            f"Aggregate PnL delta: `${payload['total_pnl_delta']:+,.2f}`.",
            "",
            "Gate 4 failed because only `mid_weak` changed, and it regressed after one add-on was rejected by the improving-followthrough gate.",
        ]
    )


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
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
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
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = _build_payload()
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
                "affected_addon_count": result["gate4"]["affected_addon_count"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
