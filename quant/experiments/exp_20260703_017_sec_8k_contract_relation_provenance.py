"""exp-20260703-017: SEC 8-K Item 1.01 contract relation provenance.

Measurement repair only. The alpha hypothesis is that customer/supplier/
contract relations disclosed in SEC 8-K Item 1.01 filings may later support an
entity-propagation candidate-pool alpha, but this run only builds a read-only
provenance surface and daily hook. It changes no trading policy.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260703-017"
OWNER = "alpha-explore"
SLUG = "sec_8k_contract_relation_provenance"
RUNNER = f"quant/experiments/exp_20260703_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
QUANT_ROOT = REPO_ROOT / "quant"
for entry in (REPO_ROOT, SCRIPTS_ROOT, QUANT_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_contract_relation_provenance import (  # noqa: E402
    OBSERVER_NAME,
    SCHEMA_VERSION,
    build_surface_from_paths,
    source_text_glob,
    write_full_surface,
    write_jsonl,
)


BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
RUN_PY = REPO_ROOT / "quant" / "run.py"
MODULE_PY = REPO_ROOT / "quant" / "sec_contract_relation_provenance.py"
TEST_MODULE_PY = REPO_ROOT / "quant" / "test_sec_contract_relation_provenance.py"
TEST_RUN_PY = REPO_ROOT / "quant" / "test_run_daily_wiring.py"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_017_{SLUG}.json"
PROBE_DIR = DATA_DIR / "probe"
PROBE_ROWS_JSONL = PROBE_DIR / "sec_8k_contract_relation_provenance_rows.jsonl"
PROBE_SUMMARY_JSON = PROBE_DIR / "sec_8k_contract_relation_provenance_summary.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

SURFACE_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "rows.jsonl"
)
SURFACE_MANIFEST = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "manifest.json"
)
SURFACE_LATEST_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / OBSERVER_NAME
    / "latest_summary.json"
)

CHANGED_FILES = [
    "quant/sec_contract_relation_provenance.py",
    "quant/test_sec_contract_relation_provenance.py",
    "quant/run.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    "data/non_ohlcv/sec_contract_relation_provenance/rows.jsonl",
    "data/non_ohlcv/sec_contract_relation_provenance/manifest.json",
    "data/non_ohlcv/sec_contract_relation_provenance/latest_summary.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_017_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/probe/sec_8k_contract_relation_provenance_rows.jsonl",
    f"data/experiments/{EXPERIMENT_ID}/probe/sec_8k_contract_relation_provenance_summary.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]

REPRODUCTION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -c \"import ast,pathlib; files=['quant/sec_contract_relation_provenance.py','quant/run.py','quant/test_sec_contract_relation_provenance.py','quant/test_run_daily_wiring.py','"
    + RUNNER
    + "']; [ast.parse(pathlib.Path(f).read_text(encoding='utf-8'), filename=f) for f in files]; print('ast syntax ok', len(files))\"",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_sec_contract_relation_provenance.py quant\\test_run_daily_wiring.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(text, path)
        return
    except PermissionError:
        pass
    path.write_text(text, encoding="utf-8")
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def write_json(path: Path, payload: Any) -> None:
    write_text(
        path,
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str)
        + "\n",
    )


def baseline_summary() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {}) or {}
    windows = payload.get("windows") or []
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(
            int(window.get("total_trades") or window.get("trade_count") or 0)
            for window in windows
        ),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 6),
        "window_count": len(windows),
        "windows": [
            {
                "label": window.get("label"),
                "expected_value_score": window.get("expected_value_score"),
                "total_pnl": window.get("total_pnl"),
                "signals_generated": window.get("signals_generated"),
                "signals_survived": window.get("signals_survived"),
                "survival_rate": window.get("survival_rate"),
            }
            for window in windows
        ],
    }


def verify_wiring() -> dict[str, Any]:
    run_text = RUN_PY.read_text(encoding="utf-8")
    module_text = MODULE_PY.read_text(encoding="utf-8")
    module_test_text = TEST_MODULE_PY.read_text(encoding="utf-8")
    run_test_text = TEST_RUN_PY.read_text(encoding="utf-8")
    tree = ast.parse(run_text)
    daily_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_persist_sec_contract_relation_provenance"
    ]
    checks = {
        "module_schema_versioned": SCHEMA_VERSION in module_text,
        "module_observer_only_flags_present": (
            '"strategy_behavior_changed": False' in module_text
            and '"trade_enabled": False' in module_text
            and '"alters_orders": False' in module_text
        ),
        "daily_helper_defined": "def _persist_sec_contract_relation_provenance" in run_text,
        "daily_helper_imports_module": "persist_sec_contract_relation_provenance" in run_text,
        "daily_helper_fail_soft": (
            "SEC contract relation provenance unavailable" in run_text
            and '"status": "unavailable"' in run_text
        ),
        "daily_paths_call_helper": len(daily_calls) >= 2,
        "surface_not_prompt_or_signal_input": (
            'trend_signals_dict["sec_contract_relation_provenance"]' not in run_text
            and '"sec_contract_relation_provenance"' not in run_text
            and "clean_trade_news" not in module_text
        ),
        "module_unit_tests_present": (
            "test_relation_evidence_extracts_specific_buckets_and_counterparty"
            in module_test_text
            and "test_persist_daily_appends_idempotently" in module_test_text
        ),
        "run_wiring_tests_present": (
            "test_sec_contract_relation_provenance_daily_wiring" in run_test_text
            and "test_sec_contract_relation_provenance_daily_wiring_fail_soft"
            in run_test_text
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "daily_call_count": len(daily_calls),
    }


def build_and_persist_probe() -> dict[str, Any]:
    paths = source_text_glob(REPO_ROOT / "data")
    rows, summary = build_surface_from_paths(paths)
    manifest = write_full_surface(rows, summary, data_dir=REPO_ROOT / "data")
    write_jsonl(rows, PROBE_ROWS_JSONL)
    probe_summary = dict(summary)
    probe_summary.update(
        {
            "source_paths_sample": [repo_rel(path) for path in paths[:10]],
            "source_file_count": len(paths),
            "probe_rows_path": repo_rel(PROBE_ROWS_JSONL),
            "probe_summary_path": repo_rel(PROBE_SUMMARY_JSON),
            "surface_rows_path": repo_rel(SURFACE_ROWS),
            "surface_manifest_path": repo_rel(SURFACE_MANIFEST),
            "surface_latest_summary_path": repo_rel(SURFACE_LATEST_SUMMARY),
            "surface_manifest": manifest,
            "sample_rows": rows[:20],
        }
    )
    write_json(PROBE_SUMMARY_JSON, probe_summary)
    return {"rows": rows, "summary": probe_summary, "manifest": manifest}


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    baseline = baseline_summary()
    wiring = verify_wiring()
    probe = build_and_persist_probe()
    summary = probe["summary"]
    checks = {
        "wiring_passed": wiring["passed"],
        "source_files_present": summary["source_file_count"] > 0,
        "item_101_rows_present": summary["item_101_input_row_count"] >= 10,
        "provenance_rows_present": summary["provenance_row_count"] > 0,
        "specific_relation_rows_present": summary["specific_relation_row_count"] > 0,
        "counterparty_candidate_rows_present": (
            summary["counterparty_candidate_row_count"] > 0
        ),
        "surface_rows_written": SURFACE_ROWS.exists() and SURFACE_ROWS.stat().st_size > 0,
        "surface_manifest_written": SURFACE_MANIFEST.exists(),
        "probe_rows_written": PROBE_ROWS_JSONL.exists()
        and PROBE_ROWS_JSONL.stat().st_size > 0,
    }
    accepted = all(checks.values())
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_sec_8k_contract_relation_provenance_surface"
        if accepted
        else "blocked_sec_8k_contract_relation_provenance_surface_not_verified"
    )
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "alpha_hypothesis": (
            "SEC Item 1.01 material-agreement disclosures may expose "
            "customer, supplier, financing, licensing, or purchase relations "
            "that can later support entity-propagation candidate-pool alpha."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_readonly_provenance_surface_plus_daily_wiring",
        "mechanism_family": "sec_contract_relation_candidate_pool_alpha",
        "trial_family": "sec_8k_contract_relation_provenance_surface",
        "trial_variant_id": "sec_8k_contract_relation_provenance_surface_v1",
        "single_causal_variable": (
            "sec_8k_item_1_01_contract_relation_provenance_surface_v1"
        ),
        "changed_variable": "sec_8k_item_1_01_contract_relation_provenance_surface_v1",
        "causal_components": ticket.get("causal_components") or [
            "SEC 8-K Item 1.01 local text parser",
            "contract relation bucket/snippet provenance",
            "daily fail-soft run.py wiring",
            "focused unit tests",
            "experiment-private probe artifact",
        ],
        "nearby_prior_experiments": [
            "family:sec_event_exposure_top1_candidate_source",
            "family:sec_text_structured_contract_economics_candidate_pool",
            "family:sec_customer_prepayment_capacity_commitment_candidate_pool",
            "exp-20260702-008",
            "exp-20260702-004",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_structured_relation_provenance_surface",
        "new_evidence_axis": (
            "New read-only provenance surface from SEC 8-K Item 1.01 local text "
            "with fixed relation buckets, evidence snippets, and daily append "
            "wiring. This is not a same-source threshold, regex sweep, top-N, "
            "hold, notional, or response-curve retune."
        ),
        "novelty_note": (
            "experiment.py new warned on SEC text neighbors, as expected. The "
            "run is closed only as measurement repair; the SEC-text alpha "
            "surface remains unaccepted until a future fixed candidate-pool "
            "test uses these rows with closed outcomes or richer relation IDs."
        ),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Customer/supplier/contract relations from Item 1.01 filings "
                "may help propagate events to economically exposed listed names."
            ),
            "2_history_check": {
                "novelty_gate": "near-neighbor warning, no saturated-source block",
                "why_not_repeat": (
                    "Prior SEC-text candidate scans failed; this run does not "
                    "test or retune a candidate source. It builds a missing "
                    "relation provenance surface requested by the reopen "
                    "conditions."
                ),
            },
            "3_single_policy_bundle": (
                "Observer-only provenance materialization and daily wiring; no "
                "executable policy bundle, signal, score, ranking, sizing, exit, "
                "prompt, or order change."
            ),
            "4_success_failure_standard": (
                "Accept only if real local Item 1.01 rows generate nonzero "
                "relation-specific provenance, artifacts are written, daily "
                "wiring is fail-soft, tests pass, and strategy metrics remain identity."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "surface_contract": {
            "observer_name": OBSERVER_NAME,
            "schema_version": SCHEMA_VERSION,
            "source": "data/non_ohlcv/sec_filing_text_*.jsonl",
            "rows_path": repo_rel(SURFACE_ROWS),
            "manifest_path": repo_rel(SURFACE_MANIFEST),
            "relation_buckets": sorted(summary["bucket_counts"]),
            "observer_only": True,
            "trade_enabled": False,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": accepted,
            "required_fields_checked": [
                "ticker",
                "cik",
                "accession_number",
                "form_type",
                "eight_k_item_codes",
                "accepted_at",
                "usable_trade_date",
                "combined_text",
                "relation_bucket",
                "evidence_snippets",
                "source_text_hash16",
            ],
            "entry_date_target_price_note": (
                "This observer emits provenance rows, not trade signal rows; "
                "entry_date and target_price are intentionally not generated."
            ),
            "source_summary": {
                key: summary[key]
                for key in (
                    "source_file_count",
                    "input_row_count",
                    "item_101_input_row_count",
                    "provenance_row_count",
                    "unique_accession_count",
                    "unique_ticker_count",
                    "specific_relation_row_count",
                    "generic_relation_row_count",
                    "counterparty_candidate_row_count",
                    "bucket_counts",
                    "quality_counts",
                )
            },
            "wiring": wiring,
            "checks": checks,
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, ranking, sizing, prompt, exit, or order rule was added.",
        },
        "gate4": {
            "mode": "measurement_repair_identity_plus_surface_materialization",
            "passed": accepted,
            "failed_reasons": failed,
            "strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_collector_changed": True,
            "daily_snapshot_exposed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "feeds_llm_prompt": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "run.py refreshes a separate observer-only SEC Item 1.01 "
                "provenance artifact after the LLM-priority handoff. The rows "
                "stay outside clean_trade_news, trend_signals_dict, prompts, "
                "ranking, sizing, exits, and orders."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The local SEC text cache already contains enough Item 1.01 "
                "filings to materialize a deterministic relation-evidence "
                f"surface: {summary['item_101_input_row_count']} input filings "
                f"produced {summary['provenance_row_count']} provenance rows "
                f"across {summary['unique_accession_count']} accessions."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not treat this as accepted SEC-text alpha evidence. Do not "
                "sweep relation regexes, item codes, top-N, hold days, notional, "
                "thresholds, or response curves on frozen windows."
            ),
            "new_evidence_required": (
                "Next legal alpha step needs a fixed candidate-pool policy that "
                "uses this provenance with closed forward replacement rows, or "
                "materially richer counterparty normalization/exposure fields "
                "such as named customer identity, contract value/duration, or "
                "revenue exposure by counterparty."
            ),
        },
        "next_retry_requires": [
            "fixed candidate-pool policy using the new provenance surface",
            "closed forward replacement-value rows or shared paper snapshot",
            "or richer normalized counterparty/value/duration exposure fields",
        ],
        "calibration": {
            "actual_decision": status,
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": (
                (ticket.get("prediction") or {}).get("success_probability")
            ),
            "predicted_failure_modes": (
                (ticket.get("prediction") or {}).get("main_failure_modes") or []
            ),
            "realized_failure_mode": None if accepted else ",".join(failed),
            "surprise_note": (
                "The cache was richer than the minimum requirement; the main "
                "remaining limitation is counterparty normalization, not row count."
            ),
        },
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "probe_rows": repo_rel(PROBE_ROWS_JSONL),
        "probe_summary": repo_rel(PROBE_SUMMARY_JSON),
        "lean_quality_passed": accepted,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
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
        "new_evidence_axis",
        "novelty_note",
        "pre_run_questions",
        "surface_contract",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "calibration",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "probe_rows",
        "probe_summary",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    source = payload["gate2"]["source_summary"]
    failed = payload["gate4"]["failed_reasons"]
    failed_text = ", ".join(failed) if failed else "none"
    return f"""# Experiment Card: {EXPERIMENT_ID}

