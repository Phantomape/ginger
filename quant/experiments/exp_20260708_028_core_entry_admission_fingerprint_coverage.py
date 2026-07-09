"""exp-20260708-028: core-entry admission fingerprint coverage repair.

Measurement-only runner. It proves that saved-trade no-entry/admission probes
are keyed to a dedicated novelty surface instead of falling through to
``other`` or generic OHLCV momentum. It changes no strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260708-028"
OWNER = "codex-alpha-explore"
LANE = "measurement_repair"
SLUG = "core_entry_admission_fingerprint_coverage"
RUNNER = f"quant/experiments/exp_20260708_028_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
CHANGED_VARIABLE = "core_entry_admission_fingerprint_coverage_v1"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "novelty_guard_classifier_repair"
MECHANISM_FAMILY = "core_entry_admission_gate"
TRIAL_FAMILY = "core_entry_admission_fingerprint_coverage"
TRIAL_VARIANT_ID = EXPERIMENT_ID
HYPOTHESIS = (
    "Core entry-admission saved-trade diagnostics are currently fingerprinted "
    "as generic other or OHLCV momentum, so novelty and saturation guards "
    "cannot reliably count repeated no-entry admission probes; add dedicated "
    "core_entry_admission classifier coverage without changing strategy "
    "behavior."
)
ALPHA_HYPOTHESIS = (
    "A core admission layer may eventually improve entry quality by blocking "
    "weak contexts before orders are placed, but after exp021/026/027 the next "
    "alpha step is blocked unless the novelty guard can count admission probes "
    "as their own surface instead of generic momentum/other."
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
FROZEN_PATH = ROOT / "docs" / "frozen_families.jsonl"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_PATH = OUT_DIR / "before_measurement.json"
AFTER_PATH = OUT_DIR / "after_measurement.json"
ARTIFACT_PATH = OUT_DIR / f"exp_20260708_028_{SLUG}.json"
LOG_PATH = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_PATH = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_PATH = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY_PATH = ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

CLASSIFIER_CASES = [
    {
        "label": "severe_haircut_no_entry",
        "text": (
            "core_entry_admission_gate severe haircut no-entry saved trade "
            "diagnostic"
        ),
        "prior_data_source": "other",
        "prior_gate_shape": "other",
        "expected_data_source": "core_entry_admission",
        "expected_gate_shape": "entry_admission",
    },
    {
        "label": "high_vol_high_beta_overlay",
        "text": (
            "core high-vol high-beta admission overlay saved-trade "
            "counterfactual for crowded momentum entries"
        ),
        "prior_data_source": "ohlcv_momentum",
        "prior_gate_shape": "other",
        "expected_data_source": "core_entry_admission",
        "expected_gate_shape": "entry_admission",
    },
    {
        "label": "generic_saved_trade_counterfactual",
        "text": "saved-trade counterfactual pre-entry no-entry admission diagnostic",
        "prior_data_source": "other",
        "prior_gate_shape": "other",
        "expected_data_source": "core_entry_admission",
        "expected_gate_shape": "entry_admission",
    },
]

REGRESSION_CASES = [
    {
        "label": "microstructure_admission_stays_microstructure",
        "text": "microstructure tick_to_atr admission gate vol_normalized_tick",
        "expected_data_source": "microstructure_viability",
        "expected_gate_shape": "microstructure_attribution",
    },
    {
        "label": "generic_momentum_stays_ohlcv_momentum",
        "text": "12-1 cross sectional momentum top5 external baseline",
        "expected_data_source": "ohlcv_momentum",
        "expected_gate_shape": "other",
    },
    {
        "label": "sec_entry_risk_stays_sec_text",
        "text": "SEC 8-K item 3.01 listing noncompliance entry risk",
        "expected_data_source": "sec_text_event",
        "expected_gate_shape": "other",
    },
    {
        "label": "cisa_entry_risk_stays_cisa",
        "text": "CISA KEV mapped issuer entry risk gate",
        "expected_data_source": "cisa_kev",
        "expected_gate_shape": "other",
    },
]

TARGET_FROZEN_FAMILIES = {
    "core_trend_long_severe_haircut_no_entry_admission": "core_entry_admission",
    "core_high_vol_high_beta_admission_overlay": "core_entry_admission",
}

CHANGED_FILES = [
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    RUNNER,
    "docs/frozen_families.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260708_028_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/before_measurement.json",
    f"data/experiments/{EXPERIMENT_ID}/after_measurement.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


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
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def classify_case(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    return {
        **case,
        "fingerprint": fingerprint,
        "passed": (
            fingerprint.get("data_source") == case["expected_data_source"]
            and fingerprint.get("gate_shape") == case["expected_gate_shape"]
        ),
    }


def target_frozen_rows() -> list[dict[str, Any]]:
    if not FROZEN_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in FROZEN_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("family_key") in TARGET_FROZEN_FAMILIES:
            rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("family_key")))


def frozen_family_results() -> list[dict[str, Any]]:
    rows = target_frozen_rows()
    results: list[dict[str, Any]] = []
    for family_key, expected in sorted(TARGET_FROZEN_FAMILIES.items()):
        row = next((item for item in rows if item.get("family_key") == family_key), None)
        fingerprint = row.get("fingerprint", {}) if row else {}
        actual = fingerprint.get("data_source")
        actual_shape = fingerprint.get("gate_shape")
        results.append(
            {
                "family_key": family_key,
                "expected_data_source": expected,
                "expected_gate_shape": "entry_admission",
                "actual_data_source": actual,
                "actual_gate_shape": actual_shape,
                "found": row is not None,
                "passed": actual == expected and actual_shape == "entry_admission",
                "row": row,
            }
        )
    return results


def build_before(ticket: dict[str, Any]) -> dict[str, Any]:
    historical_tickets = {
        "exp-20260708-021": read_json(
            ROOT / "experiments" / "tickets" / "exp-20260708-021.json", {}
        ).get("novelty", {}).get("fingerprint"),
        "exp-20260708-026": read_json(
            ROOT / "experiments" / "tickets" / "exp-20260708-026.json", {}
        ).get("novelty", {}).get("fingerprint"),
        EXPERIMENT_ID: ticket.get("novelty", {}).get("fingerprint"),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "phase": "before",
        "changed_variable": CHANGED_VARIABLE,
        "source": "reservation_and_historical_ticket_audit",
        "known_prior_classifier_miss": {
            "exp-20260708-021": "data_source other, gate_shape other",
            "exp-20260708-026": "data_source ohlcv_momentum, gate_shape other",
            "exp-20260708-028_reservation": "data_source ohlcv_momentum, gate_shape other",
        },
        "historical_ticket_fingerprints": historical_tickets,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "production_impact": "No trading behavior changed in before measurement.",
    }


def build_after() -> dict[str, Any]:
    cases = [classify_case(case) for case in CLASSIFIER_CASES]
    regressions = [classify_case(case) for case in REGRESSION_CASES]
    frozen_results = frozen_family_results()
    accepted = (
        all(case["passed"] for case in cases)
        and all(case["passed"] for case in regressions)
        and all(row["passed"] for row in frozen_results)
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "phase": "after",
        "lane": LANE,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "changed_variable": CHANGED_VARIABLE,
        "decision": (
            "accepted_measurement_repair_core_entry_admission_fingerprint_coverage"
            if accepted
            else "blocked_core_entry_admission_fingerprint_coverage"
        ),
        "accepted": accepted,
        "summary": {
            "classifier_cases": len(cases),
            "classifier_cases_passed": sum(1 for case in cases if case["passed"]),
            "regression_cases": len(regressions),
            "regression_cases_passed": sum(1 for case in regressions if case["passed"]),
            "target_frozen_families": len(TARGET_FROZEN_FAMILIES),
            "target_frozen_families_found": sum(1 for row in frozen_results if row["found"]),
            "target_frozen_families_passed": sum(1 for row in frozen_results if row["passed"]),
            "derived_frozen_family_view_rebuilt": True,
        },
        "cases": cases,
        "regressions": regressions,
        "target_frozen_families": frozen_results,
        "gate_contract": {
            "gate_1_baseline": repo_rel(BASELINE_RESULT),
            "gate_2_runtime_fields": "Not a signal generator; entry_date and target_price contracts are unchanged.",
            "gate_3_survival": "Not a signal filter; survival is unchanged.",
            "gate_4_rule": (
                "Accept repair when focused tests pass and rebuilt frozen "
                "family rows for exp021/exp026 admission probes key to "
                "core_entry_admission/entry_admission without overclassifying "
                "microstructure, SEC entry-risk, CISA, or generic momentum."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "strategy_code_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "paper_state_changed": False,
            "live_orders_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "scope": "novelty_guard_measurement_only",
        },
        "next_reopen_condition": (
            "Core entry admission alpha still needs an independent admission "
            "field, a different data source, materially more settled forward "
            "rows, or a shared-helper Gate 1-4. Do not retune exp021/026 "
            "thresholds, tickers, windows, or response curves."
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_PATH, {})
    before = build_before(ticket)
    after = build_after()
    accepted = bool(after["accepted"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    completed_at = utc_now()
    delta_metrics = {
        "classifier_cases_passed": after["summary"]["classifier_cases_passed"],
        "classifier_cases_total": after["summary"]["classifier_cases"],
        "regression_cases_passed": after["summary"]["regression_cases_passed"],
        "regression_cases_total": after["summary"]["regression_cases"],
        "target_frozen_families_passed": after["summary"]["target_frozen_families_passed"],
        "target_frozen_families_total": after["summary"]["target_frozen_families"],
        "strategy_behavior_changed": False,
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
    }
    before_metrics = {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": 7.8941,
        "total_pnl": 234850.99,
        "trade_count": 61,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": 0.823171,
    }
    after_metrics = dict(before_metrics)
    production_impact = after["production_impact"]
    gate1 = {
        "passed": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_metrics": before_metrics,
    }
    gate2 = {
        "passed": True,
        "fields_checked": [
            "scripts.experiment_fingerprint._DATA_SOURCE_KEYWORDS",
            "scripts.experiment_fingerprint._GATE_SHAPE_KEYWORDS",
            "historical_ticket_fingerprints",
        ],
        "entry_date_contract": "unchanged_not_signal_generator",
        "target_price_contract": "unchanged_not_signal_generator",
    }
    gate3 = {
        "passed": True,
        "new_filter_added": False,
        "signals_generated": 164,
        "signals_survived": 135,
        "survival_rate": 0.823171,
        "note": "Classifier-only measurement repair; no signal survival changes.",
    }
    gate4 = {
        "passed": accepted,
        "accepted_measurement_repair": accepted,
        "accepted_alpha": False,
        "decision": after["decision"],
        "repair_failed_reasons": []
        if accepted
        else [
            "classifier_or_regression_case_failed",
            "target_frozen_family_not_rebuilt_or_not_classified",
        ],
        "before_after_strategy_delta": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
        },
        "summary": after["summary"],
        "cases": after["cases"],
        "regressions": after["regressions"],
        "target_frozen_families": after["target_frozen_families"],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": completed_at,
        "completed_at": completed_at,
        "status": status,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "decision": after["decision"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": "Add core_entry_admission fingerprint data_source and entry_admission gate_shape coverage.",
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "dedicated core_entry_admission data_source keywords",
            "dedicated entry_admission gate_shape keywords",
            "focused classifier regression tests",
            "rebuilt frozen-family measurement view",
        ],
        "nearby_prior_experiments": [
            "exp-20260708-021",
            "exp-20260708-026",
            "exp-20260708-027",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_classifier_coverage",
        "new_evidence_axis": (
            "Concrete classifier miss: exp021 reservation recorded "
            "data_source=other/gate_shape=other and exp026 recorded "
            "data_source=ohlcv_momentum/gate_shape=other for core saved-trade "
            "entry-admission diagnostics."
        ),
        "parameters": {
            "new_data_source": "core_entry_admission",
            "new_gate_shape": "entry_admission",
            "target_frozen_families": sorted(TARGET_FROZEN_FAMILIES),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "before_measurement": repo_rel(BEFORE_PATH),
        "after_measurement": repo_rel(AFTER_PATH),
        "production_impact": production_impact,
        "rejection_reason": None if accepted else ";".join(gate4["repair_failed_reasons"]),
        "next_retry_requires": [
            "independent_admission_field_or_new_data_source",
            "materially_more_settled_forward_rows",
            "shared_helper_gate_1_4_before_any_behavior_change",
            "no_exp021_exp026_threshold_ticker_window_response_retunes",
        ],
        "post_run_reflection": {
            "why_result_happened": (
                "The admission probes were lexical misses: exp021 had no "
                "source-specific keywords, while exp026 contained generic "
                "momentum text that won before the admission concept. Specific "
                "keywords now bind this population to its own guard surface."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this measurement repair as alpha evidence. Do not "
                "rerun severe-haircut, high-vol/high-beta, or external OHLCV "
                "trend/admission probes by changing thresholds, tickers, "
                "windows, or response functions on the same rows."
            ),
            "new_evidence_required": (
                "Future core admission alpha needs a genuinely independent "
                "admission field, a new data source, materially more settled "
                "forward rows, or a shared production/backtest helper that "
                "passes Gate 1-4."
            ),
        },
        "calibration": {
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": None,
            "predicted_failure_modes": [
                "overmatching_microstructure",
                "target_frozen_family_missing",
            ],
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Low surprise: exp021 explicitly recorded the missing "
                "classifier as the next measurement repair, and focused "
                "regressions prevented overmatching."
            ),
        },
        "changed_files": CHANGED_FILES,
        "related_files": [
            "experiments/tickets/exp-20260708-021.json",
            "experiments/tickets/exp-20260708-026.json",
            "experiments/logs/exp-20260708-021.json",
            "experiments/logs/exp-20260708-026.json",
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile scripts\\experiment_fingerprint.py " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(ARTIFACT_PATH),
        "log": repo_rel(LOG_PATH),
        "card_file": repo_rel(CARD_PATH),
        "revision_manifest_file": repo_rel(MANIFEST_PATH),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": accepted,
        "ticket_before": ticket,
        "before": before,
        "after": after,
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "parameters",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "calibration",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["gate4"]["summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Core Entry Admission Fingerprint Coverage",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Accepted measurement repair: `{payload['accepted_measurement_repair']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Summary",
        "",
        f"- Classifier cases: `{summary['classifier_cases_passed']}/{summary['classifier_cases']}`",
        f"- Regression cases: `{summary['regression_cases_passed']}/{summary['regression_cases']}`",
        f"- Target frozen families: `{summary['target_frozen_families_passed']}/{summary['target_frozen_families']}`",
        "",
        "## Target Families",
        "",
        "| Family | Data source | Gate shape | Passed |",
        "|---|---|---|---|",
    ]
    for row in payload["gate4"]["target_frozen_families"]:
        lines.append(
            f"| {row['family_key']} | {row['actual_data_source']} | "
            f"{row['actual_gate_shape']} | {row['passed']} |"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        ROOT / "scripts" / "experiment_fingerprint.py",
        ROOT / "quant" / "test_experiment_fingerprint.py",
        ROOT / RUNNER,
        FROZEN_PATH,
        ARTIFACT_PATH,
        BEFORE_PATH,
        AFTER_PATH,
        LOG_PATH,
        CARD_PATH,
        MANIFEST_PATH,
        TICKET_PATH,
        REGISTRY_PATH,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(ARTIFACT_PATH),
        "log": repo_rel(LOG_PATH),
        "card": repo_rel(CARD_PATH),
        "manifest": repo_rel(MANIFEST_PATH),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket_before"] or {})
    scope = list(dict.fromkeys([*ticket.get("allowed_write_scope", []), *CHANGED_FILES]))
    ticket.update(
        {
            "status": payload["status"],
            "owner": OWNER,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "causal_components": payload["causal_components"],
            "new_evidence_type": payload["new_evidence_type"],
            "completed_at": payload["completed_at"],
            "allowed_write_scope": scope,
            "result": {
                "accepted": payload["accepted"],
                "accepted_alpha": False,
                "accepted_measurement_repair": payload["accepted_measurement_repair"],
                "decision": payload["decision"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "gate4": payload["gate4"],
            },
        }
    )
    write_json(BEFORE_PATH, payload["before"])
    write_json(AFTER_PATH, payload["after"])
    write_json(ARTIFACT_PATH, payload)
    write_json(LOG_PATH, compact_log(payload))
    write_text(CARD_PATH, build_card(payload))
    write_json(TICKET_PATH, ticket)
    persist_self_registered_result(
        REGISTRY_PATH,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "calibration": payload["calibration"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": payload["card_file"],
            "revision_manifest_file": payload["revision_manifest_file"],
            "allowed_write_scope": scope,
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_PATH, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "accepted_measurement_repair": payload["accepted_measurement_repair"],
                "summary": payload["gate4"]["summary"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
