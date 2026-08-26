"""Unit tests for experiment_registry.persist_self_registered_result.

Verifies the sanctioned self-registration path enforces a pre-run prediction
for prediction-required lanes and propagates it onto both the registry entry
and the ticket file -- the two holes the legacy hand-rolled _update_registry()
helpers left open.

No JavaScript was used.
"""

from __future__ import annotations

import hashlib
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
import experiment_registry as experiment_registry_module  # noqa: E402


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


@pytest.mark.parametrize(
    "experiment_id",
    [
        "../../outside",
        "EXP-20990101-900",
        "exp_20990101_900",
        "exp-20990101-900_suffix",
    ],
)
def test_self_register_rejects_noncanonical_id_without_file_side_effects(
    tmp_path, experiment_id
):
    registry_path = _setup_registry(tmp_path)
    original_registry = registry_path.read_bytes()

    with pytest.raises(ValueError, match="exact canonical"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
        )

    assert registry_path.read_bytes() == original_registry
    assert not (tmp_path / "experiments").exists()
    assert not (tmp_path / "outside.json").exists()


PRIVATE_REPLAY_DISPOSITION_CONTRACT = (
    "private_replay_scout_artifact_disposition_contract_version"
)
PRIVATE_REPLAY_CLAIM_BINDING = "private_replay_scout_closeout_claim_binding"
EXPERIMENT_EVER_CLAIMED = "experiment_ever_claimed"


def _private_replay_claim_binding(ticket: dict):
    payload = {
        "schema_version": 1,
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "change_type": ticket.get("change_type"),
        "artifact_disposition_contract_version": ticket.get(
            PRIVATE_REPLAY_DISPOSITION_CONTRACT
        ),
        "allowed_write_scope": list(ticket.get("allowed_write_scope")),
        "must_not_touch": list(ticket.get("must_not_touch")),
    }
    payload["binding_hash"] = hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
    ).hexdigest()
    return payload


def _research_replay_ticket(
    experiment_id: str,
    *,
    admission_class: str = "research_replay",
    change_type: str = "private_replay_scout",
    include_contract_marker: bool = True,
):
    selected_evidence_grade = (
        "lead" if admission_class == "research_replay" else "observed_only"
    )
    ticket = {
        "experiment_id": experiment_id,
        "experiment_uid": f"expuid-{experiment_id[-3:]}fixture",
        "lane": "alpha_search",
        "change_type": change_type,
        "status": "claimed",
        "created_at": "2099-01-01T00:00:00+00:00",
        "claimed_at": "2099-01-01T00:01:00+00:00",
        "prediction": _prediction(),
        "alpha_promotion": {
            "admission_class": admission_class,
            "selected_evidence_grade": selected_evidence_grade,
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "source_readiness_bindings": [{"surface_id": "fixture"}],
        },
        "research_refs": [],
        "allowed_write_scope": [f"data/experiments/{experiment_id}/"],
        "must_not_touch": [],
    }
    if include_contract_marker:
        ticket[PRIVATE_REPLAY_DISPOSITION_CONTRACT] = 1
        ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(ticket)
    return ticket


def _save_existing_ticket(registry_path: Path, ticket: dict):
    tickets_dir = registry_path.parent.parent / "experiments" / "tickets"
    manifests_dir = registry_path.parent.parent / "experiments" / "manifests"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    ticket["ticket_file"] = f"experiments/tickets/{ticket['experiment_id']}.json"
    ticket["revision_manifest_file"] = (
        f"experiments/manifests/{ticket['experiment_id']}.json"
    )
    ticket[EXPERIMENT_EVER_CLAIMED] = ticket.get("status") != "proposed"
    claimed = ticket[EXPERIMENT_EVER_CLAIMED] is True
    reservation_ticket = dict(ticket)
    if claimed:
        reservation_ticket.update(
            {
                "status": "proposed",
                "claimed_at": None,
                EXPERIMENT_EVER_CLAIMED: False,
            }
        )
    experiment_registry_module.save_ticket(reservation_ticket, tickets_dir)
    experiment_registry_module.save_revision_manifest(
        reservation_ticket,
        manifests_dir,
        repo_root=registry_path.parent.parent,
        ticket_file=tickets_dir / f"{ticket['experiment_id']}.json",
        overwrite=False,
    )
    if claimed:
        ticket[experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
            experiment_registry_module._build_experiment_claim_transition(
                ticket, force=False
            )
        )
        experiment_registry_module._save_claim_transition_manifest_intent(
            ticket, manifests_dir
        )
        experiment_registry_module.save_ticket(ticket, tickets_dir)
        experiment_registry_module.save_revision_manifest(
            ticket,
            manifests_dir,
            repo_root=registry_path.parent.parent,
            ticket_file=tickets_dir / f"{ticket['experiment_id']}.json",
        )
    entry = experiment_registry_module._ticket_index_entry(ticket, tickets_dir)
    experiment_registry_module.save_registry(
        {"schema_version": 1, "experiments": [entry]}, registry_path
    )


