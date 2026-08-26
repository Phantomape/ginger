import hashlib
import json
import importlib.util
import threading
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from experiment_registry import (  # noqa: E402
    append_log_entry,
    audit_experiment_process,
    build_log_draft,
    claim_ticket,
    collect_experiment_id_sources,
    create_ticket,
    evaluate_gate,
    experiment_log_exists,
    experiment_id_exists_in_log,
    default_file_stem,
    iter_experiments,
    judge_results,
    locked_registry_update,
    load_registry,
    next_experiment_id,
    normalize_prediction,
    persist_self_registered_result,
    require_available_experiment_id,
    reserve_experiment,
    save_experiment_log_entry,
    save_registry,
    update_result,
)
import experiment_registry as experiment_registry_module  # noqa: E402
from quant.test_alpha_debate import _research_claim_receipt_fixture  # noqa: E402


def alpha_prediction():
    return {
        "success_probability": 0.4,
        "main_failure_modes": ["thin_sample"],
        "confidence_reason": (
            "Mechanism has production visible PIT evidence, nearby trials were mixed, "
            "and thin sample or concentration can still fail."
        ),
    }


class _FakeAlphaPromotionApi:
    PROMOTION_REQUIRED_LANES = frozenset(
        {"alpha_search", "alpha_discovery", "universe_scout"}
    )

    def __init__(self):
        self.revalidate_error = None
        self.revalidated = []
        self.anchor_overrides = {}

    @staticmethod
    def normalize_ticket_proposal(value):
        return dict(value)

    def validate_promotion_request(self, path, expected_proposal=None, repo_root=None):
        assert path == "data/alpha_search/promotion.json"
        assert expected_proposal["lane"] == "alpha_search"
        anchor = {
            "promotion_request_path": path,
            "promotion_request_sha256": "a" * 64,
            "promotion_hash": "b" * 64,
            "panel_path": "data/alpha_search/panel.json",
            "panel_sha256": "e" * 64,
            "panel_hash": "f" * 64,
            "selection_scope_id": "scope-fixture",
            "candidate_id": "candidate-fixture",
            "candidate_snapshot_hash": "1" * 64,
            "preflight_hash": "2" * 64,
            "research_refs": ["res-20260721-fixture"],
        }
        anchor.update(self.anchor_overrides)
        return anchor

    def revalidate_ticket_promotion(self, ticket, repo_root=None):
        self.revalidated.append((ticket["experiment_id"], repo_root))
        if self.revalidate_error is not None:
            raise ValueError(self.revalidate_error)
        return ticket["alpha_promotion"]


def _alpha_ticket_kwargs():
    return {
        "lane": "alpha_search",
        "hypothesis": "A directly observed prior/fact gap should converge.",
        "change_type": "candidate_pool",
        "single_causal_variable": "official_prior_gap",
        "causal_components": ["official fact", "observable market prior"],
        "mechanism_family": "official_prior_gap",
        "trial_family": "official_prior_gap_v1",
        "changed_variable": "candidate admission",
        "prediction": alpha_prediction(),
    }


def _research_replay_anchor_overrides():
    return {
        "admission_class": "research_replay",
        "selected_evidence_grade": "lead",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "source_readiness_bindings": [
            {
                "surface_id": "research-fixture",
                "pit_status": "research_pit",
                "source_contract_hash": "3" * 64,
                "readiness_hash": "4" * 64,
            }
        ],
    }


def _research_ticket_kwargs():
    values = _alpha_ticket_kwargs()
    values["change_type"] = "private_replay_scout"
    return values


PRIVATE_REPLAY_DISPOSITION_CONTRACT = (
    "private_replay_scout_artifact_disposition_contract_version"
)
PRIVATE_REPLAY_CLAIM_BINDING = "private_replay_scout_closeout_claim_binding"
PRIVATE_REPLAY_LOG_SHA256 = "private_replay_scout_canonical_log_sha256"
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


def _write_private_replay_result(
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
    return (
        artifact_path,
        relative_path.as_posix(),
        hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
    )


def _auditable_private_replay_ticket(
    experiment_id: str,
    *,
    status: str,
    artifact: str | None = None,
    artifact_sha256: str | None = None,
    include_contract_marker: bool = True,
    created_at: str = "2099-01-01T00:00:00+00:00",
):
    experiment_day = experiment_id[4:12]
    claimed_at = (
        f"{experiment_day[:4]}-{experiment_day[4:6]}-"
        f"{experiment_day[6:8]}T00:01:00+00:00"
        if status != "proposed"
        else None
    )
    result = {
        "decision": status,
        "calibration": {"actual_decision": status},
    }
    if artifact is not None:
        result["artifact"] = artifact
    if artifact_sha256 is not None:
        result["artifact_sha256"] = artifact_sha256
    ticket = {
        "experiment_id": experiment_id,
        "experiment_uid": f"expuid-{experiment_id[-3:]}fixture",
        "lane": "alpha_search",
        "change_type": "private_replay_scout",
        "status": status,
        "owner": "fixture-owner" if status != "proposed" else None,
        "created_at": created_at,
        "claimed_at": claimed_at,
        "prediction": alpha_prediction(),
        "alpha_promotion": _research_replay_anchor_overrides(),
        "allowed_write_scope": [f"data/experiments/{experiment_id}/"],
        "must_not_touch": [],
        "result": result,
        EXPERIMENT_EVER_CLAIMED: status != "proposed",
    }
    if include_contract_marker:
        ticket[PRIVATE_REPLAY_DISPOSITION_CONTRACT] = 1
        ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(
            ticket
        )
    if status != "proposed":
        ticket[experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
            experiment_registry_module._build_experiment_claim_transition(
                ticket, force=False
            )
        )
    return ticket


def _private_replay_log_row(ticket: dict):
    result = ticket.get("result") or {}
    row = {
        "experiment_id": ticket["experiment_id"],
        "experiment_uid": ticket.get("experiment_uid"),
        "status": ticket["status"],
        "decision": ticket["status"],
        "change_type": ticket.get("change_type"),
        "admission_class": (ticket.get("alpha_promotion") or {}).get(
            "admission_class"
        ),
        "alpha_promotion": ticket.get("alpha_promotion"),
        "research_refs": ticket.get("research_refs") or [],
        PRIVATE_REPLAY_DISPOSITION_CONTRACT: ticket.get(
            PRIVATE_REPLAY_DISPOSITION_CONTRACT
        ),
        PRIVATE_REPLAY_CLAIM_BINDING: ticket.get(PRIVATE_REPLAY_CLAIM_BINDING),
        "calibration": result.get("calibration") or {"actual_decision": ticket["status"]},
    }
    for field_name in (
        "artifact",
        "artifact_sha256",
        "artifact_disposition",
        "evidence_invalid",
    ):
        if field_name in result:
            row[field_name] = result[field_name]
    return row


def _bind_future_log_intent(ticket: dict, row: dict):
    if experiment_registry_module.experiment_reservation_identity_required(
        ticket
    ):
        canonical = experiment_registry_module.strip_oversized_fields(row)
        ticket[
            experiment_registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD
        ] = canonical
        ticket[
            experiment_registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD
        ] = experiment_registry_module._canonical_json_hash(canonical)


def _write_private_replay_log(root: Path, ticket: dict):
    path = root / "experiments" / "logs" / f"{ticket['experiment_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = _private_replay_log_row(ticket)
    ticket.setdefault("result", {})[PRIVATE_REPLAY_LOG_SHA256] = (
        experiment_registry_module._private_replay_scout_log_sha256(row)
    )
    _bind_future_log_intent(ticket, row)
    path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return path, row


def _persist_file_backed_ticket_bundle(root: Path, ticket: dict):
    """Seed a claimed/terminal fixture through the reservation claim anchors."""

    experiment_id = ticket["experiment_id"]
    tickets_dir = root / "experiments" / "tickets"
    manifests_dir = root / "experiments" / "manifests"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    reservation_ticket = dict(ticket)
    reservation_ticket.update(
        {
            "status": "proposed",
            "claimed_at": None,
            "result": None,
            EXPERIMENT_EVER_CLAIMED: False,
        }
    )
    reservation_ticket.pop(
        experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD, None
    )
    reservation_ticket.pop("alpha_promotion_claim_receipt", None)
    experiment_registry_module.save_ticket(reservation_ticket, tickets_dir)
    experiment_registry_module.save_revision_manifest(
        reservation_ticket,
        manifests_dir,
        repo_root=root,
        ticket_file=tickets_dir / f"{experiment_id}.json",
        overwrite=False,
    )
    claimed_ticket = dict(ticket)
    claimed_ticket.update(
        {
            "status": "claimed",
            "completed_at": None,
            "result": None,
            EXPERIMENT_EVER_CLAIMED: True,
        }
    )
    claimed_ticket[
        experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD
    ] = (
        experiment_registry_module._build_experiment_claim_transition(
            claimed_ticket, force=False
        )
    )
    experiment_registry_module._save_claim_transition_manifest_intent(
        claimed_ticket, manifests_dir
    )
    experiment_registry_module.save_ticket(claimed_ticket, tickets_dir)
    experiment_registry_module.save_revision_manifest(
        claimed_ticket,
        manifests_dir,
        repo_root=root,
        ticket_file=tickets_dir / f"{experiment_id}.json",
    )
    ticket[experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
        claimed_ticket[experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD]
    )
    if ticket.get("status") != "claimed":
        experiment_registry_module.save_ticket(ticket, tickets_dir)
        experiment_registry_module.save_revision_manifest(
            ticket,
            manifests_dir,
            repo_root=root,
            ticket_file=tickets_dir / f"{experiment_id}.json",
        )
    return tickets_dir / f"{experiment_id}.json"


def test_alpha_ticket_requires_hash_bound_promotion_before_any_reservation(tmp_path):
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }

    with pytest.raises(ValueError, match="requires --promotion-request"):
        create_ticket(registry, **_alpha_ticket_kwargs())

    assert registry["experiments"] == []


def test_alpha_ticket_stores_promotion_and_claim_revalidates_before_force(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    ticket = create_ticket(
        registry,
        promotion_request="data/alpha_search/promotion.json",
        **_alpha_ticket_kwargs(),
    )

    assert ticket["research_refs"] == ["res-20260721-fixture"]
    assert ticket["alpha_promotion"]["candidate_id"] == "candidate-fixture"

    fake.revalidate_error = "promotion artifact was tampered"
    with pytest.raises(ValueError, match="tampered"):
        claim_ticket(registry, ticket["experiment_id"], "codex", force=True)
    assert ticket["status"] == "proposed"

    fake.revalidate_error = None
    claimed, conflicts = claim_ticket(
        registry, ticket["experiment_id"], "codex", force=True
    )
    assert conflicts == []
    assert claimed["status"] == "claimed"
    assert len(fake.revalidated) == 2


def test_research_replay_anchor_is_stored_and_claim_revalidated(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    fake.anchor_overrides = _research_replay_anchor_overrides()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    ticket = create_ticket(
        registry,
        promotion_request="data/alpha_search/promotion.json",
        **_research_ticket_kwargs(),
    )

    assert ticket["alpha_promotion"]["admission_class"] == "research_replay"
    assert ticket["alpha_promotion"]["result_ceiling"] == "observed_only"
    assert ticket["alpha_promotion"]["paper_live_eligible"] is False
    claimed, conflicts = claim_ticket(
        registry, ticket["experiment_id"], "codex", force=True
    )
    assert conflicts == []
    assert claimed["status"] == "claimed"
    assert fake.revalidated == [(ticket["experiment_id"], tmp_path)]


def test_real_research_claim_creates_receipt_and_audit_uses_snapshot(tmp_path):
    fixture = _research_claim_receipt_fixture(tmp_path)
    ticket = fixture["ticket"]
    ticket.update(
        {
            "experiment_id": "exp-20260729-901",
            "owner": None,
            "allowed_write_scope": [],
            "locked_variables": [],
        }
    )
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }

    claimed, conflicts = claim_ticket(
        registry, ticket["experiment_id"], "codex", force=True
    )
    assert conflicts == []
    assert claimed["status"] == "claimed"
    receipt = claimed["alpha_promotion_claim_receipt"]
    assert receipt["claimed_validation_at"] == claimed["claimed_at"]
    assert receipt["research_artifact_snapshots"]

    fixture["paths"]["artifact"].write_text(
        json.dumps({"timestamp": "2099-01-01T00:02:00Z", "probability": 0.8}),
        encoding="utf-8",
    )
    updated = update_result(
        registry,
        ticket["experiment_id"],
        {
            "decision": "rejected",
            "acceptance_reasons": [],
            "before_metrics": {"expected_value_score": 1.0},
            "after_metrics": {"expected_value_score": 0.5},
            "delta_metrics": {"expected_value_score": -0.5},
        },
        "before.json",
        "after.json",
        status_override="rejected",
        realized_failure_mode="fixture_rejected",
        surprise_note="Receipt-backed closeout fixture.",
    )
    assert updated["status"] == "rejected"
    assert updated["alpha_promotion_claim_receipt"] == receipt
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    audit = audit_experiment_process(
        registry,
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )
    assert audit["invalid_alpha_promotion_count"] == 0

    claimed["alpha_promotion_claim_receipt"]["receipt_hash"] = "0" * 64
    forged_audit = audit_experiment_process(
        registry,
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )
    assert forged_audit["invalid_alpha_promotion_count"] == 1
    assert "claim_receipt_hash_mismatch" in forged_audit[
        "invalid_alpha_promotion_examples"
    ][0]["error"]


def test_post_rollout_measurement_ticket_claim_does_not_require_alpha_receipt(
    tmp_path,
):
    ticket = {
        "experiment_id": "exp-20990101-104",
        "experiment_uid": "expuid-measurement-fixture",
        "lane": "measurement_repair",
        "status": "proposed",
        "owner": None,
        "created_at": "2099-01-01T00:00:00+00:00",
        "claimed_at": None,
        "allowed_write_scope": [],
        "locked_variables": [],
    }
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }

    claimed, conflicts = claim_ticket(
        registry, ticket["experiment_id"], "codex", force=True
    )

    assert conflicts == []
    assert claimed["status"] == "claimed"
    assert claimed["owner"] == "codex"
    assert claimed["claimed_at"]
    assert "alpha_promotion" not in claimed
    assert "alpha_promotion_claim_receipt" not in claimed


