"""exp-20260719-004: fixed entity/theme bundle on materially more settled rows.

Observed-only alpha refresh.  This is a thin wrapper around the unchanged
exp-20260710-007 attribution recipe.  It changes only the evidence cohort to
the 2026-07-18 outcome ledger, which has more than doubled the settled rows.
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
    / "exp_20260710_007_entity_theme_news_more_settled_forward_value_20260709.py"
)


def _load_prior() -> Any:
    spec = importlib.util.spec_from_file_location("exp_20260710_007_prior", PRIOR_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load prior runner: {PRIOR_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = _load_prior()
base = prior.base

EXPERIMENT_ID = "exp-20260719-004"
SLUG = "entity_theme_news_more_settled_forward_value_20260718"
RUNNER = f"quant/experiments/exp_20260719_004_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

base.EXPERIMENT_ID = EXPERIMENT_ID
base.OWNER = "codex-root"
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
    / "entity_theme_news_observer_outcomes_20260718.jsonl"
)
base.SUMMARY_JSON = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "outcome_summaries"
    / "entity_theme_news_observer_outcome_summary_20260718.json"
)
base.OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
base.OUT_JSON = base.OUT_DIR / f"exp_20260719_004_{SLUG}.json"
base.LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
base.CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
base.MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
base.TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

base.HYPOTHESIS = (
    "Observed-only alpha refresh: with 47512 settled entity-theme news observer "
    "rows as of 2026-07-18 versus 22264 in exp-20260710-007, the unchanged fixed "
    "source bundle should clear the same 10-day cash/SPY/QQQ replacement-value "
    "bar before any shared helper is reconsidered."
)
base.ALPHA_HYPOTHESIS = (
    "If the fixed entity/theme source bundle contains a monetizable event-relation "
    "edge, the more-than-doubled settled cohort should show broad positive 10-day "
    "replacement value versus cash, SPY, and QQQ without any map or policy retune."
)
base.TRIAL_VARIANT_ID = "materially_more_settled_rows_20260718_v1"
base.CHANGED_VARIABLE = "entity_theme_news_source_bundle_more_settled_rows_20260718_v1"
base.NEW_EVIDENCE_AXIS = (
    "Materially more settled forward rows: the 2026-07-18 entity_theme_news "
    "summary reports 47512 settled cash/SPY/QQQ rows versus 22264 in "
    "exp-20260710-007 (+25248, +113.4%), exceeding the recorded 33396-row "
    "reopen floor; source manifest, horizon, notional, query/theme/ticker maps, "
    "and acceptance rule remain unchanged."
)
base.NEARBY_PRIORS = [
    "exp-20260703-014",
    "exp-20260706-012",
    "exp-20260707-013",
    "exp-20260710-007",
    "exp-20260713-001",
    "exp-20260713-003",
]
base.CAUSAL_COMPONENTS = [
    "read-only 2026-07-18 entity-theme outcome-ledger analysis",
    "unchanged fixed source-bundle aggregate checks from exp-20260710-007",
    "materially-more-settled-row comparison",
    "theme/query/ticker/date concentration audit",
    "no strategy behavior change",
]
base.CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260719_004_{SLUG}.json",
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
    previous = _read_log("exp-20260710-007")
    previous_settled = int((previous.get("summary") or {}).get("settled_rows") or 0)
    current_settled = int(result["summary"]["settled_rows"])
    result["delta_metrics"]["settled_rows_vs_exp_20260710_007"] = (
        current_settled - previous_settled
    )
    result["delta_metrics"]["settled_row_growth_vs_exp_20260710_007_pct"] = (
        round((current_settled - previous_settled) / previous_settled, 6)
        if previous_settled
        else None
    )
    result["prior_comparison"]["exp-20260710-007"] = {
        "settled_rows": previous_settled,
        "candidate_outcome_rows": (previous.get("summary") or {}).get(
            "candidate_outcome_rows"
        ),
        "decision": previous.get("decision"),
    }
    result["saturation_accounting"] = {
        "data_source": "entity_theme_news",
        "machine_gate_shape": "candidate_pool_top1_10d",
        "frozen_family_gate_shape": "other",
        "manual_same_family_trials_after_run": 4,
        "saturation_threshold": 12,
        "saturated": False,
        "classifier_caveat": (
            "Legacy fixed-bundle rows are classified under gate_shape=other while "
            "this ticket fingerprints as candidate_pool_top1_10d, so the machine "
            "source-saturation cell reports 0 trials. Manual accounting is 4/12."
        ),
    }
    result["related_files"] = [
        RUNNER,
        base.repo_rel(PRIOR_RUNNER),
        base.repo_rel(base.LEDGER_JSONL),
        base.repo_rel(base.SUMMARY_JSON),
        "experiments/logs/exp-20260710-007.json",
    ]
    if result["gate4"]["failed_reasons"]:
        result["post_run_reflection"]["why_result_happened"] = (
            "The enlarged cohort stayed positive versus cash and SPY, but its QQQ "
            "mean and median were negative and only three query groups beat both "
            "ETF comparators.  Breadth and concentration passed, so more rows "
            "confirmed benchmark-relative source-bundle dilution rather than a "
            "deployable relation edge."
        )
        result["post_run_reflection"]["new_evidence_required"] = (
            "Park this fixed source-bundle row-attribution surface until at least "
            "71268 settled cash/SPY/QQQ rows under the unchanged manifest, a true "
            "PIT historical news archive, or a materially richer independent "
            "entity-relation/economic source."
        )
        matched_prediction_modes = []
        if (result["summary"]["row_level"]["qqq"]["median"] or 0) < 0:
            matched_prediction_modes.append("qqq_median_negative")
        if int(result["summary"]["positive_query_groups_vs_spy_and_qqq"]) == 3:
            matched_prediction_modes.append("only_three_query_groups_beat_spy_and_qqq")
        result["calibration"]["matched_prediction_failure_modes"] = (
            matched_prediction_modes
        )
        result["calibration"]["predicted_failure_mode_hit"] = bool(
            matched_prediction_modes
        )
    else:
        result["post_run_reflection"]["new_evidence_required"] = (
            "Treat this only as an observed-only lead; promotion still requires the "
            "prospective first-seen exact-URL observer to reach its recorded 75-event "
            "breadth and replacement-value gate."
        )
    return result


base.build_result = build_result


if __name__ == "__main__":
    raise SystemExit(base.main())
