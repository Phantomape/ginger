from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import experiment_registry as registry_module  # noqa: E402


CONTRACT_VERSION = "private_replay_scout_artifact_disposition_contract_version"
CLAIM_BINDING = "private_replay_scout_closeout_claim_binding"
REGISTRY_IDENTITY = "private_replay_scout_registry_identity"
EXPERIMENT_EVER_CLAIMED = "experiment_ever_claimed"


def _prediction():
    return {
        "recorded_at": "2099-01-01T00:00:00+00:00",
        "success_probability": 0.2,
        "main_failure_modes": ["thin_sample"],
        "confidence_reason": (
            "The private replay is bounded and outcome-blind, while a thin "
            "sample remains the dominant failure mode."
        ),
    }


def _private_ticket(experiment_id: str, *, status: str = "claimed"):
    ticket = {
        "experiment_id": experiment_id,
        "experiment_uid": f"expuid-{experiment_id[-3:]}fixture",
        "status": status,
        "lane": "alpha_search",
        "owner": "fixture-owner",
        "hypothesis": "A bounded private replay may produce an observed-only lead.",
        "change_type": "private_replay_scout",
        "mechanism_family": "fixture_private_replay",
        "trial_family": "fixture_private_replay_v1",
        "trial_variant_id": experiment_id,
        "single_causal_variable": "fixture private replay",
        "changed_variable": "fixture membership",
        "causal_components": ["fixed candidate frame"],
        "prior_trial_count": 0,
        "nearby_prior_experiments": [],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "fixture",
        "locked_variables": ["fixture membership"],
        "evaluation_windows": [],
        "prediction": _prediction(),
        "created_at": "2099-01-01T00:00:00+00:00",
        "claimed_at": (
            "2099-01-01T00:01:00+00:00" if status != "proposed" else None
        ),
        "completed_at": None,
        "result": None,
        EXPERIMENT_EVER_CLAIMED: status != "proposed",
        "alpha_promotion": {
            "admission_class": "research_replay",
            "selected_evidence_grade": "lead",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "source_readiness_bindings": [{"surface_id": "fixture"}],
        },
        "research_refs": [],
        "allowed_write_scope": [f"data/experiments/{experiment_id}/"],
        "must_not_touch": [],
        CONTRACT_VERSION: 1,
        "ticket_file": f"experiments/tickets/{experiment_id}.json",
        "revision_manifest_file": f"experiments/manifests/{experiment_id}.json",
    }
    ticket[CLAIM_BINDING] = registry_module._private_replay_scout_claim_binding(
        ticket
    )
    return ticket


def _write_artifact(root: Path, experiment_id: str, *, status: str = "rejected"):
    relative = Path("data") / "experiments" / experiment_id / "result.json"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": experiment_id,
        "record_type": "v2_private_replay_scout_result",
        "status": status,
        "decision": status,
        "disposition": (
            "positive_replay_lead_not_promoted"
            if status == "observed_only"
            else "rejected"
        ),
        "evidence_invalid": False,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path, relative.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()


def _write_bundle(root: Path, ticket: dict):
    registry_path = root / "docs" / "experiment_registry.json"
    tickets_dir = root / "experiments" / "tickets"
    manifests_dir = root / "experiments" / "manifests"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    claimed = ticket.get(EXPERIMENT_EVER_CLAIMED) is True
    reservation_ticket = dict(ticket)
    if claimed:
        reservation_ticket.update(
            {
                "status": "proposed",
                "claimed_at": None,
                EXPERIMENT_EVER_CLAIMED: False,
            }
        )
    registry_module.save_ticket(reservation_ticket, tickets_dir)
    registry_module.save_revision_manifest(
        reservation_ticket,
        manifests_dir,
        repo_root=root,
        ticket_file=tickets_dir / f"{ticket['experiment_id']}.json",
        overwrite=False,
    )
    if claimed:
        ticket[registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
            registry_module._build_experiment_claim_transition(ticket, force=False)
        )
        registry_module._save_claim_transition_manifest_intent(
            ticket, manifests_dir
        )
        registry_module.save_ticket(ticket, tickets_dir)
        registry_module.save_revision_manifest(
            ticket,
            manifests_dir,
            repo_root=root,
            ticket_file=tickets_dir / f"{ticket['experiment_id']}.json",
        )
    entry = registry_module._ticket_index_entry(ticket, tickets_dir)
    registry_module.save_registry(
        {"schema_version": 1, "experiments": [entry]}, registry_path
    )
    return registry_path, tickets_dir, root / "experiments" / "logs"


def _judgement(status: str = "rejected"):
    return {
        "decision": status,
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 0.0},
        "after_metrics": {"expected_value_score": 0.0},
        "delta_metrics": {"expected_value_score": 0.0},
    }


def _draft(
    ticket,
    judgement,
    before,
    after,
    root,
    *,
    realized_failure_mode=None,
):
    return registry_module.build_log_draft(
        ticket,
        judgement,
        before,
        after,
        status_override=judgement["decision"],
        realized_failure_mode=realized_failure_mode,
        repo_root=root,
    )


