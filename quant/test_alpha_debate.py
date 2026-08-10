from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from quant.alpha_search_contract import HypothesisCandidate, canonical_hash
from quant.alpha_search_engine import (
    AlphaSearchError,
    build_selection_scope_manifest,
    freeze_selection_panel,
)
from quant.alpha_search_history import build_historical_prior_snapshot
from quant.alpha_search_registry import EvidenceSurfaceRegistry
from quant.test_alpha_search_cli import _candidate, _surfaces
from scripts import agent_mailbox
from scripts.alpha_debate import (
    CLAIM_SNAPSHOT_MAX_FILE_BYTES,
    DebateContractError,
    RESEARCH_REPLAY_CHANGE_TYPE,
    build_debate_lock,
    build_promotion_request,
    build_ticket_promotion_claim_receipt,
    candidate_pool_hash,
    claim_receipt_required_for_ticket,
    normalize_ticket_proposal,
    revalidate_ticket_promotion,
    validate_debate_lock,
    validate_promotion_request,
    validate_ticket_promotion_claim_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ALPHA_SEARCH_CLI = REPO_ROOT / "scripts" / "alpha_search.py"


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _receipt(
    *,
    channel: str,
    name: str,
    role: str,
    runtime: str,
    run_id: str,
    initiator_runtime: str,
    requested_model: str | None = None,
) -> dict:
    return agent_mailbox.make_launch_receipt(
        channel=channel,
        participant=name,
        role=role,
        runtime=runtime,
        run_id=run_id,
        executable=sys.executable,
        executable_version=f"python-{sys.version_info.major}.{sys.version_info.minor}",
        requested_model=(
            requested_model
            if requested_model is not None
            else f"fixture-{runtime}"
        ),
        cross_provider_acknowledged=(role != "initiator"),
        nonce=f"nonce-{role}-{run_id}",
        initiator_runtime=initiator_runtime if role != "initiator" else None,
    )


def _participant(
    *,
    channel: str,
    name: str,
    role: str,
    runtime: str,
    run_id: str,
    initiator_runtime: str,
    requested_model: str | None = None,
) -> dict:
    return {
        "name": name,
        "runtime": runtime,
        "provider": {"codex": "openai", "claude": "anthropic"}[runtime],
        "run_id": run_id,
        "launch_receipt": _receipt(
            channel=channel,
            name=name,
            role=role,
            runtime=runtime,
            run_id=run_id,
            initiator_runtime=initiator_runtime,
            requested_model=requested_model,
        ),
    }


def _debate_draft(final_pool_hash: str, *, initiator_runtime: str = "codex") -> dict:
    channel = "alpha-debate-fixture"
    opposite = "claude" if initiator_runtime == "codex" else "codex"
    return {
        "schema_version": 1,
        "record_type": "alpha_debate_lock",
        "channel": channel,
        "initiator": _participant(
            channel=channel,
            name="initiator-agent",
            role="initiator",
            runtime=initiator_runtime,
            run_id="run-init",
            initiator_runtime=initiator_runtime,
        ),
        "challenger": _participant(
            channel=channel,
            name="challenger-agent",
            role="challenger",
            runtime=opposite,
            run_id="run-challenge",
            initiator_runtime=initiator_runtime,
        ),
        "verifier": _participant(
            channel=channel,
            name="verifier-agent",
            role="verifier",
            runtime=opposite,
            run_id="run-verify",
            initiator_runtime=initiator_runtime,
        ),
        "outcome_accessed": False,
        "verdict": "proceed",
        "verification_status": "verified",
        "challenge_summary": "The challenger tested the market-prior and PIT assumptions.",
        "resolution_summary": "The final pool retains only the source-bound candidate.",
        "load_bearing_claims": [
            {
                "claim": "The selected candidate has canonical PIT source snapshots.",
                "source": "fixture panel and surface registry",
                "verification_status": "verified",
            }
        ],
        "unresolved_load_bearing_claims": [],
        "challenged_candidate_pool_hash": canonical_hash(["draft-pool"]),
        "final_candidate_pool_hash": final_pool_hash,
    }


def _codex_model_diverse_debate_draft(final_pool_hash: str) -> dict:
    draft = _debate_draft(final_pool_hash, initiator_runtime="codex")
    for role, model in (
        ("initiator", "gpt-5.6-sol"),
        ("challenger", "gpt-5.6-terra"),
        ("verifier", "gpt-5.6-sol"),
    ):
        draft[role] = _participant(
            channel=draft["channel"],
            name=f"{role}-agent",
            role=role,
            runtime="codex",
            run_id={
                "initiator": "run-init",
                "challenger": "run-challenge",
                "verifier": "run-verify",
            }[role],
            initiator_runtime="codex",
            requested_model=model,
        )
    return draft


def _populate_mailbox(
    tmp_path: Path,
    draft: dict,
    *,
    roles: tuple[str, ...] = ("initiator", "challenger", "verifier"),
) -> Path:
    mailbox_root = tmp_path / "data" / "agent_mailbox"
    attachments = mailbox_root / draft["channel"] / "attachments"
    attachments.mkdir(parents=True, exist_ok=True)
    challenge_path = attachments / "challenge.md"
    verification_path = attachments / "verification.md"
    challenge_path.write_text(draft["challenge_summary"], encoding="utf-8")
    verification_path.write_text(draft["resolution_summary"], encoding="utf-8")
    messages = {
        "initiator": ("Frozen candidate pool submitted for challenge.", None),
        "challenger": ("Challenge complete; see bound attachment.", challenge_path),
        "verifier": ("Verification complete; see bound attachment.", verification_path),
    }
    for role in roles:
        text, attachment = messages[role]
        participant = draft[role]
        agent_mailbox.send_message(
            draft["channel"],
            f"display-{role}",
            text,
            role=role,
            runtime=participant["runtime"],
            provider=participant["provider"],
            run_id=participant["run_id"],
            identity_receipt=participant["launch_receipt"],
            attachment=attachment,
            root=mailbox_root,
        )
    return mailbox_root


def _build_lock(tmp_path: Path, draft: dict) -> dict:
    mailbox_root = _populate_mailbox(tmp_path, draft)
    return build_debate_lock(
        draft, repo_root=tmp_path, mailbox_root=mailbox_root
    )


def _history_snapshot(tmp_path: Path) -> dict:
    (tmp_path / "experiments" / "logs").mkdir(parents=True)
    frozen = tmp_path / "frozen.jsonl"
    frozen.write_text(
        json.dumps(
            {
                "family_key": "unrelated_fixture_family",
                "fingerprint": {
                    "data_source": "unrelated_source",
                    "field_tags": ["unrelated"],
                    "gate_shape": "other",
                },
                "representative_exps": ["exp-20260719-001"],
                "status": "single_attempt",
                "reopen_condition": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-07-20T20:29:00Z",
        repo_root=tmp_path,
        isolated_fixture=True,
    )


def _gate_candidate(registry: EvidenceSurfaceRegistry) -> dict:
    candidate = _candidate()
    candidate["candidate_id"] = "pending"
    candidate["evidence_grade"] = "gate_candidate"
    candidate["research_refs"] = [
        "res-20260721-structured-event-representation-for-text-alpha"
    ]
    surface_rows = {
        row["surface_id"]: row for row in registry.to_dict()["surfaces"]
    }
    candidate["source_readiness_snapshot"] = [
        {
            "surface_id": surface_id,
            "snapshot_hash": canonical_hash(surface_rows[surface_id]),
        }
        for surface_id in sorted(candidate["surface_ids"])
    ]
    return HypothesisCandidate.with_computed_id(candidate).to_dict()


def _panel_fixture(tmp_path: Path) -> dict[str, object]:
    surfaces_value = _surfaces()
    registry = EvidenceSurfaceRegistry.from_dict(surfaces_value)
    prior = _history_snapshot(tmp_path)
    candidate = _gate_candidate(registry)
    scope = build_selection_scope_manifest(
        scope_name="promotion-fixture",
        preregistered_at="2026-07-20T20:30:00Z",
        data_cutoff="2026-07-20T21:00:00Z",
        freeze_at="2026-07-20T21:30:00Z",
        generator_version="promotion-fixture-v1",
        candidate_generation_config={"outcome_fields_allowed": False},
        allowed_surface_ids=list(registry.surface_ids),
        surface_registry_hash=registry.canonical_hash,
        prior_fingerprints=prior,
        queue_budgets={"exploration": 1, "adjacent": 0, "exploitation": 0},
        expected_candidate_count=1,
        selection_limit=1,
    )
    panel = freeze_selection_panel(
        [candidate],
        registry,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=prior,
    )
    assert panel["selected_candidate_ids"] == [candidate["candidate_id"]]

    paths = {
        "panel": tmp_path / "panel.json",
        "scope": tmp_path / "scope.json",
        "surfaces": tmp_path / "surfaces.json",
        "prior": tmp_path / "prior.json",
    }
    _write(paths["panel"], panel)
    _write(paths["scope"], scope)
    _write(paths["surfaces"], surfaces_value)
    _write(paths["prior"], prior)
    return {
        "panel": panel,
        "candidate": candidate,
        "scope": scope,
        "surfaces": surfaces_value,
        "prior": prior,
        "paths": paths,
    }


def _research_replay_fixture(
    tmp_path: Path, *, research_artifact: Path | None = None
) -> dict[str, object]:
    surfaces_value = copy.deepcopy(_surfaces())
    if research_artifact is None:
        artifact_dir = tmp_path / "data" / "research_replay"
        artifact_dir.mkdir(parents=True)
        research_artifact = artifact_dir / "market-prior.json"
        research_artifact.write_text(
            json.dumps(
                {"timestamp": "2026-07-20T20:00:00Z", "probability": 0.4}
            ),
            encoding="utf-8",
        )
    relative_artifact = research_artifact.relative_to(tmp_path).as_posix()
    research_digest = hashlib.sha256(research_artifact.read_bytes()).hexdigest()
    market_prior = next(
        row
        for row in surfaces_value["surfaces"]
        if row["surface_id"] == "market-prior"
    )
    market_prior.update(
        {
            "artifacts": [relative_artifact],
            "artifact_snapshot_hashes": {relative_artifact: research_digest},
            "pit_status": "research_pit",
            "evidence_grade": "lead",
            "gate_ready": False,
            "research_pit_basis": (
                "row timestamp is the simulated decision clock; historical "
                "vendor vintages remain unverified"
            ),
            "known_future_leakage": False,
        }
    )
    registry = EvidenceSurfaceRegistry.from_dict(surfaces_value)
    prior = _history_snapshot(tmp_path)
    candidate = _gate_candidate(registry)
    candidate["candidate_id"] = "pending"
    candidate["evidence_grade"] = "lead"
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()
    scope = build_selection_scope_manifest(
        scope_name="research-replay-promotion-fixture",
        preregistered_at="2026-07-20T20:30:00Z",
        data_cutoff="2026-07-20T21:00:00Z",
        freeze_at="2026-07-20T21:30:00Z",
        generator_version="research-replay-promotion-fixture-v1",
        candidate_generation_config={"outcome_fields_allowed": False},
        allowed_surface_ids=list(registry.surface_ids),
        surface_registry_hash=registry.canonical_hash,
        prior_fingerprints=prior,
        queue_budgets={"exploration": 1, "adjacent": 0, "exploitation": 0},
        expected_candidate_count=1,
        selection_limit=1,
    )
    panel = freeze_selection_panel(
        [candidate],
        registry,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=prior,
    )
    assert panel["selected_candidate_ids"] == [candidate["candidate_id"]]
    paths = {
        "panel": tmp_path / "research-panel.json",
        "scope": tmp_path / "research-scope.json",
        "surfaces": tmp_path / "research-surfaces.json",
        "prior": tmp_path / "research-prior.json",
        "artifact": research_artifact,
    }
    _write(paths["panel"], panel)
    _write(paths["scope"], scope)
    _write(paths["surfaces"], surfaces_value)
    _write(paths["prior"], prior)
    return {
        "panel": panel,
        "candidate": candidate,
        "scope": scope,
        "surfaces": surfaces_value,
        "prior": prior,
        "paths": paths,
    }


def _proposal() -> dict:
    return normalize_ticket_proposal(
        {
            "lane": "alpha_search",
            "hypothesis": "A direct prior versus official fact gap may reprice.",
            "change_type": "candidate_pool",
            "single_causal_variable": "official_probability_repricing",
            "causal_components": ["official fact", "observable market prior"],
            "mechanism_family": "official_probability_repricing",
            "trial_family": "official_probability_repricing_v1",
            "changed_variable": "candidate admission",
            "prediction": {
                "success_probability": 0.25,
                "main_failure_modes": ["already priced"],
                "confidence_reason": "Predeclared direct prior.",
            },
        }
    )


def _research_proposal() -> dict:
    proposal = _proposal()
    proposal["change_type"] = RESEARCH_REPLAY_CHANGE_TYPE
    return normalize_ticket_proposal(proposal)


@pytest.mark.parametrize("initiator_runtime", ["codex", "claude"])
def test_debate_lock_accepts_both_cross_runtime_directions(
    tmp_path: Path, initiator_runtime: str,
) -> None:
    lock = _build_lock(
        tmp_path,
        _debate_draft(canonical_hash(["final-pool"]), initiator_runtime=initiator_runtime)
    )
    assert validate_debate_lock(lock, repo_root=tmp_path) == lock
    assert lock["challenger"]["runtime"] != lock["initiator"]["runtime"]
    assert lock["verifier"]["runtime"] == lock["challenger"]["runtime"]


def test_debate_lock_accepts_model_diverse_codex_runs(tmp_path: Path) -> None:
    draft = _codex_model_diverse_debate_draft(canonical_hash(["final-pool"]))
    lock = _build_lock(tmp_path, draft)
    assert validate_debate_lock(lock, repo_root=tmp_path) == lock
    assert lock["mailbox_binding"]["verification_level"] == (
        "launcher_attested_codex_model_diverse"
    )
    assert {
        lock[role]["launch_receipt"]["requested_model"]
        for role in ("initiator", "challenger", "verifier")
    } == {"gpt-5.6-sol", "gpt-5.6-terra"}


def test_debate_lock_rejects_single_model_codex_runs(tmp_path: Path) -> None:
    draft = _codex_model_diverse_debate_draft(canonical_hash(["final-pool"]))
    for role in ("initiator", "challenger", "verifier"):
        participant = draft[role]
        draft[role] = _participant(
            channel=draft["channel"],
            name=participant["name"],
            role=role,
            runtime="codex",
            run_id=participant["run_id"],
            initiator_runtime="codex",
            requested_model="gpt-5.6-sol",
        )
    with pytest.raises(DebateContractError, match="codex_model_diversity_required"):
        build_debate_lock(draft, repo_root=tmp_path)


def test_debate_lock_rejects_same_runtime_missing_receipt_tamper_and_unresolved(
    tmp_path: Path,
) -> None:
    pool_hash = canonical_hash(["final-pool"])
    valid = _debate_draft(pool_hash)

    same_runtime = copy.deepcopy(valid)
    same_runtime["challenger"] = _participant(
        channel=same_runtime["channel"],
        name="challenger-agent",
        role="challenger",
        runtime="codex",
        run_id="run-challenge",
        initiator_runtime="codex",
    )
    with pytest.raises(DebateContractError, match="unsupported_review_topology"):
        build_debate_lock(same_runtime)

    missing_receipt = copy.deepcopy(valid)
    del missing_receipt["challenger"]["launch_receipt"]
    with pytest.raises(DebateContractError, match="missing_field"):
        build_debate_lock(missing_receipt)

    locked = _build_lock(tmp_path, valid)
    locked["resolution_summary"] = "tampered after verifier lock"
    with pytest.raises(DebateContractError, match="debate_hash_mismatch"):
        validate_debate_lock(locked, repo_root=tmp_path)

    unresolved = copy.deepcopy(valid)
    unresolved["unresolved_load_bearing_claims"] = ["PIT timestamp not checked"]
    with pytest.raises(DebateContractError, match="unresolved_load_bearing_claim"):
        build_debate_lock(unresolved)


def test_debate_lock_requires_receipt_bound_challenger_and_verifier_messages(
    tmp_path: Path,
) -> None:
    draft = _debate_draft(canonical_hash(["final-pool"]))
    mailbox_root = _populate_mailbox(
        tmp_path, draft, roles=("initiator", "challenger")
    )
    with pytest.raises(DebateContractError, match="receipt_bound_message_missing"):
        build_debate_lock(
            draft, repo_root=tmp_path, mailbox_root=mailbox_root
        )


def test_debate_lock_rejects_transcript_and_attachment_tamper(tmp_path: Path) -> None:
    transcript_root = tmp_path / "transcript"
    draft = _debate_draft(canonical_hash(["final-pool"]))
    mailbox_root = _populate_mailbox(transcript_root, draft)
    lock = build_debate_lock(
        draft, repo_root=transcript_root, mailbox_root=mailbox_root
    )
    participant = draft["initiator"]
    agent_mailbox.send_message(
        draft["channel"],
        "late-message",
        "Appended after lock.",
        role="initiator",
        runtime=participant["runtime"],
        provider=participant["provider"],
        run_id=participant["run_id"],
        identity_receipt=participant["launch_receipt"],
        root=mailbox_root,
    )
    with pytest.raises(DebateContractError, match="mailbox_binding_mismatch"):
        validate_debate_lock(
            lock, repo_root=transcript_root, mailbox_root=mailbox_root
        )

    attachment_root = tmp_path / "attachment"
    draft = _debate_draft(canonical_hash(["final-pool"]))
    mailbox_root = _populate_mailbox(attachment_root, draft)
    lock = build_debate_lock(
        draft, repo_root=attachment_root, mailbox_root=mailbox_root
    )
    verification = (
        mailbox_root
        / draft["channel"]
        / "attachments"
        / "verification.md"
    )
    verification.write_text("tampered after lock", encoding="utf-8")
    with pytest.raises(DebateContractError, match="mailbox_not_cross_model_verified"):
        validate_debate_lock(
            lock, repo_root=attachment_root, mailbox_root=mailbox_root
        )


@pytest.mark.parametrize("initiator_runtime", ["codex", "claude"])
def test_promotion_revalidates_panel_debate_and_all_file_hashes(
    tmp_path: Path, initiator_runtime: str
) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(
        debate_path,
        _build_lock(
            tmp_path,
            _debate_draft(
                candidate_pool_hash(panel), initiator_runtime=initiator_runtime
            )
        ),
    )
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "promotion.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path, expected_proposal=_proposal(), repo_root=tmp_path
    )
    assert anchor["candidate_id"] == fixture["candidate"]["candidate_id"]
    assert anchor["initiator_runtime"] == initiator_runtime
    assert anchor["research_refs"] == fixture["candidate"]["research_refs"]

    # The durable debate/promotion proof remains auditable after the local,
    # gitignored mailbox channel is removed or on another checkout.
    mailbox_root = tmp_path / "data" / "agent_mailbox"
    archived_mailbox = tmp_path / "mailbox-removed"
    mailbox_root.rename(archived_mailbox)
    assert validate_promotion_request(
        request_path, expected_proposal=_proposal(), repo_root=tmp_path
    ) == anchor

    panel_tamper = json.loads(paths["panel"].read_text(encoding="utf-8"))
    panel_tamper["selection_reason"] = "tampered"
    _write(paths["panel"], panel_tamper)
    with pytest.raises(DebateContractError, match="artifact_sha256_mismatch"):
        validate_promotion_request(request_path, repo_root=tmp_path)


def test_promotion_accepts_model_diverse_codex_debate(tmp_path: Path) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate-codex-model-diverse.json"
    _write(
        debate_path,
        _build_lock(
            tmp_path,
            _codex_model_diverse_debate_draft(candidate_pool_hash(panel)),
        ),
    )
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "promotion-codex-model-diverse.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path, expected_proposal=_proposal(), repo_root=tmp_path
    )
    assert anchor["candidate_id"] == fixture["candidate"]["candidate_id"]
    assert anchor["initiator_runtime"] == "codex"


def test_research_pit_lead_gets_hash_bound_research_replay_admission(
    tmp_path: Path,
) -> None:
    fixture = _research_replay_fixture(tmp_path)
    paths = fixture["paths"]
    debate_path = tmp_path / "research-debate.json"
    _write(
        debate_path,
        _build_lock(
            tmp_path,
            _debate_draft(candidate_pool_hash(fixture["panel"])),
        ),
    )
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_research_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "research-promotion.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path,
        expected_proposal=_research_proposal(),
        repo_root=tmp_path,
    )

    for value in (request, anchor):
        assert value["admission_class"] == "research_replay"
        assert value["selected_evidence_grade"] == "lead"
        assert value["result_ceiling"] == "observed_only"
        assert value["paper_live_eligible"] is False
        assert {row["pit_status"] for row in value["source_readiness_bindings"]} == {
            "canonical_pit",
            "research_pit",
        }


