"""exp-20260710-013: SEC filing-feature mosaic fingerprint repair.

Measurement repair. The daily SEC filing-feature mosaic is a distinct source
surface from generic SEC text, generic Companyfacts, and generic forward
replacement-value attribution. This runner records the source-key repair and
the current readiness blocker without changing strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-013"
OWNER = "alpha-explore-automation"
LANE = "measurement_repair"
SLUG = "sec_filing_features_fingerprint_repair"
RUNNER = f"quant/experiments/exp_20260710_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import experiment_fingerprint as fp  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FEATURE_SUMMARY = DATA_DIR / "non_ohlcv" / "sec_filing_features_summary_20260709.json"

HYPOTHESIS = (
    "Repair SEC filing feature mosaic fingerprint coverage so "
    "sec_filing_features / sec_filing_text_plus_companyfacts can be tracked as "
    "its own data source before any future source-credibility or "
    "predictability alpha read."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool/forward-attribution: SEC filing-feature source credibility, "
    "low-volume predictability, and text-direction-vs-price buckets may later "
    "explain filing-event replacement value, but current rows lack enough "
    "same-accession economic fields and settled forward outcomes."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "fingerprint_data_source_guard_repair"
MECHANISM_FAMILY = "alpha_novelty_guard_data_source_coverage"
TRIAL_FAMILY = "sec_filing_features_fingerprint_coverage"
TRIAL_VARIANT_ID = "sec_filing_features_source_key_v1"
SINGLE_CAUSAL_VARIABLE = "sec_filing_features_fingerprint_data_source_repair_v1"
CAUSAL_COMPONENTS = [
    "sec_filing_features_data_source_keyword",
    "fingerprint_regression_tests",
    "readiness_blocker_record",
    "no_strategy_change",
]
NEARBY_PRIORS = [
    "exp-20260708-003",
    "exp-20260708-014",
    "exp-20260710-012",
]
NEW_EVIDENCE_AXIS = (
    "Fingerprint classifier repair for a distinct SEC filing-feature mosaic "
    "surface; this changes novelty accounting only, not SEC item lists, text "
    "regexes, thresholds, candidate ranking, holds, notional, or alpha response "
    "shape."
)
ACCEPTANCE_RULE = (
    "Accepted measurement repair if SEC filing-feature examples resolve to "
    "sec_filing_features, forward-attribution and candidate-pool gate shapes are "
    "preserved, generic SEC text remains sec_text_event, SEC filer status "
    "remains sec_filer_status, Companyfacts remains companyfacts_ratio, generic "
    "forward replacement remains forward_replacement_value, and no strategy/live "
    "behavior changes."
)

CHECKS = {
    "feature_forward_attribution": {
        "text": "sec_filing_features source_credibility_bucket predictability_mosaic_bucket forward replacement value attribution",
        "expected_source": "sec_filing_features",
        "expected_shape": "forward_attribution",
    },
    "feature_candidate_pool": {
        "text": "SEC filing feature mosaic low_volume_predictability_bucket candidate pool",
        "expected_source": "sec_filing_features",
        "expected_shape": "candidate_pool_top1_10d",
    },
    "feature_text_plus_companyfacts": {
        "text": "sec_filing_text_plus_companyfacts text_direction_vs_price_bucket source",
        "expected_source": "sec_filing_features",
        "expected_shape": "other",
    },
    "sec_filer_status_control": {
        "text": "sec_cover_page_filer_status_upgrade_candidate_pool",
        "expected_source": "sec_filer_status",
        "expected_shape": "candidate_pool_top1_10d",
    },
    "sec_contract_relation_control": {
        "text": "SEC Item 1.01 contract-relation provenance candidate pool",
        "expected_source": "sec_contract_relation",
        "expected_shape": "candidate_pool_top1_10d",
    },
    "sec_text_control": {
        "text": "SEC 8-K item 3.01 listing noncompliance entry risk",
        "expected_source": "sec_text_event",
        "expected_shape": "other",
    },
    "companyfacts_control": {
        "text": "SEC Companyfacts free cash flow margin quality",
        "expected_source": "companyfacts_ratio",
        "expected_shape": "other",
    },
    "forward_replacement_control": {
        "text": "forward replacement value entry_exhaustion attribution",
        "expected_source": "forward_replacement_value",
        "expected_shape": "forward_attribution",
    },
}

CHANGED_FILES = [
    RUNNER,
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_013_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile scripts\\experiment_fingerprint.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    return value


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(text, encoding="utf-8")
        try:
            tmp.unlink()
        except OSError:
            pass


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


def load_feature_summary() -> dict[str, Any]:
    if not FEATURE_SUMMARY.exists():
        return {"exists": False, "path": repo_rel(FEATURE_SUMMARY)}
    payload = json.loads(FEATURE_SUMMARY.read_text(encoding="utf-8"))
    return {
        "exists": True,
        "path": repo_rel(FEATURE_SUMMARY),
        "rows_written": payload.get("rows_written"),
        "pit_safe_rows": payload.get("pit_safe_rows"),
        "rows_with_same_accession_facts": payload.get("rows_with_same_accession_facts"),
        "rows_with_filer_status": payload.get("rows_with_filer_status"),
        "field_counts": payload.get("field_counts", {}),
        "filer_status_parse_counts": payload.get("filer_status_parse_counts", {}),
        "pit_caveat": payload.get("pit_caveat"),
    }


def run_checks() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, spec in CHECKS.items():
        actual = fp.infer_fingerprint(spec["text"])
        source_ok = actual["data_source"] == spec["expected_source"]
        shape_ok = actual["gate_shape"] == spec["expected_shape"]
        results[name] = {
            **spec,
            "actual": actual,
            "source_ok": source_ok,
            "shape_ok": shape_ok,
            "passed": source_ok and shape_ok,
        }
    return results


def build_payload() -> dict[str, Any]:
    checks = run_checks()
    failed = [name for name, result in checks.items() if not result["passed"]]
    summary = load_feature_summary()
    readiness_blockers = []
    if not summary.get("exists"):
        readiness_blockers.append("missing_sec_filing_features_summary")
    if (summary.get("rows_written") or 0) < 100:
        readiness_blockers.append("feature_rows_below_alpha_sample_floor")
    if (summary.get("rows_with_same_accession_facts") or 0) < 50:
        readiness_blockers.append("same_accession_companyfacts_rows_too_thin")
    field_counts = summary.get("field_counts") or {}
    economic_fields = [
        "fcf_to_net_income_gap",
        "gross_margin_delta",
        "inventory_growth",
        "receivables_growth",
    ]
    if sum(int(field_counts.get(field) or 0) for field in economic_fields) < 50:
        readiness_blockers.append("economic_feature_fields_unpopulated")

    accepted = not failed
    decision = (
        "accepted_measurement_repair_sec_filing_features_fingerprint_coverage"
        if accepted
        else "blocked_sec_filing_features_fingerprint_coverage"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_guard_coverage",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "feature_summary": summary,
        "alpha_readiness": {
            "alpha_ready": False,
            "blockers": readiness_blockers,
            "note": (
                "This run deliberately does not test an alpha. Current feature "
                "rows and same-accession/economic fields are too thin for a "
                "Gate 1-4 candidate-pool or forward-attribution read."
            ),
        },
        "fingerprint_checks": checks,
        "headline_metrics": {
            "checks_total": len(checks),
            "checks_passed": sum(1 for result in checks.values() if result["passed"]),
            "failed_checks": failed,
            "sec_filing_feature_rows": summary.get("rows_written"),
            "same_accession_companyfacts_rows": summary.get("rows_with_same_accession_facts"),
            "strategy_behavior_delta": 0,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "note": "Measurement repair only; no before/after strategy replay.",
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields": [
                "experiment_fingerprint._DATA_SOURCE_KEYWORDS",
                "experiment_fingerprint.infer_fingerprint",
                "sec_filing_features",
                "sec_filing_text_plus_companyfacts",
                "source_credibility_bucket",
                "predictability_mosaic_bucket",
            ],
            "entry_date_target_price_applicability": (
                "Not applicable: this runner changes novelty accounting only "
                "and emits no trading signals."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "note": "No buy/sell/filter/ranking behavior changed.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
            "failed_reasons": failed,
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_sizing_exits_changed": False,
            "novelty_guard_accounting_changed": True,
            "daily_snapshot_exposed": False,
            "live_ready": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The keyword table had specific keys for SEC filer status, "
                "SEC contract relation, generic SEC text, Companyfacts, and "
                "forward replacement rows, but not the combined SEC filing-"
                "feature mosaic. Proposals mentioning both SEC text, "
                "Companyfacts, and replacement value were therefore routed to "
                "the wrong source population."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair as alpha evidence. Future "
                "sec_filing_features work still needs materially more PIT "
                "feature rows with same-accession/economic fields and settled "
                "cash/SPY/QQQ replacement value, or a distinct non-SEC data "
                "source. Do not sweep SEC forms/items, text regexes, "
                "credibility bucket labels, top-N, hold, cooldown, notional, "
                "or response shape on the current 17 rows."
            ),
            "new_evidence_required": (
                "A valid next alpha ticket should fingerprint as "
                "sec_filing_features and provide enough settled rows and "
                "populated economic fields for Gate 1-4 or a declared "
                "observed-only replacement-value read."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    metrics = payload["headline_metrics"]
    failed = ", ".join(metrics["failed_checks"]) or "none"
    blockers = ", ".join(payload["alpha_readiness"]["blockers"]) or "none"
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Filing-Feature Fingerprint Repair",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Checks passed: `{metrics['checks_passed']}/{metrics['checks_total']}`",
            f"- Failed checks: `{failed}`",
            f"- Alpha readiness blockers: `{blockers}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    atomic_write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=False)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": "measurement_repair_sec_filing_features_fingerprint_coverage",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "feature_summary": payload["feature_summary"],
            "alpha_readiness": payload["alpha_readiness"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    atomic_write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
                "alpha_readiness": payload["alpha_readiness"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
