"""exp-20260516-040: event rotation-surface tilt after exp039.

Alpha search, replay-only. Revalidates the strongest deterministic event-bundle
paper allocation refinement after the accepted exp-20260516-039 core stack. The
only changed variable is the bounded `rotation_breakout_leadership` paper
notional tilt above the current 2.0x non-generic positive event-surface lead.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260516_028_event_rotation_surface_tilt_after_exp020 as exp028


EXPERIMENT_ID = "exp-20260516-040"
EXPERIMENT_SLUG = "event_rotation_surface_tilt_after_exp039"

REPO_ROOT = exp028.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _parent():
    return exp028.base.prior.parent


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    exp028.EXPERIMENT_ID = EXPERIMENT_ID
    exp028.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    exp028.OUT_JSON = OUT_JSON
    exp028.LOG_JSON = LOG_JSON
    exp028.TICKET_JSON = TICKET_JSON
    exp028.ARTIFACT_MD = ARTIFACT_MD
    exp028.EXPERIMENT_LOG = EXPERIMENT_LOG
    exp028._configure_modules()


def _retag_after_exp039(payload: dict[str, Any]) -> dict[str, Any]:
    payload = exp028._retag_after_exp020(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "post_exp039_event_rotation_surface_tilt_revalidation"
    payload["changed_variable"] = "rotation_breakout_leadership_paper_notional_tilt"
    payload["hypothesis"] = (
        "After the accepted exp-20260516-039 TSM core-risk adaptation, the "
        "strongest available non-core alpha family is still the default-off "
        "event bundle. Within that paper sleeve, rotation_breakout_leadership "
        "events may retain superior replacement quality and deserve a bounded "
        "extra paper-notional tilt."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "The playbook points away from LLM/SEC soft-ranking when attribution "
            "fields are thin and away from nearby core scalar retunes after the "
            "recent accepted exp039 change. This run keeps the fixed core "
            "candidate set, avoids noisy universe expansion, and revalidates the "
            "best deterministic default-off event allocation state on the latest "
            "accepted core baseline."
        ),
    }
    history = dict(payload.get("historical_experiment_check") or {})
    history["exp-20260516-013"] = (
        "The same rotation surface cleared the paper-only gate after exp009."
    )
    history["exp-20260516-028"] = (
        "The same rotation surface cleared the paper-only gate after exp020; "
        "this run checks portability after the later exp039 TSM core-risk "
        "promotion."
    )
    history["exp-20260516-030"] = (
        "A source-specific negative-reaction tilt inside the accepted rotation "
        "surface was rejected because the source sample/concentration guard was "
        "too thin; this run does not split by source."
    )
    history["exp-20260516-039"] = (
        "Accepted TSM core-risk adaptation moved the latest core stack to "
        "aggregate EV 7.7836, so the default-off event allocation evidence "
        "needs revalidation rather than inherited acceptance."
    )
    history["recent_avoided_branches"] = (
        "Skipped LLM soft-ranking, SEC semantic source tilts, FINRA crowding, "
        "Space nearby interactions, ATR expansion, RS/RS60 retunes, DTE scalars, "
        "and broad candidate-pool expansion because recent logs mark those "
        "branches blocked, sample-limited, noisy, or rejected."
    )
    payload["historical_experiment_check"] = history
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "default-off event allocation: rotation_breakout_leadership rows "
            "retain superior replacement value after the exp039 core stack."
        ),
        "2_history_check": (
            "exp013 and exp028 passed for the same all-source rotation surface; "
            "exp030 rejected only a source-specific split. exp039 later changed "
            "the accepted core baseline, while recent LLM/FINRA/Space/ATR "
            "branches are blocked or rejected."
        ),
        "3_single_causal_variable": (
            "rotation_breakout_leadership scalar above the current 2.0x "
            "non-generic positive event-surface paper add-on."
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; compare current paper lead "
            "versus candidate, require aggregate EV/PnL improvement, at least "
            "two EV-improved windows, no EV-regressed windows, and sample guard "
            "pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260516_040_event_rotation_surface_tilt_after_exp039.py"
        ),
    }
    params = dict(payload.get("parameters") or {})
    params["accepted_core_checkpoint"] = "exp-20260516-039"
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
        "promotion_blocker_if_positive": (
            "Before live/default capital, enable a shared trade adapter used by "
            "both run.py and backtester.py, add parity tests, and collect closed "
            "forward replacement-value evidence."
        ),
    }
    payload["gate1"] = {
        "baseline_name": _parent().CURRENT_LEAD_VARIANT,
        "baseline_metrics": payload["before_metrics"][_parent().CURRENT_LEAD_VARIANT],
    }
    payload["gate2"] = {
        "required_fields": [
            "event source",
            "ticker",
            "entry_date",
            "exit_date",
            "pnl",
            "state_feature_available",
            "state_score_positive",
            "state_surface",
        ],
        "selection": payload["selection"],
        "passed": bool(
            (payload["selection"].get("rotation_surface_trade_count") or 0) >= 6
            and (payload["selection"].get("rotation_surface_windows_present") or 0) >= 2
        ),
    }
    best = payload["best_variant"]
    best_gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    payload["gate3"] = {
        "new_filter_added": False,
        "candidate_pool_changed": False,
        "survival_impact": (
            "not applicable to default-off event paper overlay; core signals "
            "and survival are unchanged"
        ),
        "passed": True,
    }
    payload["gate4"] = {
        **best_gate,
        "basis": (
            "Three canonical docs/backtesting.md windows, primary comparison "
            "against the current 2.0x non-generic positive event paper lead."
        ),
    }
    payload["why_not_other_attractive_points"] = (
        "Avoided LLM/SEC soft-ranking because fields and attribution remain "
        "insufficient; avoided FINRA crowding because borrow/float fields are "
        "missing and recent samples were thin; avoided Space nearby retunes "
        "because recent positives are default-off and interaction-sensitive; "
        "avoided broad candidate-pool expansion because recent pools added "
        "old-window noise; avoided nearby core scalar retunes after exp039 "
        "because the recent log marks them rejected or exhausted."
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
    current = payload["before_metrics"][_parent().CURRENT_LEAD_VARIANT]
    after = payload["after_metrics"][best]

    lines = [
        f"# {EXPERIMENT_ID} Event Rotation-Surface Tilt After Exp039",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether "
            "`rotation_breakout_leadership` event rows still deserve higher "
            "bounded paper notional than the current 2.0x non-generic positive "
            "event-surface add-on after the accepted exp-20260516-039 core stack."
        ),
        "",
        "## Best Variant Vs Current Lead",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _parent().base.WINDOWS:
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
                "Replay only. Production and default backtest order paths are "
                "unchanged. A positive live-capital version still requires a "
                "shared trade-enabled event adapter, run/backtester parity tests, "
                "and forward paper replacement-value evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _parent()._write_json(OUT_JSON, payload)
    compact = exp028.base.prior._compact_log(payload)
    compact["changed_variable"] = payload["changed_variable"]
    compact["gate1"] = payload["gate1"]
    compact["gate2"] = payload["gate2"]
    compact["gate3"] = payload["gate3"]
    compact["gate4"] = payload["gate4"]
    compact["total_pnl_delta"] = payload["gate4"]["delta"]["aggregate_pnl_delta"]
    _parent()._write_json(LOG_JSON, compact)
    _parent()._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation-surface tilt after exp039",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["gate4"]["delta"]["aggregate_pnl_delta"],
            "next_action": payload["next_action"],
        },
    )
    _parent()._write_text(ARTIFACT_MD, _artifact_markdown(payload))

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
    lines.append(json.dumps(_parent()._safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    _configure_modules()
    payload = exp028.base.prior._retag_payload(_parent().build_payload())
    payload = exp028.base._finalize_payload(payload)
    payload = _retag_after_exp039(payload)
    persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            _parent()._safe(
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