def test_research_replay_requires_exact_private_replay_change_type(
    tmp_path: Path,
) -> None:
    fixture = _research_replay_fixture(tmp_path)
    paths = fixture["paths"]
    debate_path = tmp_path / "research-debate.json"
    _write(
        debate_path,
        _build_lock(
            tmp_path,
            _debate_draft(candidate_pool_hash(fixture["panel"])),
        ),
    )

    with pytest.raises(DebateContractError) as error:
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )
    assert error.value.code == "research_replay_change_type_required"


def test_research_replay_revalidates_local_artifact_bytes(tmp_path: Path) -> None:
    fixture = _research_replay_fixture(tmp_path)
    paths = fixture["paths"]
    debate_path = tmp_path / "research-debate.json"
    _write(
        debate_path,
        _build_lock(
            tmp_path,
            _debate_draft(candidate_pool_hash(fixture["panel"])),
        ),
    )
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_research_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "research-promotion.json"
    _write(request_path, request)
    paths["artifact"].write_text("tampered replay bytes", encoding="utf-8")

    with pytest.raises(DebateContractError) as error:
        validate_promotion_request(request_path, repo_root=tmp_path)
    assert error.value.code == "research_artifact_sha256_mismatch"


def _research_claim_receipt_fixture(
    tmp_path: Path, *, research_artifact: Path | None = None
) -> dict[str, object]:
    fixture = _research_replay_fixture(
        tmp_path,
        research_artifact=research_artifact,
    )
    paths = fixture["paths"]
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        proposal=_research_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "research-claim-promotion.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path,
        expected_proposal=_research_proposal(),
        repo_root=tmp_path,
    )
    ticket = {
        **_research_proposal(),
        "experiment_id": "exp-20990101-001",
        "experiment_uid": "expuid-claim-receipt-fixture",
        "created_at": "2026-07-29T00:00:00+00:00",
        "status": "proposed",
        "claimed_at": None,
        "alpha_promotion": anchor,
        "research_refs": anchor["research_refs"],
    }
    return {**fixture, "request_path": request_path, "anchor": anchor, "ticket": ticket}