def _write_private_replay_artifact(
    root: Path,
    experiment_id: str,
    *,
    status: str,
    disposition: str,
    evidence_invalid: bool,
    overrides: dict | None = None,
    payload=None,
):
    if payload is None:
        payload = {
            "experiment_id": experiment_id,
            "record_type": "v2_private_replay_scout_result",
            "status": status,
            "decision": status,
            "disposition": disposition,
            "evidence_invalid": evidence_invalid,
        }
        payload.update(overrides or {})
    relative_path = (
        Path("data") / "experiments" / experiment_id / "private_replay_result.json"
    )
    artifact_path = root / relative_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return relative_path.as_posix(), hashlib.sha256(artifact_path.read_bytes()).hexdigest()


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


def test_propagates_prediction_to_registry_entry_and_ticket(tmp_path, monkeypatch):
    reg = _setup_registry(tmp_path)
    monkeypatch.setattr(
        experiment_registry_module,
        "utc_now_iso",
        lambda: "2026-08-25T00:00:00+00:00",
    )
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


def test_non_prediction_lane_allows_missing_prediction(tmp_path, monkeypatch):
    reg = _setup_registry(tmp_path)
    monkeypatch.setattr(
        experiment_registry_module,
        "utc_now_iso",
        lambda: "2026-08-25T00:00:00+00:00",
    )
    exp = persist_self_registered_result(
        reg,
        experiment_id="exp-20260608-903",
        lane="measurement_repair",
        prediction=None,
        result={"decision": "accepted"},
        status="accepted",
    )
    assert exp["status"] == "accepted"


def test_allow_missing_prediction_escape_hatch(tmp_path, monkeypatch):
    reg = _setup_registry(tmp_path)
    monkeypatch.setattr(
        experiment_registry_module,
        "utc_now_iso",
        lambda: "2026-08-25T00:00:00+00:00",
    )
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


def test_post_rollout_self_registration_requires_reservation_before_writes(tmp_path):
    reg = _setup_registry(tmp_path)
    before = reg.read_bytes()

    with pytest.raises(ValueError, match="reserve its registry and manifest"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20990101-908",
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
        )

    assert reg.read_bytes() == before
    assert not (tmp_path / "experiments").exists()


def test_post_enforcement_alpha_cannot_bypass_promotion_by_self_registering(
    tmp_path, monkeypatch
):
    reg = _setup_registry(tmp_path)
    monkeypatch.setattr(
        experiment_registry_module,
        "_alpha_promotion_gate_enabled",
        lambda registry: True,
    )

    with pytest.raises(ValueError, match="reserve and claim a promotion-anchored ticket"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20990101-901",
            lane="alpha_search",
            prediction=_prediction(),
            result={"decision": "accepted"},
            status="accepted",
        )

    assert load_registry(reg)["experiments"] == []


def test_new_alpha_self_registration_cannot_backdate_promotion_enforcement(
    tmp_path, monkeypatch
):
    reg = _setup_registry(tmp_path)
    monkeypatch.setattr(
        experiment_registry_module,
        "_alpha_promotion_gate_enabled",
        lambda registry: True,
    )

    with pytest.raises(ValueError, match="reserve and claim a promotion-anchored ticket"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20990101-907",
            lane="alpha_search",
            prediction=_prediction(),
            result={"decision": "accepted", "verdict": "live_eligible"},
            status="accepted",
            fields={
                "created_at": "2020-01-01T00:00:00+00:00",
                "alpha_promotion": {},
            },
        )

    assert load_registry(reg)["experiments"] == []


