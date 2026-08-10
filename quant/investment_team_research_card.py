"""Fail-closed adapter from Investment Team research to alpha-search leads.

The adapter is intentionally outside production and trading paths.  It turns a
four-role research synthesis into the repository's existing
``HypothesisCandidate`` contract; it does not reserve experiments, run D0-D3,
or make portfolio decisions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from quant.alpha_search_contract import (
    ContractValidationError,
    HypothesisCandidate,
    canonical_hash,
)


SCHEMA_VERSION = 1
RECORD_TYPE = "investment_team_research_card"
ROLE_NAMES = (
    "business_analyst",
    "financial_analyst",
    "industry_researcher",
    "risk_assessor",
)
ROLE_STATUSES = frozenset({"complete", "abstain"})
RESEARCHABILITY_GRADES = frozenset({"A", "B", "C"})
SOURCE_KINDS = frozenset({"primary", "secondary"})
DISPOSITIONS = frozenset({"test", "park", "reject"})


def _fail(code: str, path: str, message: str) -> None:
    raise ContractValidationError(code, path, message)


def _object(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("object_required", path, "must be an object")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            _fail("string_key_required", path, "all object keys must be strings")
        result[key] = item
    return result


def _check_fields(
    value: Mapping[str, Any],
    *,
    required: set[str],
    path: str,
) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing:
        _fail("missing_field", path, f"missing required fields: {', '.join(missing)}")
    if unknown:
        _fail("unknown_field", path, f"unknown fields: {', '.join(unknown)}")


def _text(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("nonempty_string_required", path, "must be a non-empty string")
    return value.strip()


def _string_list(value: Any, *, path: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of strings")
    result = [_text(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if not allow_empty and not result:
        _fail("nonempty_list_required", path, "must contain at least one item")
    if len(set(result)) != len(result):
        _fail("duplicate_value", path, "must not contain duplicate values")
    return result


def _timestamp(value: Any, *, path: str) -> tuple[str, datetime]:
    text = _text(value, path=path)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(
            "invalid_timestamp", path, "must be a timezone-aware ISO datetime"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("timezone_required", path, "must include a timezone")
    normalised = parsed.isoformat().replace("+00:00", "Z")
    return normalised, parsed


def _normalise_subject(value: Any) -> dict[str, Any]:
    path = "$.subject"
    raw = _object(value, path=path)
    _check_fields(raw, required={"company", "tickers", "research_question"}, path=path)
    return {
        "company": _text(raw["company"], path=f"{path}.company"),
        "tickers": _string_list(raw["tickers"], path=f"{path}.tickers", allow_empty=False),
        "research_question": _text(
            raw["research_question"], path=f"{path}.research_question"
        ),
    }


def _normalise_researchability(value: Any) -> dict[str, Any]:
    path = "$.researchability"
    raw = _object(value, path=path)
    _check_fields(raw, required={"grade", "basis", "limitations"}, path=path)
    grade = _text(raw["grade"], path=f"{path}.grade").upper()
    if grade not in RESEARCHABILITY_GRADES:
        _fail(
            "invalid_researchability_grade",
            f"{path}.grade",
            f"must be one of {sorted(RESEARCHABILITY_GRADES)}",
        )
    limitations = _string_list(raw["limitations"], path=f"{path}.limitations")
    if grade in {"B", "C"} and not limitations:
        _fail(
            "researchability_limitations_required",
            f"{path}.limitations",
            f"grade {grade} must name at least one limitation",
        )
    return {
        "grade": grade,
        "basis": _text(raw["basis"], path=f"{path}.basis"),
        "limitations": limitations,
    }


def _normalise_evidence(
    value: Any,
    *,
    path: str,
    cutoff_clock: datetime,
) -> dict[str, str]:
    raw = _object(value, path=path)
    _check_fields(
        raw,
        required={"claim", "source", "source_group", "source_kind", "known_at"},
        path=path,
    )
    source_kind = _text(raw["source_kind"], path=f"{path}.source_kind").lower()
    if source_kind not in SOURCE_KINDS:
        _fail(
            "invalid_source_kind",
            f"{path}.source_kind",
            f"must be one of {sorted(SOURCE_KINDS)}",
        )
    known_at, known_clock = _timestamp(raw["known_at"], path=f"{path}.known_at")
    if known_clock > cutoff_clock:
        _fail(
            "evidence_after_data_cutoff",
            f"{path}.known_at",
            "must be no later than card.data_cutoff",
        )
    return {
        "claim": _text(raw["claim"], path=f"{path}.claim"),
        "source": _text(raw["source"], path=f"{path}.source"),
        "source_group": _text(raw["source_group"], path=f"{path}.source_group").lower(),
        "source_kind": source_kind,
        "known_at": known_at,
    }


def _normalise_role(
    value: Any,
    *,
    role_name: str,
    cutoff_clock: datetime,
) -> dict[str, Any]:
    path = f"$.roles.{role_name}"
    raw = _object(value, path=path)
    _check_fields(raw, required={"status", "conclusion", "evidence", "uncertainty"}, path=path)
    status = _text(raw["status"], path=f"{path}.status").lower()
    if status not in ROLE_STATUSES:
        _fail("invalid_role_status", f"{path}.status", f"must be one of {sorted(ROLE_STATUSES)}")
    if not isinstance(raw["evidence"], Sequence) or isinstance(
        raw["evidence"], (str, bytes, bytearray)
    ):
        _fail("list_required", f"{path}.evidence", "must be a list")
    evidence = [
        _normalise_evidence(
            item,
            path=f"{path}.evidence[{index}]",
            cutoff_clock=cutoff_clock,
        )
        for index, item in enumerate(raw["evidence"])
    ]
    if status == "complete" and not evidence:
        _fail("role_evidence_required", f"{path}.evidence", "complete roles need evidence")
    if status == "abstain" and evidence:
        _fail("abstention_evidence_forbidden", f"{path}.evidence", "abstaining roles must leave evidence empty")

    if role_name == "financial_analyst" and status == "complete":
        sources = {item["source"] for item in evidence}
        source_groups = {item["source_group"] for item in evidence}
        source_kinds = {item["source_kind"] for item in evidence}
        if len(sources) < 2 or len(source_groups) < 2 or "primary" not in source_kinds:
            _fail(
                "financial_cross_source_evidence_required",
                f"{path}.evidence",
                "financial findings need two distinct source groups and at least one primary source",
            )

    return {
        "status": status,
        "conclusion": _text(raw["conclusion"], path=f"{path}.conclusion"),
        "evidence": evidence,
        "uncertainty": _text(raw["uncertainty"], path=f"{path}.uncertainty"),
    }


def _normalise_roles(value: Any, *, cutoff_clock: datetime) -> dict[str, Any]:
    path = "$.roles"
    raw = _object(value, path=path)
    _check_fields(raw, required=set(ROLE_NAMES), path=path)
    return {
        role_name: _normalise_role(
            raw[role_name], role_name=role_name, cutoff_clock=cutoff_clock
        )
        for role_name in ROLE_NAMES
    }


def _normalise_decision(value: Any, *, compute_candidate_id: bool) -> dict[str, Any]:
    path = "$.decision"
    raw = _object(value, path=path)
    _check_fields(
        raw,
        required={"disposition", "rationale", "next_machine_action", "candidate"},
        path=path,
    )
    disposition = _text(raw["disposition"], path=f"{path}.disposition").lower()
    if disposition not in DISPOSITIONS:
        _fail("invalid_disposition", f"{path}.disposition", f"must be one of {sorted(DISPOSITIONS)}")
    action = _text(raw["next_machine_action"], path=f"{path}.next_machine_action")
    candidate_value = raw["candidate"]
    candidate: dict[str, Any] | None
    if disposition == "test":
        if not isinstance(candidate_value, Mapping):
            _fail("candidate_required", f"{path}.candidate", "test disposition requires a candidate object")
        raw_grade = str(candidate_value.get("evidence_grade") or "").strip().lower()
        if raw_grade != "lead":
            _fail(
                "investment_team_evidence_upgrade_forbidden",
                f"{path}.candidate.evidence_grade",
                "Investment Team research may only emit lead; D0-D3 determines later maturity",
            )
        parsed = (
            HypothesisCandidate.with_computed_id(candidate_value)
            if compute_candidate_id
            else HypothesisCandidate.from_dict(candidate_value).validate_semantic_id()
        )
        candidate = parsed.to_dict()
        if action != "run_d0_d3":
            _fail(
                "invalid_test_action",
                f"{path}.next_machine_action",
                "test disposition must use run_d0_d3",
            )
    else:
        if candidate_value is not None:
            _fail(
                "stopped_candidate_forbidden",
                f"{path}.candidate",
                "park/reject cards stop before candidate projection and must use null",
            )
        candidate = None
    return {
        "disposition": disposition,
        "rationale": _text(raw["rationale"], path=f"{path}.rationale"),
        "next_machine_action": action,
        "candidate": candidate,
    }


def _normalise_card(value: Any, *, compute_ids: bool) -> dict[str, Any]:
    raw = _object(value, path="$")
    _check_fields(
        raw,
        required={
            "schema_version",
            "record_type",
            "card_id",
            "created_at",
            "data_cutoff",
            "outcome_blind",
            "trade_enabled",
            "subject",
            "researchability",
            "roles",
            "conflicts",
            "decision",
        },
        path="$",
    )
    if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
        _fail("schema_version_mismatch", "$.schema_version", f"must equal {SCHEMA_VERSION}")
    if raw["record_type"] != RECORD_TYPE:
        _fail("record_type_mismatch", "$.record_type", f"must equal {RECORD_TYPE!r}")
    if raw["outcome_blind"] is not True:
        _fail("outcome_blind_required", "$.outcome_blind", "must be true")
    if raw["trade_enabled"] is not False:
        _fail("trade_boundary_violation", "$.trade_enabled", "must be false")

    created_at, created_clock = _timestamp(raw["created_at"], path="$.created_at")
    data_cutoff, cutoff_clock = _timestamp(raw["data_cutoff"], path="$.data_cutoff")
    if created_clock < cutoff_clock:
        _fail("clock_order_invalid", "$.created_at", "must be at or after data_cutoff")

    researchability = _normalise_researchability(raw["researchability"])
    roles = _normalise_roles(raw["roles"], cutoff_clock=cutoff_clock)
    conflicts = _string_list(raw["conflicts"], path="$.conflicts")
    decision = _normalise_decision(raw["decision"], compute_candidate_id=compute_ids)
    if decision["disposition"] == "test":
        incomplete = [name for name, role in roles.items() if role["status"] != "complete"]
        if incomplete:
            _fail(
                "complete_team_required",
                "$.roles",
                f"test disposition requires complete roles: {', '.join(incomplete)}",
            )
        if conflicts:
            _fail("unresolved_conflicts", "$.conflicts", "test disposition requires an empty conflict list")
        if researchability["grade"] == "C":
            _fail(
                "researchability_c_test_forbidden",
                "$.researchability.grade",
                "grade C research must be parked or rejected",
            )

    normalised = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "card_id": _text(raw["card_id"], path="$.card_id"),
        "created_at": created_at,
        "data_cutoff": data_cutoff,
        "outcome_blind": True,
        "trade_enabled": False,
        "subject": _normalise_subject(raw["subject"]),
        "researchability": researchability,
        "roles": roles,
        "conflicts": conflicts,
        "decision": decision,
    }
    expected_id = expected_research_card_id(normalised)
    if not compute_ids and normalised["card_id"] != expected_id:
        _fail("card_id_mismatch", "$.card_id", f"expected {expected_id!r} for semantic content")
    if compute_ids:
        normalised["card_id"] = expected_id
    return normalised


def research_card_semantic_hash(value: Mapping[str, Any]) -> str:
    payload = dict(value)
    payload.pop("card_id", None)
    return canonical_hash(payload)


def expected_research_card_id(value: Mapping[str, Any]) -> str:
    return f"itrc-{research_card_semantic_hash(value)[:20]}"


def normalise_research_card(value: Mapping[str, Any]) -> dict[str, Any]:
    """Compute semantic IDs and return a validated canonical card."""

    return _normalise_card(value, compute_ids=True)


def validate_research_card(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an already-normalised card, including its semantic IDs."""

    return _normalise_card(value, compute_ids=False)


def project_hypothesis_candidate(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return the existing alpha-search candidate for a valid ``test`` card."""

    card = validate_research_card(value)
    if card["decision"]["disposition"] != "test":
        _fail(
            "candidate_projection_stopped",
            "$.decision.disposition",
            "only test cards may project a HypothesisCandidate",
        )
    return dict(card["decision"]["candidate"])


__all__ = [
    "DISPOSITIONS",
    "RECORD_TYPE",
    "RESEARCHABILITY_GRADES",
    "ROLE_NAMES",
    "SCHEMA_VERSION",
    "expected_research_card_id",
    "normalise_research_card",
    "project_hypothesis_candidate",
    "research_card_semantic_hash",
    "validate_research_card",
]
