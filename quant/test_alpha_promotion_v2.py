from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from quant import test_alpha_debate as fixtures
from quant.alpha_search_contract import HypothesisCandidate
from quant.alpha_search_engine import (
    build_selection_scope_manifest,
    freeze_selection_panel,
)
from quant.alpha_search_registry import EvidenceSurfaceRegistry
from scripts.alpha_debate import (
    normalize_ticket_proposal,
    DebateContractError,
    build_promotion_request,
    revalidate_ticket_promotion,
    validate_promotion_request,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ALPHA_SEARCH_CLI = REPO_ROOT / "scripts" / "alpha_search.py"


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_v2(tmp_path: Path, *, research: bool = False) -> tuple[dict, dict]:
    fixture = (
        fixtures._research_replay_fixture(tmp_path)
        if research
        else fixtures._panel_fixture(tmp_path)
    )
    paths = fixture["paths"]
    proposal = fixtures._research_proposal() if research else fixtures._proposal()
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        proposal=proposal,
        repo_root=tmp_path,
    )
    return fixture, request


def test_debate_free_v2_canonical_promotion_revalidates_ticket(
    tmp_path: Path,
) -> None:
    fixture, request = _build_v2(tmp_path)
    assert request["schema_version"] == 2
    assert not any(key.startswith("debate_") for key in request)

    request_path = tmp_path / "promotion-v2.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path,
        expected_proposal=fixtures._proposal(),
        repo_root=tmp_path,
    )
    assert anchor["candidate_id"] == fixture["candidate"]["candidate_id"]
    assert "initiator_runtime" not in anchor
    assert "challenger_runtime" not in anchor
    assert "verifier_runtime" not in anchor

    ticket = {
        **fixtures._proposal(),
        "prediction": {
            **fixtures._proposal()["prediction"],
            "recorded_at": "2026-07-20T21:31:00Z",
        },
        "alpha_promotion": anchor,
        "research_refs": anchor["research_refs"],
    }
    assert revalidate_ticket_promotion(ticket, repo_root=tmp_path) == anchor

    panel_path = fixture["paths"]["panel"]
    tampered = json.loads(panel_path.read_text(encoding="utf-8"))
    tampered["selection_reason"] = "tampered after promotion"
    _write(panel_path, tampered)
    with pytest.raises(DebateContractError, match="artifact_sha256_mismatch"):
        validate_promotion_request(request_path, repo_root=tmp_path)


def test_debate_free_v2_research_replay_keeps_observed_only_boundary(
    tmp_path: Path,
) -> None:
    fixture, request = _build_v2(tmp_path, research=True)
    request_path = tmp_path / "research-promotion-v2.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path,
        expected_proposal=fixtures._research_proposal(),
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
    assert anchor["candidate_id"] == fixture["candidate"]["candidate_id"]


def test_debate_free_v2_rejects_legacy_debate_fields(tmp_path: Path) -> None:
    _, request = _build_v2(tmp_path)
    request["debate_hash"] = "a" * 64
    request_path = tmp_path / "invalid-v2.json"
    _write(request_path, request)

    with pytest.raises(DebateContractError, match="unknown_field"):
        validate_promotion_request(request_path, repo_root=tmp_path)


def test_alpha_search_cli_builds_v2_without_debate_lock(tmp_path: Path) -> None:
    fixture = fixtures._panel_fixture(tmp_path)
    paths = fixture["paths"]
    proposal_path = tmp_path / "proposal.json"
    output_path = tmp_path / "promotion-v2.json"
    _write(proposal_path, fixtures._proposal())

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
    assert request["schema_version"] == 2
    assert request["candidate_id"] == fixture["candidate"]["candidate_id"]
    assert not any(key.startswith("debate_") for key in request)
    assert request["trade_enabled"] is False
    assert request["experiment_id_reserved"] is False


def _settled_forward_surfaces() -> dict:
    surfaces_value = copy.deepcopy(fixtures._surfaces())
    for row in surfaces_value["surfaces"]:
        if row["surface_id"] == "official-fact":
            row.update(
                {
                    "pit_status": "settled_forward_sufficient",
                    "evidence_grade": "observed_only",
                    "gate_ready": False,
                }
            )
    return surfaces_value


