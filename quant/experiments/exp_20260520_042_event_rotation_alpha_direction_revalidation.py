"""exp-20260520-042: event-rotation alpha direction revalidation.

Alpha search, replay-only. This run revalidates the strongest current non-core
alpha direction after reviewing recent failures and data blockers. It makes no
production, live-order, sizing, exit, LLM, news, or ticker-pool change.

No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260517_010_event_rotation_surface_after_exp009_revalidation as prev


EXPERIMENT_ID = "exp-20260520-042"
EXPERIMENT_SLUG = "event_rotation_alpha_direction_revalidation"

REPO_ROOT = prev.REPO_ROOT
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


BLOCKED_ALPHA_LANES = [
    {
        "lane": "llm_soft_ranking",
        "status": "blocked",
        "evidence": (
            "Historical attribution is not yet strong enough to compare LLM "
            "soft ranks versus non-veto candidates without replay bias."
        ),
        "nearby_experiments": ["exp-20260520-034"],
    },
    {
        "lane": "broad_market_forward_maturation",
        "status": "blocked",
        "evidence": "Current forward feed produced zero candidates/outcomes.",
        "nearby_experiments": ["exp-20260520-027"],
    },
    {
        "lane": "state_surface_capital_allocation",
        "status": "blocked",
        "evidence": (
            "The strict state-surface rule now requires >10% aggregate EV "
            "uplift for same-family scalar/profile/notional retunes, and the "
            "latest support scout was below that bar."
        ),
        "nearby_experiments": ["exp-20260520-028", "exp-20260520-033"],
    },
    {
        "lane": "sec_fact_tone_and_buyback",
        "status": "blocked",
        "evidence": (
            "SEC phrase provenance and current-row samples are insufficient; "
            "the latest buyback capacity scout had zero event trades."
        ),
        "nearby_experiments": ["exp-20260520-029", "exp-20260520-034", "exp-20260520-039"],
    },
    {
        "lane": "core_candidate_pool_promotion",
        "status": "rejected_recently",
        "evidence": (
            "The six-name pool, CIEN-only, and AGX-only attempts failed the "
            "standard multi-window/single-sample guard."
        ),
        "nearby_experiments": ["exp-20260520-007", "exp-20260520-019", "exp-20260520-040"],
    },
    {
        "lane": "current_core_dte_or_payment_network_risk",
        "status": "rejected_recently",
        "evidence": (
            "Recent DTE and payment-network risk scouts improved only isolated "
            "windows or failed sample guards."
        ),
        "nearby_experiments": ["exp-20260520-037", "exp-20260520-038", "exp-20260520-041"],
    },
    {
        "lane": "low_deployment_etf_selector",
        "status": "rejected_recently",
        "evidence": (
            "The risk-adjusted selector regressed old_thin versus the accepted "
            "raw-momentum paper overlay, so adjacent selector formulas need new "
            "forward replacement evidence first."
        ),
        "nearby_experiments": ["exp-20260520-016"],
    },
]


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    prev.EXPERIMENT_ID = EXPERIMENT_ID
    prev.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    prev.OUT_JSON = OUT_JSON
    prev.LOG_JSON = LOG_JSON
    prev.TICKET_JSON = TICKET_JSON
    prev.ARTIFACT_MD = ARTIFACT_MD
    prev.EXPERIMENT_LOG = EXPERIMENT_LOG
    prev._configure_modules()


def _lane_summary() -> list[str]:
    lines = []
    for lane in BLOCKED_ALPHA_LANES:
        related = ", ".join(lane["nearby_experiments"])
        lines.append(
            "- `{lane}`: {status}; {evidence} ({related})".format(
                lane=lane["lane"],
                status=lane["status"],
                evidence=lane["evidence"],
                related=related,
            )
        )
    return lines


def _retag_current_direction(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    passed = (
        gate["delta"]["aggregate_ev_delta"] > 0
        and gate["delta"]["aggregate_pnl_delta"] > 0
        and gate["delta"]["windows_ev_regressed"] == 0
        and gate["sample_guard_passed"]
    )

    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "alpha_search_direction_revalidation"
    payload["changed_variable"] = "event_rotation_replacement_value_direction"
    payload["decision"] = (
        "accepted_replay_only_event_rotation_as_next_alpha_direction"
        if passed
        else "rejected_event_rotation_direction_revalidation"
    )
    payload["status"] = payload["decision"]
    payload["hypothesis"] = (
        "Given the recent failed or blocked LLM, SEC, broad-market, state-surface, "
        "core candidate-pool, DTE, and low-deployment ETF lanes, the best current "
        "alpha direction is still event-rotation replacement value. Revalidate "
        "the default-off rotation_breakout_leadership paper-notional tilt across "
        "the three standard windows before spending more search budget on weaker "
        "or data-limited directions."
    )
    payload["alpha_hypothesis"] = {
        "category": "capital allocation / event-quality",
        "entry_exit_ranking_or_allocation": "capital allocation",
        "why_this_now": (
            "This lane has repeated multi-window replay evidence and a shared "
            "default-off paper policy path, while the alternative alpha lanes "
            "either lack forward samples or recently failed Gate 4."
        ),
        "playbook_alignment": (
            "Matches the playbook's event-rotation replacement-value maturation "
            "direction and avoids state-surface scalar mining."
        ),
    }
    payload["trial_accounting"] = {
        "trial_family": "event_rotation_replacement_value_maturation",
        "changed_variable": "event_rotation_replacement_value_direction",
        "prior_trial_count": 8,
        "nearby_prior_experiments": [
            "exp-20260516-013",
            "exp-20260516-028",
            "exp-20260516-040",
            "exp-20260516-044",
            "exp-20260517-001",
            "exp-20260517-010",
            "exp-20260520-027",
            "exp-20260520-033",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": (
            "current_stack_three_window_revalidation_plus_alpha_lane_blocker_triage"
        ),
        "retention_note": (
            "This is not a new threshold/profile/notional scalar promotion and "
            "does not enable live capital. It selects the next alpha direction "
            "based on the standard three-window evidence and recent blocked lanes."
        ),
    }
    history = dict(payload.get("historical_experiment_check") or {})
    history.update(
        {
            "exp-20260520-027": "Broad-market forward maturation had zero current outcomes.",
            "exp-20260520-033": "State-surface support improvement was below the strict >10% aggregate EV bar.",
            "exp-20260520-039": "SEC buyback remaining-capacity scout had zero event trades.",
            "exp-20260520-040": "AGX-only core promotion failed Gate 4 and produced no AGX executed trades.",
            "exp-20260520-041": "DTE nonconfirming candle risk improved only mid_weak.",
        }
    )
    payload["historical_experiment_check"] = history
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "Event-rotation replacement value remains the highest-confidence "
            "alpha direction; it belongs to capital allocation/event-quality."
        ),
        "2_history_check": (
            "Prior event-rotation surface runs passed replay gates, while recent "
            "LLM, SEC, broad-market, state-surface, candidate-pool, DTE, and ETF "
            "lanes were blocked or rejected. This run records that comparison."
        ),
        "3_single_causal_variable": (
            "Only the selected alpha direction is being revalidated; no production "
            "policy, threshold, ticker, scalar, prompt, or adapter is changed."
        ),
        "4_acceptance_standard": (
            "docs/backtesting.md three fixed windows; require aggregate EV/PnL "
            "improvement versus current lead, no EV-regressed window, and sample "
            "guard pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260520_042_event_rotation_alpha_direction_revalidation.py"
        ),
    }
    params = dict(payload.get("parameters") or {})
    params.update(
        {
            "candidate_alpha_lanes_reviewed": BLOCKED_ALPHA_LANES,
            "anti_js": "No JavaScript was used.",
            "production_enablement": "not attempted",
        }
    )
    payload["parameters"] = params
    payload["blocked_alpha_lanes"] = BLOCKED_ALPHA_LANES
    payload["why_not_other_attractive_points"] = (
        "The next alpha-search budget should not go into LLM soft-ranking, SEC "
        "fact-tone/buyback, broad-market forward, state-surface scalar/profile "
        "retunes, single-ticker core promotions, DTE risk patches, or ETF selector "
        "variants until those lanes gain new forward rows or fix their specific "
        "sample/provenance blockers."
    )
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
            "The revalidated policy path is shared but default-off/paper-only. "
            "This experiment does not create a backtest-only live behavior gap "
            "because it does not alter production trade generation or orders."
        ),
        "promotion_blocker_if_positive": (
            "Live/default capital still requires closed forward replacement-value "
            "evidence and explicit adapter enablement."
        ),
    }
    payload["reproduction_command"] = (
        ".venv\\Scripts\\python.exe quant\\experiments\\"
        "exp_20260520_042_event_rotation_alpha_direction_revalidation.py"
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
    current = payload["before_metrics"][prev.prior._parent().CURRENT_LEAD_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event-Rotation Alpha Direction Revalidation",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. This run compares the current accepted "
            "event-surface lead against the `rotation_breakout_leadership` paper "
            "notional tilt and records why the other high-level alpha lanes are "
            "not the next best search target."
        ),
        "",
        "## Best Variant Vs Current Lead",
        "",
        "| Window | Current EV | Variant EV | Delta EV | Current PnL | Variant PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prev.prior._parent().base.WINDOWS:
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
            "## Blocked Or Recently Rejected Lanes",
            "",
            *_lane_summary(),
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
    prev.prior._artifact_markdown = _artifact_markdown
    payload = prev.prior.exp044.exp040.exp028.base.prior._retag_payload(
        prev.prior._parent().build_payload()
    )
    payload = prev.prior.exp044.exp040.exp028.base._finalize_payload(payload)
    payload = prev.prior._retag_current_lead(payload)
    payload = prev._retag_after_exp009(payload)
    payload = _retag_current_direction(payload)
    prev.prior.persist(payload)
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_current_lead"][best]
    print(
        json.dumps(
            prev.prior._parent()._safe(
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
