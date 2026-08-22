from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import quant.alpha_search_engine as engine
from quant.alpha_search_contract import HypothesisCandidate, canonical_hash
from quant.alpha_search_engine import (
    AlphaSearchError,
    build_selection_scope_manifest,
    candidate_policy_hash,
    evaluate_preflight,
    freeze_selection_panel,
)
from quant.alpha_search_history import (
    build_historical_prior_snapshot,
    candidate_legacy_fingerprints,
    historical_record_hash,
)
from quant.test_alpha_search_engine import (
    CREATED_AT,
    DATA_CUTOFF,
    FREEZE_AT,
    PREREGISTERED_AT,
    _candidate,
    _surfaces,
)
from scripts.alpha_debate import (
    DebateContractError,
    build_promotion_request,
    normalize_ticket_proposal,
    revalidate_ticket_promotion,
    validate_promotion_request,
)


GENERATED_AT = "2026-07-20T15:00:00Z"
LANE = "entity_like_axis_c"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _history(tmp_path: Path, *, record_count: int = 2) -> dict:
    (tmp_path / "experiments" / "logs").mkdir(parents=True, exist_ok=True)
    base = _candidate()
    fingerprint = next(
        row
        for row in candidate_legacy_fingerprints(base)
        if row["data_source"] == "prediction_market"
    )
    frozen = tmp_path / "frozen.jsonl"
    rows = [
        {
            "family_key": f"entity_like_fixed_policy_{index}",
            "fingerprint": fingerprint,
            "representative_exps": [f"exp-20260719-{index + 1:03d}"],
            "status": "frozen" if index == 0 else "single_attempt",
            "reopen_condition": (
                "wait for at least +50% and +10 settled forward rows under "
                "the unchanged fixed policy"
            ),
        }
        for index in range(record_count)
    ]
    frozen.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return build_historical_prior_snapshot(
        frozen,
        history_cutoff="2026-07-20T14:59:00Z",
        repo_root=tmp_path,
        isolated_fixture=True,
    )


def _readiness(
    tmp_path: Path,
    *,
    baseline: int = 100,
    current: int = 150,
    threshold: int = 150,
) -> tuple[Path, dict, dict]:
    lane = {
        "lane": LANE,
        "counters": {
            "settled_count": current,
            "baseline_at_last_probe": baseline,
        },
        "thresholds": {"settled_count": threshold},
        "status": "ready",
        "threshold_source": "fixture Axis C contract",
        "counter_source": "fixture forward ledger",
        "note": None,
    }
    artifact = {
        "schema_version": 1,
        "generated_at": GENERATED_AT,
        "generator": "test_alpha_reopen_contract",
        "stall_flag_days": 7,
        "lanes": [lane],
    }
    path = tmp_path / "data" / "reopen_readiness.json"
    _write_json(path, artifact)
    return path, artifact, lane


def _proofs(
    tmp_path: Path,
    history: dict,
    *,
    baseline: int = 100,
    current: int = 150,
    threshold: int = 150,
    claimed_records: int | None = None,
) -> tuple[dict, Path]:
    base = _candidate()
    path, artifact, lane = _readiness(
        tmp_path, baseline=baseline, current=current, threshold=threshold
    )
    records = list(history["records"])
    if claimed_records is not None:
        records = records[:claimed_records]
    proofs = []
    for record in records:
        proofs.append(
            {
                "schema_version": 1,
                "axis": "settled_forward_growth",
                "readiness_artifact_path": path.relative_to(tmp_path).as_posix(),
                "readiness_artifact_sha256": hashlib.sha256(
                    path.read_bytes()
                ).hexdigest(),
                "readiness_generated_at": artifact["generated_at"],
                "readiness_lane": LANE,
                "readiness_lane_hash": engine.stable_hash(lane),
                "counters_hash": engine.stable_hash(lane["counters"]),
                "thresholds_hash": engine.stable_hash(lane["thresholds"]),
                "current_counter_key": "settled_count",
                "baseline_counter_key": "baseline_at_last_probe",
                "threshold_key": "settled_count",
                "current_count": current,
                "baseline_count": baseline,
                "threshold_count": threshold,
                "minimum_relative_growth_bps": 5000,
                "minimum_absolute_growth": 10,
                "historical_record_id": record["record_id"],
                "historical_record_hash": historical_record_hash(record),
                "historical_family_key": record["family_key"],
                "representative_experiment_id": record[
                    "representative_exps"
                ][0],
                "reopened_surface_id": "market-prior",
                "policy_hash": candidate_policy_hash(base),
                "fingerprint_hash": engine._fingerprint_key(base),
            }
        )
    base["candidate_id"] = "pending"
    base["quantitative_reopen_proofs"] = sorted(
        proofs, key=lambda proof: proof["historical_record_id"]
    )
    return HypothesisCandidate.with_computed_id(base).to_dict(), path


