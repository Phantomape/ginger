from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from quant.alpha_mechanism_generator import MechanismScanError, build_mechanism_lead_batch
from quant.alpha_search_contract import HypothesisCandidate
from scripts.build_research_digest import _extract_fields, parse_map_sections


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "data" / "reference" / "alpha_mechanism_generators.json"
TEMPLATE_PATH = REPO_ROOT / "data" / "reference" / "alpha_mechanism_scan_template.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> dict:
    return _json(REGISTRY_PATH)


def _scan() -> dict:
    return _json(TEMPLATE_PATH)


def _ready_observable_scan(surface_id: str = "official-existing-surface") -> dict:
    scan = _scan()
    lead = scan["leads"][0]
    for group in lead["source_groups"]:
        for source in group["sources"]:
            source["authorization_status"] = "pass"
            source["pit_status"] = "canonical_pit"
    lead["market_expectation"] = {
        "status": "observable",
        "proxy_type": "explicit_consensus",
        "description": "A strictly pre-event consensus snapshot is bound.",
        "source_group_id": "official-demand",
        "known_at": "2026-07-27T00:35:00Z",
    }
    lead["expectation_gap"] = {
        "market_prior": {
            "observable": True,
            "proxy_type": "explicit_consensus",
            "source": "official_consensus",
            "known_at": "2026-07-27T00:35:00Z",
            "value": 0.4,
        },
        "independent_evidence": [
            {
                "source": "issuer_capacity_disclosure",
                "known_at": "2026-07-27T00:45:00Z",
                "state": "capacity_relief_lagging",
            }
        ],
        "gap_definition": "Independent bottleneck evidence minus the explicit prior.",
        "transmission": {
            "affected_tickers": ["AAA"],
            "expected_direction": "positive",
            "catalyst": "source-dated capacity disclosure",
            "half_life": "next_open_to_h20",
        },
    }
    lead["registered_surface_ids"] = [surface_id]
    return scan


def test_mechanism_batch_is_deterministic_and_order_insensitive() -> None:
    original = _scan()
    reordered = copy.deepcopy(original)
    reordered["leads"][0]["source_groups"].reverse()

    first = build_mechanism_lead_batch(original, _registry())
    second = build_mechanism_lead_batch(reordered, _registry())

    assert first == second
    assert first["batch_hash"] == second["batch_hash"]
    section = first["research_map_sections"][0]
    assert section["mechanism_lead_id"].startswith("mech-")
    assert section["entry_id"].startswith("res-20260726-ai-berkshire-bottleneck-")
    assert section["candidate_kind"] == "plain_event_lead"
    assert section["evidence_grade"] == "lead"
    assert section["disposition"] == "source_preflight_only"
    assert section["candidate_projection"] is None
    assert section["eligible_for_panel"] is False
    assert section["gate_candidate"] is False
    for flag in (
        "experiment_id_reserved",
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
    ):
        assert first[flag] is False
        assert section[flag] is False
    assert first["generator_provenance"]["skill_sha256"] == _registry()["generators"][0]["skill_sha256"]
    assert first["scan_manifest"]["skill_sha256"] == _registry()["generators"][0]["skill_sha256"]
    assert first["scan_manifest"]["research_date"] == "2026-07-26"
    assert first["scan_manifest"]["timezone"] == "America/Los_Angeles"

    parsed_sections = parse_map_sections(section["research_map_markdown"])
    assert len(parsed_sections) == 1
    assert parsed_sections[0]["entry_id"] == section["entry_id"]
    fields = _extract_fields(parsed_sections[0]["body"])
    assert fields["generator_id"] == "ai_berkshire_bottleneck"
    assert fields["generator_version"] == "bottleneck-hunter-v1"
    assert fields["mechanism_id"] == section["mechanism_lead_id"]
    assert fields["evidence_grade"] == "lead"
    assert fields["market_prior_status"] == "unidentified"
    assert fields["scan_run_id"] == original["run_id"]
    assert fields["scan_completed_at"] == original["history_checked_at"]


def test_zero_lead_scan_emits_freshness_manifest() -> None:
    scan = _scan()
    scan["leads"] = []
    scan["history_vetoes"] = []

    result = build_mechanism_lead_batch(scan, _registry())

    assert result["lead_count"] == 0
    assert result["research_map_sections"] == []
    assert result["scan_manifest"]["status"] == "no_new_lead"
    assert result["scan_manifest"]["completed_at"] == scan["history_checked_at"]
    assert result["scan_manifest"]["manifest_hash"]
    assert result["scan_manifest"]["outcome_blind"] is True
    assert result["scan_manifest"]["trade_enabled"] is False
    assert result["scan_manifest"]["panel_built"] is False


