import json
from pathlib import Path

from quant.v2_contracts import canonical_hash


ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = (
    ROOT / "data" / "v2" / "repository_external_append_anchor_decision_packet.json"
)
EXPECTED_CONTRACT_SHA256 = (
    "76c8c20e28fddbf167d12202332907ead7a95dd5f7c4352507aeacb6a4dce2ed"
)
EXPECTED_HASH_SCOPE = [
    "current_boundary",
    "threat_model",
    "hash_recipe",
    "anchor_record_contract",
    "external_receipt_contract",
    "target_requirements",
    "target_options",
    "rejected_substitutes",
    "publication_protocol",
    "successor_validation",
    "canonical_read_protocol",
    "acceptance_tests",
    "selected_contract_policy",
    "activation_receipt_contract",
    "user_selection",
    "secrets_policy",
    "activation_gate",
]


def _load_packet() -> dict:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def test_external_append_anchor_packet_freezes_security_contract() -> None:
    packet = _load_packet()

    assert packet["schema_version"] == 1
    assert packet["record_type"] == (
        "v2_repository_external_append_anchor_decision_packet"
    )
    assert packet["packet_status"] == "ready_for_user_selection"
    assert packet["contract_hash_scope"] == EXPECTED_HASH_SCOPE
    assert packet["packet_contract_sha256"] == EXPECTED_CONTRACT_SHA256
    assert canonical_hash({key: packet[key] for key in EXPECTED_HASH_SCOPE}) == (
        EXPECTED_CONTRACT_SHA256
    )

    anchor_fields = set(packet["anchor_record_contract"]["required_fields"])
    assert {
        "environment",
        "ledger_stream_id",
        "anchor_sequence",
        "previous_anchor_record_sha256",
        "previous_head_hash",
        "head_exact_sha256",
        "head_hash",
        "transition_kind",
        "writer_principal_id",
    } <= anchor_fields

    provider_fields = set(packet["external_receipt_contract"]["required_fields"])
    assert {
        "anchor_contract_sha256",
        "provider_target_id",
        "immutable_locator",
        "retention_mode",
        "retain_until",
        "anchor_object_exact_sha256",
        "provider_receipt_sha256",
    } <= provider_fields

    activation_fields = set(
        packet["activation_receipt_contract"]["required_fields"]
    )
    assert {
        "anchor_contract_sha256",
        "reader_principal_id",
        "readback_provider_target_id",
        "readback_raw_sha256",
        "readback_anchor_object_exact_sha256",
        "independent_readback_evidence_sha256",
        "sequence_one_service_committed_at",
        "sequence_one_readback_verified_at",
        "cutover_verified_at",
        "anchor_gate_eligibility_started_at",
        "canonical_forward_eligibility_started_at",
    } <= activation_fields

    assert [row["test_id"] for row in packet["acceptance_tests"]] == [
        f"A{number}_{suffix}"
        for number, suffix in enumerate(
            (
                "create_only_collision",
                "writer_cannot_mutate_or_delete",
                "strong_read_after_append",
                "lost_ack_retry",
                "local_old_head_rollback",
                "sequence_gap_or_fork",
                "target_outage",
                "principal_separation",
                "rotation_same_manifest_counts",
                "cross_stream_or_environment_replay",
                "remote_one_behind_or_ahead",
                "rollback_then_append_branch",
                "anchor_genesis_cutover",
                "wrong_target_or_retention_receipt",
            ),
            start=1,
        )
    ]


def test_unselected_packet_cannot_claim_deployment_or_eligibility() -> None:
    packet = _load_packet()
    selection = packet["user_selection"]

    assert selection["template_only"] is True
    assert selection["status"] == "required"
    assert selection["implementation_authorization_status"] == "not_authorized"
    for field in (
        "selected_option_id",
        "anchor_contract_sha256",
        "writer_principal_id",
        "reader_principal_id",
        "retention_admin_principal_id",
        "secret_store_reference",
        "cutover_head_hash",
    ):
        assert field in selection
        assert selection[field] is None

    assert packet["selected_contract_policy"]["decision_packet_is_immutable"]
    assert not packet["selected_contract_policy"][
        "fill_decision_packet_in_place_allowed"
    ]
    assert packet["secrets_policy"]["tracked_values_are_references_only"]
    assert not packet["secrets_policy"]["secret_bytes_allowed_in_repository"]

    boundary = packet["current_boundary"]
    assert boundary["external_append_anchor_status"] == "absent"
    assert boundary["canonical_eligibility"] is False
    assert boundary["research_scout_precondition"] is False

    gate = packet["activation_gate"]
    assert gate["implementation_authorized"] is False
    assert gate["target_acceptance_tests_passed"] is False
    assert gate["external_append_anchor_status"] == "absent"
    assert gate["canonical_reads_allowed"] is False
    assert gate["canonical_forward_eligibility_started_at"] is None
    assert gate["research_scout_blocked"] is False
    assert gate["retroactive_evidence_upgrade_allowed"] is False
    assert gate["trade_enabled"] is False
    assert packet["experiment_id"] is None
    assert packet["trade_enabled"] is False
