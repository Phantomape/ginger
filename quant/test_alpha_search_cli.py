from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from quant.alpha_search_contract import (
    HypothesisCandidate,
    canonical_hash,
    research_only_production_impact,
)
from quant.alpha_search_ledger import load_alpha_search_events


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "scripts" / "alpha_search.py"


def _surfaces() -> dict:
    common = {
        "pit_status": "canonical_pit",
        "evidence_grade": "gate_candidate",
        "settled_count": 20,
        "independent_count": 20,
        "candidate_overlap_count": 10,
        "gate_ready": True,
        "saturation_status": "open",
        "reopen_condition": None,
        "source_contract_status": "pass",
        "as_of": "2026-07-20T20:00:00Z",
    }
    return {
        "schema_version": 1,
        "surfaces": [
            {
                **common,
                "surface_id": "market-prior",
                "data_source": "prediction_market",
                "component_sources": ["prediction_market"],
                "roles": ["market_expectation"],
                "artifacts": ["manifest:prediction-market"],
                "artifact_snapshot_hashes": {
                    "manifest:prediction-market": canonical_hash("prediction-market")
                },
                "expectation_proxy": {
                    "type": "direct_implied_probability",
                    "field": "probability",
                    "source": "prediction_market",
                },
            },
            {
                **common,
                "surface_id": "official-fact",
                "data_source": "official_fact",
                "component_sources": ["official_fact"],
                "roles": ["independent_evidence"],
                "artifacts": ["manifest:official-fact"],
                "artifact_snapshot_hashes": {
                    "manifest:official-fact": canonical_hash("official-fact")
                },
                "expectation_proxy": None,
            },
        ],
    }