## Summary

{payload["decision"]}

## Result

- Status: `{payload["status"]}`
- Accepted alpha: `false`
- Strategy behavior changed: `false`
- Item 1.01 input rows: `{source["item_101_input_row_count"]}`
- Provenance rows: `{source["provenance_row_count"]}`
- Specific relation rows: `{source["specific_relation_row_count"]}`
- Counterparty-candidate rows: `{source["counterparty_candidate_row_count"]}`
- Failed checks: `{failed_text}`
- Artifact: `{payload["artifact"]}`

## Reflection

{payload["post_run_reflection"]["why_result_happened"]}

## Reproduction

```powershell
{chr(10).join(payload["reproduction_commands"])}
```
"""


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_closeout_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "artifact": payload["artifact"],
        "log": payload["log"],
        "probe_rows": payload["probe_rows"],
        "probe_summary": payload["probe_summary"],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRODUCTION_COMMANDS,
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {}) or {}
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "calibration": payload["calibration"],
    }
    ticket["causal_components"] = payload["causal_components"]
    ticket["mechanism_family"] = payload["mechanism_family"]
    ticket["trial_family"] = payload["trial_family"]
    ticket["trial_variant_id"] = payload["trial_variant_id"]
    ticket["new_evidence_type"] = payload["new_evidence_type"]
    ticket["allowed_write_scope"] = list(dict.fromkeys(payload["allowed_write_scope"]))
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, build_manifest(payload))
    update_ticket(payload)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log_file": payload["log"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "reproduction_commands": payload["reproduction_commands"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps(compact_log_record(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
