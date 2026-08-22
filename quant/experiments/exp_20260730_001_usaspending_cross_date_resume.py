"""Verification harness for exp-20260730-001.

Runs only fixture-backed USAspending producer/wiring tests plus syntax checks.
It never calls the network, writes production observer state, or changes trading
behavior.  The JSON emitted on stdout is the reproducible closeout evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE1 = (
    ROOT
    / "data/backtests/"
    "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)


def _run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    match = re.search(r"(\d+) passed", output)
    return {
        "command": command,
        "returncode": completed.returncode,
        "passed": int(match.group(1)) if match else 0,
        "output_tail": output.strip().splitlines()[-5:],
    }


def main() -> int:
    producer_tests = _run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "quant/test_usaspending_obligation_observer.py",
            "-k",
            "pending or producer",
            "-q",
        ]
    )
    wiring_tests = _run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "quant/test_run_daily_wiring.py",
            "-k",
            "usaspending",
            "-q",
        ]
    )
    compile_check = _run(
        [
            sys.executable,
            "-B",
            "-m",
            "py_compile",
            "quant/usaspending_obligation_observer.py",
            "quant/run.py",
            "quant/test_usaspending_obligation_observer.py",
            "quant/test_run_daily_wiring.py",
        ]
    )
    gate1_sha256 = hashlib.sha256(GATE1.read_bytes()).hexdigest()
    checks = {
        "producer_fixture_tests_pass": producer_tests["returncode"] == 0,
        "daily_wiring_tests_pass": wiring_tests["returncode"] == 0,
        "pycompile_pass": compile_check["returncode"] == 0,
        "gate1_identity_unchanged": gate1_sha256
        == "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731",
    }
    report = {
        "experiment_id": "exp-20260730-001",
        "measurement_type": "usaspending_cross_date_pending_job_drain_contract",
        "checks": checks,
        "producer_tests": producer_tests,
        "daily_wiring_tests": wiring_tests,
        "compile_check": compile_check,
        "gate1_sha256": gate1_sha256,
        "network_attempted": False,
        "production_observer_state_written": False,
        "strategy_or_trade_behavior_changed": False,
        "passed": all(checks.values()),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