def test_real_research_claim_tamper_before_claim_leaves_ticket_proposed(tmp_path):
    fixture = _research_claim_receipt_fixture(tmp_path)
    ticket = fixture["ticket"]
    ticket.update(
        {
            "experiment_id": "exp-20260729-902",
            "owner": None,
            "allowed_write_scope": [],
            "locked_variables": [],
        }
    )
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    fixture["paths"]["artifact"].write_text("tampered before claim", encoding="utf-8")

    with pytest.raises(ValueError, match="research_artifact_sha256_mismatch"):
        claim_ticket(registry, ticket["experiment_id"], "codex", force=True)
    assert ticket["status"] == "proposed"
    assert ticket["claimed_at"] is None
    assert "alpha_promotion_claim_receipt" not in ticket


def test_post_rollout_proposed_alpha_cannot_close_without_claim_receipt(tmp_path):
    fixture = _research_claim_receipt_fixture(tmp_path)
    ticket = fixture["ticket"]
    ticket.update(
        {
            "experiment_id": "exp-20260729-903",
            "owner": None,
            "allowed_write_scope": [],
            "locked_variables": [],
        }
    )
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 0.5},
        "delta_metrics": {"expected_value_score": -0.5},
    }

    with pytest.raises(ValueError, match="cannot close without a successful claim"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "before.json",
            "after.json",
            status_override="rejected",
        )
    assert ticket["status"] == "proposed"
    assert ticket.get("result") is None


def test_post_rollout_proposed_alpha_cannot_self_close_without_receipt(
    tmp_path, monkeypatch
):
    fixture = _research_claim_receipt_fixture(tmp_path)
    ticket = fixture["ticket"]
    ticket["experiment_id"] = "exp-20260729-904"
    docs_dir = tmp_path / "docs"
    tickets_dir = tmp_path / "experiments" / "tickets"
    docs_dir.mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    registry_path = docs_dir / "experiment_registry.json"
    save_registry(
        {
            "schema_version": 1,
            "updated_at": None,
            "experiments": [ticket],
        },
        registry_path,
    )
    (tickets_dir / f"{ticket['experiment_id']}.json").write_text(
        json.dumps(ticket, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(experiment_registry_module, "REPO_ROOT", tmp_path)

    with pytest.raises(ValueError, match="cannot close without a successful claim"):
        persist_self_registered_result(
            registry_path,
            experiment_id=ticket["experiment_id"],
            lane="alpha_search",
            status="rejected",
            prediction=ticket["prediction"],
            result={"decision": "rejected"},
            allow_missing_prediction=True,
        )
    persisted = json.loads(
        (tickets_dir / f"{ticket['experiment_id']}.json").read_text(encoding="utf-8")
    )
    assert persisted["status"] == "proposed"


def test_claim_transition_is_idempotent_for_owner_and_rejects_takeover_or_reopen():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Protect claim state transitions.",
        change_type="identity_or_measurement_repair",
        single_causal_variable="claim transition guard",
    )
    claimed, conflicts = claim_ticket(registry, ticket["experiment_id"], "agent-a")
    assert conflicts == []
    original_claimed_at = claimed["claimed_at"]

    same, conflicts = claim_ticket(registry, ticket["experiment_id"], "agent-a")
    assert conflicts == []
    assert same["claimed_at"] == original_claimed_at
    with pytest.raises(ValueError, match="owner takeover"):
        claim_ticket(registry, ticket["experiment_id"], "agent-b", force=True)
    claimed["status"] = "rejected"
    claimed["result"] = {"decision": "rejected"}
    with pytest.raises(ValueError, match="cannot transition"):
        claim_ticket(registry, ticket["experiment_id"], "agent-a", force=True)
    assert claimed["status"] == "rejected"


def test_future_experiment_id_cannot_backdate_away_promotion_enforcement():
    ticket = {
        "experiment_id": "exp-20990101-105",
        "lane": "alpha_search",
        "status": "proposed",
        "owner": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "claimed_at": None,
        "prediction": alpha_prediction(),
        "allowed_write_scope": [],
        "locked_variables": [],
    }
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_enforce_alpha_promotion": True,
    }
    with pytest.raises(ValueError, match="missing hash-bound"):
        claim_ticket(registry, ticket["experiment_id"], "codex", force=True)
    assert ticket["status"] == "proposed"


def test_legacy_alpha_cannot_be_claimed_into_receipt_era_without_proof(monkeypatch):
    ticket = {
        "experiment_id": "exp-20200101-001",
        "lane": "alpha_search",
        "status": "proposed",
        "owner": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "claimed_at": None,
        "prediction": alpha_prediction(),
        "allowed_write_scope": [],
        "locked_variables": [],
    }
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_enforce_alpha_promotion": True,
    }
    monkeypatch.setattr(
        experiment_registry_module,
        "utc_now_iso",
        lambda: "2099-01-01T00:00:00+00:00",
    )
    with pytest.raises(ValueError, match="without a promotion anchor"):
        claim_ticket(registry, ticket["experiment_id"], "codex", force=True)
    assert ticket["status"] == "proposed"


def test_audit_checks_receipt_rollout_for_legacy_reserved_claim(tmp_path):
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [
            {
                "experiment_id": "exp-20200101-002",
                "lane": "alpha_search",
                "status": "claimed",
                "created_at": "2020-01-01T00:00:00+00:00",
                "claimed_at": "2099-01-01T00:00:00+00:00",
                "prediction": alpha_prediction(),
            }
        ],
    }
    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "tickets",
        logs_dir=tmp_path / "logs",
    )
    assert audit["passed"] is False
    assert audit["missing_alpha_promotion_count"] == 1


def test_measurement_repair_does_not_require_alpha_promotion(tmp_path):
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }

    ticket = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Make promotion admission measurable.",
        change_type="measurement_instrumentation",
        single_causal_variable="promotion admission telemetry",
    )

    assert ticket["status"] == "proposed"
    assert "alpha_promotion" not in ticket


def test_audit_blocks_post_enforcement_alpha_without_promotion(tmp_path):
    registry = {
        "schema_version": 1,
        "experiments": [
            {
                "experiment_id": "exp-20990101-001",
                "lane": "alpha_search",
                "status": "proposed",
                "created_at": "2099-01-01T00:00:00+00:00",
                "prediction": alpha_prediction(),
            }
        ],
        "_enforce_alpha_promotion": True,
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "tickets",
        logs_dir=tmp_path / "logs",
    )

    assert audit["passed"] is False
    assert audit["missing_alpha_promotion_count"] == 1
    assert audit["missing_alpha_promotion_examples"][0]["experiment_id"] == (
        "exp-20990101-001"
    )