def test_claim_receipt_snapshots_research_bytes_and_survives_live_advancement(
    tmp_path: Path,
) -> None:
    fixture = _research_claim_receipt_fixture(tmp_path)
    ticket = fixture["ticket"]
    claimed_at = "2099-01-01T00:01:00+00:00"
    receipt = build_ticket_promotion_claim_receipt(
        ticket,
        claimed_validation_at=claimed_at,
        repo_root=tmp_path,
    )
    assert receipt["promotion_hash"] == fixture["anchor"]["promotion_hash"]
    assert receipt["experiment_id"] == ticket["experiment_id"]
    assert receipt["experiment_uid"] == ticket["experiment_uid"]
    assert receipt["promotion_request_sha256"] == fixture["anchor"][
        "promotion_request_sha256"
    ]
    assert receipt["claimed_validation_at"] == claimed_at
    assert len(receipt["research_artifact_snapshots"]) == 1
    snapshot = receipt["research_artifact_snapshots"][0]
    assert snapshot["locator"] == "data/research_replay/market-prior.json"
    assert snapshot["snapshot_path"] == (
        "data/alpha_search/promotion_artifact_snapshots/" + snapshot["sha256"]
    )
    snapshot_path = tmp_path / snapshot["snapshot_path"]
    assert snapshot_path.read_bytes() == fixture["paths"]["artifact"].read_bytes()

    claimed = copy.deepcopy(ticket)
    claimed.update(
        {
            "status": "claimed",
            "claimed_at": claimed_at,
            "alpha_promotion_claim_receipt": receipt,
        }
    )
    assert validate_ticket_promotion_claim_receipt(
        claimed, repo_root=tmp_path
    ) == receipt

    fixture["paths"]["artifact"].write_text(
        json.dumps({"timestamp": "2099-01-01T00:02:00Z", "probability": 0.7}),
        encoding="utf-8",
    )
    with pytest.raises(DebateContractError) as direct_error:
        validate_promotion_request(fixture["request_path"], repo_root=tmp_path)
    assert direct_error.value.code == "research_artifact_sha256_mismatch"
    with pytest.raises(DebateContractError) as proposed_error:
        revalidate_ticket_promotion(ticket, repo_root=tmp_path)
    assert proposed_error.value.code == "research_artifact_sha256_mismatch"
    assert revalidate_ticket_promotion(claimed, repo_root=tmp_path) == fixture["anchor"]

    missing = copy.deepcopy(claimed)
    del missing["alpha_promotion_claim_receipt"]
    with pytest.raises(DebateContractError) as missing_error:
        revalidate_ticket_promotion(missing, repo_root=tmp_path)
    assert missing_error.value.code == "alpha_promotion_claim_receipt_missing"