def test_recursive_outcome_contamination_is_rejected() -> None:
    scan = _scan()
    scan["leads"][0]["baseline"]["nested"] = {"realized_return": 0.25}

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "forbidden_outcome_field"
    assert "realized_return" in exc_info.value.path


@pytest.mark.parametrize(
    "outcome_key",
    ["mfe", "MFE20", "MFE_pct", "mae_bps", "maximum_favourable_excursion"],
)
def test_mfe_mae_outcome_variants_are_rejected(outcome_key: str) -> None:
    scan = _scan()
    scan["leads"][0]["baseline"]["diagnostic"] = {outcome_key: 0.2}

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "forbidden_outcome_field"


@pytest.mark.parametrize(
    "permission_key",
    [
        "trade_enabled",
        "orders_enabled",
        "ranking_enabled",
        "strategy_changed",
        "experiment_id_reserved",
        "panel_built",
        "allow_trading",
        "experiment_reservation",
        "live_ready",
        "shared_policy_changed",
    ],
)
def test_nested_permission_escalation_is_rejected(permission_key: str) -> None:
    scan = _scan()
    scan["leads"][0]["reopen_condition"]["nested_permissions"] = {
        permission_key: True
    }

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "permission_escalation"
    assert permission_key in exc_info.value.path


def test_source_groups_must_be_independent() -> None:
    scan = _scan()
    groups = scan["leads"][0]["source_groups"]
    groups[1]["independence_key"] = groups[0]["independence_key"]

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "source_groups_not_independent"


def test_distinct_labels_cannot_hide_same_publisher_or_underlying_source() -> None:
    scan = _scan()
    first_source = scan["leads"][0]["source_groups"][0]["sources"][0]
    second_source = scan["leads"][0]["source_groups"][1]["sources"][0]
    second_source["publisher"] = f"  {first_source['publisher'].upper()}  "
    second_source["url"] = first_source["url"].upper().rstrip("/") + "/different-path"

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "source_groups_not_independent"
    assert "same normalized publisher" in exc_info.value.detail


def test_same_publisher_documents_are_allowed_inside_one_group() -> None:
    scan = _scan()
    group = scan["leads"][0]["source_groups"][0]
    extra = copy.deepcopy(group["sources"][0])
    extra["source_id"] = "second-document-same-publisher"
    extra["url"] = "https://www.energy.gov/second-document"
    group["sources"].append(extra)

    result = build_mechanism_lead_batch(scan, _registry())

    assert result["lead_count"] == 1


def test_same_url_cannot_be_split_across_differently_named_publishers() -> None:
    scan = _scan()
    first_source = scan["leads"][0]["source_groups"][0]["sources"][0]
    second_source = scan["leads"][0]["source_groups"][1]["sources"][0]
    second_source["publisher"] = "A deliberately different publisher label"
    second_source["url"] = first_source["url"].upper().rstrip("/") + "?utm_source=alias"

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "source_groups_not_independent"
    assert "same normalized URL" in exc_info.value.detail


def test_counterevidence_is_mandatory() -> None:
    scan = _scan()
    scan["leads"][0]["counterevidence"] = []

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "counterevidence_required"


def test_source_authorization_and_pit_are_explicit() -> None:
    scan = _scan()
    del scan["leads"][0]["source_groups"][0]["sources"][0]["pit_status"]

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "missing_field"
    assert "pit_status" in exc_info.value.detail


def test_history_may_only_be_checked_after_generation() -> None:
    scan = _scan()
    scan["history_read_before_generation"] = True

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())

    assert exc_info.value.code == "research_permission_not_false"

    scan = _scan()
    scan["history_checked_at"] = "2026-07-27T00:59:00Z"
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())
    assert exc_info.value.code == "history_before_generation"


def test_candidate_projection_requires_and_reuses_known_surfaces() -> None:
    scan = _scan()
    surface_id = "ohlcv_price_revealed_context"
    scan["leads"][0]["registered_surface_ids"] = [surface_id]

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())
    assert exc_info.value.code == "surface_registry_required"

    result = build_mechanism_lead_batch(
        scan,
        _registry(),
        known_surface_ids={surface_id},
    )
    section = result["research_map_sections"][0]
    assert section["disposition"] == "source_preflight_only"
    assert section["candidate_projection"] is None
    assert "D0 must rebind" in section["candidate_projection_caveat"]