@pytest.mark.parametrize(
    ("status", "result"),
    [
        ("accepted", {"decision": "accepted"}),
        ("accepted_paper_pending_forward", {"verdict": "accepted_paper_pending_forward"}),
        ("observed_only", {"decision": "observed_only", "verdict": "live_eligible"}),
    ],
)
def test_research_replay_self_registration_blocks_accepted_paper_and_live(
    tmp_path, monkeypatch, status, result
):
    reg = _setup_registry(tmp_path)
    registry = load_registry(reg)
    registry["experiments"] = [
        {
            "experiment_id": "exp-20260825-902",
            "lane": "alpha_search",
            "created_at": "2026-08-25T00:00:00+00:00",
            "prediction": _prediction(),
            "alpha_promotion": {
                "admission_class": "research_replay",
                "selected_evidence_grade": "lead",
                "result_ceiling": "observed_only",
                "paper_live_eligible": False,
                "source_readiness_bindings": [{"surface_id": "fixture"}],
            },
        }
    ]
    reg.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, ticket: ticket["alpha_promotion"],
    )

    with pytest.raises(ValueError, match="research_replay"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20260825-902",
            lane="alpha_search",
            prediction=_prediction(),
            result=result,
            status=status,
        )


def test_research_replay_self_registration_allows_observed_only(tmp_path, monkeypatch):
    reg = _setup_registry(tmp_path)
    registry = load_registry(reg)
    registry["experiments"] = [
        {
            "experiment_id": "exp-20260825-903",
            "lane": "alpha_search",
            "created_at": "2026-08-25T00:00:00+00:00",
            "prediction": _prediction(),
            "alpha_promotion": {
                "admission_class": "research_replay",
                "selected_evidence_grade": "lead",
                "result_ceiling": "observed_only",
                "paper_live_eligible": False,
                "source_readiness_bindings": [{"surface_id": "fixture"}],
            },
        }
    ]
    reg.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, ticket: ticket["alpha_promotion"],
    )

    exp = persist_self_registered_result(
        reg,
        experiment_id="exp-20260825-903",
        lane="alpha_search",
        prediction=_prediction(),
        result={"decision": "observed_only", "verdict": "research_only"},
        status="observed_only",
    )
    assert exp["status"] == "observed_only"
    assert exp["result"]["paper_live_eligible"] is False


def test_research_replay_self_registration_cannot_demote_lane_and_remove_anchor(
    tmp_path, monkeypatch
):
    reg = _setup_registry(tmp_path)
    registry = load_registry(reg)
    registry["experiments"] = [
        {
            "experiment_id": "exp-20260825-904",
            "lane": "alpha_search",
            "created_at": "2026-08-25T00:00:00+00:00",
            "prediction": _prediction(),
            "alpha_promotion": {
                "admission_class": "research_replay",
                "selected_evidence_grade": "lead",
                "result_ceiling": "observed_only",
                "paper_live_eligible": False,
                "source_readiness_bindings": [{"surface_id": "fixture"}],
            },
        }
    ]
    reg.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, ticket: ticket.get("alpha_promotion"),
    )

    with pytest.raises(ValueError, match="cannot change lane"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20260825-904",
            lane="measurement_repair",
            prediction=_prediction(),
            result={"decision": "accepted", "verdict": "live_eligible"},
            status="accepted",
            fields={"alpha_promotion": {}},
        )


def test_research_replay_self_registration_blocks_nested_live_verdict(
    tmp_path, monkeypatch
):
    reg = _setup_registry(tmp_path)
    registry = load_registry(reg)
    registry["experiments"] = [
        {
            "experiment_id": "exp-20260825-905",
            "lane": "alpha_search",
            "created_at": "2026-08-25T00:00:00+00:00",
            "prediction": _prediction(),
            "alpha_promotion": {
                "admission_class": "research_replay",
                "selected_evidence_grade": "lead",
                "result_ceiling": "observed_only",
                "paper_live_eligible": False,
                "source_readiness_bindings": [{"surface_id": "fixture"}],
            },
        }
    ]
    reg.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, ticket: ticket["alpha_promotion"],
    )

    with pytest.raises(ValueError, match="result.full_stack.verdict"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20260825-905",
            lane="alpha_search",
            prediction=_prediction(),
            result={
                "decision": "observed_only",
                "full_stack": {
                    "verdict": "live_eligible",
                    "live_ready": True,
                },
            },
            status="observed_only",
        )


