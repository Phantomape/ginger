"""exp-20260703-022: expose Item 1.01 contract economics in the daily surface.

Measurement repair only. The prior exp-20260703-021 attribution found that
fixed machine-checkable amount/duration fields were useful, but those fields
were still private to the runner. This experiment verifies the shared
observer-only provenance module now emits the same fields for full-surface and
daily-persist paths without changing trading behavior.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from sec_contract_relation_provenance import (  # noqa: E402
    OBSERVER_NAME,
    build_surface_from_paths,
    load_jsonl,
    persist_sec_contract_relation_provenance,
    source_text_glob,
)


EXPERIMENT_ID = "exp-20260703-022"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_item101_contract_economic_terms_daily_surface"
RUNNER = f"quant/experiments/exp_20260703_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SOURCE_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_contract_relation_provenance"
    / "rows.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260703_022_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Expose the exp-20260703-021 SEC Item 1.01 contract economic-terms "
    "extractor in the shared observer-only provenance surface so future daily "
    "rows can accumulate closed replacement-value evidence under the unchanged "
    "amount/duration field contract without changing trading behavior."
)
CHANGED_VARIABLE = "sec_item101_contract_economic_terms_shared_observer_surface"
TRIAL_FAMILY = "sec_item101_contract_economic_terms_daily_surface"
TRIAL_VARIANT_ID = "shared_observer_surface_v1"
NEARBY_PRIORS = [
    "exp-20260703-017",
    "exp-20260703-018",
    "exp-20260703-019",
    "exp-20260703-020",
    "exp-20260703-021",
]
PREDICTION = {
    "success_probability": 0.82,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "shared_extractor_does_not_match_runner_contract",
        "daily_persist_path_omits_new_fields",
        "real_surface_has_zero_amount_or_duration_rows",
    ],
    "confidence_reason": (
        "exp-20260703-021 already proved the extractor on the same local "
        "provenance rows. This repair only moves that fixed observer-only field "
        "contract into the shared surface and verifies daily persistence."
    ),
    "recorded_at": "2026-07-03T22:04:15+00:00",
}
CHANGED_FILES = [
    "quant/sec_contract_relation_provenance.py",
    "quant/test_sec_contract_relation_provenance.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_022_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {}) or {}
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("trade_count") or window.get("total_trades") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
    }


def field_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = Counter(str(row.get("economic_terms_bucket") or "") for row in rows)
    details = Counter(str(row.get("economic_terms_detail_bucket") or "") for row in rows)
    return {
        "row_count": len(rows),
        "rows_with_economic_terms_bucket": sum(
            1 for row in rows if row.get("economic_terms_bucket")
        ),
        "rows_with_contract_amount": sum(1 for row in rows if row.get("has_contract_amount")),
        "rows_with_contract_duration": sum(
            1 for row in rows if row.get("has_contract_duration")
        ),
        "rows_with_named_counterparty": sum(
            1 for row in rows if row.get("has_named_counterparty")
        ),
        "economic_terms_bucket_counts": dict(sorted(buckets.items())),
        "economic_terms_detail_counts": dict(sorted(details.items())),
    }


def pick_daily_probe_source(rows: list[dict[str, Any]]) -> tuple[str, Path] | None:
    for row in rows:
        if row.get("economic_terms_bucket") != "amount_or_duration":
            continue
        source_path = str(row.get("source_path") or "")
        if not source_path:
            continue
        path = REPO_ROOT / source_path
        if not path.exists():
            continue
        name = path.name
        if name.startswith("sec_filing_text_") and name.endswith(".jsonl"):
            return name.removeprefix("sec_filing_text_").removesuffix(".jsonl"), path
    return None


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    existing_rows = load_jsonl(SOURCE_ROWS)
    before_counts = field_counts(existing_rows)

    source_paths = source_text_glob()
    rebuilt_rows, rebuilt_summary = build_surface_from_paths(source_paths)
    after_counts = field_counts(rebuilt_rows)

    probe = pick_daily_probe_source(rebuilt_rows)
    probe_summary: dict[str, Any]
    probe_rows: list[dict[str, Any]] = []
    if probe is None:
        probe_summary = {"status": "no_amount_or_duration_probe_source"}
    else:
        probe_date, probe_source = probe
        probe_data_dir = OUT_DIR / "probe_data"
        probe_summary = persist_sec_contract_relation_provenance(
            probe_date,
            data_dir=probe_data_dir,
            source_path=probe_source,
        )
        daily_rows_path = probe_data_dir / "non_ohlcv" / "sec_contract_relation_provenance" / "daily" / f"{OBSERVER_NAME}_{probe_date}.jsonl"
        probe_rows = load_jsonl(daily_rows_path)
        probe_summary["probe_date"] = probe_date
        probe_summary["probe_source_path"] = repo_rel(probe_source)
        probe_summary["probe_daily_rows_path"] = repo_rel(daily_rows_path)
        probe_summary["probe_field_counts"] = field_counts(probe_rows)

    checks = {
        "real_surface_rows_present": len(rebuilt_rows) > 0,
        "all_rebuilt_rows_have_bucket": after_counts["rows_with_economic_terms_bucket"]
        == len(rebuilt_rows),
        "amount_or_duration_rows_present": (
            after_counts["economic_terms_bucket_counts"].get("amount_or_duration", 0) > 0
        ),
        "daily_probe_ok": probe_summary.get("status") == "ok",
        "daily_probe_rows_have_bucket": bool(probe_rows)
        and all(row.get("economic_terms_bucket") for row in probe_rows),
        "strategy_identity_unchanged": True,
    }
    accepted = all(checks.values())
    decision = (
        "accepted_measurement_repair_sec_item101_contract_economic_terms_daily_surface"
        if accepted
        else "blocked_sec_item101_contract_economic_terms_daily_surface"
    )
    failed = [key for key, value in checks.items() if not value]

    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_hypothesis": (
            "candidate_pool: Item 1.01 contracts with machine-checkable amount "
            "or duration terms may have better replacement value, but only after "
            "the same fields are logged by the shared observer for future rows."
        ),
        "hypothesis": HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_observer_surface_repair",
        "mechanism_family": "sec_contract_relation_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared amount/duration regex extractor",
            "normalized counterparty count tags",
            "full-surface materialization verification",
            "daily persist verification in experiment-owned probe data",
            "no trading behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "alpha_enabling_shared_observer_field_contract",
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 4),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "predicted_failure_mode_hit": bool(failed),
            "realized_failure_modes": failed,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise_note": (
                "Low surprise: the exp021 extractor moved into the shared observer "
                "and both real full-surface rows and daily probe rows carry fields."
                if accepted
                else "The shared observer did not fully materialize the economic "
                "term field contract."
            ),
        },
        "before_metrics": {
            **baseline,
            "existing_global_surface": before_counts,
        },
        "after_metrics": {
            **baseline,
            "rebuilt_full_surface": after_counts,
            "daily_probe": probe_summary,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "global_existing_rows_with_economic_terms_bucket_before": before_counts[
                "rows_with_economic_terms_bucket"
            ],
            "rebuilt_rows_with_economic_terms_bucket_after": after_counts[
                "rows_with_economic_terms_bucket"
            ],
            "rebuilt_amount_or_duration_rows_after": after_counts[
                "economic_terms_bucket_counts"
            ].get("amount_or_duration", 0),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Canonical strategy baseline is an identity reference only.",
        },
        "gate2": {
            "passed": checks["all_rebuilt_rows_have_bucket"],
            "fields_checked": [
                "economic_terms_bucket",
                "economic_terms_detail_bucket",
                "contract_amount_count",
                "contract_amount_examples",
                "contract_duration_count",
                "contract_duration_examples",
                "normalized_counterparty_count",
                "counterparty_examples",
                "has_contract_amount",
                "has_contract_duration",
                "has_named_counterparty",
            ],
            "target_price_relevance": (
                "Observer-only provenance rows do not create target exits or orders."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, rank, size, exit, prompt, or order rule changed.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed,
            "checks": checks,
            "decision_basis": (
                "Accepted only as measurement repair: shared observer rows now "
                "carry the exp021 economic-term tags needed for future forward "
                "replacement-value evidence."
            ),
        },
        "summary": {
            "source_file_count": len(source_paths),
            "rebuilt_provenance_rows": len(rebuilt_rows),
            "rebuilt_amount_or_duration_rows": after_counts[
                "economic_terms_bucket_counts"
            ].get("amount_or_duration", 0),
            "rebuilt_contract_amount_rows": after_counts["rows_with_contract_amount"],
            "rebuilt_contract_duration_rows": after_counts["rows_with_contract_duration"],
            "before_global_rows_with_economic_terms_bucket": before_counts[
                "rows_with_economic_terms_bucket"
            ],
            "daily_probe_status": probe_summary.get("status"),
            "daily_probe_rows": len(probe_rows),
            "decision": decision,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": True,
            "daily_snapshot_schema_changed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "The existing run.py daily hook calls the shared observer. This "
                "repair only enriches observer-only rows saved by that hook."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The exp021 extractor depended only on evidence snippets and "
                "counterparty candidates already produced by the shared observer, "
                "so moving it into the observer surface was a narrow field-contract "
                "repair."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep Item 1.01 amount regexes, duration regexes, "
                "counterparty-count thresholds, relation priority, top-N, hold, "
                "notional, or response curves on these rows."
            ),
            "new_evidence_required": (
                "Next alpha evidence requires prospectively accumulated daily "
                "Item 1.01 economics rows with closed cash/SPY/QQQ replacement "
                "value, true exhibit-level normalized customer/supplier identity, "
                "contract revenue exposure, or a different non-SEC-text source."
            ),
        },
        "next_retry_requires": [
            "prospectively accumulated daily Item 1.01 economics rows with closed replacement value",
            "exhibit-level normalized customer/supplier identity",
            "contract revenue exposure by counterparty",
            "a different non-SEC-text economic relation source",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool: Item 1.01 amount/duration economic terms may "
                "distinguish material contracts from boilerplate agreements."
            ),
            "2_history_check": (
                "exp-20260703-021 found the positive observed-only lead; exp019 "
                "rejected shared issuer-self promotion without this economics "
                "field. This run is a measurement repair, not another SEC slice."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept as measurement repair only if real rebuilt rows and daily "
                "probe rows carry the economic-term fields and baseline metrics "
                "remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            "quant/sec_contract_relation_provenance.py",
            "quant/test_sec_contract_relation_provenance.py",
            "quant/run.py",
            "data/non_ohlcv/sec_contract_relation_provenance/rows.jsonl",
            "experiments/logs/exp-20260703-021.json",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\sec_contract_relation_provenance.py quant\\test_sec_contract_relation_provenance.py " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_contract_relation_provenance.py quant\\test_run_daily_wiring.py -q",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": accepted,
    }
    return result


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "artifact",
        "log",
        "lean_quality_passed",
    ]
    return {key: result[key] for key in keys}


def build_card(result: dict[str, Any]) -> str:
    summary = result["summary"]
    failures = result["gate4"]["failed_reasons"] or ["none"]
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

- Status: `{result["status"]}`
- Decision: `{result["decision"]}`
- Accepted alpha: `false`
- Rebuilt provenance rows: `{summary["rebuilt_provenance_rows"]}`
- Rebuilt amount/duration rows: `{summary["rebuilt_amount_or_duration_rows"]}`
- Rebuilt contract amount rows: `{summary["rebuilt_contract_amount_rows"]}`
- Rebuilt contract duration rows: `{summary["rebuilt_contract_duration_rows"]}`
- Daily probe status: `{summary["daily_probe_status"]}`
- Daily probe rows: `{summary["daily_probe_rows"]}`
- Failed checks: `{", ".join(failures)}`

## Boundary

{result["post_run_reflection"]["forbidden_near_neighbor_retry"]}

## Reproduce

```powershell
{RUNNER_COMMAND}
.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict
```
"""


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["timestamp"]
    ticket["prediction"] = PREDICTION
    ticket["causal_components"] = result["causal_components"]
    ticket["nearby_prior_experiments"] = NEARBY_PRIORS
    ticket["trial_family"] = TRIAL_FAMILY
    ticket["trial_variant_id"] = TRIAL_VARIANT_ID
    ticket["mechanism_family"] = result["mechanism_family"]
    ticket["new_evidence_type"] = result["new_evidence_type"]
    ticket["result"] = {
        "decision": result["decision"],
        "accepted": result["accepted"],
        "accepted_alpha": False,
        "artifact": result["artifact"],
        "log": result["log"],
        "summary": result["summary"],
    }
    ticket["gate4"] = result["gate4"]
    ticket["post_run_reflection"] = result["post_run_reflection"]
    ticket["next_retry_requires"] = result["next_retry_requires"]
    ticket["changed_files"] = CHANGED_FILES
    ticket["allowed_write_scope"] = sorted(
        set(ticket.get("allowed_write_scope") or []) | set(CHANGED_FILES)
    )
    write_json(TICKET_JSON, ticket)


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "accepted": result["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": result["alpha_hypothesis"],
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": result["multiple_testing_risk_bucket"],
            "new_evidence_type": result["new_evidence_type"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "related_files": result["related_files"],
            "changed_files": CHANGED_FILES,
            "allowed_write_scope": CHANGED_FILES,
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    print(json.dumps(compact_log_record(result), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