def _generic_ticket(experiment_id: str, *, status: str = "proposed"):
    return {
        "experiment_id": experiment_id,
        "experiment_uid": f"expuid-{experiment_id[-3:]}generic",
        "status": status,
        "lane": "measurement_repair",
        "owner": "fixture-owner" if status != "proposed" else None,
        "hypothesis": "Reservation identity must survive lifecycle mutation.",
        "change_type": "measurement_repair",
        "mechanism_family": "fixture_reservation_identity",
        "trial_family": "fixture_reservation_identity_v1",
        "trial_variant_id": experiment_id,
        "single_causal_variable": "reservation identity",
        "allowed_write_scope": [f"data/experiments/{experiment_id}/"],
        "must_not_touch": [],
        "locked_variables": ["reservation identity"],
        "created_at": "2099-01-02T00:00:00+00:00",
        "claimed_at": (
            "2099-01-02T00:01:00+00:00" if status != "proposed" else None
        ),
        "completed_at": None,
        "result": None,
        EXPERIMENT_EVER_CLAIMED: status != "proposed",
        "ticket_file": f"experiments/tickets/{experiment_id}.json",
        "revision_manifest_file": f"experiments/manifests/{experiment_id}.json",
    }


def _write_generic_bundle(root: Path, ticket: dict):
    registry_path = root / "docs" / "experiment_registry.json"
    tickets_dir = root / "experiments" / "tickets"
    manifests_dir = root / "experiments" / "manifests"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    claimed = ticket.get(EXPERIMENT_EVER_CLAIMED) is True
    reservation_ticket = dict(ticket)
    if claimed:
        reservation_ticket.update(
            {
                "status": "proposed",
                "owner": None,
                "claimed_at": None,
                EXPERIMENT_EVER_CLAIMED: False,
            }
        )
    registry_module.save_ticket(reservation_ticket, tickets_dir)
    registry_module.save_revision_manifest(
        reservation_ticket,
        manifests_dir,
        repo_root=root,
        ticket_file=tickets_dir / f"{ticket['experiment_id']}.json",
        overwrite=False,
    )
    if claimed:
        ticket[registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
            registry_module._build_experiment_claim_transition(ticket, force=False)
        )
        registry_module._save_claim_transition_manifest_intent(
            ticket, manifests_dir
        )
        registry_module.save_ticket(ticket, tickets_dir)
        registry_module.save_revision_manifest(
            ticket,
            manifests_dir,
            repo_root=root,
            ticket_file=tickets_dir / f"{ticket['experiment_id']}.json",
        )
    registry_module.save_registry(
        {
            "schema_version": 1,
            "experiments": [registry_module._ticket_index_entry(ticket, tickets_dir)],
        },
        registry_path,
    )
    return registry_path, tickets_dir, manifests_dir


def test_file_backed_claim_monotonically_updates_independent_anchors(tmp_path):
    experiment_id = "exp-20990102-001"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )

    claimed, conflicts = registry_module.claim_experiment_decontended(
        registry_path, experiment_id, "fixture-owner"
    )

    assert conflicts == []
    assert claimed[EXPERIMENT_EVER_CLAIMED] is True
    persisted = registry_module.load_ticket(experiment_id, tickets_dir)
    registry_row = registry_module.load_registry(registry_path)["experiments"][0]
    manifest = json.loads(
        (manifests_dir / f"{experiment_id}.json").read_text(encoding="utf-8")
    )
    assert persisted[EXPERIMENT_EVER_CLAIMED] is True
    assert registry_row[EXPERIMENT_EVER_CLAIMED] is True
    assert manifest[EXPERIMENT_EVER_CLAIMED] is True
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is True


def test_completed_claim_same_owner_retry_is_exactly_idempotent(tmp_path):
    experiment_id = "exp-20990102-013"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    first, conflicts = registry_module.claim_experiment_decontended(
        registry_path, experiment_id, "fixture-owner"
    )
    assert conflicts == []
    paths = [
        tickets_dir / f"{experiment_id}.json",
        manifests_dir / f"{experiment_id}.json",
        registry_path,
    ]
    before = [path.read_bytes() for path in paths]

    second, conflicts = registry_module.claim_experiment_decontended(
        registry_path, experiment_id, "fixture-owner"
    )

    assert conflicts == []
    assert second == first
    assert [path.read_bytes() for path in paths] == before