@pytest.fixture(autouse=True)
def _trust_isolated_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        engine,
        "_validate_repository_reopen_history",
        lambda value, *, repo_root: value,
    )


def _preflight(candidate: dict, history: dict, tmp_path: Path) -> dict:
    return evaluate_preflight(
        candidate,
        _surfaces(),
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at=FREEZE_AT,
        selection_scope_id="scope-" + "7" * 24,
        repo_root=tmp_path,
    )


def test_valid_multiple_entity_like_axis_c_proofs_waive_only_bound_records(
    tmp_path: Path,
) -> None:
    history = _history(tmp_path)
    candidate, _ = _proofs(tmp_path, history)

    result = _preflight(candidate, history, tmp_path)

    assert result["decision"] == "pass"
    assert result["gates"]["D3"] == {"status": "pass", "reasons": []}
    assert candidate["candidate_id"] == _candidate()["candidate_id"]


def test_no_proof_preserves_unchanged_d3_rejection(tmp_path: Path) -> None:
    history = _history(tmp_path)

    result = _preflight(_candidate(), history, tmp_path)

    assert result["decision"] == "reject"
    assert sum(
        reason.startswith("legacy_near_neighbor:")
        for reason in result["gates"]["D3"]["reasons"]
    ) == 2


@pytest.mark.parametrize(
    ("baseline", "current", "threshold", "reason"),
    [
        (100, 149, 150, "quantitative_reopen_relative_growth_insufficient"),
        (10, 15, 15, "quantitative_reopen_absolute_growth_insufficient"),
    ],
)
def test_axis_c_enforces_both_growth_floors(
    tmp_path: Path,
    baseline: int,
    current: int,
    threshold: int,
    reason: str,
) -> None:
    history = _history(tmp_path)
    candidate, _ = _proofs(
        tmp_path,
        history,
        baseline=baseline,
        current=current,
        threshold=threshold,
    )

    result = _preflight(candidate, history, tmp_path)

    assert result["decision"] == "reject"
    assert any(
        item.startswith(reason) for item in result["gates"]["D3"]["reasons"]
    )


@pytest.mark.parametrize(
    ("field", "replacement", "reason"),
    [
        ("readiness_artifact_sha256", "0" * 64, "readiness_artifact_sha256_mismatch"),
        ("readiness_lane", "wrong_lane", "readiness_lane_binding_mismatch"),
        ("current_count", 151, "readiness_current_count_mismatch"),
        ("threshold_count", 151, "readiness_threshold_count_mismatch"),
        ("historical_family_key", "wrong_family", "historical_family_binding_mismatch"),
        (
            "representative_experiment_id",
            "exp-20260718-999",
            "historical_experiment_binding_mismatch",
        ),
        ("policy_hash", "1" * 64, "quantitative_reopen_policy_hash_mismatch"),
        (
            "fingerprint_hash",
            "2" * 64,
            "quantitative_reopen_fingerprint_hash_mismatch",
        ),
    ],
)
def test_mismatched_exact_bindings_fail_closed(
    tmp_path: Path, field: str, replacement: object, reason: str
) -> None:
    history = _history(tmp_path)
    candidate, _ = _proofs(tmp_path, history)
    candidate["quantitative_reopen_proofs"][0][field] = replacement

    result = _preflight(candidate, history, tmp_path)

    assert result["decision"] == "reject"
    assert any(
        reason in item for item in result["gates"]["D3"]["reasons"]
    )


def test_additional_unbound_neighbor_still_blocks(tmp_path: Path) -> None:
    history = _history(tmp_path, record_count=3)
    candidate, _ = _proofs(tmp_path, history, claimed_records=2)
    unbound = history["records"][2]["representative_exps"][0]

    result = _preflight(candidate, history, tmp_path)

    assert result["decision"] == "reject"
    assert any(
        unbound in reason for reason in result["gates"]["D3"]["reasons"]
    )