def test_canonical_self_registration_cannot_backdate_and_remove_anchor(tmp_path):
    reg = _setup_registry(tmp_path)
    registry = load_registry(reg)
    registry["experiments"] = [
        {
            "experiment_id": "exp-20260825-906",
            "lane": "alpha_search",
            "created_at": "2026-08-25T00:00:00+00:00",
            "prediction": _prediction(),
            "alpha_promotion": {"promotion_hash": "a" * 64},
        }
    ]
    reg.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(ValueError, match="immutable existing ticket field"):
        persist_self_registered_result(
            reg,
            experiment_id="exp-20260825-906",
            lane="alpha_search",
            prediction=_prediction(),
            result={"decision": "accepted"},
            status="accepted",
            fields={
                "created_at": "2020-01-01T00:00:00+00:00",
                "alpha_promotion": {},
            },
        )


@pytest.mark.parametrize(
    ("status", "disposition", "evidence_invalid"),
    [
        ("observed_only", "positive_replay_lead_not_promoted", False),
        ("rejected", "rejected", False),
        ("rejected", "inconclusive_insufficient_sample", False),
        ("rejected", "invalid_contaminated", True),
    ],
)
def test_future_private_replay_self_registration_accepts_protocol_dispositions(
    tmp_path, monkeypatch, status, disposition, evidence_invalid
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-910"
    ticket = _research_replay_ticket(experiment_id)
    _save_existing_ticket(registry_path, ticket)
    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status=status,
        disposition=disposition,
        evidence_invalid=evidence_invalid,
    )
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    closed = persist_self_registered_result(
        registry_path,
        experiment_id=experiment_id,
        lane="alpha_search",
        prediction=_prediction(),
        result={
            "decision": status,
            "artifact": artifact,
            "artifact_sha256": artifact_sha256,
        },
        status=status,
    )

    assert closed["status"] == status
    assert closed["result"]["artifact"] == artifact
    assert closed["result"]["artifact_sha256"] == artifact_sha256
    assert closed["result"]["artifact_disposition"] == disposition
    assert closed["result"]["evidence_invalid"] is evidence_invalid