def test_interrupted_claim_fails_then_repairs_forward_on_same_owner_retry(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-004"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    original_locked_update = registry_module.locked_registry_update

    def fail_registry_update(*args, **kwargs):
        raise OSError("simulated registry cache write failure")

    monkeypatch.setattr(
        registry_module, "locked_registry_update", fail_registry_update
    )
    with pytest.raises(OSError, match="simulated registry"):
        registry_module.claim_experiment_decontended(
            registry_path, experiment_id, "fixture-owner"
        )

    interrupted = registry_module.load_ticket(experiment_id, tickets_dir)
    manifest = json.loads(
        (manifests_dir / f"{experiment_id}.json").read_text(encoding="utf-8")
    )
    registry_row = registry_module.load_registry(registry_path)["experiments"][0]
    assert interrupted["status"] == "claimed"
    assert interrupted[EXPERIMENT_EVER_CLAIMED] is True
    assert manifest[EXPERIMENT_EVER_CLAIMED] is True
    assert registry_row[EXPERIMENT_EVER_CLAIMED] is False

    monkeypatch.setattr(
        registry_module, "locked_registry_update", original_locked_update
    )
    recovered, conflicts = registry_module.claim_experiment_decontended(
        registry_path, experiment_id, "fixture-owner"
    )
    assert conflicts == []
    assert recovered["status"] == "claimed"
    repaired_row = registry_module.load_registry(registry_path)["experiments"][0]
    assert repaired_row[EXPERIMENT_EVER_CLAIMED] is True
    registry_module._validate_file_backed_reservation_anchors(
        registry_path, recovered
    )


def test_claim_strict_cache_cannot_recreate_deleted_reservation_row(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-018"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    original_locked_update = registry_module.locked_registry_update

    def delete_row_before_mutator(path, mutator, **kwargs):
        def wrapped(registry):
            registry["experiments"] = []
            registry_module.save_registry(registry, path)
            return mutator(registry)

        return original_locked_update(path, wrapped, **kwargs)

    monkeypatch.setattr(
        registry_module, "locked_registry_update", delete_row_before_mutator
    )

    with pytest.raises(ValueError, match="existing reservation registry row"):
        registry_module.claim_experiment_decontended(
            registry_path, experiment_id, "fixture-owner"
        )

    assert registry_module.load_registry(registry_path)["experiments"] == []
    assert registry_module.load_ticket(experiment_id, tickets_dir)[
        "status"
    ] == "claimed"


def test_ticket_only_claim_flip_cannot_be_reblessed_as_recovery(tmp_path):
    experiment_id = "exp-20990102-010"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    forged = registry_module.load_ticket(experiment_id, tickets_dir)
    forged.update(
        {
            "status": "claimed",
            "owner": "fixture-owner",
            "claimed_at": "2099-01-02T00:01:00+00:00",
            EXPERIMENT_EVER_CLAIMED: True,
        }
    )
    registry_module.save_ticket(forged, tickets_dir)
    manifest_path = manifests_dir / f"{experiment_id}.json"
    manifest_before = manifest_path.read_bytes()
    registry_before = registry_path.read_bytes()

    with pytest.raises(ValueError, match="claim transition"):
        registry_module.claim_experiment_decontended(
            registry_path, experiment_id, "fixture-owner"
        )

    assert manifest_path.read_bytes() == manifest_before
    assert registry_path.read_bytes() == registry_before


def test_audit_requires_manifest_claim_transition_for_ever_claimed_ticket(
    tmp_path,
):
    experiment_id = "exp-20990102-011"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    manifest_path = manifests_dir / f"{experiment_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop(registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )

    assert audit["passed"] is False
    assert "manifest claim transition" in json.dumps(
        audit["canonical_record_violation_examples"]
    )


def test_post_rollout_log_rejects_preterminal_ticket_and_audit_detects_shard(
    tmp_path,
):
    experiment_id = "exp-20990102-012"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    logs_dir = tmp_path / "experiments" / "logs"
    row = {
        "experiment_id": experiment_id,
        "status": "accepted",
        "decision": "accepted",
    }

    with pytest.raises(ValueError, match="terminal canonical ticket"):
        registry_module.save_experiment_log_entry(
            row,
            logs_dir=logs_dir,
            registry_path=registry_path,
        )
    assert not (logs_dir / f"{experiment_id}.json").exists()

    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps(row, indent=2) + "\n", encoding="utf-8"
    )
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        file_backed_registry=True,
    )
    assert audit["passed"] is False
    assert "terminal canonical ticket" in json.dumps(
        audit["canonical_record_violation_examples"]
    )


@pytest.mark.parametrize(
    "ticket",
    [
        {
            "experiment_id": "exp-20260825-997",
            "status": "claimed",
            "lane": "measurement_repair",
            "created_at": "2026-08-25T00:00:00+00:00",
            EXPERIMENT_EVER_CLAIMED: True,
        },
        {
            "experiment_id": "exp-20260825-998",
            "status": "proposed",
            "lane": "measurement_repair",
            "created_at": "2026-08-25T00:00:00+00:00",
            registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD: {
                "schema_version": 1,
                "force": False,
                "transition_hash": "missing-independent-identity",
            },
        },
        {
            "experiment_id": "exp-20260825-996",
            "status": "rejected",
            "lane": "measurement_repair",
            "created_at": "2026-08-25T00:00:00+00:00",
            registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD: {
                "experiment_id": "exp-20260825-996",
                "status": "rejected",
                "decision": "rejected",
            },
            registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD: (
                "f" * 64
            ),
        },
    ],
)
def test_old_id_rollout_marker_residue_cannot_disable_anchor_contract(
    tmp_path, ticket
):
    tickets_dir = tmp_path / "experiments" / "tickets"
    manifests_dir = tmp_path / "experiments" / "manifests"
    tickets_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir(parents=True)
    experiment_id = ticket["experiment_id"]
    registry_module.save_ticket(ticket, tickets_dir)
    registry_module.save_registry(
        {"schema_version": 1, "experiments": [dict(ticket)]}, registry_path
    )
    (manifests_dir / f"{experiment_id}.json").write_text(
        json.dumps({"experiment_id": experiment_id}, indent=2) + "\n",
        encoding="utf-8",
    )

    assert registry_module.experiment_reservation_identity_required(ticket)
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is False
    assert "reservation identity" in json.dumps(
        audit["canonical_record_violation_examples"]
    )


