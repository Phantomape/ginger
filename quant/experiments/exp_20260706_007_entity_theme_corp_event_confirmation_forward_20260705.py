"""exp-20260706-007: rerun entity/theme confirmation on new forward rows.

This observed-only alpha reuses the fixed 30-calendar-day corporate-event
entity-exposure confirmation contract from exp-20260705-017. The only evidence
change is the 2026-07-05 entity/theme outcome ledger, whose settled forward row
count advanced materially after the prior closeout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.experiments import (  # noqa: E402
    exp_20260705_017_entity_theme_sec_event_cross_confirmation as base,
)


EXPERIMENT_ID = "exp-20260706-007"
SLUG = "entity_theme_corp_event_confirmation_forward_20260705"
RUNNER = f"quant/experiments/exp_20260706_007_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
CHANGED_VARIABLE = (
    "entity_theme_news_corporate_event_exposure_confirmation_forward_20260705_v1"
)
HYPOTHESIS = (
    "Observed-only alpha: after the 2026-07-05 entity/theme observer refresh, "
    "the unchanged 30-day corporate-event entity-exposure confirmation contract "
    "now has materially more settled forward rows and may separate stronger "
    "cash/SPY/QQQ replacement value than unconfirmed rows."
)
NEW_EVIDENCE_AXIS = (
    "new data source and materially more settled forward rows: "
    "entity_theme_news_observer outcome ledger plus "
    "corporate_event_entity_exposure_map, not SEC FTD and not FINRA; settled "
    "rows advanced from 2735 in exp-20260705-017 to 8158 in the 20260705 "
    "outcome summary under the unchanged 30-day confirmation contract"
)
NEARBY_PRIORS = [
    "exp-20260705-017",
    "exp-20260703-014",
    "exp-20260702-011",
    "exp-20260702-012",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "confirmed_rows_still_do_not_beat_unconfirmed",
        "entity_exposure_overbroad",
        "new_rows_same_noise_profile",
        "current_news_snapshot_pit_caveat",
    ],
    "confidence_reason": (
        "The prior fixed 30-day corporate-event exposure confirmation contract "
        "failed on 2735 settled rows, but the 20260705 entity_theme_news_observer "
        "ledger expands to 8158 settled rows under the same observer/outcome rule. "
        "That is legal new forward evidence, not a threshold or horizon retune; "
        "the base rate stays low because both sources were noisy and the news "
        "observer remains a current-snapshot PIT caveat."
    ),
}


def configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.OWNER = "alpha-explore"
    base.SLUG = SLUG
    base.RUNNER = RUNNER
    base.RUNNER_COMMAND = RUNNER_COMMAND
    base.HYPOTHESIS = HYPOTHESIS
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.MECHANISM_FAMILY = "cross_source_entity_relation_confirmation"
    base.TRIAL_FAMILY = "entity_theme_corporate_event_exposure_confirmation"
    base.TRIAL_VARIANT_ID = (
        "corporate_event_exposure_30d_confirmation_20260705_forward_rows_v1"
    )
    base.NEARBY_PRIORS = NEARBY_PRIORS
    base.NEW_EVIDENCE_AXIS = NEW_EVIDENCE_AXIS
    base.DEFAULT_PREDICTION = DEFAULT_PREDICTION
    base.ENTITY_THEME_LEDGER = (
        base.REPO_ROOT
        / "data"
        / "non_ohlcv"
        / "entity_theme_news_observer"
        / "outcome_ledgers"
        / "entity_theme_news_observer_outcomes_20260705.jsonl"
    )
    base.OUT_DIR = base.REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    base.OUT_JSON = (
        base.OUT_DIR / f"exp_20260706_007_{SLUG}.json"
    )
    base.LOG_JSON = (
        base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    )
    base.CARD_MD = (
        base.REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
    )
    base.MANIFEST_JSON = (
        base.REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
    )
    base.TICKET_JSON = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    base.CHANGED_FILES = [
        RUNNER,
        f"data/experiments/{EXPERIMENT_ID}/exp_20260706_007_{SLUG}.json",
        f"experiments/cards/{EXPERIMENT_ID}.md",
        f"experiments/manifests/{EXPERIMENT_ID}.json",
        f"experiments/tickets/{EXPERIMENT_ID}.json",
        f"experiments/logs/{EXPERIMENT_ID}.json",
        "docs/experiment_registry.json",
    ]


def finalize_result(result: dict) -> dict:
    result["new_evidence_type"] = "materially_more_settled_forward_rows"
    result["new_evidence_axis"] = NEW_EVIDENCE_AXIS
    result["changed_files"] = list(base.CHANGED_FILES)
    result["related_files"] = [
        RUNNER,
        base.repo_rel(base.ENTITY_THEME_LEDGER),
        base.repo_rel(base.ENTITY_THEME_SUMMARY),
        base.repo_rel(base.EVENT_ROWS),
        base.repo_rel(base.EXPOSURE_MANIFEST),
        "experiments/logs/exp-20260705-017.json",
        "experiments/logs/exp-20260703-014.json",
        "experiments/logs/exp-20260702-011.json",
        "experiments/logs/exp-20260702-012.json",
    ]
    result["reproduction_commands"] = [
        RUNNER_COMMAND,
        ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
    ]
    result["source_artifacts"]["entity_theme_ledger"] = base.repo_rel(
        base.ENTITY_THEME_LEDGER
    )
    result["post_run_reflection"]["new_evidence_required"] = (
        "A further retry needs additional prospectively accumulated "
        "entity/theme rows beyond the 20260705 ledger under this unchanged "
        "confirmation contract, a true PIT historical news archive, or a "
        "different independent entity-relation source."
    )
    result["next_retry_requires"] = [
        "additional prospective entity/theme observer rows beyond the 20260705 ledger",
        "unchanged 30-day corporate-event confirmation contract for the next audit",
        "or a true PIT historical news archive with observation-time availability",
        "or a different independent relation source; no threshold retune on this snapshot",
    ]
    return result


def main() -> int:
    configure_base()
    result = finalize_result(base.build_result())
    base.write_json(base.OUT_JSON, result)
    base.save_experiment_log_entry(base.compact_log_record(result), allow_duplicate=True)
    base.write_text(base.CARD_MD, base.build_card(result))
    base.write_manifest(result)
    base.update_ticket(result)
    base.persist_self_registered_result(
        base.REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=base.LANE,
        prediction=result["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": result["observed_only_lead"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": base.OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": HYPOTHESIS,
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": base.MECHANISM_FAMILY,
            "trial_family": base.TRIAL_FAMILY,
            "trial_variant_id": base.TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": base.repo_rel(base.CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": base.CHANGED_FILES,
            "allowed_write_scope": base.CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(
        json.dumps(
            base.compact_log_record(result),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
