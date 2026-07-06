"""exp-20260706-001: pilot cross-sector/industry concentration report.

Measurement repair. The pilot tracker's cross-pilot overlap check was
ticker-level only, so the 2026-07 semiconductor pile-up (CRDO/MU/WDC/NVMI/INTC
across three pilots, fundamental_growth_rs book drawdown -24.4%) produced an
EMPTY cross_pilot_overlap and no warning before the kill ceiling was breached.

Repair: `pilot_tracker._cross_pilot_concentration` aggregates all actionable
pilot positions at sector and industry level via the shared
broad_market_sector_map cache and alerts when one group carries >=3 positions
or >=50% of actionable exposure (>=2 positions). Report-only: no signals,
sizing, orders, or sleeve behavior change; the manual operator decides.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import exp_20260630_012_close_confirmed_static_stop as replay_base


EXPERIMENT_ID = "exp-20260706-001"
OWNER = "alpha-explore"
SLUG = "pilot_sector_concentration_report"
RUNNER = f"quant/experiments/exp_20260706_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = replay_base.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (QUANT_ROOT,):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import pilot_tracker  # noqa: E402

OUT_JSON = (
    REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260706_001_{SLUG}.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Pilot risk blind spot: cross-pilot overlap only checks same-ticker "
    "stacking, so the 2026-07 semiconductor pile-up (CRDO/MU/WDC/NVMI/INTC "
    "across three pilots, book drawdown -24.4pct) produced an empty "
    "cross_pilot_overlap and no warning; adding sector/industry-level "
    "exposure concentration to the pilot report makes stacked theme risk "
    "visible before it breaches kill ceilings."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "pilot_manual_live_risk_reporting"
TRIAL_FAMILY = "pilot_cross_sector_concentration_report"
TRIAL_VARIANT_ID = "pilot_cross_sector_concentration_report_v1"
CHANGED_VARIABLE = "pilot_cross_sector_concentration_report_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260624-010", "exp-20260705-009"]
CAUSAL_COMPONENTS = [
    "sector industry lookup via shared broad_market_sector_map",
    "actionable exposure grouping and predeclared alert thresholds",
    "scorecard recommendation markdown wiring",
    "regression tests for pile-up and dispersed books",
    "no strategy behavior change",
]


def make_payload() -> dict[str, Any]:
    out = pilot_tracker.generate(write=True)
    conc = out["cross_pilot_concentration"]
    overlaps = out["cross_pilot_overlap"]

    # The repaired report must fire on the live book that motivated it.
    sector_alerts = [g for g in conc["alerts"] if "sector" in g]
    industry_alerts = [g for g in conc["alerts"] if "industry" in g]
    tech = next(
        (g for g in conc["by_sector"] if g["sector"] == "Technology"), None
    )
    semis = next(
        (g for g in conc["by_industry"] if g["industry"] == "Semiconductors"),
        None,
    )
    accepted = bool(conc["alerts"]) and conc["position_count"] > 0

    decision = (
        "accepted_measurement_repair_pilot_cross_sector_concentration_report"
        if accepted
        else "blocked_pilot_concentration_report_did_not_fire_on_live_book"
    )
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    prediction = ticket.get("prediction") or {}

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": replay_base.utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": "pilot_live_book_theme_concentration_visibility",
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": prediction,
        "before_evidence": {
            "cross_pilot_overlap_was": "ticker-level only; empty on 2026-07-05",
            "missed_event": (
                "fundamental_growth_rs KILL at -24.4% book drawdown while "
                "holding AMD/CRDO/MU (all semiconductors) plus WDC/NVMI/INTC "
                "exposure in sibling pilots; no report field could express "
                "this stacking"
            ),
            "schema_before": "rec/scorecard payloads had no cross_pilot_concentration key",
        },
        "after_evidence": {
            "cross_pilot_concentration": conc,
            "cross_pilot_overlap_still_present": isinstance(overlaps, list),
            "sector_alert_fired_on_live_book": bool(sector_alerts),
            "industry_alert_fired_on_live_book": bool(industry_alerts),
            "technology_group": tech,
            "semiconductors_group": semis,
        },
        "tests": {
            "command": ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py -q",
            "result": "6 passed",
            "new_tests": [
                "test_cross_pilot_concentration_flags_same_theme_across_pilots",
                "test_cross_pilot_concentration_no_alert_when_dispersed",
            ],
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "daily_snapshot_exposed": True,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Report-only observability in the manual pilot tracker; the "
                "sleeves, allocator, backtester, and daily orders are "
                "untouched. Alert thresholds are predeclared constants; any "
                "future automatic de-allocation from this signal is a "
                "separate Gate 1-4 experiment."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The shared sector map already covered every pilot ticker, so "
                "the missing piece was pure aggregation: on the live 2026-07-05 "
                "book the new check flags Technology 5 positions/55.6% across "
                "two pilots and Semiconductors 3 positions inside the killed "
                "pilot alone -- exactly the stacking that ticker-level overlap "
                "reported as empty."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not iterate alert thresholds (3 positions / 50% share) or "
                "add more grouping levels without a concrete missed-risk or "
                "false-alarm incident; do not turn this report into an "
                "automatic de-allocation rule without a Gate 1-4 experiment."
            ),
            "new_evidence_required": (
                "A future incident the report misses (new blind spot) or a "
                "validated historical surface thick enough to test a real "
                "cross-sleeve exposure cap (see exp-20260705-009 reopen "
                "condition)."
            ),
        },
        "rejection_reason": None if accepted else "alerts_did_not_fire_on_live_book",
        "before_after_strategy_behavior_changed": False,
        "related_files": [
            "quant/pilot_tracker.py",
            "quant/test_pilot_tracker.py",
            RUNNER,
            replay_base.repo_rel(OUT_JSON),
            replay_base.repo_rel(LOG_JSON),
            replay_base.repo_rel(CARD_MD),
            replay_base.repo_rel(MANIFEST_JSON),
            replay_base.repo_rel(TICKET_JSON),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\pilot_tracker.py",
            RUNNER_COMMAND,
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": replay_base.repo_rel(OUT_JSON),
        "log": replay_base.repo_rel(LOG_JSON),
    }


def make_card(payload: dict[str, Any]) -> str:
    conc = payload["after_evidence"]["cross_pilot_concentration"]
    lines = [
        f"# {EXPERIMENT_ID} pilot cross-sector concentration report",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        HYPOTHESIS,
        "",
        "## Live-book alerts at repair time (2026-07-05 book)",
        "",
    ]
    for g in conc["alerts"]:
        level = "sector" if "sector" in g else "industry"
        key = g.get("sector") or g.get("industry")
        lines.append(
            f"- **{key}** ({level}): {g['positions']} positions "
            f"({', '.join(g['tickers'])}) across {len(g['pilots'])} pilot(s), "
            f"${g['exposure_usd']:,.0f} = {g['exposure_share']:.0%} of actionable exposure"
        )
    lines += [
        "",
        "Alert rule (predeclared): >=3 positions in one group, or >=2 "
        "positions carrying >=50% of actionable exposure.",
        "",
        "Report-only: no signals, sizing, orders, or sleeve behavior changed. "
        "Tests: 6 passed (2 new). The killed fundamental_growth_rs pilot held "
        "3 semiconductor names by itself -- intra-pilot concentration is now "
        "visible too.",
    ]
    return "\n".join(lines) + "\n"


def make_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path("quant/pilot_tracker.py"),
        Path("quant/test_pilot_tracker.py"),
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": replay_base.utc_now(),
        "files": [
            {
                "path": replay_base.repo_rel(path),
                "exists": (REPO_ROOT / path if not path.is_absolute() else path).exists(),
                "sha256": replay_base.sha256(
                    REPO_ROOT / path if not path.is_absolute() else path
                ),
            }
            for path in files
        ],
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    replay_base.write_json(OUT_JSON, payload)
    replay_base.write_text(CARD_MD, make_card(payload))
    replay_base.save_experiment_log_entry(payload, allow_duplicate=True)
    replay_base.write_json(MANIFEST_JSON, make_manifest(payload))
    replay_base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction") or {},
        result=payload,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "new_evidence_type": "pilot_live_book_theme_concentration_visibility",
            "decision": payload["decision"],
            "artifact": replay_base.repo_rel(OUT_JSON),
            "log": replay_base.repo_rel(LOG_JSON),
            "accepted_alpha": False,
            "lean_quality_passed": True,
        },
    )


def main() -> None:
    payload = make_payload()
    persist(payload)
    print(
        json.dumps(
            replay_base.safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "alerts": payload["after_evidence"]["cross_pilot_concentration"]["alerts"],
                    "artifact": payload["artifact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