@pytest.mark.parametrize(
    "created_at",
    ["2026-08-26T09:00:00", "not-a-timestamp"],
)
def test_old_id_invalid_or_naive_rollout_clock_fails_file_backed_audit(
    tmp_path, created_at
):
    experiment_id = "exp-20260825-999"
    ticket = {
        "experiment_id": experiment_id,
        "status": "proposed",
        "lane": "measurement_repair",
        "created_at": created_at,
    }
    tickets_dir = tmp_path / "experiments" / "tickets"
    tickets_dir.mkdir(parents=True)
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_module.save_ticket(ticket, tickets_dir)
    registry_module.save_registry(
        {"schema_version": 1, "experiments": [dict(ticket)]}, registry_path
    )

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is False
    rendered = json.dumps(audit["canonical_record_violation_examples"])
    assert "reservation identity" in rendered or "clock is malformed" in rendered


def test_post_rollout_close_persists_log_and_first_writer_is_immutable(tmp_path):
    experiment_id = "exp-20990102-014"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    row = {
        "experiment_id": experiment_id,
        "status": "rejected",
        "decision": "rejected",
    }
    registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        _judgement("rejected"),
        tmp_path / "before.json",
        tmp_path / "after.json",
        status_override="rejected",
        log_draft=row,
    )
    closeout_audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert closeout_audit["passed"] is True

    logs_dir = tmp_path / "experiments" / "logs"
    path = registry_module.save_experiment_log_entry(
        row,
        logs_dir=logs_dir,
        registry_path=registry_path,
    )
    before = path.read_bytes()
    with pytest.raises(
        ValueError, match="payload commitment|immutable.*conflicts"
    ):
        registry_module.save_experiment_log_entry(
            {**row, "notes": "different first-writer payload"},
            allow_duplicate=True,
            logs_dir=logs_dir,
            registry_path=registry_path,
        )
    assert path.read_bytes() == before


def test_standard_close_preflights_existing_conflicting_log(tmp_path):
    experiment_id = "exp-20990102-019"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "status": "accepted",
                "decision": "accepted",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    ticket_path = tickets_dir / f"{experiment_id}.json"
    ticket_before = ticket_path.read_bytes()

    with pytest.raises(ValueError, match="existing canonical log conflicts"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            _judgement("rejected"),
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
            log_draft={
                "experiment_id": experiment_id,
                "timestamp": "first-draft",
                "status": "rejected",
                "decision": "rejected",
            },
        )

    assert ticket_path.read_bytes() == ticket_before


def test_standard_close_rejects_wrong_log_identity_before_terminal(tmp_path):
    experiment_id = "exp-20990102-022"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    ticket_path = tickets_dir / f"{experiment_id}.json"
    ticket_before = ticket_path.read_bytes()

    with pytest.raises(ValueError, match="experiment_id.*mirror"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            _judgement("rejected"),
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
            log_draft={
                "experiment_id": "exp-20990102-999",
                "status": "rejected",
                "decision": "rejected",
            },
        )

    assert ticket_path.read_bytes() == ticket_before


def test_standard_close_shard_failure_recovers_exact_ticket_intent(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-020"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    first_row = {
        "experiment_id": experiment_id,
        "timestamp": "first-draft",
        "status": "rejected",
        "decision": "rejected",
    }
    original_save_log = registry_module.save_experiment_log_entry
    monkeypatch.setattr(
        registry_module,
        "save_experiment_log_entry",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("simulated shard failure")
        ),
    )

    with pytest.raises(OSError, match="simulated shard failure"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            _judgement("rejected"),
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
            log_draft=first_row,
        )

    terminal = registry_module.load_ticket(experiment_id, tickets_dir)
    assert terminal[registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD] == (
        first_row
    )
    assert not (
        tmp_path / "experiments" / "logs" / f"{experiment_id}.json"
    ).exists()

    monkeypatch.setattr(
        registry_module, "save_experiment_log_entry", original_save_log
    )
    repaired = registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        _judgement("rejected"),
        tmp_path / "before.json",
        tmp_path / "after.json",
        status_override="rejected",
        log_draft={**first_row, "timestamp": "fresh-process-draft"},
    )

    assert repaired["status"] == "rejected"
    assert json.loads(
        (
            tmp_path
            / "experiments"
            / "logs"
            / f"{experiment_id}.json"
        ).read_text(encoding="utf-8")
    ) == first_row
    assert registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )["passed"] is True


def test_standard_close_cache_failure_surfaces_and_same_close_repairs(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-016"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    row = {
        "experiment_id": experiment_id,
        "status": "rejected",
        "decision": "rejected",
    }
    original_locked_update = registry_module.locked_registry_update
    monkeypatch.setattr(
        registry_module,
        "locked_registry_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("simulated terminal cache failure")
        ),
    )

    with pytest.raises(OSError, match="terminal cache failure"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            _judgement("rejected"),
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
            log_draft=row,
        )
    terminal = registry_module.load_ticket(experiment_id, tickets_dir)
    assert terminal["status"] == "rejected"
    assert registry_module.load_registry(registry_path)["experiments"][0][
        "status"
    ] == "claimed"

    monkeypatch.setattr(
        registry_module, "locked_registry_update", original_locked_update
    )
    repaired = registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        _judgement("rejected"),
        tmp_path / "before.json",
        tmp_path / "after.json",
        status_override="rejected",
        log_draft=row,
    )
    registry_module.save_experiment_log_entry(
        row,
        logs_dir=tmp_path / "experiments" / "logs",
        registry_path=registry_path,
    )
    assert repaired["status"] == "rejected"
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is True