def test_claim_receipt_cutoff_and_durable_clock_order_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _research_claim_receipt_fixture(tmp_path)
    assert claim_receipt_required_for_ticket(
        {
            "experiment_id": "exp-20260729-001",
            "lane": "alpha_search",
            "status": "claimed",
            "created_at": "2026-07-28T23:59:59+00:00",
            "claimed_at": "2026-07-28T23:59:59+00:00",
        }
    )
    assert not claim_receipt_required_for_ticket(
        {
            "experiment_id": "exp-20260729-002",
            "lane": "measurement_repair",
            "status": "claimed",
            "created_at": "2026-07-29T00:01:00+00:00",
            "claimed_at": "2026-07-29T00:02:00+00:00",
        }
    )
    with pytest.raises(DebateContractError) as order_error:
        build_ticket_promotion_claim_receipt(
            fixture["ticket"],
            claimed_validation_at="2026-07-28T23:59:59+00:00",
            repo_root=tmp_path,
        )
    assert order_error.value.code == "claim_receipt_clock_order_invalid"

    malformed = copy.deepcopy(fixture["ticket"])
    malformed["created_at"] = "not-an-iso-clock"
    with pytest.raises(DebateContractError) as malformed_error:
        build_ticket_promotion_claim_receipt(
            malformed,
            claimed_validation_at="2099-01-01T00:01:00+00:00",
            repo_root=tmp_path,
        )
    assert malformed_error.value.code == "claim_receipt_clock_invalid"