def test_audit_blocks_research_replay_above_observed_only_ceiling(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    fake.anchor_overrides = _research_replay_anchor_overrides()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    anchor = fake.validate_promotion_request(
        "data/alpha_search/promotion.json",
        expected_proposal={"lane": "alpha_search"},
    )
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [
            {
                "experiment_id": "exp-20990101-002",
                "lane": "alpha_search",
                "status": "accepted_paper_pending_forward",
                "created_at": "2099-01-01T00:00:00+00:00",
                "prediction": alpha_prediction(),
                "alpha_promotion": anchor,
                "research_refs": anchor["research_refs"],
                "result": {"decision": "accepted_paper_pending_forward"},
            }
        ],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "tickets",
        logs_dir=tmp_path / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_replay_count"] == 1
    assert audit["research_result_ceiling_violation_count"] == 1


def test_audit_accepts_all_future_private_replay_disposition_mappings(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    tickets = []
    mappings = [
        ("observed_only", "positive_replay_lead_not_promoted", False),
        ("rejected", "rejected", False),
        ("rejected", "inconclusive_insufficient_sample", False),
        ("rejected", "invalid_contaminated", True),
    ]
    for sequence, (status, disposition, evidence_invalid) in enumerate(
        mappings, start=10
    ):
        experiment_id = f"exp-20990101-{sequence:03d}"
        _, artifact, artifact_sha256 = _write_private_replay_result(
            tmp_path,
            experiment_id,
            status=status,
            disposition=disposition,
            evidence_invalid=evidence_invalid,
        )
        ticket = _auditable_private_replay_ticket(
            experiment_id,
            status=status,
            artifact=artifact,
            artifact_sha256=artifact_sha256,
        )
        ticket["result"].update(
            {
                "artifact_disposition": disposition,
                "evidence_invalid": evidence_invalid,
            }
        )
        _write_private_replay_log(tmp_path, ticket)
        tickets_dir = tmp_path / "experiments" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / f"{experiment_id}.json").write_text(
            json.dumps(ticket, indent=2) + "\n", encoding="utf-8"
        )
        tickets.append(ticket)
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": tickets,
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is True
    assert audit["research_replay_count"] == 4
    assert audit["research_result_ceiling_violation_count"] == 0


def test_audit_blocks_closed_future_private_replay_ticket_without_log_shard(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-025"
    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    ticket["result"].update(
        {"artifact_disposition": "rejected", "evidence_invalid": False}
    )
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    assert "log" in " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    ).lower()


def test_audit_blocks_orphan_future_private_replay_log_shard(tmp_path, monkeypatch):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-026"
    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    ticket["result"].update(
        {"artifact_disposition": "rejected", "evidence_invalid": False}
    )
    _write_private_replay_log(tmp_path, ticket)

    audit = audit_experiment_process(
        {"schema_version": 1, "_enforce_alpha_promotion": True, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    rendered = json.dumps(audit).lower()
    assert audit["passed"] is False
    assert experiment_id in rendered
    assert "orphan" in rendered


@pytest.mark.parametrize(
    ("field_name", "mismatched_value"),
    [
        ("artifact_sha256", "0" * 64),
        ("artifact_disposition", "inconclusive_insufficient_sample"),
        ("evidence_invalid", True),
    ],
)
def test_audit_blocks_future_private_replay_ticket_log_binding_mismatch(
    tmp_path, monkeypatch, field_name, mismatched_value
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-027"
    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    ticket["result"].update(
        {"artifact_disposition": "rejected", "evidence_invalid": False}
    )
    log_path, log_row = _write_private_replay_log(tmp_path, ticket)
    log_row[field_name] = mismatched_value
    log_path.write_text(json.dumps(log_row, indent=2) + "\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    assert field_name in " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )


def test_audit_blocks_future_private_replay_ticket_log_artifact_path_mismatch(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-028"
    artifact_path, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    ticket["result"].update(
        {"artifact_disposition": "rejected", "evidence_invalid": False}
    )
    alternate_path = artifact_path.with_name("alternate_private_replay_result.json")
    alternate_path.write_bytes(artifact_path.read_bytes())
    alternate_artifact = alternate_path.relative_to(tmp_path).as_posix()
    log_path, log_row = _write_private_replay_log(tmp_path, ticket)
    log_row["artifact"] = alternate_artifact
    log_path.write_text(json.dumps(log_row, indent=2) + "\n", encoding="utf-8")
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    assert "artifact" in " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )


@pytest.mark.parametrize(
    "created_at",
    [
        "2026-08-22T01:00:00+00:00",
        "not-a-timestamp",
        "2026-08-22T01:00:00",
        None,
    ],
)
def test_audit_preserves_markerless_legacy_private_replay_closeout_by_experiment_date(
    tmp_path, monkeypatch, created_at
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    ticket = _auditable_private_replay_ticket(
        "exp-20260822-001",
        status="rejected",
        include_contract_marker=False,
        created_at=created_at,
    )
    if created_at is None:
        ticket.pop("created_at")
    ticket.pop(EXPERIMENT_EVER_CLAIMED, None)
    ticket.pop(
        experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD, None
    )
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is True
    assert audit["research_replay_count"] == 1
    assert audit["research_result_ceiling_violation_count"] == 0


def test_audit_buckets_legacy_research_closeout_violation_as_report_only(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    ticket = _auditable_private_replay_ticket(
        "exp-20260810-901",
        status="observed_only_rejected",
        include_contract_marker=False,
        created_at="2026-08-10T00:00:00+00:00",
    )
    ticket.pop(EXPERIMENT_EVER_CLAIMED, None)
    ticket.pop(
        experiment_registry_module.EXPERIMENT_CLAIM_TRANSITION_FIELD, None
    )
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["research_result_ceiling_violation_count"] == 1
    assert audit["post_enforcement_research_result_ceiling_violation_count"] == 0
    assert audit["legacy_research_result_ceiling_violation_count"] == 1
    assert audit["passed"] is True
    assert audit["legacy_research_result_ceiling_violation_examples"][0][
        "enforcement_bucket"
    ] == "legacy_pre_enforcement"


@pytest.mark.parametrize("status", ["proposed", "claimed"])
def test_audit_blocks_open_future_private_replay_ticket_missing_contract_marker(
    tmp_path, monkeypatch, status
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    ticket = _auditable_private_replay_ticket(
        "exp-20990101-021",
        status=status,
        include_contract_marker=False,
        created_at="2020-01-01T00:00:00+00:00",
    )
    ticket["hub_identity"] = {
        "reserved_at": "2099-01-01T00:00:00+00:00"
    }
    ticket["result"] = None
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    assert "contract" in " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )


@pytest.mark.parametrize("status", ["proposed", "claimed"])
def test_claim_blocks_future_private_replay_ticket_missing_contract_marker(
    tmp_path, monkeypatch, status
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    ticket = _auditable_private_replay_ticket(
        "exp-20990101-022",
        status=status,
        include_contract_marker=False,
        created_at="2020-01-01T00:00:00+00:00",
    )
    ticket.update(
        {
            "hub_identity": {"reserved_at": "2099-01-01T00:00:00+00:00"},
            "owner": "codex" if status == "claimed" else None,
            "claimed_at": (
                "2099-01-01T00:01:00+00:00" if status == "claimed" else None
            ),
            "result": None,
        }
    )
    registry = {
        "schema_version": 1,
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    with pytest.raises(ValueError, match="contract|marker|version"):
        claim_ticket(registry, ticket["experiment_id"], "codex", force=True)

    assert ticket["status"] == status


@pytest.mark.parametrize(
    ("ticket_status", "result_decision", "result_status"),
    [
        ("Rejected", "rejected", None),
        (" rejected ", "rejected", None),
        ("rejected", "Rejected", None),
        ("rejected", " rejected ", None),
        ("rejected", "rejected", "Rejected"),
        ("rejected", "observed_only", None),
        ("rejected", "rejected", "observed_only"),
    ],
)
def test_audit_requires_canonical_consistent_private_replay_outer_terminal_fields(
    tmp_path, monkeypatch, ticket_status, result_decision, result_status
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-023"
    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    ticket["status"] = ticket_status
    ticket["result"]["decision"] = result_decision
    if result_status is not None:
        ticket["result"]["status"] = result_status
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    reasons = " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )
    assert "status" in reasons or "decision" in reasons or "canonical" in reasons


@pytest.mark.parametrize("disposition", [[], {}])
def test_audit_reports_non_string_private_replay_disposition_as_violation(
    tmp_path, monkeypatch, disposition
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-024"
    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition=disposition,
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    log_row = {
        "experiment_id": experiment_id,
        "status": "rejected",
        "decision": "rejected",
        "artifact": artifact,
        "artifact_sha256": artifact_sha256,
    }
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps(log_row), encoding="utf-8"
    )
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    assert "disposition" in " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )


@pytest.mark.parametrize(
    ("case", "error_pattern"),
    [
        ("missing_contract_marker", "contract|marker|version"),
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
    ],
)
def test_audit_rejects_future_private_replay_artifact_contract_violations(
    tmp_path, monkeypatch, case, error_pattern
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-020"
    status = "rejected"
    disposition = "rejected"
    evidence_invalid = False
    overrides = {}
    payload = None
    include_contract_marker = case != "missing_contract_marker"

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
        overrides["record_type"] = "wrong_type"
    elif case == "status_identity_mismatch":
        overrides["status"] = "observed_only"
    elif case == "decision_identity_mismatch":
        overrides["decision"] = "observed_only"
    elif case == "contaminated_without_invalid_flag":
        disposition = "invalid_contaminated"
    elif case == "clean_disposition_with_invalid_flag":
        evidence_invalid = True

    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status=status,
        disposition=disposition,
        evidence_invalid=evidence_invalid,
        overrides=overrides,
        payload=payload,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status=status,
        artifact=artifact,
        artifact_sha256=artifact_sha256,
        include_contract_marker=include_contract_marker,
    )
    if case == "artifact_hash_mismatch":
        ticket["result"]["artifact_sha256"] = "0" * 64
    elif case == "artifact_outside_repo":
        ticket["result"]["artifact"] = "../outside-private-replay-result.json"
    elif case == "missing_artifact_binding":
        ticket["result"].pop("artifact")
    elif case == "artifact_outside_allowed_scope":
        ticket["allowed_write_scope"] = ["data/experiments/some-other-experiment/"]
    elif case == "artifact_in_must_not_touch":
        ticket["must_not_touch"] = [artifact]
    elif case == "result_decision_mismatch":
        ticket["result"]["decision"] = "observed_only"
    elif case == "result_status_mismatch":
        ticket["result"]["status"] = "observed_only"
    elif case == "artifact_disposition_mirror_mismatch":
        ticket["result"]["artifact_disposition"] = "invalid_contaminated"
    elif case == "evidence_invalid_mirror_mismatch":
        ticket["result"]["evidence_invalid"] = True
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_result_ceiling_violation_count"] == 1
    violation = audit["research_result_ceiling_violation_examples"][0]
    assert violation["experiment_id"] == experiment_id
    assert any(
        __import__("re").search(error_pattern, reason, flags=__import__("re").IGNORECASE)
        for reason in violation["violations"]
    )


def test_audit_private_replay_contract_cannot_be_bypassed_by_lane_demotion(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-036"
    ticket = _auditable_private_replay_ticket(experiment_id, status="claimed")
    ticket["lane"] = "measurement_repair"
    ticket.pop(PRIVATE_REPLAY_DISPOSITION_CONTRACT)
    registry = {
        "schema_version": 1,
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["research_replay_count"] == 1
    violation_text = " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )
    assert "demote lane" in violation_text
    assert PRIVATE_REPLAY_DISPOSITION_CONTRACT in violation_text


def test_future_private_replay_claim_cannot_be_bypassed_by_lane_demotion(tmp_path):
    experiment_id = "exp-20990101-042"
    ticket = _auditable_private_replay_ticket(experiment_id, status="proposed")
    ticket["lane"] = "measurement_repair"
    ticket["owner"] = None
    ticket.pop(PRIVATE_REPLAY_DISPOSITION_CONTRACT)
    registry = {
        "schema_version": 1,
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    with pytest.raises(ValueError, match="cannot demote lane"):
        claim_ticket(registry, experiment_id, "codex", force=True)

    assert ticket["status"] == "proposed"
    assert ticket["owner"] is None
    assert "alpha_promotion_claim_receipt" not in ticket


def test_future_private_replay_claim_binding_detects_scope_drift(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    experiment_id = "exp-20990101-043"
    ticket = _auditable_private_replay_ticket(experiment_id, status="proposed")
    ticket["owner"] = None
    registry = {
        "schema_version": 1,
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    claimed, conflicts = claim_ticket(registry, experiment_id, "codex", force=True)

    assert conflicts == []
    assert claimed["status"] == "claimed"
    assert claimed[PRIVATE_REPLAY_CLAIM_BINDING] == _private_replay_claim_binding(
        claimed
    )
    claimed["allowed_write_scope"] = ["data/experiments/widened/"]

    with pytest.raises(ValueError, match="claim binding.*allowed_write_scope"):
        claim_ticket(registry, experiment_id, "codex", force=True)


def test_audit_future_private_replay_requires_research_anchor_after_claim(tmp_path):
    experiment_id = "exp-20990101-044"
    ticket = _auditable_private_replay_ticket(experiment_id, status="claimed")
    ticket.pop("alpha_promotion")
    ticket.pop(PRIVATE_REPLAY_DISPOSITION_CONTRACT)
    registry = {"schema_version": 1, "experiments": [ticket]}

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    violations = " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )
    assert "admission_class='research_replay'" in violations
    assert "claim binding" in violations


@pytest.mark.parametrize("matching_log", [False, True])
def test_audit_blocks_registry_cache_without_canonical_ticket_shard(
    tmp_path, matching_log
):
    experiment_id = "exp-20990101-050"
    ticket = {
        "experiment_id": experiment_id,
        "lane": "measurement_repair",
        "status": "proposed",
        "created_at": "2099-01-01T00:00:00+00:00",
    }
    if matching_log:
        logs_dir = tmp_path / "experiments" / "logs"
        logs_dir.mkdir(parents=True)
        (logs_dir / f"{experiment_id}.json").write_text(
            json.dumps(
                {"experiment_id": experiment_id, "decision": "rejected"}
            ),
            encoding="utf-8",
        )
    registry = {"schema_version": 1, "experiments": [ticket]}

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert any(
        item["canonical_experiment_id"] == experiment_id
        and "missing its canonical ticket shard" in item["error"]
        for item in audit["canonical_record_violation_examples"]
    )


def test_audit_blocks_open_private_contract_cache_without_ticket_shard(tmp_path):
    experiment_id = "exp-20990101-051"
    ticket = _auditable_private_replay_ticket(experiment_id, status="proposed")
    ticket["result"] = None
    registry = {"schema_version": 1, "experiments": [ticket]}

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert any(
        "missing its canonical ticket shard" in item["error"]
        for item in audit["canonical_record_violation_examples"]
    )


@pytest.mark.parametrize(
    ("mutation", "error_pattern"),
    [
        ("missing_change_type", "change_type='private_replay_scout'"),
        ("settled_forward_anchor", "admission_class='research_replay'"),
    ],
)
def test_future_private_replay_claim_rejects_contract_identity_swaps(
    tmp_path, mutation, error_pattern
):
    experiment_id = "exp-20990101-046"
    ticket = _auditable_private_replay_ticket(experiment_id, status="proposed")
    ticket["owner"] = None
    if mutation == "missing_change_type":
        ticket.pop("change_type")
    else:
        ticket["alpha_promotion"].update(_settled_forward_anchor_overrides())
    registry = {
        "schema_version": 1,
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
        "experiments": [ticket],
    }

    with pytest.raises(ValueError, match=error_pattern):
        claim_ticket(registry, experiment_id, "codex", force=True)

    assert ticket["status"] == "proposed"


@pytest.mark.parametrize("mutation", ["missing_change_type", "settled_forward_anchor"])
def test_audit_future_private_replay_rejects_contract_identity_swaps(
    tmp_path, mutation
):
    experiment_id = "exp-20990101-047"
    ticket = _auditable_private_replay_ticket(experiment_id, status="claimed")
    if mutation == "missing_change_type":
        ticket.pop("change_type")
    else:
        ticket["alpha_promotion"].update(_settled_forward_anchor_overrides())
    registry = {"schema_version": 1, "experiments": [ticket]}

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    violations = " ".join(
        audit["research_result_ceiling_violation_examples"][0]["violations"]
    )
    assert "private replay contract identity requires" in violations


@pytest.mark.parametrize("mutation", ["missing_change_type", "settled_forward_anchor"])
def test_closeout_future_private_replay_rejects_contract_identity_swaps(
    tmp_path, mutation
):
    experiment_id = "exp-20990101-054"
    ticket = _auditable_private_replay_ticket(experiment_id, status="claimed")
    ticket["result"] = None
    if mutation == "missing_change_type":
        ticket.pop("change_type")
    else:
        ticket["alpha_promotion"].update(_settled_forward_anchor_overrides())
    registry = {"schema_version": 1, "experiments": [ticket]}
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {},
        "after_metrics": {},
        "delta_metrics": {},
    }

    with pytest.raises(ValueError, match="private replay contract identity requires"):
        update_result(
            registry,
            experiment_id,
            judgement,
            tmp_path / "before.json",
            tmp_path / "after.json",
            status_override="rejected",
        )

    assert ticket["status"] == "claimed"


@pytest.mark.parametrize("record_type", ["ticket", "log"])
def test_audit_binds_canonical_filename_to_inner_experiment_id(tmp_path, record_type):
    canonical_id = "exp-20990101-037"
    declared_id = "exp-20990101-038"
    registry = {
        "schema_version": 1,
        "experiments": [
            {
                "experiment_id": declared_id,
                "lane": "measurement_repair",
                "status": "proposed",
            }
        ],
    }
    directory = tmp_path / "experiments" / f"{record_type}s"
    directory.mkdir(parents=True)
    (directory / f"{canonical_id}.json").write_text(
        json.dumps(
            {
                "experiment_id": declared_id,
                "lane": "measurement_repair",
                "status": "proposed",
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert audit["canonical_record_violation_count"] >= 1
    assert any(
        item["record_type"] == record_type
        and item["canonical_experiment_id"] == canonical_id
        and item["declared_experiment_id"] == declared_id
        for item in audit["canonical_record_violation_examples"]
    )


@pytest.mark.parametrize("record_type", ["ticket", "log"])
def test_audit_reports_legacy_filename_identity_debt_without_blocking(
    tmp_path, record_type
):
    canonical_id = "exp-20260417-902"
    declared_id = "exp-20260417-903"
    registry = {"schema_version": 1, "experiments": []}
    directory = tmp_path / "experiments" / f"{record_type}s"
    directory.mkdir(parents=True)
    (directory / f"{canonical_id}_legacy_suffix.json").write_text(
        json.dumps(
            {
                "experiment_id": declared_id,
                "lane": "measurement_repair",
                "status": "rejected",
                "created_at": "2026-04-17T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        registry,
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is True
    assert audit["canonical_record_violation_count"] == 0
    assert audit["legacy_canonical_record_violation_count"] >= 1
    assert any(
        item["record_type"] == record_type
        and item["enforcement_bucket"] == "legacy_pre_enforcement"
        for item in audit["legacy_canonical_record_violation_examples"]
    )


def test_audit_rejects_orphan_log_even_without_private_replay_markers(tmp_path):
    experiment_id = "exp-20990101-039"
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps({"experiment_id": experiment_id, "decision": "rejected"}),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert audit["canonical_record_violation_count"] == 1
    assert "orphan" in audit["canonical_record_violation_examples"][0]["error"]


def test_audit_reports_legacy_orphan_log_without_blocking(tmp_path):
    experiment_id = "exp-20260417-901"
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps({"experiment_id": experiment_id, "decision": "rejected"}),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is True
    assert audit["canonical_record_violation_count"] == 0
    assert audit["legacy_orphan_log_count"] == 1


def test_audit_blocks_old_id_orphan_with_post_cutoff_clock(tmp_path):
    experiment_id = "exp-20260417-904"
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "decision": "rejected",
                "created_at": "2099-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert audit["canonical_record_violation_count"] == 1
    assert audit["canonical_record_violation_examples"][0][
        "enforcement_bucket"
    ] == "post_enforcement"


def test_audit_explicit_contract_marker_overrides_legacy_record_date(tmp_path):
    experiment_id = "exp-20260417-905"
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}_legacy_suffix.json").write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "decision": "rejected",
                PRIVATE_REPLAY_DISPOSITION_CONTRACT: 1,
                "created_at": "2026-04-17T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert any(
        item["enforcement_bucket"] == "post_enforcement"
        and "filename stem" in item["error"]
        for item in audit["canonical_record_violation_examples"]
    )


@pytest.mark.parametrize("record_type", ["ticket", "log"])
@pytest.mark.parametrize(
    "filename",
    [
        "exp_20990101_048.json",
        "EXP-20990101-048.json",
        "alternate-record.json",
    ],
)
def test_audit_blocks_alternate_post_enforcement_record_filenames(
    tmp_path, record_type, filename
):
    experiment_id = "exp-20990101-048"
    directory = tmp_path / "experiments" / f"{record_type}s"
    directory.mkdir(parents=True)
    (directory / filename).write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "lane": "measurement_repair",
                "status": "rejected",
                "created_at": "2099-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert any(
        item["record_type"] == record_type
        and item["canonical_experiment_id"] == experiment_id
        and "filename stem" in item["error"]
        for item in audit["canonical_record_violation_examples"]
    )


@pytest.mark.parametrize("record_type", ["ticket", "log"])
def test_audit_blocks_non_object_post_enforcement_record_files(tmp_path, record_type):
    experiment_id = "exp-20990101-049"
    directory = tmp_path / "experiments" / f"{record_type}s"
    directory.mkdir(parents=True)
    (directory / f"{experiment_id}.json").write_text("[]", encoding="utf-8")

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=tmp_path / "experiments" / "logs",
    )

    assert audit["passed"] is False
    assert any(
        item["record_type"] == record_type
        and "JSON object" in item["error"]
        for item in audit["canonical_record_violation_examples"]
    )


def test_audit_reports_exp_like_legacy_record_with_naive_pre_cutoff_clock(tmp_path):
    experiment_id = "exp-next-777"
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "decision": "rejected",
                "timestamp": "2026-04-18T22:19:00.736517",
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is True
    assert audit["canonical_record_violation_count"] == 0
    assert audit["legacy_canonical_record_violation_count"] == 2


def test_audit_blocks_undated_non_object_exp_like_record(tmp_path):
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "exp-future-record.json").write_text("[]", encoding="utf-8")

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert audit["canonical_record_violation_count"] == 1


@pytest.mark.parametrize(
    ("created_at", "expected_passed"),
    [
        ("2026-08-26T05:09:59+00:00", True),
        ("2026-08-26T05:10:00+00:00", False),
    ],
)
def test_audit_canonical_record_cutoff_is_inclusive(
    tmp_path, created_at, expected_passed
):
    experiment_id = "exp-20260417-906"
    logs_dir = tmp_path / "experiments" / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / f"{experiment_id}.json").write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "decision": "rejected",
                "created_at": created_at,
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "experiments": []},
        tickets_dir=tmp_path / "experiments" / "tickets",
        logs_dir=logs_dir,
    )

    assert audit["passed"] is expected_passed
    assert audit["canonical_record_violation_count"] == (
        0 if expected_passed else 1
    )


def test_create_ticket_assigns_incrementing_id_and_baseline(tmp_path):
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_tickets_dir": str(tmp_path / "tickets"),
    }

    first = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Find repeated bad trade family.",
        change_type="analysis_only",
        single_causal_variable="bad trade taxonomy",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=["docs/"],
        evaluation_windows=[{"start": "2025-10-23", "end": "2026-04-21"}],
        exclusive_scope_ok=True,
    )
    second = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Make replay coverage measurable.",
        change_type="measurement_instrumentation",
        single_causal_variable="replay coverage bucket",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=["scripts/"],
        exclusive_scope_ok=True,
    )

    assert first["experiment_id"].endswith("-001")
    assert second["experiment_id"].endswith("-002")
    assert first["experiment_uid"].startswith("expuid-")
    assert first["experiment_uid"] != second["experiment_uid"]
    assert first["hub_identity"]["scheme"] == "hf_hub_local_v1"
    assert first["hub_identity"]["repo_id"] == (
        f"ginger/experiments/{first['experiment_id']}"
    )
    assert first["card_file"].endswith(f"cards/{first['experiment_id']}.md")
    assert first["revision_manifest_file"].endswith(
        f"manifests/{first['experiment_id']}.json"
    )
    assert first["status"] == "proposed"
    assert first["baseline_result_file"] == "data/backtests/backtest_results_20260425.json"
    card_path = tmp_path / "cards" / f"{first['experiment_id']}.md"
    manifest_path = tmp_path / "manifests" / f"{first['experiment_id']}.json"
    assert card_path.exists()
    assert manifest_path.exists()
    assert f"# Experiment Card: {first['experiment_id']}" in card_path.read_text(
        encoding="utf-8"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_type"] == "ginger_experiment_revision_manifest"
    assert manifest["experiment_id"] == first["experiment_id"]
    assert manifest["files"]["ticket"]["sha256"]
    assert manifest["files"]["card"]["sha256"]

    path = tmp_path / "registry.json"
    save_registry(registry, path)
    loaded = load_registry(path)
    assert len(loaded["experiments"]) == 2
    assert loaded["experiments"][0]["ticket_file"].endswith(
        f"tickets/{first['experiment_id']}.json"
    )


def test_create_ticket_auto_generates_per_experiment_write_scope(tmp_path):
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_tickets_dir": str(tmp_path / "tickets"),
    }

    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Find one reproducible failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="hold quality taxonomy",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
    )

    scopes = ticket["allowed_write_scope"]
    stem = f"{ticket['experiment_id'].replace('-', '_')}_hold_quality_taxonomy"
    assert f"quant/experiments/{stem}.py" in scopes
    assert f"data/experiments/{ticket['experiment_id']}/{stem}.json" in scopes
    assert f"experiments/tickets/{ticket['experiment_id']}.json" in scopes
    assert f"experiments/logs/{ticket['experiment_id']}.json" in scopes
    assert "data/" not in scopes


def test_next_experiment_id_scans_all_identity_sources(tmp_path):
    root = tmp_path
    (root / "docs").mkdir()
    (root / "data" / "experiments" / "exp-20990101-009").mkdir(parents=True)
    (root / "experiments" / "tickets").mkdir(parents=True)
    (root / "docs" / "experiments" / "tickets").mkdir(parents=True)
    (root / "experiments" / "logs").mkdir(parents=True)
    (root / "quant" / "experiments").mkdir(parents=True)

    (root / "docs" / "experiment_log.jsonl").write_text(
        json.dumps({"experiment_id": "exp-20990101-007"}) + "\n",
        encoding="utf-8",
    )
    (root / "experiments" / "tickets" / "exp-20990101-010.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-010"}),
        encoding="utf-8",
    )
    (root / "docs" / "experiments" / "tickets" / "exp-20990101-011.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-011"}),
        encoding="utf-8",
    )
    (root / "experiments" / "logs" / "exp-20990101-012.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-012"}),
        encoding="utf-8",
    )
    (root / "experiments" / "cards").mkdir(parents=True)
    (root / "experiments" / "cards" / "exp-20990101-014.md").write_text(
        "---\nexperiment_id: exp-20990101-014\n---\n",
        encoding="utf-8",
    )
    (root / "experiments" / "manifests").mkdir(parents=True)
    (root / "experiments" / "manifests" / "exp-20990101-015.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-015"}),
        encoding="utf-8",
    )
    (root / "quant" / "experiments" / "exp_20990101_013_runner.py").write_text(
        "EXPERIMENT_ID = 'exp-20990101-013'\n",
        encoding="utf-8",
    )
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "_repo_root": str(root),
        "experiments": [{"experiment_id": "exp-20990101-003"}],
    }

    sources = collect_experiment_id_sources(registry, root=root)

    assert "exp-20990101-007" in sources
    assert "exp-20990101-009" in sources
    assert "exp-20990101-011" in sources
    assert "exp-20990101-013" in sources
    assert "exp-20990101-014" in sources
    assert "exp-20990101-015" in sources
    assert next_experiment_id(registry, today="20990101", root=root) == "exp-20990101-016"


def test_create_ticket_rejects_explicit_id_already_seen_on_filesystem(tmp_path):
    root = tmp_path
    (root / "data" / "experiments" / "exp-20990101-004").mkdir(parents=True)
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_repo_root": str(root),
        "_tickets_dir": str(root / "experiments" / "tickets"),
    }

    try:
        create_ticket(
            registry,
            experiment_id="exp-20990101-004",
            lane="measurement_repair",
            hypothesis="Reserve an explicit ID only if the namespace is free.",
            change_type="identity_reservation",
            single_causal_variable="explicit reservation collision",
        )
    except ValueError as exc:
        assert "experiment_id already exists: exp-20990101-004" in str(exc)
        assert "data_experiment:path" in str(exc)
    else:
        raise AssertionError("filesystem-owned experiment_id was accepted")

    assert not (root / "experiments" / "tickets" / "exp-20990101-004.json").exists()