def test_self_register_cache_failure_leaves_sources_and_retry_repairs(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-017"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    original_locked_update = registry_module.locked_registry_update
    monkeypatch.setattr(
        registry_module,
        "locked_registry_update",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("simulated self-register cache failure")
        ),
    )
    request_result = {"decision": "rejected", "metric": 1.0}

    with pytest.raises(OSError, match="self-register cache failure"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result=request_result,
            status="rejected",
        )
    assert registry_module.load_ticket(experiment_id, tickets_dir)["status"] == (
        "rejected"
    )
    log_path = tmp_path / "experiments" / "logs" / f"{experiment_id}.json"
    assert log_path.exists()

    monkeypatch.setattr(
        registry_module, "locked_registry_update", original_locked_update
    )
    repaired = registry_module.persist_self_registered_result(
        registry_path,
        experiment_id=experiment_id,
        lane="measurement_repair",
        prediction=None,
        result=request_result,
        status="rejected",
    )
    assert repaired["status"] == "rejected"
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is True


def test_self_register_shard_failure_recovers_from_terminal_intent(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-023"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    request_result = {"decision": "rejected", "metric": 1.0}
    original_save_log = registry_module.save_experiment_log_entry
    monkeypatch.setattr(
        registry_module,
        "save_experiment_log_entry",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError("simulated self-register shard failure")
        ),
    )

    with pytest.raises(OSError, match="self-register shard failure"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result=request_result,
            status="rejected",
        )

    terminal = registry_module.load_ticket(experiment_id, tickets_dir)
    committed_row = terminal[
        registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD
    ]
    assert terminal["status"] == "rejected"
    assert not (
        tmp_path / "experiments" / "logs" / f"{experiment_id}.json"
    ).exists()

    monkeypatch.setattr(
        registry_module, "save_experiment_log_entry", original_save_log
    )
    repaired = registry_module.persist_self_registered_result(
        registry_path,
        experiment_id=experiment_id,
        lane="measurement_repair",
        prediction=None,
        result=request_result,
        status="rejected",
    )

    assert repaired["status"] == "rejected"
    assert json.loads(
        (
            tmp_path
            / "experiments"
            / "logs"
            / f"{experiment_id}.json"
        ).read_text(encoding="utf-8")
    ) == committed_row


def test_terminal_cache_rechecks_manifest_after_ticket_and_log_write(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990102-021"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    manifest_path = manifests_dir / f"{experiment_id}.json"
    original_locked_update = registry_module.locked_registry_update

    def delete_manifest_before_mutator(path, mutator, **kwargs):
        manifest_path.unlink(missing_ok=True)
        return original_locked_update(path, mutator, **kwargs)

    monkeypatch.setattr(
        registry_module,
        "locked_registry_update",
        delete_manifest_before_mutator,
    )

    with pytest.raises(ValueError, match="reservation manifest"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            _judgement("rejected"),
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
            log_draft={
                "experiment_id": experiment_id,
                "status": "rejected",
                "decision": "rejected",
            },
        )

    assert registry_module.load_ticket(experiment_id, tickets_dir)[
        "status"
    ] == "rejected"
    assert (
        tmp_path / "experiments" / "logs" / f"{experiment_id}.json"
    ).exists()
    assert not manifest_path.exists()


def test_terminal_cache_rejects_conflicting_private_log_commitment(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-121"
    ticket = _private_ticket(experiment_id)
    artifact_path, _, _ = _write_artifact(tmp_path, experiment_id)
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    judgement = _judgement()
    draft = _draft(
        ticket, judgement, tmp_path / "before.json", artifact_path, tmp_path
    )
    monkeypatch.setattr(
        registry_module, "_revalidate_alpha_promotion_for_claim", lambda *a, **k: None
    )
    registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        judgement,
        tmp_path / "before.json",
        artifact_path,
        status_override="rejected",
        log_draft=draft,
    )
    registry = registry_module.load_registry(registry_path)
    registry["experiments"][0][
        registry_module.PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD
    ] = "f" * 64
    registry_module.save_registry(registry, registry_path)
    ticket_before = (tickets_dir / f"{experiment_id}.json").read_bytes()
    log_before = (logs_dir / f"{experiment_id}.json").read_bytes()
    registry_before = registry_path.read_bytes()

    with pytest.raises(ValueError, match="commitment conflicts"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            judgement,
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
            log_draft=draft,
        )

    assert (tickets_dir / f"{experiment_id}.json").read_bytes() == ticket_before
    assert (logs_dir / f"{experiment_id}.json").read_bytes() == log_before
    assert registry_path.read_bytes() == registry_before


def test_claimed_ticket_cannot_roll_back_to_proposed_or_duplicate_close(tmp_path):
    experiment_id = "exp-20990102-002"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    registry_module.claim_experiment_decontended(
        registry_path, experiment_id, "fixture-owner"
    )
    rolled_back = registry_module.load_ticket(experiment_id, tickets_dir)
    rolled_back.update(
        {
            "status": "proposed",
            "owner": None,
            "claimed_at": None,
            EXPERIMENT_EVER_CLAIMED: False,
        }
    )
    registry_module.save_ticket(rolled_back, tickets_dir)

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is False
    with pytest.raises(ValueError, match="ever-claimed|lifecycle|identity"):
        registry_module.claim_experiment_decontended(
            registry_path, experiment_id, "fixture-owner"
        )
    with pytest.raises(ValueError, match="ever-claimed|lifecycle|identity"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            _judgement(),
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
            realized_failure_mode="duplicate_reservation_accounting",
        )


def test_whole_strip_cannot_be_reblessed_by_claim_or_manifest_regeneration(
    tmp_path,
):
    experiment_id = "exp-20990102-003"
    registry_path, tickets_dir, manifests_dir = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    stripped = {
        "experiment_id": experiment_id,
        "status": "proposed",
        "lane": "measurement_repair",
        "created_at": "2020-01-01T00:00:00+00:00",
        "allowed_write_scope": [],
        "locked_variables": [],
    }
    registry_module.save_ticket(stripped, tickets_dir)
    registry_module.save_registry(
        {"schema_version": 1, "experiments": []}, registry_path
    )
    (manifests_dir / f"{experiment_id}.json").unlink()

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
        file_backed_registry=True,
    )
    assert audit["passed"] is False
    with pytest.raises(
        ValueError, match="reservation-time|ever-claimed|exact boolean"
    ):
        registry_module.claim_experiment_decontended(
            registry_path, experiment_id, "fixture-owner"
        )
    with pytest.raises(ValueError, match="cannot regenerate|exact boolean"):
        registry_module.save_revision_manifest(
            stripped,
            manifests_dir,
            repo_root=tmp_path,
            ticket_file=tickets_dir / f"{experiment_id}.json",
        )