@pytest.mark.parametrize("relative_path", [".env", ".git/config"])
def test_research_artifact_declaration_rejects_secret_or_control_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    artifact = tmp_path / relative_path
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("sensitive fixture", encoding="utf-8")
    with pytest.raises(DebateContractError) as error:
        _research_claim_receipt_fixture(
            tmp_path,
            research_artifact=artifact,
        )
    assert error.value.code == "claim_snapshot_source_forbidden"


def test_research_artifact_declaration_rejects_claim_cas_source(
    tmp_path: Path,
) -> None:
    artifact = (
        tmp_path
        / "data"
        / "alpha_search"
        / "promotion_artifact_snapshots"
        / ("a" * 64)
    )
    artifact.parent.mkdir(parents=True)
    artifact.write_text("recursive CAS fixture", encoding="utf-8")
    with pytest.raises(DebateContractError) as error:
        _research_claim_receipt_fixture(
            tmp_path,
            research_artifact=artifact,
        )
    assert error.value.code == "claim_snapshot_source_is_cas"


def test_claim_receipt_rejects_oversized_artifact_before_cas_write(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "data" / "research_replay" / "warehouse.sqlite"
    artifact.parent.mkdir(parents=True)
    with artifact.open("wb") as handle:
        handle.seek(CLAIM_SNAPSHOT_MAX_FILE_BYTES)
        handle.write(b"x")
    fixture = _research_claim_receipt_fixture(
        tmp_path,
        research_artifact=artifact,
    )
    with pytest.raises(DebateContractError) as error:
        build_ticket_promotion_claim_receipt(
            fixture["ticket"],
            claimed_validation_at="2099-01-01T00:01:00+00:00",
            repo_root=tmp_path,
        )
    assert error.value.code == "claim_snapshot_source_too_large"
    assert "compact manifest/hash artifact" in error.value.detail
    assert not (
        tmp_path / "data" / "alpha_search" / "promotion_artifact_snapshots"
    ).exists()


def test_claim_receipt_fails_on_receipt_snapshot_and_bound_panel_tamper(
    tmp_path: Path,
) -> None:
    fixture = _research_claim_receipt_fixture(tmp_path)
    claimed_at = "2099-01-01T00:01:00+00:00"
    receipt = build_ticket_promotion_claim_receipt(
        fixture["ticket"],
        claimed_validation_at=claimed_at,
        repo_root=tmp_path,
    )
    claimed = copy.deepcopy(fixture["ticket"])
    claimed.update(
        {
            "status": "rejected",
            "claimed_at": claimed_at,
            "alpha_promotion_claim_receipt": receipt,
        }
    )

    forged = copy.deepcopy(claimed)
    forged["alpha_promotion_claim_receipt"]["promotion_hash"] = "c" * 64
    with pytest.raises(DebateContractError) as receipt_error:
        revalidate_ticket_promotion(forged, repo_root=tmp_path)
    assert receipt_error.value.code == "claim_receipt_promotion_hash_mismatch"

    copied = copy.deepcopy(claimed)
    copied["experiment_id"] = "exp-20990101-999"
    with pytest.raises(DebateContractError) as identity_error:
        revalidate_ticket_promotion(copied, repo_root=tmp_path)
    assert identity_error.value.code == "claim_receipt_experiment_id_mismatch"

    extra_bytes = b"unrelated receipt artifact"
    extra_digest = hashlib.sha256(extra_bytes).hexdigest()
    extra_snapshot = (
        tmp_path
        / "data"
        / "alpha_search"
        / "promotion_artifact_snapshots"
        / extra_digest
    )
    extra_snapshot.write_bytes(extra_bytes)
    extra = copy.deepcopy(claimed)
    extra_receipt = extra["alpha_promotion_claim_receipt"]
    extra_receipt["research_artifact_snapshots"].append(
        {
            "locator": "data/research_replay/unrelated.json",
            "sha256": extra_digest,
            "snapshot_path": (
                "data/alpha_search/promotion_artifact_snapshots/" + extra_digest
            ),
        }
    )
    extra_receipt["receipt_hash"] = canonical_hash(
        {key: value for key, value in extra_receipt.items() if key != "receipt_hash"}
    )
    with pytest.raises(DebateContractError) as membership_error:
        validate_ticket_promotion_claim_receipt(extra, repo_root=tmp_path)
    assert membership_error.value.code == "claim_receipt_artifact_set_mismatch"

    panel_path = fixture["paths"]["panel"]
    original_panel = panel_path.read_bytes()
    panel = json.loads(original_panel)
    panel["selection_reason"] = "tampered after claim"
    _write(panel_path, panel)
    with pytest.raises(DebateContractError) as panel_error:
        revalidate_ticket_promotion(claimed, repo_root=tmp_path)
    assert panel_error.value.code == "artifact_sha256_mismatch"
    panel_path.write_bytes(original_panel)

    snapshot_path = tmp_path / receipt["research_artifact_snapshots"][0]["snapshot_path"]
    snapshot_path.write_text("tampered snapshot", encoding="utf-8")
    with pytest.raises(DebateContractError) as snapshot_error:
        revalidate_ticket_promotion(claimed, repo_root=tmp_path)
    assert snapshot_error.value.code == "claim_receipt_snapshot_sha256_mismatch"


def test_claim_receipt_refuses_conflicting_content_addressed_bytes(
    tmp_path: Path,
) -> None:
    fixture = _research_claim_receipt_fixture(tmp_path)
    digest = hashlib.sha256(fixture["paths"]["artifact"].read_bytes()).hexdigest()
    snapshot_dir = tmp_path / "data" / "alpha_search" / "promotion_artifact_snapshots"
    snapshot_dir.mkdir(parents=True)
    destination = snapshot_dir / digest
    destination.write_text("conflicting bytes", encoding="utf-8")

    with pytest.raises(DebateContractError) as error:
        build_ticket_promotion_claim_receipt(
            fixture["ticket"],
            claimed_validation_at="2099-01-01T00:01:00+00:00",
            repo_root=tmp_path,
        )
    assert error.value.code == "claim_snapshot_conflict"
    assert destination.read_text(encoding="utf-8") == "conflicting bytes"


def test_promotion_rejects_nonpass_and_grade_mismatch(tmp_path: Path) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))

    grade_mismatch = copy.deepcopy(panel)
    selected = grade_mismatch["selected_candidate_id"]
    grade_mismatch["candidate_snapshots"][0]["evidence_grade"] = "observer"
    _write(paths["panel"], grade_mismatch)
    with pytest.raises((DebateContractError, AlphaSearchError)):
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )

    nonpass = copy.deepcopy(panel)
    nonpass["preflight_decisions"][selected]["decision"] = "park"
    _write(paths["panel"], nonpass)
    with pytest.raises((DebateContractError, AlphaSearchError)):
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )


def test_promotion_rejects_pre_reservation_abort_artifact(tmp_path: Path) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))
    abort_dir = tmp_path / "data" / "alpha_search"
    abort_dir.mkdir(parents=True)
    _write(
        abort_dir / "fixture_abort.json",
        {
            "schema_version": 1,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "abort_before_alpha_reservation",
            "selection_scope_id": panel["selection_scope_id"],
            "panel_hash": panel["panel_hash"],
            "candidate_id": fixture["candidate"]["candidate_id"],
            "reason": "fixture readiness was superseded before alpha reservation",
        },
    )
    with pytest.raises(DebateContractError, match="pre_reservation_abort_blocks_promotion"):
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )


def test_abort_veto_precedes_evidence_grade_validation(tmp_path: Path) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))
    revoked = copy.deepcopy(panel)
    revoked["candidate_snapshots"][0]["evidence_grade"] = "observed_only"
    _write(paths["panel"], revoked)
    abort_dir = tmp_path / "data" / "alpha_search"
    abort_dir.mkdir(parents=True)
    _write(
        abort_dir / "revoked_abort.json",
        {
            "schema_version": 1,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "abort_before_alpha_reservation",
            "selection_scope_id": panel["selection_scope_id"],
            "panel_hash": panel["panel_hash"],
        },
    )

    with pytest.raises(DebateContractError) as error:
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )
    assert error.value.code == "pre_reservation_abort_blocks_promotion"


