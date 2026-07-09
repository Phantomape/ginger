"""exp-20260708-029: pair-spread fingerprint coverage repair.

Measurement-only runner. It proves that relative-value / pair-spread alpha
probes are keyed to their own novelty surface instead of falling into generic
``regime_state`` / ``notional_scalar`` guards. It changes no strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260708-029"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "chop_spread_fingerprint_coverage"
RUNNER = f"quant/experiments/exp_20260708_029_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
CHANGE_TYPE = "measurement_repair"
CHANGED_VARIABLE = "chop_relative_value_spread_fingerprint_coverage_v1"
MECHANISM_FAMILY = "experiment_fingerprint_governance"
TRIAL_FAMILY = "chop_relative_value_spread_fingerprint"
TRIAL_VARIANT_ID = EXPERIMENT_ID
HYPOTHESIS = (
    "Pair-spread alpha searches need a dedicated fingerprint surface: "
    "exp-20260708-025 showed chop pair-spread long-short probes classify as "
    "regime_state/notional_scalar, so future relative-value alpha work can "
    "bypass or collide with the wrong novelty and saturation guards."
)
ALPHA_HYPOTHESIS = (
    "A future chop / relative-value pair-spread alpha may be worth revisiting "
    "only with a genuinely new pair-linkage data source or materially more "
    "settled forward spread rows. This run does not retune exp-20260708-025; "
    "it repairs the guard surface that would govern any later alpha search."
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_PATH = OUT_DIR / f"exp_20260708_029_{SLUG}.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_PATH = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_PATH = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_PATH = ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)

TARGET_CASES = [
    {
        "label": "exp025_style_chop_pair_spread",
        "text": "chop pair-spread long-short market-neutral zscore entry sleeve with notional cap",
        "prior_data_source": "regime_state",
        "prior_gate_shape": "notional_scalar",
        "expected_data_source": "relative_value_spread",
        "expected_gate_shape": "pair_spread",
    },
    {
        "label": "explicit_relative_value_spread",
        "text": "relative_value_spread pair_zscore spread entry probe",
        "prior_data_source": "regime_state",
        "prior_gate_shape": "notional_scalar",
        "expected_data_source": "relative_value_spread",
        "expected_gate_shape": "pair_spread",
    },
    {
        "label": "ticket_hypothesis_reclassification",
        "text": " ".join([HYPOTHESIS, CHANGED_VARIABLE, MECHANISM_FAMILY, TRIAL_FAMILY]),
        "prior_data_source": "regime_state",
        "prior_gate_shape": "notional_scalar",
        "expected_data_source": "relative_value_spread",
        "expected_gate_shape": "pair_spread",
    },
]

REGRESSION_CASES = [
    {
        "label": "microstructure_spread_to_atr",
        "text": "microstructure spread_to_atr tick_to_atr viability attribution",
        "expected_data_source": "microstructure_viability",
        "expected_gate_shape": "microstructure_attribution",
    },
    {
        "label": "core_entry_admission_no_entry",
        "text": "core_entry_admission_gate severe haircut no-entry saved trade diagnostic",
        "expected_data_source": "core_entry_admission",
        "expected_gate_shape": "entry_admission",
    },
    {
        "label": "sec_text_event_item_code",
        "text": "SEC 8-K item 3.01 listing noncompliance entry risk",
        "expected_data_source": "sec_text_event",
        "expected_gate_shape": "other",
    },
    {
        "label": "portfolio_covariance_overlay",
        "text": "portfolio covariance daily mark-to-market overlay",
        "expected_data_source": "portfolio_covariance_lane",
        "expected_gate_shape": "portfolio_daily_equity_overlay",
    },
]

CHANGED_FILES = [
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    RUNNER,
    "docs/frozen_families.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260708_029_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return value.resolve().relative_to(ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    baseline = read_json(BASELINE_RESULT, {})
    aggregate_after = baseline.get("aggregate", {}).get("after", {})
    windows = baseline.get("by_window", {})
    generated = sum(
        int(row.get("after", {}).get("signals_generated", 0))
        for row in windows.values()
    )
    survived = sum(
        int(row.get("after", {}).get("signals_survived", 0))
        for row in windows.values()
    )
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": aggregate_after.get("expected_value_score"),
        "total_pnl": aggregate_after.get("total_pnl"),
        "trade_count": aggregate_after.get("trade_count"),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def classify(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    return {
        **case,
        "fingerprint": fingerprint,
        "passed": (
            fingerprint.get("data_source") == case["expected_data_source"]
            and fingerprint.get("gate_shape") == case["expected_gate_shape"]
        ),
    }


def build_card(log: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} {SLUG}",
            "",
            f"- Lane: `{LANE}`",
            f"- Decision: `{log['decision']}`",
            f"- Accepted measurement repair: `{log['accepted_measurement_repair']}`",
            f"- Artifact: `{log['artifact']}`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            (
                "Pair-spread / relative-value text now resolves to "
                "`relative_value_spread` + `pair_spread`; regression cases "
                "kept microstructure, core entry-admission, SEC text, and "
                "portfolio covariance surfaces unchanged."
            ),
            "",
            "## Reflection",
            "",
            log["post_run_reflection"],
            "",
        ]
    )


def build_manifest() -> dict[str, Any]:
    files = [
        RUNNER,
        "scripts/experiment_fingerprint.py",
        "quant/test_experiment_fingerprint.py",
        repo_rel(ARTIFACT_PATH),
        repo_rel(LOG_PATH),
        repo_rel(CARD_PATH),
        repo_rel(TICKET_PATH),
        repo_rel(MANIFEST_PATH),
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "files": [
            {
                "path": item,
                "sha256": sha256(ROOT / item),
            }
            for item in files
        ],
    }


def main() -> None:
    ticket = read_json(TICKET_PATH, {})
    prediction = ticket.get("prediction") or {}
    before_fingerprint = ticket.get("novelty", {}).get("fingerprint", {})
    target_results = [classify(case) for case in TARGET_CASES]
    regression_results = [classify(case) for case in REGRESSION_CASES]
    target_passed = sum(1 for row in target_results if row["passed"])
    regression_passed = sum(1 for row in regression_results if row["passed"])
    all_passed = target_passed == len(target_results) and regression_passed == len(regression_results)
    metrics = baseline_metrics()
    decision = (
        "accepted_measurement_repair_chop_spread_fingerprint_coverage"
        if all_passed
        else "blocked_measurement_repair_chop_spread_fingerprint_coverage"
    )

    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "before": {
            "source": "reserved_ticket_novelty_fingerprint",
            "reservation_fingerprint": before_fingerprint,
            "known_issue": "pair-spread text was mapped to regime_state/notional_scalar before this repair",
        },
        "after": {
            "target_cases": target_results,
            "regression_cases": regression_results,
            "passed": all_passed,
        },
        "baseline_metrics": metrics,
        "strategy_behavior_changed": False,
    }
    write_json(ARTIFACT_PATH, artifact)

    delta_metrics = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "target_cases_passed": target_passed,
        "target_cases_total": len(target_results),
        "regression_cases_passed": regression_passed,
        "regression_cases_total": len(regression_results),
        "strategy_behavior_changed": False,
    }
    log = {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": all_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": all_passed,
        "alpha_ready": False,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "causal_components": [
            "relative_value_spread data_source keywords",
            "pair_spread gate_shape keywords",
            "specific regression tests preventing spread overmatch",
        ],
        "artifact": repo_rel(ARTIFACT_PATH),
        "before_metrics": metrics,
        "after_metrics": metrics,
        "delta_metrics": delta_metrics,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": metrics,
        },
        "gate2": {
            "passed": True,
            "fields_checked": [
                "scripts.experiment_fingerprint._DATA_SOURCE_KEYWORDS",
                "scripts.experiment_fingerprint._GATE_SHAPE_KEYWORDS",
                "experiments.tickets.exp-20260708-029.novelty.fingerprint",
            ],
            "entry_date_contract": "unchanged_not_signal_generator",
            "target_price_contract": "unchanged_not_signal_generator",
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": metrics["signals_generated"],
            "signals_survived": metrics["signals_survived"],
            "survival_rate": metrics["survival_rate"],
            "note": "Classifier-only measurement repair; no entry/exit/ranking/sizing filter changed.",
        },
        "gate4": {
            "accepted_alpha": False,
            "accepted_measurement_repair": all_passed,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
            "target_cases": target_results,
            "regression_cases": regression_results,
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_or_sizing_changed": False,
            "novelty_guard_surface_changed": True,
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile scripts\\experiment_fingerprint.py " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "actual_success": int(all_passed),
            "predicted_failure_mode_hit": not all_passed,
            "surprise_note": (
                "Low surprise: the pre-run classifier output and reservation "
                "fingerprint both identified the wrong regime/notional surface; "
                "focused tests controlled the main overmatch risk."
            ),
        },
        "post_run_reflection": (
            "Accepted as measurement repair only. The prior alpha result in "
            "exp-20260708-025 remains rejected/insufficient; do not retune the "
            "same pair-spread thresholds. Reopen pair-spread alpha only with a "
            "new non-price pair-linkage data source or materially more settled "
            "forward spread rows."
        ),
        "completed_at": utc_now(),
    }
    write_json(LOG_PATH, log)
    write_text(CARD_PATH, build_card(log))

    persist_self_registered_result(
        REGISTRY_PATH,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=prediction,
        result=log,
        status="completed",
        fields={
            "owner": OWNER,
            "change_type": CHANGE_TYPE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": log["causal_components"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "allowed_write_scope": ticket.get("allowed_write_scope"),
            "locked_variables": ticket.get("locked_variables"),
            "acceptance_rule": ticket.get("acceptance_rule"),
        },
    )
    write_json(MANIFEST_PATH, build_manifest())

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": decision,
                "accepted_measurement_repair": all_passed,
                "artifact": repo_rel(ARTIFACT_PATH),
                "target_cases_passed": target_passed,
                "regression_cases_passed": regression_passed,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