def test_future_proposed_self_register_requires_duplicate_accounting(tmp_path):
    experiment_id = "exp-20990102-005"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id)
    )
    before = (tickets_dir / f"{experiment_id}.json").read_bytes()

    with pytest.raises(ValueError, match="without a claim.*duplicate"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
        )

    assert (tickets_dir / f"{experiment_id}.json").read_bytes() == before


@pytest.mark.parametrize(
    ("status", "result", "error"),
    [
        ("ACCEPTED", {"decision": "ACCEPTED"}, "terminal status"),
        ("accepted", {"decision": "rejected"}, "exactly mirror"),
    ],
)
def test_future_claimed_self_register_rejects_invalid_terminal_candidate(
    tmp_path, status, result, error
):
    experiment_id = "exp-20990102-006"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    before = (tickets_dir / f"{experiment_id}.json").read_bytes()

    with pytest.raises(ValueError, match=error):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result=result,
            status=status,
        )

    assert (tickets_dir / f"{experiment_id}.json").read_bytes() == before


def test_standard_terminal_ticket_cannot_be_overwritten_by_self_register(tmp_path):
    experiment_id = "exp-20990102-007"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        _judgement("rejected"),
        tmp_path / "before.json",
        tmp_path / "after.json",
        status_override="rejected",
        log_draft={
            "experiment_id": experiment_id,
            "status": "rejected",
            "decision": "rejected",
        },
    )
    before = (tickets_dir / f"{experiment_id}.json").read_bytes()

    with pytest.raises(ValueError, match="terminal results are immutable"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "accepted"},
            status="accepted",
        )

    assert (tickets_dir / f"{experiment_id}.json").read_bytes() == before


def test_self_register_preflights_existing_conflicting_log_before_terminal(
    tmp_path,
):
    experiment_id = "exp-20990102-015"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    log_path = logs_dir / f"{experiment_id}.json"
    log_path.write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "status": "accepted",
                "decision": "accepted",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    ticket_path = tickets_dir / f"{experiment_id}.json"
    before = ticket_path.read_bytes()

    with pytest.raises(ValueError, match="existing canonical log conflicts"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
        )

    assert ticket_path.read_bytes() == before
    assert json.loads(log_path.read_text(encoding="utf-8"))["status"] == "accepted"


@pytest.mark.parametrize(
    "field",
    [
        "hypothesis",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "revision_manifest_file",
    ],
)
def test_future_self_register_cannot_mutate_reservation_identity(
    tmp_path, field
):
    experiment_id = "exp-20990102-008"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    before = (tickets_dir / f"{experiment_id}.json").read_bytes()

    with pytest.raises(ValueError, match="identity|claim transition"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
            fields={field: "tampered"},
        )

    assert (tickets_dir / f"{experiment_id}.json").read_bytes() == before


def test_self_register_rejects_registry_only_anchor_injection(tmp_path):
    experiment_id = "exp-20990102-009"
    registry_path, tickets_dir, _ = _write_generic_bundle(
        tmp_path, _generic_ticket(experiment_id, status="claimed")
    )
    before = (tickets_dir / f"{experiment_id}.json").read_bytes()

    with pytest.raises(ValueError, match="lifecycle/identity keys"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
            fields={
                registry_module.EXPERIMENT_RESERVATION_IDENTITY_FIELD: {
                    "schema_version": 1,
                    "identity_hash": "injected",
                }
            },
        )

    assert (tickets_dir / f"{experiment_id}.json").read_bytes() == before