def test_promotion_fails_closed_on_corrupt_abort_artifact(tmp_path: Path) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))
    abort_dir = tmp_path / "data" / "alpha_search"
    abort_dir.mkdir(parents=True)
    (abort_dir / "corrupt_abort.json").write_text("{", encoding="utf-8")

    with pytest.raises(DebateContractError) as error:
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )
    assert error.value.code == "invalid_pre_reservation_abort_artifact"


@pytest.mark.parametrize(
    "invalid_abort",
    [
        [],
        {
            "schema_version": True,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "abort_before_alpha_reservation",
            "panel_hash": "0" * 64,
        },
        {
            "schema_version": 1,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "parked",
            "panel_hash": "0" * 64,
        },
        {
            "schema_version": 1,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "abort_before_alpha_reservation",
        },
    ],
)
def test_promotion_fails_closed_on_invalid_abort_contract(
    tmp_path: Path, invalid_abort: object,
) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))
    abort_dir = tmp_path / "data" / "alpha_search"
    abort_dir.mkdir(parents=True)
    _write(abort_dir / "invalid_abort.json", invalid_abort)

    with pytest.raises(DebateContractError) as error:
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            debate_artifact_path=debate_path,
            proposal=_proposal(),
            repo_root=tmp_path,
        )
    assert error.value.code == "invalid_pre_reservation_abort_artifact"


