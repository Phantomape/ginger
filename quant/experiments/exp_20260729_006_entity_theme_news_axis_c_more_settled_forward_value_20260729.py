"""exp-20260729-006: entity/theme Axis-C more-settled forward value.

Observed-only research-PIT private replay scout.  This is a thin wrapper around
the unchanged exp-20260719-004 attribution recipe.  It changes only the
evidence cohort to the latest 2026-07-28 outcome ledger, whose settled row
count crossed the recorded Axis-C reopen threshold.  It does not retune the
source manifest, query/theme/ticker maps, horizon, notional, acceptance rule,
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

EXPERIMENT_ID = "exp-20260729-006"
OWNER = "codex-alpha"
SLUG = "entity_theme_news_axis_c_more_settled_forward_value_20260729"
RUNNER = f"quant/experiments/exp_20260729_006_{SLUG}.py"
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
    / "entity_theme_news_observer_outcomes_20260728.jsonl"
)
base.SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_summaries"
    / "entity_theme_news_observer_outcome_summary_20260728.json"
)
base.OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260729_006_{SLUG}.json"
base.LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
base.CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
base.MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
base.TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

base.HYPOTHESIS = (
    "Research-PIT private replay scout: with 73275 settled entity-theme news "
    "observer rows now available versus 47512 in exp-20260719-004, the "
    "unchanged fixed six-query source bundle should clear the same 10-session "
    "cash/SPY/QQQ replacement-value bar before any shared helper is "
    "reconsidered; result ceiling observed_only and no paper/live authority."
)
base.ALPHA_HYPOTHESIS = (
    "If the fixed entity/theme Google News observer source bundle contains a "
    "monetizable event-relation edge, the newly matured 73275-row settled "
    "forward cohort should show broad positive H10 replacement value versus "
    "cash, SPY, and QQQ without any query, ticker-map, horizon, notional, "
    "response, ranking, sizing, exit, order, or live retune."
)
base.CHANGE_TYPE = "private_replay_scout"
base.MECHANISM_FAMILY = "production_visible_entity_theme_news_observer_candidate_pool"
base.TRIAL_FAMILY = "entity_theme_news_source_bundle_forward_value"
base.TRIAL_VARIANT_ID = "materially_more_settled_rows_20260729_v1"
base.CHANGED_VARIABLE = "entity_theme_news_source_bundle_axis_c_more_settled_rows_20260729_v1"
base.NEW_EVIDENCE_AXIS = (
    "Materially more settled forward rows: latest entity_theme_news readiness "
    "has 73275 settled cash/SPY/QQQ rows versus exp-20260719-004 baseline "
    "47512 (+25763, +54.22%), exceeding the 71268 Axis-C reopen threshold; "
    "fixed source manifest, horizon, notional, query/theme/ticker maps, and "
    "acceptance rule remain unchanged."
)
base.NEARBY_PRIORS = [
    "exp-20260703-014",
    "exp-20260706-012",
    "exp-20260707-013",
    "exp-20260710-007",
    "exp-20260719-004",
]
base.CAUSAL_COMPONENTS = [
    "read-only latest entity-theme outcome-ledger analysis after reserve",
    "unchanged fixed six-query source manifest",
    "unchanged ten-session cash SPY QQQ replacement-value rule",
    "Axis-C settled row count crossed 71268",
    "no strategy ranking sizing exit prompt order paper or live behavior change",
]
base.CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260729_006_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
base.REPRODUCTION_COMMANDS = [
    f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
    RUNNER_COMMAND,
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
    previous = _read_log("exp-20260719-004")
    previous_settled = int((previous.get("summary") or {}).get("settled_rows") or 0)
    current_settled = int(result["summary"]["settled_rows"])
    result["delta_metrics"]["settled_rows_vs_exp_20260719_004"] = (
        current_settled - previous_settled
    )
    result["delta_metrics"]["settled_row_growth_vs_exp_20260719_004_pct"] = (
        round((current_settled - previous_settled) / previous_settled, 6)
        if previous_settled
        else None
    )
    result["prior_comparison"]["exp-20260719-004"] = {
        "settled_rows": previous_settled,
        "candidate_outcome_rows": (previous.get("summary") or {}).get(
            "candidate_outcome_rows"
        ),
        "decision": previous.get("decision"),
    }
    result["alpha_promotion"] = {
        "promotion_request": "data/alpha_search/promotions/entity_theme_axis_c_scout_20260729.json",
        "schema_version": 2,
        "candidate_id": "cand-9592dadba5fa01a3ea24",
        "selection_scope_id": "scope-5792cc21a42938c85fa336ed",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
    }
    result["saturation_accounting"] = {
        "data_source": "entity_theme_news",
        "machine_gate_shape": "candidate_pool_top1_10d",
        "manual_same_family_trials_after_run": 5,
        "saturation_threshold": 12,
        "saturated": False,
        "classifier_caveat": (
            "Legacy fixed-bundle rows were partly classified under gate_shape=other; "
            "manual same-family accounting is five closed fixed source-bundle probes "
            "after this run."
        ),
    }
    result["related_files"] = [
        RUNNER,
        base.repo_rel(PRIOR_RUNNER),
        base.repo_rel(base.LEDGER_JSONL),
        base.repo_rel(base.SUMMARY_JSON),
        "data/alpha_search/promotions/entity_theme_axis_c_scout_20260729.json",
        "data/alpha_search/entity_theme_selection_panel_20260729.json",
        "data/alpha_search/entity_theme_scope_manifest_20260729.json",
        "data/alpha_search/entity_theme_surfaces_20260729.json",
        "experiments/logs/exp-20260719-004.json",
    ]
    if result["gate4"]["failed_reasons"]:
        result["post_run_reflection"]["new_evidence_required"] = (
            "Park this unchanged fixed source-bundle row-attribution surface until "
            "at least 109913 settled cash/SPY/QQQ rows under the unchanged manifest "
            "(50% above 73275), a true canonical PIT historical news archive, or a "
            "materially richer independent entity-relation/economic source."
        )
        result["post_run_reflection"]["forbidden_near_neighbor_retry"] = (
            "Do not retune entity/theme queries, theme labels, candidate ticker maps, "
            "horizons, notional, response curves, SEC-confirmation windows, ranking, "
            "sizing, exits, or live/paper behavior on this same source bundle."
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


if __name__ == "__main__":
    raise SystemExit(base.main())
