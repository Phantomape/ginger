"""Small registry helpers for coordinating multi-agent experiments."""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


REPO_ROOT = Path(__file__).resolve().parents[1]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_paths import backtest_result_glob  # noqa: E402

DEFAULT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"
DEFAULT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
DEFAULT_EXPERIMENTS_DIR = REPO_ROOT / "experiments"
DEFAULT_TICKETS_DIR = DEFAULT_EXPERIMENTS_DIR / "tickets"
DEFAULT_EXPERIMENT_LOGS_DIR = DEFAULT_EXPERIMENTS_DIR / "logs"
DEFAULT_CARDS_DIR = DEFAULT_EXPERIMENTS_DIR / "cards"
DEFAULT_MANIFESTS_DIR = DEFAULT_EXPERIMENTS_DIR / "manifests"
DEFAULT_LOCK_TIMEOUT_SECONDS = 30
STALE_LOCK_SECONDS = 300
EXPERIMENT_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])exp[-_](\d{8})[-_](\d{3,})(?!\d)",
    re.IGNORECASE,
)
ACTIVE_STATUSES = {"claimed", "running"}
RESERVATION_INTENT_OPEN_STATUSES = {"proposed", "claimed", "running"}
FINAL_STATUSES = {"accepted", "rejected", "observed_only"}
SHARED_COORDINATION_SCOPES = {
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
}
DISALLOWED_BROAD_SCOPES = {
    "data",
    "docs",
    "quant",
    "scripts",
}
VALID_LANES = {
    "alpha_search",
    "alpha_discovery",
    "loss_attribution",
    "universe_scout",
    "measurement_repair",
}
PREDICTION_REQUIRED_LANES = {
    "alpha_search",
    "alpha_discovery",
    "universe_scout",
}
PREDICTION_ENFORCEMENT_STARTED_AT = "2026-05-29T21:33:00+00:00"
LEAN_QUALITY_ENFORCEMENT_STARTED_AT = "2026-06-07T01:44:00+00:00"
ALPHA_PROMOTION_ENFORCEMENT_STARTED_AT = "2026-07-22T06:34:58+00:00"
LEAN_HARD_INTEGRITY_ENFORCEMENT_STARTED_AT = "2026-08-26T06:51:49+00:00"
EXPERIMENT_RESERVATION_IDENTITY_ENFORCEMENT_STARTED_AT = (
    "2026-08-26T08:20:00+00:00"
)
EXPERIMENT_RESERVATION_IDENTITY_MIN_ID = "exp-20260826-006"
RESEARCH_REPLAY_ADMISSION_CLASS = "research_replay"
RESEARCH_REPLAY_RESULT_CEILING = "observed_only"
RESEARCH_REPLAY_FINAL_STATUSES = {"observed_only", "rejected"}
PRIVATE_REPLAY_SCOUT_CHANGE_TYPE = "private_replay_scout"
PRIVATE_REPLAY_SCOUT_ARTIFACT_RECORD_TYPE = "v2_private_replay_scout_result"
PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION = 1
PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_ENFORCEMENT_STARTED_AT = (
    "2026-08-26T05:10:00+00:00"
)
PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITIONS = {
    "observed_only": {"positive_replay_lead_not_promoted"},
    "rejected": {
        "rejected",
        "inconclusive_insufficient_sample",
        "invalid_contaminated",
    },
}
PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD = (
    "private_replay_scout_closeout_claim_binding"
)
PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD = (
    "private_replay_scout_registry_identity"
)
PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD = (
    "private_replay_scout_canonical_log_sha256"
)
PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD = (
    "private_replay_scout_registry_canonical_log_sha256"
)
EXPERIMENT_RESERVATION_IDENTITY_FIELD = "experiment_reservation_identity"
EXPERIMENT_EVER_CLAIMED_FIELD = "experiment_ever_claimed"
EXPERIMENT_CLAIM_TRANSITION_FIELD = "experiment_claim_transition"
EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD = "experiment_closeout_log_intent"
EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD = (
    "experiment_closeout_log_intent_sha256"
)
SETTLED_FORWARD_ADMISSION_CLASS = "settled_forward_attribution"
# Both research-boundary admission classes share the observed_only ceiling;
# they differ only in the evidence grade frozen at promotion time.
_RESEARCH_ADMISSION_EXPECTED_GRADES = {
    RESEARCH_REPLAY_ADMISSION_CLASS: "lead",
    SETTLED_FORWARD_ADMISSION_CLASS: "observed_only",
}
_SELF_REGISTER_IMMUTABLE_EXISTING_FIELDS = frozenset(
    {
        "experiment_id",
        "experiment_uid",
        "created_at",
        "claimed_at",
        "owner",
        "lane",
        "change_type",
        "alpha_promotion",
        "alpha_promotion_claim_receipt",
        "private_replay_scout_artifact_disposition_contract_version",
        PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD,
        PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD,
        EXPERIMENT_EVER_CLAIMED_FIELD,
        "allowed_write_scope",
        "must_not_touch",
        "hub_identity",
        "ticket_file",
    }
)
_SELF_REGISTER_FORBIDDEN_INPUT_FIELDS = frozenset(
    {
        "experiment_id",
        "experiment_uid",
        "ticket_file",
        "status",
        "result",
        "claimed_at",
        "completed_at",
        EXPERIMENT_RESERVATION_IDENTITY_FIELD,
        PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD,
        PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD,
        EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD,
        EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD,
    }
)


def _alpha_promotion_api():
    """Import the deterministic discovery-promotion contract lazily.

    ``experiment_registry`` is also imported by old runners and isolated unit
    fixtures.  Keeping this import lazy avoids making those legacy read/close
    paths depend on the research-only alpha-search stack.
    """

    import alpha_debate

    return alpha_debate


def _alpha_promotion_gate_enabled(registry):
    """Return True for this checkout (or an explicit isolated test context)."""

    if registry.get("_enforce_alpha_promotion") is True:
        return True
    repo_root = _registry_repo_root(registry)
    if repo_root is None:
        return False
    try:
        return repo_root.resolve() == REPO_ROOT.resolve()
    except OSError:
        return False


def _alpha_promotion_required_for_lane(lane):
    try:
        api = _alpha_promotion_api()
        required = getattr(
            api,
            "PROMOTION_REQUIRED_LANES",
            api.DEBATE_REQUIRED_LANES,
        )
    except (ImportError, AttributeError):
        required = PREDICTION_REQUIRED_LANES
    return lane in required


def _ticket_proposal_payload(
    *, lane, hypothesis, change_type, single_causal_variable,
    causal_components, mechanism_family, trial_family, changed_variable,
    prediction,
):
    payload = {
        "lane": lane,
        "hypothesis": hypothesis,
        "change_type": change_type,
        "single_causal_variable": single_causal_variable,
        "causal_components": list(causal_components or []),
        "mechanism_family": mechanism_family,
        "trial_family": trial_family,
        "changed_variable": changed_variable,
        "prediction": dict(prediction or {}),
    }
    # recorded_at is deliberately volatile reservation metadata; the promotion
    # binds the probability/reasons, not the microsecond at which CLI parsing
    # normalized them.
    payload["prediction"].pop("recorded_at", None)
    try:
        return _alpha_promotion_api().normalize_ticket_proposal(payload)
    except (ImportError, AttributeError):
        return payload


def _validate_alpha_promotion_for_creation(
    registry, *, lane, promotion_request, proposal,
):
    required = _alpha_promotion_required_for_lane(lane)
    enforced = _alpha_promotion_gate_enabled(registry)
    if required and enforced and not promotion_request:
        raise ValueError(
            f"{lane} requires --promotion-request after outcome-blind D0-D3 "
            "panel verification; no experiment ID was reserved"
        )
    if not promotion_request:
        return None
    repo_root = _registry_repo_root(registry) or REPO_ROOT
    return _alpha_promotion_api().validate_promotion_request(
        promotion_request,
        expected_proposal=proposal,
        repo_root=repo_root,
    )


def _ticket_is_post_alpha_promotion_enforcement(ticket):
    cutoff = datetime.fromisoformat(ALPHA_PROMOTION_ENFORCEMENT_STARTED_AT)
    values = [ticket.get("created_at")]
    hub_identity = ticket.get("hub_identity")
    if isinstance(hub_identity, dict):
        values.append(hub_identity.get("reserved_at"))
    valid_timestamp_seen = False
    for value in values:
        if not value:
            continue
        try:
            observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        valid_timestamp_seen = True
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if observed.astimezone(timezone.utc) >= cutoff.astimezone(timezone.utc):
            return True
    normalized = normalize_experiment_id(ticket.get("experiment_id"))
    if not normalized:
        return False
    experiment_day = normalized[4:12]
    cutoff_day = cutoff.date().strftime("%Y%m%d")
    return experiment_day > cutoff_day or (
        experiment_day == cutoff_day and not valid_timestamp_seen
    )


def _revalidate_alpha_promotion_for_claim(registry, ticket):
    anchor = ticket.get("alpha_promotion")
    private_contract_indicator = _private_replay_scout_contract_indicator(ticket)
    research_bound = (
        isinstance(anchor, dict)
        and anchor.get("admission_class") in _RESEARCH_ADMISSION_EXPECTED_GRADES
    ) or private_contract_indicator
    if research_bound and not _alpha_promotion_required_for_lane(ticket.get("lane")):
        raise ValueError(
            f"{ticket.get('experiment_id')} research/private replay cannot demote "
            f"lane to {ticket.get('lane')!r} before claim"
        )
    if not _alpha_promotion_required_for_lane(ticket.get("lane")):
        return None
    if private_contract_indicator:
        _validate_private_replay_scout_identity(ticket)
    enforced = _alpha_promotion_gate_enabled(registry)
    if not anchor:
        if enforced and _ticket_is_post_alpha_promotion_enforcement(ticket):
            raise ValueError(
                f"{ticket.get('experiment_id')} cannot be claimed: missing "
                "hash-bound outcome-blind alpha promotion proof"
            )
        return None
    repo_root = _registry_repo_root(registry) or REPO_ROOT
    if _private_replay_scout_artifact_contract_required(ticket, anchor):
        _private_replay_scout_scope_entries(
            ticket, "allowed_write_scope", Path(repo_root).resolve()
        )
        _private_replay_scout_scope_entries(
            ticket, "must_not_touch", Path(repo_root).resolve()
        )
        _validate_private_replay_scout_claim_binding(ticket)
    return _alpha_promotion_api().revalidate_ticket_promotion(
        ticket,
        repo_root=repo_root,
    )


def _build_alpha_promotion_claim_receipt(
    registry, ticket, *, claimed_validation_at=None
):
    """Snapshot claim-time research bytes when the promotion API supports v1 receipts.

    The feature check preserves isolated legacy/fake promotion APIs.  The real
    repository API always exposes the builder, so production alpha claims cannot
    silently skip receipt creation.
    """

    if not _alpha_promotion_required_for_lane(ticket.get("lane")):
        return None
    if not ticket.get("alpha_promotion"):
        return None
    api = _alpha_promotion_api()
    builder = getattr(api, "build_ticket_promotion_claim_receipt", None)
    if builder is None:
        return None
    repo_root = _registry_repo_root(registry) or REPO_ROOT
    return builder(
        ticket,
        claimed_validation_at=claimed_validation_at,
        repo_root=repo_root,
    )


def _is_never_claimed_duplicate_accounting_close(ticket, decision, realized_failure_mode):
    """True only for the non-substantive abandonment of a reservation that was
    never successfully claimed.

    A promotion-lane reservation whose claim fails *inside* claim-receipt
    construction (e.g. the receipt CAS per-file size cap) can otherwise neither
    be claimed nor closed: every closeout path demands a receipt that only a
    successful claim can produce (deadlock cases exp-20260804-002,
    exp-20260814-001). The bypass is deliberately narrow: the ticket must still
    be an unclaimed ``proposed`` reservation with no receipt, and the close must
    be pure ``duplicate_reservation_accounting`` bookkeeping with a
    rejected-flavored terminal status. Every substantive closeout (accepted,
    observed_only, or any close of a claimed ticket) stays receipt-gated.
    """

    if str(ticket.get("status") or "") != "proposed":
        return False
    if ticket.get("claimed_at"):
        return False
    if ticket.get("alpha_promotion_claim_receipt"):
        return False
    if (
        EXPERIMENT_EVER_CLAIMED_FIELD in ticket
        and ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD) is not False
    ):
        return False
    if str(realized_failure_mode or "") != "duplicate_reservation_accounting":
        return False
    return str(decision or "").startswith("rejected")


def _require_alpha_promotion_claim_receipt_for_close(
    registry, ticket, *, decision=None, realized_failure_mode=None
):
    """Block post-rollout proposed-to-terminal alpha closeout bypasses."""

    if not _alpha_promotion_required_for_lane(ticket.get("lane")):
        return
    if _is_never_claimed_duplicate_accounting_close(
        ticket, decision, realized_failure_mode
    ):
        return
    # Isolated/legacy registry users predate promotion admission and do not have
    # a repository root at which the receipt's content-addressed bytes can be
    # verified.  The production checkout (and explicit enforcement fixtures)
    # always take the guarded path.
    if not _alpha_promotion_gate_enabled(registry):
        return
    api = _alpha_promotion_api()
    required = getattr(api, "claim_receipt_required_for_ticket", None)
    if required is None:
        return
    if required(ticket) and not ticket.get("alpha_promotion_claim_receipt"):
        raise ValueError(
            f"{ticket.get('experiment_id')} cannot close without a successful "
            "claim and alpha_promotion_claim_receipt"
        )


def _research_replay_metadata(experiment):
    anchor = experiment.get("alpha_promotion")
    if not isinstance(anchor, dict):
        return None
    admission_class = anchor.get("admission_class")
    expected_grade = _RESEARCH_ADMISSION_EXPECTED_GRADES.get(admission_class)
    if expected_grade is None:
        return None
    expected = {
        "admission_class": admission_class,
        "selected_evidence_grade": expected_grade,
        "result_ceiling": RESEARCH_REPLAY_RESULT_CEILING,
        "paper_live_eligible": False,
    }
    mismatches = [
        f"{key}={anchor.get(key)!r}"
        for key, expected_value in expected.items()
        if anchor.get(key) != expected_value
    ]
    bindings = anchor.get("source_readiness_bindings")
    if not isinstance(bindings, list) or not bindings:
        mismatches.append("source_readiness_bindings=missing")
    if mismatches:
        raise ValueError(
            f"{experiment.get('experiment_id')} has an invalid research_replay "
            "admission boundary: " + ", ".join(mismatches)
        )
    return expected


def _private_replay_scout_artifact_contract_required(experiment, metadata):
    if _private_replay_scout_contract_indicator(experiment):
        _validate_private_replay_scout_identity(experiment, metadata=metadata)
    if metadata.get("admission_class") != RESEARCH_REPLAY_ADMISSION_CLASS:
        return False
    if experiment.get("change_type") != PRIVATE_REPLAY_SCOUT_CHANGE_TYPE:
        return False

    version = experiment.get(
        "private_replay_scout_artifact_disposition_contract_version"
    )
    if version is not None:
        if type(version) is not int or (
            version != PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION
        ):
            raise ValueError(
                f"{experiment.get('experiment_id')} has invalid private replay "
                f"artifact disposition contract version {version!r}"
            )
        _private_replay_scout_scope_entries(experiment, "allowed_write_scope")
        _private_replay_scout_scope_entries(experiment, "must_not_touch")
        return True

    if _private_replay_scout_post_contract_identity(experiment):
        raise ValueError(
            f"{experiment.get('experiment_id')} future private replay scout is "
            "missing private_replay_scout_artifact_disposition_contract_version"
        )
    return False


def _private_replay_scout_post_contract_identity(experiment):
    cutoff = datetime.fromisoformat(
        PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_ENFORCEMENT_STARTED_AT
    )
    timestamp_values = [
        experiment.get(field)
        for field in (
            "created_at",
            "reserved_at",
        )
    ]
    hub_identity = experiment.get("hub_identity")
    if isinstance(hub_identity, dict):
        timestamp_values.append(hub_identity.get("reserved_at"))
    post_enforcement_timestamp = False
    for value in timestamp_values:
        if value is None:
            continue
        try:
            observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if observed.tzinfo is None:
            continue
        if observed.astimezone(timezone.utc) >= cutoff.astimezone(timezone.utc):
            post_enforcement_timestamp = True
            break

    normalized_id = normalize_experiment_id(experiment.get("experiment_id"))
    experiment_day = normalized_id[4:12] if normalized_id else None
    cutoff_day = cutoff.date().strftime("%Y%m%d")
    post_enforcement_identity = (
        experiment_day is None or experiment_day >= cutoff_day
    )
    return post_enforcement_timestamp or post_enforcement_identity


def _private_replay_scout_contract_indicator(experiment):
    return (
        PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD in experiment
        or PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD in experiment
        or PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD in experiment
        or "private_replay_scout_artifact_disposition_contract_version"
        in experiment
        or (
            experiment.get("change_type") == PRIVATE_REPLAY_SCOUT_CHANGE_TYPE
            and _private_replay_scout_post_contract_identity(experiment)
        )
    )


def _validate_private_replay_scout_identity(experiment, *, metadata=None):
    experiment_id = experiment.get("experiment_id")
    if experiment.get("status") not in {
        "proposed",
        "claimed",
        "running",
        "observed_only",
        "rejected",
    }:
        raise ValueError(
            f"{experiment_id} private replay contract status must use an exact "
            f"canonical lifecycle value, got {experiment.get('status')!r}"
        )
    if experiment.get("change_type") != PRIVATE_REPLAY_SCOUT_CHANGE_TYPE:
        raise ValueError(
            f"{experiment_id} private replay contract identity requires "
            "change_type='private_replay_scout'"
        )
    anchor = experiment.get("alpha_promotion")
    admission_class = (
        metadata.get("admission_class")
        if isinstance(metadata, dict)
        else anchor.get("admission_class") if isinstance(anchor, dict) else None
    )
    if admission_class != RESEARCH_REPLAY_ADMISSION_CLASS:
        raise ValueError(
            f"{experiment_id} private replay contract identity requires "
            "alpha_promotion.admission_class='research_replay'"
        )


def _private_replay_scout_claim_binding(ticket):
    _private_replay_scout_scope_entries(ticket, "allowed_write_scope")
    _private_replay_scout_scope_entries(ticket, "must_not_touch")
    payload = {
        "schema_version": 1,
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "change_type": ticket.get("change_type"),
        "artifact_disposition_contract_version": ticket.get(
            "private_replay_scout_artifact_disposition_contract_version"
        ),
        "allowed_write_scope": list(ticket.get("allowed_write_scope")),
        "must_not_touch": list(ticket.get("must_not_touch")),
    }
    payload["binding_hash"] = _canonical_json_hash(payload)
    return payload


def _private_replay_scout_registry_identity(ticket):
    anchor = ticket.get("alpha_promotion")
    claim_binding = ticket.get(PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD)
    payload = {
        "schema_version": 1,
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "lane": ticket.get("lane"),
        "change_type": ticket.get("change_type"),
        "admission_class": (
            anchor.get("admission_class") if isinstance(anchor, dict) else None
        ),
        "artifact_disposition_contract_version": ticket.get(
            "private_replay_scout_artifact_disposition_contract_version"
        ),
        "allowed_write_scope": ticket.get("allowed_write_scope"),
        "must_not_touch": ticket.get("must_not_touch"),
        "claim_binding_hash": (
            claim_binding.get("binding_hash")
            if isinstance(claim_binding, dict)
            else None
        ),
    }
    payload["identity_hash"] = _canonical_json_hash(payload)
    return payload


def _private_replay_scout_registry_identity_is_valid(value):
    if not isinstance(value, dict):
        return False
    payload = {key: item for key, item in value.items() if key != "identity_hash"}
    return (
        value.get("schema_version") == 1
        and value.get("identity_hash") == _canonical_json_hash(payload)
    )


def _experiment_id_sequence(experiment_id):
    normalized = normalize_experiment_id(experiment_id)
    if not normalized:
        return None
    match = re.fullmatch(r"exp-(\d{8})-(\d+)", normalized)
    if match is None:
        return None
    return match.group(1), int(match.group(2))


def _experiment_reservation_identity_required(ticket):
    if not isinstance(ticket, dict):
        return False
    if any(
        field in ticket
        for field in (
            EXPERIMENT_RESERVATION_IDENTITY_FIELD,
            EXPERIMENT_EVER_CLAIMED_FIELD,
            EXPERIMENT_CLAIM_TRANSITION_FIELD,
            EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD,
            EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD,
        )
    ):
        return True
    current = _experiment_id_sequence(ticket.get("experiment_id"))
    minimum = _experiment_id_sequence(EXPERIMENT_RESERVATION_IDENTITY_MIN_ID)
    if current is not None and minimum is not None and current >= minimum:
        return True
    cutoff = datetime.fromisoformat(
        EXPERIMENT_RESERVATION_IDENTITY_ENFORCEMENT_STARTED_AT
    )
    for value in (
        ticket.get("created_at"),
        (ticket.get("hub_identity") or {}).get("reserved_at"),
    ):
        try:
            observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if observed.astimezone(timezone.utc) >= cutoff:
            return True
    return False


def _experiment_reservation_clock_invalid(ticket):
    if not isinstance(ticket, dict):
        return False
    for value in (
        ticket.get("created_at"),
        (ticket.get("hub_identity") or {}).get("reserved_at"),
    ):
        if value in (None, ""):
            continue
        try:
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return True
    return False


def experiment_reservation_identity_required(ticket):
    """Public predicate for CLI callers governed by the rollout contract."""

    return _experiment_reservation_identity_required(ticket)


def _experiment_reservation_identity(ticket):
    payload = {
        "schema_version": 1,
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "created_at": ticket.get("created_at"),
        "lane": ticket.get("lane"),
        "change_type": ticket.get("change_type"),
        "hypothesis": ticket.get("hypothesis"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "allowed_write_scope": ticket.get("allowed_write_scope"),
        "must_not_touch": ticket.get("must_not_touch"),
        "ticket_file": ticket.get("ticket_file"),
        "revision_manifest_file": ticket.get("revision_manifest_file"),
    }
    payload["identity_hash"] = _canonical_json_hash(payload)
    return payload


def _experiment_reservation_identity_is_valid(value):
    if not isinstance(value, dict):
        return False
    payload = {key: item for key, item in value.items() if key != "identity_hash"}
    return (
        value.get("schema_version") == 1
        and value.get("identity_hash") == _canonical_json_hash(payload)
    )


def _build_experiment_claim_transition(ticket, *, force):
    receipt = ticket.get("alpha_promotion_claim_receipt")
    claim_binding = ticket.get(PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD)
    payload = {
        "schema_version": 1,
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "reservation_identity_hash": _experiment_reservation_identity(ticket).get(
            "identity_hash"
        ),
        "owner": ticket.get("owner"),
        "claimed_at": ticket.get("claimed_at"),
        "force": bool(force),
        "alpha_promotion_claim_receipt_hash": (
            _canonical_json_hash(receipt) if isinstance(receipt, dict) else None
        ),
        "private_replay_claim_binding_hash": (
            claim_binding.get("binding_hash")
            if isinstance(claim_binding, dict)
            else None
        ),
    }
    payload["transition_hash"] = _canonical_json_hash(payload)
    return payload


def _experiment_claim_transition_is_valid(value, ticket):
    if not _experiment_claim_transition_payload_is_valid(value):
        return False
    return value == _build_experiment_claim_transition(
        ticket,
        force=value["force"],
    )


def _experiment_claim_transition_payload_is_valid(value):
    if not isinstance(value, dict) or type(value.get("force")) is not bool:
        return False
    payload = {key: item for key, item in value.items() if key != "transition_hash"}
    return (
        value.get("schema_version") == 1
        and value.get("transition_hash") == _canonical_json_hash(payload)
    )


def _validate_experiment_claim_lifecycle(ticket):
    if not _experiment_reservation_identity_required(ticket):
        return
    ever_claimed = ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD)
    if type(ever_claimed) is not bool:
        raise ValueError(
            f"{ticket.get('experiment_id')} requires an exact boolean "
            f"{EXPERIMENT_EVER_CLAIMED_FIELD}"
        )
    status = ticket.get("status")
    if status not in ({"proposed"} | ACTIVE_STATUSES | FINAL_STATUSES):
        raise ValueError(
            f"{ticket.get('experiment_id')} lifecycle status must use an exact "
            "canonical lifecycle value"
        )
    if status == "proposed" and ever_claimed:
        raise ValueError(
            f"{ticket.get('experiment_id')} cannot roll an ever-claimed ticket "
            "back to proposed"
        )
    if status in ACTIVE_STATUSES and not ever_claimed:
        raise ValueError(
            f"{ticket.get('experiment_id')} active ticket must retain its "
            "ever-claimed lifecycle marker"
        )
    if ever_claimed:
        claimed_at = ticket.get("claimed_at")
        try:
            parsed_claimed_at = datetime.fromisoformat(
                str(claimed_at).replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            parsed_claimed_at = None
        if parsed_claimed_at is None or parsed_claimed_at.tzinfo is None:
            raise ValueError(
                f"{ticket.get('experiment_id')} ever-claimed ticket requires "
                "an exact timezone-aware claimed_at"
            )
    if ever_claimed and not _experiment_claim_transition_is_valid(
        ticket.get(EXPERIMENT_CLAIM_TRANSITION_FIELD), ticket
    ):
        raise ValueError(
            f"{ticket.get('experiment_id')} ever-claimed ticket requires its "
            "valid hash-bound claim transition"
        )
    if status in FINAL_STATUSES and not ever_claimed:
        result = ticket.get("result") or {}
        calibration = result.get("calibration") or {}
        failure_mode = result.get("realized_failure_mode") or calibration.get(
            "realized_failure_mode"
        )
        if failure_mode != "duplicate_reservation_accounting":
            raise ValueError(
                f"{ticket.get('experiment_id')} terminal ticket without a claim "
                "must be duplicate-reservation accounting only"
            )


def _validate_private_replay_scout_claim_binding(ticket):
    expected = _private_replay_scout_claim_binding(ticket)
    actual = ticket.get(PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD)
    if actual != expected:
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay claim binding for "
            "change_type/allowed_write_scope/must_not_touch/contract version "
            "is missing or does not match claim-time identity"
        )
    return actual


