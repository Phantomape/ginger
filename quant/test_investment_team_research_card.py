from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from quant.alpha_search_contract import ContractValidationError
from quant.investment_team_research_card import (
    ROLE_NAMES,
    normalise_research_card,
    project_hypothesis_candidate,
    validate_research_card,
)


def _candidate() -> dict:
    return {
        "schema_version": 1,
        "candidate_kind": "plain_event_lead",
        "candidate_id": "pending",
        "search_queue": "exploration",
        "title": "Customer concentration disclosure as a candidate risk signal",
        "hypothesis": "A newly disclosed customer concentration may alter forward earnings resilience.",
        "fingerprint": {
            "data_source": "company filings",
            "component_sources": ["company filings", "industry data"],
            "expectation_proxy": "unidentified",
            "economic_mechanism": "customer concentration changes earnings resilience",
            "decision_surface": "candidate pool",
            "payoff_shape": "asymmetric downside avoidance",
            "horizon": "20 trading days",
            "execution_dependency": "liquid common stock",
            "portfolio_role": "research lead",
        },
        "surface_ids": ["surface-company-filings", "surface-industry-data"],
        "expectation_gap": None,
        "why_not_arbitraged": "The disclosure requires issuer and industry context.",
        "falsifier": "No difference versus the existing candidate pool after PIT-safe replay.",
        "baseline": {"policy": "existing candidate pool"},
        "treatment": {"policy": "observe disclosed customer concentration"},
        "replacement_value_comparator": "existing candidate admitted at the same slot",
        "expected_horizon": "20 trading days",
        "execution_envelope": {
            "intended_instrument": "common stock",
            "liquidity_dependency": "baseline liquidity rules",
            "costs_and_carry": "baseline commissions and slippage",
            "borrow_dependency": "none for long-only lead",
            "capacity_constraint": "no production allocation",
            "timing_constraint": "after source known_at",
            "trade_enabled": False,
            "orders_enabled": False,
            "live_ready": False,
        },
        "evidence_grade": "lead",
        "production_impact": {"trade_enabled": False},
        "next_machine_action": "run outcome-blind D0-D3",
    }


def _evidence(role_name: str) -> list[dict]:
    if role_name == "financial_analyst":
        return [
            {
                "claim": "The filing discloses material customer concentration.",
                "source": "sec-filing-20260730",
                "source_group": "sec_filing",
                "source_kind": "primary",
                "known_at": "2026-07-30T21:00:00Z",
            },
            {
                "claim": "Industry data indicates weaker end-market diversification.",
                "source": "industry-dataset-20260730",
                "source_group": "industry_data",
                "source_kind": "secondary",
                "known_at": "2026-07-30T22:00:00Z",
            },
        ]
    return [
        {
            "claim": f"Evidence-backed {role_name} finding.",
            "source": f"{role_name}-primary-20260730",
            "source_group": "primary_document",
            "source_kind": "primary",
            "known_at": "2026-07-30T20:00:00Z",
        }
    ]


def _card() -> dict:
    return {
        "schema_version": 1,
        "record_type": "investment_team_research_card",
        "card_id": "pending",
        "created_at": "2026-07-31T21:00:00Z",
        "data_cutoff": "2026-07-31T20:00:00Z",
        "outcome_blind": True,
        "trade_enabled": False,
        "subject": {
            "company": "Example Corp",
            "tickers": ["EXM"],
            "research_question": "Can customer concentration become a testable candidate-pool hypothesis?",
        },
        "researchability": {
            "grade": "B",
            "basis": "Primary filings are available, but customer-level economics are incomplete.",
            "limitations": ["Customer contract economics are not fully public."],
        },
        "roles": {
            role_name: {
                "status": "complete",
                "conclusion": f"{role_name} found a bounded research lead.",
                "evidence": _evidence(role_name),
                "uncertainty": "The effect size and timing remain untested.",
            }
            for role_name in ROLE_NAMES
        },
        "conflicts": [],
        "decision": {
            "disposition": "test",
            "rationale": "The mechanism is explicit enough for outcome-blind preflight.",
            "next_machine_action": "run_d0_d3",
            "candidate": _candidate(),
        },
    }