def test_create_ticket_reserves_explicit_unused_id_and_normalizes_format(tmp_path):
    root = tmp_path
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_repo_root": str(root),
        "_tickets_dir": str(root / "experiments" / "tickets"),
    }

    ticket = create_ticket(
        registry,
        experiment_id="exp_20990101_004",
        lane="measurement_repair",
        hypothesis="Reserve an explicit unused ID.",
        change_type="identity_reservation",
        single_causal_variable="explicit reservation",
    )

    assert ticket["experiment_id"] == "exp-20990101-004"
    assert ticket["hub_identity"]["repo_id"] == "ginger/experiments/exp-20990101-004"
    assert (root / "experiments" / "tickets" / "exp-20990101-004.json").exists()
    assert (root / "experiments" / "cards" / "exp-20990101-004.md").exists()
    assert (root / "experiments" / "manifests" / "exp-20990101-004.json").exists()


def test_require_available_experiment_id_reports_invalid_format():
    try:
        require_available_experiment_id("not-a-hub-id", {"experiments": []})
    except ValueError as exc:
        assert "exp-YYYYMMDD-NNN" in str(exc)
    else:
        raise AssertionError("invalid experiment_id was accepted")


def test_create_ticket_file_slug_overrides_auto_generated_file_stem():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Find one reproducible failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="bad trade hold-quality taxonomy",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        file_slug="hold_quality_audit",
    )

    stem = f"{ticket['experiment_id'].replace('-', '_')}_hold_quality_audit"
    assert f"quant/experiments/{stem}.py" in ticket["allowed_write_scope"]
    assert (
        f"data/experiments/{ticket['experiment_id']}/{stem}.json"
        in ticket["allowed_write_scope"]
    )


def test_create_ticket_records_trial_accounting_fields():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Mature one broad-market paper source.",
        change_type="default_off_paper_forward_maturation",
        single_causal_variable="broad-market replacement value ledger",
        mechanism_family="broad_market_leadership",
        trial_family="broad_market_forward_maturation",
        trial_variant_id="replacement_value_v1",
        changed_variable="broad_market_forward_ledger_fields",
        prior_trial_count=4,
        nearby_prior_experiments=["exp-20990101-001"],
        multiple_testing_risk_bucket="moderate",
        new_evidence_type="new_forward_rows",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction=alpha_prediction(),
    )

    assert ticket["mechanism_family"] == "broad_market_leadership"
    assert ticket["trial_family"] == "broad_market_forward_maturation"
    assert ticket["trial_variant_id"] == "replacement_value_v1"
    assert ticket["changed_variable"] == "broad_market_forward_ledger_fields"
    assert ticket["prior_trial_count"] == 4
    assert ticket["nearby_prior_experiments"] == ["exp-20990101-001"]
    assert ticket["multiple_testing_risk_bucket"] == "moderate"
    assert ticket["new_evidence_type"] == "new_forward_rows"


def test_create_ticket_records_pre_run_prediction():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test one calibrated alpha hypothesis.",
        change_type="default_off_paper_allocation",
        single_causal_variable="calibrated alpha prediction",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction=normalize_prediction(
            success_probability=0.35,
            expected_ev_delta=0.12,
            expected_pnl_delta=2500.0,
            main_failure_modes=["sample_too_thin", "concentration_failed"],
            confidence_reason=(
                "Prior paper evidence is positive, related families were mixed, and "
                "forward rows may be too thin or concentrated."
            ),
        ),
    )

    prediction = ticket["prediction"]
    assert prediction["success_probability"] == 0.35
    assert prediction["expected_ev_delta"] == 0.12
    assert prediction["expected_pnl_delta"] == 2500.0
    assert prediction["main_failure_modes"] == [
        "sample_too_thin",
        "concentration_failed",
    ]
    assert prediction["recorded_at"]


def test_alpha_search_ticket_requires_prediction():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    try:
        create_ticket(
            registry,
            lane="alpha_search",
            hypothesis="Test one alpha hypothesis.",
            change_type="ranking_rule",
            single_causal_variable="new ranking field",
        )
    except ValueError as exc:
        assert "requires a pre-run prediction" in str(exc)
        assert "missing_prediction" in str(exc)
    else:
        raise AssertionError("alpha_search ticket without prediction was accepted")

    ticket = create_ticket(
        registry,
        lane="alpha_search",
        hypothesis="Test one alpha hypothesis.",
        change_type="ranking_rule",
        single_causal_variable="new ranking field",
        prediction=alpha_prediction(),
    )

    assert ticket["lane"] == "alpha_search"
    assert ticket["prediction"]["success_probability"] == 0.4


def test_alpha_ticket_prediction_requires_failure_modes():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    try:
        create_ticket(
            registry,
            lane="alpha_discovery",
            hypothesis="Test one alpha hypothesis.",
            change_type="risk_scalar_or_topup",
            single_causal_variable="new risk scalar",
            prediction={"success_probability": 0.5},
        )
    except ValueError as exc:
        assert "missing_main_failure_modes" in str(exc)
    else:
        raise AssertionError("alpha ticket without failure modes was accepted")


def test_alpha_ticket_prediction_requires_substantive_confidence_reason():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    for reason, expected in [
        ("TODO", "missing_substantive_confidence_reason"),
        ("Prior evidence is mixed.", "confidence_reason_too_short"),
    ]:
        try:
            create_ticket(
                registry,
                lane="alpha_search",
                hypothesis="Test one alpha hypothesis.",
                change_type="ranking_rule",
                single_causal_variable=f"new ranking field {expected}",
                prediction={
                    "success_probability": 0.35,
                    "main_failure_modes": ["thin_sample"],
                    "confidence_reason": reason,
                },
            )
        except ValueError as exc:
            assert "requires a substantive pre-run prediction" in str(exc)
            assert expected in str(exc)
        else:
            raise AssertionError("weak confidence reason was accepted")


def test_default_file_stem_falls_back_when_slug_has_no_ascii():
    assert default_file_stem("exp-20990101-001", "坏交易") == (
        "exp_20990101_001_experiment"
    )


def test_create_ticket_rejects_broad_directory_scope_without_exclusive_flag():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    try:
        create_ticket(
            registry,
            lane="loss_attribution",
            hypothesis="Find one reproducible failure family.",
            change_type="failure_taxonomy",
            single_causal_variable="hold quality taxonomy",
            baseline_result_file="data/backtests/backtest_results_20260425.json",
            allowed_write_scope=["quant/experiments/legacy/exp_loss_attribution_runner.py", "data/"],
        )
    except ValueError as exc:
        assert "broad allowed_write_scope" in str(exc)
        assert "data/" in str(exc)
    else:
        raise AssertionError("broad data/ scope was accepted")


