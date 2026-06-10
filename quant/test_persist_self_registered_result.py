"""Unit tests for experiment_registry.persist_self_registered_result.

Verifies the sanctioned self-registration path enforces a pre-run prediction
for prediction-required lanes and propagates it onto both the registry entry
and the ticket file -- the two holes the legacy hand-rolled _update_registry()
helpers left open.

No JavaScript was used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    load_registry,
    persist_self_registered_result,
)


def _setup_registry(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    reg_path = docs / "experiment_registry.json"
    reg_path.write_text(
        json.dumps({"schema_version": 1, "experiments": []}), encoding="utf-8"
    )
    return reg_path


def _prediction():
    return {
        "success_probability": 0.3,
        "main_failure_modes": ["thin_sample"],
        "confidence_reason": (
            "Free PIT-safe field has plausible mechanism, prior qualifiers were mixed, "
            "and thin sample remains the main failure risk."
        ),
    }


def test_requires_prediction_for_alpha_lane(tmp_path):
    reg = _setup_registry(tmp_path)
    with pytest.raises(ValueError):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20260608-901",
            lane="alpha_search",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
        )


def test_rejects_weak_prediction_quality_for_alpha_lane(tmp_path):
    reg = _setup_registry(tmp_path)
    with pytest.raises(ValueError, match="substantive pre-run prediction"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20260608-905",
            lane="alpha_search",
            prediction={
                "success_probability": 0.3,
                "main_failure_modes": ["thin_sample"],
                "confidence_reason": "TODO",
            },
            result={"decision": "rejected"},
            status="rejected",
        )


def test_propagates_prediction_to_registry_entry_and_ticket(tmp_path):
    reg = _setup_registry(tmp_path)
    exp = persist_self_registered_result(
        reg,
        experiment_id="exp-20260608-902",
        lane="alpha_search",
        prediction=_prediction(),
        result={"decision": "rejected"},
        status="rejected",
        fields={"mechanism_family": "mf_demo", "trial_family": "tf_demo"},
    )
    assert exp["prediction"]["success_probability"] == 0.3
    assert exp["mechanism_family"] == "mf_demo"
    assert exp["status"] == "rejected"
    assert exp["created_at"] and exp["completed_at"]

    saved = load_registry(reg)
    entry = next(
        e for e in saved["experiments"] if e["experiment_id"] == "exp-20260608-902"
    )
    assert entry.get("prediction"), "prediction must be persisted on the registry entry"
    assert entry["trial_family"] == "tf_demo"

    ticket_path = tmp_path / "experiments" / "tickets" / "exp-20260608-902.json"
    assert ticket_path.exists()
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert ticket.get("prediction"), "prediction must be propagated onto the ticket"
    assert ticket["result"]["decision"] == "rejected"


def test_non_prediction_lane_allows_missing_prediction(tmp_path):
    reg = _setup_registry(tmp_path)
    exp = persist_self_registered_result(
        reg,
        experiment_id="exp-20260608-903",
        lane="measurement_repair",
        prediction=None,
        result={"decision": "accepted"},
        status="accepted",
    )
    assert exp["status"] == "accepted"


def test_allow_missing_prediction_escape_hatch(tmp_path):
    reg = _setup_registry(tmp_path)
    exp = persist_self_registered_result(
        reg,
        experiment_id="exp-20260608-904",
        lane="alpha_search",
        prediction=None,
        result={"decision": "observed_only"},
        status="observed_only",
        allow_missing_prediction=True,
    )
    assert exp["status"] == "observed_only"