def test_audit_rejects_registry_ticket_pointer_redirect(tmp_path):
    experiment_a = "exp-20990101-101"
    experiment_b = "exp-20990101-102"
    tickets_dir = tmp_path / "experiments" / "tickets"
    tickets_dir.mkdir(parents=True)
    (tickets_dir / f"{experiment_b}.json").write_text(
        json.dumps(
            {
                "experiment_id": experiment_b,
                "status": "claimed",
                "lane": "measurement_repair",
                "created_at": "2099-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    registry = {
        "experiments": [
            {
                "experiment_id": experiment_a,
                "status": "claimed",
                "lane": "measurement_repair",
                "created_at": "2099-01-01T00:00:00+00:00",
                "ticket_file": f"experiments/tickets/{experiment_b}.json",
            }
        ]
    }

    audit = registry_module.audit_experiment_process(
        registry,
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
    )

    errors = " ".join(
        row["error"] for row in audit["canonical_record_violation_examples"]
    )
    assert audit["passed"] is False
    assert "ticket_file must equal" in errors
    assert "missing its canonical ticket shard" in errors


def test_audit_rejects_private_ticket_without_registry_or_manifest_anchor(tmp_path):
    ticket = _private_ticket("exp-20990101-103")
    tickets_dir = tmp_path / "experiments" / "tickets"
    tickets_dir.mkdir(parents=True)
    registry_module.save_ticket(ticket, tickets_dir)

    audit = registry_module.audit_experiment_process(
        {"experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=tmp_path / "experiments" / "logs",
    )

    errors = " ".join(
        row["error"] for row in audit["canonical_record_violation_examples"]
    )
    assert audit["passed"] is False
    assert "missing its registry identity entry" in errors
    assert "missing its valid manifest identity snapshot" in errors


def test_audit_rejects_stripped_ticket_against_independent_identity(tmp_path):
    experiment_id = "exp-20990101-104"
    ticket = _private_ticket(experiment_id)
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    stripped = {
        "experiment_id": experiment_id,
        "status": "claimed",
        "lane": "measurement_repair",
        "created_at": ticket["created_at"],
    }
    registry_module.save_ticket(stripped, tickets_dir)

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    errors = " ".join(
        row["error"] for row in audit["canonical_record_violation_examples"]
    )
    assert audit["passed"] is False
    assert "registry/ticket private replay closeout identity mismatch" in errors


def test_audit_rejects_manifest_inner_identity_drift(tmp_path):
    experiment_id = "exp-20990101-105"
    ticket = _private_ticket(experiment_id)
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    manifest_path = tmp_path / "experiments" / "manifests" / f"{experiment_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["experiment_id"] = "exp-20990101-999"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    errors = " ".join(
        row["error"] for row in audit["canonical_record_violation_examples"]
    )
    assert audit["passed"] is False
    assert "invalid private replay manifest identity snapshot" in errors


def test_committed_log_rejects_first_writer_payload_mismatch(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-106"
    ticket = _private_ticket(experiment_id)
    artifact_path, _, _ = _write_artifact(tmp_path, experiment_id)
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    judgement = _judgement()
    draft = _draft(ticket, judgement, tmp_path / "before.json", artifact_path, tmp_path)
    monkeypatch.setattr(
        registry_module, "_revalidate_alpha_promotion_for_claim", lambda *a, **k: None
    )

    registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        judgement,
        tmp_path / "before.json",
        artifact_path,
        status_override="rejected",
        log_draft=draft,
    )
    sentinel = {**draft, "delta_metrics": {"expected_value_score": 99.0}}
    with pytest.raises(ValueError, match="payload commitment"):
        registry_module.save_experiment_log_entry(sentinel, logs_dir=logs_dir)
    assert json.loads(
        (logs_dir / f"{experiment_id}.json").read_text(encoding="utf-8")
    ) == registry_module.strip_oversized_fields(draft)

    registry_module.save_experiment_log_entry(draft, logs_dir=logs_dir)
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )
    assert audit["passed"] is True


def test_terminal_mutation_rejects_draft_inconsistent_with_judgement(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-107"
    ticket = _private_ticket(experiment_id)
    artifact_path, _, _ = _write_artifact(tmp_path, experiment_id)
    registry_path, tickets_dir, _ = _write_bundle(tmp_path, ticket)
    judgement = _judgement()
    draft = _draft(ticket, judgement, tmp_path / "before.json", artifact_path, tmp_path)
    draft["delta_metrics"] = {"expected_value_score": 1.0}
    monkeypatch.setattr(
        registry_module, "_revalidate_alpha_promotion_for_claim", lambda *a, **k: None
    )

    with pytest.raises(ValueError, match="authoritative close inputs.*delta_metrics"):
        registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            judgement,
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
            log_draft=draft,
        )

    persisted = registry_module.load_ticket(experiment_id, tickets_dir)
    assert persisted["status"] == "claimed"
    assert persisted["result"] is None


def test_audit_rejects_terminal_log_with_ticket_rolled_back_to_proposed(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-108"
    ticket = _private_ticket(experiment_id)
    artifact_path, _, _ = _write_artifact(tmp_path, experiment_id)
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    judgement = _judgement()
    draft = _draft(ticket, judgement, tmp_path / "before.json", artifact_path, tmp_path)
    monkeypatch.setattr(
        registry_module, "_revalidate_alpha_promotion_for_claim", lambda *a, **k: None
    )
    registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        judgement,
        tmp_path / "before.json",
        artifact_path,
        status_override="rejected",
        log_draft=draft,
    )
    registry_module.save_experiment_log_entry(draft, logs_dir=logs_dir)
    persisted = registry_module.load_ticket(experiment_id, tickets_dir)
    persisted["status"] = "proposed"
    registry_module.save_ticket(persisted, tickets_dir)

    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )
    rendered = json.dumps(audit["research_result_ceiling_violation_examples"])
    assert audit["passed"] is False
    assert "requires a terminal ticket" in rendered


