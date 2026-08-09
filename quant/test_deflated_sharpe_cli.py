from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import deflated_sharpe  # noqa: E402


def _returns(values):
    return [
        {"date": f"2026-01-{index + 2:02d}", "return": value}
        for index, value in enumerate(values)
    ]


def _trial(config_id, values):
    return_series = _returns(values)
    return {
        "config_id": config_id,
        "config": {"variant": config_id},
        "attempted": True,
        "selection_scope": "promotion-2026q1-core",
        "window": {"start": "2026-01-02", "end": "2026-01-07"},
        "frequency": "daily",
        "return_basis": "strategy_equity_return",
        "risk_free_assumption": "zero",
        "protocol": "canonical-v1",
        "data": "snapshot-sha256:abc",
        "cost": {"model": "round-trip-v2"},
        "return_series": return_series,
        "return_series_sha256": hashlib.sha256(
            json.dumps(
                {"schema": "dated_periodic_return_series_v1", "rows": return_series},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "return_series_source": f"data/backtests/{config_id}.json#sharpe_inference",
    }


def _payload():
    trials = [
        _trial("winner", [0.01, -0.004, 0.006, -0.002, 0.008, 0.001]),
        _trial("loser-a", [-0.003, 0.009, -0.001, 0.007, -0.004, 0.005]),
        _trial("loser-b", [0.006, -0.002, 0.009, -0.005, 0.004, 0.003]),
    ]
    return {
        "selected_config_id": "winner",
        "expected_attempt_count": 3,
        "selection_pool_complete": True,
        "periods_per_year": 252,
        "expected_return_dates": [row["date"] for row in trials[0]["return_series"]],
        "trials": trials,
    }


def test_build_report_normalizes_computed_panel_for_gate5():
    report = deflated_sharpe.build_report(_payload())
    gate5 = report["gate5_dsr_report"]

    assert report["status"] == "computable"
    assert gate5["status"] == "computed"
    assert gate5["selection_pool_complete"] is True
    assert gate5["selection_scope_id"] == "promotion-2026q1-core"
    assert len(gate5["panel_hash"]) == 64
    assert 0.0 <= gate5["dsr_probability"] <= 1.0


def test_incomplete_panel_fails_closed_without_numeric_dsr():
    payload = _payload()
    payload["expected_attempt_count"] = 4
    report = deflated_sharpe.build_report(payload)
    gate5 = report["gate5_dsr_report"]

    assert report["status"] == "not_computable"
    assert "trial_panel_attempt_count_mismatch" in report["panel_result"]["reason_codes"]
    assert gate5["status"] == "not_computable"
    assert gate5["selection_pool_complete"] is False
    assert gate5["dsr_probability"] is None


def test_cli_writes_report_and_returns_nonzero_for_missing_evidence(tmp_path):
    payload = _payload()
    payload["trials"] = payload["trials"][:1]
    input_path = tmp_path / "panel.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    exit_code = deflated_sharpe.main(
        ["--input", str(input_path), "--output", str(output_path)]
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert written["status"] == "not_computable"
    assert written["gate5_dsr_report"]["dsr_probability"] is None