def test_create_ticket_expands_scope_templates():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}

    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test one shadow source.",
        change_type="new_strategy_shadow",
        single_causal_variable="shadow source",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction=alpha_prediction(),
        allowed_write_scope=[
            "quant/experiments/{experiment_id}_{lane}.py",
            "data/experiments/{experiment_id}/{change_type}.json",
        ],
    )

    assert ticket["allowed_write_scope"] == [
        f"quant/experiments/{ticket['experiment_id']}_alpha_discovery.py",
        f"data/experiments/{ticket['experiment_id']}/new_strategy_shadow.json",
    ]


def test_claim_detects_scope_and_variable_conflicts():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    first = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test one breakout ranking key.",
        change_type="ranking_rule",
        single_causal_variable="breakout ranking key",
        allowed_write_scope=["quant/signal_engine.py"],
        prediction=alpha_prediction(),
    )
    second = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="Test conflicting breakout ranking key.",
        change_type="ranking_rule",
        single_causal_variable="breakout ranking key",
        allowed_write_scope=["quant/"],
        exclusive_scope_ok=True,
        prediction=alpha_prediction(),
    )

    claimed, conflicts = claim_ticket(registry, first["experiment_id"], "agent-a")
    assert claimed["status"] == "claimed"
    assert conflicts == []

    _, conflicts = claim_ticket(registry, second["experiment_id"], "agent-b")
    assert conflicts
    assert conflicts[0]["experiment_id"] == first["experiment_id"]
    assert conflicts[0]["locked_variable_conflicts"] == ["breakout ranking key"]


def test_claim_ignores_shared_coordination_file_scopes():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    first = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Record one failure taxonomy.",
        change_type="failure_taxonomy",
        single_causal_variable="taxonomy A",
        allowed_write_scope=[
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
    )
    second = create_ticket(
        registry,
        lane="universe_scout",
        hypothesis="Record one universe scout artifact.",
        change_type="universe_expansion",
        single_causal_variable="universe B",
        allowed_write_scope=[
            "D:/Github/ginger/docs/experiment_log.jsonl",
            "D:/Github/ginger/docs/experiment_registry.json",
        ],
        prediction=alpha_prediction(),
    )

    _, conflicts = claim_ticket(registry, first["experiment_id"], "agent-loss")
    assert conflicts == []

    claimed, conflicts = claim_ticket(registry, second["experiment_id"], "agent-universe")
    assert conflicts == []
    assert claimed["status"] == "claimed"


def test_claim_still_blocks_same_locked_variable_with_shared_scopes():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    first = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Study one shared failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="shared failure family",
        allowed_write_scope=["docs/experiment_log.jsonl"],
    )
    second = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Study same shared failure family.",
        change_type="failure_taxonomy",
        single_causal_variable="shared failure family",
        allowed_write_scope=["docs/experiment_registry.json"],
    )

    _, conflicts = claim_ticket(registry, first["experiment_id"], "agent-a")
    assert conflicts == []

    _, conflicts = claim_ticket(registry, second["experiment_id"], "agent-b")
    assert conflicts
    assert conflicts[0]["scope_conflicts"] == []
    assert conflicts[0]["locked_variable_conflicts"] == ["shared failure family"]


def test_evaluate_gate_accepts_expected_value_improvement():
    before = {
        "expected_value_score": 1.0,
        "sharpe": 2.0,
        "max_drawdown_pct": 0.05,
        "win_rate": 0.5,
        "trade_count": 20,
        "total_pnl": 1000.0,
    }
    after = {
        "expected_value_score": 1.11,
        "sharpe": 2.0,
        "max_drawdown_pct": 0.05,
        "win_rate": 0.5,
        "trade_count": 20,
        "total_pnl": 1000.0,
    }

    judgement = evaluate_gate(before, after)

    assert judgement["decision"] == "accepted"
    assert "expected_value_score improved" in judgement["acceptance_reasons"][0]


def test_judge_results_extracts_metrics_and_rejects_no_delta(tmp_path):
    before = {
        "total_trades": 10,
        "win_rate": 0.5,
        "total_pnl": 1000.0,
        "sharpe": 1.0,
        "sharpe_daily": 1.5,
        "max_drawdown_pct": 0.04,
        "survival_rate": 0.9,
        "benchmarks": {"strategy_total_return_pct": 0.1},
    }
    after = dict(before)
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_path.write_text(json.dumps(before), encoding="utf-8")
    after_path.write_text(json.dumps(after), encoding="utf-8")

    judgement = judge_results(before_path, after_path)

    assert judgement["before_metrics"]["expected_value_score"] == 0.15
    assert judgement["delta_metrics"]["trade_count"] == 0
    assert judgement["decision"] == "rejected"


def test_log_draft_can_be_marked_observed_only_and_appended(tmp_path):
    registry = {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
        "_tickets_dir": str(tmp_path / "tickets"),
    }
    ticket = create_ticket(
        registry,
        lane="measurement_repair",
        hypothesis="Record a measurement artifact without strategy acceptance.",
        change_type="measurement_instrumentation",
        single_causal_variable="log append path",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        allowed_write_scope=["scripts/"],
        exclusive_scope_ok=True,
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 1.0},
        "delta_metrics": {"expected_value_score": 0.0},
    }

    draft = build_log_draft(
        ticket,
        judgement,
        "data/before.json",
        "data/after.json",
        status_override="observed_only",
        change_summary="Append-log path observed without strategy claim.",
        notes="No strategy decision intended.",
    )
    log_path = tmp_path / "experiment_log.jsonl"
    shard = append_log_entry(log_path, draft)

    assert draft["status"] == "observed_only"
    assert draft["decision"] == "observed_only"
    assert draft["trial_family"] == "measurement_instrumentation"
    assert draft["changed_variable"] == "log append path"
    assert draft["rejection_reason"] is None
    # append_log_entry now persists to the per-experiment shard; the retired
    # monolithic log is no longer written.
    assert not log_path.exists()
    assert shard == tmp_path / "experiments" / "logs" / f"{ticket['experiment_id']}.json"
    assert (
        json.loads(shard.read_text(encoding="utf-8"))["experiment_id"]
        == ticket["experiment_id"]
    )


def test_research_replay_log_and_update_result_enforce_observed_only_ceiling(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    fake.anchor_overrides = _research_replay_anchor_overrides()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    monkeypatch.setattr(experiment_registry_module, "REPO_ROOT", tmp_path)
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    ticket = create_ticket(
        registry,
        promotion_request="data/alpha_search/promotion.json",
        **_research_ticket_kwargs(),
    )
    judgement = {
        "decision": "accepted_paper_pending_forward",
        "acceptance_reasons": ["diagnostic Gate 4 passed"],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 2.0},
        "delta_metrics": {"expected_value_score": 1.0},
    }

    with pytest.raises(ValueError, match="result_ceiling=observed_only"):
        build_log_draft(ticket, judgement, "before.json", "after.json")
    with pytest.raises(ValueError, match="result_ceiling=observed_only"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "before.json",
            "after.json",
        )

    artifact_path, artifact, _ = _write_private_replay_result(
        tmp_path,
        ticket["experiment_id"],
        status="observed_only",
        disposition="positive_replay_lead_not_promoted",
        evidence_invalid=False,
    )
    ticket["allowed_write_scope"].append(artifact)
    ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(ticket)
    draft = build_log_draft(
        ticket,
        judgement,
        "before.json",
        artifact_path,
        status_override="observed_only",
    )
    updated = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "before.json",
        artifact_path,
        status_override="observed_only",
        log_draft=draft,
    )
    assert draft["decision"] == "observed_only"
    assert draft["paper_live_eligible"] is False
    assert updated["status"] == "observed_only"
    assert updated["result"]["admission_class"] == "research_replay"
    assert updated["result"]["paper_live_eligible"] is False


@pytest.mark.parametrize(
    ("status", "disposition", "evidence_invalid"),
    [
        ("observed_only", "positive_replay_lead_not_promoted", False),
        ("rejected", "rejected", False),
        ("rejected", "inconclusive_insufficient_sample", False),
        ("rejected", "invalid_contaminated", True),
    ],
)
def test_future_private_replay_standard_closeout_binds_after_artifact(
    tmp_path, monkeypatch, status, disposition, evidence_invalid
):
    fake = _FakeAlphaPromotionApi()
    fake.anchor_overrides = _research_replay_anchor_overrides()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    monkeypatch.setattr(experiment_registry_module, "REPO_ROOT", tmp_path)
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    ticket = create_ticket(
        registry,
        promotion_request="data/alpha_search/promotion.json",
        **_research_ticket_kwargs(),
    )
    ticket[PRIVATE_REPLAY_DISPOSITION_CONTRACT] = 1
    artifact_path, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        ticket["experiment_id"],
        status=status,
        disposition=disposition,
        evidence_invalid=evidence_invalid,
    )
    ticket["allowed_write_scope"].append(artifact)
    ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(ticket)
    judgement = {
        "decision": status,
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 1.0},
        "delta_metrics": {"expected_value_score": 0.0},
    }

    draft = build_log_draft(
        ticket,
        judgement,
        tmp_path / "before.json",
        artifact_path,
        status_override=status,
    )
    closed = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        tmp_path / "before.json",
        artifact_path,
        status_override=status,
        log_draft=draft,
    )

    assert draft["artifact"] == artifact
    assert draft["artifact_sha256"] == artifact_sha256
    assert draft["artifact_disposition"] == disposition
    assert draft["evidence_invalid"] is evidence_invalid
    assert closed["result"]["artifact"] == artifact
    assert closed["result"]["artifact_sha256"] == artifact_sha256
    assert closed["result"]["artifact_disposition"] == disposition
    assert closed["result"]["evidence_invalid"] is evidence_invalid


@pytest.mark.parametrize(
    ("overrides", "disposition", "evidence_invalid", "error_pattern"),
    [
        ({"experiment_id": "exp-20990101-999"}, "rejected", False, "experiment_id|identity"),
        ({"record_type": "wrong_type"}, "rejected", False, "record_type|identity"),
        ({"status": "observed_only"}, "rejected", False, "status|identity"),
        ({"decision": "observed_only"}, "rejected", False, "decision|identity"),
        ({}, "unknown", False, "disposition"),
        ({}, "invalid_contaminated", False, "evidence_invalid"),
    ],
)
def test_future_private_replay_standard_closeout_rejects_invalid_after_artifact(
    tmp_path,
    monkeypatch,
    overrides,
    disposition,
    evidence_invalid,
    error_pattern,
):
    fake = _FakeAlphaPromotionApi()
    fake.anchor_overrides = _research_replay_anchor_overrides()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    monkeypatch.setattr(experiment_registry_module, "REPO_ROOT", tmp_path)
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    ticket = create_ticket(
        registry,
        promotion_request="data/alpha_search/promotion.json",
        **_research_ticket_kwargs(),
    )
    ticket[PRIVATE_REPLAY_DISPOSITION_CONTRACT] = 1
    artifact_path, artifact, _ = _write_private_replay_result(
        tmp_path,
        ticket["experiment_id"],
        status="rejected",
        disposition=disposition,
        evidence_invalid=evidence_invalid,
        overrides=overrides,
    )
    ticket["allowed_write_scope"].append(artifact)
    ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(ticket)
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 1.0},
        "delta_metrics": {"expected_value_score": 0.0},
    }

    with pytest.raises(ValueError, match=error_pattern):
        build_log_draft(
            ticket,
            judgement,
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
        )
    with pytest.raises(ValueError, match=error_pattern):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
        )
    assert ticket["status"] == "proposed"
    assert ticket.get("result") is None


def test_future_private_replay_exact_file_scope_rejects_descendant_artifact(tmp_path):
    experiment_id = "exp-20990101-034"
    exact_scope = (
        Path("data") / "experiments" / experiment_id / "private_replay_result.json"
    )
    artifact_path = tmp_path / exact_scope / "child.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "record_type": "v2_private_replay_scout_result",
                "status": "rejected",
                "decision": "rejected",
                "disposition": "rejected",
                "evidence_invalid": False,
            }
        ),
        encoding="utf-8",
    )
    ticket = _auditable_private_replay_ticket(experiment_id, status="rejected")
    ticket["allowed_write_scope"] = [exact_scope.as_posix()]
    ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(ticket)

    with pytest.raises(ValueError, match="allowed_write_scope"):
        build_log_draft(
            ticket,
            {"decision": "rejected"},
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
            repo_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("must_not_touch", "data/experiments/protected.json"),
        ("allowed_write_scope", [None]),
    ],
)
def test_future_private_replay_scope_shape_fails_closed(
    tmp_path, field_name, invalid_value
):
    experiment_id = "exp-20990101-035"
    artifact_path, _, _ = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(experiment_id, status="rejected")
    ticket[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        build_log_draft(
            ticket,
            {"decision": "rejected"},
            tmp_path / "before.json",
            artifact_path,
            status_override="rejected",
            repo_root=tmp_path,
        )


def _settled_forward_anchor_overrides():
    return {
        "admission_class": "settled_forward_attribution",
        "selected_evidence_grade": "observed_only",
        "result_ceiling": "observed_only",
        "paper_live_eligible": False,
        "source_readiness_bindings": [
            {
                "surface_id": "settled-forward-fixture",
                "pit_status": "settled_forward_sufficient",
                "source_contract_hash": "5" * 64,
                "readiness_hash": "6" * 64,
            }
        ],
    }


def test_settled_forward_attribution_enforces_observed_only_ceiling(
    tmp_path, monkeypatch
):
    fake = _FakeAlphaPromotionApi()
    fake.anchor_overrides = _settled_forward_anchor_overrides()
    monkeypatch.setattr(experiment_registry_module, "_alpha_promotion_api", lambda: fake)
    registry = {
        "schema_version": 1,
        "experiments": [],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    kwargs = _alpha_ticket_kwargs()
    kwargs["change_type"] = "observed_only_attribution"
    ticket = create_ticket(
        registry,
        promotion_request="data/alpha_search/promotion.json",
        **kwargs,
    )
    judgement = {
        "decision": "accepted_paper_pending_forward",
        "acceptance_reasons": ["diagnostic Gate 4 passed"],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 2.0},
        "delta_metrics": {"expected_value_score": 1.0},
    }

    with pytest.raises(ValueError, match="result_ceiling=observed_only"):
        build_log_draft(ticket, judgement, "before.json", "after.json")
    with pytest.raises(ValueError, match="result_ceiling=observed_only"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "before.json",
            "after.json",
        )

    updated = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "before.json",
        "after.json",
        status_override="observed_only",
    )
    assert updated["status"] == "observed_only"
    assert updated["result"]["admission_class"] == "settled_forward_attribution"
    assert updated["result"]["selected_evidence_grade"] == "observed_only"
    assert updated["result"]["paper_live_eligible"] is False