def test_normalise_validate_and_project_existing_candidate_contract() -> None:
    card = normalise_research_card(_card())

    assert card["card_id"].startswith("itrc-")
    assert card["decision"]["candidate"]["candidate_id"].startswith("cand-")
    assert validate_research_card(card) == card
    assert project_hypothesis_candidate(card) == card["decision"]["candidate"]
    assert project_hypothesis_candidate(card)["evidence_grade"] == "lead"


def test_missing_role_fails_closed() -> None:
    raw = _card()
    del raw["roles"]["risk_assessor"]

    with pytest.raises(ContractValidationError, match="missing_field"):
        normalise_research_card(raw)


def test_financial_role_requires_cross_source_evidence() -> None:
    raw = _card()
    raw["roles"]["financial_analyst"]["evidence"] = [
        raw["roles"]["financial_analyst"]["evidence"][0]
    ]

    with pytest.raises(ContractValidationError, match="financial_cross_source_evidence_required"):
        normalise_research_card(raw)


def test_evidence_after_cutoff_fails_closed() -> None:
    raw = _card()
    raw["roles"]["business_analyst"]["evidence"][0]["known_at"] = "2026-07-31T20:00:01Z"

    with pytest.raises(ContractValidationError, match="evidence_after_data_cutoff"):
        normalise_research_card(raw)


def test_researchability_does_not_upgrade_candidate_evidence() -> None:
    raw = _card()
    raw["researchability"]["grade"] = "A"
    raw["researchability"]["limitations"] = []
    raw["decision"]["candidate"]["evidence_grade"] = "gate_candidate"

    with pytest.raises(ContractValidationError, match="investment_team_evidence_upgrade_forbidden"):
        normalise_research_card(raw)


@pytest.mark.parametrize("mutation", ["conflict", "grade_c", "abstention"])
def test_test_disposition_requires_clear_complete_research(mutation: str) -> None:
    raw = _card()
    if mutation == "conflict":
        raw["conflicts"] = ["Financial and industry roles disagree on demand durability."]
        error = "unresolved_conflicts"
    elif mutation == "grade_c":
        raw["researchability"]["grade"] = "C"
        error = "researchability_c_test_forbidden"
    else:
        role = raw["roles"]["risk_assessor"]
        role["status"] = "abstain"
        role["evidence"] = []
        error = "complete_team_required"

    with pytest.raises(ContractValidationError, match=error):
        normalise_research_card(raw)


def test_park_card_stops_before_candidate_projection() -> None:
    raw = _card()
    raw["roles"]["risk_assessor"] = {
        "status": "abstain",
        "conclusion": "Management evidence is insufficient.",
        "evidence": [],
        "uncertainty": "No primary-source capital allocation history is available.",
    }
    raw["conflicts"] = ["Management quality cannot yet be verified."]
    raw["decision"] = {
        "disposition": "park",
        "rationale": "Collect primary management evidence before forming a machine candidate.",
        "next_machine_action": "collect_primary_management_evidence",
        "candidate": None,
    }
    card = normalise_research_card(raw)

    assert validate_research_card(card)["decision"]["disposition"] == "park"
    with pytest.raises(ContractValidationError, match="candidate_projection_stopped"):
        project_hypothesis_candidate(card)


def test_card_id_detects_post_normalisation_edits() -> None:
    card = normalise_research_card(_card())
    changed = copy.deepcopy(card)
    changed["decision"]["rationale"] = "Changed after signing."

    with pytest.raises(ContractValidationError, match="card_id_mismatch"):
        validate_research_card(changed)


def test_cli_normalise_validate_project_round_trip(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "investment_team_research_card.py"
    source = tmp_path / "input.json"
    card_path = tmp_path / "card.json"
    candidate_path = tmp_path / "candidate.json"
    source.write_text(json.dumps(_card()), encoding="utf-8")

    for command in (
        ["normalise", str(source), "--output", str(card_path)],
        ["validate", str(card_path)],
        ["project", str(card_path), "--output", str(candidate_path)],
    ):
        completed = subprocess.run(
            [sys.executable, "-B", str(script), *command],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert candidate["candidate_id"].startswith("cand-")
    assert candidate["evidence_grade"] == "lead"