def test_private_terminal_writers_share_one_ticket_cas(tmp_path, monkeypatch):
    experiment_id = "exp-20990101-109"
    ticket = _private_ticket(experiment_id)
    artifact_path, artifact, artifact_sha256 = _write_artifact(
        tmp_path, experiment_id
    )
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    judgement = _judgement()
    draft = _draft(ticket, judgement, tmp_path / "before.json", artifact_path, tmp_path)
    monkeypatch.setattr(
        registry_module, "_revalidate_alpha_promotion_for_claim", lambda *a, **k: None
    )
    start = Barrier(2)

    def standard_close():
        start.wait()
        closed = registry_module.update_result_decontended(
            registry_path,
            experiment_id,
            judgement,
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
            log_draft=draft,
        )
        registry_module.save_experiment_log_entry(draft, logs_dir=logs_dir)
        return closed["status"]

    def self_registered_close():
        start.wait()
        closed = registry_module.persist_self_registered_result(
            registry_path,
            experiment_id=experiment_id,
            lane="alpha_search",
            prediction=_prediction(),
            result={
                "decision": "rejected",
                "artifact": artifact,
                "artifact_sha256": artifact_sha256,
                "calibration": {"actual_decision": "rejected"},
            },
            status="rejected",
        )
        return closed["status"]

    outcomes = []
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(standard_close), pool.submit(self_registered_close)]
        for future in futures:
            try:
                outcomes.append(future.result(timeout=10))
            except ValueError as exc:
                errors.append(str(exc))

    assert outcomes == ["rejected"]
    assert len(errors) == 1
    assert "terminal" in errors[0]
    persisted = registry_module.load_ticket(experiment_id, tickets_dir)
    assert persisted["status"] == "rejected"
    assert (logs_dir / f"{experiment_id}.json").exists()


def test_never_claimed_duplicate_abandonment_commits_log_and_audits(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-110"
    ticket = _private_ticket(experiment_id, status="proposed")
    artifact_path, _, _ = _write_artifact(tmp_path, experiment_id)
    registry_path, tickets_dir, logs_dir = _write_bundle(tmp_path, ticket)
    judgement = _judgement()
    draft = _draft(
        ticket,
        judgement,
        tmp_path / "before.json",
        artifact_path,
        tmp_path,
        realized_failure_mode="duplicate_reservation_accounting",
    )
    monkeypatch.setattr(
        registry_module,
        "_require_alpha_promotion_claim_receipt_for_close",
        lambda *a, **k: None,
    )

    closed = registry_module.update_result_decontended(
        registry_path,
        experiment_id,
        judgement,
        tmp_path / "before.json",
        artifact_path,
        status_override="rejected",
        realized_failure_mode="duplicate_reservation_accounting",
        log_draft=draft,
    )
    registry_module.save_experiment_log_entry(draft, logs_dir=logs_dir)
    audit = registry_module.audit_experiment_process(
        registry_module.load_registry(registry_path),
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    assert closed["status"] == "rejected"
    assert audit["passed"] is True


def test_self_register_cannot_redirect_input_id_to_another_ticket(tmp_path):
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_module.save_registry(
        {"schema_version": 1, "experiments": []}, registry_path
    )
    target_id = "exp-20990101-112"
    target_path = tmp_path / "experiments" / "tickets" / f"{target_id}.json"
    target_path.parent.mkdir(parents=True)
    target_path.write_text('{"sentinel": true}\n', encoding="utf-8")
    before = target_path.read_bytes()

    with pytest.raises(ValueError, match="lifecycle/identity keys"):
        registry_module.persist_self_registered_result(
            registry_path,
            experiment_id="exp-20990101-111",
            lane="measurement_repair",
            prediction=None,
            result={"decision": "rejected"},
            status="rejected",
            fields={"experiment_id": target_id},
        )

    assert target_path.read_bytes() == before
    assert not (
        tmp_path / "experiments" / "tickets" / "exp-20990101-111.json"
    ).exists()


def test_private_status_spelling_is_exact_and_conflicts_fail_closed(tmp_path):
    malformed = _private_ticket("exp-20990101-113")
    malformed["status"] = " Claimed"
    contender = {
        "experiment_id": "exp-20990101-114",
        "status": "proposed",
        "allowed_write_scope": malformed["allowed_write_scope"],
        "locked_variables": [],
    }
    registry = {"experiments": [malformed, contender], "_repo_root": str(tmp_path)}

    conflicts = registry_module.find_conflicts(registry, contender)
    assert conflicts[0]["experiment_id"] == malformed["experiment_id"]
    with pytest.raises(ValueError, match="exact canonical lifecycle value"):
        registry_module.claim_ticket(
            registry, malformed["experiment_id"], malformed["owner"], force=True
        )