def test_log_draft_includes_prediction_calibration():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="A confident alpha hypothesis fails.",
        change_type="default_off_paper_allocation",
        single_causal_variable="calibration failure",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction={
            "success_probability": 0.8,
            "expected_ev_delta": 0.2,
            "expected_pnl_delta": 4000.0,
            "main_failure_modes": ["sample_too_thin"],
            "confidence_reason": (
                "Frozen-window paper evidence looks strong, but related support "
                "sleeves often failed when sample size was thin."
            ),
        },
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0, "total_pnl": 1000.0},
        "after_metrics": {"expected_value_score": 0.9, "total_pnl": 700.0},
        "delta_metrics": {"expected_value_score": -0.1, "total_pnl": -300.0},
    }

    draft = build_log_draft(
        ticket,
        judgement,
        "data/before.json",
        "data/after.json",
        realized_failure_mode="sample_too_thin",
    )

    assert draft["prediction"]["success_probability"] == 0.8
    assert draft["calibration"]["actual_success"] == 0
    assert draft["calibration"]["calibration_direction"] == "overconfident"
    assert draft["calibration"]["brier_score"] == 0.64
    assert draft["calibration"]["ev_prediction_error"] == -0.3
    assert draft["calibration"]["predicted_failure_mode_hit"] is True


def test_log_draft_rejects_legacy_alpha_without_prediction():
    ticket = {
        "experiment_id": "exp-20990101-020",
        "lane": "alpha_search",
        "hypothesis": "Legacy hand-written alpha ticket.",
        "change_type": "ranking_rule",
        "single_causal_variable": "legacy missing prediction",
    }
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 0.9},
        "delta_metrics": {"expected_value_score": -0.1},
    }

    try:
        build_log_draft(ticket, judgement, "before.json", "after.json")
    except ValueError as exc:
        assert "requires a pre-run prediction" in str(exc)
    else:
        raise AssertionError("legacy alpha closeout without prediction was accepted")

    draft = build_log_draft(
        ticket,
        judgement,
        "before.json",
        "after.json",
        allow_missing_prediction=True,
    )
    assert draft["experiment_id"] == "exp-20990101-020"
    assert "prediction" not in draft