def _private_replay_scout_scope_entries(experiment, field_name, root=None):
    raw_entries = experiment.get(field_name)
    if not isinstance(raw_entries, list):
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay {field_name} "
            "must be a list of non-empty repository-relative strings"
        )
    if root is None:
        # Claim/audit marker validation needs the shape check even before a
        # repository root is available. Artifact validation below resolves the
        # same frozen entries against its explicit workspace root.
        for raw_entry in raw_entries:
            if type(raw_entry) is not str or not raw_entry.strip():
                raise ValueError(
                    f"{experiment.get('experiment_id')} private replay {field_name} "
                    "must contain only non-empty strings"
                )
        return None

    entries = []
    for raw_entry in raw_entries:
        if type(raw_entry) is not str or not raw_entry.strip():
            raise ValueError(
                f"{experiment.get('experiment_id')} private replay {field_name} "
                "must contain only non-empty strings"
            )
        normalized_raw = raw_entry.strip().replace("\\", "/")
        is_directory = normalized_raw.endswith("/")
        source = Path(raw_entry.strip())
        candidate = source if source.is_absolute() else root / source
        try:
            relative = candidate.resolve().relative_to(root).as_posix().rstrip("/")
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"{experiment.get('experiment_id')} private replay {field_name} "
                f"entry {raw_entry!r} must resolve inside the repository"
            ) from exc
        if not relative:
            raise ValueError(
                f"{experiment.get('experiment_id')} private replay {field_name} "
                "cannot grant the repository root"
            )
        entries.append((os.path.normcase(relative), is_directory))
    return entries


def _private_replay_scout_artifact_in_scope(experiment, relative_path, root):
    relative = os.path.normcase(
        str(relative_path).replace("\\", "/").strip("/")
    )

    allowed = _private_replay_scout_scope_entries(
        experiment, "allowed_write_scope", root
    )
    if not any(
        relative == scope or (is_directory and relative.startswith(scope + os.sep))
        for scope, is_directory in allowed
    ):
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact path "
            f"{relative_path!r} is outside allowed_write_scope"
        )

    forbidden = _private_replay_scout_scope_entries(
        experiment, "must_not_touch", root
    )
    if any(
        relative == scope or (is_directory and relative.startswith(scope + os.sep))
        for scope, is_directory in forbidden
    ):
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact path "
            f"{relative_path!r} is protected by must_not_touch"
        )


def _resolve_private_replay_scout_artifact(
    experiment,
    decision,
    *,
    result=None,
    artifact_path=None,
    artifact_sha256=None,
    repo_root=None,
):
    root = Path(repo_root or REPO_ROOT).resolve()
    binding_from_result = artifact_path is None
    locator = artifact_path
    expected_sha256 = artifact_sha256
    if isinstance(result, dict):
        locator = locator or result.get("artifact")
        expected_sha256 = expected_sha256 or result.get("artifact_sha256")
    if not isinstance(locator, (str, os.PathLike)) or not str(locator).strip():
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay closeout requires "
            "a result artifact path"
        )
    if binding_from_result and expected_sha256 is None:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay closeout requires "
            "result artifact_sha256"
        )

    source = Path(locator)
    candidate = source if source.is_absolute() else root / source
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact path must "
            "resolve to a file inside the repository"
        ) from exc
    if not resolved.is_file():
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact path is not a file"
        )
    _private_replay_scout_artifact_in_scope(experiment, relative, root)

    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact could not be read"
        ) from exc
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        if (
            not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            or expected_sha256 != actual_sha256
        ):
            raise ValueError(
                f"{experiment.get('experiment_id')} private replay artifact_sha256 mismatch"
            )
    try:
        artifact = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact must be valid JSON"
        ) from exc
    if not isinstance(artifact, dict):
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact must be a JSON object"
        )

    expected_identity = {
        "experiment_id": experiment.get("experiment_id"),
        "record_type": PRIVATE_REPLAY_SCOUT_ARTIFACT_RECORD_TYPE,
        "status": decision,
        "decision": decision,
    }
    identity_mismatches = [
        f"{key}={artifact.get(key)!r}"
        for key, expected in expected_identity.items()
        if artifact.get(key) != expected
    ]
    if identity_mismatches:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact identity mismatch: "
            + ", ".join(identity_mismatches)
        )

    disposition = artifact.get("disposition")
    allowed = PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITIONS[decision]
    if not isinstance(disposition, str) or disposition not in allowed:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact disposition "
            f"{disposition!r} is invalid for status {decision!r}"
        )
    evidence_invalid = artifact.get("evidence_invalid")
    expected_evidence_invalid = disposition == "invalid_contaminated"
    if evidence_invalid is not expected_evidence_invalid:
        raise ValueError(
            f"{experiment.get('experiment_id')} private replay artifact disposition "
            f"{disposition!r} requires evidence_invalid={str(expected_evidence_invalid).lower()}"
        )
    _reject_nested_research_replay_authority(
        experiment.get("experiment_id"), artifact, "artifact"
    )
    return {
        "artifact": relative,
        "artifact_sha256": actual_sha256,
        "artifact_disposition": disposition,
        "evidence_invalid": evidence_invalid,
    }


def _enforce_research_replay_result_ceiling(
    experiment,
    decision,
    result=None,
    *,
    artifact_path=None,
    artifact_sha256=None,
    repo_root=None,
):
    """Prevent a research replay from acquiring paper/live authority.

    Only the two terminal registry dispositions permitted by the policy are
    accepted.  This deliberately rejects every ``accepted_*`` spelling and
    paper/live verdict even if a caller bypasses ``final_decision`` and writes
    a custom result object through the self-registration API.
    """

    private_contract_indicator = _private_replay_scout_contract_indicator(experiment)
    metadata = _research_replay_metadata(experiment)
    if private_contract_indicator:
        _validate_private_replay_scout_identity(experiment, metadata=metadata)
    if metadata is None:
        return None
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in RESEARCH_REPLAY_FINAL_STATUSES:
        raise ValueError(
            f"{experiment.get('experiment_id')} research_replay has "
            f"result_ceiling={RESEARCH_REPLAY_RESULT_CEILING}; cannot close as "
            f"{decision!r}. Only observed_only or rejected is permitted"
        )
    if isinstance(result, dict):
        for field_name in ("decision", "status"):
            value = result.get(field_name)
            if value is None:
                continue
            normalized = str(value).strip().lower()
            if normalized not in RESEARCH_REPLAY_FINAL_STATUSES:
                raise ValueError(
                    f"{experiment.get('experiment_id')} research_replay result "
                    f"cannot record {field_name}={value!r} above its observed_only ceiling"
                )
        verdict = result.get("verdict")
        if verdict is not None and str(verdict).strip().lower() not in {
            "research_only",
            "reject",
            "rejected",
            "observed_only",
        }:
            raise ValueError(
                f"{experiment.get('experiment_id')} research_replay cannot record "
                f"paper/live verdict {verdict!r}"
            )
        for field_name in ("paper_live_eligible", "live_ready", "live_eligible"):
            if (
                field_name in result
                and result[field_name] is not False
                and result[field_name] is not None
            ):
                raise ValueError(
                    f"{experiment.get('experiment_id')} research_replay requires "
                    f"{field_name}=false"
                )
        _reject_nested_research_replay_authority(
            experiment.get("experiment_id"), result
        )
    contract_required = _private_replay_scout_artifact_contract_required(
        experiment, metadata
    )
    if contract_required:
        _validate_private_replay_scout_claim_binding(experiment)
        if not isinstance(decision, str) or decision != normalized_decision:
            raise ValueError(
                f"{experiment.get('experiment_id')} private replay closeout status "
                f"must use canonical {normalized_decision!r}, got {decision!r}"
            )
        if isinstance(result, dict):
            if result.get("decision") != normalized_decision:
                raise ValueError(
                    f"{experiment.get('experiment_id')} private replay result "
                    f"decision must equal terminal status {normalized_decision!r}"
                )
            for field_name in ("decision", "status"):
                if field_name in result and result[field_name] != normalized_decision:
                    raise ValueError(
                        f"{experiment.get('experiment_id')} private replay result "
                        f"{field_name} must equal terminal status {normalized_decision!r}"
                    )
        artifact_metadata = _resolve_private_replay_scout_artifact(
            experiment,
            normalized_decision,
            result=result,
            artifact_path=artifact_path,
            artifact_sha256=artifact_sha256,
            repo_root=repo_root,
        )
        if isinstance(result, dict):
            for field_name, expected in artifact_metadata.items():
                if field_name not in result:
                    continue
                actual = result[field_name]
                mismatch = (
                    actual is not expected
                    if field_name == "evidence_invalid"
                    else actual != expected
                )
                if mismatch:
                    raise ValueError(
                        f"{experiment.get('experiment_id')} private replay result "
                        f"{field_name} does not match the bound artifact"
                    )
        metadata.update(artifact_metadata)
    return metadata


_PRIVATE_REPLAY_SCOUT_BINDING_FIELDS = (
    "artifact",
    "artifact_sha256",
    "artifact_disposition",
    "evidence_invalid",
)

_PRIVATE_REPLAY_SCOUT_LOG_MIRROR_FIELDS = (
    "change_type",
    "alpha_promotion",
    "research_refs",
)

_PRIVATE_REPLAY_SCOUT_COMMITTED_LOG_MIRROR_FIELDS = (
    "experiment_uid",
    "private_replay_scout_artifact_disposition_contract_version",
    PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD,
)


def _private_replay_scout_log_sha256(row):
    """Hash exactly the compact row that canonical log persistence writes."""

    return _canonical_json_hash(strip_oversized_fields(row))


def _validate_private_replay_scout_log_draft_inputs(
    ticket,
    log_draft,
    judgement,
    before_path,
    after_path,
    repo_root,
):
    """Bind the committed draft to this exact close calculation.

    Presentation fields such as notes/reflection remain caller-authored, but
    identity, frozen design, paths, metrics, and calibration must be the values
    derived from the ticket and this judgement.
    """

    result = ticket.get("result") or {}
    expected = {
        "experiment_id": ticket.get("experiment_id"),
        "status": ticket.get("status"),
        "decision": ticket.get("status"),
        "hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components") or [],
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "research_refs": ticket.get("research_refs") or [],
        "alpha_promotion": ticket.get("alpha_promotion"),
        "component": ", ".join(ticket.get("allowed_write_scope") or []),
        "parameters": {
            "single_causal_variable": ticket.get("single_causal_variable"),
            "locked_variables": ticket.get("locked_variables") or [],
        },
        "date_range": (ticket.get("evaluation_windows") or [{}])[0],
        "secondary_windows": (ticket.get("evaluation_windows") or [])[1:],
        "before_metrics": judgement.get("before_metrics"),
        "after_metrics": judgement.get("after_metrics"),
        "delta_metrics": judgement.get("delta_metrics"),
        "related_files": [
            _repo_relative(before_path, repo_root),
            _repo_relative(after_path, repo_root),
        ],
    }
    prediction = normalize_prediction(ticket.get("prediction"))
    if prediction:
        expected["prediction"] = prediction
        expected["calibration"] = result.get("calibration")
    mismatches = [
        field_name
        for field_name, expected_value in expected.items()
        if log_draft.get(field_name) != expected_value
    ]
    if mismatches:
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay canonical log draft "
            "does not match authoritative close inputs: " + ", ".join(mismatches)
        )


def _row_declares_private_replay_scout_contract(row):
    if not isinstance(row, dict):
        return False
    anchor = row.get("alpha_promotion")
    admission_class = row.get("admission_class")
    if admission_class is None and isinstance(anchor, dict):
        admission_class = anchor.get("admission_class")
    return (
        row.get("change_type") == PRIVATE_REPLAY_SCOUT_CHANGE_TYPE
        and admission_class == RESEARCH_REPLAY_ADMISSION_CLASS
    )


def _private_replay_scout_binding_mismatch(left, right, field_name):
    if field_name == "evidence_invalid":
        return left is not right
    return left != right


def _validate_private_replay_scout_ticket_log_binding(ticket, log_row, repo_root):
    if log_row.get("experiment_id") != ticket.get("experiment_id"):
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay ticket/log "
            "experiment_id binding mismatch"
        )
    metadata = _research_replay_metadata(ticket)
    if metadata is None or not _private_replay_scout_artifact_contract_required(
        ticket, metadata
    ):
        return False

    ticket_status = ticket.get("status")
    if not _closed_status(ticket_status):
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay log requires a terminal ticket"
        )
    ticket_result = ticket.get("result")
    if not isinstance(ticket_result, dict):
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay terminal ticket requires result"
        )

    ticket_metadata = _enforce_research_replay_result_ceiling(
        ticket,
        ticket_status,
        result=ticket_result,
        repo_root=repo_root,
    )
    log_status = log_row.get("status") if isinstance(log_row, dict) else None
    log_decision = log_row.get("decision") if isinstance(log_row, dict) else None
    if log_status != ticket_status or log_decision != ticket_status:
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay log status and decision "
            "must equal the terminal ticket status"
        )
    log_metadata = _enforce_research_replay_result_ceiling(
        ticket,
        log_status,
        result=log_row,
        repo_root=repo_root,
    )

    if ticket_result.get("decision") != ticket_status:
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay ticket result decision "
            "must equal the terminal ticket status"
        )
    committed_sha256 = ticket_result.get(PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD)
    if (
        not isinstance(committed_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", committed_sha256) is None
    ):
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay terminal ticket "
            "requires an exact canonical log payload commitment"
        )
    mirror_fields = _PRIVATE_REPLAY_SCOUT_LOG_MIRROR_FIELDS
    mirror_fields += _PRIVATE_REPLAY_SCOUT_COMMITTED_LOG_MIRROR_FIELDS
    for field_name in mirror_fields:
        log_value = log_row.get(field_name)
        ticket_value = ticket.get(field_name)
        if field_name == "research_refs":
            log_value = log_value or []
            ticket_value = ticket_value or []
        if log_value != ticket_value:
            raise ValueError(
                f"{ticket.get('experiment_id')} private replay ticket/log "
                f"{field_name} binding mismatch"
            )
    for field_name in _PRIVATE_REPLAY_SCOUT_BINDING_FIELDS:
        ticket_value = ticket_result.get(field_name)
        log_value = log_row.get(field_name)
        expected_ticket_value = ticket_metadata.get(field_name)
        expected_log_value = log_metadata.get(field_name)
        if _private_replay_scout_binding_mismatch(
            ticket_value, expected_ticket_value, field_name
        ):
            raise ValueError(
                f"{ticket.get('experiment_id')} private replay ticket {field_name} "
                "does not match the bound artifact"
            )
        if _private_replay_scout_binding_mismatch(
            log_value, expected_log_value, field_name
        ):
            raise ValueError(
                f"{ticket.get('experiment_id')} private replay log {field_name} "
                "does not match the bound artifact"
            )
        if _private_replay_scout_binding_mismatch(
            ticket_value, log_value, field_name
        ):
            raise ValueError(
                f"{ticket.get('experiment_id')} private replay ticket/log "
                f"{field_name} binding mismatch"
            )
    if committed_sha256 != _private_replay_scout_log_sha256(log_row):
        raise ValueError(
            f"{ticket.get('experiment_id')} private replay canonical log "
            "does not match the terminal ticket payload commitment"
        )
    return True


def _validate_post_rollout_ticket_log_mirror(ticket, log_row):
    """Prevent a log shard from granting terminal authority before the ticket."""

    if not _experiment_reservation_identity_required(ticket):
        return False
    ticket_status = ticket.get("status")
    if ticket_status not in FINAL_STATUSES:
        raise ValueError(
            f"{ticket.get('experiment_id')} post-rollout log requires an exact "
            "terminal canonical ticket"
        )
    ticket_result = ticket.get("result")
    if (
        not isinstance(ticket_result, dict)
        or ticket_result.get("decision") != ticket_status
    ):
        raise ValueError(
            f"{ticket.get('experiment_id')} post-rollout terminal ticket result "
            "decision must mirror its status"
        )
    if (
        not isinstance(log_row, dict)
        or log_row.get("experiment_id") != ticket.get("experiment_id")
        or log_row.get("status") != ticket_status
        or log_row.get("decision") != ticket_status
    ):
        raise ValueError(
            f"{ticket.get('experiment_id')} post-rollout log experiment_id, "
            "status, and decision must mirror the terminal ticket"
        )
    return True


def _bind_post_rollout_closeout_log_intent(ticket, log_row):
    """Make the exact future canonical shard recoverable from the ticket.

    The ticket is the first durable terminal source.  Persisting the compact
    canonical row and its hash in that same write means a later shard/cache I/O
    failure can be repaired by experiment id without rebuilding volatile fields
    such as the log timestamp.
    """

    if not _experiment_reservation_identity_required(ticket):
        return strip_oversized_fields(log_row)
    canonical_row = strip_oversized_fields(log_row)
    _validate_post_rollout_ticket_log_mirror(ticket, canonical_row)
    ticket[EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD] = canonical_row
    ticket[EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD] = _canonical_json_hash(
        canonical_row
    )
    return canonical_row


def _validated_post_rollout_closeout_log_intent(ticket, repo_root):
    """Return the exact hash-bound future shard carried by a terminal ticket."""

    if not _experiment_reservation_identity_required(ticket):
        return None
    experiment_id = ticket.get("experiment_id")
    row = ticket.get(EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD)
    committed_hash = ticket.get(
        EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD
    )
    if not isinstance(row, dict) or not isinstance(committed_hash, str):
        raise ValueError(
            f"{experiment_id} post-rollout terminal ticket requires its exact "
            "canonical log intent"
        )
    if committed_hash != _canonical_json_hash(row):
        raise ValueError(
            f"{experiment_id} post-rollout canonical log intent hash mismatch"
        )
    _validate_post_rollout_ticket_log_mirror(ticket, row)
    if _private_replay_scout_contract_indicator(ticket):
        _validate_private_replay_scout_ticket_log_binding(
            ticket, row, repo_root
        )
    return row


def _validate_terminal_close_retry_inputs(
    ticket,
    judgement,
    before_path,
    after_path,
    *,
    status_override,
    realized_failure_mode,
    repo_root,
):
    """Require a terminal repair request to describe the committed close."""

    experiment_id = ticket.get("experiment_id")
    result = ticket.get("result")
    if not isinstance(result, dict):
        raise ValueError(f"{experiment_id} terminal repair requires result")
    requested_decision = final_decision(
        judgement,
        status_override,
        experiment=ticket,
    )
    expected = {
        "decision": requested_decision,
        "before_result_file": _repo_relative(before_path, repo_root),
        "after_result_file": _repo_relative(after_path, repo_root),
        "delta_metrics": judgement.get("delta_metrics") or {},
    }
    if realized_failure_mode is not None:
        expected["realized_failure_mode"] = realized_failure_mode
    mismatches = [
        field_name
        for field_name, expected_value in expected.items()
        if result.get(field_name) != expected_value
    ]
    if ticket.get("status") != requested_decision or mismatches:
        details = ", ".join(mismatches) or "status"
        raise ValueError(
            f"{experiment_id} terminal results are immutable; repair request "
            f"does not match {details}"
        )


def _validate_experiment_log_row_for_persistence(
    row, logs_root, *, registry_path=None
):
    experiment_id = row.get("experiment_id") if isinstance(row, dict) else None
    _require_canonical_experiment_id(experiment_id, field_name="log experiment_id")
    logs_root = Path(logs_root).resolve()
    repo_root = logs_root.parent.parent
    ticket = load_ticket(experiment_id, logs_root.parent / "tickets")
    if ticket is None:
        if _row_declares_private_replay_scout_contract(row):
            raise ValueError(
                f"{experiment_id} private replay log requires its canonical ticket"
            )
        return None

    if _experiment_reservation_identity_required(ticket):
        resolved_registry_path = (
            Path(registry_path)
            if registry_path is not None
            else repo_root / "docs" / "experiment_registry.json"
        )
        if not resolved_registry_path.exists():
            raise ValueError(
                f"{experiment_id} log persistence requires the selected "
                "registry path for reservation-anchor validation"
            )
        _validate_file_backed_reservation_anchors(
            resolved_registry_path, ticket
        )
        _validate_post_rollout_ticket_log_mirror(ticket, row)
        committed_row = _validated_post_rollout_closeout_log_intent(
            ticket, repo_root
        )
        if strip_oversized_fields(row) != committed_row:
            raise ValueError(
                f"{experiment_id} canonical log payload commitment does not "
                "match the exact terminal closeout intent"
            )

    private_contract_indicator = _private_replay_scout_contract_indicator(ticket)
    if private_contract_indicator:
        _validate_private_replay_scout_identity(ticket)
        _validate_private_replay_scout_claim_binding(ticket)
    metadata = _research_replay_metadata(ticket)
    if metadata is None:
        if private_contract_indicator:
            raise ValueError(
                f"{experiment_id} future private replay log requires a "
                "research-bound alpha_promotion anchor"
            )
        return ticket
    if _private_replay_scout_artifact_contract_required(ticket, metadata):
        _validate_private_replay_scout_ticket_log_binding(ticket, row, repo_root)
    else:
        _enforce_research_replay_result_ceiling(
            ticket,
            row.get("status") or row.get("decision"),
            result=row,
            repo_root=repo_root,
        )
    return ticket


def _reject_nested_research_replay_authority(experiment_id, value, path="result"):
    """Reject paper/live authority hidden inside nested runner artifacts."""

    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key).strip().lower()
            item_path = f"{path}.{raw_key}"
            if key in {
                "paper_live_eligible",
                "paper_eligible",
                "live_ready",
                "live_eligible",
                "trade_enabled",
                "orders_enabled",
            } and item is not False and item is not None:
                raise ValueError(
                    f"{experiment_id} research_replay cannot persist "
                    f"{item_path}=true"
                )
            if key in {
                "decision",
                "status",
                "verdict",
                "full_stack_verdict",
                "final_decision",
                "disposition",
            } and isinstance(item, str):
                normalized = item.strip().lower()
                if (
                    normalized == "accepted"
                    or normalized.startswith("accepted_")
                    or normalized
                    in {
                        "live_eligible",
                        "paper_eligible",
                        "paper_live_eligible",
                    }
                ):
                    raise ValueError(
                        f"{experiment_id} research_replay cannot persist "
                        f"{item_path}={item!r}"
                    )
            _reject_nested_research_replay_authority(
                experiment_id, item, item_path
            )
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_nested_research_replay_authority(
                experiment_id, item, f"{path}[{index}]"
            )


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_experiment_uid():
    return f"expuid-{uuid.uuid4().hex[:16]}"


def normalize_experiment_id(value):
    if value is None:
        return None
    match = EXPERIMENT_ID_RE.search(str(value))
    if not match:
        return None
    date, sequence = match.groups()
    return f"exp-{date}-{int(sequence):03d}"


def _require_canonical_experiment_id(value, *, field_name="experiment_id"):
    if type(value) is not str or normalize_experiment_id(value) != value:
        raise ValueError(
            f"{field_name} must be an exact canonical exp-YYYYMMDD-NNN string, "
            f"got {value!r}"
        )
    return value


def _repo_relative(path, repo_root=None):
    p = Path(path)
    if p.is_absolute():
        try:
            root = Path(repo_root or REPO_ROOT).resolve()
            return p.resolve().relative_to(root).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix()


def load_registry(path=DEFAULT_REGISTRY):
    path = Path(path)
    if not path.exists():
        return {"schema_version": 1, "updated_at": None, "experiments": []}
    with path.open(encoding="utf-8-sig") as f:
        data = json.load(f)
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", None)
    data.setdefault("experiments", [])
    return data


def registry_workspace_root(registry_path):
    """Derive the workspace root for both docs/ and flat registry layouts."""
    path = Path(registry_path).resolve()
    return path.parent.parent if path.parent.name == "docs" else path.parent


