"""exp-20260517-001: event rotation-surface current-lead revalidation.

Alpha search, replay-only. Revalidates the strongest current non-core alpha
direction after the latest nearby core scouts: the default-off event bundle
rotation_breakout_leadership paper-notional tilt.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260516_044_event_rotation_surface_tilt_after_exp042 as exp044


EXPERIMENT_ID = "exp-20260517-001"
EXPERIMENT_SLUG = "event_rotation_surface_current_lead_revalidation"

REPO_ROOT = exp044.REPO_ROOT
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
    return exp044._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    exp044.EXPERIMENT_ID = EXPERIMENT_ID
    exp044.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    exp044.OUT_JSON = OUT_JSON
    exp044.LOG_JSON = LOG_JSON
    exp044.TICKET_JSON = TICKET_JSON
    exp044.ARTIFACT_MD = ARTIFACT_MD
    exp044.EXPERIMENT_LOG = EXPERIMENT_LOG
    exp044._configure_modules()


def _retag_current_lead(payload: dict[str, Any]) -> dict[str, Any]:
    payload = exp044._retag_after_exp042(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "current_lead_event_rotation_surface_revalidation"
    payload["changed_variable"] = "rotation_breakout_leadership_paper_notional_tilt"
    payload["hypothesis"] = (
        "Recent logs make LLM soft-ranking, SEC cash-flow semantics, candidate-pool "
        "expansion, ATR range states, and signal-day weak-price mirrors poor next "
        "alpha targets. The highest-expected-value direction is therefore the "
        "already interpretable default-off event bundle, specifically the "
        "rotation_breakout_leadership paper-notional tilt over the 2.0x non-generic "
        "event-surface lead."
    )
    payload["alpha_hypothesis"] = {
        "category": "allocation/event-quality",
        "entry_exit_ranking_or_allocation": "allocation",
        "why_this_now": (
            "This keeps the core candidate set fixed and tests the strongest "
            "event-quality alpha after the latest accepted core stack. It avoids "
            "known data blockers rather than trying to rescue sparse LLM/SEC fields "
            "or noisy universe additions."
        ),
    }
    history = dict(payload.get("historical_experiment_check") or {})
    history["exp-20260516-044"] = (
        "The same all-source rotation surface cleared the paper-only gate after "
        "the exp042 ISRG core-risk adaptation."
    )
    history["exp-20260516-046"] = (
        "Signal-day ATR compression risk scalar was rejected; this run avoids "
        "nearby OHLCV range-state retunes."
    )
    history["exp-20260516-047"] = (
        "Signal-day relative weakness haircut was rejected; this run avoids the "
        "mirror of accepted green/SPY leadership sizing."
    )
    history["exp-20260516-900"] = (
        "Insider/Form 4 overlay remains field- and concentration-limited; it is "
        "not the next three-window capital allocation target."
    )
    payload["historical_experiment_check"] = history
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "default-off event allocation: rotation_breakout_leadership rows "
            "remain the strongest current event-quality allocation alpha."
        ),
        "2_history_check": (
            "exp013, exp028, exp040, and exp044 passed for the same all-source "
            "rotation surface; exp030 rejected only a source-specific split. "
            "The latest rejected exp046/exp047 core states do not change the "
            "accepted core baseline."
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
            "exp_20260517_001_event_rotation_surface_current_lead_revalidation.py"
        ),
    }
    params = dict(payload.get("parameters") or {})
    params["accepted_core_checkpoint"] = "exp-20260516-042"
    params["latest_rejected_core_scouts_checked"] = ["exp-20260516-046", "exp-20260516-047"]
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
        "LLM/SEC soft-ranking lacks mature PIT-safe attribution; buyback and "
        "insider branches require richer credibility or market-cap fields; recent "
        "candidate-pool and range-state scouts added noise or failed Gate 4. The "
        "event rotation surface remains the cleanest alpha with repeated "
        "three-window evidence."
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
        f"# {EXPERIMENT_ID} Event Rotation-Surface Current-Lead Revalidation",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Revalidates whether "
            "`rotation_breakout_leadership` event rows still deserve higher "
            "bounded paper notional than the current 2.0x non-generic positive "
            "event-surface add-on after the latest rejected adjacent core scouts."
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


def persist(payload: dict[str, Any]) -> None:
    _parent()._write_json(OUT_JSON, payload)
    compact = exp044.exp040.exp028.base.prior._compact_log(payload)
    compact["changed_variable"] = payload["changed_variable"]
    compact["gate1"] = payload["gate1"]
    compact["gate2"] = payload["gate2"]
    compact["gate3"] = payload["gate3"]
    compact["gate4"] = payload["gate4"]
    compact["total_pnl_delta"] = payload["gate4"]["delta"]["aggregate_pnl_delta"]
    compact["production_impact"] = payload["production_impact"]
    _parent()._write_json(LOG_JSON, compact)
    _parent()._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event rotation-surface current-lead revalidation",
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
    payload = exp044.exp040.exp028.base.prior._retag_payload(_parent().build_payload())
    payload = exp044.exp040.exp028.base._finalize_payload(payload)
    payload = _retag_current_lead(payload)
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
