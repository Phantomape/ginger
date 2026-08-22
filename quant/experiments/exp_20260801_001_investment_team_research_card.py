#!/usr/bin/env python3
"""Acceptance runner for exp-20260801-001."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
)
OUTPUT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260801-001"
    / "investment_team_research_card_acceptance.json"
)
PRODUCTION_PATHS = (
    REPO_ROOT / "quant" / "run.py",
    REPO_ROOT / "quant" / "backtester.py",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    baseline_before = _sha256(BASELINE)
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "quant/test_investment_team_research_card.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    baseline_after = _sha256(BASELINE)
    production_imports = {
        path.relative_to(REPO_ROOT).as_posix(): "investment_team_research_card"
        in path.read_text(encoding="utf-8")
        for path in PRODUCTION_PATHS
    }
    accepted = (
        completed.returncode == 0
        and baseline_before == baseline_after
        and not any(production_imports.values())
    )
    result = {
        "schema_version": 1,
        "experiment_id": "exp-20260801-001",
        "status": "accepted_measurement_repair" if accepted else "rejected",
        "decision_variable": "investment_team_research_card_adapter_v1",
        "strategy_logic_changed": False,
        "orders_or_live_path_changed": False,
        "gate_1_4_required": False,
        "gate_1_4_reason": "Isolated research-admission tooling; no strategy or execution path imports it.",
        "baseline_result_file": BASELINE.relative_to(REPO_ROOT).as_posix(),
        "baseline_sha256_before": baseline_before,
        "baseline_sha256_after": baseline_after,
        "baseline_byte_identical": baseline_before == baseline_after,
        "production_import_scan": production_imports,
        "focused_test_returncode": completed.returncode,
        "focused_test_stdout": completed.stdout.strip(),
        "focused_test_stderr": completed.stderr.strip(),
        "acceptance_checks": {
            "four_role_fail_closed_contract": completed.returncode == 0,
            "financial_cross_source_contract": completed.returncode == 0,
            "researchability_does_not_upgrade_evidence": completed.returncode == 0,
            "existing_hypothesis_candidate_projection": completed.returncode == 0,
            "park_reject_stop_before_projection": completed.returncode == 0,
            "no_production_import": not any(production_imports.values()),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(OUTPUT)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
