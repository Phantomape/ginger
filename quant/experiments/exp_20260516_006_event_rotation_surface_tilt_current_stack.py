"""exp-20260516-006: current-stack event rotation-surface tilt replay.

Alpha search, replay-only. Revalidates the strongest event-bundle paper
allocation refinement after the accepted 2026-05-15 core stack: keep the full
default-off event bundle and current non-generic positive state-surface add-on
fixed, and test only whether `rotation_breakout_leadership` event rows still
deserve extra bounded paper notional.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260510_001_event_rotation_surface_tilt as parent


EXPERIMENT_ID = "exp-20260516-006"
EXPERIMENT_SLUG = "event_rotation_surface_tilt_current_stack"

REPO_ROOT = parent.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "current_stack_event_rotation_surface_tilt_revalidation"
    payload["hypothesis"] = (
        "After the accepted exp-20260515-028 core sizing stack, the strongest "
        "available alpha family is still the default-off event bundle. Within "
        "that paper sleeve, rotation-breakout leadership events may retain "
        "better replacement-quality than other positive non-generic event "
        "surfaces and deserve a bounded extra paper-notional tilt."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "Recent core SPY-excess, close-location, R:R, green-momentum, "
            "candidate-pool, Space, and SEC semantic branches are rejected, "
            "sample-limited, or field-blocked. This run revalidates the prior "
            "strongest replay-positive event-allocation state on the current "
            "accepted core stack without changing production orders."
        ),
    }
    payload["historical_experiment_check"] = {
        "exp-20260509-006": (
            "Current-stack event bundle improved all three canonical windows "
            "and became the strongest paper-only alpha direction at that time."
        ),
        "exp-20260509-007": (
            "Non-generic positive state-surface add-on beat the full event "
            "bundle across all three windows."
        ),
        "exp-20260510-001": (
            "Rotation-breakout leadership tilt beat the non-generic add-on "
            "lead across all three windows on the prior core stack."
        ),
        "exp-20260515-028": (
            "Accepted core confirmed-quality sizing changed the core baseline; "
            "event tilt must be revalidated rather than assumed portable."
        ),
        "recent_rejected_or_blocked_branches": {
            "signal_day_spy_excess": (
                "exp-20260513-010/011 already rejected simple SPY "
                "outperformance/excess-margin top-ups."
            ),
            "gap_vulnerability": (
                "Earlier global, sector-pocket, and cushion variants already "
                "exist; current production contains gap-vulnerability rules."
            ),
            "sec_semantics": (
                "exp-20260516-003 found no usable same-accession directional "
                "rows for the fresh SEC branch."
            ),
            "green_deceleration": (
                "exp-20260516-004 was rejected on old_thin and drawdown."
            ),
            "space_pool": (
                "exp-20260516-005 and recent VSAT/Space breadth runs remain "
                "sample-limited or old-window fragile."
            ),
        },
    }
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "event-bundle paper allocation: rotation_breakout_leadership rows "
            "retain superior event-quality/replacement signal on the current "
            "accepted core stack."
        ),
        "2_history_check": (
            "The same surface was promising in exp-20260510-001, but the core "
            "baseline has changed since exp-20260515-028; nearby core branches "
            "were rejected or blocked as listed in historical_experiment_check."
        ),
        "3_single_causal_variable": (
            "rotation_breakout_leadership scalar above the current 2.0x "
            "non-generic positive event-surface paper add-on."
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; compare current lead vs "
            "candidate, require majority EV improvement, zero EV regression, "
            "material aggregate EV/PnL lift, and sample guard pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260516_006_event_rotation_surface_tilt_current_stack.py"
        ),
    }
    payload["backtest_protocol"] = {
        "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
        "windows": parent.base.WINDOWS,
        "config": {
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
            "event_overlay": "default_off_paper_replay",
        },
    }
    payload["parameters"] = dict(payload.get("parameters") or {})
    payload["parameters"]["anti_js"] = "No JavaScript was used."
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "promotion_blocker_if_positive": (
            "Before live/default capital, implement a shared trade-enabled "
            "event adapter used by run.py and backtester.py, add parity tests, "
            "and collect closed forward replacement-value evidence."
        ),
    }
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_role_changed": False,
        "blocker_relation": (
            "LLM soft-ranking remains attribution/sample-limited, so this run "
            "uses deterministic PIT event/state fields only."
        ),
    }
    payload["why_not_other_attractive_points"] = (
        "Skipped SEC semantic tuning, LLM soft-ranking, Space ticker/pool "
        "breadth, simple SPY-excess, gap-vulnerability, close-location, R:R, "
        "and green momentum variants because recent logs mark those branches "
        "rejected, sample-limited, or field-blocked."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    current = payload["before_metrics"][parent.CURRENT_LEAD_VARIANT]
    after = payload["after_metrics"][best]

    lines = [
        f"# {EXPERIMENT_ID} Event Rotation-Surface Tilt Current Stack",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Revalidates whether "
            "`rotation_breakout_leadership` event rows deserve a higher bounded "
            "paper notional than the current 2.0x non-generic positive "
            "event-surface add-on after the accepted exp-20260515-028 core stack."
        ),
        "",
        "## Best Variant Vs Current Lead",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent.base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {cev:.4f} | {aev:.4f} | {dev:+.4f} | ${cpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                cev=current[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                cpnl=current[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate Gate",
            "",
            "- EV delta vs current lead: {:+.4f} ({:+.2%})".format(
                gate["delta"]["aggregate_ev_delta"],
                gate["delta"]["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- PnL delta vs current lead: ${:+,.2f} ({:+.2%})".format(
                gate["delta"]["aggregate_pnl_delta"],
                gate["delta"]["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- EV windows improved/regressed: {}/{}".format(
                gate["delta"]["windows_ev_improved"],
                gate["delta"]["windows_ev_regressed"],
            ),
            "- Sample guard passed: `{}`".format(gate["sample_guard_passed"]),
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"] or "",
            "",
            "## Production Impact",
            "",
            (
                "Replay only. Production and default backtest order paths are unchanged. "
                "A positive live-capital version still requires a shared trade-enabled "
                "event adapter, run/backtester parity tests, and forward paper "
                "replacement-value evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "parameters": payload["parameters"],
        "gate_questions": payload["gate_questions"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "best_variant": best,
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "selection": payload["selection"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
        "related_files": payload["related_files"],
    }


def persist(payload: dict[str, Any]) -> None:
    parent._write_json(OUT_JSON, payload)
    parent._write_json(LOG_JSON, payload)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation-surface tilt current stack",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "next_action": payload["next_action"],
        },
    )
    parent._write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(parent._safe(_compact_log(payload)), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _retag_payload(parent.build_payload())
    persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            parent._safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "ev_delta_vs_current": gate["delta"]["aggregate_ev_delta"],
                    "pnl_delta_vs_current": gate["delta"]["aggregate_pnl_delta"],
                    "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                    "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                    "sample_guard_passed": gate["sample_guard_passed"],
                    "out_json": str(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