def test_audit_experiment_process_reports_legacy_without_failing(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20260528-008.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260528-008",
                "lane": "alpha_search",
                "status": "accepted_legacy_stub",
                "updated_at": "2026-05-28T05:36:40+00:00",
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20260528-008.json").write_text(
        json.dumps({"experiment_id": "exp-20260528-008", "decision": "accepted"}),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    assert audit["passed"] is True
    assert audit["closed_legacy_pre_enforcement_missing_prediction_count"] == 1
    assert audit["closed_post_enforcement_missing_prediction_count"] == 0
    assert audit["closed_legacy_pre_enforcement_missing_calibration_count"] == 1
    assert audit["closed_post_enforcement_missing_calibration_count"] == 0


def test_audit_experiment_process_fails_post_enforcement_gaps(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20990101-030.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-030",
                "lane": "alpha_search",
                "status": "accepted_post_enforcement_stub",
                "created_at": "2099-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20990101-030.json").write_text(
        json.dumps({"experiment_id": "exp-20990101-030", "decision": "accepted"}),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
    )

    assert audit["passed"] is False
    assert audit["post_enforcement_missing_prediction_count"] == 1
    assert audit["closed_post_enforcement_missing_prediction_count"] == 1
    assert audit["closed_post_enforcement_missing_calibration_count"] == 1
    assert audit["post_enforcement_missing_prediction_examples"][0][
        "experiment_id"
    ] == "exp-20990101-030"


def test_lean_audit_flags_weak_reasoning_and_missing_reflection(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20990101-040.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-040",
                "lane": "alpha_search",
                "status": "accepted",
                "created_at": "2099-01-01T00:00:00+00:00",
                "prediction": {
                    "success_probability": 0.4,
                    "main_failure_modes": ["thin_sample"],
                    "confidence_reason": "Maybe works.",
                },
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20990101-040.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20990101-040",
                "decision": "accepted",
                "calibration": {"actual_success": 1},
                "post_run_reflection": {
                    "why_result_happened": "TODO",
                    "forbidden_near_neighbor_retry": "TODO",
                    "new_evidence_required": "TODO",
                },
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        lean=True,
    )

    assert audit["passed"] is False
    assert audit["lean_quality_passed"] is False
    assert audit["post_enforcement_weak_prediction_quality_count"] == 1
    assert audit["closed_post_enforcement_weak_reflection_count"] == 1


def test_lean_audit_reports_legacy_debt_without_blocking(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20260607-002.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260607-002",
                "lane": "alpha_search",
                "status": "rejected",
                "created_at": "2026-06-07T01:18:00+00:00",
                "prediction": {
                    "success_probability": 0.4,
                    "main_failure_modes": ["thin_sample"],
                    "confidence_reason": "Maybe works.",
                },
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20260607-002.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260607-002",
                "decision": "rejected",
                "calibration": {"actual_success": 0},
                "post_run_reflection": {
                    "why_result_happened": "TODO",
                    "forbidden_near_neighbor_retry": "TODO",
                    "new_evidence_required": "TODO",
                },
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        lean=True,
    )

    assert audit["passed"] is True
    assert audit["lean_quality_passed"] is True
    assert audit["weak_prediction_quality_count"] == 1
    assert audit["post_enforcement_weak_prediction_quality_count"] == 0
    assert audit["closed_weak_reflection_count"] == 1
    assert audit["closed_post_enforcement_weak_reflection_count"] == 0


def test_lean_audit_passes_substantive_reasoning_and_reflection(tmp_path):
    tickets_dir = tmp_path / "experiments" / "tickets"
    logs_dir = tmp_path / "experiments" / "logs"
    tickets_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (tickets_dir / "exp-20260825-041.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260825-041",
                "lane": "alpha_search",
                "status": "accepted",
                "created_at": "2026-08-25T00:00:00+00:00",
                "prediction": {
                    "success_probability": 0.34,
                    "main_failure_modes": ["drawdown_drift", "window_regression"],
                    "confidence_reason": (
                        "Peer-shock rows previously improved all windows, but "
                        "this variant may fail if it duplicates selected consensus flow."
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    (logs_dir / "exp-20260825-041.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-20260825-041",
                "decision": "accepted",
                "calibration": {"actual_success": 1},
                "post_run_reflection": {
                    "why_result_happened": (
                        "The policy worked because peer-shock rows added "
                        "independent relation evidence instead of duplicating "
                        "the accepted consensus source family."
                    ),
                    "forbidden_near_neighbor_retry": (
                        "Do not retune correlation thresholds on the same windows."
                    ),
                    "new_evidence_required": (
                        "Retry only with closed forward replacement-value rows "
                        "or a new PIT peer-classification source."
                    ),
                },
            }
        ),
        encoding="utf-8",
    )

    audit = audit_experiment_process(
        {"schema_version": 1, "updated_at": None, "experiments": []},
        tickets_dir=tickets_dir,
        logs_dir=logs_dir,
        lean=True,
    )

    assert audit["passed"] is True
    assert audit["lean_quality_passed"] is True
    assert audit["post_enforcement_weak_prediction_quality_count"] == 0
    assert audit["closed_post_enforcement_weak_reflection_count"] == 0


def test_per_experiment_log_entry_is_written_to_own_file(tmp_path):
    row = {"experiment_id": "exp-20990101-003", "decision": "observed_only"}
    logs_dir = tmp_path / "logs"

    path = save_experiment_log_entry(row, logs_dir=logs_dir)

    assert path == logs_dir / "exp-20990101-003.json"
    assert experiment_log_exists("exp-20990101-003", logs_dir=logs_dir)
    assert json.loads(path.read_text(encoding="utf-8"))["decision"] == "observed_only"


def test_per_experiment_log_entry_rejects_expected_identity_mismatch(tmp_path):
    row = {"experiment_id": "exp-20990101-002", "decision": "observed_only"}
    logs_dir = tmp_path / "logs"

    with pytest.raises(ValueError, match="experiment log identity mismatch"):
        save_experiment_log_entry(
            row,
            expected_experiment_id="exp-20990101-017",
            logs_dir=logs_dir,
        )

    assert not logs_dir.exists()


def test_mortgage_wrapper_rebinds_inherited_compact_log_identity(monkeypatch):
    runner = (
        ROOT
        / "quant"
        / "experiments"
        / "exp_20260711_017_mortgage_rate_relief_residential_leadership.py"
    )
    spec = importlib.util.spec_from_file_location("mortgage_log_identity_test", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = module.prior.scaffold.prior.base
    monkeypatch.setattr(
        base,
        "compact_log",
        lambda payload: {
            "experiment_id": "exp-20260711-002",
            "artifact": "data/experiments/exp-20260711-002/stale.json",
            "log": "experiments/logs/exp-20260711-002.json",
            "hypothesis": "stale MOVE identity",
        },
    )

    row = module.build_log_record({})

    assert row["experiment_id"] == "exp-20260711-017"
    assert row["hypothesis"] == module.HYPOTHESIS
    assert row["changed_variable"] == module.CHANGED_VARIABLE
    assert row["artifact"].startswith("data/experiments/exp-20260711-017/")
    assert row["log"] == "experiments/logs/exp-20260711-017.json"


def test_append_log_entry_is_idempotent_on_repeat(tmp_path):
    # The retired monolithic appender now writes the per-experiment shard and is
    # idempotent: a repeat (e.g. the runner already wrote its own shard) is a
    # no-op rather than a duplicate error.
    row = {"experiment_id": "exp-20990101-001", "decision": "observed_only"}
    log_path = tmp_path / "experiment_log.jsonl"
    first = append_log_entry(log_path, row)
    second = append_log_entry(log_path, row)

    assert first == second
    assert first.exists()
    assert not log_path.exists()


def test_append_log_entry_reraises_validator_value_error_without_created_shard(
    tmp_path, monkeypatch
):
    row = {"experiment_id": "exp-20990101-004", "decision": "rejected"}
    log_path = tmp_path / "experiment_log.jsonl"

    def reject_row(*args, **kwargs):
        raise ValueError("private replay validator rejected the log row")

    monkeypatch.setattr(
        experiment_registry_module, "save_experiment_log_entry", reject_row
    )

    with pytest.raises(ValueError, match="validator rejected"):
        append_log_entry(log_path, row)

    assert not (
        tmp_path / "experiments" / "logs" / "exp-20990101-004.json"
    ).exists()


@pytest.mark.parametrize(
    "experiment_id",
    [
        "../tickets/exp-20990101-060",
        "EXP-20990101-060",
        "exp_20990101_060",
        "exp-20990101-060_suffix",
    ],
)
@pytest.mark.parametrize("writer", ["save", "append"])
def test_log_writers_reject_noncanonical_identity_without_file_side_effects(
    tmp_path, experiment_id, writer
):
    row = {"experiment_id": experiment_id, "decision": "rejected"}
    logs_dir = tmp_path / "experiments" / "logs"

    with pytest.raises(ValueError, match="exact canonical"):
        if writer == "save":
            save_experiment_log_entry(row, logs_dir=logs_dir)
        else:
            append_log_entry(tmp_path / "docs" / "experiment_log.jsonl", row)

    assert not logs_dir.exists()
    assert not (tmp_path / "experiments" / "tickets").exists()


def test_append_log_entry_treats_file_exists_race_as_idempotent_only_after_shard_exists(
    tmp_path, monkeypatch
):
    row = {"experiment_id": "exp-20990101-005", "decision": "rejected"}
    log_path = tmp_path / "experiment_log.jsonl"
    expected_shard = (
        tmp_path / "experiments" / "logs" / "exp-20990101-005.json"
    )

    def race_writer(value, *, logs_dir, **kwargs):
        shard = Path(logs_dir) / "exp-20990101-005.json"
        shard.parent.mkdir(parents=True, exist_ok=True)
        shard.write_text(json.dumps(value), encoding="utf-8")
        raise FileExistsError("raced with another shard writer")

    monkeypatch.setattr(
        experiment_registry_module, "save_experiment_log_entry", race_writer
    )

    shard = append_log_entry(log_path, row)

    assert shard == expected_shard
    assert json.loads(shard.read_text(encoding="utf-8")) == row


def test_append_log_entry_reraises_file_exists_when_race_created_no_shard(
    tmp_path, monkeypatch
):
    row = {"experiment_id": "exp-20990101-007", "decision": "rejected"}
    log_path = tmp_path / "experiment_log.jsonl"

    def missing_race_winner(*args, **kwargs):
        raise FileExistsError("reported race without a durable shard")

    monkeypatch.setattr(
        experiment_registry_module,
        "save_experiment_log_entry",
        missing_race_winner,
    )

    with pytest.raises(FileExistsError, match="without a durable shard"):
        append_log_entry(log_path, row)


def test_append_log_entry_validates_existing_shard_before_idempotent_return(tmp_path):
    row = {"experiment_id": "exp-20990101-006", "decision": "rejected"}
    log_path = tmp_path / "experiment_log.jsonl"
    shard = tmp_path / "experiments" / "logs" / "exp-20990101-006.json"
    shard.parent.mkdir(parents=True)
    shard.write_text(
        json.dumps({"experiment_id": "exp-20990101-006", "decision": "observed_only"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="existing|mismatch|different|conflict"):
        append_log_entry(log_path, row)


def test_private_contract_log_duplicate_is_exact_idempotent_only(tmp_path):
    experiment_id = "exp-20990101-052"
    _, artifact, artifact_sha256 = _write_private_replay_result(
        tmp_path,
        experiment_id,
        status="rejected",
        disposition="rejected",
        evidence_invalid=False,
    )
    ticket = _auditable_private_replay_ticket(
        experiment_id,
        status="rejected",
        artifact=artifact,
        artifact_sha256=artifact_sha256,
    )
    ticket["result"].update(
        {"artifact_disposition": "rejected", "evidence_invalid": False}
    )
    row = _private_replay_log_row(ticket)
    ticket["result"][PRIVATE_REPLAY_LOG_SHA256] = (
        experiment_registry_module._private_replay_scout_log_sha256(row)
    )
    _bind_future_log_intent(ticket, row)
    tickets_dir = tmp_path / "experiments" / "tickets"
    ticket["ticket_file"] = f"experiments/tickets/{experiment_id}.json"
    ticket["revision_manifest_file"] = (
        f"experiments/manifests/{experiment_id}.json"
    )
    _persist_file_backed_ticket_bundle(tmp_path, ticket)
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir(parents=True)
    experiment_registry_module.save_registry(
        {
            "schema_version": 1,
            "experiments": [
                experiment_registry_module._ticket_index_entry(ticket, tickets_dir)
            ],
        },
        registry_path,
    )
    logs_dir = tmp_path / "experiments" / "logs"
    path = save_experiment_log_entry(
        row, logs_dir=logs_dir, registry_path=registry_path
    )
    original = path.read_bytes()

    assert save_experiment_log_entry(
        row,
        allow_duplicate=True,
        logs_dir=logs_dir,
        registry_path=registry_path,
    ) == path
    assert path.read_bytes() == original

    conflicting = {**row, "notes": "conflicting rewrite"}
    with pytest.raises(ValueError, match="payload commitment|immutable.*conflicts"):
        save_experiment_log_entry(
            conflicting,
            allow_duplicate=True,
            logs_dir=logs_dir,
            registry_path=registry_path,
        )
    assert path.read_bytes() == original


def test_append_log_entry_writes_shards_not_monolithic_log(tmp_path):
    log_path = tmp_path / "experiment_log.jsonl"
    first = append_log_entry(
        log_path, {"experiment_id": "exp-20990101-002", "decision": "observed_only"}
    )
    second = append_log_entry(
        log_path,
        {"experiment_id": "exp-20990101-003", "decision": "observed_only"},
    )

    logs_dir = tmp_path / "experiments" / "logs"
    assert first == logs_dir / "exp-20990101-002.json"
    assert second == logs_dir / "exp-20990101-003.json"
    assert first.exists() and second.exists()
    # The retired monolithic log is never written.
    assert not log_path.exists()


def _custom_judge_workspace(
    tmp_path: Path, experiment_id: str, *, ticket_overrides: dict | None = None
):
    workspace = tmp_path / "custom-workspace"
    registry_path = workspace / "docs" / "experiment_registry.json"
    tickets_dir = workspace / "experiments" / "tickets"
    registry_path.parent.mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    ticket = {
        "experiment_id": experiment_id,
        "lane": "measurement_repair",
        "change_type": "identity_or_measurement_repair",
        "status": "claimed",
        "owner": "codex",
        "hypothesis": "A custom registry close must remain in its own workspace.",
        "single_causal_variable": "custom registry close root",
        "allowed_write_scope": [f"experiments/logs/{experiment_id}.json"],
        "must_not_touch": [],
        "locked_variables": ["custom registry close root"],
        "evaluation_windows": [],
        "prediction": None,
        "created_at": "2099-01-01T00:00:00+00:00",
        "claimed_at": "2099-01-01T00:01:00+00:00",
        "completed_at": None,
        "result": None,
        EXPERIMENT_EVER_CLAIMED: True,
    }
    ticket.update(ticket_overrides or {})
    if (
        ticket.get("change_type") == "private_replay_scout"
        and ticket.get(PRIVATE_REPLAY_DISPOSITION_CONTRACT) == 1
        and ticket.get("status") != "proposed"
    ):
        ticket[PRIVATE_REPLAY_CLAIM_BINDING] = _private_replay_claim_binding(ticket)
    ticket["ticket_file"] = f"experiments/tickets/{experiment_id}.json"
    ticket["revision_manifest_file"] = (
        f"experiments/manifests/{experiment_id}.json"
    )
    ticket_path = _persist_file_backed_ticket_bundle(workspace, ticket)
    entry = experiment_registry_module._ticket_index_entry(ticket, tickets_dir)
    experiment_registry_module.save_registry(
        {"schema_version": 1, "experiments": [entry]}, registry_path
    )
    before = workspace / "before.json"
    after = workspace / "after.json"
    before.write_text(json.dumps({"expected_value_score": 1.0}), encoding="utf-8")
    after.write_text(json.dumps({"expected_value_score": 1.0}), encoding="utf-8")
    return workspace, registry_path, ticket_path, before, after


def _load_judge_experiment_module():
    script = ROOT / "scripts" / "judge_experiment.py"
    spec = importlib.util.spec_from_file_location("judge_experiment_contract_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_experiment_entrypoint_module():
    script = ROOT / "scripts" / "experiment.py"
    spec = importlib.util.spec_from_file_location("experiment_entrypoint_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lean_strict_cli_surfaces_and_blocks_hard_closeout_integrity(
    tmp_path, monkeypatch, capsys
):
    module = _load_experiment_entrypoint_module()
    experiment_id = "exp-20990101-045"
    monkeypatch.setattr(module, "load_registry", lambda path: {"experiments": []})
    monkeypatch.setattr(module, "_self_register_new_offenders", lambda: [])
    monkeypatch.setattr(
        module,
        "_audit_alpha_playbook",
        lambda: {"passed": True, "violations": []},
    )
    monkeypatch.setattr(
        module,
        "audit_experiment_process",
        lambda *args, **kwargs: {
            "lean_quality_passed": True,
            "research_result_ceiling_violation_count": 1,
            "research_result_ceiling_violation_examples": [
                {
                    "experiment_id": experiment_id,
                    "violations": ["missing canonical experiment log shard"],
                }
            ],
            "post_enforcement_research_result_ceiling_violation_count": 1,
            "post_enforcement_research_result_ceiling_violation_examples": [
                {
                    "experiment_id": experiment_id,
                    "violations": ["missing canonical experiment log shard"],
                }
            ],
            "legacy_research_result_ceiling_violation_count": 0,
            "canonical_record_violation_count": 0,
            "canonical_record_violation_examples": [],
            "legacy_canonical_record_violation_count": 0,
            "legacy_orphan_log_count": 0,
            "missing_alpha_promotion_count": 0,
            "missing_alpha_promotion_examples": [],
            "invalid_alpha_promotion_count": 0,
            "invalid_alpha_promotion_examples": [],
            "post_hard_integrity_alpha_promotion_violation_count": 0,
            "post_hard_integrity_alpha_promotion_violation_examples": [],
            "legacy_hard_integrity_alpha_promotion_violation_count": 0,
            "post_enforcement_weak_prediction_quality_examples": [],
            "closed_post_enforcement_weak_reflection_examples": [],
            "post_enforcement_missing_prediction_examples": [],
            "closed_post_enforcement_missing_calibration_examples": [],
        },
    )

    with pytest.raises(SystemExit, match="2"):
        module._audit(
            [
                "--registry",
                str(tmp_path / "docs" / "experiment_registry.json"),
                "--lean-strict",
            ]
        )

    summary = json.loads(capsys.readouterr().out)
    assert summary["lean_strict_passed"] is False
    assert summary["hard_integrity_passed"] is False
    assert summary["lean_strict_failure_domains"] == [
        "research_closeout_integrity"
    ]
    assert summary["hard_integrity_violations"]["research_closeout_integrity"] == {
        "count": 1,
        "example_ids": [experiment_id],
    }


def test_lean_strict_cli_blocks_alpha_promotion_integrity(
    tmp_path, monkeypatch, capsys
):
    module = _load_experiment_entrypoint_module()
    experiment_id = "exp-20990101-046"
    monkeypatch.setattr(module, "load_registry", lambda path: {"experiments": []})
    monkeypatch.setattr(module, "_self_register_new_offenders", lambda: [])
    monkeypatch.setattr(
        module,
        "_audit_alpha_playbook",
        lambda: {"passed": True, "violations": []},
    )
    monkeypatch.setattr(
        module,
        "audit_experiment_process",
        lambda *args, **kwargs: {
            "lean_quality_passed": True,
            "missing_alpha_promotion_count": 1,
            "missing_alpha_promotion_examples": [
                {"experiment_id": experiment_id, "status": "claimed"}
            ],
            "invalid_alpha_promotion_count": 0,
            "invalid_alpha_promotion_examples": [],
            "post_hard_integrity_alpha_promotion_violation_count": 1,
            "post_hard_integrity_alpha_promotion_violation_examples": [
                {"experiment_id": experiment_id, "status": "claimed"}
            ],
            "legacy_hard_integrity_alpha_promotion_violation_count": 0,
            "post_enforcement_research_result_ceiling_violation_count": 0,
            "post_enforcement_research_result_ceiling_violation_examples": [],
            "legacy_research_result_ceiling_violation_count": 0,
            "canonical_record_violation_count": 0,
            "canonical_record_violation_examples": [],
            "legacy_canonical_record_violation_count": 0,
            "legacy_orphan_log_count": 0,
            "post_enforcement_weak_prediction_quality_examples": [],
            "closed_post_enforcement_weak_reflection_examples": [],
            "post_enforcement_missing_prediction_examples": [],
            "closed_post_enforcement_missing_calibration_examples": [],
        },
    )

    with pytest.raises(SystemExit, match="2"):
        module._audit(
            [
                "--registry",
                str(tmp_path / "docs" / "experiment_registry.json"),
                "--lean-strict",
            ]
        )

    summary = json.loads(capsys.readouterr().out)
    assert summary["lean_strict_passed"] is False
    assert summary["hard_integrity_passed"] is False
    assert summary["lean_strict_failure_domains"] == [
        "alpha_promotion_integrity"
    ]
    assert summary["hard_integrity_violations"]["alpha_promotion_integrity"] == {
        "count": 1,
        "example_ids": [experiment_id],
    }


def test_judge_experiment_custom_registry_validates_draft_before_terminal_update(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-031"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path, experiment_id
    )
    module = _load_judge_experiment_module()
    monkeypatch.setattr(
        module,
        "build_log_draft",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("draft validation failed")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--write-registry",
            "--status-override",
            "rejected",
            "--log-draft",
            "--append-log",
        ],
    )

    with pytest.raises(ValueError, match="draft validation failed"):
        module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "claimed"
    assert persisted.get("result") is None
    assert not (workspace / "experiments" / "logs" / f"{experiment_id}.json").exists()


def test_judge_experiment_custom_registry_closes_with_log_in_custom_workspace(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-032"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path, experiment_id
    )
    module = _load_judge_experiment_module()
    real_save = experiment_registry_module.save_experiment_log_entry
    expected_logs_dir = workspace / "experiments" / "logs"

    def guarded_save(row, **kwargs):
        assert Path(kwargs["logs_dir"]).resolve() == expected_logs_dir.resolve()
        return real_save(row, **kwargs)

    monkeypatch.setattr(module, "save_experiment_log_entry", guarded_save)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--write-registry",
            "--status-override",
            "rejected",
            "--log-draft",
            "--append-log",
        ],
    )

    module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    log_path = expected_logs_dir / f"{experiment_id}.json"
    assert persisted["status"] == "rejected"
    assert persisted["result"]["decision"] == "rejected"
    assert log_path.exists()
    assert json.loads(log_path.read_text(encoding="utf-8"))["experiment_id"] == (
        experiment_id
    )


def test_judge_experiment_fresh_retry_repairs_terminal_cache_from_log_intent(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-055"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path, experiment_id
    )
    args = [
        "judge_experiment.py",
        "--registry",
        str(registry_path),
        "--experiment-id",
        experiment_id,
        "--before",
        str(before),
        "--after",
        str(after),
        "--write-registry",
        "--status-override",
        "rejected",
        "--log-draft",
        "--append-log",
    ]
    original_locked_update = experiment_registry_module.locked_registry_update
    monkeypatch.setattr(
        experiment_registry_module,
        "locked_registry_update",
        lambda *a, **k: (_ for _ in ()).throw(
            OSError("simulated terminal cache failure")
        ),
    )
    first_module = _load_judge_experiment_module()
    monkeypatch.setattr(sys, "argv", args)

    with pytest.raises(OSError, match="terminal cache failure"):
        first_module.main()

    terminal = json.loads(ticket_path.read_text(encoding="utf-8"))
    committed_row = terminal[
        experiment_registry_module.EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD
    ]
    log_path = workspace / "experiments" / "logs" / f"{experiment_id}.json"
    assert json.loads(log_path.read_text(encoding="utf-8")) == committed_row
    assert load_registry(registry_path)["experiments"][0]["status"] == "claimed"

    monkeypatch.setattr(
        experiment_registry_module,
        "locked_registry_update",
        original_locked_update,
    )
    second_module = _load_judge_experiment_module()
    monkeypatch.setattr(sys, "argv", args)
    second_module.main()

    assert load_registry(registry_path)["experiments"][0]["status"] == "rejected"


def test_judge_experiment_future_generic_write_requires_canonical_log_append(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-054"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path, experiment_id
    )
    module = _load_judge_experiment_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--write-registry",
            "--status-override",
            "rejected",
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "claimed"
    assert persisted.get("result") is None
    assert not (workspace / "experiments" / "logs" / f"{experiment_id}.json").exists()


@pytest.mark.parametrize("extra_args", [[], ["--log-draft"]])
def test_judge_experiment_future_private_write_requires_canonical_log_append(
    tmp_path, monkeypatch, extra_args
):
    experiment_id = "exp-20990101-033"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path,
        experiment_id,
        ticket_overrides={
            "lane": "alpha_search",
            "change_type": "private_replay_scout",
            PRIVATE_REPLAY_DISPOSITION_CONTRACT: 1,
            "alpha_promotion": _research_replay_anchor_overrides(),
        },
    )
    module = _load_judge_experiment_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--write-registry",
            "--status-override",
            "rejected",
            *extra_args,
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "claimed"
    assert persisted.get("result") is None
    assert not (workspace / "experiments" / "logs" / f"{experiment_id}.json").exists()


def test_judge_experiment_future_private_rejects_duplicate_log_escape(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-053"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path,
        experiment_id,
        ticket_overrides={
            "lane": "alpha_search",
            "change_type": "private_replay_scout",
            PRIVATE_REPLAY_DISPOSITION_CONTRACT: 1,
            "alpha_promotion": _research_replay_anchor_overrides(),
        },
    )
    module = _load_judge_experiment_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--append-log",
            "--allow-duplicate-log-id",
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "claimed"
    assert not (workspace / "experiments" / "logs" / f"{experiment_id}.json").exists()


def test_judge_experiment_preflights_existing_log_before_terminal_update(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-040"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path, experiment_id
    )
    log_path = workspace / "experiments" / "logs" / f"{experiment_id}.json"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("{}", encoding="utf-8")
    module = _load_judge_experiment_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--write-registry",
            "--status-override",
            "rejected",
            "--append-log",
        ],
    )

    with pytest.raises(ValueError, match="log already exists"):
        module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "claimed"
    assert persisted.get("result") is None


