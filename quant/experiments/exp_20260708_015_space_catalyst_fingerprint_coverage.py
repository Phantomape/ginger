"""exp-20260708-015: space-catalyst fingerprint coverage repair artifact.

This runner writes measurement artifacts only. It does not change signals,
ranking, sizing, exits, paper orders, or live orders.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260708-015"
CHANGED_VARIABLE = "space_catalyst_experiment_fingerprint_data_source_key_v1"
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
ARTIFACT_PATH = OUT_DIR / "exp_20260708_015_space_catalyst_fingerprint_coverage.json"

CLASSIFIER_CASES = [
    {
        "label": "event_state_shadow",
        "text": "space_catalyst event state shadow ledger",
        "prior_data_source": "other",
        "expected_data_source": "space_catalyst",
        "expected_gate_shape": "other",
    },
    {
        "label": "observation_slot_forward_supply",
        "text": "space catalyst observation slot forward supply",
        "prior_data_source": "other",
        "expected_data_source": "space_catalyst",
        "expected_gate_shape": "other",
    },
    {
        "label": "event_ledger_with_forward_replacement",
        "text": "space_catalyst_event_ledger closed decision forward replacement attribution",
        "prior_data_source": "forward_replacement_value",
        "expected_data_source": "space_catalyst",
        "expected_gate_shape": "forward_attribution",
    },
]

REGRESSION_CASES = [
    {
        "label": "generic_forward_replacement",
        "text": "forward replacement value entry_exhaustion attribution",
        "expected_data_source": "forward_replacement_value",
        "expected_gate_shape": "forward_attribution",
    },
    {
        "label": "entity_theme_news",
        "text": "entity-theme news relation observer",
        "expected_data_source": "entity_theme_news",
        "expected_gate_shape": "other",
    },
    {
        "label": "ohlcv_space_word_not_overclassified",
        "text": "launch lunar core pool candidate selection",
        "expected_data_source": "other",
        "expected_gate_shape": "candidate_pool_top1_10d",
    },
]

TARGET_FROZEN_FAMILIES = {
    "space_catalyst_standard_surface_contract": "space_catalyst",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_frozen_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not FROZEN_PATH.exists():
        return rows
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


def _frozen_source_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for family, expected in sorted(TARGET_FROZEN_FAMILIES.items()):
        match = next((row for row in rows if row.get("family_key") == family), None)
        actual = match.get("fingerprint", {}).get("data_source") if match else None
        results.append(
            {
                "family_key": family,
                "expected_data_source": expected,
                "actual_data_source": actual,
                "found": match is not None,
                "passed": actual == expected,
                "row": match,
            }
        )
    return results


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
            "prior_data_source": "other_or_forward_replacement_value",
            "target_family": "space_catalyst_standard_surface_contract",
            "evidence": (
                "Before this repair, the active space_catalyst observer surface "
                "had no dedicated data_source key. Ticket reservation showed "
                "the alpha-blocker wording collapsed into generic "
                "forward_replacement_value, and frozen family rows with the "
                "space_catalyst surface were not reliably keyed to the surface."
            ),
        },
        "alpha_hypothesis": (
            "Space catalyst official-event rows may contain event-relation alpha, "
            "but future alpha retries need the novelty guard to count that "
            "population under a dedicated source key before row-growth or "
            "provenance evidence can be trusted."
        ),
        "production_impact": "No trading behavior changed in before measurement.",
    }


def build_after() -> dict[str, Any]:
    cases = [_classify_case(row) for row in CLASSIFIER_CASES]
    regressions = [_classify_case(row) for row in REGRESSION_CASES]
    frozen_results = _frozen_source_results(_target_frozen_rows())
    accepted = (
        all(row["passed"] for row in cases)
        and all(row["passed"] for row in regressions)
        and all(row["passed"] for row in frozen_results)
    )
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "after",
        "lane": "measurement_repair",
        "hypothesis": (
            "Space catalyst alpha remains parked until materially new closed "
            "forward replacement rows, richer event provenance, or a shared "
            "helper beats accepted comparators. This run only fixes its "
            "novelty/saturation identity."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "decision": (
            "accepted_measurement_repair_space_catalyst_fingerprint_coverage"
            if accepted
            else "blocked_space_catalyst_fingerprint_coverage"
        ),
        "accepted": accepted,
        "summary": {
            "classifier_cases": len(cases),
            "classifier_cases_passed": sum(1 for row in cases if row["passed"]),
            "regression_cases": len(regressions),
            "regression_cases_passed": sum(1 for row in regressions if row["passed"]),
            "target_frozen_families": len(TARGET_FROZEN_FAMILIES),
            "target_frozen_families_found": sum(1 for row in frozen_results if row["found"]),
            "target_frozen_families_passed": sum(1 for row in frozen_results if row["passed"]),
            "derived_frozen_family_view_rebuilt": True,
        },
        "cases": cases,
        "regressions": regressions,
        "target_frozen_families": frozen_results,
        "gate_contract": {
            "gate_1_baseline": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "gate_2_runtime_fields": "Not a signal generator; entry_date and target_price contracts are unchanged.",
            "gate_3_survival": "Not a signal filter; survival is unchanged.",
            "gate_4_rule": "Accept repair when focused tests pass and the rebuilt frozen family view keys space_catalyst_standard_surface_contract to space_catalyst without overclassifying generic forward-replacement or launch/lunar text.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "trade_enabled": False,
            "scope": "novelty_guard_measurement_only",
        },
        "next_reopen_condition": (
            "Space catalyst alpha still requires materially new closed forward "
            "replacement-value rows beyond the current 18 closed decisions, "
            "richer official event provenance, or a shared default-off helper "
            "that beats accepted comparators."
        ),
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
            "quant/experiments/exp_20260708_015_space_catalyst_fingerprint_coverage.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260708_015_space_catalyst_fingerprint_coverage.py",
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
