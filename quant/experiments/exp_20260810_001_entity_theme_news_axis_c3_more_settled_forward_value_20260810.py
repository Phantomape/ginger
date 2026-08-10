"""exp-20260810-001: entity/theme Axis-C third more-settled forward value read.

Observed-only research-PIT private replay scout.  This is a thin wrapper around
the unchanged exp-20260719-004 attribution recipe via the exp-20260729-006
wrapper lineage.  It changes only the evidence cohort to the latest 2026-08-10
outcome ledger, whose settled row count crossed the 109913 Axis-C reopen
threshold declared at exp-20260729-006 closeout.  It does not retune the
source manifest, query/theme/ticker maps, horizon, row size, acceptance rule,
ranking, sizing, exits, orders, paper, or live behavior.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PRIOR_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260719_004_entity_theme_news_more_settled_forward_value_20260718.py"
)


def _load_prior() -> Any:
    spec = importlib.util.spec_from_file_location("exp_20260719_004_prior", PRIOR_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load prior runner: {PRIOR_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = _load_prior()
base = prior.base

EXPERIMENT_ID = "exp-20260810-001"
OWNER = "claude-scheduled-alpha"
SLUG = "entity_theme_news_axis_c3_more_settled_forward_value_20260810"
RUNNER = f"quant/experiments/exp_20260810_001_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

base.EXPERIMENT_ID = EXPERIMENT_ID
base.OWNER = OWNER
base.SLUG = SLUG
base.RUNNER = RUNNER
base.RUNNER_PS = RUNNER_PS
base.RUNNER_COMMAND = RUNNER_COMMAND
base.BASELINE_JSON = (
    REPO_ROOT / "data" / "experiments" / "exp-20260715-010" / "after_measurement.json"
)
base.LEDGER_JSONL = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_ledgers"
    / "entity_theme_news_observer_outcomes_20260810.jsonl"
)
base.SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_summaries"
    / "entity_theme_news_observer_outcome_summary_20260810.json"
)
base.OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260810_001_{SLUG}.json"
base.LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
base.CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
base.MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
base.TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

base.HYPOTHESIS = (
    "Third axis-C reopen read of the unchanged fixed six-query entity/theme "
    "news source bundle: with 114541 settled cash/SPY/QQQ replacement-value "
    "rows now materially more than the 73275 available at exp-20260729-006 "
    "(+41266, +56.32%, crossing the declared 109913 bar), the unchanged "
    "source manifest, query/theme/ticker maps, 10-session horizon, 4000-USD "
    "fixed row size, and the exp-20260719-004 acceptance rule should show "
    "broad positive next-open-to-10-session-close replacement value versus "
    "cash, SPY, and QQQ across query groups without any retune; result "
    "ceiling observed_only and no paper/live authority."
)
base.ALPHA_HYPOTHESIS = (
    "If the fixed entity/theme Google News observer source bundle contains a "
    "monetizable event-relation edge, the newly matured 114541-row settled "
    "forward cohort should show broad positive H10 replacement value versus "
    "cash, SPY, and QQQ without any query, ticker-map, horizon, row-size, "
    "response, ranking, sizing, exit, order, or live retune."
)
base.CHANGE_TYPE = "private_replay_scout"
base.MECHANISM_FAMILY = "production_visible_entity_theme_news_observer_candidate_pool"
base.TRIAL_FAMILY = "entity_theme_news_source_bundle_forward_value"
base.TRIAL_VARIANT_ID = "materially_more_settled_rows_20260810_v1"
base.CHANGED_VARIABLE = "entity_theme_news_source_bundle_axis_c_more_settled_rows_20260810_v1"
base.NEW_EVIDENCE_AXIS = (
    "Materially more settled forward rows: latest entity_theme_news readiness "
    "has 114541 settled cash/SPY/QQQ rows versus exp-20260729-006 baseline "
    "73275 (+41266, +56.32%), exceeding the 109913 Axis-C reopen threshold; "
    "fixed source manifest, horizon, row size, query/theme/ticker maps, and "
    "acceptance rule remain unchanged."
)
base.NEARBY_PRIORS = [
    "exp-20260703-014",
    "exp-20260706-012",
    "exp-20260707-013",
    "exp-20260710-007",
    "exp-20260719-004",
    "exp-20260729-006",
]
base.CAUSAL_COMPONENTS = [
    "read-only latest entity-theme outcome-ledger attribution after reserve; cohort frozen outcome-blind in data/alpha_search/entity_theme_axis_c3_readiness_20260810.json (ledger sha256 recorded) before any replacement value was read",
    "unchanged fixed six-query source manifest / query-theme-ticker maps / 10-session horizon / 4000-USD fixed row size",
    "unchanged exp-20260719-004 acceptance rule as the frozen falsifier; no per-query sub-verdicts read before it",
    "section 2.4 axis (c): settled rows grew 73275 -> 114541 (+56.32% and +41266 absolute) crossing the 109913 bar declared at exp-20260729-006 closeout; machine lane entity_theme_axis_c status ready in data/reopen_readiness.json (generated 2026-08-10T16:45:19Z)",
    "if any acceptance bar fails then re-park the face at >=171812 settled rows and sync scripts/build_reopen_readiness.py in this same ticket per the 2026-07-22 reopen-threshold-sync rule",
    "no strategy / ranking / sizing / exit / order / paper / live behavior change; trade_enabled=false; result ceiling observed_only",
]
base.CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260810_001_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
base.REPRODUCTION_COMMANDS = [
    f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\build_reopen_readiness.py",
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def _read_log(experiment_id: str) -> dict[str, Any]:
    path = REPO_ROOT / "experiments" / "logs" / f"{experiment_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


_prior_build_result = base.build_result


def build_result() -> dict[str, Any]:
    result = _prior_build_result()
    previous = _read_log("exp-20260729-006")
    previous_settled = int((previous.get("summary") or {}).get("settled_rows") or 0)
    current_settled = int(result["summary"]["settled_rows"])
    result["delta_metrics"]["settled_rows_vs_exp_20260729_006"] = (
        current_settled - previous_settled
    )
    result["delta_metrics"]["settled_row_growth_vs_exp_20260729_006_pct"] = (
        round((current_settled - previous_settled) / previous_settled, 6)
        if previous_settled
        else None
    )
    result["prior_comparison"]["exp-20260729-006"] = {
        "settled_rows": previous_settled,
        "candidate_outcome_rows": (previous.get("summary") or {}).get(
            "candidate_outcome_rows"
        ),
        "decision": previous.get("decision"),
    }
    result["alpha_promotion"] = {
        "promotion_request": "data/alpha_search/promotions/entity_theme_axis_c3_scout_20260810.json",
        "schema_version": 2,
        "candidate_id": "cand-3f164742aa04c09841d4",
        "selection_scope_id": "scope-bbab47020ad43febe0bae992",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
    }
    result["saturation_accounting"] = {
        "data_source": "entity_theme_news",
        "machine_gate_shape": "other",
        "manual_same_family_trials_after_run": 6,
        "saturation_threshold": 12,
        "saturated": False,
        "classifier_caveat": (
            "This ticket's hypothesis avoids gate-shape keywords, so the machine "
            "fingerprint routes to gate_shape=other like the frozen family record; "
            "prior probes were split between candidate_pool_top1_10d and other. "
            "Manual same-family accounting is six closed fixed source-bundle probes "
            "after this run; the observed-only streak on entity_theme_news reaches "
            "three consecutive closes if this read fails, so any fourth probe needs "
            "the redeclared 171812-row bar plus an explicit observed-only override."
        ),
    }
    result["related_files"] = [
        RUNNER,
        base.repo_rel(PRIOR_RUNNER),
        base.repo_rel(base.LEDGER_JSONL),
        base.repo_rel(base.SUMMARY_JSON),
        "data/alpha_search/promotions/entity_theme_axis_c3_scout_20260810.json",
        "data/alpha_search/entity_theme_axis_c3_selection_panel_20260810.json",
        "data/alpha_search/entity_theme_axis_c3_scope_manifest_20260810.json",
        "data/alpha_search/entity_theme_axis_c3_surfaces_20260810.json",
        "data/alpha_search/entity_theme_axis_c3_readiness_20260810.json",
        "experiments/logs/exp-20260729-006.json",
    ]
    if result["gate4"]["failed_reasons"]:
        result["post_run_reflection"]["new_evidence_required"] = (
            "Park this unchanged fixed source-bundle row-attribution surface until "
            "at least 171812 settled cash/SPY/QQQ rows under the unchanged manifest "
            "(50% above 114541), a true canonical PIT historical news archive, or a "
            "materially richer independent entity-relation/economic source."
        )
        result["post_run_reflection"]["forbidden_near_neighbor_retry"] = (
            "Do not retune entity/theme queries, theme labels, candidate ticker maps, "
            "horizons, row size, response curves, SEC-confirmation windows, ranking, "
            "sizing, exits, or live/paper behavior on this same source bundle; the "
            "entity_theme_news observed-only streak reaches three consecutive closes "
            "with this result, so a fourth probe additionally needs an explicit "
            "observed-only override with the redeclared bar."
        )
        matched_prediction_modes = []
        if (result["summary"]["row_level"]["qqq"]["median"] or 0) < 0:
            matched_prediction_modes.append("qqq_mean_or_median_negative")
        if int(result["summary"]["positive_query_groups_vs_spy_and_qqq"]) < 4:
            matched_prediction_modes.append("only_three_query_groups_beat_spy_and_qqq")
        if result["gate4"]["failed_reasons"]:
            matched_prediction_modes.append("benchmark_relative_edge_absent")
        result["calibration"]["matched_prediction_failure_modes"] = (
            sorted(set(matched_prediction_modes))
        )
        result["calibration"]["predicted_failure_mode_hit"] = bool(
            matched_prediction_modes
        )
    else:
        result["post_run_reflection"]["new_evidence_required"] = (
            "Treat this only as an observed-only lead. Promotion beyond research "
            "requires canonical as-published news vintages, a shared default-off "
            "helper, daily parity, and full Gate 1-4."
        )
    return result


base.build_result = build_result


def _normalise_registry_decision(value: Any) -> Any:
    """research_replay tickets may only close observed_only or rejected.

    Descriptive decisions like observed_only_rejected stay in nested gate4 and
    artifact fields; the registry top-level fields get the normalized form
    (exp-20260806-001 persist-boundary rule).
    """
    if isinstance(value, str) and value.startswith("observed_only") and value != "observed_only":
        return "rejected" if "reject" in value else "observed_only"
    return value


_prior_persist_self_registered_result = base.persist_self_registered_result


def _normalising_persist_self_registered_result(*args: Any, **kwargs: Any) -> Any:
    if "status" in kwargs:
        kwargs["status"] = _normalise_registry_decision(kwargs["status"])
    result = kwargs.get("result")
    if isinstance(result, dict) and "decision" in result:
        result = dict(result)
        result["decision"] = _normalise_registry_decision(result["decision"])
        kwargs["result"] = result
    fields = kwargs.get("fields")
    if isinstance(fields, dict) and "decision" in fields:
        fields = dict(fields)
        fields["decision"] = _normalise_registry_decision(fields["decision"])
        kwargs["fields"] = fields
    return _prior_persist_self_registered_result(*args, **kwargs)


base.persist_self_registered_result = _normalising_persist_self_registered_result


if __name__ == "__main__":
    raise SystemExit(base.main())
