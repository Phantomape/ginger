"""exp-20260517-010: event rotation-surface revalidation after exp009.

Alpha search, replay-only. Revalidates the strongest current non-core alpha
direction after the latest accepted core allocation stack: the default-off
event bundle rotation_breakout_leadership paper-notional tilt.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260517_001_event_rotation_surface_current_lead_revalidation as prior


EXPERIMENT_ID = "exp-20260517-010"
EXPERIMENT_SLUG = "event_rotation_surface_after_exp009_revalidation"

REPO_ROOT = prior.REPO_ROOT
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


def _configure_modules() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior._configure_modules()


def _retag_after_exp009(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "post_exp009_event_rotation_surface_revalidation"
    payload["changed_variable"] = "rotation_breakout_leadership_paper_notional_tilt"
    payload["hypothesis"] = (
        "After exp-20260517-009 accepted a narrow core allocation improvement, "
        "the highest-value next alpha is still not another sparse ticker or LLM "
        "soft-ranking branch. Revalidate whether the default-off event bundle's "
        "rotation_breakout_leadership paper-notional tilt remains additive on "
        "top of the latest accepted core stack."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "The recent accepted core change was small and production-shared, "
            "while repeated event-surface runs have shown larger replacement "
            "value. This run keeps the core candidate set fixed and checks that "
            "the event rotation surface still improves all three standard "
            "windows after exp009."
        ),
    }
    history = dict(payload.get("historical_experiment_check") or {})
    history["exp-20260517-001"] = (
        "The same default-off event rotation surface passed before exp009; this "
        "run checks that it remains positive after the latest accepted core "
        "allocation change."
    )
    history["exp-20260517-008"] = (
        "Broad ample-slot rank-1 top-up was rejected because old_thin commodity "
        "single-trade concentration outweighed late-window gains."
    )
    history["exp-20260517-009"] = (
        "Stock-only ample-slot rank-1 top-up was accepted as a small "
        "production-shared core allocation improvement; it is the current "
        "accepted core checkpoint for this revalidation."
    )
    payload["historical_experiment_check"] = history
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "default-off event allocation: rotation_breakout_leadership rows "
            "remain the strongest current event-quality alpha after exp009."
        ),
        "2_history_check": (
            "exp013, exp028, exp040, exp044, and exp001 passed for the same "
            "all-source rotation surface; exp030 rejected only a sparse "
            "source-specific split. exp009 changed the accepted core stack, so "
            "current-stack revalidation is required."
        ),
        "3_single_causal_variable": (
            "rotation_breakout_leadership scalar above the current 2.0x "
            "non-generic positive event-surface paper add-on."
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; compare current paper lead "
            "versus candidate, require aggregate EV/PnL improvement, no "
            "EV-regressed windows, and sample guard pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260517_010_event_rotation_surface_after_exp009_revalidation.py"
        ),
    }
    params = dict(payload.get("parameters") or {})
    params["accepted_core_checkpoint"] = "exp-20260517-009"
    params["latest_core_scouts_checked"] = ["exp-20260517-008", "exp-20260517-009"]
    params["anti_js"] = "No JavaScript was used."
    payload["parameters"] = params
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
        "shared_default_off_paper_policy_present": True,
        "shared_paper_policy_file": "quant/event_sleeve_bundle.py",
        "production_consistency_note": (
            "The default-off paper attribution path already uses the shared "
            "event_sleeve_bundle rotation-tilt config. This experiment does not "
            "enable live/default orders; trade plans remain blocked by explicit "
            "enablement and forward-paper gates."
        ),
        "promotion_blocker_if_positive": (
            "Live/default capital still requires closed forward replacement-value "
            "evidence and an explicit trade-enabled adapter configuration."
        ),
    }
    payload["why_not_other_attractive_points"] = (
        "LLM/SEC soft-ranking remains PIT-attribution limited, candidate-pool "
        "expansion has recently added noise, and nearby core allocation scouts "
        "only found small or concentrated effects. The event rotation surface is "
        "the cleanest repeated alpha with a production-shared default-off path."
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
    current = payload["before_metrics"][prior._parent().CURRENT_LEAD_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Rotation-Surface Revalidation After Exp009",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Revalidates whether "
            "`rotation_breakout_leadership` event rows still deserve higher "
            "bounded paper notional than the current 2.0x non-generic positive "
            "event-surface add-on after the accepted exp009 core allocation "
            "change."
        ),
        "",
        "## Best Variant Vs Current Lead",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior._parent().base.WINDOWS:
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
            "## Production Impact",
            "",
            (
                "Replay only. The default-off paper path is shared in "
                "`quant/event_sleeve_bundle.py`, and this run does not enable "
                "live/default orders. A live-capital version still needs closed "
                "forward replacement-value evidence and explicit enablement."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    _configure_modules()
    prior._artifact_markdown = _artifact_markdown
    payload = prior.exp044.exp040.exp028.base.prior._retag_payload(prior._parent().build_payload())
    payload = prior.exp044.exp040.exp028.base._finalize_payload(payload)
    payload = prior._retag_current_lead(payload)
    payload = _retag_after_exp009(payload)
    prior.persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            prior._parent()._safe(
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
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