def test_promotion_allows_same_candidate_in_fresh_panel_and_scope(
    tmp_path: Path,
) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))
    abort_dir = tmp_path / "data" / "alpha_search"
    abort_dir.mkdir(parents=True)
    _write(
        abort_dir / "stale_abort.json",
        {
            "schema_version": 1,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "abort_before_alpha_reservation",
            "selection_scope_id": "scope-stale",
            "panel_hash": "0" * 64,
            "candidate_id": fixture["candidate"]["candidate_id"],
        },
    )

    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_proposal(),
        repo_root=tmp_path,
    )
    assert request["candidate_id"] == fixture["candidate"]["candidate_id"]


def test_promotion_validation_rejects_abort_recorded_after_build(
    tmp_path: Path,
) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    _write(debate_path, _build_lock(tmp_path, _debate_draft(candidate_pool_hash(panel))))
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "promotion-before-abort.json"
    _write(request_path, request)
    abort_dir = tmp_path / "data" / "alpha_search"
    abort_dir.mkdir(parents=True)
    _write(
        abort_dir / "late_abort.json",
        {
            "schema_version": 1,
            "record_type": "alpha_search_pre_reservation_abort",
            "decision": "abort_before_alpha_reservation",
            "selection_scope_id": panel["selection_scope_id"],
        },
    )

    with pytest.raises(DebateContractError, match="pre_reservation_abort_blocks_promotion"):
        validate_promotion_request(
            request_path, expected_proposal=_proposal(), repo_root=tmp_path
        )


def test_alpha_search_build_promotion_cli_writes_only_requested_artifact(
    tmp_path: Path,
) -> None:
    fixture = _panel_fixture(tmp_path)
    panel = fixture["panel"]
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    proposal_path = tmp_path / "proposal.json"
    output_path = tmp_path / "promotion.json"
    draft = _debate_draft(candidate_pool_hash(panel))
    mailbox_root = _populate_mailbox(tmp_path, draft)
    _write(
        debate_path,
        build_debate_lock(
            draft, repo_root=tmp_path, mailbox_root=mailbox_root
        ),
    )
    _write(proposal_path, _proposal())
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ALPHA_SEARCH_CLI),
            "build-promotion",
            str(paths["panel"]),
            "--surfaces",
            str(paths["surfaces"]),
            "--scope-manifest",
            str(paths["scope"]),
            "--prior-fingerprints",
            str(paths["prior"]),
            "--debate-lock",
            str(debate_path),
            "--proposal",
            str(proposal_path),
            "--output",
            str(output_path),
            "--repo-root",
            str(tmp_path),
            "--isolated-fixture",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    request = json.loads(output_path.read_text(encoding="utf-8"))
    assert request["candidate_id"] == fixture["candidate"]["candidate_id"]
    assert request["trade_enabled"] is False
    assert request["experiment_id_reserved"] is False


def test_claim_time_revalidation_binds_ticket_proposal_and_anchor(
    tmp_path: Path,
) -> None:
    fixture = _panel_fixture(tmp_path)
    paths = fixture["paths"]
    debate_path = tmp_path / "debate.json"
    request_path = tmp_path / "promotion.json"
    _write(
        debate_path,
        _build_lock(
            tmp_path,
            _debate_draft(candidate_pool_hash(fixture["panel"]))
        ),
    )
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        debate_artifact_path=debate_path,
        proposal=_proposal(),
        repo_root=tmp_path,
    )
    _write(request_path, request)
    anchor = validate_promotion_request(request_path, repo_root=tmp_path)
    ticket = {
        **_proposal(),
        "prediction": {
            **_proposal()["prediction"],
            "recorded_at": "2026-07-20T21:31:00Z",
        },
        "alpha_promotion": anchor,
        "research_refs": anchor["research_refs"],
    }
    assert revalidate_ticket_promotion(ticket, repo_root=tmp_path) == anchor

    ticket["hypothesis"] = "changed after promotion"
    with pytest.raises(DebateContractError, match="ticket_proposal_mismatch"):
        revalidate_ticket_promotion(ticket, repo_root=tmp_path)


def test_research_refs_change_snapshot_hash_but_not_candidate_id() -> None:
    base = _candidate()
    with_ref = dict(base)
    with_ref["research_refs"] = ["res-20260721-layout-faithful-edgar-filing-data"]
    with_ref["candidate_id"] = "pending"
    rebuilt = HypothesisCandidate.with_computed_id(with_ref)
    assert rebuilt.candidate_id == base["candidate_id"]
    assert rebuilt.canonical_hash != canonical_hash(base)