def _atomic_write_text(text, path):
    """Write text via same-directory temp file + atomic os.replace.

    Closes the corruption window where an unlocked reader sees a truncated or
    stale-tailed file, and where a shorter rewrite leaves an older file's
    trailing bytes (bug audit #9).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as f:
            tmp = f.name
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, path)
        except PermissionError:
            if os.name != "nt":
                raise
            with path.open("w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def save_registry(registry, path=DEFAULT_REGISTRY):
    path = Path(path)
    registry["updated_at"] = utc_now_iso()
    persisted = {k: v for k, v in registry.items() if not k.startswith("_")}
    _atomic_write_text(
        json.dumps(persisted, indent=2, ensure_ascii=False) + "\n", path)


def ticket_path(experiment_id, tickets_dir=DEFAULT_TICKETS_DIR):
    _require_canonical_experiment_id(experiment_id)
    return Path(tickets_dir) / f"{experiment_id}.json"


def experiment_log_path(experiment_id, logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR):
    _require_canonical_experiment_id(experiment_id)
    return Path(logs_dir) / f"{experiment_id}.json"


def experiment_card_path(experiment_id, cards_dir=DEFAULT_CARDS_DIR):
    return Path(cards_dir) / f"{experiment_id}.md"


def revision_manifest_path(experiment_id, manifests_dir=DEFAULT_MANIFESTS_DIR):
    return Path(manifests_dir) / f"{experiment_id}.json"


def save_ticket(ticket, tickets_dir=DEFAULT_TICKETS_DIR, *, overwrite=True):
    path = ticket_path(ticket["experiment_id"], tickets_dir)
    text = json.dumps(ticket, indent=2, ensure_ascii=False) + "\n"
    if not overwrite:
        # Atomic exclusive create (registry-decontention step 0): the ticket
        # file's existence IS the reservation. O_EXCL closes the check-then-write
        # TOCTOU race where two concurrent reservers both pass an exists() check
        # and clobber each other. We write straight to the final path (no
        # same-dir .tmp), so a hard-kill mid-write leaves at most a short ticket
        # at a known id -- never an orphaned `.<id>.json.<rand>.tmp`. Raises
        # FileExistsError if the id is already taken, preserving the prior
        # overwrite=False contract.
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        return path
    _atomic_write_text(text, path)
    return path


def _registry_tickets_dir(registry):
    return Path(registry.get("_tickets_dir", DEFAULT_TICKETS_DIR))


def _registry_logs_dir(registry):
    return Path(registry.get("_logs_dir", DEFAULT_EXPERIMENT_LOGS_DIR))


def _registry_cards_dir(registry):
    if registry.get("_cards_dir"):
        return Path(registry["_cards_dir"])
    if registry.get("_tickets_dir"):
        return Path(registry["_tickets_dir"]).parent / "cards"
    return DEFAULT_CARDS_DIR


def _registry_manifests_dir(registry):
    if registry.get("_manifests_dir"):
        return Path(registry["_manifests_dir"])
    if registry.get("_tickets_dir"):
        return Path(registry["_tickets_dir"]).parent / "manifests"
    return DEFAULT_MANIFESTS_DIR


def _registry_repo_root(registry):
    value = registry.get("_repo_root")
    return Path(value) if value else None


def load_ticket(experiment_id, tickets_dir=DEFAULT_TICKETS_DIR):
    path = ticket_path(experiment_id, tickets_dir)
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def reservation_intents_dir(registry):
    if registry.get("_tickets_dir"):
        return Path(registry["_tickets_dir"]).parent / "reservation_intents"
    return DEFAULT_EXPERIMENTS_DIR / "reservation_intents"


def _canonical_json_hash(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compact_canonical_json_hash(value):
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reservation_intent_payload(ticket_kwargs):
    """Return the stable reservation identity for retry/concurrency de-duping.

    This key intentionally excludes the eventual experiment id and volatile
    timestamps. It is stricter than the fuzzy in-flight duplicate guard: only an
    effectively identical reserve request maps to the same intent.
    """
    keys = (
        "lane",
        "hypothesis",
        "change_type",
        "single_causal_variable",
        "causal_components",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "baseline_result_file",
        "allowed_write_scope",
        "must_not_touch",
        "locked_variables",
        "evaluation_windows",
        "acceptance_rule",
        "file_slug",
        "exclusive_scope_ok",
        "promotion_request",
    )
    payload = {key: ticket_kwargs.get(key) for key in keys if key in ticket_kwargs}
    prediction = normalize_prediction(ticket_kwargs.get("prediction"))
    if prediction:
        prediction = dict(prediction)
        prediction.pop("recorded_at", None)
        payload["prediction"] = prediction
    return payload


def reservation_intent_for(ticket_kwargs):
    payload = _reservation_intent_payload(ticket_kwargs)
    key = _canonical_json_hash(payload)
    manifest = {
        "schema_version": 1,
        "key": key,
        "payload_hash": key,
        "payload": payload,
    }
    return manifest


def reservation_intent_path(registry, intent):
    return reservation_intents_dir(registry) / f"{intent['key']}.json"


def _ticket_matches_reservation_intent(ticket, intent_key):
    return (ticket.get("reservation_intent") or {}).get("key") == intent_key


def _open_ticket_for_reservation_intent(registry, intent):
    intent_key = intent["key"]
    tickets_dir = _registry_tickets_dir(registry)
    path = reservation_intent_path(registry, intent)
    payload = _load_json_file(path)
    experiment_id = payload.get("experiment_id") if isinstance(payload, dict) else None
    if experiment_id:
        ticket = load_ticket(experiment_id, tickets_dir)
        if (
            isinstance(ticket, dict)
            and ticket.get("status") in RESERVATION_INTENT_OPEN_STATUSES
            and _ticket_matches_reservation_intent(ticket, intent_key)
        ):
            return ticket

    if tickets_dir.exists():
        for ticket_path_candidate in sorted(tickets_dir.glob("exp-*.json")):
            ticket = _load_json_file(ticket_path_candidate)
            if not isinstance(ticket, dict):
                continue
            if ticket.get("status") not in RESERVATION_INTENT_OPEN_STATUSES:
                continue
            if _ticket_matches_reservation_intent(ticket, intent_key):
                return ticket
    return None


def save_reservation_intent(registry, intent, ticket):
    path = reservation_intent_path(registry, intent)
    payload = {
        "schema_version": 1,
        "key": intent["key"],
        "payload_hash": intent["payload_hash"],
        "experiment_id": ticket["experiment_id"],
        "experiment_uid": ticket.get("experiment_uid"),
        "status_at_write": ticket.get("status"),
        "ticket_file": ticket.get("ticket_file"),
        "created_at": utc_now_iso(),
    }
    _atomic_write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        path,
    )
    return path


def _ticket_index_entry(ticket, tickets_dir=DEFAULT_TICKETS_DIR):
    tickets_dir = Path(tickets_dir).resolve()
    workspace_root = tickets_dir.parent.parent
    canonical_ticket_path = ticket_path(ticket["experiment_id"], tickets_dir)
    index_ticket_file = (
        _repo_relative(canonical_ticket_path, workspace_root)
        if workspace_root.resolve() == REPO_ROOT.resolve()
        else canonical_ticket_path.resolve().as_posix()
    )
    entry = {
        "experiment_id": ticket.get("experiment_id"),
        "status": ticket.get("status"),
        "lane": ticket.get("lane"),
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": index_ticket_file,
        "card_file": ticket.get("card_file"),
        "revision_manifest_file": ticket.get("revision_manifest_file"),
        "updated_at": utc_now_iso(),
    }
    if _experiment_reservation_identity_required(ticket):
        _validate_experiment_claim_lifecycle(ticket)
        entry[EXPERIMENT_RESERVATION_IDENTITY_FIELD] = (
            _experiment_reservation_identity(ticket)
        )
        entry[EXPERIMENT_EVER_CLAIMED_FIELD] = ticket.get(
            EXPERIMENT_EVER_CLAIMED_FIELD
        )
    if _private_replay_scout_contract_indicator(ticket):
        entry[PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD] = (
            _private_replay_scout_registry_identity(ticket)
        )
        result = ticket.get("result")
        if isinstance(result, dict) and result.get(
            PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD
        ):
            entry[PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD] = result[
                PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD
            ]
    return entry


def _sync_index_entry(registry, ticket):
    experiments = registry.setdefault("experiments", [])
    entry = _ticket_index_entry(ticket, _registry_tickets_dir(registry))
    for i, existing in enumerate(experiments):
        if existing.get("experiment_id") == ticket.get("experiment_id"):
            if _experiment_reservation_identity_required(ticket):
                existing_reservation_identity = existing.get(
                    EXPERIMENT_RESERVATION_IDENTITY_FIELD
                )
                if existing_reservation_identity is None:
                    raise ValueError(
                        f"{ticket.get('experiment_id')} registry cannot backfill "
                        "a missing reservation identity"
                    )
                if (
                    not _experiment_reservation_identity_is_valid(
                        existing_reservation_identity
                    )
                    or existing_reservation_identity
                    != _experiment_reservation_identity(ticket)
                ):
                    raise ValueError(
                        f"{ticket.get('experiment_id')} registry reservation "
                        "identity mismatch"
                    )
                existing_ever_claimed = existing.get(
                    EXPERIMENT_EVER_CLAIMED_FIELD
                )
                candidate_ever_claimed = ticket.get(
                    EXPERIMENT_EVER_CLAIMED_FIELD
                )
                if type(existing_ever_claimed) is not bool:
                    raise ValueError(
                        f"{ticket.get('experiment_id')} registry cannot backfill "
                        "a missing ever-claimed marker"
                    )
                if existing_ever_claimed and not candidate_ever_claimed:
                    raise ValueError(
                        f"{ticket.get('experiment_id')} registry rejects lifecycle "
                        "rollback after claim"
                    )
                entry[EXPERIMENT_RESERVATION_IDENTITY_FIELD] = (
                    existing_reservation_identity
                )
                entry[EXPERIMENT_EVER_CLAIMED_FIELD] = bool(
                    existing_ever_claimed or candidate_ever_claimed
                )
            # Registry provenance is first-write immutable. A later cache
            # refresh may add the one-time terminal log commitment, but it may
            # never bless changed claim/scope identity by recomputing it from a
            # mutated ticket.
            existing_identity = existing.get(
                PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD
            )
            if existing_identity is not None:
                expected_private_identity = (
                    _private_replay_scout_registry_identity(ticket)
                )
                if (
                    not _private_replay_scout_registry_identity_is_valid(
                        existing_identity
                    )
                    or existing_identity != expected_private_identity
                ):
                    raise ValueError(
                        f"{ticket.get('experiment_id')} registry private replay "
                        "identity mismatch"
                    )
                entry[PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD] = (
                    existing_identity
                )
            elif _private_replay_scout_contract_indicator(ticket):
                raise ValueError(
                    f"{ticket.get('experiment_id')} registry cannot backfill a "
                    "missing private replay identity"
                )
            existing_log_sha256 = existing.get(
                PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD
            )
            if existing_log_sha256 is not None:
                result = ticket.get("result")
                expected_log_sha256 = (
                    result.get(PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD)
                    if isinstance(result, dict)
                    else None
                )
                if existing_log_sha256 != expected_log_sha256:
                    raise ValueError(
                        f"{ticket.get('experiment_id')} registry canonical log "
                        "commitment conflicts with the terminal ticket"
                    )
                entry[PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD] = (
                    existing_log_sha256
                )
            experiments[i] = {**existing, **entry}
            return experiments[i]
    experiments.append(entry)
    return entry


def materialize_experiment(entry):
    ticket_file = entry.get("ticket_file")
    if ticket_file:
        path = REPO_ROOT / ticket_file
        if path.exists():
            with path.open(encoding="utf-8-sig") as f:
                return json.load(f)
    return entry


def iter_experiments(registry):
    return [materialize_experiment(entry) for entry in registry.get("experiments", [])]


def lock_path_for(path):
    path = Path(path)
    return path.with_name(path.name + ".lock")


def _acquire_os_lock(handle):
    if os.name == "nt":
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError from exc
        return
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise
    except OSError as exc:
        raise BlockingIOError from exc


def _release_os_lock(handle):
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def file_lock(path, *, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
              stale_seconds=STALE_LOCK_SECONDS):
    lock_path = lock_path_for(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_seconds
    payload = {
        "pid": os.getpid(),
        "created_at": utc_now_iso(),
        "target": _repo_relative(path),
    }

    lock_path.touch(exist_ok=True)
    with lock_path.open("r+", encoding="utf-8") as handle:
        while True:
            try:
                _acquire_os_lock(handle)
                break
            except BlockingIOError:
                if time.time() >= deadline:
                    raise TimeoutError(f"timed out waiting for lock: {lock_path}")
                time.sleep(0.1)

        try:
            handle.seek(0)
            handle.truncate()
            json.dump(payload, handle, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            yield lock_path
        finally:
            released_payload = dict(payload)
            released_payload["released_at"] = utc_now_iso()
            handle.seek(0)
            handle.truncate()
            json.dump(released_payload, handle, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            _release_os_lock(handle)


def locked_registry_update(path, mutator, *, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    with file_lock(path, timeout_seconds=timeout_seconds):
        path = Path(path)
        workspace_root = registry_workspace_root(path)
        registry = load_registry(path)
        registry["_repo_root"] = str(workspace_root)
        registry["_tickets_dir"] = str(workspace_root / "experiments" / "tickets")
        registry["_logs_dir"] = str(workspace_root / "experiments" / "logs")
        registry["_cards_dir"] = str(workspace_root / "experiments" / "cards")
        registry["_manifests_dir"] = str(workspace_root / "experiments" / "manifests")
        result = mutator(registry)
        save_registry(registry, path)
        return result


def latest_backtest_result(data_dir=None):
    data_dir = Path(data_dir or (REPO_ROOT / "data"))
    files = backtest_result_glob(data_dir)
    if not files:
        return None
    return _repo_relative(files[-1])


def _remember_id_source(sources, experiment_id, source):
    normalized = normalize_experiment_id(experiment_id)
    if normalized:
        sources.setdefault(normalized, set()).add(source)


def _load_json_file(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _scan_json_id_file(path, sources, source_prefix, *, root):
    path = Path(path)
    _remember_id_source(sources, path.name, f"{source_prefix}:filename:{_repo_relative(path)}")
    data = _load_json_file(path)
    if isinstance(data, dict):
        _remember_id_source(
            sources,
            data.get("experiment_id"),
            f"{source_prefix}:json:{_repo_relative(path)}",
        )
        for key in (
            "artifact",
            "json",
            "ticket_file",
            "log_file",
            "card_file",
            "revision_manifest_file",
        ):
            value = data.get(key)
            if value:
                _remember_id_source(
                    sources,
                    value,
                    f"{source_prefix}:ref:{_repo_relative(path)}:{key}",
                )
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    for match in EXPERIMENT_ID_RE.finditer(text):
        _remember_id_source(
            sources,
            match.group(0),
            f"{source_prefix}:text:{_repo_relative(path)}",
        )


def collect_experiment_id_sources(registry=None, *, root=None):
    registry = registry or {}
    include_filesystem = root is not None or bool(registry.get("_repo_root"))
    root = Path(root or registry.get("_repo_root", REPO_ROOT))
    sources = {}

    for exp in registry.get("experiments", []):
        _remember_id_source(sources, exp.get("experiment_id"), "registry")
        for key in ("ticket_file", "log_file", "card_file", "revision_manifest_file"):
            if exp.get(key):
                _remember_id_source(sources, exp[key], f"registry:{key}")
        result = exp.get("result")
        if isinstance(result, dict):
            for key in ("artifact", "json"):
                if result.get(key):
                    _remember_id_source(sources, result[key], f"registry:result:{key}")

    if not include_filesystem:
        return {experiment_id: sorted(values) for experiment_id, values in sources.items()}

    log_path = root / "docs" / "experiment_log.jsonl"
    if log_path.exists():
        try:
            with log_path.open(encoding="utf-8-sig") as f:
                for line_number, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        row = {}
                    if isinstance(row, dict):
                        _remember_id_source(
                            sources,
                            row.get("experiment_id"),
                            f"jsonl:{_repo_relative(log_path)}:{line_number}",
                        )
                    if "exp-" in line or "exp_" in line:
                        for match in EXPERIMENT_ID_RE.finditer(line):
                            _remember_id_source(
                                sources,
                                match.group(0),
                                f"jsonl:text:{_repo_relative(log_path)}:{line_number}",
                            )
        except OSError:
            pass

    json_dirs = [
        (root / "experiments" / "tickets", "ticket"),
        (root / "docs" / "experiments" / "tickets", "docs_ticket"),
        (root / "experiments" / "logs", "log"),
        (root / "docs" / "experiments" / "logs", "docs_log"),
        (root / "experiments" / "manifests", "manifest"),
    ]
    for directory, source_prefix in json_dirs:
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            _scan_json_id_file(path, sources, source_prefix, root=root)

    path_dirs = [
        (root / "data" / "experiments", "data_experiment"),
        (root / "experiments" / "artifacts", "artifact"),
    ]
    for directory, source_prefix in path_dirs:
        if not directory.exists():
            continue
        for path in directory.iterdir():
            _remember_id_source(
                sources,
                path.name,
                f"{source_prefix}:path:{_repo_relative(path)}",
                )

    cards_dir = root / "experiments" / "cards"
    if cards_dir.exists():
        for path in cards_dir.glob("*.md"):
            _remember_id_source(
                sources,
                path.name,
                f"card:filename:{_repo_relative(path)}",
            )
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in EXPERIMENT_ID_RE.finditer(text):
                _remember_id_source(
                    sources,
                    match.group(0),
                    f"card:text:{_repo_relative(path)}",
                )

    quant_experiments = root / "quant" / "experiments"
    if quant_experiments.exists():
        for path in quant_experiments.rglob("exp*"):
            if path.is_file():
                _remember_id_source(
                    sources,
                    path.name,
                    f"runner:path:{_repo_relative(path)}",
                )

    return {experiment_id: sorted(values) for experiment_id, values in sources.items()}


def next_experiment_id(registry, today=None, *, root=None):
    today = today or datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"exp-{today}-"
    max_seen = 0
    for eid in collect_experiment_id_sources(registry, root=root):
        if eid.startswith(prefix):
            max_seen = max(max_seen, int(eid.rsplit("-", 1)[1]))
    return f"{prefix}{max_seen + 1:03d}"


def require_available_experiment_id(experiment_id, registry, *, root=None):
    normalized = normalize_experiment_id(experiment_id)
    if not normalized:
        raise ValueError(
            "experiment_id must match exp-YYYYMMDD-NNN, got "
            f"{experiment_id!r}"
        )
    sources = collect_experiment_id_sources(registry, root=root)
    if normalized in sources:
        joined = ", ".join(sources[normalized])
        raise ValueError(f"experiment_id already exists: {normalized} ({joined})")
    return normalized


def parse_csv(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def _research_digest_status(decision):
    value = str(decision or "").lower()
    if value == "proposed":
        return "proposed"
    if value.startswith("accepted"):
        return "accepted"
    if value.startswith("rejected") or value in {"rolled_back", "duplicate_reservation_accounting"}:
        return "rejected"
    if value.startswith("observed_only") or value in {"blocked", "parked"}:
        return "parked"
    return None


def _append_research_digest_transition(ticket, decision, *, repo_root=None, reason=None):
    """Best-effort, idempotent backlink from an experiment to digest entries."""

    refs = sorted(set(ticket.get("research_refs") or []))
    status = _research_digest_status(decision)
    if not refs or status is None:
        return {"appended": 0, "status": status}
    root = Path(repo_root or REPO_ROOT)
    ledger = root / "data" / "research_digest" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    latest = {}
    with file_lock(ledger):
        if ledger.exists():
            for raw in ledger.read_text(encoding="utf-8-sig").splitlines():
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if row.get("entry_id"):
                    latest[row["entry_id"]] = row
        rows = []
        for entry_id in refs:
            prior = latest.get(entry_id) or {}
            if prior.get("status") == status and prior.get("exp_id") == ticket.get("experiment_id"):
                continue
            rows.append({
                "entry_id": entry_id,
                "status": status,
                "exp_id": ticket.get("experiment_id"),
                "reason": reason or f"experiment {status}: {ticket.get('hypothesis')}",
                "actor": ticket.get("owner") or "experiment_protocol",
                "ts": utc_now_iso().replace("+00:00", "Z"),
            })
        if rows:
            with ledger.open("a", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
    return {"appended": len(rows), "status": status}


def _sync_research_digest_quietly(ticket, decision, *, repo_root=None, reason=None):
    try:
        return _append_research_digest_transition(
            ticket, decision, repo_root=repo_root, reason=reason
        )
    except Exception as exc:
        print(
            f"[research-digest] backlink pending for {ticket.get('experiment_id')}: {exc}",
            file=sys.stderr,
        )
        return {"appended": 0, "error": str(exc)}


def _optional_float(value, field_name):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number, got {value!r}") from exc


def normalize_prediction(
    prediction=None,
    *,
    success_probability=None,
    expected_ev_delta=None,
    expected_pnl_delta=None,
    main_failure_modes=None,
    confidence_reason=None,
):
    """Normalize an experiment pre-run prediction.

    The prediction is research-process metadata only. It must never be consumed
    by trading, ranking, sizing, or risk logic.
    """
    base = dict(prediction or {})
    if success_probability is not None:
        base["success_probability"] = success_probability
    if expected_ev_delta is not None:
        base["expected_ev_delta"] = expected_ev_delta
    if expected_pnl_delta is not None:
        base["expected_pnl_delta"] = expected_pnl_delta
    if main_failure_modes is not None:
        base["main_failure_modes"] = main_failure_modes
    if confidence_reason is not None:
        base["confidence_reason"] = confidence_reason

    probability = _optional_float(base.get("success_probability"), "success_probability")
    expected_ev = _optional_float(base.get("expected_ev_delta"), "expected_ev_delta")
    expected_pnl = _optional_float(base.get("expected_pnl_delta"), "expected_pnl_delta")
    failure_modes = parse_csv(base.get("main_failure_modes"))
    reason = str(base.get("confidence_reason") or "").strip()

    if probability is None and expected_ev is None and expected_pnl is None and not failure_modes and not reason:
        return None
    if probability is not None and not 0.0 <= probability <= 1.0:
        raise ValueError("success_probability must be between 0 and 1")

    normalized = {
        "success_probability": probability,
        "expected_ev_delta": expected_ev,
        "expected_pnl_delta": expected_pnl,
        "main_failure_modes": failure_modes,
        "confidence_reason": reason or None,
    }
    if base.get("recorded_at"):
        normalized["recorded_at"] = base["recorded_at"]
    else:
        normalized["recorded_at"] = utc_now_iso()
    return normalized


def prediction_required_for_lane(lane):
    return lane in PREDICTION_REQUIRED_LANES


def prediction_missing_reasons(ticket):
    if not prediction_required_for_lane(ticket.get("lane")):
        return []
    prediction = normalize_prediction(ticket.get("prediction"))
    if not prediction:
        return ["missing_prediction"]
    reasons = []
    if prediction.get("success_probability") is None:
        reasons.append("missing_success_probability")
    if not prediction.get("main_failure_modes"):
        reasons.append("missing_main_failure_modes")
    return reasons


def _word_count(value):
    return len(re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", str(value or "")))


def _looks_placeholder(value):
    text = str(value or "").strip().lower()
    if not text:
        return True
    # Word-boundary match for single-word placeholders: bare substring matching
    # flagged real prose — "fill" inside "backfilled", "none" inside
    # "nonetheless" — and backfill is a common repo term in confidence reasons
    # and reflections.
    word_placeholders = ("todo", "tbd", "none", "placeholder", "fill")
    phrase_placeholders = ("n/a", "test prediction", "why this prior is reasonable")
    if any(phrase in text for phrase in phrase_placeholders):
        return True
    return any(
        re.search(rf"\b{re.escape(word)}\b", text) for word in word_placeholders
    )


def lean_prediction_quality_reasons(ticket):
    if not prediction_required_for_lane(ticket.get("lane")):
        return []
    prediction = normalize_prediction(ticket.get("prediction"))
    if not prediction:
        return ["missing_prediction"]
    reason = prediction.get("confidence_reason")
    reasons = []
    if prediction.get("success_probability") is None:
        reasons.append("missing_success_probability")
    if _looks_placeholder(reason):
        reasons.append("missing_substantive_confidence_reason")
    elif _word_count(reason) < 12:
        reasons.append("confidence_reason_too_short")
    if not prediction.get("main_failure_modes"):
        reasons.append("missing_main_failure_modes")
    return reasons


def lean_reflection_quality_reasons(ticket, log_row):
    if not prediction_required_for_lane(ticket.get("lane")):
        return []
    reflection = log_row.get("post_run_reflection") if isinstance(log_row, dict) else None
    reasons = []
    if isinstance(reflection, dict):
        why = reflection.get("why_result_happened")
        forbidden = reflection.get("forbidden_near_neighbor_retry")
        new_evidence = reflection.get("new_evidence_required")
        if _looks_placeholder(why) or _word_count(why) < 10:
            reasons.append("weak_result_reflection")
        if _looks_placeholder(forbidden):
            reasons.append("missing_forbidden_retry")
        if _looks_placeholder(new_evidence):
            reasons.append("missing_new_evidence_required")
        return reasons

    calibration = log_row.get("calibration") if isinstance(log_row, dict) else None
    surprise_note = calibration.get("surprise_note") if isinstance(calibration, dict) else None
    notes = log_row.get("notes") if isinstance(log_row, dict) else None
    fallback = surprise_note or notes
    if _looks_placeholder(fallback) or _word_count(fallback) < 15:
        reasons.append("missing_post_run_reflection")
    return reasons


def require_pre_run_prediction(ticket, *, allow_missing_prediction=False):
    reasons = prediction_missing_reasons(ticket)
    if not reasons or allow_missing_prediction:
        return
    experiment_id = ticket.get("experiment_id") or "new experiment"
    lane = ticket.get("lane")
    joined = ", ".join(reasons)
    raise ValueError(
        f"{lane} ticket {experiment_id} requires a pre-run prediction "
        f"before work can continue; missing: {joined}"
    )


def require_pre_run_prediction_quality(ticket, *, allow_missing_prediction=False):
    """Require substantive pre-run prediction text for new alpha/scout work.

    Presence is enforced separately by ``require_pre_run_prediction``. This
    quality gate keeps placeholder or one-line confidence reasons from entering
    the workflow through the normal reservation path or sanctioned
    self-registration path.
    """
    reasons = lean_prediction_quality_reasons(ticket)
    if not reasons or allow_missing_prediction:
        return
    experiment_id = ticket.get("experiment_id") or "new experiment"
    lane = ticket.get("lane")
    joined = ", ".join(reasons)
    raise ValueError(
        f"{lane} ticket {experiment_id} requires a substantive pre-run "
        f"prediction before work can continue; weak: {joined}"
    )


def parse_windows(values):
    windows = []
    for raw in values or []:
        if ":" not in raw:
            raise ValueError(f"window must be START:END, got {raw!r}")
        start, end = raw.split(":", 1)
        windows.append({"start": start, "end": end})
    return windows


def _template_scope(scope, experiment_id, lane, change_type):
    return scope.format(
        experiment_id=experiment_id,
        lane=lane,
        change_type=change_type,
    )


def experiment_file_prefix(experiment_id):
    return experiment_id.replace("-", "_")


def slugify_file_part(value, fallback="experiment"):
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value or "").strip("_").lower()
    slug = re.sub(r"_+", "_", slug)
    return slug[:80].strip("_") or fallback


def default_file_stem(experiment_id, single_causal_variable, file_slug=None):
    slug_source = file_slug or single_causal_variable
    return f"{experiment_file_prefix(experiment_id)}_{slugify_file_part(slug_source)}"


def _yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, (bool, int, float)):
        return json.dumps(value)
    return json.dumps(str(value), ensure_ascii=False)


def _metadata_tags(ticket):
    raw = [
        ticket.get("lane"),
        ticket.get("status"),
        ticket.get("change_type"),
        ticket.get("mechanism_family"),
        ticket.get("trial_family"),
        ticket.get("new_evidence_type"),
    ]
    tags = []
    for value in raw:
        slug = slugify_file_part(value, fallback="")
        if slug and slug not in tags:
            tags.append(slug)
    return tags


def build_experiment_card_markdown(ticket):
    metadata = {
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "status": ticket.get("status"),
        "lane": ticket.get("lane"),
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components") or [],
        "new_evidence_type": ticket.get("new_evidence_type"),
        "created_at": ticket.get("created_at"),
        "baseline_result_file": ticket.get("baseline_result_file"),
    }
    hub_identity = ticket.get("hub_identity") or {}
    if hub_identity.get("repo_id"):
        metadata["hub_repo_id"] = hub_identity["repo_id"]

    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("tags:")
    for tag in _metadata_tags(ticket):
        lines.append(f"  - {_yaml_scalar(tag)}")
    lines.extend([
        "---",
        "",
        f"# Experiment Card: {ticket.get('experiment_id')}",
        "",
        "## Summary",
        "",
        ticket.get("hypothesis") or "TODO: fill experiment hypothesis.",
        "",
        "## Identity",
        "",
        f"- Status: `{ticket.get('status')}`",
        f"- Lane: `{ticket.get('lane')}`",
        f"- Change type: `{ticket.get('change_type')}`",
        f"- Owner: `{ticket.get('owner') or 'unclaimed'}`",
        f"- UID: `{ticket.get('experiment_uid')}`",
        "",
        "## Decision Hypothesis",
        "",
        f"- Decision variable / policy bundle: `{ticket.get('single_causal_variable')}`",
        f"- Changed variable: `{ticket.get('changed_variable')}`",
        f"- Causal components: `{', '.join(ticket.get('causal_components') or []) or 'none'}`",
        f"- Locked variables: `{', '.join(ticket.get('locked_variables') or [])}`",
        "",
        "## Trial Accounting",
        "",
        f"- Mechanism family: `{ticket.get('mechanism_family')}`",
        f"- Trial family: `{ticket.get('trial_family')}`",
        f"- Trial variant: `{ticket.get('trial_variant_id')}`",
        f"- Prior trial count: `{ticket.get('prior_trial_count')}`",
        f"- Nearby prior experiments: `{', '.join(ticket.get('nearby_prior_experiments') or []) or 'none'}`",
        f"- New evidence type: `{ticket.get('new_evidence_type')}`",
        f"- Multiple-testing risk: `{ticket.get('multiple_testing_risk_bucket')}`",
        "",
        "## Lean Alpha Contract",
        "",
        "- Hypothesis inference: why this should make money, which prior experiments matter, and what would falsify it.",
        "- Fixed policy bundle: what is accepted/rejected as one object, and which edits are only implementation/parity/live-realism/test work.",
        "- Measurement plan: windows, before/after metrics, production parity, and live-realistic envelope if relevant.",
        "- Reflection plan: likely failure explanation, forbidden near-neighbor retries, and required new evidence for another attempt.",
        "",
        "## Evaluation Plan",
        "",
        f"- Baseline result file: `{ticket.get('baseline_result_file') or 'not set'}`",
        f"- Acceptance rule: {ticket.get('acceptance_rule')}",
        "",
        "## Reserved Files",
        "",
    ])
    for scope in ticket.get("allowed_write_scope") or []:
        lines.append(f"- `{scope}`")
    lines.extend([
        "",
        "## Alpha Discovery Promotion",
        "",
        "```json",
        json.dumps(ticket.get("alpha_promotion") or {}, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        f"- Research refs: `{', '.join(ticket.get('research_refs') or []) or 'none'}`",
        "",
        "## Pre-Run Prediction",
        "",
        "```json",
        json.dumps(ticket.get("prediction") or {}, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
        "## Post-Run Reflection",
        "",
        "- Why did the result happen? TODO",
        "- Which near-neighbor retry is now forbidden? TODO",
        "- What new evidence would justify a retry? TODO",
        "",
        "## Closeout Notes",
        "",
        "- Decision: TODO",
        "- Before artifact: TODO",
        "- After artifact: TODO",
        "- Main blocker or acceptance basis: TODO",
        "- Next retry requires: TODO",
        "",
    ])
    return "\n".join(lines)


def save_experiment_card(ticket, cards_dir=DEFAULT_CARDS_DIR, *, overwrite=True):
    path = experiment_card_path(ticket["experiment_id"], cards_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as f:
        f.write(build_experiment_card_markdown(ticket))
    return path


def _sha256_file(path):
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_capture(root, *args):
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_revision_snapshot(root):
    root = Path(root or REPO_ROOT)
    status = _git_capture(root, "status", "--short")
    return {
        "commit": _git_capture(root, "rev-parse", "HEAD"),
        "branch": _git_capture(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "status_short": status.splitlines() if status else [],
    }


def _resolve_workspace_path(value, root):
    if not value:
        return None
    path = Path(value)
    if path.is_absolute() or root is None:
        return path
    return Path(root) / path


def _file_manifest_entry(value, *, root=None):
    path = _resolve_workspace_path(value, root)
    if path is None:
        return None
    return {
        "path": _repo_relative(path),
        "exists": path.exists(),
        "sha256": _sha256_file(path),
    }


def build_revision_manifest(ticket, *, repo_root=None, ticket_file=None, card_file=None):
    repo_root = Path(repo_root or REPO_ROOT)
    files = {
        "ticket": _file_manifest_entry(ticket_file or ticket.get("ticket_file"), root=repo_root),
        "card": _file_manifest_entry(card_file or ticket.get("card_file"), root=repo_root),
        "baseline_result": _file_manifest_entry(ticket.get("baseline_result_file"), root=repo_root),
    }
    promotion = ticket.get("alpha_promotion") or {}
    for label, keys in {
        "alpha_promotion": ("promotion_request_path", "artifact_path"),
        "alpha_debate": ("debate_artifact_path",),
        "alpha_selection_panel": ("panel_path",),
    }.items():
        value = next((promotion.get(key) for key in keys if promotion.get(key)), None)
        if value:
            files[label] = _file_manifest_entry(value, root=repo_root)
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "generated_at": utc_now_iso(),
        "created_at": ticket.get("created_at"),
        "hub_identity": ticket.get("hub_identity") or {},
        "git": _git_revision_snapshot(repo_root),
        "files": {key: value for key, value in files.items() if value is not None},
        "artifact_roots": {
            "runner": f"quant/experiments/{experiment_file_prefix(ticket['experiment_id'])}_<slug>.py",
            "data": f"data/experiments/{ticket['experiment_id']}/",
            "artifact": f"experiments/artifacts/{ticket['experiment_id']}_<slug>.md",
            "log": f"experiments/logs/{ticket['experiment_id']}.json",
        },
        "reservation_note": (
            "Generated when the experiment ID was reserved. Update or regenerate "
            "after final artifacts exist if exact after-run hashes are required."
        ),
    }
    if _experiment_reservation_identity_required(ticket):
        _validate_experiment_claim_lifecycle(ticket)
        manifest[EXPERIMENT_RESERVATION_IDENTITY_FIELD] = (
            _experiment_reservation_identity(ticket)
        )
        manifest[EXPERIMENT_EVER_CLAIMED_FIELD] = ticket.get(
            EXPERIMENT_EVER_CLAIMED_FIELD
        )
    if _private_replay_scout_contract_indicator(ticket):
        manifest[PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD] = (
            _private_replay_scout_registry_identity(ticket)
        )
    return manifest


def save_revision_manifest(
    ticket,
    manifests_dir=DEFAULT_MANIFESTS_DIR,
    *,
    repo_root=None,
    ticket_file=None,
    card_file=None,
    overwrite=True,
):
    path = revision_manifest_path(ticket["experiment_id"], manifests_dir)
    if (
        not overwrite
        and _experiment_reservation_identity_required(ticket)
        and ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD) is True
    ):
        raise ValueError(
            f"{ticket.get('experiment_id')} cannot create a missing reservation "
            "manifest from an already claimed ticket"
        )
    manifest = build_revision_manifest(
        ticket,
        repo_root=repo_root,
        ticket_file=ticket_file,
        card_file=card_file,
    )
    existing = _load_json_file(path) if path.exists() else None
    if overwrite and _experiment_reservation_identity_required(ticket):
        if not isinstance(existing, dict):
            raise ValueError(
                f"{ticket.get('experiment_id')} cannot regenerate a missing "
                "reservation manifest identity"
            )
        existing_reservation_identity = existing.get(
            EXPERIMENT_RESERVATION_IDENTITY_FIELD
        )
        if (
            not _experiment_reservation_identity_is_valid(
                existing_reservation_identity
            )
            or existing_reservation_identity
            != _experiment_reservation_identity(ticket)
        ):
            raise ValueError(
                f"{ticket.get('experiment_id')} manifest reservation identity "
                "is missing or does not match the ticket"
            )
        existing_ever_claimed = existing.get(EXPERIMENT_EVER_CLAIMED_FIELD)
        ticket_ever_claimed = ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD)
        if type(existing_ever_claimed) is not bool:
            raise ValueError(
                f"{ticket.get('experiment_id')} manifest ever-claimed marker "
                "is missing"
            )
        if existing_ever_claimed and not ticket_ever_claimed:
            raise ValueError(
                f"{ticket.get('experiment_id')} manifest rejects lifecycle "
                "rollback after claim"
            )
        manifest[EXPERIMENT_RESERVATION_IDENTITY_FIELD] = (
            existing_reservation_identity
        )
        manifest[EXPERIMENT_EVER_CLAIMED_FIELD] = bool(
            existing_ever_claimed or ticket_ever_claimed
        )
        existing_claim_transition = existing.get(
            EXPERIMENT_CLAIM_TRANSITION_FIELD
        )
        ticket_claim_transition = ticket.get(
            EXPERIMENT_CLAIM_TRANSITION_FIELD
        )
        if ticket_ever_claimed:
            if (
                not _experiment_claim_transition_is_valid(
                    ticket_claim_transition, ticket
                )
                or existing_claim_transition != ticket_claim_transition
            ):
                raise ValueError(
                    f"{ticket.get('experiment_id')} manifest is missing the "
                    "hash-bound claim transition intent"
                )
            manifest[EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
                existing_claim_transition
            )
        elif existing_claim_transition is not None:
            # A crash may leave a pre-ticket claim intent in the reservation
            # manifest. It grants no authority while all lifecycle markers are
            # false, but it remains available for a fresh, fully revalidated
            # claim attempt to replace.
            manifest[EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
                existing_claim_transition
            )
    if overwrite and path.exists():
        if isinstance(existing, dict) and existing.get(
            PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD
        ) is not None:
            if (
                _private_replay_scout_contract_indicator(ticket)
                and existing[PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD]
                != _private_replay_scout_registry_identity(ticket)
            ):
                raise ValueError(
                    f"{ticket.get('experiment_id')} manifest private replay "
                    "identity does not match the ticket"
                )
            manifest[PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD] = existing[
                PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD
            ]
        elif _private_replay_scout_contract_indicator(ticket):
            raise ValueError(
                f"{ticket.get('experiment_id')} cannot backfill a missing "
                "private replay manifest identity"
            )
    text = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if not overwrite:
        # Atomic exclusive create, consistent with save_ticket / save_experiment_card:
        # no TOCTOU exists()-then-write race and no same-dir .tmp residue.
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        return path
    _atomic_write_text(text, path)
    return path


def _save_claim_transition_manifest_intent(ticket, manifests_dir):
    """Persist claim authorization independently before mutating the ticket."""

    experiment_id = ticket.get("experiment_id")
    transition = ticket.get(EXPERIMENT_CLAIM_TRANSITION_FIELD)
    if (
        ticket.get("status") != "claimed"
        or ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD) is not True
        or not _experiment_claim_transition_is_valid(transition, ticket)
    ):
        raise ValueError(
            f"{experiment_id} cannot persist an invalid claim transition intent"
        )
    path = revision_manifest_path(experiment_id, manifests_dir)
    manifest = _load_json_file(path)
    if not isinstance(manifest, dict) or manifest.get("experiment_id") != experiment_id:
        raise ValueError(
            f"{experiment_id} claim requires its reservation-time manifest"
        )
    expected_identity = _experiment_reservation_identity(ticket)
    if (
        manifest.get(EXPERIMENT_RESERVATION_IDENTITY_FIELD) != expected_identity
        or manifest.get(EXPERIMENT_EVER_CLAIMED_FIELD) is not False
    ):
        raise ValueError(
            f"{experiment_id} claim transition intent requires an unclaimed, "
            "matching reservation manifest"
        )
    manifest[EXPERIMENT_CLAIM_TRANSITION_FIELD] = transition
    _atomic_write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        path,
    )
    return path


def default_allowed_write_scope(
    experiment_id,
    lane,
    single_causal_variable,
    file_slug=None,
):
    stem = default_file_stem(experiment_id, single_causal_variable, file_slug)
    return [
        f"quant/experiments/{stem}.py",
        f"data/experiments/{experiment_id}/{stem}.json",
        f"experiments/cards/{experiment_id}.md",
        f"experiments/manifests/{experiment_id}.json",
        f"experiments/tickets/{experiment_id}.json",
        f"experiments/logs/{experiment_id}.json",
        "docs/experiment_log.jsonl",
        "docs/experiment_registry.json",
    ]


def normalize_allowed_write_scope(
    scopes,
    *,
    experiment_id,
    lane,
    change_type,
    single_causal_variable,
    file_slug=None,
    exclusive_scope_ok=False,
):
    if not scopes:
        return default_allowed_write_scope(
            experiment_id,
            lane,
            single_causal_variable,
            file_slug,
        )

    normalized = [
        _template_scope(scope, experiment_id, lane, change_type)
        for scope in scopes
    ]
    if exclusive_scope_ok:
        return normalized

    broad = [
        scope for scope in normalized
        if _normalize_scope(scope) in DISALLOWED_BROAD_SCOPES
    ]
    if broad:
        raise ValueError(
            "broad allowed_write_scope entries require --exclusive-scope-ok: "
            + ", ".join(broad)
        )
    return normalized


def get_experiment(registry, experiment_id):
    if "_tickets_dir" in registry:
        canonical = load_ticket(experiment_id, _registry_tickets_dir(registry))
        if canonical is not None:
            return canonical
    for exp in registry.get("experiments", []):
        if exp.get("experiment_id") == experiment_id:
            return materialize_experiment(exp)
    return None


def create_ticket(
    registry,
    *,
    experiment_id=None,
    lane,
    hypothesis,
    change_type,
    single_causal_variable,
    causal_components=None,
    mechanism_family=None,
    trial_family=None,
    trial_variant_id=None,
    changed_variable=None,
    prior_trial_count=0,
    nearby_prior_experiments=None,
    multiple_testing_risk_bucket="minimal",
    new_evidence_type="not_declared",
    baseline_result_file=None,
    allowed_write_scope=None,
    must_not_touch=None,
    locked_variables=None,
    evaluation_windows=None,
    acceptance_rule=None,
    owner=None,
    file_slug=None,
    exclusive_scope_ok=False,
    prediction=None,
    promotion_request=None,
    reservation_intent=None,
):
    if lane not in VALID_LANES:
        raise ValueError(f"lane must be one of {sorted(VALID_LANES)}")
    repo_root = _registry_repo_root(registry)
    baseline = baseline_result_file or latest_backtest_result()
    if experiment_id is None:
        experiment_id = next_experiment_id(registry, root=repo_root)
    experiment_id = require_available_experiment_id(
        experiment_id,
        registry,
        root=repo_root,
    )
    changed_variable = changed_variable or single_causal_variable
    mechanism_family = mechanism_family or change_type
    trial_family = trial_family or mechanism_family
    trial_variant_id = trial_variant_id or experiment_id
    created_at = utc_now_iso()
    file_part = slugify_file_part(file_slug or single_causal_variable)
    write_scope = normalize_allowed_write_scope(
        allowed_write_scope,
        experiment_id=experiment_id,
        lane=lane,
        change_type=change_type,
        single_causal_variable=single_causal_variable,
        file_slug=file_slug,
        exclusive_scope_ok=exclusive_scope_ok,
    )
    normalized_prediction = normalize_prediction(prediction)
    require_pre_run_prediction(
        {
            "experiment_id": experiment_id,
            "lane": lane,
            "prediction": normalized_prediction,
        }
    )
    require_pre_run_prediction_quality(
        {
            "experiment_id": experiment_id,
            "lane": lane,
            "prediction": normalized_prediction,
        }
    )
    promotion_anchor = None
    if _alpha_promotion_required_for_lane(lane) or promotion_request:
        proposal_payload = _ticket_proposal_payload(
            lane=lane,
            hypothesis=hypothesis,
            change_type=change_type,
            single_causal_variable=single_causal_variable,
            causal_components=causal_components or [],
            mechanism_family=mechanism_family,
            trial_family=trial_family,
            changed_variable=changed_variable,
            prediction=normalized_prediction,
        )
        promotion_anchor = _validate_alpha_promotion_for_creation(
            registry,
            lane=lane,
            promotion_request=promotion_request,
            proposal=proposal_payload,
        )
    ticket = {
        "experiment_id": experiment_id,
        "experiment_uid": new_experiment_uid(),
        "hub_identity": {
            "scheme": "hf_hub_local_v1",
            "namespace": "ginger/experiments",
            "repo_id": f"ginger/experiments/{experiment_id}",
            "slug": file_part,
            "reserved_at": created_at,
            "reservation_rule": (
                "Reserve the ticket (atomic O_EXCL create) before writing "
                "runners, artifacts, data, or logs. Existing IDs are rejected "
                "across registry, JSONL, tickets, logs, artifacts, data, and "
                "runners."
            ),
        },
        "status": "proposed",
        "lane": lane,
        "owner": owner,
        "hypothesis": hypothesis,
        "change_type": change_type,
        "mechanism_family": mechanism_family,
        "trial_family": trial_family,
        "trial_variant_id": trial_variant_id,
        "single_causal_variable": single_causal_variable,
        "changed_variable": changed_variable,
        "causal_components": causal_components or [],
        "prior_trial_count": int(prior_trial_count or 0),
        "nearby_prior_experiments": nearby_prior_experiments or [],
        "multiple_testing_risk_bucket": multiple_testing_risk_bucket,
        "new_evidence_type": new_evidence_type,
        "baseline_result_file": baseline,
        "allowed_write_scope": write_scope,
        "must_not_touch": must_not_touch or [],
        "locked_variables": locked_variables or (
            [single_causal_variable] if single_causal_variable else []
        ),
        "evaluation_windows": evaluation_windows or [],
        "acceptance_rule": acceptance_rule or "Use AGENTS.md Gate 4.",
        "prediction": normalized_prediction,
        "created_at": created_at,
        "claimed_at": None,
        "completed_at": None,
        "result": None,
    }
    if _experiment_reservation_identity_required(ticket):
        ticket[EXPERIMENT_EVER_CLAIMED_FIELD] = False
    if reservation_intent:
        ticket["reservation_intent"] = {
            "schema_version": 1,
            "key": reservation_intent["key"],
            "payload_hash": reservation_intent["payload_hash"],
        }
    if promotion_anchor:
        ticket["alpha_promotion"] = promotion_anchor
        ticket["research_refs"] = list(promotion_anchor.get("research_refs") or [])
        if (
            promotion_anchor.get("admission_class")
            == RESEARCH_REPLAY_ADMISSION_CLASS
            and change_type == PRIVATE_REPLAY_SCOUT_CHANGE_TYPE
        ):
            ticket[
                "private_replay_scout_artifact_disposition_contract_version"
            ] = PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION
            # Freeze identity and write scopes at reservation, not only after a
            # successful claim.  The narrow never-claimed duplicate-abandonment
            # path must remain auditable without inventing authority it never
            # received.
            ticket[PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD] = (
                _private_replay_scout_claim_binding(ticket)
            )
    if "_tickets_dir" in registry:
        workspace_root = _registry_repo_root(registry)
        ticket_file = ticket_path(experiment_id, _registry_tickets_dir(registry))
        card_file = experiment_card_path(experiment_id, _registry_cards_dir(registry))
        manifest_file = revision_manifest_path(
            experiment_id,
            _registry_manifests_dir(registry),
        )
        ticket["ticket_file"] = _repo_relative(ticket_file, workspace_root)
        ticket["card_file"] = _repo_relative(card_file, workspace_root)
        ticket["revision_manifest_file"] = _repo_relative(
            manifest_file, workspace_root
        )
        for label, path in (
            ("experiment ticket", ticket_file),
            ("experiment card", card_file),
            ("revision manifest", manifest_file),
        ):
            if path.exists():
                raise ValueError(f"{label} already exists: {path}")
        try:
            save_ticket(ticket, _registry_tickets_dir(registry), overwrite=False)
            save_experiment_card(ticket, _registry_cards_dir(registry), overwrite=False)
            save_revision_manifest(
                ticket,
                _registry_manifests_dir(registry),
                repo_root=workspace_root,
                ticket_file=ticket_file,
                card_file=card_file,
                overwrite=False,
            )
        except FileExistsError as exc:
            raise ValueError(f"experiment identity artifact already exists: {exc}") from exc
        _sync_index_entry(registry, ticket)
        _sync_research_digest_quietly(
            ticket,
            "proposed",
            repo_root=workspace_root,
            reason="promotion request reserved as an experiment ticket",
        )
    else:
        registry.setdefault("experiments", []).append(ticket)
    return ticket


def _file_backed_registry_context(registry_path):
    """Registry-like context with workspace dir keys resolved from the registry
    path, WITHOUT loading docs/experiment_registry.json.

    The reserve path uses this so it never needs the full (1.8 MB) registry
    object to allocate an id: the ticket file is the source of truth.
    """
    workspace_root = registry_workspace_root(registry_path)
    return {
        "_repo_root": str(workspace_root),
        "_tickets_dir": str(workspace_root / "experiments" / "tickets"),
        "_logs_dir": str(workspace_root / "experiments" / "logs"),
        "_cards_dir": str(workspace_root / "experiments" / "cards"),
        "_manifests_dir": str(workspace_root / "experiments" / "manifests"),
        "experiments": [],
    }


def reserve_experiment(registry_path, *, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
                       max_attempts=64, **ticket_kwargs):
    """Reserve an experiment WITHOUT holding the global registry lock across the
    heavy id-collision scan (registry-decontention step 1).

    The ticket file is the atomic source of truth: ``create_ticket`` allocates an
    id (lock-free filesystem scan) and writes the ticket via O_EXCL (step 0), so
    two concurrent reservers cannot take the same id -- the loser gets a
    FileExistsError-derived ValueError and retries the next sequence number.
    ``docs/experiment_registry.json`` is then refreshed best-effort under a brief
    lock (index entry only, NOT the scan), keeping it a current-but-non-
    authoritative cache for legacy readers. A contended/missed cache refresh
    never fails an already-durable reservation.
    """
    explicit = ticket_kwargs.get("experiment_id") is not None
    intent = None if explicit else reservation_intent_for(ticket_kwargs)
    last_exc = None
    context = _file_backed_registry_context(registry_path)

    if intent:
        lock_target = reservation_intent_path(context, intent)
        with file_lock(lock_target, timeout_seconds=timeout_seconds):
            existing = _open_ticket_for_reservation_intent(context, intent)
            if existing:
                save_reservation_intent(context, intent, existing)
                _best_effort_cache_upsert(registry_path, existing, timeout_seconds)
                return existing
            ticket_kwargs = {**ticket_kwargs, "reservation_intent": intent}

            for _ in range(max_attempts):
                context = _file_backed_registry_context(registry_path)
                try:
                    ticket = create_ticket(context, **ticket_kwargs)
                except ValueError as exc:
                    # Auto-allocated ids retry the next sequence number on collision;
                    # non-collision validation errors propagate.
                    if "already exists" not in str(exc):
                        raise
                    last_exc = exc
                    continue
                save_reservation_intent(context, intent, ticket)
                _best_effort_cache_upsert(registry_path, ticket, timeout_seconds)
                return ticket
        raise last_exc or RuntimeError("failed to reserve an available experiment id")

    for _ in range(max_attempts):
        context = _file_backed_registry_context(registry_path)
        try:
            ticket = create_ticket(context, **ticket_kwargs)
        except ValueError as exc:
            if explicit or "already exists" not in str(exc):
                raise
            last_exc = exc
            continue
        _best_effort_cache_upsert(registry_path, ticket, timeout_seconds)
        return ticket
    raise last_exc or RuntimeError("failed to reserve an available experiment id")


def _path_overlaps(left, right):
    a = _normalize_scope(left)
    b = _normalize_scope(right)
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _normalize_scope(scope):
    return _repo_relative(scope).replace("\\", "/").rstrip("/").lower()


def _is_shared_coordination_scope(scope):
    return _normalize_scope(scope) in SHARED_COORDINATION_SCOPES


def _conflict_scopes(scopes):
    return [scope for scope in (scopes or []) if not _is_shared_coordination_scope(scope)]


def find_conflicts(registry, experiment):
    conflicts = []
    scopes = _conflict_scopes(experiment.get("allowed_write_scope") or [])
    locked = set(experiment.get("locked_variables") or [])
    experiment_id = experiment.get("experiment_id")
    for other in iter_experiments(registry):
        # Skip self by id, not by object identity: iter_experiments materializes
        # entries by re-reading the ticket file, so the self entry is a distinct
        # object from `experiment` and an identity check would let an experiment
        # spuriously conflict with itself.
        if other.get("experiment_id") == experiment_id:
            continue
        normalized_status = str(other.get("status") or "").strip().lower()
        if normalized_status not in ACTIVE_STATUSES:
            continue
        other_scopes = _conflict_scopes(other.get("allowed_write_scope") or [])
        scope_hits = [
            [s, o]
            for s in scopes
            for o in other_scopes
            if _path_overlaps(s, o)
        ]
        locked_hits = sorted(locked.intersection(other.get("locked_variables") or []))
        if scope_hits or locked_hits:
            conflicts.append({
                "experiment_id": other.get("experiment_id"),
                "owner": other.get("owner"),
                "status": other.get("status"),
                "scope_conflicts": scope_hits,
                "locked_variable_conflicts": locked_hits,
            })
    return conflicts


def claim_ticket(registry, experiment_id, owner, force=False):
    _require_canonical_experiment_id(experiment_id)
    exp = get_experiment(registry, experiment_id)
    if not exp:
        raise ValueError(f"unknown experiment_id: {experiment_id}")
    status = str(exp.get("status") or "").strip().lower()
    if (
        _private_replay_scout_contract_indicator(exp)
        and exp.get("status") != status
    ):
        raise ValueError(
            f"{experiment_id} private replay contract status must use an exact "
            f"canonical lifecycle value, got {exp.get('status')!r}"
        )
    current_owner = exp.get("owner")
    if status == "claimed":
        if current_owner != owner:
            raise ValueError(
                f"{experiment_id} is already claimed by {current_owner!r}; "
                f"owner takeover by {owner!r} is forbidden"
            )
        _revalidate_alpha_promotion_for_claim(registry, exp)
        if EXPERIMENT_EVER_CLAIMED_FIELD in exp:
            _validate_experiment_claim_lifecycle(exp)
        return exp, []
    if status != "proposed":
        raise ValueError(
            f"{experiment_id} cannot transition from {status!r} to claimed"
        )
    if exp.get("claimed_at"):
        raise ValueError(
            f"{experiment_id} proposed ticket cannot carry claimed_at before claim"
        )
    if current_owner not in (None, "", owner):
        raise ValueError(
            f"{experiment_id} proposed ticket is assigned to {current_owner!r}; "
            f"claim by {owner!r} is forbidden"
        )
    if EXPERIMENT_EVER_CLAIMED_FIELD in exp:
        _validate_experiment_claim_lifecycle(exp)
    # This is an admission proof, not a contention override.  It is checked
    # before conflicts so --force can never turn a missing/tampered debate or
    # D0-D3 promotion artifact into a valid alpha claim.
    _revalidate_alpha_promotion_for_claim(registry, exp)
    conflicts = find_conflicts(registry, exp)
    if conflicts and not force:
        return exp, conflicts
    existing_receipt = exp.get("alpha_promotion_claim_receipt")
    if existing_receipt is not None and exp.get("status") == "proposed":
        raise ValueError(
            f"{experiment_id} proposed ticket cannot carry a pre-claim "
            "alpha_promotion_claim_receipt"
        )
    receipt = _build_alpha_promotion_claim_receipt(registry, exp)
    private_replay_claim_binding = None
    research_metadata = _research_replay_metadata(exp)
    if research_metadata is not None and _private_replay_scout_artifact_contract_required(
        exp, research_metadata
    ):
        private_replay_claim_binding = _private_replay_scout_claim_binding(exp)
    claimed_at = (
        receipt.get("claimed_validation_at")
        if isinstance(receipt, dict)
        else utc_now_iso()
    )
    claim_candidate = dict(exp)
    claim_candidate.update(
        {
            "owner": owner,
            "status": "claimed",
            "claimed_at": claimed_at,
        }
    )
    if _experiment_reservation_identity_required(claim_candidate):
        claim_candidate[EXPERIMENT_EVER_CLAIMED_FIELD] = True
    if receipt is not None:
        claim_candidate["alpha_promotion_claim_receipt"] = receipt
    if private_replay_claim_binding is not None:
        claim_candidate[PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD] = (
            private_replay_claim_binding
        )
    required = getattr(
        _alpha_promotion_api(), "claim_receipt_required_for_ticket", None
    )
    if (
        _alpha_promotion_gate_enabled(registry)
        and required is not None
        and required(claim_candidate)
        and receipt is None
    ):
        raise ValueError(
            f"{experiment_id} cannot be claimed after receipt enforcement "
            "without a promotion anchor and alpha_promotion_claim_receipt"
        )
    if _experiment_reservation_identity_required(claim_candidate):
        claim_candidate[EXPERIMENT_CLAIM_TRANSITION_FIELD] = (
            _build_experiment_claim_transition(claim_candidate, force=force)
        )
        _validate_experiment_claim_lifecycle(claim_candidate)
    exp["owner"] = owner
    exp["status"] = "claimed"
    exp["claimed_at"] = claimed_at
    if _experiment_reservation_identity_required(exp):
        exp[EXPERIMENT_EVER_CLAIMED_FIELD] = True
    if receipt is not None:
        exp["alpha_promotion_claim_receipt"] = receipt
    if private_replay_claim_binding is not None:
        exp[PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD] = private_replay_claim_binding
    if _experiment_reservation_identity_required(exp):
        exp[EXPERIMENT_CLAIM_TRANSITION_FIELD] = claim_candidate[
            EXPERIMENT_CLAIM_TRANSITION_FIELD
        ]
    if "_tickets_dir" in registry and not registry.get("_ticket_shard_view"):
        if _experiment_reservation_identity_required(exp):
            _save_claim_transition_manifest_intent(
                exp,
                _registry_manifests_dir(registry),
            )
        save_ticket(exp, _registry_tickets_dir(registry))
        if _experiment_reservation_identity_required(exp):
            save_revision_manifest(
                exp,
                _registry_manifests_dir(registry),
                repo_root=_registry_repo_root(registry),
                ticket_file=ticket_path(
                    experiment_id, _registry_tickets_dir(registry)
                ),
                card_file=experiment_card_path(
                    experiment_id, _registry_cards_dir(registry)
                ),
            )
        _sync_index_entry(registry, exp)
    return exp, []


def metric_snapshot(result):
    benchmarks = result.get("benchmarks") or {}
    total_return = benchmarks.get("strategy_total_return_pct")
    sharpe_daily = result.get("sharpe_daily")
    ev = result.get("expected_value_score")
    if ev is None and total_return is not None and sharpe_daily is not None:
        ev = round(total_return * sharpe_daily, 4)
    return {
        "expected_value_score": ev,
        "sharpe": result.get("sharpe"),
        "sharpe_daily": sharpe_daily,
        "total_return_pct": total_return,
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "total_pnl": result.get("total_pnl"),
    }


def _delta(after, before, key):
    a = after.get(key)
    b = before.get(key)
    if a is None or b is None:
        return None
    return round(a - b, 6)


def evaluate_gate(before_metrics, after_metrics):
    reasons = []
    before_ev = before_metrics.get("expected_value_score")
    after_ev = after_metrics.get("expected_value_score")
    if before_ev not in (None, 0) and after_ev is not None:
        ev_pct = (after_ev - before_ev) / abs(before_ev)
        if ev_pct > 0.10:
            reasons.append(f"expected_value_score improved {ev_pct:.2%}")

    sharpe_delta = _delta(after_metrics, before_metrics, "sharpe")
    if sharpe_delta is not None and sharpe_delta > 0.1:
        reasons.append(f"sharpe improved {sharpe_delta:.4f}")

    dd_delta = _delta(after_metrics, before_metrics, "max_drawdown_pct")
    if dd_delta is not None and dd_delta < -0.01:
        reasons.append(f"max_drawdown_pct fell {-dd_delta:.4f}")

    before_pnl = before_metrics.get("total_pnl")
    after_pnl = after_metrics.get("total_pnl")
    if before_pnl not in (None, 0) and after_pnl is not None:
        pnl_pct = (after_pnl - before_pnl) / abs(before_pnl)
        if pnl_pct > 0.05:
            reasons.append(f"total_pnl improved {pnl_pct:.2%}")

    trade_delta = _delta(after_metrics, before_metrics, "trade_count")
    win_delta = _delta(after_metrics, before_metrics, "win_rate")
    if trade_delta is not None and win_delta is not None:
        if trade_delta > 0 and win_delta >= 0:
            reasons.append("trade_count increased while win_rate did not decline")

    return {
        "decision": "accepted" if reasons else "rejected",
        "acceptance_reasons": reasons,
    }


def judge_results(before_path, after_path):
    with Path(before_path).open(encoding="utf-8-sig") as f:
        before_raw = json.load(f)
    with Path(after_path).open(encoding="utf-8-sig") as f:
        after_raw = json.load(f)
    before = metric_snapshot(before_raw)
    after = metric_snapshot(after_raw)
    delta = {
        key: _delta(after, before, key)
        for key in before
        if isinstance(before.get(key), (int, float)) or isinstance(after.get(key), (int, float))
    }
    gate = evaluate_gate(before, after)
    return {
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        **gate,
    }


def final_decision(judgement, status_override=None, *, experiment=None):
    if status_override is None:
        return judgement["decision"]
    if status_override not in FINAL_STATUSES:
        raise ValueError(f"status_override must be one of {sorted(FINAL_STATUSES)}")
    if (
        status_override == "accepted"
        and isinstance(experiment, dict)
        and prediction_required_for_lane(experiment.get("lane"))
        and not str(judgement.get("decision") or "").startswith("accepted")
    ):
        raise ValueError(
            "alpha status_override cannot promote a non-accepted Gate decision "
            "to accepted"
        )
    return status_override


def _actual_success_from_decision(decision):
    if decision in {"accepted"} or str(decision).startswith("accepted"):
        return 1
    if decision in {"rejected", "rolled_back"} or str(decision).startswith("rejected"):
        return 0
    return None


def _surprise_level(probability, actual_success):
    if probability is None or actual_success is None:
        return "not_scored"
    surprise = abs(probability - actual_success)
    if surprise >= 0.75:
        return "high"
    if surprise >= 0.50:
        return "medium"
    if surprise >= 0.25:
        return "low"
    return "very_low"


def _calibration_direction(probability, actual_success):
    if probability is None or actual_success is None:
        return "not_scored"
    predicted_success = probability >= 0.5
    if predicted_success and not actual_success:
        return "overconfident"
    if not predicted_success and actual_success:
        return "underconfident"
    return "directionally_calibrated"


def build_prediction_calibration(
    prediction,
    judgement,
    decision,
    *,
    realized_failure_mode=None,
    surprise_note=None,
):
    prediction = normalize_prediction(prediction)
    if not prediction:
        return None

    actual_success = _actual_success_from_decision(decision)
    probability = prediction.get("success_probability")
    brier_score = None
    if probability is not None and actual_success is not None:
        brier_score = round((probability - actual_success) ** 2, 6)

    deltas = judgement.get("delta_metrics") or {}
    actual_ev_delta = deltas.get("expected_value_score")
    actual_pnl_delta = deltas.get("total_pnl")
    expected_ev_delta = prediction.get("expected_ev_delta")
    expected_pnl_delta = prediction.get("expected_pnl_delta")

    ev_prediction_error = None
    if actual_ev_delta is not None and expected_ev_delta is not None:
        ev_prediction_error = round(actual_ev_delta - expected_ev_delta, 6)
    pnl_prediction_error = None
    if actual_pnl_delta is not None and expected_pnl_delta is not None:
        pnl_prediction_error = round(actual_pnl_delta - expected_pnl_delta, 2)

    predicted_modes = prediction.get("main_failure_modes") or []
    realized_mode = str(realized_failure_mode or "").strip() or None
    failure_mode_hit = None
    if realized_mode:
        failure_mode_hit = realized_mode in predicted_modes

    return {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": probability,
        "brier_score": brier_score,
        "calibration_direction": _calibration_direction(probability, actual_success),
        "surprise_level": _surprise_level(probability, actual_success),
        "expected_ev_delta": expected_ev_delta,
        "actual_ev_delta": actual_ev_delta,
        "ev_prediction_error": ev_prediction_error,
        "expected_pnl_delta": expected_pnl_delta,
        "actual_pnl_delta": actual_pnl_delta,
        "pnl_prediction_error": pnl_prediction_error,
        "predicted_failure_modes": predicted_modes,
        "realized_failure_mode": realized_mode,
        "predicted_failure_mode_hit": failure_mode_hit,
        "surprise_note": surprise_note,
    }


def build_log_draft(
    experiment,
    judgement,
    before_path,
    after_path,
    *,
    status_override=None,
    change_summary=None,
    notes=None,
    realized_failure_mode=None,
    surprise_note=None,
    allow_missing_prediction=False,
    repo_root=None,
):
    decision = final_decision(
        judgement,
        status_override,
        experiment=experiment,
    )
    research_replay = _enforce_research_replay_result_ceiling(
        experiment,
        decision,
        result=experiment.get("result") if isinstance(experiment, dict) else None,
        artifact_path=after_path,
        repo_root=repo_root or REPO_ROOT,
    )
    require_pre_run_prediction(
        experiment,
        allow_missing_prediction=allow_missing_prediction,
    )
    row = {
        "experiment_id": experiment.get("experiment_id"),
        "timestamp": utc_now_iso(),
        "status": decision,
        "hypothesis": experiment.get("hypothesis"),
        "change_summary": change_summary or (
            "Generated by scripts/judge_experiment.py; fill in code changes before appending."
        ),
        "change_type": experiment.get("change_type"),
        "mechanism_family": experiment.get("mechanism_family"),
        "trial_family": experiment.get("trial_family"),
        "trial_variant_id": experiment.get("trial_variant_id"),
        "changed_variable": experiment.get("changed_variable"),
        "causal_components": experiment.get("causal_components") or [],
        "prior_trial_count": experiment.get("prior_trial_count", 0),
        "nearby_prior_experiments": experiment.get("nearby_prior_experiments") or [],
        "multiple_testing_risk_bucket": experiment.get("multiple_testing_risk_bucket"),
        "new_evidence_type": experiment.get("new_evidence_type"),
        "research_refs": experiment.get("research_refs") or [],
        "alpha_promotion": experiment.get("alpha_promotion"),
        "component": ", ".join(experiment.get("allowed_write_scope") or []),
        "parameters": {
            "single_causal_variable": experiment.get("single_causal_variable"),
            "locked_variables": experiment.get("locked_variables") or [],
        },
        "date_range": (experiment.get("evaluation_windows") or [{}])[0],
        "secondary_windows": (experiment.get("evaluation_windows") or [])[1:],
        "market_regime_summary": {},
        "before_metrics": judgement["before_metrics"],
        "after_metrics": judgement["after_metrics"],
        "delta_metrics": judgement["delta_metrics"],
        "llm_metrics": {"used_llm": False},
        "decision": decision,
        "rejection_reason": (
            None if decision in {"accepted", "observed_only"}
            else "No AGENTS.md Gate 4 acceptance condition was met."
        ),
        "next_retry_requires": [],
        "related_files": [
            _repo_relative(before_path, repo_root),
            _repo_relative(after_path, repo_root),
        ],
        "notes": notes if notes is not None else "; ".join(judgement.get("acceptance_reasons") or []),
    }
    if research_replay:
        row.update(research_replay)
        if _private_replay_scout_artifact_contract_required(
            experiment, _research_replay_metadata(experiment)
        ):
            row.update(
                {
                    "experiment_uid": experiment.get("experiment_uid"),
                    "private_replay_scout_artifact_disposition_contract_version": (
                        experiment.get(
                            "private_replay_scout_artifact_disposition_contract_version"
                        )
                    ),
                    PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD: experiment.get(
                        PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD
                    ),
                }
            )
    prediction = normalize_prediction(experiment.get("prediction"))
    if prediction:
        row["prediction"] = prediction
        row["calibration"] = build_prediction_calibration(
            prediction,
            judgement,
            decision,
            realized_failure_mode=realized_failure_mode,
            surprise_note=surprise_note,
        )
    row["post_run_reflection"] = {
        "why_result_happened": surprise_note or "TODO",
        "realized_failure_mode": realized_failure_mode,
        "forbidden_near_neighbor_retry": "TODO",
        "new_evidence_required": "TODO",
    }
    return row


def update_result(
    registry,
    experiment_id,
    judgement,
    before_path,
    after_path,
    *,
    status_override=None,
    realized_failure_mode=None,
    surprise_note=None,
    allow_missing_prediction=False,
    log_draft=None,
):
    _require_canonical_experiment_id(experiment_id)
    exp = get_experiment(registry, experiment_id)
    if not exp:
        raise ValueError(f"unknown experiment_id: {experiment_id}")
    if _closed_status(exp.get("status")):
        raise ValueError(
            f"{experiment_id} is already terminal ({exp.get('status')}); "
            "terminal results are immutable"
        )
    decision = final_decision(
        judgement,
        status_override,
        experiment=exp,
    )
    # Close-time validation is independent from claim-time validation.  A
    # promotion artifact changed after claim must not retain authority merely
    # because the ticket was valid earlier.  The one exception is the
    # non-substantive abandonment of a never-claimed reservation: it grants no
    # authority, so it must not re-deadlock on promotion drift or on the claim
    # receipt that a failed claim can never produce.
    if not _is_never_claimed_duplicate_accounting_close(
        exp, decision, realized_failure_mode
    ):
        _revalidate_alpha_promotion_for_claim(registry, exp)
    _require_alpha_promotion_claim_receipt_for_close(
        registry,
        exp,
        decision=decision,
        realized_failure_mode=realized_failure_mode,
    )
    registry_root = _registry_repo_root(registry) or REPO_ROOT
    research_replay = _enforce_research_replay_result_ceiling(
        exp,
        decision,
        artifact_path=after_path,
        repo_root=registry_root,
    )
    require_pre_run_prediction(
        exp,
        allow_missing_prediction=allow_missing_prediction,
    )
    exp["status"] = decision
    exp["completed_at"] = utc_now_iso()
    exp["result"] = {
        "decision": decision,
        "acceptance_reasons": judgement.get("acceptance_reasons") or [],
        "before_result_file": _repo_relative(before_path, registry_root),
        "after_result_file": _repo_relative(after_path, registry_root),
        "delta_metrics": judgement.get("delta_metrics") or {},
        "research_refs": exp.get("research_refs") or [],
    }
    if realized_failure_mode is not None:
        exp["result"]["realized_failure_mode"] = realized_failure_mode
    if research_replay:
        exp["result"].update(research_replay)
        if _private_replay_scout_artifact_contract_required(exp, research_replay):
            if not isinstance(log_draft, dict):
                raise ValueError(
                    f"{experiment_id} private replay closeout requires a "
                    "prevalidated canonical log draft before terminal mutation"
                )
            if isinstance(log_draft, dict):
                exp["result"][PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD] = (
                    _private_replay_scout_log_sha256(log_draft)
                )
    prediction = normalize_prediction(exp.get("prediction"))
    if prediction:
        exp["result"]["calibration"] = build_prediction_calibration(
            prediction,
            judgement,
            decision,
            realized_failure_mode=realized_failure_mode,
            surprise_note=surprise_note,
        )
    if research_replay and isinstance(log_draft, dict):
        _validate_private_replay_scout_log_draft_inputs(
            exp,
            log_draft,
            judgement,
            before_path,
            after_path,
            registry_root,
        )
        _validate_private_replay_scout_ticket_log_binding(
            exp, log_draft, registry_root
        )
    if "_tickets_dir" in registry and not registry.get("_ticket_shard_view"):
        save_ticket(exp, _registry_tickets_dir(registry))
        _sync_index_entry(registry, exp)
    return exp


def _best_effort_cache_upsert(registry_path, ticket, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    """Refresh the docs/experiment_registry.json index entry for one ticket under
    a brief lock. Best-effort: the ticket file is authoritative and the registry
    index is rebuildable from tickets, so a contended/missed refresh must never
    fail an already-durable per-id ticket write."""
    try:
        locked_registry_update(
            registry_path,
            lambda reg: _sync_index_entry(reg, ticket),
            timeout_seconds=timeout_seconds,
        )
    except Exception:
        pass


def _best_effort_full_cache_upsert(
    registry_path, ticket, timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS
):
    """Compatibility cache refresh for legacy self-registering runners.

    Their registry rows historically retained result/prediction fields. Keep
    that read shape while the canonical ticket remains authoritative.
    """

    def _upsert(registry):
        experiments = registry.setdefault("experiments", [])
        for index, existing in enumerate(experiments):
            if existing.get("experiment_id") == ticket.get("experiment_id"):
                experiments[index] = {**existing, **ticket}
                break
        else:
            experiments.append(dict(ticket))
        return _sync_index_entry(registry, ticket)

    try:
        locked_registry_update(
            registry_path, _upsert, timeout_seconds=timeout_seconds
        )
    except Exception:
        pass


def _strict_claim_cache_upsert(
    registry_path,
    experiment_id,
    expected_transition,
    timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
):
    """Finish a post-rollout claim using the latest canonical ticket bytes."""

    context = _file_backed_registry_context(registry_path)
    tickets_dir = _registry_tickets_dir(context)

    def _upsert(registry):
        latest = load_ticket(experiment_id, tickets_dir)
        if latest is None:
            raise ValueError(f"unknown experiment_id: {experiment_id}")
        _validate_experiment_claim_lifecycle(latest)
        if (
            latest.get("status") != "claimed"
            or latest.get(EXPERIMENT_CLAIM_TRANSITION_FIELD)
            != expected_transition
        ):
            raise ValueError(
                f"{experiment_id} canonical claim changed before registry "
                "anchor persistence"
            )
        _validate_strict_persisted_anchors(
            registry,
            latest,
            allow_registry_claim_lag=True,
        )
        return _sync_index_entry(registry, latest)

    return locked_registry_update(
        registry_path,
        _upsert,
        timeout_seconds=timeout_seconds,
    )


def _validate_strict_persisted_anchors(
    registry,
    ticket,
    *,
    allow_registry_claim_lag=False,
    require_terminal_log=False,
):
    """Recheck independent anchors in the exact locked cache snapshot."""

    experiment_id = ticket.get("experiment_id")
    rows = [
        row
        for row in registry.get("experiments", [])
        if isinstance(row, dict) and row.get("experiment_id") == experiment_id
    ]
    if len(rows) != 1:
        raise ValueError(
            f"{experiment_id} strict cache persistence requires exactly one "
            "existing reservation registry row"
        )
    registry_row = rows[0]
    manifest = _load_json_file(
        revision_manifest_path(
            experiment_id, _registry_manifests_dir(registry)
        )
    )
    if not isinstance(manifest, dict) or manifest.get(
        "experiment_id"
    ) != experiment_id:
        raise ValueError(
            f"{experiment_id} strict cache persistence requires its existing "
            "reservation manifest"
        )

    if _experiment_reservation_identity_required(ticket):
        expected_identity = _experiment_reservation_identity(ticket)
        registry_identity = registry_row.get(
            EXPERIMENT_RESERVATION_IDENTITY_FIELD
        )
        manifest_identity = manifest.get(
            EXPERIMENT_RESERVATION_IDENTITY_FIELD
        )
        if (
            not _experiment_reservation_identity_is_valid(registry_identity)
            or registry_identity != expected_identity
            or manifest_identity != expected_identity
        ):
            raise ValueError(
                f"{experiment_id} strict cache persistence found a missing or "
                "changed reservation identity"
            )
        ticket_ever_claimed = ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD)
        registry_ever_claimed = registry_row.get(
            EXPERIMENT_EVER_CLAIMED_FIELD
        )
        manifest_ever_claimed = manifest.get(
            EXPERIMENT_EVER_CLAIMED_FIELD
        )
        if (
            type(ticket_ever_claimed) is not bool
            or type(registry_ever_claimed) is not bool
            or type(manifest_ever_claimed) is not bool
            or (
                not allow_registry_claim_lag
                and registry_ever_claimed is not ticket_ever_claimed
            )
            or manifest_ever_claimed is not ticket_ever_claimed
        ):
            raise ValueError(
                f"{experiment_id} strict cache persistence found inconsistent "
                "ever-claimed anchors"
            )
        if ticket_ever_claimed:
            transition = ticket.get(EXPERIMENT_CLAIM_TRANSITION_FIELD)
            if (
                not _experiment_claim_transition_is_valid(transition, ticket)
                or manifest.get(EXPERIMENT_CLAIM_TRANSITION_FIELD)
                != transition
            ):
                raise ValueError(
                    f"{experiment_id} strict cache persistence requires the "
                    "hash-bound manifest claim transition"
                )

    if _private_replay_scout_contract_indicator(ticket):
        expected_private_identity = _private_replay_scout_registry_identity(
            ticket
        )
        if (
            registry_row.get(PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD)
            != expected_private_identity
            or manifest.get(PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD)
            != expected_private_identity
        ):
            raise ValueError(
                f"{experiment_id} strict cache persistence found a missing or "
                "changed private replay identity"
            )
        result = ticket.get("result")
        expected_log_sha256 = (
            result.get(PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD)
            if isinstance(result, dict)
            else None
        )
        existing_log_sha256 = registry_row.get(
            PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD
        )
        if (
            existing_log_sha256 is not None
            and existing_log_sha256 != expected_log_sha256
        ):
            raise ValueError(
                f"{experiment_id} registry canonical log commitment conflicts "
                "with the terminal ticket"
            )

    if require_terminal_log:
        logs_dir = _registry_logs_dir(registry)
        log_row = _load_json_file(
            experiment_log_path(experiment_id, logs_dir)
        )
        if not isinstance(log_row, dict):
            raise ValueError(
                f"{experiment_id} strict terminal cache persistence requires "
                "the canonical log shard"
            )
        if _experiment_reservation_identity_required(ticket):
            committed_row = _validated_post_rollout_closeout_log_intent(
                ticket, _registry_repo_root(registry)
            )
            if log_row != committed_row:
                raise ValueError(
                    f"{experiment_id} canonical log differs from the terminal "
                    "closeout intent"
                )
        if _private_replay_scout_contract_indicator(ticket):
            _validate_private_replay_scout_ticket_log_binding(
                ticket, log_row, _registry_repo_root(registry)
            )


def _terminal_cache_contract_required(ticket):
    return bool(
        isinstance(ticket, dict)
        and (
            _experiment_reservation_identity_required(ticket)
            or _private_replay_scout_contract_indicator(ticket)
        )
    )


def _strict_terminal_cache_upsert(
    registry_path,
    terminal_ticket,
    timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
):
    """Persist terminal cache commitments or fail with a same-id repair path."""

    experiment_id = terminal_ticket.get("experiment_id")
    expected_status = terminal_ticket.get("status")
    expected_result_hash = _canonical_json_hash(terminal_ticket.get("result"))
    context = _file_backed_registry_context(registry_path)
    tickets_dir = _registry_tickets_dir(context)

    def _upsert(registry):
        latest = load_ticket(experiment_id, tickets_dir)
        if latest is None:
            raise ValueError(f"unknown experiment_id: {experiment_id}")
        if (
            latest.get("status") != expected_status
            or expected_status not in FINAL_STATUSES
            or _canonical_json_hash(latest.get("result")) != expected_result_hash
        ):
            raise ValueError(
                f"{experiment_id} canonical terminal result changed before "
                "registry commitment persistence"
            )
        _validate_experiment_claim_lifecycle(latest)
        _validate_strict_persisted_anchors(
            registry,
            latest,
            require_terminal_log=True,
        )
        return _sync_index_entry(registry, latest)

    return locked_registry_update(
        registry_path,
        _upsert,
        timeout_seconds=timeout_seconds,
    )


def rebuild_registry_from_tickets(registry_path):
    """Build a registry view (workspace dir keys + full ticket dicts) by scanning
    experiments/tickets/*.json, WITHOUT reading docs/experiment_registry.json.

    Tickets are the source of truth; this is the lock-free read view used by
    conflict detection (and any reader that needs guaranteed-fresh data).
    """
    ctx = _file_backed_registry_context(registry_path)
    ctx["_ticket_shard_view"] = True
    tickets_dir = Path(ctx["_tickets_dir"])
    experiments = []
    if tickets_dir.exists():
        for path in sorted(tickets_dir.glob("exp-*.json")):
            try:
                with path.open(encoding="utf-8-sig") as f:
                    ticket = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(ticket, dict) and ticket.get("experiment_id"):
                experiments.append(ticket)
    ctx["experiments"] = experiments
    ctx["_ticket_shard_view"] = True
    return ctx


def _validate_file_backed_reservation_anchors(
    registry_path,
    ticket,
    *,
    allow_incomplete_claim_transition=False,
):
    """Require both reservation-time anchors before a ticket can mutate.

    A claim writes the canonical ticket first so no independent anchor can
    grant authority that the ticket does not yet carry.  A process failure may
    therefore leave the ticket marked claimed while one or both cache anchors
    still carry the reservation-time ``False`` marker.  Only the claim path may
    recognize that narrow, forward-only state and repair it under the same
    per-ticket lock; close and log writers continue to fail closed.

    Returns ``True`` only when that recoverable claim transition is present.
    """

    if _experiment_reservation_clock_invalid(ticket):
        raise ValueError(
            f"{ticket.get('experiment_id')} canonical reservation clock is "
            "malformed"
        )
    if not _experiment_reservation_identity_required(ticket):
        return
    injected_anchor_fields = sorted(
        field
        for field in (
            EXPERIMENT_RESERVATION_IDENTITY_FIELD,
            PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD,
            PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD,
        )
        if field in ticket
    )
    if injected_anchor_fields:
        raise ValueError(
            f"{ticket.get('experiment_id')} canonical ticket cannot carry "
            "registry/manifest-only anchor fields: "
            + ", ".join(injected_anchor_fields)
        )
    _validate_experiment_claim_lifecycle(ticket)
    experiment_id = ticket.get("experiment_id")
    expected_identity = _experiment_reservation_identity(ticket)
    raw_registry = load_registry(registry_path)
    registry_row = next(
        (
            row
            for row in raw_registry.get("experiments", [])
            if isinstance(row, dict) and row.get("experiment_id") == experiment_id
        ),
        None,
    )
    context = _file_backed_registry_context(registry_path)
    manifest = _load_json_file(
        revision_manifest_path(
            experiment_id,
            _registry_manifests_dir(context),
        )
    )
    registry_identity = (
        registry_row.get(EXPERIMENT_RESERVATION_IDENTITY_FIELD)
        if isinstance(registry_row, dict)
        else None
    )
    manifest_identity = (
        manifest.get(EXPERIMENT_RESERVATION_IDENTITY_FIELD)
        if isinstance(manifest, dict)
        and manifest.get("experiment_id") == experiment_id
        else None
    )
    if (
        not _experiment_reservation_identity_is_valid(registry_identity)
        or not _experiment_reservation_identity_is_valid(manifest_identity)
        or registry_identity != manifest_identity
        or registry_identity != expected_identity
    ):
        raise ValueError(
            f"{experiment_id} reservation-time registry/manifest identity "
            "is missing or does not match the canonical ticket"
        )
    registry_ever_claimed = registry_row.get(EXPERIMENT_EVER_CLAIMED_FIELD)
    manifest_ever_claimed = manifest.get(EXPERIMENT_EVER_CLAIMED_FIELD)
    ticket_ever_claimed = ticket.get(EXPERIMENT_EVER_CLAIMED_FIELD)
    markers_are_boolean = (
        type(registry_ever_claimed) is bool
        and type(manifest_ever_claimed) is bool
        and type(ticket_ever_claimed) is bool
    )
    marker_state = (
        ticket_ever_claimed,
        manifest_ever_claimed,
        registry_ever_claimed,
    )
    incomplete_claim_transition = bool(
        allow_incomplete_claim_transition
        and markers_are_boolean
        and ticket.get("status") == "claimed"
        and marker_state in {
            (True, False, False),
            (True, True, False),
        }
    )
    if not markers_are_boolean or (
        not incomplete_claim_transition
        and (
            registry_ever_claimed != manifest_ever_claimed
            or registry_ever_claimed != ticket_ever_claimed
        )
    ):
        raise ValueError(
            f"{experiment_id} ever-claimed lifecycle anchors are missing or "
            "inconsistent"
        )
    if ticket_ever_claimed:
        ticket_claim_transition = ticket.get(
            EXPERIMENT_CLAIM_TRANSITION_FIELD
        )
        manifest_claim_transition = manifest.get(
            EXPERIMENT_CLAIM_TRANSITION_FIELD
        )
        if (
            not _experiment_claim_transition_is_valid(
                ticket_claim_transition, ticket
            )
            or manifest_claim_transition != ticket_claim_transition
        ):
            raise ValueError(
                f"{experiment_id} claim recovery requires its independent, "
                "hash-bound manifest transition intent"
            )
    if _private_replay_scout_contract_indicator(ticket):
        expected_private_identity = _private_replay_scout_registry_identity(ticket)
        registry_private_identity = registry_row.get(
            PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD
        )
        manifest_private_identity = manifest.get(
            PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD
        )
        if (
            not _private_replay_scout_registry_identity_is_valid(
                registry_private_identity
            )
            or registry_private_identity != manifest_private_identity
            or registry_private_identity != expected_private_identity
        ):
            raise ValueError(
                f"{experiment_id} reservation-time private replay identity "
                "is missing or does not match the canonical ticket"
            )
    return incomplete_claim_transition


def claim_experiment_decontended(registry_path, experiment_id, owner, *, force=False,
                                 timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    """Claim a ticket without the global registry lock (registry-decontention
    step 2). The cross-experiment conflict view is read lock-free from tickets
    (advisory; a few-ms-stale overlap view is acceptable); the claim mutation is
    serialized by a per-id ticket lock so two agents cannot both claim the same
    id.  Post-rollout claims return only after the ticket, manifest, and
    registry lifecycle anchors all record the monotonic claim transition."""
    view = rebuild_registry_from_tickets(registry_path)
    tickets_dir = Path(view["_tickets_dir"])
    target = ticket_path(experiment_id, tickets_dir)
    should_refresh_cache = False
    strict_transition = None
    with file_lock(target, timeout_seconds=timeout_seconds):
        current = load_ticket(experiment_id, tickets_dir)
        if current is None:
            raise ValueError(f"unknown experiment_id: {experiment_id}")
        incomplete_claim_transition = _validate_file_backed_reservation_anchors(
            registry_path,
            current,
            allow_incomplete_claim_transition=True,
        )
        view["experiments"] = [
            e for e in view["experiments"]
            if e.get("experiment_id") != experiment_id
        ]
        view["experiments"].append(current)
        if incomplete_claim_transition:
            if current.get("owner") != owner:
                raise ValueError(
                    f"{experiment_id} interrupted claim belongs to "
                    f"{current.get('owner')!r}; recovery by {owner!r} is forbidden"
                )
            # Re-run admission against current bytes. The persisted transition
            # proves a real claim attempt reached the manifest-intent step, but
            # it must not preserve stale promotion authority or hide a new
            # conflicting active scope.
            _revalidate_alpha_promotion_for_claim(view, current)
            recovery_conflicts = find_conflicts(view, current)
            transition = current[EXPERIMENT_CLAIM_TRANSITION_FIELD]
            if recovery_conflicts and not transition.get("force"):
                raise ValueError(
                    f"{experiment_id} interrupted claim recovery is blocked by "
                    "current scope conflicts"
                )
            save_revision_manifest(
                current,
                _registry_manifests_dir(view),
                repo_root=_registry_repo_root(view),
                ticket_file=target,
                card_file=experiment_card_path(
                    experiment_id, _registry_cards_dir(view)
                ),
            )
            ticket = current
            conflicts = []
            strict_transition = transition
        elif current.get("status") == "claimed":
            # A complete same-owner claim is idempotent. claim_ticket still
            # revalidates live promotion/receipt bytes and rejects owner
            # takeover, but no reservation anchor may be rewritten.
            return claim_ticket(
                view, experiment_id, owner, force=force
            )
        else:
            ticket, conflicts = claim_ticket(
                view, experiment_id, owner, force=force
            )
            if not conflicts or force:
                if _experiment_reservation_identity_required(ticket):
                    _save_claim_transition_manifest_intent(
                        ticket,
                        _registry_manifests_dir(view),
                    )
                save_ticket(ticket, tickets_dir)
                if _experiment_reservation_identity_required(ticket):
                    save_revision_manifest(
                        ticket,
                        _registry_manifests_dir(view),
                        repo_root=_registry_repo_root(view),
                        ticket_file=target,
                        card_file=experiment_card_path(
                            experiment_id, _registry_cards_dir(view)
                        ),
                    )
                    strict_transition = ticket[
                        EXPERIMENT_CLAIM_TRANSITION_FIELD
                    ]
                else:
                    should_refresh_cache = True
    if strict_transition is not None:
        _strict_claim_cache_upsert(
            registry_path,
            experiment_id,
            strict_transition,
            timeout_seconds,
        )
        latest = load_ticket(experiment_id, tickets_dir)
        if latest is None:
            raise ValueError(f"unknown experiment_id: {experiment_id}")
        _validate_file_backed_reservation_anchors(registry_path, latest)
        ticket = latest
    elif should_refresh_cache:
        _best_effort_cache_upsert(registry_path, ticket, timeout_seconds)
    return ticket, conflicts


def update_result_decontended(registry_path, experiment_id, judgement, before_path,
                              after_path, *, status_override=None,
                              realized_failure_mode=None, surprise_note=None,
                              allow_missing_prediction=False,
                              log_draft=None,
                              timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    """Record an experiment result without the global registry lock (step 2).
    Close touches a single ticket, so a per-id ticket lock fully serializes it.
    Contract-governed closes persist an exact recoverable shard before their
    mandatory terminal cache commitment."""
    ctx = _file_backed_registry_context(registry_path)
    ctx["_ticket_shard_view"] = True
    tickets_dir = Path(ctx["_tickets_dir"])
    target = ticket_path(experiment_id, tickets_dir)
    log_row_to_persist = None
    terminal_repair = False
    with file_lock(target, timeout_seconds=timeout_seconds):
        current = load_ticket(experiment_id, tickets_dir)
        if current is None:
            raise ValueError(f"unknown experiment_id: {experiment_id}")
        _validate_file_backed_reservation_anchors(registry_path, current)
        effective_log_draft = log_draft
        if (
            effective_log_draft is None
            and (
                _private_replay_scout_contract_indicator(current)
                or _experiment_reservation_identity_required(current)
            )
        ):
            finish_intent = current.get("alpha_workflow_finish_intent")
            intent_log_row = (
                finish_intent.get("log_row")
                if isinstance(finish_intent, dict)
                else None
            )
            if (
                isinstance(intent_log_row, dict)
                and finish_intent.get("log_row_hash")
                == _compact_canonical_json_hash(intent_log_row)
            ):
                effective_log_draft = intent_log_row
        if (
            _experiment_reservation_identity_required(current)
            and not isinstance(effective_log_draft, dict)
        ):
            raise ValueError(
                f"{experiment_id} post-rollout closeout requires a "
                "prevalidated canonical log draft before terminal mutation"
            )
        terminal_repair = bool(
            _terminal_cache_contract_required(current)
            and current.get("status") in FINAL_STATUSES
        )
        if terminal_repair:
            _validate_terminal_close_retry_inputs(
                current,
                judgement,
                before_path,
                after_path,
                status_override=status_override,
                realized_failure_mode=realized_failure_mode,
                repo_root=registry_workspace_root(registry_path),
            )
            if _experiment_reservation_identity_required(current):
                log_row_to_persist = (
                    _validated_post_rollout_closeout_log_intent(
                        current, registry_workspace_root(registry_path)
                    )
                )
            elif _private_replay_scout_contract_indicator(current):
                _validate_private_replay_scout_ticket_log_binding(
                    current,
                    effective_log_draft,
                    registry_workspace_root(registry_path),
                )
                log_row_to_persist = strip_oversized_fields(
                    effective_log_draft
                )
            else:
                _validate_post_rollout_ticket_log_mirror(
                    current, effective_log_draft
                )
                log_row_to_persist = strip_oversized_fields(
                    effective_log_draft
                )
            exp = current
        else:
            ctx["experiments"] = [current]
            exp = update_result(
                ctx,
                experiment_id,
                judgement,
                before_path,
                after_path,
                status_override=status_override,
                realized_failure_mode=realized_failure_mode,
                surprise_note=surprise_note,
                allow_missing_prediction=allow_missing_prediction,
                log_draft=effective_log_draft,
            )
            if _experiment_reservation_identity_required(exp):
                _validate_post_rollout_ticket_log_mirror(
                    exp, effective_log_draft
                )
                log_row_to_persist = _bind_post_rollout_closeout_log_intent(
                    exp, effective_log_draft
                )
            elif _private_replay_scout_contract_indicator(exp):
                log_row_to_persist = strip_oversized_fields(
                    effective_log_draft
                )
            if isinstance(log_row_to_persist, dict):
                canonical_log_path = experiment_log_path(
                    experiment_id,
                    registry_workspace_root(registry_path)
                    / "experiments"
                    / "logs",
                )
                if canonical_log_path.exists():
                    existing_log_row = _load_json_file(canonical_log_path)
                    if existing_log_row != log_row_to_persist:
                        raise ValueError(
                            f"{experiment_id} existing canonical log conflicts "
                            "with the terminal closeout candidate"
                        )
            _validate_experiment_claim_lifecycle(exp)
            save_ticket(exp, tickets_dir)
    if _terminal_cache_contract_required(exp):
        if not isinstance(log_row_to_persist, dict):
            raise ValueError(
                f"{experiment_id} contract-governed terminal close requires "
                "an exact canonical log row"
            )
        save_experiment_log_entry(
            log_row_to_persist,
            expected_experiment_id=experiment_id,
            logs_dir=registry_workspace_root(registry_path)
            / "experiments"
            / "logs",
            registry_path=registry_path,
            timeout_seconds=timeout_seconds,
        )
        _strict_terminal_cache_upsert(registry_path, exp, timeout_seconds)
    else:
        _best_effort_cache_upsert(registry_path, exp, timeout_seconds)
    _sync_research_digest_quietly(
        exp,
        exp.get("status"),
        repo_root=registry_workspace_root(registry_path),
        reason="experiment closeout propagated by experiment.py close",
    )
    return exp


def persist_self_registered_result(
    registry_path,
    *,
    experiment_id,
    lane,
    prediction,
    result,
    status,
    fields=None,
    allow_missing_prediction=False,
    timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS,
):
    """Sanctioned path for runners that compute their own before/after result and
    persist it themselves, instead of writing ``docs/experiment_registry.json``
    by hand.

    Hand-rolled self-registration historically bypassed
    ``require_pre_run_prediction`` and dropped the ``prediction`` from the
    persisted record (it survived only in the log), so the audit reported
    ``missing_prediction`` even when the agent had predicted. This helper closes
    both holes: it REQUIRES a pre-run prediction for prediction-required lanes and
    PROPAGATES the normalized prediction onto the upserted registry entry and
    ticket.

    ``fields`` is an optional dict of extra ticket fields to persist
    (``change_type``, ``mechanism_family``, ``trial_family``,
    ``single_causal_variable``, etc.). Non-prediction-required lanes are accepted
    without a prediction, matching ``require_pre_run_prediction``.
    """
    _require_canonical_experiment_id(experiment_id)
    if isinstance(fields, dict):
        forbidden = sorted(
            key
            for key in _SELF_REGISTER_FORBIDDEN_INPUT_FIELDS
            if key in fields and fields[key] is not None
        )
        if forbidden:
            raise ValueError(
                f"{experiment_id} self-registration fields cannot set lifecycle/"
                f"identity keys: {', '.join(forbidden)}"
            )

    normalized = normalize_prediction(prediction)
    require_pre_run_prediction(
        {"experiment_id": experiment_id, "lane": lane, "prediction": normalized},
        allow_missing_prediction=allow_missing_prediction,
    )
    require_pre_run_prediction_quality(
        {"experiment_id": experiment_id, "lane": lane, "prediction": normalized},
        allow_missing_prediction=allow_missing_prediction,
    )

    workspace_root = registry_workspace_root(registry_path)
    registry = _file_backed_registry_context(registry_path)
    tickets_dir = Path(registry["_tickets_dir"])
    target = ticket_path(experiment_id, tickets_dir)
    canonical_log_row = None
    terminal_repair_log_row = None

    # Reject brand-new post-rollout self-registration before file_lock creates
    # the ticket directory or lock sidecar. The guarded check is repeated after
    # locking below; this read-only fast path only removes an avoidable durable
    # side effect from a request that can never be authorized.
    if not target.exists():
        preflight_registry = load_registry(registry_path)
        preflight_existing = next(
            (
                row
                for row in preflight_registry.get("experiments", [])
                if isinstance(row, dict)
                and row.get("experiment_id") == experiment_id
            ),
            None,
        )
        if preflight_existing is None and _experiment_reservation_identity_required(
            {"experiment_id": experiment_id, "created_at": utc_now_iso()}
        ):
            if (
                _alpha_promotion_gate_enabled(preflight_registry)
                and _alpha_promotion_required_for_lane(lane)
            ):
                raise ValueError(
                    f"{experiment_id} cannot self-register new alpha work: "
                    "reserve and claim a promotion-anchored ticket first"
                )
            raise ValueError(
                f"{experiment_id} cannot self-register a new post-rollout "
                "experiment; reserve its registry and manifest identity first"
            )

    # If a prior self-register attempt durably wrote both terminal sources but
    # failed while committing the registry cache, the same input may repair the
    # cache without rewriting either immutable source.
    terminal_repair = None
    if target.exists():
        with file_lock(target, timeout_seconds=timeout_seconds):
            repair_candidate = load_ticket(experiment_id, tickets_dir)
            if (
                _terminal_cache_contract_required(repair_candidate)
                and repair_candidate.get("status") in FINAL_STATUSES
            ):
                _validate_file_backed_reservation_anchors(
                    registry_path, repair_candidate
                )
                if status != repair_candidate.get("status") or lane != repair_candidate.get(
                    "lane"
                ):
                    raise ValueError(
                        f"{experiment_id} terminal results are immutable; "
                        "repair status/lane does not match the canonical ticket"
                    )
                canonical_result = repair_candidate.get("result")
                if not isinstance(result, dict) or not isinstance(
                    canonical_result, dict
                ) or any(
                    canonical_result.get(key) != value
                    for key, value in result.items()
                ):
                    raise ValueError(
                        f"{experiment_id} is already terminal and terminal "
                        "results are immutable; repair input does not match "
                        "the canonical result"
                    )
                if isinstance(fields, dict) and any(
                    value is not None and repair_candidate.get(key) != value
                    for key, value in fields.items()
                ):
                    raise ValueError(
                        f"{experiment_id} terminal repair fields do not match "
                        "the canonical ticket"
                    )
                if _experiment_reservation_identity_required(
                    repair_candidate
                ):
                    terminal_repair_log_row = (
                        _validated_post_rollout_closeout_log_intent(
                            repair_candidate, workspace_root
                        )
                    )
                else:
                    repair_log_path = experiment_log_path(
                        experiment_id,
                        workspace_root / "experiments" / "logs",
                    )
                    repair_log = _load_json_file(repair_log_path)
                    if not isinstance(repair_log, dict):
                        raise ValueError(
                            f"{experiment_id} terminal repair requires its "
                            "existing canonical log shard"
                        )
                    terminal_repair_log_row = repair_log
                terminal_repair = repair_candidate
    if terminal_repair is not None:
        save_experiment_log_entry(
            terminal_repair_log_row,
            expected_experiment_id=experiment_id,
            logs_dir=workspace_root / "experiments" / "logs",
            registry_path=registry_path,
            timeout_seconds=timeout_seconds,
        )
        _strict_terminal_cache_upsert(
            registry_path, terminal_repair, timeout_seconds
        )
        return terminal_repair

    # Standard close and self-registration share this exact per-ticket lock.
    # Reload only after acquiring it so a stale runner cannot overwrite a
    # terminal result committed by the other close path.
    with file_lock(target, timeout_seconds=timeout_seconds):
        canonical_existing = load_ticket(experiment_id, tickets_dir)
        if canonical_existing is not None:
            _validate_file_backed_reservation_anchors(
                registry_path, canonical_existing
            )
        raw_registry = load_registry(registry_path)
        raw_existing = next(
            (
                row
                for row in raw_registry.get("experiments", [])
                if isinstance(row, dict)
                and row.get("experiment_id") == experiment_id
            ),
            None,
        )
        if canonical_existing is not None:
            existing = canonical_existing
        elif isinstance(raw_existing, dict) and (
            raw_existing.get("ticket_file")
            or _private_replay_scout_contract_indicator(raw_existing)
        ):
            raise ValueError(
                f"{experiment_id} self-registration requires its exact canonical "
                "workspace ticket shard"
            )
        else:
            # Compatibility only for old registry-only, non-contract runners.
            existing = raw_existing

        if (
            canonical_existing is None
            and isinstance(existing, dict)
            and _experiment_reservation_identity_required(existing)
        ):
            raise ValueError(
                f"{experiment_id} post-rollout self-registration requires its "
                "reservation-time canonical ticket, registry, and manifest anchors"
            )

        now = utc_now_iso()
        existing_lane = existing.get("lane") if existing is not None else None
        existing_research_replay = (
            _research_replay_metadata(existing) if existing is not None else None
        )
        existing_private_contract = bool(
            existing is not None
            and _private_replay_scout_contract_indicator(existing)
        )
        registry["experiments"] = [existing] if existing is not None else []

        if existing is not None:
            if canonical_existing is not None and _closed_status(
                canonical_existing.get("status")
            ):
                raise ValueError(
                    f"{experiment_id} canonical ticket is already terminal "
                    f"({canonical_existing.get('status')}); terminal results "
                    "are immutable"
                )
            _require_alpha_promotion_claim_receipt_for_close(registry, existing)
            if existing_lane is not None and lane != existing_lane:
                raise ValueError(
                    f"{experiment_id} cannot change lane during self-registered closeout: "
                    f"{existing_lane!r} -> {lane!r}"
                )
            if isinstance(fields, dict):
                for key in sorted(_SELF_REGISTER_IMMUTABLE_EXISTING_FIELDS):
                    if (
                        key in fields
                        and fields[key] is not None
                        and fields[key] != existing.get(key)
                    ):
                        raise ValueError(
                            f"{experiment_id} cannot overwrite immutable existing "
                            f"ticket field {key!r} during closeout"
                        )

        if (
            _alpha_promotion_gate_enabled(registry)
            and _alpha_promotion_required_for_lane(lane)
            and existing is None
        ):
            probe = {
                "experiment_id": experiment_id,
                "lane": lane,
                "created_at": now,
            }
            if _ticket_is_post_alpha_promotion_enforcement(probe):
                raise ValueError(
                    f"{experiment_id} cannot self-register new alpha work: "
                    "reserve and claim a promotion-anchored ticket first"
                )
        if existing is None and _experiment_reservation_identity_required(
            {"experiment_id": experiment_id, "created_at": now}
        ):
            raise ValueError(
                f"{experiment_id} cannot self-register a new post-rollout "
                "experiment; reserve its registry and manifest identity first"
            )

        exp = dict(existing) if existing is not None else {
            "experiment_id": experiment_id
        }
        exp.setdefault("created_at", now)
        if isinstance(fields, dict):
            for key, value in fields.items():
                if value is not None:
                    exp[key] = value
        if exp.get("experiment_id") != experiment_id:
            raise ValueError(
                f"{experiment_id} self-registration cannot redirect canonical identity"
            )
        _require_canonical_experiment_id(exp.get("experiment_id"))
        exp["lane"] = lane

        if existing_research_replay is not None and _research_replay_metadata(exp) is None:
            raise ValueError(
                f"{experiment_id} cannot remove its research_replay admission during closeout"
            )
        if existing is not None and (
            _alpha_promotion_required_for_lane(existing_lane)
            or _alpha_promotion_required_for_lane(lane)
            or existing_private_contract
            or existing_research_replay is not None
        ):
            _revalidate_alpha_promotion_for_claim(registry, exp)

        research_replay = _enforce_research_replay_result_ceiling(
            exp,
            status,
            result=result,
            repo_root=workspace_root,
        )
        exp["status"] = status
        if normalized:
            exp["prediction"] = normalized
        stored_result = dict(result) if isinstance(result, dict) else result
        if research_replay and isinstance(stored_result, dict):
            stored_result.update(research_replay)
        private_contract = bool(
            research_replay
            and _private_replay_scout_artifact_contract_required(
                exp, research_replay
            )
        )
        if private_contract:
            canonical_log_row = {
                **stored_result,
                "experiment_id": experiment_id,
                "experiment_uid": exp.get("experiment_uid"),
                "timestamp": now,
                "status": status,
                "decision": status,
                "change_type": exp.get("change_type"),
                "alpha_promotion": exp.get("alpha_promotion"),
                "research_refs": exp.get("research_refs"),
                "private_replay_scout_artifact_disposition_contract_version": (
                    exp.get(
                        "private_replay_scout_artifact_disposition_contract_version"
                    )
                ),
                PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD: exp.get(
                    PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD
                ),
            }
            stored_result[PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD] = (
                _private_replay_scout_log_sha256(canonical_log_row)
            )
        elif _experiment_reservation_identity_required(exp):
            canonical_log_row = {
                **(stored_result if isinstance(stored_result, dict) else {}),
                "experiment_id": experiment_id,
                "experiment_uid": exp.get("experiment_uid"),
                "timestamp": now,
                "status": status,
                "decision": status,
                "lane": exp.get("lane"),
                "change_type": exp.get("change_type"),
            }
        exp["result"] = stored_result
        exp["updated_at"] = now
        exp["completed_at"] = now
        if _experiment_reservation_identity_required(exp):
            if exp.get("status") not in FINAL_STATUSES:
                raise ValueError(
                    f"{experiment_id} self-registered terminal status must be "
                    f"one of {sorted(FINAL_STATUSES)}"
                )
            if not isinstance(stored_result, dict) or stored_result.get(
                "decision"
            ) != exp.get("status"):
                raise ValueError(
                    f"{experiment_id} self-registered result.decision must "
                    "exactly mirror the terminal ticket status"
                )
            _validate_experiment_claim_lifecycle(exp)
            if canonical_existing is not None:
                _validate_file_backed_reservation_anchors(registry_path, exp)
        if private_contract:
            _validate_private_replay_scout_ticket_log_binding(
                exp, canonical_log_row, workspace_root
            )
        if _experiment_reservation_identity_required(exp):
            canonical_log_row = _bind_post_rollout_closeout_log_intent(
                exp, canonical_log_row
            )
        if isinstance(canonical_log_row, dict):
            canonical_log_path = experiment_log_path(
                experiment_id,
                workspace_root / "experiments" / "logs",
            )
            if canonical_log_path.exists():
                existing_log_row = _load_json_file(canonical_log_path)
                expected_log_row = strip_oversized_fields(canonical_log_row)
                if existing_log_row != expected_log_row:
                    raise ValueError(
                        f"{experiment_id} existing canonical log conflicts with "
                        "the self-registered terminal candidate"
                    )
        save_ticket(exp, tickets_dir, overwrite=canonical_existing is not None)

    if isinstance(canonical_log_row, dict):
        save_experiment_log_entry(
            canonical_log_row,
            expected_experiment_id=experiment_id,
            logs_dir=workspace_root / "experiments" / "logs",
            registry_path=registry_path,
            timeout_seconds=timeout_seconds,
        )
    if _terminal_cache_contract_required(exp):
        _strict_terminal_cache_upsert(registry_path, exp, timeout_seconds)
    else:
        _best_effort_full_cache_upsert(registry_path, exp, timeout_seconds)
    return exp


def _load_json_file(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _closed_status(value):
    status = str(value or "").strip().lower()
    return status in FINAL_STATUSES or status.startswith(
        ("accepted", "rejected", "observed_only")
    )


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _experiment_id_date(experiment_id):
    normalized = normalize_experiment_id(experiment_id)
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized[4:12], "%Y%m%d").date()
    except ValueError:
        return None


def _prediction_enforcement_datetime():
    parsed = _parse_iso_datetime(PREDICTION_ENFORCEMENT_STARTED_AT)
    if parsed is None:
        raise ValueError("invalid PREDICTION_ENFORCEMENT_STARTED_AT")
    return parsed


def _lean_quality_enforcement_datetime():
    parsed = _parse_iso_datetime(LEAN_QUALITY_ENFORCEMENT_STARTED_AT)
    if parsed is None:
        raise ValueError("invalid LEAN_QUALITY_ENFORCEMENT_STARTED_AT")
    return parsed


def _lean_hard_integrity_enforcement_datetime():
    parsed = _parse_iso_datetime(LEAN_HARD_INTEGRITY_ENFORCEMENT_STARTED_AT)
    if parsed is None:
        raise ValueError("invalid LEAN_HARD_INTEGRITY_ENFORCEMENT_STARTED_AT")
    return parsed


def _enforcement_bucket(ticket, cutoff):
    """Classify prediction gaps as legacy or post-enforcement.

    Missing timestamps are treated as legacy because we cannot prove the agent
    saw the new code-enforced rule. A future-dated experiment ID still counts
    as post-enforcement even when a hand-written stub omits timestamps.
    """
    for field in ("created_at", "reserved_at", "updated_at", "claimed_at", "completed_at"):
        parsed = _parse_iso_datetime(ticket.get(field))
        if parsed is not None:
            return (
                "post_enforcement"
                if parsed >= cutoff
                else "legacy_pre_enforcement"
            )

    hub_identity = ticket.get("hub_identity") or {}
    parsed = _parse_iso_datetime(hub_identity.get("reserved_at"))
    if parsed is not None:
        return "post_enforcement" if parsed >= cutoff else "legacy_pre_enforcement"

    experiment_date = _experiment_id_date(ticket.get("experiment_id"))
    if experiment_date and experiment_date > cutoff.date():
        return "post_enforcement"
    return "legacy_pre_enforcement"


def prediction_enforcement_bucket(ticket):
    """Classify prediction-presence gaps against the original cutoff."""
    return _enforcement_bucket(ticket, _prediction_enforcement_datetime())


def lean_quality_enforcement_bucket(ticket):
    """Classify lean quality gaps without blocking historical process debt."""
    return _enforcement_bucket(ticket, _lean_quality_enforcement_datetime())


def _reservation_identity_audit_violations(
    experiment_id,
    registry_row,
    canonical_row,
    manifest,
    *,
    ticket_path_value,
    manifest_path_value,
    require_persisted_anchors,
):
    source = canonical_row or registry_row or {"experiment_id": experiment_id}
    violations = []

    def add(record_type, path, error, declared_id=None):
        violations.append(
            {
                "record_type": record_type,
                "path": str(path),
                "canonical_experiment_id": experiment_id,
                "declared_experiment_id": declared_id,
                "enforcement_bucket": "post_enforcement",
                "error": error,
            }
        )

    invalid_clock = bool(
        require_persisted_anchors
        and _experiment_reservation_clock_invalid(source)
    )
    anchored = bool(
        _experiment_reservation_identity_required(source)
        or any(
            isinstance(row, dict)
            and any(
                field in row
                for field in (
                    EXPERIMENT_RESERVATION_IDENTITY_FIELD,
                    EXPERIMENT_EVER_CLAIMED_FIELD,
                    EXPERIMENT_CLAIM_TRANSITION_FIELD,
                    EXPERIMENT_CLOSEOUT_LOG_INTENT_FIELD,
                    EXPERIMENT_CLOSEOUT_LOG_INTENT_SHA256_FIELD,
                )
            )
            for row in (registry_row, manifest)
        )
    )
    if invalid_clock:
        add(
            "reservation_clock",
            ticket_path_value,
            "canonical reservation clock is malformed",
            source.get("experiment_id") if isinstance(source, dict) else None,
        )
    if not anchored:
        return violations

    full_snapshot_fields = {
        "experiment_uid",
        "change_type",
        "allowed_write_scope",
        "must_not_touch",
    }
    registry_is_full = bool(
        isinstance(registry_row, dict)
        and full_snapshot_fields.issubset(registry_row)
    )
    registry_identity = (
        registry_row.get(EXPERIMENT_RESERVATION_IDENTITY_FIELD)
        if isinstance(registry_row, dict)
        else None
    )
    if (
        registry_identity is None
        and registry_is_full
        and not require_persisted_anchors
    ):
        registry_identity = _experiment_reservation_identity(registry_row)
    if registry_identity is None:
        add(
            "registry_reservation_identity",
            ticket_path_value,
            "future canonical ticket is missing its registry reservation identity",
            registry_row.get("experiment_id") if isinstance(registry_row, dict) else None,
        )
    elif not _experiment_reservation_identity_is_valid(registry_identity):
        add(
            "registry_reservation_identity",
            ticket_path_value,
            "invalid experiment registry reservation identity snapshot",
            registry_row.get("experiment_id") if isinstance(registry_row, dict) else None,
        )

    manifest_identity = (
        manifest.get(EXPERIMENT_RESERVATION_IDENTITY_FIELD)
        if isinstance(manifest, dict)
        and manifest.get("experiment_id") == experiment_id
        else None
    )
    manifest_required = (
        require_persisted_anchors or not registry_is_full or registry_row is None
    )
    if manifest_identity is None and manifest_required:
        add(
            "manifest_reservation_identity",
            manifest_path_value,
            "future canonical ticket is missing its manifest reservation identity",
            manifest.get("experiment_id") if isinstance(manifest, dict) else None,
        )
    elif manifest_identity is not None and not _experiment_reservation_identity_is_valid(
        manifest_identity
    ):
        add(
            "manifest_reservation_identity",
            manifest_path_value,
            "invalid experiment manifest reservation identity snapshot",
            manifest.get("experiment_id") if isinstance(manifest, dict) else None,
        )

    if (
        registry_identity is not None
        and manifest_identity is not None
        and registry_identity != manifest_identity
    ):
        add(
            "manifest_reservation_identity",
            manifest_path_value,
            "registry/manifest reservation identity mismatch",
            manifest.get("experiment_id") if isinstance(manifest, dict) else None,
        )
    if isinstance(canonical_row, dict):
        actual_identity = _experiment_reservation_identity(canonical_row)
        for label, identity, path in (
            ("registry", registry_identity, ticket_path_value),
            ("manifest", manifest_identity, manifest_path_value),
        ):
            if identity is not None and identity != actual_identity:
                add(
                    f"{label}_reservation_identity",
                    path,
                    f"{label}/ticket reservation identity mismatch",
                    canonical_row.get("experiment_id"),
                )
        try:
            _validate_experiment_claim_lifecycle(canonical_row)
        except ValueError as exc:
            add(
                "ticket_claim_lifecycle",
                ticket_path_value,
                str(exc),
                canonical_row.get("experiment_id"),
            )

    ticket_ever_claimed = (
        canonical_row.get(EXPERIMENT_EVER_CLAIMED_FIELD)
        if isinstance(canonical_row, dict)
        else None
    )
    registry_ever_claimed = (
        registry_row.get(EXPERIMENT_EVER_CLAIMED_FIELD)
        if isinstance(registry_row, dict)
        else None
    )
    manifest_ever_claimed = (
        manifest.get(EXPERIMENT_EVER_CLAIMED_FIELD)
        if isinstance(manifest, dict)
        else None
    )
    required_markers = [ticket_ever_claimed, registry_ever_claimed]
    if manifest_required or manifest_identity is not None:
        required_markers.append(manifest_ever_claimed)
    if any(type(value) is not bool for value in required_markers):
        add(
            "ticket_claim_lifecycle",
            ticket_path_value,
            "future ticket is missing an exact ever-claimed lifecycle anchor",
            canonical_row.get("experiment_id") if isinstance(canonical_row, dict) else None,
        )
    elif len(set(required_markers)) != 1:
        add(
            "ticket_claim_lifecycle",
            ticket_path_value,
            "ticket/registry/manifest ever-claimed lifecycle mismatch",
            canonical_row.get("experiment_id") if isinstance(canonical_row, dict) else None,
        )
    elif isinstance(canonical_row, dict):
        ticket_transition = canonical_row.get(
            EXPERIMENT_CLAIM_TRANSITION_FIELD
        )
        manifest_transition = (
            manifest.get(EXPERIMENT_CLAIM_TRANSITION_FIELD)
            if isinstance(manifest, dict)
            else None
        )
        if ticket_ever_claimed:
            if (
                not _experiment_claim_transition_is_valid(
                    ticket_transition, canonical_row
                )
                or (
                    (manifest_required or manifest_identity is not None)
                    and manifest_transition != ticket_transition
                )
            ):
                add(
                    "ticket_claim_transition",
                    manifest_path_value,
                    "ever-claimed ticket is missing its exact hash-bound "
                    "manifest claim transition",
                    canonical_row.get("experiment_id"),
                )
        elif manifest_transition is not None:
            expected_identity = _experiment_reservation_identity(canonical_row)
            if (
                not _experiment_claim_transition_payload_is_valid(
                    manifest_transition
                )
                or manifest_transition.get("experiment_id") != experiment_id
                or manifest_transition.get("experiment_uid")
                != canonical_row.get("experiment_uid")
                or manifest_transition.get("reservation_identity_hash")
                != expected_identity.get("identity_hash")
            ):
                add(
                    "manifest_claim_transition",
                    manifest_path_value,
                    "unclaimed manifest carries an invalid claim transition "
                    "intent residue",
                    canonical_row.get("experiment_id"),
                )
    return violations


def _ticket_records_for_audit(
    registry,
    tickets_dir=DEFAULT_TICKETS_DIR,
    *,
    require_persisted_reservation_anchors=False,
):
    records = {}
    registry_records = {}
    canonical_ticket_rows = {}
    canonical_ticket_file_ids = set()
    identity_violations = []
    tickets_path = Path(tickets_dir).resolve()
    audit_repo_root = tickets_path.parent.parent
    manifests_path = tickets_path.parent / "manifests"
    expected_ticket_prefix = Path("experiments") / "tickets"

    # The registry is an independent provenance snapshot, not a path-following
    # loader.  Never materialize its mutable ticket_file here: doing so can make
    # registry id A disappear by redirecting it to ticket B (or outside a custom
    # workspace).  Canonical shards are loaded independently below.
    for raw in registry.get("experiments", []):
        if not isinstance(raw, dict):
            continue
        experiment_id = raw.get("experiment_id")
        if not experiment_id:
            continue
        registry_records[experiment_id] = raw
        records[experiment_id] = dict(raw)
        ticket_file = raw.get("ticket_file")
        expected_ticket_file = (
            expected_ticket_prefix / f"{experiment_id}.json"
        ).as_posix()
        pointer_is_exact = ticket_file == expected_ticket_file
        if isinstance(ticket_file, str) and Path(ticket_file).is_absolute():
            try:
                pointer_is_exact = (
                    Path(ticket_file).resolve()
                    == (tickets_path / f"{experiment_id}.json").resolve()
                )
            except OSError:
                pointer_is_exact = False
        if ticket_file is not None and not pointer_is_exact:
            identity_violations.append(
                {
                    "record_type": "registry_ticket_pointer",
                    "path": str(ticket_file),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": experiment_id,
                    "enforcement_bucket": _canonical_record_enforcement_bucket(
                        raw, experiment_id
                    ),
                    "error": (
                        "registry ticket_file must equal its exact workspace "
                        f"canonical path {expected_ticket_file}"
                    ),
                }
            )
    if tickets_path.exists():
        for path in sorted(
            item
            for item in tickets_path.iterdir()
            if item.is_file() and item.suffix.lower() == ".json"
        ):
            row = _load_json_file(path)
            path_experiment_id = normalize_experiment_id(path.stem)
            declared_id = row.get("experiment_id") if isinstance(row, dict) else None
            declared_experiment_id = normalize_experiment_id(declared_id)
            path_looks_like_experiment = bool(
                re.match(r"(?i)^exp[-_]", path.stem)
            )
            declared_looks_like_experiment = bool(
                re.match(r"(?i)^exp[-_]", str(declared_id or ""))
            )
            if (
                path_experiment_id is None
                and declared_experiment_id is None
                and not path_looks_like_experiment
                and not declared_looks_like_experiment
            ):
                continue
            experiment_id = (
                path_experiment_id
                or declared_experiment_id
                or str(declared_id or path.stem)
            )
            if path_experiment_id and path.stem == path_experiment_id:
                canonical_ticket_file_ids.add(path_experiment_id)
            if not isinstance(row, dict):
                identity_violations.append(
                    {
                        "record_type": "ticket",
                        "path": str(path),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": None,
                        "enforcement_bucket": _canonical_record_enforcement_bucket(
                            {}, experiment_id
                        ),
                        "error": "ticket file must contain a JSON object",
                    }
                )
                continue
            if (
                path_experiment_id is None
                or declared_experiment_id is None
                or path.stem != experiment_id
                or declared_id != experiment_id
            ):
                identity_violations.append(
                    {
                        "record_type": "ticket",
                        "path": str(path),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": declared_id,
                        "enforcement_bucket": _canonical_record_enforcement_bucket(
                            row, experiment_id
                        ),
                        "error": "ticket filename stem must equal its exact experiment_id",
                    }
                )
            if experiment_id:
                records[experiment_id] = {**records.get(experiment_id, {}), **row}
                if (
                    path_experiment_id == experiment_id
                    and declared_id == experiment_id
                    and path.stem == experiment_id
                ):
                    canonical_ticket_rows[experiment_id] = row
    for experiment_id, row in sorted(registry_records.items()):
        if experiment_id not in canonical_ticket_file_ids:
            identity_violations.append(
                {
                    "record_type": "ticket",
                    "path": str(tickets_path / f"{experiment_id}.json"),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": row.get("experiment_id"),
                    "enforcement_bucket": _canonical_record_enforcement_bucket(
                        row, experiment_id
                    ),
                    "error": "registry experiment is missing its canonical ticket shard",
                }
            )

        canonical_row = canonical_ticket_rows.get(experiment_id)
        full_snapshot_fields = {
            "experiment_uid",
            "change_type",
            "alpha_promotion",
            "allowed_write_scope",
            "must_not_touch",
        }
        raw_is_full_snapshot = full_snapshot_fields.issubset(row)
        stored_identity = row.get(PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD)
        expected_identity = None
        if stored_identity is not None:
            if (
                not _private_replay_scout_registry_identity_is_valid(stored_identity)
                or stored_identity.get("experiment_id") != experiment_id
            ):
                identity_violations.append(
                    {
                        "record_type": "registry_ticket_identity",
                        "path": str(tickets_path / f"{experiment_id}.json"),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": row.get("experiment_id"),
                        "enforcement_bucket": "post_enforcement",
                        "error": "invalid private replay registry identity snapshot",
                    }
                )
            else:
                expected_identity = stored_identity
        elif _private_replay_scout_contract_indicator(row) or (
            isinstance(canonical_row, dict)
            and _private_replay_scout_contract_indicator(canonical_row)
        ):
            # Full in-memory fixtures and legacy registry rows can themselves be
            # the snapshot. Compact production index rows must carry the
            # explicit identity field written by _ticket_index_entry.
            if raw_is_full_snapshot and not require_persisted_reservation_anchors:
                expected_identity = _private_replay_scout_registry_identity(row)
            else:
                identity_violations.append(
                    {
                        "record_type": "registry_ticket_identity",
                        "path": str(tickets_path / f"{experiment_id}.json"),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": row.get("experiment_id"),
                        "enforcement_bucket": "post_enforcement",
                        "error": "missing private replay registry identity snapshot",
                    }
                )

        manifest_path = manifests_path / f"{experiment_id}.json"
        manifest = _load_json_file(manifest_path)
        manifest_identity = (
            manifest.get(PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD)
            if isinstance(manifest, dict)
            else None
        )
        compact_contract_record = bool(
            (not raw_is_full_snapshot or require_persisted_reservation_anchors)
            and (
                stored_identity is not None
                or _private_replay_scout_contract_indicator(row)
                or (
                    isinstance(canonical_row, dict)
                    and _private_replay_scout_contract_indicator(canonical_row)
                )
            )
        )
        manifest_identity_is_exact = bool(
            isinstance(manifest, dict)
            and manifest.get("experiment_id") == experiment_id
            and isinstance(manifest_identity, dict)
            and manifest_identity.get("experiment_id") == experiment_id
            and _private_replay_scout_registry_identity_is_valid(
                manifest_identity
            )
        )
        if manifest_identity is not None and not manifest_identity_is_exact:
            identity_violations.append(
                {
                    "record_type": "manifest_ticket_identity",
                    "path": str(manifest_path),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": (
                        manifest.get("experiment_id")
                        if isinstance(manifest, dict)
                        else None
                    ),
                    "enforcement_bucket": "post_enforcement",
                    "error": "invalid private replay manifest identity snapshot",
                }
            )
        elif compact_contract_record and manifest_identity is None:
            identity_violations.append(
                {
                    "record_type": "manifest_ticket_identity",
                    "path": str(manifest_path),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": (
                        manifest.get("experiment_id")
                        if isinstance(manifest, dict)
                        else None
                    ),
                    "enforcement_bucket": "post_enforcement",
                    "error": "missing private replay manifest identity snapshot",
                }
            )
        elif manifest_identity is not None:
            if expected_identity is not None and manifest_identity != expected_identity:
                identity_violations.append(
                    {
                        "record_type": "manifest_ticket_identity",
                        "path": str(manifest_path),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": manifest.get("experiment_id"),
                        "enforcement_bucket": "post_enforcement",
                        "error": (
                            "registry/manifest private replay identity mismatch"
                        ),
                    }
                )
            expected_identity = manifest_identity
        if expected_identity is not None:
            actual_identity = (
                _private_replay_scout_registry_identity(canonical_row)
                if isinstance(canonical_row, dict)
                else None
            )
            if actual_identity != expected_identity:
                identity_violations.append(
                    {
                        "record_type": "registry_ticket_identity",
                        "path": str(tickets_path / f"{experiment_id}.json"),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": (
                            canonical_row.get("experiment_id")
                            if isinstance(canonical_row, dict)
                            else None
                        ),
                        "enforcement_bucket": "post_enforcement",
                        "error": (
                            "registry/ticket private replay closeout identity mismatch"
                        ),
                    }
                )
        stored_log_sha256 = row.get(
            PRIVATE_REPLAY_SCOUT_REGISTRY_LOG_SHA256_FIELD
        )
        actual_log_sha256 = (
            (canonical_row.get("result") or {}).get(
                PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD
            )
            if isinstance(canonical_row, dict)
            and isinstance(canonical_row.get("result"), dict)
            else None
        )
        if stored_log_sha256 is not None and (
            not isinstance(stored_log_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", stored_log_sha256) is None
        ):
            identity_violations.append(
                {
                    "record_type": "registry_log_commitment",
                    "path": str(tickets_path / f"{experiment_id}.json"),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": row.get("experiment_id"),
                    "enforcement_bucket": "post_enforcement",
                    "error": "invalid private replay registry log commitment",
                }
            )
        elif stored_log_sha256 != actual_log_sha256 and (
            stored_log_sha256 is not None
            or (
                actual_log_sha256 is not None
                and PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD in row
            )
        ):
            identity_violations.append(
                {
                    "record_type": "registry_log_commitment",
                    "path": str(tickets_path / f"{experiment_id}.json"),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": row.get("experiment_id"),
                    "enforcement_bucket": "post_enforcement",
                    "error": (
                        "registry/ticket private replay canonical log "
                        "commitment mismatch"
                    ),
                }
            )
    for experiment_id, canonical_row in sorted(canonical_ticket_rows.items()):
        if experiment_id in registry_records:
            continue
        manifest_path = manifests_path / f"{experiment_id}.json"
        manifest = _load_json_file(manifest_path)
        manifest_identity = (
            manifest.get(PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD)
            if isinstance(manifest, dict)
            else None
        )
        if (
            not _private_replay_scout_contract_indicator(canonical_row)
            and manifest_identity is None
        ):
            continue
        identity_violations.append(
            {
                "record_type": "registry_ticket_identity",
                "path": str(tickets_path / f"{experiment_id}.json"),
                "canonical_experiment_id": experiment_id,
                "declared_experiment_id": canonical_row.get("experiment_id"),
                "enforcement_bucket": "post_enforcement",
                "error": (
                    "private replay canonical ticket is missing its registry "
                    "identity entry"
                ),
            }
        )
        if not (
            isinstance(manifest, dict)
            and manifest.get("experiment_id") == experiment_id
            and isinstance(manifest_identity, dict)
            and manifest_identity.get("experiment_id") == experiment_id
            and _private_replay_scout_registry_identity_is_valid(
                manifest_identity
            )
        ):
            identity_violations.append(
                {
                    "record_type": "manifest_ticket_identity",
                    "path": str(manifest_path),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": (
                        manifest.get("experiment_id")
                        if isinstance(manifest, dict)
                        else None
                    ),
                    "enforcement_bucket": "post_enforcement",
                    "error": (
                        "private replay canonical ticket is missing its valid "
                        "manifest identity snapshot"
                    ),
                }
            )
        elif (
            _private_replay_scout_registry_identity(canonical_row)
            != manifest_identity
        ):
            identity_violations.append(
                {
                    "record_type": "manifest_ticket_identity",
                    "path": str(manifest_path),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": canonical_row.get("experiment_id"),
                    "enforcement_bucket": "post_enforcement",
                    "error": (
                        "manifest/ticket private replay closeout identity mismatch"
                    ),
                }
            )
    for experiment_id in sorted(set(registry_records) | set(canonical_ticket_rows)):
        manifest_path = manifests_path / f"{experiment_id}.json"
        identity_violations.extend(
            _reservation_identity_audit_violations(
                experiment_id,
                registry_records.get(experiment_id),
                canonical_ticket_rows.get(experiment_id),
                _load_json_file(manifest_path),
                ticket_path_value=tickets_path / f"{experiment_id}.json",
                manifest_path_value=manifest_path,
                require_persisted_anchors=(
                    require_persisted_reservation_anchors
                ),
            )
        )
    if manifests_path.exists():
        for manifest_path in sorted(manifests_path.glob("exp-*.json")):
            experiment_id = normalize_experiment_id(manifest_path.stem)
            if not experiment_id or experiment_id in canonical_ticket_rows:
                continue
            manifest = _load_json_file(manifest_path)
            manifest_identity = (
                manifest.get(PRIVATE_REPLAY_SCOUT_REGISTRY_IDENTITY_FIELD)
                if isinstance(manifest, dict)
                else None
            )
            reservation_identity = (
                manifest.get(EXPERIMENT_RESERVATION_IDENTITY_FIELD)
                if isinstance(manifest, dict)
                else None
            )
            if reservation_identity is not None:
                identity_violations.append(
                    {
                        "record_type": "manifest_reservation_identity",
                        "path": str(manifest_path),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": (
                            manifest.get("experiment_id")
                            if isinstance(manifest, dict)
                            else None
                        ),
                        "enforcement_bucket": "post_enforcement",
                        "error": (
                            "reservation manifest identity is missing its "
                            "canonical ticket shard"
                        ),
                    }
                )
            if manifest_identity is None:
                continue
            identity_violations.append(
                {
                    "record_type": "manifest_ticket_identity",
                    "path": str(manifest_path),
                    "canonical_experiment_id": experiment_id,
                    "declared_experiment_id": (
                        manifest.get("experiment_id")
                        if isinstance(manifest, dict)
                        else None
                    ),
                    "enforcement_bucket": "post_enforcement",
                    "error": (
                        "private replay manifest identity is missing its canonical "
                        "ticket shard"
                    ),
                }
            )
    return records, identity_violations


def _log_records_for_audit(logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR):
    records = {}
    identity_violations = []
    logs_path = Path(logs_dir)
    if logs_path.exists():
        for path in sorted(
            item
            for item in logs_path.iterdir()
            if item.is_file() and item.suffix.lower() == ".json"
        ):
            row = _load_json_file(path)
            path_experiment_id = normalize_experiment_id(path.stem)
            declared_id = row.get("experiment_id") if isinstance(row, dict) else None
            declared_experiment_id = normalize_experiment_id(declared_id)
            path_looks_like_experiment = bool(
                re.match(r"(?i)^exp[-_]", path.stem)
            )
            declared_looks_like_experiment = bool(
                re.match(r"(?i)^exp[-_]", str(declared_id or ""))
            )
            if (
                path_experiment_id is None
                and declared_experiment_id is None
                and not path_looks_like_experiment
                and not declared_looks_like_experiment
            ):
                continue
            experiment_id = (
                path_experiment_id
                or declared_experiment_id
                or str(declared_id or path.stem)
            )
            if not isinstance(row, dict):
                identity_violations.append(
                    {
                        "record_type": "log",
                        "path": str(path),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": None,
                        "enforcement_bucket": _canonical_record_enforcement_bucket(
                            {}, experiment_id
                        ),
                        "error": "log file must contain a JSON object",
                    }
                )
                continue
            if (
                path_experiment_id is None
                or declared_experiment_id is None
                or path.stem != experiment_id
                or declared_id != experiment_id
            ):
                identity_violations.append(
                    {
                        "record_type": "log",
                        "path": str(path),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": declared_id,
                        "enforcement_bucket": _canonical_record_enforcement_bucket(
                            row, experiment_id
                        ),
                        "error": "log filename stem must equal its exact experiment_id",
                    }
                )
            if experiment_id:
                records[experiment_id] = row
    return records, identity_violations


def _canonical_record_enforcement_bucket(row, canonical_experiment_id):
    """Keep pre-rollout filename debt visible without weakening new records."""

    if _private_replay_scout_contract_indicator(row):
        return "post_enforcement"
    cutoff = datetime.fromisoformat(
        PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_ENFORCEMENT_STARTED_AT
    )
    timestamp_values = [
        row.get(field)
        for field in (
            "created_at",
            "reserved_at",
            "updated_at",
            "claimed_at",
            "completed_at",
            "timestamp",
        )
    ]
    hub_identity = row.get("hub_identity")
    if isinstance(hub_identity, dict):
        timestamp_values.append(hub_identity.get("reserved_at"))
    legacy_evidence_seen = False
    for value in timestamp_values:
        if value is None:
            continue
        try:
            observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if observed.tzinfo is not None:
            if observed.astimezone(timezone.utc) >= cutoff.astimezone(timezone.utc):
                return "post_enforcement"
            legacy_evidence_seen = True
        elif observed.date() >= cutoff.date():
            return "post_enforcement"
        else:
            legacy_evidence_seen = True
    cutoff_day = cutoff.date().strftime("%Y%m%d")
    for value in (canonical_experiment_id, row.get("experiment_id")):
        normalized = normalize_experiment_id(value)
        raw_date = None
        if normalized:
            raw_date = normalized[4:12]
        else:
            match = re.match(r"(?i)^exp[-_](\d{8})(?:[-_]|$)", str(value or ""))
            if match:
                raw_date = match.group(1)
        if raw_date is None:
            continue
        if raw_date >= cutoff_day:
            return "post_enforcement"
        legacy_evidence_seen = True
    if legacy_evidence_seen:
        return "legacy_pre_enforcement"
    if any(
        re.match(r"(?i)^exp[-_]", str(value or ""))
        for value in (canonical_experiment_id, row.get("experiment_id"))
    ):
        return "post_enforcement"
    return "legacy_pre_enforcement"


def audit_experiment_process(
    registry,
    *,
    tickets_dir=DEFAULT_TICKETS_DIR,
    logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR,
    lean=False,
    file_backed_registry=False,
):
    """Audit whether experiment objects obey the code-enforced process contract."""
    tickets, ticket_identity_violations = _ticket_records_for_audit(
        registry,
        tickets_dir=tickets_dir,
        require_persisted_reservation_anchors=file_backed_registry,
    )
    logs, log_identity_violations = _log_records_for_audit(logs_dir=logs_dir)
    identity_violations = ticket_identity_violations + log_identity_violations
    canonical_record_violations = [
        item
        for item in identity_violations
        if item.get("enforcement_bucket") == "post_enforcement"
    ]
    legacy_canonical_record_violations = [
        item
        for item in identity_violations
        if item.get("enforcement_bucket") != "post_enforcement"
    ]
    legacy_orphan_logs = []
    alpha_ticket_count = 0
    legacy_alpha_ticket_count = 0
    post_alpha_ticket_count = 0
    closed_alpha_count = 0
    closed_legacy_alpha_count = 0
    closed_post_alpha_count = 0
    missing_prediction = []
    legacy_missing_prediction = []
    post_missing_prediction = []
    closed_missing_prediction = []
    closed_legacy_missing_prediction = []
    closed_post_missing_prediction = []
    closed_missing_calibration = []
    closed_legacy_missing_calibration = []
    closed_post_missing_calibration = []
    weak_prediction_quality = []
    post_weak_prediction_quality = []
    closed_weak_reflection = []
    closed_post_weak_reflection = []
    post_promotion_alpha_count = 0
    missing_alpha_promotion = []
    invalid_alpha_promotion = []
    research_replay_count = 0
    research_result_ceiling_violations = []
    audit_repo_root = Path(tickets_dir).resolve().parent.parent
    audit_promotion_enabled = (
        registry.get("_enforce_alpha_promotion") is True
        or audit_repo_root.resolve() == REPO_ROOT.resolve()
    )

    for experiment_id, ticket in sorted(tickets.items()):
        log_row = logs.get(experiment_id) or {}
        result = ticket.get("result") or {}
        if not isinstance(result, dict):
            result = {}
        anchor = ticket.get("alpha_promotion")
        status = ticket.get("status")
        is_closed = _closed_status(status)
        if _experiment_reservation_identity_required(ticket):
            committed_log_intent = None
            if is_closed:
                try:
                    committed_log_intent = (
                        _validated_post_rollout_closeout_log_intent(
                            ticket, audit_repo_root
                        )
                    )
                except ValueError as exc:
                    canonical_record_violations.append(
                        {
                            "record_type": "ticket_log_closeout_intent",
                            "path": str(
                                Path(tickets_dir).resolve()
                                / f"{experiment_id}.json"
                            ),
                            "canonical_experiment_id": experiment_id,
                            "declared_experiment_id": experiment_id,
                            "enforcement_bucket": "post_enforcement",
                            "error": str(exc),
                        }
                    )
            if is_closed and not log_row:
                canonical_record_violations.append(
                    {
                        "record_type": "ticket_log_terminal_mirror",
                        "path": str(
                            Path(logs_dir).resolve()
                            / f"{experiment_id}.json"
                        ),
                        "canonical_experiment_id": experiment_id,
                        "declared_experiment_id": None,
                        "enforcement_bucket": "post_enforcement",
                        "error": (
                            f"{experiment_id} post-rollout terminal ticket "
                            "requires a canonical experiment log shard"
                        ),
                    }
                )
            elif log_row:
                try:
                    _validate_post_rollout_ticket_log_mirror(ticket, log_row)
                    if (
                        committed_log_intent is not None
                        and log_row != committed_log_intent
                    ):
                        raise ValueError(
                            f"{experiment_id} canonical log differs from the "
                            "terminal closeout intent"
                        )
                except ValueError as exc:
                    canonical_record_violations.append(
                        {
                            "record_type": "ticket_log_terminal_mirror",
                            "path": str(
                                Path(logs_dir).resolve()
                                / f"{experiment_id}.json"
                            ),
                            "canonical_experiment_id": experiment_id,
                            "declared_experiment_id": log_row.get(
                                "experiment_id"
                            ),
                            "enforcement_bucket": "post_enforcement",
                            "error": str(exc),
                        }
                    )
        private_contract_indicator = _private_replay_scout_contract_indicator(ticket)
        private_identity_violations = []
        if private_contract_indicator:
            if not prediction_required_for_lane(ticket.get("lane")):
                private_identity_violations.append(
                    f"{experiment_id} future private replay cannot demote lane to "
                    f"{ticket.get('lane')!r}"
                )
            try:
                _validate_private_replay_scout_identity(ticket)
            except ValueError as exc:
                private_identity_violations.append(str(exc))
            try:
                _validate_private_replay_scout_claim_binding(ticket)
            except ValueError as exc:
                private_identity_violations.append(str(exc))

        is_research_replay = (
            isinstance(anchor, dict)
            and anchor.get("admission_class") == RESEARCH_REPLAY_ADMISSION_CLASS
        )
        if is_research_replay:
            research_replay_count += 1
            violation_reasons = list(private_identity_violations)
            research_metadata = None
            private_replay_contract_required = False
            try:
                research_metadata = _research_replay_metadata(ticket)
            except ValueError as exc:
                violation_reasons.append(str(exc))
            if research_metadata is not None:
                try:
                    private_replay_contract_required = (
                        _private_replay_scout_artifact_contract_required(
                            ticket, research_metadata
                        )
                    )
                    if private_replay_contract_required:
                        _private_replay_scout_scope_entries(
                            ticket, "allowed_write_scope", audit_repo_root
                        )
                        _private_replay_scout_scope_entries(
                            ticket, "must_not_touch", audit_repo_root
                        )
                except ValueError as exc:
                    violation_reasons.append(str(exc))
            if not prediction_required_for_lane(ticket.get("lane")):
                violation_reasons.append(
                    f"{experiment_id} research replay cannot demote lane to "
                    f"{ticket.get('lane')!r}"
                )
                if audit_promotion_enabled:
                    try:
                        _alpha_promotion_api().revalidate_ticket_promotion(
                            ticket,
                            repo_root=audit_repo_root,
                        )
                    except Exception as exc:
                        violation_reasons.append(str(exc))
            if is_closed:
                try:
                    _enforce_research_replay_result_ceiling(
                        ticket,
                        status,
                        result=result,
                        repo_root=audit_repo_root,
                    )
                except ValueError as exc:
                    violation_reasons.append(str(exc))
                if log_row:
                    try:
                        _enforce_research_replay_result_ceiling(
                            ticket,
                            log_row.get("status") or log_row.get("decision"),
                            result=log_row,
                            repo_root=audit_repo_root,
                        )
                    except ValueError as exc:
                        violation_reasons.append(str(exc))
            if private_replay_contract_required:
                committed_log_sha256 = result.get(
                    PRIVATE_REPLAY_SCOUT_LOG_SHA256_FIELD
                )
                if is_closed and (
                    not isinstance(committed_log_sha256, str)
                    or re.fullmatch(r"[0-9a-f]{64}", committed_log_sha256)
                    is None
                ):
                    violation_reasons.append(
                        f"{experiment_id} private replay terminal ticket requires "
                        "an exact canonical log payload commitment"
                    )
                if is_closed and not log_row:
                    violation_reasons.append(
                        f"{experiment_id} private replay terminal ticket requires "
                        "a canonical experiment log shard"
                    )
                elif log_row:
                    # Validate a matching private shard even if the ticket was
                    # rolled back to a nonterminal spelling/state afterwards.
                    try:
                        _validate_private_replay_scout_ticket_log_binding(
                            ticket, log_row, audit_repo_root
                        )
                    except ValueError as exc:
                        violation_reasons.append(str(exc))
            if violation_reasons:
                research_result_ceiling_violations.append(
                    {
                        "experiment_id": experiment_id,
                        "lane": ticket.get("lane"),
                        "status": status,
                        "enforcement_bucket": _canonical_record_enforcement_bucket(
                            ticket, experiment_id
                        ),
                        "violations": sorted(set(violation_reasons)),
                    }
                )
        elif private_identity_violations:
            research_replay_count += 1
            research_result_ceiling_violations.append(
                {
                    "experiment_id": experiment_id,
                    "lane": ticket.get("lane"),
                    "status": status,
                    "enforcement_bucket": _canonical_record_enforcement_bucket(
                        ticket, experiment_id
                    ),
                    "violations": sorted(set(private_identity_violations)),
                }
            )

        if not prediction_required_for_lane(ticket.get("lane")):
            continue
        alpha_ticket_count += 1
        bucket = prediction_enforcement_bucket(ticket)
        if bucket == "post_enforcement":
            post_alpha_ticket_count += 1
        else:
            legacy_alpha_ticket_count += 1
        reasons = prediction_missing_reasons(ticket)
        if audit_promotion_enabled and _alpha_promotion_required_for_lane(
            ticket.get("lane")
        ):
            promotion_api = _alpha_promotion_api()
            post_promotion_ticket = _ticket_is_post_alpha_promotion_enforcement(
                ticket
            )
            if post_promotion_ticket:
                post_promotion_alpha_count += 1
            receipt_present = "alpha_promotion_claim_receipt" in ticket
            receipt_required = False
            receipt_predicate = getattr(
                promotion_api, "claim_receipt_required_for_ticket", None
            )
            if (
                receipt_predicate is not None
                and (status in ACTIVE_STATUSES or is_closed)
            ):
                receipt_required = receipt_predicate(ticket)
            # Promotion-era tickets retain the original full validation.  In
            # addition, audit every explicit receipt and every claimed/closed
            # ticket governed by the later receipt rollout, even when its
            # reservation predates promotion enforcement.
            should_validate = (
                post_promotion_ticket or receipt_present or receipt_required
            )
            if should_validate and not ticket.get("alpha_promotion"):
                missing_alpha_promotion.append({
                    "experiment_id": experiment_id,
                    "lane": ticket.get("lane"),
                    "status": status,
                    "hard_integrity_enforcement_bucket": _enforcement_bucket(
                        ticket, _lean_hard_integrity_enforcement_datetime()
                    ),
                })
            elif should_validate:
                try:
                    promotion_api.revalidate_ticket_promotion(
                        ticket,
                        repo_root=audit_repo_root,
                    )
                except Exception as exc:
                    invalid_alpha_promotion.append({
                        "experiment_id": experiment_id,
                        "lane": ticket.get("lane"),
                        "status": status,
                        "error": str(exc),
                        "hard_integrity_enforcement_bucket": _enforcement_bucket(
                            ticket, _lean_hard_integrity_enforcement_datetime()
                        ),
                    })
        if is_closed:
            closed_alpha_count += 1
            if bucket == "post_enforcement":
                closed_post_alpha_count += 1
            else:
                closed_legacy_alpha_count += 1
        if reasons:
            item = {
                "experiment_id": experiment_id,
                "lane": ticket.get("lane"),
                "status": status,
                "missing": reasons,
                "enforcement_bucket": bucket,
            }
            missing_prediction.append(item)
            if bucket == "post_enforcement":
                post_missing_prediction.append(item)
            else:
                legacy_missing_prediction.append(item)
            if is_closed:
                closed_missing_prediction.append(item)
                if bucket == "post_enforcement":
                    closed_post_missing_prediction.append(item)
                else:
                    closed_legacy_missing_prediction.append(item)

        has_calibration = bool(log_row.get("calibration") or result.get("calibration"))
        if is_closed and not has_calibration:
            item = {
                "experiment_id": experiment_id,
                "lane": ticket.get("lane"),
                "status": status,
                "enforcement_bucket": bucket,
            }
            closed_missing_calibration.append(item)
            if bucket == "post_enforcement":
                closed_post_missing_calibration.append(item)
            else:
                closed_legacy_missing_calibration.append(item)

        if lean:
            quality_bucket = lean_quality_enforcement_bucket(ticket)
            quality_reasons = lean_prediction_quality_reasons(ticket)
            if quality_reasons:
                item = {
                    "experiment_id": experiment_id,
                    "lane": ticket.get("lane"),
                    "status": status,
                    "quality_gaps": quality_reasons,
                    "enforcement_bucket": quality_bucket,
                }
                weak_prediction_quality.append(item)
                if quality_bucket == "post_enforcement":
                    post_weak_prediction_quality.append(item)
            if is_closed:
                reflection_reasons = lean_reflection_quality_reasons(ticket, log_row)
                if reflection_reasons:
                    item = {
                        "experiment_id": experiment_id,
                        "lane": ticket.get("lane"),
                        "status": status,
                        "quality_gaps": reflection_reasons,
                        "enforcement_bucket": quality_bucket,
                    }
                    closed_weak_reflection.append(item)
                    if quality_bucket == "post_enforcement":
                        closed_post_weak_reflection.append(item)

    for experiment_id, log_row in sorted(logs.items()):
        if experiment_id in tickets:
            continue
        item = {
            "record_type": "log",
            "canonical_experiment_id": experiment_id,
            "declared_experiment_id": log_row.get("experiment_id"),
            "enforcement_bucket": _canonical_record_enforcement_bucket(
                log_row, experiment_id
            ),
            "error": "orphan canonical experiment log is missing its ticket",
        }
        post_contract_orphan = (
            _row_declares_private_replay_scout_contract(log_row)
            or "private_replay_scout_artifact_disposition_contract_version"
            in log_row
            or item["enforcement_bucket"] == "post_enforcement"
        )
        if post_contract_orphan:
            canonical_record_violations.append(item)
        else:
            legacy_canonical_record_violations.append(item)
            legacy_orphan_logs.append(item)

    post_research_result_ceiling_violations = [
        item
        for item in research_result_ceiling_violations
        if item.get("enforcement_bucket") == "post_enforcement"
    ]
    legacy_research_result_ceiling_violations = [
        item
        for item in research_result_ceiling_violations
        if item.get("enforcement_bucket") != "post_enforcement"
    ]
    promotion_integrity_violations = (
        missing_alpha_promotion + invalid_alpha_promotion
    )
    post_hard_integrity_promotion_violations = [
        item
        for item in promotion_integrity_violations
        if item.get("hard_integrity_enforcement_bucket") == "post_enforcement"
    ]
    legacy_hard_integrity_promotion_violations = [
        item
        for item in promotion_integrity_violations
        if item.get("hard_integrity_enforcement_bucket") != "post_enforcement"
    ]
    lean_passed = (
        not post_weak_prediction_quality
        and not closed_post_weak_reflection
    )
    passed = (
        not post_missing_prediction
        and not closed_post_missing_calibration
        and not missing_alpha_promotion
        and not invalid_alpha_promotion
        and not post_research_result_ceiling_violations
        and not canonical_record_violations
        and (lean_passed if lean else True)
    )
    return {
        "schema_version": 2,
        "checked_at": utc_now_iso(),
        "lean_quality_audit": bool(lean),
        "prediction_enforcement_started_at": PREDICTION_ENFORCEMENT_STARTED_AT,
        "lean_quality_enforcement_started_at": (
            LEAN_QUALITY_ENFORCEMENT_STARTED_AT if lean else None
        ),
        "alpha_promotion_enforcement_started_at": ALPHA_PROMOTION_ENFORCEMENT_STARTED_AT,
        "lean_hard_integrity_enforcement_started_at": (
            LEAN_HARD_INTEGRITY_ENFORCEMENT_STARTED_AT
        ),
        "tickets_checked": len(tickets),
        "logs_checked": len(logs),
        "alpha_ticket_count": alpha_ticket_count,
        "legacy_pre_enforcement_alpha_ticket_count": legacy_alpha_ticket_count,
        "post_enforcement_alpha_ticket_count": post_alpha_ticket_count,
        "closed_alpha_count": closed_alpha_count,
        "closed_legacy_pre_enforcement_alpha_count": closed_legacy_alpha_count,
        "closed_post_enforcement_alpha_count": closed_post_alpha_count,
        "alpha_missing_prediction_count": len(missing_prediction),
        "legacy_pre_enforcement_missing_prediction_count": len(legacy_missing_prediction),
        "post_enforcement_missing_prediction_count": len(post_missing_prediction),
        "closed_alpha_missing_prediction_count": len(closed_missing_prediction),
        "closed_legacy_pre_enforcement_missing_prediction_count": len(
            closed_legacy_missing_prediction
        ),
        "closed_post_enforcement_missing_prediction_count": len(
            closed_post_missing_prediction
        ),
        "closed_alpha_missing_calibration_count": len(closed_missing_calibration),
        "closed_legacy_pre_enforcement_missing_calibration_count": len(
            closed_legacy_missing_calibration
        ),
        "closed_post_enforcement_missing_calibration_count": len(
            closed_post_missing_calibration
        ),
        "weak_prediction_quality_count": len(weak_prediction_quality),
        "post_enforcement_weak_prediction_quality_count": len(
            post_weak_prediction_quality
        ),
        "closed_weak_reflection_count": len(closed_weak_reflection),
        "closed_post_enforcement_weak_reflection_count": len(
            closed_post_weak_reflection
        ),
        "post_promotion_alpha_count": post_promotion_alpha_count,
        "missing_alpha_promotion_count": len(missing_alpha_promotion),
        "invalid_alpha_promotion_count": len(invalid_alpha_promotion),
        "post_hard_integrity_alpha_promotion_violation_count": len(
            post_hard_integrity_promotion_violations
        ),
        "legacy_hard_integrity_alpha_promotion_violation_count": len(
            legacy_hard_integrity_promotion_violations
        ),
        "research_replay_count": research_replay_count,
        "research_result_ceiling_violation_count": len(
            research_result_ceiling_violations
        ),
        "post_enforcement_research_result_ceiling_violation_count": len(
            post_research_result_ceiling_violations
        ),
        "legacy_research_result_ceiling_violation_count": len(
            legacy_research_result_ceiling_violations
        ),
        "canonical_record_violation_count": len(canonical_record_violations),
        "legacy_canonical_record_violation_count": len(
            legacy_canonical_record_violations
        ),
        "legacy_orphan_log_count": len(legacy_orphan_logs),
        "prediction_coverage": (
            round((alpha_ticket_count - len(missing_prediction)) / alpha_ticket_count, 4)
            if alpha_ticket_count
            else None
        ),
        "legacy_pre_enforcement_prediction_coverage": (
            round(
                (legacy_alpha_ticket_count - len(legacy_missing_prediction))
                / legacy_alpha_ticket_count,
                4,
            )
            if legacy_alpha_ticket_count
            else None
        ),
        "post_enforcement_prediction_coverage": (
            round(
                (post_alpha_ticket_count - len(post_missing_prediction))
                / post_alpha_ticket_count,
                4,
            )
            if post_alpha_ticket_count
            else None
        ),
        "closed_calibration_coverage": (
            round(
                (closed_alpha_count - len(closed_missing_calibration))
                / closed_alpha_count,
                4,
            )
            if closed_alpha_count
            else None
        ),
        "legacy_pre_enforcement_closed_calibration_coverage": (
            round(
                (
                    closed_legacy_alpha_count
                    - len(closed_legacy_missing_calibration)
                )
                / closed_legacy_alpha_count,
                4,
            )
            if closed_legacy_alpha_count
            else None
        ),
        "post_enforcement_closed_calibration_coverage": (
            round(
                (closed_post_alpha_count - len(closed_post_missing_calibration))
                / closed_post_alpha_count,
                4,
            )
            if closed_post_alpha_count
            else None
        ),
        "missing_prediction_examples": missing_prediction[:25],
        "legacy_pre_enforcement_missing_prediction_examples": (
            legacy_missing_prediction[:25]
        ),
        "post_enforcement_missing_prediction_examples": post_missing_prediction[:25],
        "closed_missing_prediction_examples": closed_missing_prediction[:25],
        "closed_legacy_pre_enforcement_missing_prediction_examples": (
            closed_legacy_missing_prediction[:25]
        ),
        "closed_post_enforcement_missing_prediction_examples": (
            closed_post_missing_prediction[:25]
        ),
        "closed_missing_calibration_examples": closed_missing_calibration[:25],
        "closed_legacy_pre_enforcement_missing_calibration_examples": (
            closed_legacy_missing_calibration[:25]
        ),
        "closed_post_enforcement_missing_calibration_examples": (
            closed_post_missing_calibration[:25]
        ),
        "weak_prediction_quality_examples": weak_prediction_quality[:25],
        "post_enforcement_weak_prediction_quality_examples": (
            post_weak_prediction_quality[:25]
        ),
        "closed_weak_reflection_examples": closed_weak_reflection[:25],
        "closed_post_enforcement_weak_reflection_examples": (
            closed_post_weak_reflection[:25]
        ),
        "missing_alpha_promotion_examples": missing_alpha_promotion[:25],
        "invalid_alpha_promotion_examples": invalid_alpha_promotion[:25],
        "post_hard_integrity_alpha_promotion_violation_examples": (
            post_hard_integrity_promotion_violations[:25]
        ),
        "legacy_hard_integrity_alpha_promotion_violation_examples": (
            legacy_hard_integrity_promotion_violations[:25]
        ),
        "research_result_ceiling_violation_examples": (
            research_result_ceiling_violations[:25]
        ),
        "post_enforcement_research_result_ceiling_violation_examples": (
            post_research_result_ceiling_violations[:25]
        ),
        "legacy_research_result_ceiling_violation_examples": (
            legacy_research_result_ceiling_violations[:25]
        ),
        "canonical_record_violation_examples": canonical_record_violations[:25],
        "legacy_canonical_record_violation_examples": (
            legacy_canonical_record_violations[:25]
        ),
        "legacy_orphan_log_examples": legacy_orphan_logs[:25],
        "lean_quality_passed": lean_passed if lean else None,
        "passed": passed,
        "strict_blocks_only_post_enforcement_gaps": True,
    }


def experiment_log_exists(experiment_id, logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR):
    return experiment_log_path(experiment_id, logs_dir).exists()


# Top-level log/shard fields larger than this are diagnostic dumps (e.g.
# *_by_window candidate/trade samples) that no tooling consumes and that already
# live in the experiment artifact (data/experiments/<id>/). They bloat the
# monolithic log and shards by 100x, so they are stripped to a marker on write.
LOG_FIELD_MAX_BYTES = 50 * 1024


def strip_oversized_fields(row, *, max_field_bytes=LOG_FIELD_MAX_BYTES):
    """Return a shallow copy of a log record with any top-level field whose JSON
    serialization exceeds ``max_field_bytes`` replaced by a compact marker. The
    full value stays in the experiment artifact; the log/shard only needs the
    compact decision fields. Does NOT mutate the input (callers may also write
    the full row to the artifact). ``experiment_id`` is never stripped."""
    if not isinstance(row, dict):
        return row
    out = {}
    for key, value in row.items():
        if key == "experiment_id":
            out[key] = value
            continue
        try:
            size = len(json.dumps(value, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            size = 0
        if size > max_field_bytes:
            out[key] = (
                f"<stripped {round(size / 1024)}KB oversized field; "
                "full value retained in the experiment artifact>"
            )
        else:
            out[key] = value
    return out


def save_experiment_log_entry(row, *, allow_duplicate=False,
                              expected_experiment_id=None,
                              logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR,
                              registry_path=None,
                              timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    experiment_id = row.get("experiment_id") if isinstance(row, dict) else None
    _require_canonical_experiment_id(experiment_id, field_name="log experiment_id")
    if expected_experiment_id is not None:
        expected = _require_canonical_experiment_id(
            expected_experiment_id, field_name="expected_experiment_id"
        )
        if experiment_id != expected:
            raise ValueError(
                "experiment log identity mismatch: "
                f"expected {expected}, got {experiment_id}"
            )
    logs_root = Path(logs_dir).resolve()
    ticket = _validate_experiment_log_row_for_persistence(
        row, logs_root, registry_path=registry_path
    )
    immutable_closeout_contract = bool(
        isinstance(ticket, dict)
        and (
            _experiment_reservation_identity_required(ticket)
            or
            ticket.get(
                "private_replay_scout_artifact_disposition_contract_version"
            )
            == PRIVATE_REPLAY_SCOUT_ARTIFACT_DISPOSITION_CONTRACT_VERSION
            or PRIVATE_REPLAY_SCOUT_CLAIM_BINDING_FIELD in ticket
        )
    )
    row = strip_oversized_fields(row)
    path = experiment_log_path(experiment_id, logs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout_seconds=timeout_seconds):
        if path.exists():
            if immutable_closeout_contract:
                existing = _load_json_file(path)
                if existing == row:
                    return path
                raise ValueError(
                    f"post-rollout canonical log is immutable and conflicts "
                    f"with existing shard: {path}"
                )
            if not allow_duplicate:
                raise ValueError(f"experiment log already exists: {path}")
        _atomic_write_text(
            json.dumps(row, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            path)
    return path


def experiment_id_exists_in_log(log_path, experiment_id):
    path = Path(log_path)
    if not path.exists():
        return False
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == experiment_id:
                return True
    return False


def append_log_entry(log_path, row, *, allow_duplicate=False,
                     timeout_seconds=DEFAULT_LOCK_TIMEOUT_SECONDS):
    """Retired monolithic-log appender -> per-experiment shard writer.

    The monolithic ``docs/experiment_log.jsonl`` is no longer a tracked,
    ever-growing file. The per-experiment shard (``experiments/logs/<id>.json``)
    is the source of truth; the monolithic log is a derived view that can be
    rebuilt on demand (``scripts/experiment.py rebuild-log``, which calls
    ``rebuild_experiment_log_from_shards``). Callers that still pass the
    monolithic log path get their record persisted to the shard instead, so the
    log stops growing. Idempotent: an existing shard (e.g. one the runner already
    wrote) is left untouched. Returns the shard path.
    """
    experiment_id = row.get("experiment_id") if isinstance(row, dict) else None
    _require_canonical_experiment_id(experiment_id, field_name="log experiment_id")
    log_path = Path(log_path)
    workspace = (
        log_path.parent.parent if log_path.parent.name == "docs" else log_path.parent
    )
    logs_dir = workspace / "experiments" / "logs"
    shard = experiment_log_path(experiment_id, logs_dir)

    def validate_existing_shard(existing):
        if not isinstance(existing, dict):
            raise ValueError(f"experiment log is not valid JSON: {shard}")
        _validate_experiment_log_row_for_persistence(row, logs_dir)
        _validate_experiment_log_row_for_persistence(existing, logs_dir)
        if existing != strip_oversized_fields(row):
            raise ValueError(
                f"existing experiment log conflicts with incoming row: {shard}"
            )

    if shard.exists():
        existing = _load_json_file(shard)
        validate_existing_shard(existing)
        return shard
    try:
        return save_experiment_log_entry(
            row, logs_dir=logs_dir, timeout_seconds=timeout_seconds
        )
    except FileExistsError:
        # Raced with the runner's own shard write; the shard exists, which is the
        # goal of this call.
        if shard.exists():
            existing = _load_json_file(shard)
            validate_existing_shard(existing)
            return shard
        raise
    except ValueError as exc:
        if str(exc).startswith("experiment log already exists:") and shard.exists():
            existing = _load_json_file(shard)
            try:
                validate_existing_shard(existing)
            except ValueError as validation_exc:
                raise validation_exc from exc
            return shard
        raise


def rebuild_experiment_log_from_shards(logs_dir=DEFAULT_EXPERIMENT_LOGS_DIR,
                                       log_path=DEFAULT_LOG):
    """Regenerate the derived monolithic ``docs/experiment_log.jsonl`` from the
    per-experiment shards (the source of truth).

    Writes one compact JSONL line per shard, sorted by experiment id, so the
    output is deterministic (re-runs and parallel agents produce byte-identical
    files -> no merge conflicts even if the file is tracked). The monolithic log
    is purely a convenience view; the shards in ``experiments/logs/`` hold the
    canonical record. Returns the number of rows written.
    """
    logs_dir = Path(logs_dir)
    rows = []
    if logs_dir.is_dir():
        for shard in sorted(logs_dir.glob("exp-*.json")):
            try:
                with shard.open(encoding="utf-8-sig") as f:
                    row = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(row, dict) and row.get("experiment_id"):
                rows.append(row)
    rows.sort(key=lambda r: r.get("experiment_id", ""))
    text = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows
    )
    _atomic_write_text(text, Path(log_path))
    return len(rows)


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def add_common_registry_arg(parser):
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY),
        help="Path to experiment registry JSON.",
    )
    parser.add_argument(
        "--lock-timeout-seconds",
        type=float,
        default=DEFAULT_LOCK_TIMEOUT_SECONDS,
        help="Seconds to wait for registry/log locks before failing.",
    )