def _settled_forward_fixture(tmp_path: Path) -> tuple[dict, dict]:
    surfaces_value = _settled_forward_surfaces()
    registry = EvidenceSurfaceRegistry.from_dict(surfaces_value)
    prior = fixtures._history_snapshot(tmp_path)
    candidate = fixtures._gate_candidate(registry)
    candidate["candidate_id"] = "pending"
    candidate["evidence_grade"] = "observed_only"
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()
    scope = build_selection_scope_manifest(
        scope_name="settled-forward-promotion-fixture",
        preregistered_at="2026-07-20T20:30:00Z",
        data_cutoff="2026-07-20T21:00:00Z",
        freeze_at="2026-07-20T21:30:00Z",
        generator_version="settled-forward-promotion-fixture-v1",
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
        "panel": tmp_path / "settled-panel.json",
        "scope": tmp_path / "settled-scope.json",
        "surfaces": tmp_path / "settled-surfaces.json",
        "prior": tmp_path / "settled-prior.json",
    }
    _write(paths["panel"], panel)
    _write(paths["scope"], scope)
    _write(paths["surfaces"], surfaces_value)
    _write(paths["prior"], prior)
    return {"candidate": candidate, "paths": paths}, surfaces_value


def _settled_forward_proposal() -> dict:
    proposal = fixtures._proposal()
    proposal["change_type"] = "observed_only_attribution"
    return normalize_ticket_proposal(proposal)


def test_settled_forward_attribution_promotion_keeps_observed_only_boundary(
    tmp_path: Path,
) -> None:
    fixture, _ = _settled_forward_fixture(tmp_path)
    paths = fixture["paths"]
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        proposal=_settled_forward_proposal(),
        repo_root=tmp_path,
    )
    request_path = tmp_path / "settled-promotion-v2.json"
    _write(request_path, request)
    anchor = validate_promotion_request(
        request_path,
        expected_proposal=_settled_forward_proposal(),
        repo_root=tmp_path,
    )
    for value in (request, anchor):
        assert value["admission_class"] == "settled_forward_attribution"
        assert value["selected_evidence_grade"] == "observed_only"
        assert value["result_ceiling"] == "observed_only"
        assert value["paper_live_eligible"] is False
        assert {row["pit_status"] for row in value["source_readiness_bindings"]} == {
            "canonical_pit",
            "settled_forward_sufficient",
        }
    assert anchor["candidate_id"] == fixture["candidate"]["candidate_id"]


def test_settled_forward_attribution_requires_observed_only_change_type(
    tmp_path: Path,
) -> None:
    fixture, _ = _settled_forward_fixture(tmp_path)
    paths = fixture["paths"]
    with pytest.raises(
        DebateContractError, match="settled_forward_change_type_required"
    ):
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            proposal=fixtures._proposal(),
            repo_root=tmp_path,
        )


def test_observed_only_grade_requires_a_settled_forward_surface(
    tmp_path: Path,
) -> None:
    surfaces_value = fixtures._surfaces()
    registry = EvidenceSurfaceRegistry.from_dict(surfaces_value)
    prior = fixtures._history_snapshot(tmp_path)
    candidate = fixtures._gate_candidate(registry)
    candidate["candidate_id"] = "pending"
    candidate["evidence_grade"] = "observed_only"
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()
    scope = build_selection_scope_manifest(
        scope_name="settled-forward-missing-surface-fixture",
        preregistered_at="2026-07-20T20:30:00Z",
        data_cutoff="2026-07-20T21:00:00Z",
        freeze_at="2026-07-20T21:30:00Z",
        generator_version="settled-forward-missing-surface-v1",
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
    paths = {
        "panel": tmp_path / "all-canonical-panel.json",
        "scope": tmp_path / "all-canonical-scope.json",
        "surfaces": tmp_path / "all-canonical-surfaces.json",
        "prior": tmp_path / "all-canonical-prior.json",
    }
    _write(paths["panel"], panel)
    _write(paths["scope"], scope)
    _write(paths["surfaces"], surfaces_value)
    _write(paths["prior"], prior)
    with pytest.raises(
        DebateContractError, match="settled_forward_surface_required"
    ):
        build_promotion_request(
            panel_path=paths["panel"],
            scope_manifest_path=paths["scope"],
            surface_registry_path=paths["surfaces"],
            prior_fingerprints_path=paths["prior"],
            proposal=_settled_forward_proposal(),
            repo_root=tmp_path,
        )