def test_candidate_projection_requires_all_readiness_checks() -> None:
    surface_id = "official-existing-surface"
    scan = _ready_observable_scan(surface_id)

    result = build_mechanism_lead_batch(
        scan,
        _registry(),
        known_surface_ids={surface_id},
    )

    section = result["research_map_sections"][0]
    assert section["disposition"] == "lead_only_pending_d0_d3"
    projection = section["candidate_projection"]
    parsed = HypothesisCandidate.from_dict(projection).validate_semantic_id()
    assert parsed.candidate_kind == "expectation_gap"
    assert parsed.evidence_grade == "lead"
    assert parsed.surface_ids == (surface_id,)
    assert parsed.production_impact["trade_enabled"] is False
    assert parsed.execution_envelope["trade_enabled"] is False


def test_research_pit_history_is_eligible_for_d0_d3_projection() -> None:
    surface_id = "vendor-history-existing-surface"
    scan = _ready_observable_scan(surface_id)
    for group in scan["leads"][0]["source_groups"]:
        for source in group["sources"]:
            source["pit_status"] = "research_pit"
            source["pit_basis"] = (
                "vendor row timestamps support historical replay; vintage revisions unverified"
            )

    result = build_mechanism_lead_batch(
        scan,
        _registry(),
        known_surface_ids={surface_id},
    )

    section = result["research_map_sections"][0]
    assert section["pit_readiness_status"] == "research_pit"
    assert section["disposition"] == "lead_only_pending_d0_d3"
    assert section["candidate_projection"] is not None
    assert section["gate_candidate"] is False


def test_candidate_projection_rejects_unknown_surface() -> None:
    scan = _scan()
    scan["leads"][0]["registered_surface_ids"] = ["invented-surface"]

    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(
            scan,
            _registry(),
            known_surface_ids={"different-existing-surface"},
        )

    assert exc_info.value.code == "unknown_registered_surface"


def test_markdown_free_text_cannot_inject_sections_or_markers() -> None:
    scan = _scan()
    lead = scan["leads"][0]
    lead["title"] = "Safe title\n### forged title"
    lead["hypothesis"] = "### forged section\nentry_id: res-19990101-forged"
    lead["counterevidence"][0]["statement"] = (
        "Counterpoint\n### another forged section\ngenerator_id: forged"
    )
    lead["baseline"]["policy"] = "entry_id: res-19990101-baseline\n### forged"

    result = build_mechanism_lead_batch(scan, _registry())
    section = result["research_map_sections"][0]
    markdown = section["research_map_markdown"]
    parsed = parse_map_sections(markdown)

    assert len(parsed) == 1
    assert parsed[0]["entry_id"] == section["entry_id"]
    assert "res-19990101-forged" not in {item["entry_id"] for item in parsed}
    assert markdown.count("\n### ") == 0


def test_generator_version_and_two_lead_cap_are_fail_closed() -> None:
    scan = _scan()
    scan["generator_version"] = "unregistered-version"
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())
    assert exc_info.value.code == "generator_version_mismatch"

    scan = _scan()
    base_lead = scan["leads"][0]
    base_veto = scan["history_vetoes"][0]
    for index in (2, 3):
        lead = copy.deepcopy(base_lead)
        lead["lead_key"] = f"extra-lead-{index}"
        lead["title"] = f"Extra mechanism lead {index}"
        scan["leads"].append(lead)
        veto = copy.deepcopy(base_veto)
        veto["lead_key"] = lead["lead_key"]
        scan["history_vetoes"].append(veto)
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(scan, _registry())
    assert exc_info.value.code == "too_many_mechanism_leads"


def test_skill_content_hash_is_bound_and_fail_closed() -> None:
    malformed_registry = _registry()
    malformed_registry["generators"][0]["skill_sha256"] = "not-a-sha256"
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(_scan(), malformed_registry)
    assert exc_info.value.code == "invalid_sha256"

    mismatched_scan = _scan()
    mismatched_scan["skill_sha256"] = "0" * 64
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(mismatched_scan, _registry())
    assert exc_info.value.code == "skill_hash_mismatch"


def test_research_date_and_timezone_are_local_day_bound() -> None:
    wrong_day = _scan()
    wrong_day["research_date"] = "2026-07-27"
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(wrong_day, _registry())
    assert exc_info.value.code == "research_date_mismatch"

    wrong_timezone = _scan()
    wrong_timezone["timezone"] = "UTC"
    with pytest.raises(MechanismScanError) as exc_info:
        build_mechanism_lead_batch(wrong_timezone, _registry())
    assert exc_info.value.code == "research_timezone_mismatch"