def _candidate() -> dict:
    raw = {
        "schema_version": 1,
        "candidate_kind": "expectation_gap",
        "candidate_id": "pending",
        "search_queue": "exploration",
        "title": "Direct prior versus official fact",
        "created_at": "2026-07-20T21:15:00Z",
        "created_by": "alpha-search-cli-test",
        "hypothesis": "The independent fact implies a higher state probability than the quoted prior.",
        "fingerprint": {
            "data_source": "prediction_market",
            "component_sources": ["prediction_market", "official_fact"],
            "expectation_proxy": "direct_implied_probability",
            "economic_mechanism": "official_probability_repricing",
            "decision_surface": "candidate_pool",
            "payoff_shape": "event_drift",
            "horizon": "H5-H20",
            "execution_dependency": "liquid_cash_equity",
            "portfolio_role": "orthogonal_event_sleeve",
        },
        "surface_ids": ["market-prior", "official-fact"],
        "expectation_gap": {
            "market_prior": {
                "observable": True,
                "proxy_type": "direct_implied_probability",
                "source": "prediction_market",
                "known_at": "2026-07-20T20:00:00Z",
                "value": 0.4,
            },
            "independent_evidence": [
                {
                    "source": "official_fact",
                    "known_at": "2026-07-20T20:00:00Z",
                    "state": "confirmed",
                }
            ],
            "our_posterior": {
                "method": "frozen_calibrator_v1",
                "calibration_reference": "calibration-v1",
                "value": 0.6,
                "known_at": "2026-07-20T20:00:00Z",
            },
            "gap_definition": "posterior minus direct prior",
            "transmission": {
                "catalyst": "official resolution",
                "affected_tickers": ["AAA"],
                "expected_direction": "positive",
                "half_life": "H5-H20",
            },
        },
        "why_not_arbitraged": "The issuer map and timing are costly to maintain.",
        "falsifier": "No repricing after exact timestamp alignment.",
        "baseline": {"policy": "cash"},
        "treatment": {"policy": "frozen event admission"},
        "replacement_value_comparator": "cash, SPY, QQQ, and displaced core",
        "expected_horizon": "H5-H20",
        "execution_envelope": {
            "intended_instrument": "cash equity",
            "liquidity_dependency": "ADV floor",
            "costs_and_carry": "fixed bps",
            "borrow_dependency": "none",
            "capacity_constraint": "paper cap",
            "timing_constraint": "next session",
            "trade_enabled": False,
        },
        "evidence_grade": "observer",
        "next_machine_action": "Run novelty before any experiment reservation.",
        "production_impact": research_only_production_impact(),
    }
    return HypothesisCandidate.with_computed_id(raw).to_dict()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_freezes_verifies_reports_and_idempotently_ledgers(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate_path = tmp_path / "candidate.json"
    candidates_path = tmp_path / "candidates.json"
    surfaces_path = tmp_path / "surfaces.json"
    panel_path = tmp_path / "panel.json"
    report_path = tmp_path / "report.json"
    scope_path = tmp_path / "scope.json"
    generation_config_path = tmp_path / "generation-config.json"
    prior_fingerprints_path = tmp_path / "prior-fingerprints.json"
    frozen_families_path = tmp_path / "frozen-families.jsonl"
    ledger_path = tmp_path / "events.jsonl"
    _write(candidate_path, candidate)
    _write(candidates_path, {"candidates": [candidate]})
    _write(surfaces_path, _surfaces())
    _write(
        generation_config_path,
        {"queues": ["exploration", "adjacent", "exploitation"], "outcome_fields_allowed": False},
    )
    frozen_families_path.write_text(
        json.dumps(
            {
                "family_key": "unrelated_old_family",
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
    built_history = _run(
        "build-history",
        "--frozen-families", str(frozen_families_path),
        "--history-cutoff", "2026-07-20T20:29:00Z",
        "--isolated-history-fixture",
        "--output", str(prior_fingerprints_path),
    )
    assert built_history.returncode == 0, built_history.stderr

    validated = _run("validate-candidate", str(candidate_path))
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["valid"] is True

    built_scope = _run(
        "build-scope",
        "--scope-name", "phase1-cli-test",
        "--preregistered-at", "2026-07-20T20:30:00Z",
        "--data-cutoff", "2026-07-20T21:00:00Z",
        "--freeze-at", "2026-07-20T21:30:00Z",
        "--generator-version", "cli-test-generator-v1",
        "--generation-config", str(generation_config_path),
        "--surfaces", str(surfaces_path),
        "--prior-fingerprints", str(prior_fingerprints_path),
        "--isolated-history-fixture",
        "--allowed-surface", "market-prior",
        "--allowed-surface", "official-fact",
        "--queue-budget", "exploration=1",
        "--queue-budget", "adjacent=0",
        "--queue-budget", "exploitation=0",
        "--expected-candidate-count", "1",
        "--selection-limit", "1",
        "--output", str(scope_path),
    )
    assert built_scope.returncode == 0, built_scope.stderr

    command = (
        "build-panel",
        str(candidates_path),
        "--surfaces", str(surfaces_path),
        "--scope-manifest", str(scope_path),
        "--prior-fingerprints", str(prior_fingerprints_path),
        "--isolated-history-fixture",
        "--selection-pool-complete",
        "--ledger", str(ledger_path),
        "--output", str(panel_path),
    )
    first = _run(*command)
    assert first.returncode == 0, first.stderr
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    assert panel["selected_candidate_id"] == candidate["candidate_id"]
    assert panel["outcome_blind"] is True
    assert len(load_alpha_search_events(ledger_path)) == 3

    retry = _run(*command)
    assert retry.returncode == 0, retry.stderr
    assert len(load_alpha_search_events(ledger_path)) == 3

    verified = _run(
        "verify-panel",
        str(panel_path),
        "--surfaces", str(surfaces_path),
        "--scope-manifest", str(scope_path),
        "--prior-fingerprints", str(prior_fingerprints_path),
        "--isolated-history-fixture",
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["valid"] is True

    reported = _run(
        "report",
        str(panel_path),
        "--surfaces", str(surfaces_path),
        "--scope-manifest", str(scope_path),
        "--prior-fingerprints", str(prior_fingerprints_path),
        "--isolated-history-fixture",
        "--output", str(report_path),
    )
    assert reported.returncode == 0, reported.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["panel_hash"] == panel["panel_hash"]
    assert report["trade_enabled"] is False


def test_cli_new_scope_rejects_bare_empty_prior(tmp_path: Path) -> None:
    surfaces_path = tmp_path / "surfaces.json"
    generation_config_path = tmp_path / "generation-config.json"
    prior_path = tmp_path / "prior.json"
    _write(surfaces_path, _surfaces())
    _write(generation_config_path, {"queues": ["exploration"], "outcome_fields_allowed": False})
    _write(prior_path, [])
    result = _run(
        "build-scope",
        "--scope-name", "must-fail-closed",
        "--preregistered-at", "2026-07-20T20:30:00Z",
        "--data-cutoff", "2026-07-20T21:00:00Z",
        "--freeze-at", "2026-07-20T21:30:00Z",
        "--generator-version", "cli-test-generator-v1",
        "--generation-config", str(generation_config_path),
        "--surfaces", str(surfaces_path),
        "--prior-fingerprints", str(prior_path),
        "--allowed-surface", "market-prior",
        "--queue-budget", "exploration=1",
        "--expected-candidate-count", "1",
    )
    assert result.returncode == 2
    assert "historical_snapshot_required" in result.stderr


def test_cli_strict_scope_rejects_noncanonical_fixture_snapshot(tmp_path: Path) -> None:
    surfaces_path = tmp_path / "surfaces.json"
    generation_config_path = tmp_path / "generation-config.json"
    frozen_path = tmp_path / "frozen.jsonl"
    prior_path = tmp_path / "prior.json"
    _write(surfaces_path, _surfaces())
    _write(generation_config_path, {"queues": ["exploration"], "outcome_fields_allowed": False})
    frozen_path.write_text(
        json.dumps(
            {
                "family_key": "fixture_family",
                "fingerprint": {
                    "data_source": "fixture_source",
                    "field_tags": ["fixture"],
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
    built = _run(
        "build-history",
        "--frozen-families", str(frozen_path),
        "--history-cutoff", "2026-07-20T20:29:00Z",
        "--isolated-history-fixture",
        "--output", str(prior_path),
    )
    assert built.returncode == 0, built.stderr
    result = _run(
        "build-scope",
        "--scope-name", "strict-repo-history",
        "--preregistered-at", "2026-07-20T20:30:00Z",
        "--data-cutoff", "2026-07-20T21:00:00Z",
        "--freeze-at", "2026-07-20T21:30:00Z",
        "--generator-version", "cli-test-generator-v1",
        "--generation-config", str(generation_config_path),
        "--surfaces", str(surfaces_path),
        "--prior-fingerprints", str(prior_path),
        "--allowed-surface", "market-prior",
        "--queue-budget", "exploration=1",
        "--expected-candidate-count", "1",
    )
    assert result.returncode == 2
    assert "canonical_history_anchor_required" in result.stderr


def test_cli_rejects_outcome_contamination(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["realized_return"] = 0.2
    path = tmp_path / "contaminated.json"
    _write(path, candidate)
    result = _run("validate-candidate", str(path))
    assert result.returncode == 2
    assert "forbidden_outcome_field" in result.stderr


def test_cli_research_refs_are_snapshot_metadata_not_candidate_identity(
    tmp_path: Path,
) -> None:
    candidate = _candidate()
    original_id = candidate["candidate_id"]
    candidate["research_refs"] = [
        "res-20260721-structured-event-representation-for-text-alpha",
        "res-20260721-layout-faithful-edgar-filing-data",
        "res-20260721-structured-event-representation-for-text-alpha",
    ]
    path = tmp_path / "research-referenced.json"
    _write(path, candidate)
    result = _run("validate-candidate", str(path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["candidate_id"] == original_id

    candidate["research_refs"] = ["research-note-without-date-prefix"]
    _write(path, candidate)
    invalid = _run("validate-candidate", str(path))
    assert invalid.returncode == 2
    assert "invalid_research_ref" in invalid.stderr


def test_cli_builds_lead_only_external_mechanism_batch(tmp_path: Path) -> None:
    scan_path = REPO_ROOT / "data" / "reference" / "alpha_mechanism_scan_template.json"
    registry_path = REPO_ROOT / "data" / "reference" / "alpha_mechanism_generators.json"
    output_path = tmp_path / "mechanism-batch.json"

    result = _run(
        "build-mechanism-leads",
        str(scan_path),
        "--generator-registry",
        str(registry_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == json.loads(result.stdout)
    assert payload["record_type"] == "external_mechanism_lead_batch"
    assert payload["scan_manifest"]["status"] == "leads_generated"
    assert payload["scan_manifest"]["completed_at"]
    assert payload["lead_count"] == 1
    section = payload["research_map_sections"][0]
    assert section["candidate_kind"] == "plain_event_lead"
    assert section["evidence_grade"] == "lead"
    assert section["disposition"] == "source_preflight_only"
    assert section["candidate_projection"] is None
    assert section["eligible_for_panel"] is False
    assert payload["experiment_id_reserved"] is False
    assert payload["trade_enabled"] is False
    assert payload["orders_enabled"] is False
    assert payload["ranking_enabled"] is False
    assert payload["panel_built"] is False


def test_cli_mechanism_scan_rejects_recursive_outcome_field(tmp_path: Path) -> None:
    scan = json.loads(
        (REPO_ROOT / "data" / "reference" / "alpha_mechanism_scan_template.json").read_text(
            encoding="utf-8"
        )
    )
    scan["leads"][0]["treatment"]["audit"] = {"forward_return": 0.1}
    scan_path = tmp_path / "contaminated-mechanism-scan.json"
    _write(scan_path, scan)

    result = _run("build-mechanism-leads", str(scan_path))

    assert result.returncode == 2
    assert "forbidden_outcome_field" in result.stderr
    assert "forward_return" in result.stderr


def test_cli_zero_lead_mechanism_scan_still_emits_manifest(tmp_path: Path) -> None:
    scan = json.loads(
        (REPO_ROOT / "data" / "reference" / "alpha_mechanism_scan_template.json").read_text(
            encoding="utf-8"
        )
    )
    scan["run_id"] = "zero-lead-cli-test"
    scan["leads"] = []
    scan["history_vetoes"] = []
    scan_path = tmp_path / "zero-lead-scan.json"
    _write(scan_path, scan)

    result = _run("build-mechanism-leads", str(scan_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["research_map_sections"] == []
    assert payload["scan_manifest"]["status"] == "no_new_lead"
    assert payload["scan_manifest"]["run_id"] == "zero-lead-cli-test"
    assert payload["scan_manifest"]["completed_at"] == scan["history_checked_at"]
    assert payload["scan_manifest"]["trade_enabled"] is False
    assert payload["scan_manifest"]["experiment_id_reserved"] is False