def test_judge_experiment_flat_custom_registry_uses_its_parent_as_workspace(
    tmp_path, monkeypatch
):
    experiment_id = "exp-20990101-041"
    workspace, registry_path, ticket_path, before, after = _custom_judge_workspace(
        tmp_path,
        experiment_id,
        ticket_overrides={
            "lane": "alpha_search",
            "change_type": "private_replay_scout",
            "prediction": alpha_prediction(),
            PRIVATE_REPLAY_DISPOSITION_CONTRACT: 1,
            "alpha_promotion": _research_replay_anchor_overrides(),
            "allowed_write_scope": ["after.json"],
        },
    )
    after.write_text(
        json.dumps(
            {
                "experiment_id": experiment_id,
                "record_type": "v2_private_replay_scout_result",
                "status": "rejected",
                "decision": "rejected",
                "disposition": "rejected",
                "evidence_invalid": False,
            }
        ),
        encoding="utf-8",
    )
    flat_registry_path = workspace / "registry.json"
    registry_path.replace(flat_registry_path)
    module = _load_judge_experiment_module()
    monkeypatch.setattr(
        experiment_registry_module,
        "_revalidate_alpha_promotion_for_claim",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        experiment_registry_module,
        "_require_alpha_promotion_claim_receipt_for_close",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "judge_experiment.py",
            "--registry",
            str(flat_registry_path),
            "--experiment-id",
            experiment_id,
            "--before",
            str(before),
            "--after",
            str(after),
            "--write-registry",
            "--status-override",
            "rejected",
            "--append-log",
        ],
    )

    module.main()

    persisted = json.loads(ticket_path.read_text(encoding="utf-8"))
    expected_log = workspace / "experiments" / "logs" / f"{experiment_id}.json"
    assert persisted["status"] == "rejected"
    assert expected_log.exists()
    assert not (tmp_path / "experiments" / "logs" / f"{experiment_id}.json").exists()


def test_locked_registry_update_serializes_read_modify_write(tmp_path):
    registry_path = tmp_path / "experiment_registry.json"
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    def add_ticket(registry):
        return create_ticket(
            registry,
            lane="measurement_repair",
            hypothesis="Create ticket under lock.",
            change_type="logging_fix",
            single_causal_variable="locked registry update",
            baseline_result_file="data/backtests/backtest_results_20260425.json",
        )

    ticket = locked_registry_update(registry_path, add_ticket)
    loaded = load_registry(registry_path)

    assert ticket["experiment_id"].endswith("-001")
    assert len(loaded["experiments"]) == 1
    assert iter_experiments(loaded)[0]["single_causal_variable"] == "locked registry update"
    lock_path = tmp_path / "experiment_registry.json.lock"
    assert lock_path.exists()
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock_payload["target"].endswith("experiment_registry.json")
    assert "released_at" in lock_payload


def test_locked_registry_update_uses_workspace_ticket_directory_for_docs_registry(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    registry_path = docs_dir / "experiment_registry.json"
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    def add_ticket(registry):
        return create_ticket(
            registry,
            lane="measurement_repair",
            hypothesis="Create ticket in workspace experiments directory.",
            change_type="logging_fix",
            single_causal_variable="ticket directory split brain",
            baseline_result_file="data/backtests/backtest_results_20260425.json",
        )

    ticket = locked_registry_update(registry_path, add_ticket)

    assert (tmp_path / "experiments" / "tickets" / f"{ticket['experiment_id']}.json").exists()
    assert not (tmp_path / "docs" / "experiments" / "tickets" / f"{ticket['experiment_id']}.json").exists()


def test_concurrent_locked_registry_updates_do_not_duplicate_ids(tmp_path):
    registry_path = tmp_path / "experiment_registry.json"
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)
    tickets = []

    def worker(i):
        def add_ticket(registry):
            return create_ticket(
                registry,
                lane="measurement_repair",
                hypothesis=f"Create concurrent ticket {i}.",
                change_type="logging_fix",
                single_causal_variable=f"locked registry update {i}",
                baseline_result_file="data/backtests/backtest_results_20260425.json",
            )

        tickets.append(locked_registry_update(registry_path, add_ticket))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    loaded = load_registry(registry_path)
    ids = [exp["experiment_id"] for exp in loaded["experiments"]]

    assert len(tickets) == 6
    assert len(ids) == 6
    assert len(set(ids)) == 6
    assert ids == sorted(ids)


def _intent_lock_kwargs():
    return {
        "lane": "measurement_repair",
        "hypothesis": (
            "Protect identical automatic reservation retries with an intent lock."
        ),
        "change_type": "identity_or_measurement_repair",
        "single_causal_variable": "reservation intent lock",
        "allowed_write_scope": ["scripts/experiment_registry.py"],
    }


def test_reserve_experiment_returns_existing_open_ticket_for_identical_intent(tmp_path):
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir()
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    first = reserve_experiment(registry_path, **_intent_lock_kwargs())
    second = reserve_experiment(registry_path, **_intent_lock_kwargs())

    assert second["experiment_id"] == first["experiment_id"]
    assert second["experiment_uid"] == first["experiment_uid"]
    intent = second["reservation_intent"]
    assert intent["key"]
    intent_path = (
        tmp_path
        / "experiments"
        / "reservation_intents"
        / f"{intent['key']}.json"
    )
    assert json.loads(intent_path.read_text(encoding="utf-8"))["experiment_id"] == (
        first["experiment_id"]
    )


def test_reserve_experiment_recovers_open_ticket_when_intent_file_missing(tmp_path):
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir()
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    first = reserve_experiment(registry_path, **_intent_lock_kwargs())
    intent_path = (
        tmp_path
        / "experiments"
        / "reservation_intents"
        / f"{first['reservation_intent']['key']}.json"
    )
    intent_path.unlink()

    second = reserve_experiment(registry_path, **_intent_lock_kwargs())

    assert second["experiment_id"] == first["experiment_id"]
    assert intent_path.exists()


def test_reserve_experiment_allows_new_intent_after_prior_ticket_closes(tmp_path):
    registry_path = tmp_path / "docs" / "experiment_registry.json"
    registry_path.parent.mkdir()
    save_registry({"schema_version": 1, "updated_at": None, "experiments": []}, registry_path)

    first = reserve_experiment(registry_path, **_intent_lock_kwargs())
    ticket_path = tmp_path / "experiments" / "tickets" / f"{first['experiment_id']}.json"
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ticket["status"] = "rejected"
    ticket_path.write_text(json.dumps(ticket, indent=2) + "\n", encoding="utf-8")

    second = reserve_experiment(registry_path, **_intent_lock_kwargs())

    assert second["experiment_id"] != first["experiment_id"]
    assert second["experiment_id"].endswith("-002")


def test_update_result_honors_status_override():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="Close an analysis ticket as observed only.",
        change_type="analysis_only",
        single_causal_variable="loss taxonomy",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "delta_metrics": {},
    }

    updated = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "data/before.json",
        "data/after.json",
        status_override="observed_only",
    )

    assert updated["status"] == "observed_only"
    assert updated["result"]["decision"] == "observed_only"


def test_update_result_refuses_to_overwrite_terminal_result():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="loss_attribution",
        hypothesis="A terminal closeout must remain immutable.",
        change_type="analysis_only",
        single_causal_variable="terminal result immutability",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "delta_metrics": {},
    }
    first = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "data/before.json",
        "data/after.json",
    )

    with pytest.raises(ValueError, match="terminal results are immutable"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "data/different_before.json",
            "data/different_after.json",
        )

    assert first["result"]["before_result_file"] == "data/before.json"
    assert first["result"]["after_result_file"] == "data/after.json"


def test_alpha_status_override_cannot_promote_rejected_gate_to_accepted():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="A rejected Gate result cannot be promoted by a CLI override.",
        change_type="candidate_pool",
        single_causal_variable="accepted override boundary",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction={
            "success_probability": 0.2,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": ["no replacement value"],
            "confidence_reason": (
                "The candidate mechanism is measurable, but the prior remains weak and "
                "the test explicitly protects the machine Gate from manual promotion."
            ),
        },
    )
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 0.5},
        "delta_metrics": {"expected_value_score": -0.5},
    }

    with pytest.raises(ValueError, match="cannot promote"):
        build_log_draft(
            ticket,
            judgement,
            "data/before.json",
            "data/after.json",
            status_override="accepted",
        )
    with pytest.raises(ValueError, match="cannot promote"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "data/before.json",
            "data/after.json",
            status_override="accepted",
        )


def test_update_result_records_prediction_calibration():
    registry = {"schema_version": 1, "updated_at": None, "experiments": []}
    ticket = create_ticket(
        registry,
        lane="alpha_discovery",
        hypothesis="A low-confidence idea wins.",
        change_type="risk_scalar_or_topup",
        single_causal_variable="calibrated topup",
        baseline_result_file="data/backtests/backtest_results_20260425.json",
        prediction={
            "success_probability": 0.2,
            "expected_ev_delta": 0.01,
            "main_failure_modes": ["drawdown_failed"],
            "confidence_reason": (
                "Low-confidence top-up may help if drawdown stays contained, but "
                "nearby risk-scalar trials often failed tail-risk guards."
            ),
        },
    )
    judgement = {
        "decision": "accepted",
        "acceptance_reasons": ["expected_value_score improved 12.00%"],
        "delta_metrics": {"expected_value_score": 0.12},
    }

    updated = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "data/before.json",
        "data/after.json",
    )

    calibration = updated["result"]["calibration"]
    assert calibration["actual_success"] == 1
    assert calibration["calibration_direction"] == "underconfident"
    assert calibration["brier_score"] == 0.64


def test_looks_placeholder_word_boundary():
    from experiment_registry import _looks_placeholder

    # Real prose containing placeholder words as substrings must pass.
    assert _looks_placeholder(
        "backfilled pre-2023 index history raises episode count; nonetheless "
        "the sample stays thin"
    ) is False
    # Bare placeholders must still be caught.
    assert _looks_placeholder("TODO") is True
    assert _looks_placeholder("fill in later") is True
    assert _looks_placeholder("none") is True
    assert _looks_placeholder("") is True


def _deadlocked_reservation_registry(tmp_path, experiment_id):
    fixture = _research_claim_receipt_fixture(tmp_path)
    ticket = fixture["ticket"]
    ticket.update(
        {
            "experiment_id": experiment_id,
            "owner": None,
            "allowed_write_scope": [],
            "locked_variables": [],
        }
    )
    registry = {
        "schema_version": 1,
        "experiments": [ticket],
        "_repo_root": str(tmp_path),
        "_enforce_alpha_promotion": True,
    }
    judgement = {
        "decision": "rejected",
        "acceptance_reasons": [],
        "before_metrics": {"expected_value_score": 1.0},
        "after_metrics": {"expected_value_score": 1.0},
        "delta_metrics": {"expected_value_score": 0.0},
    }
    return registry, ticket, judgement


def test_never_claimed_duplicate_accounting_close_bypasses_claim_receipt(tmp_path):
    registry, ticket, judgement = _deadlocked_reservation_registry(
        tmp_path, "exp-20260729-905"
    )
    closed = update_result(
        registry,
        ticket["experiment_id"],
        judgement,
        "before.json",
        "after.json",
        status_override="rejected",
        realized_failure_mode="duplicate_reservation_accounting",
    )
    assert closed["status"] == "rejected"
    assert closed["result"]["decision"] == "rejected"


def test_never_claimed_duplicate_accounting_close_requires_rejected_status(tmp_path):
    registry, ticket, judgement = _deadlocked_reservation_registry(
        tmp_path, "exp-20260729-906"
    )
    judgement["decision"] = "observed_only"
    with pytest.raises(ValueError, match="cannot close without a successful claim"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "before.json",
            "after.json",
            status_override="observed_only",
            realized_failure_mode="duplicate_reservation_accounting",
        )
    assert ticket["status"] == "proposed"


def test_never_claimed_close_without_duplicate_mode_still_requires_receipt(tmp_path):
    registry, ticket, judgement = _deadlocked_reservation_registry(
        tmp_path, "exp-20260729-907"
    )
    with pytest.raises(ValueError, match="cannot close without a successful claim"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "before.json",
            "after.json",
            status_override="rejected",
            realized_failure_mode="unrelated_failure",
        )
    assert ticket["status"] == "proposed"


def test_claimed_ticket_duplicate_accounting_close_still_requires_receipt(tmp_path):
    registry, ticket, judgement = _deadlocked_reservation_registry(
        tmp_path, "exp-20260729-908"
    )
    ticket["status"] = "claimed"
    ticket["claimed_at"] = "2099-01-01T00:01:00+00:00"
    ticket["owner"] = "someone"
    with pytest.raises(ValueError, match="claim"):
        update_result(
            registry,
            ticket["experiment_id"],
            judgement,
            "before.json",
            "after.json",
            status_override="rejected",
            realized_failure_mode="duplicate_reservation_accounting",
        )
    assert ticket["status"] == "claimed"