@pytest.mark.parametrize(
    ("case", "error_pattern"),
    [
        ("missing_disposition", "disposition"),
        ("unknown_disposition", "disposition"),
        ("status_disposition_mismatch", "disposition"),
        ("artifact_hash_mismatch", "sha256|hash"),
        ("artifact_outside_repo", "artifact|repo|path"),
        ("artifact_outside_allowed_scope", "allowed_write_scope|scope"),
        ("artifact_in_must_not_touch", "must_not_touch"),
        ("missing_artifact_binding", "artifact"),
        ("artifact_not_json_object", "object"),
        ("experiment_id_mismatch", "experiment_id|identity"),
        ("record_type_mismatch", "record_type|identity"),
        ("status_identity_mismatch", "status|identity"),
        ("decision_identity_mismatch", "decision|identity"),
        ("contaminated_without_invalid_flag", "evidence_invalid"),
        ("clean_disposition_with_invalid_flag", "evidence_invalid"),
        ("result_decision_mismatch", "decision|status"),
        ("result_status_mismatch", "decision|status"),
        ("artifact_disposition_mirror_mismatch", "artifact_disposition"),
        ("evidence_invalid_mirror_mismatch", "evidence_invalid"),
        ("missing_result_decision", "decision"),
    ],
)
def test_future_private_replay_self_registration_rejects_invalid_artifact_contract(
    tmp_path, monkeypatch, case, error_pattern
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-911"
    ticket = _research_replay_ticket(experiment_id)
    status = "rejected"
    disposition = "rejected"
    evidence_invalid = False
    overrides = {}
    payload = None

    if case == "missing_disposition":
        overrides["disposition"] = None
    elif case == "unknown_disposition":
        disposition = "unknown"
    elif case == "status_disposition_mismatch":
        status = "observed_only"
    elif case == "artifact_not_json_object":
        payload = []
    elif case == "experiment_id_mismatch":
        overrides["experiment_id"] = "exp-20990101-999"
    elif case == "record_type_mismatch":
        overrides["record_type"] = "not_a_private_replay_result"
    elif case == "status_identity_mismatch":
        overrides["status"] = "observed_only"
    elif case == "decision_identity_mismatch":
        overrides["decision"] = "observed_only"
    elif case == "contaminated_without_invalid_flag":
        disposition = "invalid_contaminated"
    elif case == "clean_disposition_with_invalid_flag":
        evidence_invalid = True

    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status=status,
        disposition=disposition,
        evidence_invalid=evidence_invalid,
        overrides=overrides,
        payload=payload,
    )
    result = {
        "decision": status,
        "artifact": artifact,
        "artifact_sha256": artifact_sha256,
    }
    if case == "artifact_hash_mismatch":
        result["artifact_sha256"] = "0" * 64
    elif case == "artifact_outside_repo":
        result["artifact"] = "../outside-private-replay-result.json"
    elif case == "missing_artifact_binding":
        result.pop("artifact")
    elif case == "artifact_outside_allowed_scope":
        ticket["allowed_write_scope"] = ["data/experiments/some-other-experiment/"]
    elif case == "artifact_in_must_not_touch":
        ticket["must_not_touch"] = [artifact]
    elif case == "result_decision_mismatch":
        result["decision"] = "observed_only"
    elif case == "result_status_mismatch":
        result["status"] = "observed_only"
    elif case == "artifact_disposition_mirror_mismatch":
        result["artifact_disposition"] = "invalid_contaminated"
    elif case == "evidence_invalid_mirror_mismatch":
        result["evidence_invalid"] = True
    elif case == "missing_result_decision":
        result.pop("decision")
    _save_existing_ticket(registry_path, ticket)
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    with pytest.raises(ValueError, match=error_pattern):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result=result,
            status=status,
        )

    persisted = json.loads(
        (
            tmp_path
            / "experiments"
            / "tickets"
            / f"{experiment_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert persisted["status"] == "claimed"
    assert "result" not in persisted


@pytest.mark.parametrize(
    "frozen_field", ["allowed_write_scope", "must_not_touch", "change_type"]
)
def test_future_private_replay_self_registration_cannot_rewrite_contract_fields(
    tmp_path, monkeypatch, frozen_field
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-916"
    ticket = _research_replay_ticket(experiment_id)
    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    if frozen_field == "allowed_write_scope":
        ticket[frozen_field] = ["data/experiments/some-other-experiment/"]
        replacement = [f"data/experiments/{experiment_id}/"]
    elif frozen_field == "must_not_touch":
        ticket[frozen_field] = [artifact]
        replacement = []
    else:
        replacement = "analysis_only"
    _save_existing_ticket(registry_path, ticket)
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    with pytest.raises(ValueError, match=f"immutable.*{frozen_field}"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result={
                "decision": "rejected",
                "artifact": artifact,
                "artifact_sha256": artifact_sha256,
            },
            status="rejected",
            fields={frozen_field: replacement},
        )

    persisted = json.loads(
        (
            tmp_path
            / "experiments"
            / "tickets"
            / f"{experiment_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert persisted["status"] == "claimed"
    assert persisted[frozen_field] == ticket[frozen_field]


@pytest.mark.parametrize("disposition", [[], {}])
def test_future_private_replay_non_string_disposition_raises_structured_value_error(
    tmp_path, monkeypatch, disposition
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-915"
    ticket = _research_replay_ticket(experiment_id)
    _save_existing_ticket(registry_path, ticket)
    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition=disposition,
        evidence_invalid=False,
    )
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    with pytest.raises(ValueError, match="disposition"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result={
                "decision": "rejected",
                "artifact": artifact,
                "artifact_sha256": artifact_sha256,
            },
            status="rejected",
        )


@pytest.mark.parametrize(
    ("outer_status", "result_decision", "result_status"),
    [
        ("Rejected", "rejected", None),
        (" rejected ", "rejected", None),
        ("rejected", "Rejected", None),
        ("rejected", " rejected ", None),
        ("rejected", "rejected", "Rejected"),
    ],
)
def test_future_private_replay_self_registration_requires_canonical_outer_terminal_fields(
    tmp_path, monkeypatch, outer_status, result_decision, result_status
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-914"
    ticket = _research_replay_ticket(experiment_id)
    _save_existing_ticket(registry_path, ticket)
    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    result = {
        "decision": result_decision,
        "artifact": artifact,
        "artifact_sha256": artifact_sha256,
    }
    if result_status is not None:
        result["status"] = result_status
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    with pytest.raises(ValueError, match="canonical|status|decision"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result=result,
            status=outer_status,
        )


@pytest.mark.parametrize(
    ("created_at", "reserved_at"),
    [
        ("2020-01-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00"),
        ("not-a-timestamp", None),
        ("2099-01-01T00:00:00", None),
        (None, None),
    ],
)
def test_future_private_replay_self_registration_requires_contract_marker_even_when_timestamps_are_untrusted(
    tmp_path, monkeypatch, created_at, reserved_at
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-912"
    ticket = _research_replay_ticket(experiment_id)
    ticket.pop(PRIVATE_REPLAY_DISPOSITION_CONTRACT)
    if created_at is None:
        ticket.pop("created_at")
    else:
        ticket["created_at"] = created_at
    if reserved_at is not None:
        ticket["hub_identity"] = {"reserved_at": reserved_at}
    _save_existing_ticket(registry_path, ticket)
    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    with pytest.raises(ValueError, match="contract|marker|version|clock.*malformed"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result={
                "decision": "rejected",
                "artifact": artifact,
                "artifact_sha256": artifact_sha256,
            },
            status="rejected",
        )


@pytest.mark.parametrize(
    ("admission_class", "change_type"),
    [
        ("research_replay", "candidate_pool"),
        ("settled_forward_attribution", "candidate_pool"),
    ],
)
def test_disposition_contract_does_not_expand_beyond_future_private_replay_scouts(
    tmp_path, monkeypatch, admission_class, change_type
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-913"
    ticket = _research_replay_ticket(
        experiment_id,
        admission_class=admission_class,
        change_type=change_type,
        include_contract_marker=False,
    )
    _save_existing_ticket(registry_path, ticket)
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    closed = persist_self_registered_result(
        registry_path,
        experiment_id=experiment_id,
        lane="alpha_search",
        prediction=_prediction(),
        result={"decision": "observed_only"},
        status="observed_only",
    )

    assert closed["status"] == "observed_only"
    assert "artifact_disposition" not in closed["result"]


@pytest.mark.parametrize(
    ("admission_class", "change_type"),
    [
        ("research_replay", "candidate_pool"),
        ("settled_forward_attribution", "private_replay_scout"),
    ],
)
def test_self_register_rejects_private_contract_identity_swaps(
    tmp_path, monkeypatch, admission_class, change_type
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-914"
    ticket = _research_replay_ticket(
        experiment_id,
        admission_class=admission_class,
        change_type=change_type,
    )
    _save_existing_ticket(registry_path, ticket)
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )

    with pytest.raises(ValueError, match="private replay contract identity requires"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result={"decision": "observed_only"},
            status="observed_only",
        )


def test_self_register_rejects_pre_demoted_private_contract_ticket(tmp_path):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-915"
    ticket = _research_replay_ticket(experiment_id)
    ticket["lane"] = "measurement_repair"
    _save_existing_ticket(registry_path, ticket)

    with pytest.raises(ValueError, match="cannot demote lane"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
        )

    persisted = load_registry(registry_path)["experiments"][0]
    assert persisted["status"] == "claimed"


def test_self_register_rejects_terminal_private_contract_rewrite(
    tmp_path, monkeypatch
):
    registry_path = _setup_registry(tmp_path)
    experiment_id = "exp-20990101-916"
    ticket = _research_replay_ticket(experiment_id)
    _save_existing_ticket(registry_path, ticket)
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda registry, current: current["alpha_promotion"],
    )
    artifact, artifact_sha256 = _write_private_replay_artifact(
        tmp_path,
        experiment_id,
        status="observed_only",
        disposition="positive_replay_lead_not_promoted",
        evidence_invalid=False,
    )
    first_result = {
        "decision": "observed_only",
        "artifact": artifact,
        "artifact_sha256": artifact_sha256,
    }
    closed = persist_self_registered_result(
        registry_path,
        experiment_id=experiment_id,
        lane="alpha_search",
        prediction=_prediction(),
        result=first_result,
        status="observed_only",
    )
    original_result = dict(closed["result"])

    with pytest.raises(ValueError, match="already terminal.*immutable"):
        persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result={**first_result, "notes": "conflicting terminal rewrite"},
            status="observed_only",
        )

    persisted = json.loads(
        (tmp_path / "experiments" / "tickets" / f"{experiment_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["result"] == original_result
