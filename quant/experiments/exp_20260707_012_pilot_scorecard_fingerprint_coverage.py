"""exp-20260707-012: pilot scorecard fingerprint coverage repair artifact."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260707-012"
CHANGED_VARIABLE = "pilot_scorecard_fingerprint_coverage"
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
ARTIFACT_PATH = OUT_DIR / "exp_20260707_012_pilot_scorecard_fingerprint_coverage.json"

CASES = [
    {
        "label": "kill_readiness",
        "text": "pilot_scorecard_kill_graduate_readiness current pilot scorecard kill rule readiness",
    },
    {
        "label": "graduation_readiness",
        "text": "pilot scorecard graduation readiness current pilot recommendations",
    },
    {
        "label": "recommendations_file",
        "text": "data/pilots/pilot_recommendations_2026-07-07.json scorecard kill verdict",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pilot_frozen_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in FROZEN_PATH.read_text(encoding="utf-8").splitlines():
        if "pilot_scorecard" not in line:
            continue
        rows.append(json.loads(line))
    return rows


def _classify(text: str) -> dict[str, Any]:
    fingerprint = fp.infer_fingerprint(text)
    return {
        "text": text,
        "fingerprint": fingerprint,
        "passed": (
            fingerprint.get("data_source") == "pilot_scorecard"
            and fingerprint.get("gate_shape") == "pilot_scorecard_readiness"
        ),
    }


def build_before() -> dict[str, Any]:
    ticket = _load_json(TICKET_PATH)
    reservation_fp = ticket.get("novelty", {}).get("fingerprint", {})
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "before",
        "changed_variable": CHANGED_VARIABLE,
        "source": "reservation_novelty_fingerprint",
        "reservation_fingerprint": reservation_fp,
        "guard_gap_present": (
            reservation_fp.get("data_source") == "other"
            or reservation_fp.get("gate_shape") == "other"
        ),
        "nearest_before": ticket.get("novelty", {}).get("nearest", [])[:5],
        "production_impact": "No trading behavior changed in before measurement.",
    }


def build_after() -> dict[str, Any]:
    cases = [_classify(row["text"]) | {"label": row["label"]} for row in CASES]
    frozen_rows = _pilot_frozen_rows()
    frozen_passed = all(
        row.get("fingerprint", {}).get("data_source") == "pilot_scorecard"
        and row.get("fingerprint", {}).get("gate_shape") == "pilot_scorecard_readiness"
        for row in frozen_rows
    )
    cases_passed = all(row["passed"] for row in cases)
    accepted = bool(cases_passed and frozen_rows and frozen_passed)
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "phase": "after",
        "lane": "measurement_repair",
        "hypothesis": (
            "Pilot scorecard readiness and kill-rule alpha governance remains "
            "vulnerable to repeated same-surface probes while experiment_fingerprint "
            "classifies pilot_scorecard families as other/other."
        ),
        "changed_variable": CHANGED_VARIABLE,
        "decision": (
            "accepted_measurement_repair_pilot_scorecard_fingerprint_coverage"
            if accepted
            else "blocked_pilot_scorecard_fingerprint_coverage"
        ),
        "accepted": accepted,
        "summary": {
            "classifier_cases": len(cases),
            "classifier_cases_passed": sum(1 for row in cases if row["passed"]),
            "pilot_frozen_rows": len(frozen_rows),
            "pilot_frozen_rows_passed": sum(
                1
                for row in frozen_rows
                if row.get("fingerprint", {}).get("data_source") == "pilot_scorecard"
                and row.get("fingerprint", {}).get("gate_shape") == "pilot_scorecard_readiness"
            ),
            "derived_frozen_family_view_rebuilt": True,
        },
        "cases": cases,
        "pilot_frozen_families": frozen_rows,
        "gate_contract": {
            "gate_1_baseline": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "gate_2_runtime_fields": "Not a signal generator; entry_date and target_price contracts are unchanged.",
            "gate_3_survival": "Not a signal filter; survival is unchanged.",
            "gate_4_rule": "Accept repair when focused tests pass and pilot scorecard frozen rows rebuild with a concrete source and gate shape.",
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
            "quant/experiments/exp_20260707_012_pilot_scorecard_fingerprint_coverage.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260707_012_pilot_scorecard_fingerprint_coverage.py",
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