def test_duplicate_empty_and_non_neighbor_claims_reject(tmp_path: Path) -> None:
    history = _history(tmp_path)
    candidate, _ = _proofs(tmp_path, history)

    duplicate = copy.deepcopy(candidate)
    duplicate["quantitative_reopen_proofs"][1] = copy.deepcopy(
        duplicate["quantitative_reopen_proofs"][0]
    )
    duplicate_result = _preflight(duplicate, history, tmp_path)
    assert "quantitative_reopen_duplicate_target" in " ".join(
        duplicate_result["gates"]["D3"]["reasons"]
    )

    empty = copy.deepcopy(candidate)
    empty["quantitative_reopen_proofs"] = []
    empty_result = _preflight(empty, history, tmp_path)
    assert "quantitative_reopen_proofs_empty" in empty_result["gates"]["D3"][
        "reasons"
    ]

    non_neighbor = copy.deepcopy(candidate)
    non_neighbor["fingerprint"]["economic_mechanism"] = "unrelated_mechanism"
    non_neighbor_result = _preflight(non_neighbor, history, tmp_path)
    assert any(
        "fingerprint_hash_mismatch" in reason
        or "target_not_blocking_neighbor" in reason
        for reason in non_neighbor_result["gates"]["D3"]["reasons"]
    )


def _proposal() -> dict:
    return normalize_ticket_proposal(
        {
            "lane": "alpha_search",
            "hypothesis": "A fixed entity-like surface is ready for Axis-C replay.",
            "change_type": "candidate_pool",
            "single_causal_variable": "fixed_axis_c_replay",
            "causal_components": ["settled forward rows", "unchanged policy"],
            "mechanism_family": "fixed_axis_c_replay",
            "trial_family": "fixed_axis_c_replay_v1",
            "changed_variable": "new settled evidence only",
            "prediction": {
                "success_probability": 0.25,
                "main_failure_modes": ["already priced"],
                "confidence_reason": "Exact quantitative reopen proof.",
            },
        }
    )


def _promotion_fixture(tmp_path: Path) -> tuple[dict, dict, Path]:
    history = _history(tmp_path)
    candidate, readiness_path = _proofs(tmp_path, history)
    candidate["candidate_id"] = "pending"
    candidate["evidence_grade"] = "gate_candidate"
    surfaces = _surfaces()
    surface_rows = {
        row["surface_id"]: row for row in surfaces.to_dict()["surfaces"]
    }
    candidate["source_readiness_snapshot"] = [
        {
            "surface_id": surface_id,
            "snapshot_hash": canonical_hash(surface_rows[surface_id]),
        }
        for surface_id in sorted(candidate["surface_ids"])
    ]
    candidate = HypothesisCandidate.with_computed_id(candidate).to_dict()
    scope = build_selection_scope_manifest(
        scope_name="axis-c-promotion-fixture",
        preregistered_at=PREREGISTERED_AT,
        data_cutoff=DATA_CUTOFF,
        freeze_at=FREEZE_AT,
        generator_version="axis-c-promotion-fixture-v1",
        candidate_generation_config={"outcome_fields_allowed": False},
        allowed_surface_ids=list(surfaces.surface_ids),
        surface_registry_hash=surfaces.canonical_hash,
        prior_fingerprints=history,
        queue_budgets={"exploration": 1, "adjacent": 0, "exploitation": 0},
        expected_candidate_count=1,
        selection_limit=1,
    )
    panel = freeze_selection_panel(
        [candidate],
        surfaces,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=history,
        repo_root=tmp_path,
    )
    paths = {
        "panel": tmp_path / "panel.json",
        "scope": tmp_path / "scope.json",
        "surfaces": tmp_path / "surfaces.json",
        "prior": tmp_path / "prior.json",
        "promotion": tmp_path / "promotion.json",
    }
    for name, value in (
        ("panel", panel),
        ("scope", scope),
        ("surfaces", surfaces.to_dict()),
        ("prior", history),
    ):
        _write_json(paths[name], value)
    request = build_promotion_request(
        panel_path=paths["panel"],
        scope_manifest_path=paths["scope"],
        surface_registry_path=paths["surfaces"],
        prior_fingerprints_path=paths["prior"],
        proposal=_proposal(),
        repo_root=tmp_path,
    )
    _write_json(paths["promotion"], request)
    return request, paths, readiness_path


def test_promotion_build_validate_revalidate_and_post_build_tamper(
    tmp_path: Path,
) -> None:
    request, paths, readiness_path = _promotion_fixture(tmp_path)
    anchor = validate_promotion_request(
        paths["promotion"], expected_proposal=_proposal(), repo_root=tmp_path
    )
    assert anchor["quantitative_reopen_binding"] == request[
        "quantitative_reopen_binding"
    ]
    ticket = {
        **_proposal(),
        "research_refs": [],
        "alpha_promotion": anchor,
    }
    assert revalidate_ticket_promotion(ticket, repo_root=tmp_path) == anchor

    readiness_path.write_text(
        readiness_path.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(DebateContractError):
        validate_promotion_request(paths["promotion"], repo_root=tmp_path)
    with pytest.raises(DebateContractError):
        revalidate_ticket_promotion(ticket, repo_root=tmp_path)
