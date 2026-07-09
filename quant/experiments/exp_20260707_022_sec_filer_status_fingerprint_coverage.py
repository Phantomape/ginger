"""exp-20260707-022: SEC filer-status fingerprint coverage repair artifact.

This runner writes measurement artifacts only. It does not change signals,
ranking, sizing, exits, paper orders, or live orders.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260707-022"
CHANGED_VARIABLE = "sec_periodic_filer_status_data_source_keywords"
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_fingerprint as fp  # noqa: E402


TICKET_PATH = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
FROZEN_PATH = ROOT / "docs" / "frozen_families.jsonl"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
BEFORE_PATH = OUT_DIR / "before_measurement.json"
AFTER_PATH = OUT_DIR / "after_measurement.json"
ARTIFACT_PATH = OUT_DIR / "exp_20260707_022_sec_filer_status_fingerprint_coverage.json"

CLASSIFIER_CASES = [
    {
        "label": "cover_page_candidate_pool",
        "text": "sec_cover_page_filer_status_upgrade_candidate_pool sec_cover_page_filer_status_upgrade_candidate_source_v1",
        "expected_data_source": "sec_filer_status",
        "expected_gate_shape": "candidate_pool_top1_10d",
    },
    {
        "label": "historical_dei_materialization",
        "text": "sec_periodic_historical_dei_status_materialization sec_periodic_historical_dei_status_materialization_v1",
        "expected_data_source": "sec_filer_status",
        "expected_gate_shape": "other",
    },
    {
        "label": "dei_checkbox_parser",
        "text": "sec_dei_cover_status_checkbox_table_parser sec_dei_cover_status_checkbox_table_parser_v1",
        "expected_data_source": "sec_filer_status",
        "expected_gate_shape": "other",
    },
    {
        "label": "cover_xbrl_priority",
        "text": "sec_periodic_cover_xbrl_doc_priority",
        "expected_data_source": "sec_filer_status",
        "expected_gate_shape": "other",
    },
]

REGRESSION_CASES = [
    {
        "label": "generic_sec_item_event",
        "text": "SEC 8-K item 3.01 listing noncompliance entry risk",
        "expected_data_source": "sec_text_event",
    },
    {
        "label": "companyfacts_ratio",
        "text": "SEC Companyfacts free cash flow margin quality",
        "expected_data_source": "companyfacts_ratio",
    },
    {
        "label": "filing_timeliness",
        "text": "quarterly filing timeliness earliness candidate pool",
        "expected_data_source": "filing_timeliness",
    },
]

TARGET_FROZEN_FAMILIES = {
    "post_leadlag_nonrepeat_surface_readiness",
    "sec_10k_10q_cover_page_materialization_probe",
    "sec_cover_page_filer_status_upgrade_candidate_pool",
    "sec_cover_page_status_current_text_parser",
    "sec_dei_cover_status_checkbox_table_parser",
    "sec_dei_cover_status_shared_parser",
    "sec_periodic_cover_xbrl_doc_priority",
    "sec_periodic_historical_dei_status_materialization",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_frozen_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in FROZEN_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("family_key") in TARGET_FROZEN_FAMILIES:
            rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("family_key")))


def _classify_case(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    return {
        **case,
        "fingerprint": fingerprint,
        "passed": (
            fingerprint.get("data_source") == case["expected_data_source"]
            and fingerprint.get("gate_shape") == case["expected_gate_shape"]
        ),
    }


def _classify_regression(case: dict[str, str]) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(case["text"])
    return {
        **case,
        "fingerprint": fingerprint,
        "passed": fingerprint.get("data_source") == case["expected_data_source"],
    }


def build_before() -> dict[str, Any]:
    ticket = _load_json(TICKET_PATH)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "before",
        "changed_variable": CHANGED_VARIABLE,
        "source": "reservation_and_frozen_family_audit",
        "reservation_fingerprint": ticket.get("novelty", {}).get("fingerprint", {}),
        "known_prior_classifier_miss": {
            "data_source": "other",
            "families": sorted(TARGET_FROZEN_FAMILIES),
            "evidence": "Before this repair, frozen_families had SEC cover-page/DEI/filer-status rows in the catch-all source bucket.",
        },
        "production_impact": "No trading behavior changed in before measurement.",
    }


def build_after() -> dict[str, Any]:
    cases = [_classify_case(row) for row in CLASSIFIER_CASES]
    regressions = [_classify_regression(row) for row in REGRESSION_CASES]
    frozen_rows = _target_frozen_rows()
    frozen_family_keys = {str(row.get("family_key")) for row in frozen_rows}
    missing_frozen = sorted(TARGET_FROZEN_FAMILIES - frozen_family_keys)
    frozen_passed = all(
        row.get("fingerprint", {}).get("data_source") == "sec_filer_status"
        for row in frozen_rows
    )
    accepted = (
        all(row["passed"] for row in cases)
        and all(row["passed"] for row in regressions)
        and not missing_frozen
        and frozen_passed
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "after",
        "lane": "measurement_repair",
        "hypothesis": (
            "SEC 10-K/10-Q cover-page and DEI filer-status transition alpha has "
            "already been structurally blocked, but the novelty fingerprint still "
            "classified that family as data_source=other."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "decision": (
            "accepted_measurement_repair_sec_filer_status_fingerprint_coverage"
            if accepted
            else "blocked_sec_filer_status_fingerprint_coverage"
        ),
        "accepted": accepted,
        "summary": {
            "classifier_cases": len(cases),
            "classifier_cases_passed": sum(1 for row in cases if row["passed"]),
            "regression_cases": len(regressions),
            "regression_cases_passed": sum(1 for row in regressions if row["passed"]),
            "target_frozen_families": len(TARGET_FROZEN_FAMILIES),
            "target_frozen_families_found": len(frozen_rows),
            "target_frozen_families_passed": sum(
                1
                for row in frozen_rows
                if row.get("fingerprint", {}).get("data_source") == "sec_filer_status"
            ),
            "missing_target_frozen_families": missing_frozen,
            "derived_frozen_family_view_rebuilt": True,
        },
        "cases": cases,
        "regressions": regressions,
        "target_frozen_families": frozen_rows,
        "gate_contract": {
            "gate_1_baseline": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "gate_2_runtime_fields": "Not a signal generator; entry_date and target_price contracts are unchanged.",
            "gate_3_survival": "Not a signal filter; survival is unchanged.",
            "gate_4_rule": "Accept repair when focused tests pass and target frozen families rebuild with sec_filer_status without overclassifying generic SEC text.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "live_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "scope": "novelty_guard_measurement_only",
        },
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    before = build_before()
    after = build_after()
    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "before": before,
        "after": after,
        "decision": after["decision"],
        "accepted": after["accepted"],
        "changed_files": [
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/frozen_families.jsonl",
            "quant/experiments/exp_20260707_022_sec_filer_status_fingerprint_coverage.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260707_022_sec_filer_status_fingerprint_coverage.py",
        ],
    }
    BEFORE_PATH.write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
    AFTER_PATH.write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "before": BEFORE_PATH.as_posix(),
                "after": AFTER_PATH.as_posix(),
                "artifact": ARTIFACT_PATH.as_posix(),
                "accepted": after["accepted"],
            },
            indent=2,
        )
    )
    return 0 if after["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
