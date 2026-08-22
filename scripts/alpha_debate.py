#!/usr/bin/env python3
"""Independent alpha debate locks and immutable promotion requests.

This module is deliberately admission-only.  It validates outcome-blind
research artifacts and returns compact hash anchors for experiment tickets; it
never reserves an experiment ID, changes strategy state, or enables trading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.alpha_search_contract import canonical_hash, canonical_json  # noqa: E402
from quant.alpha_search_engine import (  # noqa: E402
    AlphaSearchError,
    verify_selection_panel,
)
from quant.data_paths import atomic_write_json  # noqa: E402


PROMOTION_REQUIRED_LANES = frozenset(
    {"alpha_search", "alpha_discovery", "universe_scout"}
)
# Legacy debate-lock validation covers the same proposal lanes.  Keep the old
# public name so schema-v1 callers remain source-compatible while promotion
# enforcement no longer derives its meaning from debate participation.
DEBATE_REQUIRED_LANES = PROMOTION_REQUIRED_LANES
RUNTIME_PROVIDERS = {"codex": "openai", "claude": "anthropic"}
DEBATE_LOCK_SCHEMA_VERSION = 1
LEGACY_PROMOTION_SCHEMA_VERSION = 1
PROMOTION_SCHEMA_VERSION = 2
RESEARCH_REPLAY_CHANGE_TYPE = "private_replay_scout"
RESEARCH_REPLAY_ADMISSION_CLASS = "research_replay"
RESEARCH_REPLAY_RESULT_CEILING = "observed_only"
# Settled-forward observed-only attribution (AGENTS.md section 5 evidence
# ladder: settled_forward_sufficient -> observed_only attribution).  The
# machine ceiling is identical to research replay; the class differs only in
# which PIT statuses back the surfaces and in the bound proposal change type.
SETTLED_FORWARD_CHANGE_TYPE = "observed_only_attribution"
SETTLED_FORWARD_ADMISSION_CLASS = "settled_forward_attribution"
SETTLED_FORWARD_RESULT_CEILING = "observed_only"
CLAIM_RECEIPT_SCHEMA_VERSION = 1
CLAIM_RECEIPT_RECORD_TYPE = "alpha_promotion_claim_receipt"
CLAIM_RECEIPT_ENFORCEMENT_STARTED_AT = "2026-07-29T00:00:00+00:00"
PROMOTION_ARTIFACT_SNAPSHOT_DIR = (
    Path("data") / "alpha_search" / "promotion_artifact_snapshots"
)
CLAIM_SNAPSHOT_MAX_FILE_BYTES = 64 * 1024 * 1024
CLAIM_SNAPSHOT_MAX_TOTAL_BYTES = 128 * 1024 * 1024
CLAIM_SNAPSHOT_ALLOWED_ROOTS = (
    Path("data"),
    Path("docs"),
    Path("experiments") / "logs",
    Path("experiments") / "manifests",
)
CROSS_PROVIDER_VERIFICATION_LEVEL = "launcher_attested_cross_model"
CODEX_MODEL_DIVERSE_VERIFICATION_LEVEL = (
    "launcher_attested_codex_model_diverse"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_RESEARCH_REF_RE = re.compile(r"res-\d{8}-[a-z0-9][a-z0-9._-]*")


class DebateContractError(ValueError):
    """Fail-closed validation error with a stable code and JSON path."""

    def __init__(self, code: str, path: str, detail: str):
        self.code = str(code)
        self.path = str(path)
        self.detail = str(detail)
        super().__init__(f"[{self.code}] {self.path}: {self.detail}")


def _fail(code: str, path: str, detail: str) -> None:
    raise DebateContractError(code, path, detail)


def _mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("mapping_required", path, "must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        _fail("string_key_required", path, "all object keys must be strings")
    return value


def _fields(
    value: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str] | None = None,
    path: str,
) -> None:
    optional = optional or set()
    missing = sorted(required - set(value))
    if missing:
        _fail("missing_field", path, f"missing required fields: {', '.join(missing)}")
    unknown = sorted(set(value) - required - optional)
    if unknown:
        _fail("unknown_field", path, f"unknown fields: {', '.join(unknown)}")


def _text(value: Any, *, path: str, lower: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("nonempty_string_required", path, "must be a non-empty string")
    result = value.strip()
    return result.lower() if lower else result


def _sha256(value: Any, *, path: str) -> str:
    digest = _text(value, path=path, lower=True)
    if _SHA256_RE.fullmatch(digest) is None:
        _fail("invalid_sha256", path, "must be a lowercase SHA-256 digest")
    return digest


def _json_value(value: Any, *, path: str) -> Any:
    try:
        # Round-tripping through canonical JSON strips MappingProxyType and
        # gives callers one deterministic plain JSON representation.
        return json.loads(canonical_json(value))
    except Exception as exc:
        _fail("invalid_json_value", path, str(exc))


def _string_list(
    value: Any,
    *,
    path: str,
    required: bool = False,
    lower: bool = False,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list of strings")
    result = sorted(
        {
            _text(item, path=f"{path}[{index}]", lower=lower)
            for index, item in enumerate(value)
        }
    )
    if required and not result:
        _fail("nonempty_list_required", path, "must contain at least one value")
    return result


def _research_refs(value: Any, *, path: str) -> list[str]:
    refs = _string_list(value, path=path, lower=True)
    for index, ref in enumerate(refs):
        if _RESEARCH_REF_RE.fullmatch(ref) is None:
            _fail(
                "invalid_research_ref",
                f"{path}[{index}]",
                "must match res-YYYYMMDD-<slug>",
            )
    return refs


def _read_json(path: str | Path, *, contract_path: str = "$") -> Any:
    source = Path(path)
    try:
        return json.loads(source.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        _fail("artifact_read_failed", contract_path, f"{source}: {exc}")
    except json.JSONDecodeError as exc:
        _fail(
            "invalid_json",
            contract_path,
            f"{source}:{exc.lineno}:{exc.colno}: {exc.msg}",
        )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        _fail("artifact_read_failed", "$", f"{path}: {exc}")
    return digest.hexdigest()


def _iter_pre_reservation_aborts(root: Path):
    abort_dir = root / "data" / "alpha_search"
    if not abort_dir.exists():
        return
    try:
        resolved_root = root.resolve(strict=True)
        resolved_dir = abort_dir.resolve(strict=True)
        resolved_dir.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        _fail(
            "invalid_pre_reservation_abort_artifact",
            "$.pre_reservation_aborts",
            f"{abort_dir}: {exc}",
        )
    if not resolved_dir.is_dir():
        _fail(
            "invalid_pre_reservation_abort_artifact",
            "$.pre_reservation_aborts",
            f"{_normalise_locator(resolved_dir, repo_root=root)} must be a directory",
        )
    try:
        abort_paths = sorted(resolved_dir.glob("*abort*.json"))
    except OSError as exc:
        _fail(
            "invalid_pre_reservation_abort_artifact",
            "$.pre_reservation_aborts",
            f"{_normalise_locator(resolved_dir, repo_root=root)}: {exc}",
        )
    for path in abort_paths:
        try:
            resolved_path = path.resolve(strict=True)
            resolved_path.relative_to(resolved_root)
        except (OSError, ValueError) as exc:
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                f"{path}: {exc}",
            )
        if not resolved_path.is_file():
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                f"{_normalise_locator(resolved_path, repo_root=root)} must be a file",
            )
        try:
            raw = json.loads(resolved_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                f"{_normalise_locator(resolved_path, repo_root=root)}: {exc}",
            )
        if not isinstance(raw, Mapping):
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                f"{_normalise_locator(resolved_path, repo_root=root)} must be a JSON object",
            )
        if raw.get("record_type") != "alpha_search_pre_reservation_abort":
            continue
        if type(raw.get("schema_version")) is not int or raw.get("schema_version") != 1:
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                (
                    f"{_normalise_locator(resolved_path, repo_root=root)} "
                    "must use schema_version 1"
                ),
            )
        if raw.get("decision") != "abort_before_alpha_reservation":
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                (
                    f"{_normalise_locator(resolved_path, repo_root=root)} must record "
                    "decision=abort_before_alpha_reservation"
                ),
            )
        panel_hash = raw.get("panel_hash")
        scope_id = raw.get("selection_scope_id")
        if panel_hash is not None and (
            not isinstance(panel_hash, str)
            or _SHA256_RE.fullmatch(panel_hash.strip().lower()) is None
        ):
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                f"{_normalise_locator(resolved_path, repo_root=root)} has invalid panel_hash",
            )
        if scope_id is not None and (
            not isinstance(scope_id, str) or not scope_id.strip()
        ):
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                (
                    f"{_normalise_locator(resolved_path, repo_root=root)} has invalid "
                    "selection_scope_id"
                ),
            )
        if panel_hash is None and scope_id is None:
            _fail(
                "invalid_pre_reservation_abort_artifact",
                "$.pre_reservation_aborts",
                (
                    f"{_normalise_locator(resolved_path, repo_root=root)} must bind "
                    "panel_hash or selection_scope_id"
                ),
            )
        yield resolved_path, raw


def _reject_pre_reservation_abort(
    panel_anchor: Mapping[str, Any],
    *,
    root: Path,
) -> None:
    panel_hash = panel_anchor.get("panel_hash")
    scope_id = panel_anchor.get("selection_scope_id")
    for path, abort in _iter_pre_reservation_aborts(root) or ():
        matched_fields = []
        if isinstance(panel_hash, str) and abort.get("panel_hash") == panel_hash:
            matched_fields.append("panel_hash")
        if isinstance(scope_id, str) and abort.get("selection_scope_id") == scope_id:
            matched_fields.append("selection_scope_id")
        if not matched_fields:
            continue
        _fail(
            "pre_reservation_abort_blocks_promotion",
            "$.panel",
            (
                f"{_normalise_locator(path, repo_root=root)} already records "
                "abort_before_alpha_reservation for this promotion anchor "
                f"({', '.join(matched_fields)})"
            ),
        )


def _resolve_locator(locator: str, *, repo_root: Path, path: str) -> Path:
    text = _text(locator, path=path)
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        _fail("artifact_missing", path, f"{candidate}: {exc}")
    if not resolved.is_file():
        _fail("artifact_not_file", path, f"{resolved} is not a file")
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        _fail(
            "artifact_outside_repo",
            path,
            "durable debate and promotion artifacts must live inside repo_root",
        )
    return resolved


def _normalise_locator(path: str | Path, *, repo_root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _canonical_repo_locator(locator: Any, *, repo_root: Path, path: str) -> str:
    """Return one canonical repo-relative locator without requiring live bytes.

    Claim receipts must remain usable after a mutable research artifact advances
    or is rotated away.  Their locators therefore need lexical containment
    validation, while ordinary promotion validation continues to use
    ``_resolve_locator`` and requires the live file to exist.
    """

    text = _text(locator, path=path).replace("\\", "/")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        _fail("artifact_outside_repo", path, "artifact locator must stay inside repo_root")
    if text != relative:
        _fail(
            "artifact_locator_not_canonical",
            path,
            f"must use canonical repo-relative locator {relative!r}",
        )
    return relative


def _normalise_declared_repo_locator(
    locator: Any, *, repo_root: Path, path: str
) -> str:
    """Normalize a promotion-declared locator while enforcing containment."""

    text = _text(locator, path=path)
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        _fail("artifact_outside_repo", path, "artifact locator must stay inside repo_root")


def _validate_claim_snapshot_source_locator(locator: str, *, path: str) -> None:
    """Restrict durable receipt copies to intentional evidence roots."""

    locator_parts = Path(locator).parts
    cas_parts = PROMOTION_ARTIFACT_SNAPSHOT_DIR.parts
    if locator_parts[: len(cas_parts)] == cas_parts:
        _fail(
            "claim_snapshot_source_is_cas",
            path,
            "a research artifact declaration cannot point back into the claim CAS",
        )
    if any(
        part == ".git" or part == ".env" or part.startswith(".env.")
        for part in locator_parts
    ):
        _fail(
            "claim_snapshot_source_forbidden",
            path,
            "secret and repository-control paths cannot be promotion artifacts",
        )
    if not any(
        locator_parts[: len(root.parts)] == root.parts
        for root in CLAIM_SNAPSHOT_ALLOWED_ROOTS
    ):
        allowed = ", ".join(root.as_posix() for root in CLAIM_SNAPSHOT_ALLOWED_ROOTS)
        _fail(
            "claim_snapshot_source_root_forbidden",
            path,
            f"research artifacts must live under one of: {allowed}",
        )


def _resolve_mailbox_root(
    locator: str | Path, *, repo_root: Path, path: str = "$.mailbox_binding.mailbox_root"
) -> Path:
    candidate = Path(locator)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        _fail("mailbox_root_missing", path, f"{candidate}: {exc}")
    if not resolved.is_dir():
        _fail("mailbox_root_not_directory", path, str(resolved))
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        _fail(
            "mailbox_root_outside_repo",
            path,
            "mailbox root must live inside repo_root",
        )
    return resolved


def _proposal_prediction(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    raw = dict(_mapping(value, path="$.prediction"))
    raw.pop("recorded_at", None)
    if "main_failure_modes" in raw:
        raw["main_failure_modes"] = _string_list(
            raw["main_failure_modes"], path="$.prediction.main_failure_modes"
        )
    return dict(_json_value(raw, path="$.prediction"))


def normalize_ticket_proposal(
    value: Mapping[str, Any] | None = None, **fields: Any
) -> dict[str, Any]:
    """Return the deterministic experiment proposal bound by a promotion.

    The function accepts either one mapping or keyword fields so the registry,
    CLI fixtures, and standalone validators share exactly one normalizer.
    Volatile ``prediction.recorded_at`` is intentionally excluded.
    """

    if value is not None and fields:
        _fail("ambiguous_proposal", "$", "pass a mapping or keyword fields, not both")
    raw = dict(_mapping(value if value is not None else fields, path="$"))
    required = {
        "lane",
        "hypothesis",
        "change_type",
        "single_causal_variable",
        "causal_components",
        "mechanism_family",
        "trial_family",
        "changed_variable",
        "prediction",
    }
    _fields(raw, required=required, path="$")
    lane = _text(raw["lane"], path="$.lane", lower=True)
    if lane not in PROMOTION_REQUIRED_LANES:
        _fail(
            "promotion_lane_mismatch",
            "$.lane",
            f"must be one of {sorted(PROMOTION_REQUIRED_LANES)}",
        )
    return {
        "lane": lane,
        "hypothesis": _text(raw["hypothesis"], path="$.hypothesis"),
        "change_type": _text(raw["change_type"], path="$.change_type"),
        "single_causal_variable": _text(
            raw["single_causal_variable"], path="$.single_causal_variable"
        ),
        "causal_components": _string_list(
            raw["causal_components"], path="$.causal_components"
        ),
        "mechanism_family": _text(
            raw["mechanism_family"], path="$.mechanism_family"
        ),
        "trial_family": _text(raw["trial_family"], path="$.trial_family"),
        "changed_variable": _text(
            raw["changed_variable"], path="$.changed_variable"
        ),
        "prediction": _proposal_prediction(raw["prediction"]),
    }


def _mailbox_api():
    try:
        from scripts import agent_mailbox
    except ImportError:  # Imported as ``alpha_debate`` from scripts on sys.path.
        import agent_mailbox  # type: ignore
    return agent_mailbox


def _participant(
    value: Any,
    *,
    role: str,
    channel: str,
    path: str,
) -> dict[str, Any]:
    raw = dict(_mapping(value, path=path))
    for alias, canonical in (
        ("participant", "name"),
        ("agent_name", "name"),
        ("launcher_receipt", "launch_receipt"),
        ("receipt", "launch_receipt"),
    ):
        if alias in raw:
            if canonical in raw:
                _fail(
                    "ambiguous_participant_field",
                    path,
                    f"use only {canonical}, not both {canonical} and {alias}",
                )
            raw[canonical] = raw.pop(alias)
    _fields(
        raw,
        required={"name", "runtime", "provider", "run_id", "launch_receipt"},
        path=path,
    )
    name = _text(raw["name"], path=f"{path}.name")
    runtime = _text(raw["runtime"], path=f"{path}.runtime", lower=True)
    if runtime not in RUNTIME_PROVIDERS:
        _fail("invalid_runtime", f"{path}.runtime", "must be codex or claude")
    provider = _text(raw["provider"], path=f"{path}.provider", lower=True)
    expected_provider = RUNTIME_PROVIDERS[runtime]
    if provider != expected_provider:
        _fail(
            "runtime_provider_mismatch",
            f"{path}.provider",
            f"{runtime} requires provider {expected_provider}",
        )
    run_id = _text(raw["run_id"], path=f"{path}.run_id")
    receipt_raw = _mapping(raw["launch_receipt"], path=f"{path}.launch_receipt")
    mailbox = _mailbox_api()
    validator = getattr(mailbox, "validate_launch_receipt", None)
    if not callable(validator):
        _fail(
            "launcher_receipt_validator_unavailable",
            f"{path}.launch_receipt",
            "agent_mailbox.validate_launch_receipt is required",
        )
    try:
        report = validator(
            receipt_raw,
            expected_channel=channel,
            expected_participant=name,
            expected_role=role,
            expected_runtime=runtime,
            expected_provider=provider,
            expected_run_id=run_id,
        )
    except Exception as exc:
        _fail("invalid_launch_receipt", f"{path}.launch_receipt", str(exc))
    if not isinstance(report, Mapping) or report.get("valid") is not True:
        errors = report.get("errors") if isinstance(report, Mapping) else report
        _fail(
            "invalid_launch_receipt",
            f"{path}.launch_receipt",
            f"launcher validation failed: {errors}",
        )
    receipt = report.get("receipt")
    if not isinstance(receipt, Mapping):
        _fail(
            "invalid_launch_receipt",
            f"{path}.launch_receipt",
            "validator did not return a normalized receipt",
        )
    return {
        "name": name,
        "runtime": runtime,
        "provider": provider,
        "run_id": run_id,
        "launch_receipt": _json_value(receipt, path=f"{path}.launch_receipt"),
    }


def _review_verification_level(
    participants: Mapping[str, Mapping[str, Any]],
) -> str:
    """Return the admissible independence mode, or fail closed.

    Cross-provider review keeps its original semantics.  The same-provider
    alternative is deliberately narrower: all three roles must be Codex runs,
    every launcher receipt must bind a non-empty requested model, and the
    challenger model must differ from both the initiator and verifier.  The
    latter two may share a model because their run IDs and participants remain
    independently bound.
    """

    initiator = participants["initiator"]
    challenger = participants["challenger"]
    verifier = participants["verifier"]
    opposite = "claude" if initiator["runtime"] == "codex" else "codex"
    if (
        challenger["runtime"] == opposite
        and verifier["runtime"] == opposite
    ):
        for role, participant in (
            ("challenger", challenger),
            ("verifier", verifier),
        ):
            if participant["launch_receipt"].get(
                "initiator_runtime"
            ) != initiator["runtime"]:
                _fail(
                    "receipt_initiator_runtime_mismatch",
                    f"$.{role}.launch_receipt.initiator_runtime",
                    "must bind the debate initiator runtime",
                )
        return CROSS_PROVIDER_VERIFICATION_LEVEL

    if all(
        participant["runtime"] == "codex"
        and participant["provider"] == "openai"
        for participant in participants.values()
    ):
        models: dict[str, str] = {}
        for role, participant in participants.items():
            requested_model = participant["launch_receipt"].get(
                "requested_model"
            )
            if not isinstance(requested_model, str) or not requested_model.strip():
                _fail(
                    "requested_model_required",
                    f"$.{role}.launch_receipt.requested_model",
                    "Codex model-diverse review requires a non-empty model ID",
                )
            models[role] = requested_model.strip().casefold()
            if role != "initiator" and participant["launch_receipt"].get(
                "initiator_runtime"
            ) != "codex":
                _fail(
                    "receipt_initiator_runtime_mismatch",
                    f"$.{role}.launch_receipt.initiator_runtime",
                    "must bind the Codex debate initiator runtime",
                )
        if (
            len(set(models.values())) < 2
            or models["challenger"] == models["initiator"]
            or models["challenger"] == models["verifier"]
        ):
            _fail(
                "codex_model_diversity_required",
                "$.challenger.launch_receipt.requested_model",
                "challenger must use a different requested model from both "
                "initiator and verifier",
            )
        return CODEX_MODEL_DIVERSE_VERIFICATION_LEVEL

    _fail(
        "unsupported_review_topology",
        "$",
        "review must be opposite-provider or three model-diverse Codex runs",
    )


def _verified_claims(value: Any, *, path: str) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("list_required", path, "must be a list")
    claims: list[dict[str, str]] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        raw = _mapping(item, path=item_path)
        _fields(
            raw,
            required={"claim", "source", "verification_status"},
            optional={"resolution"},
            path=item_path,
        )
        status = _text(
            raw["verification_status"],
            path=f"{item_path}.verification_status",
            lower=True,
        )
        if status != "verified":
            _fail(
                "unresolved_load_bearing_claim",
                f"{item_path}.verification_status",
                "every load-bearing claim must be verified",
            )
        claim = {
            "claim": _text(raw["claim"], path=f"{item_path}.claim"),
            "source": _text(raw["source"], path=f"{item_path}.source"),
            "verification_status": "verified",
        }
        if raw.get("resolution") is not None:
            claim["resolution"] = _text(
                raw["resolution"], path=f"{item_path}.resolution"
            )
        claims.append(claim)
    return sorted(claims, key=canonical_json)


def _mailbox_binding(
    *,
    channel: str,
    participants: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
    mailbox_root: Path,
) -> dict[str, Any]:
    """Recompute the transcript proof behind a durable debate lock."""

    expected_level = _review_verification_level(participants)

    mailbox = _mailbox_api()
    verifier = getattr(mailbox, "verify_channel", None)
    reader = getattr(mailbox, "read_transcript", None)
    if not callable(verifier) or not callable(reader):
        _fail(
            "mailbox_verifier_unavailable",
            "$.mailbox_binding",
            "agent_mailbox.verify_channel and read_transcript are required",
        )
    try:
        report = verifier(channel, root=mailbox_root, repo_root=repo_root)
        rows = reader(channel, root=mailbox_root)
    except Exception as exc:
        _fail("mailbox_verification_failed", "$.mailbox_binding", str(exc))
    if not isinstance(report, Mapping):
        _fail("mailbox_verification_failed", "$.mailbox_binding", "invalid report")
    verification_flag = (
        "cross_model_verified"
        if expected_level == CROSS_PROVIDER_VERIFICATION_LEVEL
        else "codex_model_diverse_verified"
    )
    if report.get("structured_valid") is not True or report.get(
        verification_flag
    ) is not True:
        _fail(
            "mailbox_not_cross_model_verified",
            "$.mailbox_binding",
            f"verification_level={report.get('verification_level')!r} "
            f"errors={report.get('errors')!r}",
        )
    if report.get("verification_level") != expected_level:
        _fail(
            "mailbox_verification_level_mismatch",
            "$.mailbox_binding.verification_level",
            f"must be {expected_level}",
        )
    if report.get("legacy_messages") != 0:
        _fail(
            "mailbox_legacy_messages_forbidden",
            "$.mailbox_binding.legacy_messages",
            "a durable debate channel must be fully structured",
        )
    if report.get("dangling"):
        _fail(
            "mailbox_dangling_reference",
            "$.mailbox_binding",
            f"dangling references: {report.get('dangling')}",
        )
    transcript_sha256 = _sha256(
        report.get("transcript_sha256"), path="$.mailbox_binding.transcript_sha256"
    )
    raw_attachments = _mapping(
        report.get("attachment_sha256"), path="$.mailbox_binding.attachment_sha256"
    )
    attachment_sha256 = {
        _text(key, path="$.mailbox_binding.attachment_sha256.<path>").replace(
            "\\", "/"
        ): _sha256(value, path=f"$.mailbox_binding.attachment_sha256.{key}")
        for key, value in sorted(raw_attachments.items())
    }
    if not isinstance(rows, list):
        _fail("mailbox_transcript_invalid", "$.mailbox_binding", "transcript must be a list")

    participant_messages: dict[str, dict[str, Any]] = {}
    for role in ("initiator", "challenger", "verifier"):
        participant = participants[role]
        expected_receipt_hash = participant["launch_receipt"]["receipt_hash"]
        seqs: list[int] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            receipt = row.get("identity_receipt")
            if not isinstance(receipt, Mapping):
                continue
            if (
                row.get("role") == role
                and row.get("runtime") == participant["runtime"]
                and row.get("provider") == participant["provider"]
                and row.get("run_id") == participant["run_id"]
                and receipt.get("participant") == participant["name"]
                and receipt.get("receipt_hash") == expected_receipt_hash
                and isinstance(row.get("seq"), int)
                and isinstance(row.get("text"), str)
                and bool(row.get("text", "").strip())
            ):
                seqs.append(int(row["seq"]))
        if not seqs:
            _fail(
                "receipt_bound_message_missing",
                f"$.mailbox_binding.participant_messages.{role}",
                "the receipt-bound participant must have a non-empty structured message",
            )
        participant_messages[role] = {
            "participant": participant["name"],
            "run_id": participant["run_id"],
            "receipt_hash": expected_receipt_hash,
            "message_seqs": sorted(set(seqs)),
        }
    if max(participant_messages["verifier"]["message_seqs"]) <= max(
        participant_messages["challenger"]["message_seqs"]
    ):
        _fail(
            "verifier_message_not_after_challenge",
            "$.mailbox_binding.participant_messages.verifier",
            "at least one verifier message must follow the final challenger message",
        )
    return {
        "mailbox_root": _normalise_locator(mailbox_root, repo_root=repo_root),
        "transcript_sha256": transcript_sha256,
        "attachment_sha256": attachment_sha256,
        "verification_level": expected_level,
        "structured_messages": int(report.get("structured_messages") or 0),
        "legacy_messages": 0,
        "participant_messages": participant_messages,
    }


def _frozen_mailbox_binding(
    value: Any,
    *,
    participants: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the durable mailbox proof without reopening local mail files.

    The live, gitignored mailbox is required when a lock is first built and
    again when a promotion is built.  Once those hashes are frozen, ticket
    claim/audit must remain portable and must not depend on retaining one
    machine's temporary channel forever.
    """

    expected_level = _review_verification_level(participants)
    raw = _mapping(value, path="$.mailbox_binding")
    required = {
        "mailbox_root",
        "transcript_sha256",
        "attachment_sha256",
        "verification_level",
        "structured_messages",
        "legacy_messages",
        "participant_messages",
    }
    _fields(raw, required=required, path="$.mailbox_binding")
    if raw["verification_level"] != expected_level:
        _fail(
            "mailbox_verification_level_mismatch",
            "$.mailbox_binding.verification_level",
            f"must be {expected_level}",
        )
    structured_messages = raw["structured_messages"]
    if (
        not isinstance(structured_messages, int)
        or isinstance(structured_messages, bool)
        or structured_messages < 3
    ):
        _fail(
            "mailbox_structured_message_count_invalid",
            "$.mailbox_binding.structured_messages",
            "must be an integer of at least three",
        )
    if raw["legacy_messages"] != 0 or isinstance(raw["legacy_messages"], bool):
        _fail(
            "mailbox_legacy_messages_forbidden",
            "$.mailbox_binding.legacy_messages",
            "must be zero",
        )
    attachment_raw = _mapping(
        raw["attachment_sha256"], path="$.mailbox_binding.attachment_sha256"
    )
    attachment_sha256 = {
        _text(key, path="$.mailbox_binding.attachment_sha256.<path>").replace(
            "\\", "/"
        ): _sha256(value, path=f"$.mailbox_binding.attachment_sha256.{key}")
        for key, value in sorted(attachment_raw.items())
    }
    participant_raw = _mapping(
        raw["participant_messages"],
        path="$.mailbox_binding.participant_messages",
    )
    if set(participant_raw) != {"initiator", "challenger", "verifier"}:
        _fail(
            "mailbox_participant_roles_invalid",
            "$.mailbox_binding.participant_messages",
            "must contain exactly initiator, challenger, and verifier",
        )
    participant_messages: dict[str, dict[str, Any]] = {}
    for role in ("initiator", "challenger", "verifier"):
        path = f"$.mailbox_binding.participant_messages.{role}"
        message = _mapping(participant_raw[role], path=path)
        _fields(
            message,
            required={"participant", "run_id", "receipt_hash", "message_seqs"},
            path=path,
        )
        participant = participants[role]
        if message["participant"] != participant["name"]:
            _fail("mailbox_participant_mismatch", f"{path}.participant", role)
        if message["run_id"] != participant["run_id"]:
            _fail("mailbox_run_id_mismatch", f"{path}.run_id", role)
        expected_receipt_hash = participant["launch_receipt"]["receipt_hash"]
        receipt_hash = _sha256(message["receipt_hash"], path=f"{path}.receipt_hash")
        if receipt_hash != expected_receipt_hash:
            _fail("mailbox_receipt_hash_mismatch", f"{path}.receipt_hash", role)
        seq_values = message["message_seqs"]
        if not isinstance(seq_values, list) or not seq_values:
            _fail("mailbox_message_seqs_invalid", f"{path}.message_seqs", role)
        if any(
            not isinstance(seq, int) or isinstance(seq, bool) or seq < 1
            for seq in seq_values
        ):
            _fail(
                "mailbox_message_seqs_invalid",
                f"{path}.message_seqs",
                "all sequence numbers must be positive integers",
            )
        seqs = sorted(set(seq_values))
        if seqs != seq_values:
            _fail(
                "mailbox_message_seqs_not_canonical",
                f"{path}.message_seqs",
                "must be sorted and unique",
            )
        participant_messages[role] = {
            "participant": participant["name"],
            "run_id": participant["run_id"],
            "receipt_hash": receipt_hash,
            "message_seqs": seqs,
        }
    if max(participant_messages["challenger"]["message_seqs"]) <= min(
        participant_messages["initiator"]["message_seqs"]
    ):
        _fail(
            "challenger_message_not_after_initiator",
            "$.mailbox_binding.participant_messages.challenger",
            "at least one challenger message must follow the initiator",
        )
    if max(participant_messages["verifier"]["message_seqs"]) <= max(
        participant_messages["challenger"]["message_seqs"]
    ):
        _fail(
            "verifier_message_not_after_challenge",
            "$.mailbox_binding.participant_messages.verifier",
            "at least one verifier message must follow the final challenger message",
        )
    return {
        "mailbox_root": _text(
            raw["mailbox_root"], path="$.mailbox_binding.mailbox_root"
        ).replace("\\", "/"),
        "transcript_sha256": _sha256(
            raw["transcript_sha256"], path="$.mailbox_binding.transcript_sha256"
        ),
        "attachment_sha256": attachment_sha256,
        "verification_level": expected_level,
        "structured_messages": structured_messages,
        "legacy_messages": 0,
        "participant_messages": participant_messages,
    }


def _normalise_debate_lock(
    value: Mapping[str, Any],
    *,
    require_hash: bool,
    repo_root: Path,
    mailbox_root: Path | None,
) -> dict[str, Any]:
    raw = _mapping(value, path="$" )
    required = {
        "channel",
        "initiator",
        "challenger",
        "verifier",
        "outcome_accessed",
        "verdict",
        "verification_status",
        "challenge_summary",
        "resolution_summary",
        "challenged_candidate_pool_hash",
        "final_candidate_pool_hash",
    }
    optional = {
        "schema_version",
        "record_type",
        "debate_id",
        "created_at",
        "load_bearing_claims",
        "unresolved_load_bearing_claims",
        "mailbox_binding",
        "debate_hash",
    }
    _fields(raw, required=required, optional=optional, path="$")
    schema_version = raw.get("schema_version", DEBATE_LOCK_SCHEMA_VERSION)
    if schema_version != DEBATE_LOCK_SCHEMA_VERSION or isinstance(schema_version, bool):
        _fail("schema_version_mismatch", "$.schema_version", "must equal 1")
    record_type = raw.get("record_type", "alpha_debate_lock")
    if record_type != "alpha_debate_lock":
        _fail("record_type_mismatch", "$.record_type", "must be alpha_debate_lock")
    channel = _text(raw["channel"], path="$.channel")
    initiator = _participant(raw["initiator"], role="initiator", channel=channel, path="$.initiator")
    challenger = _participant(raw["challenger"], role="challenger", channel=channel, path="$.challenger")
    verifier = _participant(raw["verifier"], role="verifier", channel=channel, path="$.verifier")

    names = {initiator["name"], challenger["name"], verifier["name"]}
    run_ids = {initiator["run_id"], challenger["run_id"], verifier["run_id"]}
    if len(names) != 3:
        _fail("participant_identity_collision", "$", "all role names must be distinct")
    if len(run_ids) != 3:
        _fail("participant_run_id_collision", "$", "all role run_ids must be distinct")
    if raw["outcome_accessed"] is not False:
        _fail("outcome_accessed", "$.outcome_accessed", "must be exactly false")
    verdict = _text(raw["verdict"], path="$.verdict", lower=True)
    if verdict != "proceed":
        _fail("debate_not_proceed", "$.verdict", "must be proceed")
    verification_status = _text(
        raw["verification_status"], path="$.verification_status", lower=True
    )
    if verification_status != "verified":
        _fail(
            "debate_not_verified",
            "$.verification_status",
            "must be verified",
        )
    unresolved = raw.get("unresolved_load_bearing_claims", [])
    if not isinstance(unresolved, Sequence) or isinstance(
        unresolved, (str, bytes, bytearray)
    ):
        _fail("list_required", "$.unresolved_load_bearing_claims", "must be a list")
    if unresolved:
        _fail(
            "unresolved_load_bearing_claim",
            "$.unresolved_load_bearing_claims",
            "must be empty before promotion",
        )
    raw_mailbox_binding = raw.get("mailbox_binding")
    participants = {
        "initiator": initiator,
        "challenger": challenger,
        "verifier": verifier,
    }
    _review_verification_level(participants)
    if require_hash:
        actual_mailbox_binding = _frozen_mailbox_binding(
            raw_mailbox_binding,
            participants=participants,
        )
        # Passing mailbox_root explicitly requests a live replay.  The default
        # validates only the durable proof so claim/audit works after the local,
        # gitignored channel is cleaned or on another checkout.
        if mailbox_root is not None:
            live_root = _resolve_mailbox_root(mailbox_root, repo_root=repo_root)
            live_binding = _mailbox_binding(
                channel=channel,
                participants=participants,
                repo_root=repo_root,
                mailbox_root=live_root,
            )
            if actual_mailbox_binding != live_binding:
                _fail(
                    "mailbox_binding_mismatch",
                    "$.mailbox_binding",
                    "transcript, attachments, or receipt-bound messages changed",
                )
    else:
        live_root = _resolve_mailbox_root(
            mailbox_root or repo_root / "data" / "agent_mailbox",
            repo_root=repo_root,
        )
        actual_mailbox_binding = _mailbox_binding(
            channel=channel,
            participants=participants,
            repo_root=repo_root,
            mailbox_root=live_root,
        )
    result: dict[str, Any] = {
        "schema_version": DEBATE_LOCK_SCHEMA_VERSION,
        "record_type": "alpha_debate_lock",
        "channel": channel,
        "initiator": initiator,
        "challenger": challenger,
        "verifier": verifier,
        "outcome_accessed": False,
        "verdict": "proceed",
        "verification_status": "verified",
        "challenge_summary": _text(
            raw["challenge_summary"], path="$.challenge_summary"
        ),
        "resolution_summary": _text(
            raw["resolution_summary"], path="$.resolution_summary"
        ),
        "load_bearing_claims": _verified_claims(
            raw.get("load_bearing_claims", []), path="$.load_bearing_claims"
        ),
        "unresolved_load_bearing_claims": [],
        "mailbox_binding": actual_mailbox_binding,
        "challenged_candidate_pool_hash": _sha256(
            raw["challenged_candidate_pool_hash"],
            path="$.challenged_candidate_pool_hash",
        ),
        "final_candidate_pool_hash": _sha256(
            raw["final_candidate_pool_hash"], path="$.final_candidate_pool_hash"
        ),
    }
    for field_name in ("debate_id", "created_at"):
        if raw.get(field_name) is not None:
            result[field_name] = _text(raw[field_name], path=f"$.{field_name}")
    expected_hash = canonical_hash(result)
    if require_hash:
        claimed = _sha256(raw.get("debate_hash"), path="$.debate_hash")
        if claimed != expected_hash:
            _fail(
                "debate_hash_mismatch",
                "$.debate_hash",
                "does not match the canonical debate lock",
            )
        result["debate_hash"] = claimed
    else:
        result["debate_hash"] = expected_hash
    return result


def build_debate_lock(
    value: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    mailbox_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a draft and add its immutable internal ``debate_hash``."""

    return _normalise_debate_lock(
        value,
        require_hash=False,
        repo_root=Path(repo_root or REPO_ROOT).resolve(),
        mailbox_root=None if mailbox_root is None else Path(mailbox_root),
    )


def validate_debate_lock(
    value: str | Path | Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
    mailbox_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a locked artifact or an already-loaded mapping."""

    if isinstance(value, (str, Path)):
        value = _mapping(_read_json(value, contract_path="$"), path="$")
    return _normalise_debate_lock(
        value,
        require_hash=True,
        repo_root=Path(repo_root or REPO_ROOT).resolve(),
        mailbox_root=None if mailbox_root is None else Path(mailbox_root),
    )


def candidate_pool_hash(panel: Mapping[str, Any]) -> str:
    """Hash the complete, canonically sorted candidate snapshot pool."""

    snapshots = panel.get("candidate_snapshots")
    if not isinstance(snapshots, list) or any(
        not isinstance(item, Mapping) for item in snapshots
    ):
        _fail("candidate_snapshots_missing", "$.candidate_snapshots", "must be a list")
    ordered = sorted(
        (dict(item) for item in snapshots), key=lambda item: str(item.get("candidate_id") or "")
    )
    ids = [str(item.get("candidate_id") or "") for item in ordered]
    if not ids or any(not candidate_id for candidate_id in ids) or len(ids) != len(set(ids)):
        _fail(
            "candidate_ids_invalid_or_duplicate",
            "$.candidate_snapshots",
            "candidate IDs must be non-empty and unique",
        )
    return canonical_hash(ordered)


def _surface_payload(value: Any) -> Any:
    """Use the same strict surface-registry normalization as alpha_search.py."""

    if isinstance(value, Mapping) and isinstance(value.get("surfaces"), list):
        payload = dict(value)
        payload.setdefault("schema_version", 1)
    elif isinstance(value, list):
        payload = {"schema_version": 1, "surfaces": value}
    else:
        _fail(
            "invalid_surface_registry",
            "$.surface_registry",
            "must be {schema_version, surfaces} or a surface list",
        )
    try:
        from quant.alpha_search_registry import EvidenceSurfaceRegistry

        return EvidenceSurfaceRegistry.from_dict(payload)
    except Exception as exc:
        _fail("invalid_surface_registry", "$.surface_registry", str(exc))


def _source_readiness_bindings(value: Any, *, path: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        _fail("list_required", path, "must be a list of source/readiness bindings")
    bindings: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        raw = _mapping(item, path=item_path)
        _fields(
            raw,
            required={
                "surface_id",
                "pit_status",
                "source_contract_hash",
                "readiness_hash",
            },
            path=item_path,
        )
        surface_id = _text(raw["surface_id"], path=f"{item_path}.surface_id")
        if surface_id in seen:
            _fail(
                "duplicate_surface_binding",
                f"{item_path}.surface_id",
                surface_id,
            )
        seen.add(surface_id)
        bindings.append(
            {
                "surface_id": surface_id,
                "pit_status": _text(
                    raw["pit_status"], path=f"{item_path}.pit_status", lower=True
                ),
                "source_contract_hash": _sha256(
                    raw["source_contract_hash"],
                    path=f"{item_path}.source_contract_hash",
                ),
                "readiness_hash": _sha256(
                    raw["readiness_hash"], path=f"{item_path}.readiness_hash"
                ),
            }
        )
    if not bindings:
        _fail("nonempty_list_required", path, "must bind at least one surface")
    ordered = sorted(bindings, key=lambda item: item["surface_id"])
    if bindings != ordered:
        _fail("surface_bindings_not_canonical", path, "must be sorted by surface_id")
    return ordered


def _selected_surface_bindings(
    candidate: Mapping[str, Any],
    *,
    surfaces: Any,
    repo_root: Path,
    research_artifact_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    research_artifact_declarations: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Freeze independent source-contract/readiness identities for admission.

    A research-PIT declaration is useful only when it names reproducible local
    bytes.  The evidence-surface contract validates the declared hash shape;
    this admission layer additionally reads each research artifact and proves
    that the declared digest is the digest actually admitted.
    """

    surface_ids = _string_list(
        candidate.get("surface_ids", []),
        path="$.panel.selected_candidate.surface_ids",
        required=True,
    )
    bindings: list[dict[str, str]] = []
    for surface_id in surface_ids:
        try:
            surface = surfaces.get(surface_id)
            surface_row = surface.to_dict()
            source_contract = surfaces.source_contract(surface_id)
            readiness = surfaces.readiness(surface_id)
        except Exception as exc:
            _fail(
                "selected_surface_binding_failed",
                "$.panel.selected_candidate.surface_ids",
                f"{surface_id}: {exc}",
            )
        pit_status = _text(
            surface_row.get("pit_status"),
            path=f"$.surface_registry.{surface_id}.pit_status",
            lower=True,
        )
        bindings.append(
            {
                "surface_id": surface_id,
                "pit_status": pit_status,
                "source_contract_hash": _sha256(
                    source_contract.get("source_contract_hash"),
                    path=f"$.surface_registry.{surface_id}.source_contract_hash",
                ),
                "readiness_hash": _sha256(
                    readiness.get("readiness_hash"),
                    path=f"$.surface_registry.{surface_id}.readiness_hash",
                ),
            }
        )
        if pit_status == "settled_forward_sufficient":
            if readiness.get("source_contract_status") != "pass":
                _fail(
                    "settled_forward_source_contract_not_ready",
                    f"$.surface_registry.{surface_id}.source_contract_status",
                    "must be pass",
                )
            if int(surface_row.get("settled_count") or 0) <= 0:
                _fail(
                    "settled_forward_history_required",
                    f"$.surface_registry.{surface_id}.settled_count",
                    "settled forward attribution requires settled rows",
                )
            continue
        if pit_status != "research_pit":
            continue
        if readiness.get("source_contract_status") != "pass":
            _fail(
                "research_pit_source_contract_not_ready",
                f"$.surface_registry.{surface_id}.source_contract_status",
                "must be pass",
            )
        if int(readiness.get("independent_count") or 0) <= 0:
            _fail(
                "research_pit_history_required",
                f"$.surface_registry.{surface_id}.independent_count",
                "must be positive",
            )
        if int(readiness.get("candidate_overlap_count") or 0) <= 0:
            _fail(
                "research_pit_overlap_required",
                f"$.surface_registry.{surface_id}.candidate_overlap_count",
                "must be positive",
            )
        if not readiness.get("as_of"):
            _fail(
                "research_pit_as_of_required",
                f"$.surface_registry.{surface_id}.as_of",
                "must bind the historical snapshot clock",
            )
        if surface_row.get("known_future_leakage") is not False:
            _fail(
                "research_pit_leakage_attestation_required",
                f"$.surface_registry.{surface_id}.known_future_leakage",
                "must be exactly false",
            )
        if not str(surface_row.get("research_pit_basis") or "").strip():
            _fail(
                "research_pit_basis_required",
                f"$.surface_registry.{surface_id}.research_pit_basis",
                "must name the decision timestamp and unresolved vintage caveat",
            )
        artifact_hashes = readiness.get("artifact_snapshot_hashes")
        if not isinstance(artifact_hashes, Mapping) or not artifact_hashes:
            _fail(
                "research_artifact_hashes_required",
                f"$.surface_registry.{surface_id}.artifact_snapshot_hashes",
                "must bind local replay bytes",
            )
        for locator, raw_expected_digest in sorted(artifact_hashes.items()):
            contract_path = (
                f"$.surface_registry.{surface_id}."
                f"artifact_snapshot_hashes.{locator}"
            )
            expected_digest = _sha256(raw_expected_digest, path=contract_path)
            canonical_locator = _normalise_declared_repo_locator(
                locator,
                repo_root=repo_root,
                path=contract_path,
            )
            _validate_claim_snapshot_source_locator(
                canonical_locator,
                path=contract_path,
            )
            if research_artifact_snapshots is None:
                artifact_path = _resolve_locator(
                    str(locator),
                    repo_root=repo_root,
                    path=contract_path,
                )
            else:
                snapshot = research_artifact_snapshots.get(canonical_locator)
                if snapshot is None:
                    _fail(
                        "claim_receipt_artifact_missing",
                        contract_path,
                        f"claim receipt has no snapshot for {canonical_locator}",
                    )
                if snapshot.get("sha256") != expected_digest:
                    _fail(
                        "claim_receipt_artifact_digest_mismatch",
                        contract_path,
                        (
                            f"declared {expected_digest}, receipt "
                            f"{snapshot.get('sha256')}"
                        ),
                    )
                artifact_path = Path(snapshot["path"])
            actual_digest = _file_sha256(artifact_path)
            if actual_digest != expected_digest:
                _fail(
                    "research_artifact_sha256_mismatch",
                    contract_path,
                    f"expected {expected_digest}, actual {actual_digest}",
                )
            if research_artifact_declarations is not None:
                research_artifact_declarations.append(
                    {
                        "surface_id": surface_id,
                        "locator": canonical_locator,
                        "sha256": expected_digest,
                        "path": artifact_path,
                    }
                )
    return bindings


def _selected_panel_anchor(
    panel: Mapping[str, Any],
    *,
    surfaces: Any,
    scope_manifest: Mapping[str, Any],
    prior_fingerprints: Any,
    repo_root: Path,
    research_artifact_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    research_artifact_declarations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    try:
        verification = verify_selection_panel(
            panel,
            surfaces=surfaces,
            scope_manifest=scope_manifest,
            prior_fingerprints=prior_fingerprints,
            require_external_context=True,
            repo_root=repo_root,
        )
    except AlphaSearchError as exc:
        _fail(
            "panel_verification_failed",
            "$.panel",
            f"{exc.code}: {exc.detail}",
        )
    if verification.get("valid") is not True:
        _fail("panel_verification_failed", "$.panel", str(verification))
    selected = panel.get("selected_candidate_ids")
    if not isinstance(selected, list) or len(selected) != 1:
        _fail(
            "single_selected_candidate_required",
            "$.panel.selected_candidate_ids",
            "promotion requires exactly one selected candidate",
        )
    candidate_id = _text(selected[0], path="$.panel.selected_candidate_ids[0]")
    if panel.get("selected_candidate_id") != candidate_id:
        _fail(
            "selected_candidate_id_mismatch",
            "$.panel.selected_candidate_id",
            "must equal the sole selected candidate",
        )
    candidates = panel.get("candidate_snapshots") or []
    candidate = next(
        (
            dict(item)
            for item in candidates
            if isinstance(item, Mapping) and item.get("candidate_id") == candidate_id
        ),
        None,
    )
    if candidate is None:
        _fail("selected_candidate_missing", "$.panel", candidate_id)
    selected_evidence_grade = candidate.get("evidence_grade")
    if selected_evidence_grade not in {"gate_candidate", "lead", "observed_only"}:
        _fail(
            "promotion_evidence_grade_mismatch",
            "$.panel.selected_candidate.evidence_grade",
            "selected candidate must be gate_candidate, research-PIT lead, "
            "or settled-forward observed_only",
        )
    preflight = (panel.get("preflight_decisions") or {}).get(candidate_id)
    if not isinstance(preflight, Mapping):
        _fail("selected_preflight_missing", "$.panel.preflight_decisions", candidate_id)
    if preflight.get("outcome_blind") is not True:
        _fail(
            "selected_preflight_not_outcome_blind",
            "$.panel.preflight_decisions.outcome_blind",
            "must be exactly true",
        )
    if preflight.get("decision") != "pass":
        _fail(
            "selected_preflight_not_pass",
            "$.panel.preflight_decisions.decision",
            "must be pass",
        )
    gates = preflight.get("gates")
    if not isinstance(gates, Mapping) or set(gates) != {"D0", "D1", "D2", "D3"}:
        _fail(
            "selected_preflight_gates_invalid",
            "$.panel.preflight_decisions.gates",
            "must contain exactly D0-D3",
        )
    for gate_name in ("D0", "D1", "D2", "D3"):
        gate = gates[gate_name]
        if (
            not isinstance(gate, Mapping)
            or gate.get("status") != "pass"
            or gate.get("reasons") != []
        ):
            _fail(
                "selected_preflight_gate_not_pass",
                f"$.panel.preflight_decisions.gates.{gate_name}",
                "must be outcome-blind pass with no reasons",
            )
    surface_bindings = _selected_surface_bindings(
        candidate,
        surfaces=surfaces,
        repo_root=repo_root,
        research_artifact_snapshots=research_artifact_snapshots,
        research_artifact_declarations=research_artifact_declarations,
    )
    pit_statuses = {binding["pit_status"] for binding in surface_bindings}
    if selected_evidence_grade == "gate_candidate":
        if pit_statuses != {"canonical_pit"}:
            _fail(
                "canonical_promotion_pit_mismatch",
                "$.panel.selected_candidate.surface_ids",
                "gate_candidate promotion requires only canonical_pit surfaces",
            )
        admission_class = "canonical_promotion"
    elif selected_evidence_grade == "observed_only":
        if not pit_statuses.issubset({"settled_forward_sufficient", "canonical_pit"}):
            _fail(
                "settled_forward_pit_mismatch",
                "$.panel.selected_candidate.surface_ids",
                "observed-only attribution requires every surface to be "
                "settled_forward_sufficient or canonical_pit",
            )
        if "settled_forward_sufficient" not in pit_statuses:
            _fail(
                "settled_forward_surface_required",
                "$.panel.selected_candidate.surface_ids",
                "at least one referenced surface must be settled_forward_sufficient",
            )
        admission_class = SETTLED_FORWARD_ADMISSION_CLASS
    else:
        if not pit_statuses.issubset({"research_pit", "canonical_pit"}):
            _fail(
                "research_replay_pit_mismatch",
                "$.panel.selected_candidate.surface_ids",
                "lead replay requires every surface to be research_pit or canonical_pit",
            )
        if "research_pit" not in pit_statuses:
            _fail(
                "research_replay_requires_research_pit",
                "$.panel.selected_candidate.surface_ids",
                "at least one referenced surface must be research_pit",
            )
        admission_class = RESEARCH_REPLAY_ADMISSION_CLASS
    candidate_hash = (panel.get("candidate_snapshot_hashes") or {}).get(candidate_id)
    preflight_hash = (panel.get("preflight_decision_hashes") or {}).get(candidate_id)
    anchor = {
        "panel_hash": _sha256(panel.get("panel_hash"), path="$.panel.panel_hash"),
        "selection_scope_id": _text(
            panel.get("selection_scope_id"), path="$.panel.selection_scope_id"
        ),
        "candidate_id": candidate_id,
        "candidate_snapshot_hash": _sha256(
            candidate_hash, path="$.panel.candidate_snapshot_hashes"
        ),
        "preflight_hash": _sha256(
            preflight_hash, path="$.panel.preflight_decision_hashes"
        ),
        "final_candidate_pool_hash": candidate_pool_hash(panel),
        "admission_class": admission_class,
        "selected_evidence_grade": selected_evidence_grade,
        "source_readiness_bindings": surface_bindings,
        "research_refs": _research_refs(
            candidate.get("research_refs", []), path="$.panel.selected_candidate.research_refs"
        ),
    }
    reopen_proofs = candidate.get("quantitative_reopen_proofs")
    if reopen_proofs is not None:
        if not isinstance(reopen_proofs, list) or not reopen_proofs:
            _fail(
                "quantitative_reopen_proofs_invalid",
                "$.panel.selected_candidate.quantitative_reopen_proofs",
                "must be a non-empty canonical list",
            )
        proofs = [
            dict(
                _mapping(
                    proof,
                    path=(
                        "$.panel.selected_candidate.quantitative_reopen_proofs"
                        f"[{index}]"
                    ),
                )
            )
            for index, proof in enumerate(reopen_proofs)
        ]
        anchor["quantitative_reopen_binding"] = {
            "proofs": proofs,
            "proofs_hash": canonical_hash(proofs),
        }
    return anchor


_PROMOTION_FIELDS = {
    "schema_version",
    "record_type",
    "proposal",
    "proposal_hash",
    "panel_path",
    "panel_sha256",
    "panel_hash",
    "scope_manifest_path",
    "scope_manifest_sha256",
    "scope_manifest_hash",
    "surface_registry_path",
    "surface_registry_sha256",
    "surface_registry_hash",
    "prior_fingerprints_path",
    "prior_fingerprints_sha256",
    "prior_fingerprint_snapshot_hash",
    "selection_scope_id",
    "candidate_id",
    "candidate_snapshot_hash",
    "preflight_hash",
    "final_candidate_pool_hash",
    "research_refs",
    "outcome_blind",
    "trade_enabled",
    "experiment_id_reserved",
    "promotion_hash",
}

_LEGACY_DEBATE_PROMOTION_FIELDS = {
    "debate_artifact_path",
    "debate_artifact_sha256",
    "debate_hash",
}

_RESEARCH_PROMOTION_FIELDS = {
    "admission_class",
    "selected_evidence_grade",
    "result_ceiling",
    "paper_live_eligible",
    "source_readiness_bindings",
}
_OPTIONAL_PROMOTION_FIELDS = {"quantitative_reopen_binding"}


def _normalise_quantitative_reopen_binding(value: Any) -> dict[str, Any]:
    raw = _mapping(value, path="$.quantitative_reopen_binding")
    _fields(
        raw,
        required={"proofs", "proofs_hash"},
        path="$.quantitative_reopen_binding",
    )
    proofs = raw["proofs"]
    if not isinstance(proofs, list) or not proofs:
        _fail(
            "quantitative_reopen_proofs_invalid",
            "$.quantitative_reopen_binding.proofs",
            "must be a non-empty list",
        )
    normal_proofs = [
        _json_value(
            _mapping(
                proof,
                path=f"$.quantitative_reopen_binding.proofs[{index}]",
            ),
            path=f"$.quantitative_reopen_binding.proofs[{index}]",
        )
        for index, proof in enumerate(proofs)
    ]
    proof_ids = [str(proof.get("historical_record_id") or "") for proof in normal_proofs]
    if any(not record_id for record_id in proof_ids) or proof_ids != sorted(
        set(proof_ids)
    ):
        _fail(
            "quantitative_reopen_proofs_not_canonical",
            "$.quantitative_reopen_binding.proofs",
            "targets must be non-empty, unique, and sorted",
        )
    proofs_hash = _sha256(
        raw["proofs_hash"], path="$.quantitative_reopen_binding.proofs_hash"
    )
    if canonical_hash(normal_proofs) != proofs_hash:
        _fail(
            "quantitative_reopen_proofs_hash_mismatch",
            "$.quantitative_reopen_binding.proofs_hash",
            "does not match the ordered proof list",
        )
    return {"proofs": normal_proofs, "proofs_hash": proofs_hash}


def _research_admission_fields(
    panel_anchor: Mapping[str, Any], proposal: Mapping[str, Any]
) -> dict[str, Any]:
    admission_class = panel_anchor.get("admission_class")
    if admission_class == RESEARCH_REPLAY_ADMISSION_CLASS:
        if proposal.get("change_type") != RESEARCH_REPLAY_CHANGE_TYPE:
            _fail(
                "research_replay_change_type_required",
                "$.proposal.change_type",
                f"must be exactly {RESEARCH_REPLAY_CHANGE_TYPE}",
            )
        return {
            "admission_class": RESEARCH_REPLAY_ADMISSION_CLASS,
            "selected_evidence_grade": "lead",
            "result_ceiling": RESEARCH_REPLAY_RESULT_CEILING,
            "paper_live_eligible": False,
            "source_readiness_bindings": list(
                panel_anchor["source_readiness_bindings"]
            ),
        }
    if admission_class == SETTLED_FORWARD_ADMISSION_CLASS:
        if proposal.get("change_type") != SETTLED_FORWARD_CHANGE_TYPE:
            _fail(
                "settled_forward_change_type_required",
                "$.proposal.change_type",
                f"must be exactly {SETTLED_FORWARD_CHANGE_TYPE}",
            )
        return {
            "admission_class": SETTLED_FORWARD_ADMISSION_CLASS,
            "selected_evidence_grade": "observed_only",
            "result_ceiling": SETTLED_FORWARD_RESULT_CEILING,
            "paper_live_eligible": False,
            "source_readiness_bindings": list(
                panel_anchor["source_readiness_bindings"]
            ),
        }
    return {}


def _normalise_promotion_shape(value: Mapping[str, Any]) -> dict[str, Any]:
    raw = _mapping(value, path="$" )
    schema_version = raw.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in {
        LEGACY_PROMOTION_SCHEMA_VERSION,
        PROMOTION_SCHEMA_VERSION,
    }:
        _fail(
            "schema_version_mismatch",
            "$.schema_version",
            "must equal 1 (legacy debated) or 2 (debate-free)",
        )
    required_fields = set(_PROMOTION_FIELDS)
    if schema_version == LEGACY_PROMOTION_SCHEMA_VERSION:
        required_fields.update(_LEGACY_DEBATE_PROMOTION_FIELDS)
    _fields(
        raw,
        required=required_fields,
        optional=_RESEARCH_PROMOTION_FIELDS | _OPTIONAL_PROMOTION_FIELDS,
        path="$",
    )
    present_research_fields = set(raw) & _RESEARCH_PROMOTION_FIELDS
    if present_research_fields and present_research_fields != _RESEARCH_PROMOTION_FIELDS:
        missing = sorted(_RESEARCH_PROMOTION_FIELDS - present_research_fields)
        _fail(
            "incomplete_research_admission",
            "$",
            f"missing research admission fields: {', '.join(missing)}",
        )
    if raw["record_type"] != "alpha_experiment_promotion_request":
        _fail(
            "record_type_mismatch",
            "$.record_type",
            "must be alpha_experiment_promotion_request",
        )
    proposal = normalize_ticket_proposal(_mapping(raw["proposal"], path="$.proposal"))
    result = {
        "schema_version": schema_version,
        "record_type": "alpha_experiment_promotion_request",
        "proposal": proposal,
        "proposal_hash": _sha256(raw["proposal_hash"], path="$.proposal_hash"),
        "panel_path": _text(raw["panel_path"], path="$.panel_path").replace("\\", "/"),
        "panel_sha256": _sha256(raw["panel_sha256"], path="$.panel_sha256"),
        "panel_hash": _sha256(raw["panel_hash"], path="$.panel_hash"),
        "scope_manifest_path": _text(
            raw["scope_manifest_path"], path="$.scope_manifest_path"
        ).replace("\\", "/"),
        "scope_manifest_sha256": _sha256(
            raw["scope_manifest_sha256"], path="$.scope_manifest_sha256"
        ),
        "scope_manifest_hash": _sha256(
            raw["scope_manifest_hash"], path="$.scope_manifest_hash"
        ),
        "surface_registry_path": _text(
            raw["surface_registry_path"], path="$.surface_registry_path"
        ).replace("\\", "/"),
        "surface_registry_sha256": _sha256(
            raw["surface_registry_sha256"], path="$.surface_registry_sha256"
        ),
        "surface_registry_hash": _sha256(
            raw["surface_registry_hash"], path="$.surface_registry_hash"
        ),
        "prior_fingerprints_path": _text(
            raw["prior_fingerprints_path"], path="$.prior_fingerprints_path"
        ).replace("\\", "/"),
        "prior_fingerprints_sha256": _sha256(
            raw["prior_fingerprints_sha256"], path="$.prior_fingerprints_sha256"
        ),
        "prior_fingerprint_snapshot_hash": _sha256(
            raw["prior_fingerprint_snapshot_hash"],
            path="$.prior_fingerprint_snapshot_hash",
        ),
        "selection_scope_id": _text(
            raw["selection_scope_id"], path="$.selection_scope_id"
        ),
        "candidate_id": _text(raw["candidate_id"], path="$.candidate_id"),
        "candidate_snapshot_hash": _sha256(
            raw["candidate_snapshot_hash"], path="$.candidate_snapshot_hash"
        ),
        "preflight_hash": _sha256(raw["preflight_hash"], path="$.preflight_hash"),
        "final_candidate_pool_hash": _sha256(
            raw["final_candidate_pool_hash"], path="$.final_candidate_pool_hash"
        ),
        "research_refs": _research_refs(raw["research_refs"], path="$.research_refs"),
        "outcome_blind": raw["outcome_blind"],
        "trade_enabled": raw["trade_enabled"],
        "experiment_id_reserved": raw["experiment_id_reserved"],
        "promotion_hash": _sha256(raw["promotion_hash"], path="$.promotion_hash"),
    }
    if "quantitative_reopen_binding" in raw:
        result["quantitative_reopen_binding"] = (
            _normalise_quantitative_reopen_binding(
                raw["quantitative_reopen_binding"]
            )
        )
    if schema_version == LEGACY_PROMOTION_SCHEMA_VERSION:
        result.update(
            {
                "debate_artifact_path": _text(
                    raw["debate_artifact_path"], path="$.debate_artifact_path"
                ).replace("\\", "/"),
                "debate_artifact_sha256": _sha256(
                    raw["debate_artifact_sha256"],
                    path="$.debate_artifact_sha256",
                ),
                "debate_hash": _sha256(raw["debate_hash"], path="$.debate_hash"),
            }
        )
    if present_research_fields:
        result.update(
            {
                "admission_class": _text(
                    raw["admission_class"], path="$.admission_class", lower=True
                ),
                "selected_evidence_grade": _text(
                    raw["selected_evidence_grade"],
                    path="$.selected_evidence_grade",
                    lower=True,
                ),
                "result_ceiling": _text(
                    raw["result_ceiling"], path="$.result_ceiling", lower=True
                ),
                "paper_live_eligible": raw["paper_live_eligible"],
                "source_readiness_bindings": _source_readiness_bindings(
                    raw["source_readiness_bindings"],
                    path="$.source_readiness_bindings",
                ),
            }
        )
        if result["admission_class"] == RESEARCH_REPLAY_ADMISSION_CLASS:
            if result["selected_evidence_grade"] != "lead":
                _fail(
                    "research_replay_grade_mismatch",
                    "$.selected_evidence_grade",
                    "must be lead",
                )
            if result["result_ceiling"] != RESEARCH_REPLAY_RESULT_CEILING:
                _fail(
                    "research_replay_result_ceiling_mismatch",
                    "$.result_ceiling",
                    f"must be {RESEARCH_REPLAY_RESULT_CEILING}",
                )
        elif result["admission_class"] == SETTLED_FORWARD_ADMISSION_CLASS:
            if result["selected_evidence_grade"] != "observed_only":
                _fail(
                    "settled_forward_grade_mismatch",
                    "$.selected_evidence_grade",
                    "must be observed_only",
                )
            if result["result_ceiling"] != SETTLED_FORWARD_RESULT_CEILING:
                _fail(
                    "settled_forward_result_ceiling_mismatch",
                    "$.result_ceiling",
                    f"must be {SETTLED_FORWARD_RESULT_CEILING}",
                )
        else:
            _fail(
                "invalid_admission_class",
                "$.admission_class",
                f"must be {RESEARCH_REPLAY_ADMISSION_CLASS} or "
                f"{SETTLED_FORWARD_ADMISSION_CLASS}",
            )
        if result["paper_live_eligible"] is not False:
            _fail(
                "research_replay_paper_live_boundary",
                "$.paper_live_eligible",
                "must be false",
            )
    if result["proposal_hash"] != canonical_hash(proposal):
        _fail("proposal_hash_mismatch", "$.proposal_hash", "does not match proposal")
    if result["outcome_blind"] is not True:
        _fail("outcome_blind_not_attested", "$.outcome_blind", "must be true")
    for field_name in ("trade_enabled", "experiment_id_reserved"):
        if result[field_name] is not False:
            _fail("research_boundary_violation", f"$.{field_name}", "must be false")
    expected_hash = canonical_hash(
        {key: item for key, item in result.items() if key != "promotion_hash"}
    )
    if result["promotion_hash"] != expected_hash:
        _fail(
            "promotion_hash_mismatch",
            "$.promotion_hash",
            "does not match the canonical promotion request",
        )
    return result


def build_promotion_request(
    *,
    panel_path: str | Path,
    scope_manifest_path: str | Path,
    surface_registry_path: str | Path,
    prior_fingerprints_path: str | Path,
    proposal: Mapping[str, Any],
    debate_artifact_path: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Strictly revalidate a panel and freeze an immutable promotion request.

    Debate-free promotions use schema v2.  Supplying the deprecated debate
    artifact preserves the complete schema-v1 contract for existing callers.
    """

    root = Path(repo_root or REPO_ROOT).resolve()
    paths = {
        "panel": _resolve_locator(str(panel_path), repo_root=root, path="$.panel_path"),
        "scope_manifest": _resolve_locator(
            str(scope_manifest_path), repo_root=root, path="$.scope_manifest_path"
        ),
        "surface_registry": _resolve_locator(
            str(surface_registry_path), repo_root=root, path="$.surface_registry_path"
        ),
        "prior_fingerprints": _resolve_locator(
            str(prior_fingerprints_path), repo_root=root, path="$.prior_fingerprints_path"
        ),
    }
    if debate_artifact_path is not None:
        paths["debate_artifact"] = _resolve_locator(
            str(debate_artifact_path), repo_root=root, path="$.debate_artifact_path"
        )
    panel = _mapping(_read_json(paths["panel"]), path="$.panel")
    _reject_pre_reservation_abort(panel, root=root)
    scope = _mapping(_read_json(paths["scope_manifest"]), path="$.scope_manifest")
    surfaces = _surface_payload(_read_json(paths["surface_registry"]))
    prior = _read_json(paths["prior_fingerprints"])
    panel_anchor = _selected_panel_anchor(
        panel,
        surfaces=surfaces,
        scope_manifest=scope,
        prior_fingerprints=prior,
        repo_root=root,
    )
    debate: dict[str, Any] | None = None
    if debate_artifact_path is not None:
        debate_raw = _mapping(
            _read_json(paths["debate_artifact"]), path="$.debate"
        )
        debate_binding = _mapping(
            debate_raw.get("mailbox_binding"), path="$.debate.mailbox_binding"
        )
        debate = validate_debate_lock(
            debate_raw,
            repo_root=root,
            mailbox_root=debate_binding.get("mailbox_root"),
        )
        if debate["final_candidate_pool_hash"] != panel_anchor["final_candidate_pool_hash"]:
            _fail(
                "debate_candidate_pool_mismatch",
                "$.debate.final_candidate_pool_hash",
                "must equal the canonical sorted panel candidate snapshots",
            )
    normal_proposal = normalize_ticket_proposal(proposal)
    request: dict[str, Any] = {
        "schema_version": (
            LEGACY_PROMOTION_SCHEMA_VERSION
            if debate is not None
            else PROMOTION_SCHEMA_VERSION
        ),
        "record_type": "alpha_experiment_promotion_request",
        "proposal": normal_proposal,
        "proposal_hash": canonical_hash(normal_proposal),
        "panel_path": _normalise_locator(paths["panel"], repo_root=root),
        "panel_sha256": _file_sha256(paths["panel"]),
        "panel_hash": panel_anchor["panel_hash"],
        "scope_manifest_path": _normalise_locator(
            paths["scope_manifest"], repo_root=root
        ),
        "scope_manifest_sha256": _file_sha256(paths["scope_manifest"]),
        "scope_manifest_hash": _sha256(
            scope.get("manifest_hash"), path="$.scope_manifest.manifest_hash"
        ),
        "surface_registry_path": _normalise_locator(
            paths["surface_registry"], repo_root=root
        ),
        "surface_registry_sha256": _file_sha256(paths["surface_registry"]),
        "surface_registry_hash": _sha256(
            panel.get("surface_registry_hash"), path="$.panel.surface_registry_hash"
        ),
        "prior_fingerprints_path": _normalise_locator(
            paths["prior_fingerprints"], repo_root=root
        ),
        "prior_fingerprints_sha256": _file_sha256(paths["prior_fingerprints"]),
        "prior_fingerprint_snapshot_hash": _sha256(
            panel.get("prior_fingerprint_snapshot_hash"),
            path="$.panel.prior_fingerprint_snapshot_hash",
        ),
        "selection_scope_id": panel_anchor["selection_scope_id"],
        "candidate_id": panel_anchor["candidate_id"],
        "candidate_snapshot_hash": panel_anchor["candidate_snapshot_hash"],
        "preflight_hash": panel_anchor["preflight_hash"],
        "final_candidate_pool_hash": panel_anchor["final_candidate_pool_hash"],
        "research_refs": panel_anchor["research_refs"],
        "outcome_blind": True,
        "trade_enabled": False,
        "experiment_id_reserved": False,
    }
    if "quantitative_reopen_binding" in panel_anchor:
        request["quantitative_reopen_binding"] = panel_anchor[
            "quantitative_reopen_binding"
        ]
    if debate is not None:
        request.update(
            {
                "debate_artifact_path": _normalise_locator(
                    paths["debate_artifact"], repo_root=root
                ),
                "debate_artifact_sha256": _file_sha256(paths["debate_artifact"]),
                "debate_hash": debate["debate_hash"],
            }
        )
    request.update(_research_admission_fields(panel_anchor, normal_proposal))
    request["promotion_hash"] = canonical_hash(request)
    return _normalise_promotion_shape(request)


def _verify_bound_artifact(
    request: Mapping[str, Any],
    *,
    root: Path,
    prefix: str,
) -> Path:
    locator_key = f"{prefix}_path"
    sha_key = f"{prefix}_sha256"
    path = _resolve_locator(request[locator_key], repo_root=root, path=f"$.{locator_key}")
    actual_sha = _file_sha256(path)
    if actual_sha != request[sha_key]:
        _fail(
            "artifact_sha256_mismatch",
            f"$.{sha_key}",
            f"expected {request[sha_key]}, actual {actual_sha}",
        )
    return path


def _anchor_for_request(
    request: Mapping[str, Any],
    *,
    request_path: Path,
    request_sha256: str,
    root: Path,
    debate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    anchor = {
        "promotion_request_path": _normalise_locator(request_path, repo_root=root),
        "promotion_request_sha256": request_sha256,
        "promotion_hash": request["promotion_hash"],
        "panel_path": request["panel_path"],
        "panel_sha256": request["panel_sha256"],
        "panel_hash": request["panel_hash"],
        "selection_scope_id": request["selection_scope_id"],
        "candidate_id": request["candidate_id"],
        "candidate_snapshot_hash": request["candidate_snapshot_hash"],
        "preflight_hash": request["preflight_hash"],
        "research_refs": list(request["research_refs"]),
    }
    if "quantitative_reopen_binding" in request:
        anchor["quantitative_reopen_binding"] = request[
            "quantitative_reopen_binding"
        ]
    if request["schema_version"] == LEGACY_PROMOTION_SCHEMA_VERSION:
        if debate is None:
            _fail(
                "legacy_debate_missing",
                "$.debate_artifact_path",
                "schema-v1 promotion requires its bound debate artifact",
            )
        anchor.update(
            {
                "debate_artifact_path": request["debate_artifact_path"],
                "debate_artifact_sha256": request["debate_artifact_sha256"],
                "debate_hash": request["debate_hash"],
                "initiator_runtime": debate["initiator"]["runtime"],
                "challenger_runtime": debate["challenger"]["runtime"],
                "verifier_runtime": debate["verifier"]["runtime"],
            }
        )
    for field_name in sorted(_RESEARCH_PROMOTION_FIELDS):
        if field_name in request:
            value = request[field_name]
            anchor[field_name] = (
                [dict(item) for item in value]
                if field_name == "source_readiness_bindings"
                else value
            )
    return anchor


def _validate_promotion_request(
    path: str | Path,
    expected_proposal: Mapping[str, Any] | None = None,
    repo_root: str | Path | None = None,
    *,
    _research_artifact_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    _research_artifact_declarations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Re-open every bound artifact and return a compact ticket anchor.

    The underscored snapshot resolver is reserved for verified claimed-ticket
    receipts.  Public/direct callers always validate the declared live research
    bytes, preserving the pre-claim fail-closed boundary.
    """

    root = Path(repo_root or REPO_ROOT).resolve()
    request_path = Path(path)
    if not request_path.is_absolute():
        request_path = root / request_path
    try:
        request_path = request_path.resolve(strict=True)
    except OSError as exc:
        _fail("promotion_request_missing", "$", f"{request_path}: {exc}")
    if not request_path.is_file():
        _fail("promotion_request_not_file", "$", str(request_path))
    try:
        request_path.relative_to(root)
    except ValueError:
        _fail(
            "promotion_request_outside_repo",
            "$",
            "promotion request must live inside repo_root",
        )
    request_sha = _file_sha256(request_path)
    raw = _mapping(_read_json(request_path), path="$" )
    request = _normalise_promotion_shape(raw)
    if request != dict(raw):
        _fail("promotion_request_not_canonical", "$", "must use canonical normalized fields")
    if expected_proposal is not None:
        expected = normalize_ticket_proposal(expected_proposal)
        if request["proposal"] != expected:
            _fail(
                "ticket_proposal_mismatch",
                "$.proposal",
                "promotion request does not bind the ticket proposal",
            )

    panel_path = _verify_bound_artifact(request, root=root, prefix="panel")
    scope_path = _verify_bound_artifact(request, root=root, prefix="scope_manifest")
    surfaces_path = _verify_bound_artifact(request, root=root, prefix="surface_registry")
    prior_path = _verify_bound_artifact(request, root=root, prefix="prior_fingerprints")
    debate: dict[str, Any] | None = None
    if request["schema_version"] == LEGACY_PROMOTION_SCHEMA_VERSION:
        debate_path = _verify_bound_artifact(
            request, root=root, prefix="debate_artifact"
        )
        debate = validate_debate_lock(debate_path, repo_root=root)
    panel = _mapping(_read_json(panel_path), path="$.panel")
    _reject_pre_reservation_abort(panel, root=root)
    scope = _mapping(_read_json(scope_path), path="$.scope_manifest")
    surfaces = _surface_payload(_read_json(surfaces_path))
    prior = _read_json(prior_path)
    panel_anchor = _selected_panel_anchor(
        panel,
        surfaces=surfaces,
        scope_manifest=scope,
        prior_fingerprints=prior,
        repo_root=root,
        research_artifact_snapshots=_research_artifact_snapshots,
        research_artifact_declarations=_research_artifact_declarations,
    )
    expected_admission = _research_admission_fields(
        panel_anchor, request["proposal"]
    )
    present_admission = {
        key: request[key]
        for key in _RESEARCH_PROMOTION_FIELDS
        if key in request
    }
    if present_admission != expected_admission:
        _fail(
            "promotion_admission_mismatch",
            "$.admission_class",
            f"request={present_admission!r} actual={expected_admission!r}",
        )
    bindings = {
        "panel_hash": panel_anchor["panel_hash"],
        "scope_manifest_hash": scope.get("manifest_hash"),
        "surface_registry_hash": panel.get("surface_registry_hash"),
        "prior_fingerprint_snapshot_hash": panel.get(
            "prior_fingerprint_snapshot_hash"
        ),
        "selection_scope_id": panel_anchor["selection_scope_id"],
        "candidate_id": panel_anchor["candidate_id"],
        "candidate_snapshot_hash": panel_anchor["candidate_snapshot_hash"],
        "preflight_hash": panel_anchor["preflight_hash"],
        "final_candidate_pool_hash": panel_anchor["final_candidate_pool_hash"],
        "research_refs": panel_anchor["research_refs"],
    }
    if "quantitative_reopen_binding" in panel_anchor:
        bindings["quantitative_reopen_binding"] = panel_anchor[
            "quantitative_reopen_binding"
        ]
    elif "quantitative_reopen_binding" in request:
        bindings["quantitative_reopen_binding"] = None
    if debate is not None:
        bindings["debate_hash"] = debate["debate_hash"]
    for key, actual in bindings.items():
        if request.get(key) != actual:
            _fail(
                "promotion_binding_mismatch",
                f"$.{key}",
                f"request={request.get(key)!r} actual={actual!r}",
            )
    if (
        debate is not None
        and debate["final_candidate_pool_hash"]
        != panel_anchor["final_candidate_pool_hash"]
    ):
        _fail(
            "debate_candidate_pool_mismatch",
            "$.debate.final_candidate_pool_hash",
            "does not match canonical sorted panel candidate snapshots",
        )
    return _anchor_for_request(
        request,
        request_path=request_path,
        request_sha256=request_sha,
        root=root,
        debate=debate,
    )


def validate_promotion_request(
    path: str | Path,
    expected_proposal: Mapping[str, Any] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Strictly re-open live promotion and research-artifact bytes."""

    return _validate_promotion_request(
        path,
        expected_proposal=expected_proposal,
        repo_root=repo_root,
    )


def _proposal_from_ticket(ticket: Mapping[str, Any]) -> dict[str, Any]:
    prediction = dict(ticket.get("prediction") or {})
    prediction.pop("recorded_at", None)
    return normalize_ticket_proposal(
        {
            "lane": ticket.get("lane"),
            "hypothesis": ticket.get("hypothesis"),
            "change_type": ticket.get("change_type"),
            "single_causal_variable": ticket.get("single_causal_variable"),
            "causal_components": ticket.get("causal_components") or [],
            "mechanism_family": ticket.get("mechanism_family"),
            "trial_family": ticket.get("trial_family"),
            "changed_variable": ticket.get("changed_variable"),
            "prediction": prediction,
        }
    )


def _ticket_can_use_claim_receipt(ticket: Mapping[str, Any]) -> bool:
    status = str(ticket.get("status") or "").strip().lower()
    return status in {"claimed", "running"} or status.startswith(
        ("accepted", "rejected", "observed_only")
    )


def _claim_receipt_required(ticket: Mapping[str, Any]) -> bool:
    """Use every durable clock monotonically; no backdated field can opt out."""

    cutoff = datetime.fromisoformat(CLAIM_RECEIPT_ENFORCEMENT_STARTED_AT)
    values = [ticket.get("claimed_at"), ticket.get("created_at")]
    hub_identity = ticket.get("hub_identity")
    if isinstance(hub_identity, Mapping):
        values.append(hub_identity.get("reserved_at"))
    malformed_claim_clock = False
    for raw in values:
        if not raw:
            continue
        try:
            observed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            if raw == ticket.get("claimed_at"):
                malformed_claim_clock = True
            continue
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if observed.astimezone(timezone.utc) >= cutoff.astimezone(timezone.utc):
            return True
    if malformed_claim_clock and _ticket_can_use_claim_receipt(ticket):
        return True
    match = re.search(r"exp[-_](\d{8})[-_]\d+", str(ticket.get("experiment_id") or ""))
    if not match:
        return False
    experiment_day = match.group(1)
    cutoff_day = cutoff.date().strftime("%Y%m%d")
    return experiment_day >= cutoff_day


def claim_receipt_required_for_ticket(ticket: Mapping[str, Any]) -> bool:
    """Public rollout predicate used by registry closeout guards."""

    raw_ticket = _mapping(ticket, path="$.ticket")
    lane = str(raw_ticket.get("lane") or "").strip().lower()
    if lane not in PROMOTION_REQUIRED_LANES:
        return False
    return _claim_receipt_required(raw_ticket)


def _aware_claim_clock(value: Any, *, path: str) -> datetime:
    text_value = _text(value, path=path)
    try:
        observed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError:
        _fail(
            "claim_receipt_clock_invalid",
            path,
            "must be an ISO-8601 timestamp",
        )
    if observed.tzinfo is None:
        _fail(
            "claim_receipt_clock_timezone_missing",
            path,
            "must include an explicit UTC offset",
        )
    return observed.astimezone(timezone.utc)


def _validate_claim_clock_order(
    ticket: Mapping[str, Any], claimed_validation_at: Any
) -> str:
    validation_text = _text(
        claimed_validation_at,
        path="$.ticket.alpha_promotion_claim_receipt.claimed_validation_at",
    )
    validation_time = _aware_claim_clock(
        validation_text,
        path="$.ticket.alpha_promotion_claim_receipt.claimed_validation_at",
    )
    durable_clocks = [("created_at", ticket.get("created_at"))]
    hub_identity = ticket.get("hub_identity")
    if isinstance(hub_identity, Mapping):
        durable_clocks.append(
            ("hub_identity.reserved_at", hub_identity.get("reserved_at"))
        )
    for field, value in durable_clocks:
        if value in (None, ""):
            continue
        durable_time = _aware_claim_clock(value, path=f"$.ticket.{field}")
        if validation_time < durable_time:
            _fail(
                "claim_receipt_clock_order_invalid",
                "$.ticket.alpha_promotion_claim_receipt.claimed_validation_at",
                f"must be at or after $.ticket.{field}",
            )
    return validation_text


def _normalise_claim_receipt(
    value: Any,
    *,
    ticket: Mapping[str, Any],
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    raw = _mapping(value, path="$.ticket.alpha_promotion_claim_receipt")
    required = {
        "schema_version",
        "record_type",
        "experiment_id",
        "experiment_uid",
        "promotion_hash",
        "promotion_request_sha256",
        "claimed_validation_at",
        "research_artifact_snapshots",
        "receipt_hash",
    }
    _fields(
        raw,
        required=required,
        path="$.ticket.alpha_promotion_claim_receipt",
    )
    if (
        type(raw["schema_version"]) is not int
        or raw["schema_version"] != CLAIM_RECEIPT_SCHEMA_VERSION
    ):
        _fail(
            "claim_receipt_schema_version_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.schema_version",
            f"must equal {CLAIM_RECEIPT_SCHEMA_VERSION}",
        )
    if raw["record_type"] != CLAIM_RECEIPT_RECORD_TYPE:
        _fail(
            "claim_receipt_record_type_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.record_type",
            f"must equal {CLAIM_RECEIPT_RECORD_TYPE}",
        )
    experiment_id = _text(
        raw["experiment_id"],
        path="$.ticket.alpha_promotion_claim_receipt.experiment_id",
    )
    experiment_uid = _text(
        raw["experiment_uid"],
        path="$.ticket.alpha_promotion_claim_receipt.experiment_uid",
    )
    if experiment_id != ticket.get("experiment_id"):
        _fail(
            "claim_receipt_experiment_id_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.experiment_id",
            "must equal the ticket experiment_id",
        )
    if experiment_uid != ticket.get("experiment_uid"):
        _fail(
            "claim_receipt_experiment_uid_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.experiment_uid",
            "must equal the ticket experiment_uid",
        )
    claimed_validation_at = _validate_claim_clock_order(
        ticket,
        raw["claimed_validation_at"],
    )
    if claimed_validation_at != ticket.get("claimed_at"):
        _fail(
            "claim_receipt_validation_time_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.claimed_validation_at",
            "must equal the ticket claimed_at timestamp",
        )
    stored_anchor = _mapping(
        ticket.get("alpha_promotion"), path="$.ticket.alpha_promotion"
    )
    promotion_hash = _sha256(
        raw["promotion_hash"],
        path="$.ticket.alpha_promotion_claim_receipt.promotion_hash",
    )
    request_sha = _sha256(
        raw["promotion_request_sha256"],
        path="$.ticket.alpha_promotion_claim_receipt.promotion_request_sha256",
    )
    if promotion_hash != stored_anchor.get("promotion_hash"):
        _fail(
            "claim_receipt_promotion_hash_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.promotion_hash",
            "does not bind the ticket alpha_promotion promotion_hash",
        )
    if request_sha != stored_anchor.get("promotion_request_sha256"):
        _fail(
            "claim_receipt_request_sha256_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.promotion_request_sha256",
            "does not bind the ticket alpha_promotion promotion_request_sha256",
        )

    raw_entries = raw["research_artifact_snapshots"]
    if not isinstance(raw_entries, list):
        _fail(
            "claim_receipt_artifact_list_required",
            "$.ticket.alpha_promotion_claim_receipt.research_artifact_snapshots",
            "must be a list",
        )
    entries: list[dict[str, str]] = []
    snapshot_map: dict[str, dict[str, Any]] = {}
    for index, value_entry in enumerate(raw_entries):
        entry_path = (
            "$.ticket.alpha_promotion_claim_receipt."
            f"research_artifact_snapshots[{index}]"
        )
        entry = _mapping(value_entry, path=entry_path)
        _fields(
            entry,
            required={"locator", "sha256", "snapshot_path"},
            path=entry_path,
        )
        locator = _canonical_repo_locator(
            entry["locator"], repo_root=repo_root, path=f"{entry_path}.locator"
        )
        digest = _sha256(entry["sha256"], path=f"{entry_path}.sha256")
        expected_snapshot_path = (PROMOTION_ARTIFACT_SNAPSHOT_DIR / digest).as_posix()
        snapshot_path = _canonical_repo_locator(
            entry["snapshot_path"],
            repo_root=repo_root,
            path=f"{entry_path}.snapshot_path",
        )
        if snapshot_path != expected_snapshot_path:
            _fail(
                "claim_receipt_snapshot_path_mismatch",
                f"{entry_path}.snapshot_path",
                f"must equal {expected_snapshot_path}",
            )
        unresolved_snapshot = repo_root / snapshot_path
        if unresolved_snapshot.is_symlink():
            _fail(
                "claim_receipt_snapshot_symlink_forbidden",
                f"{entry_path}.snapshot_path",
                "content-addressed snapshots must be regular immutable files",
            )
        resolved_snapshot = _resolve_locator(
            snapshot_path,
            repo_root=repo_root,
            path=f"{entry_path}.snapshot_path",
        )
        actual_digest = _file_sha256(resolved_snapshot)
        if actual_digest != digest:
            _fail(
                "claim_receipt_snapshot_sha256_mismatch",
                f"{entry_path}.snapshot_path",
                f"expected {digest}, actual {actual_digest}",
            )
        if locator in snapshot_map:
            _fail(
                "claim_receipt_duplicate_locator",
                f"{entry_path}.locator",
                f"duplicate locator {locator}",
            )
        normal_entry = {
            "locator": locator,
            "sha256": digest,
            "snapshot_path": snapshot_path,
        }
        entries.append(normal_entry)
        snapshot_map[locator] = {
            "sha256": digest,
            "path": resolved_snapshot,
        }
    if entries != sorted(entries, key=lambda item: (item["locator"], item["sha256"])):
        _fail(
            "claim_receipt_artifacts_not_canonical",
            "$.ticket.alpha_promotion_claim_receipt.research_artifact_snapshots",
            "entries must be sorted by locator and digest",
        )
    normal = {
        "schema_version": CLAIM_RECEIPT_SCHEMA_VERSION,
        "record_type": CLAIM_RECEIPT_RECORD_TYPE,
        "experiment_id": experiment_id,
        "experiment_uid": experiment_uid,
        "promotion_hash": promotion_hash,
        "promotion_request_sha256": request_sha,
        "claimed_validation_at": claimed_validation_at,
        "research_artifact_snapshots": entries,
    }
    receipt_hash = _sha256(
        raw["receipt_hash"],
        path="$.ticket.alpha_promotion_claim_receipt.receipt_hash",
    )
    if canonical_hash(normal) != receipt_hash:
        _fail(
            "claim_receipt_hash_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.receipt_hash",
            "does not match the canonical receipt payload",
        )
    normal["receipt_hash"] = receipt_hash
    if normal != dict(raw):
        _fail(
            "claim_receipt_not_canonical",
            "$.ticket.alpha_promotion_claim_receipt",
            "must use canonical normalized fields and ordering",
        )
    return normal, snapshot_map


def _revalidate_ticket_promotion_anchor(
    raw_ticket: Mapping[str, Any],
    *,
    repo_root: Path,
    research_artifact_snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    research_artifact_declarations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stored = _mapping(raw_ticket.get("alpha_promotion"), path="$.ticket.alpha_promotion")
    request_path = stored.get("promotion_request_path") or stored.get("artifact_path")
    if not request_path:
        _fail(
            "promotion_request_path_missing",
            "$.ticket.alpha_promotion",
            "ticket anchor must name the promotion request",
        )
    anchor = _validate_promotion_request(
        request_path,
        expected_proposal=_proposal_from_ticket(raw_ticket),
        repo_root=repo_root,
        _research_artifact_snapshots=research_artifact_snapshots,
        _research_artifact_declarations=research_artifact_declarations,
    )
    for key, value in anchor.items():
        if stored.get(key) != value:
            _fail(
                "ticket_promotion_anchor_mismatch",
                f"$.ticket.alpha_promotion.{key}",
                f"ticket={stored.get(key)!r} actual={value!r}",
            )
    ticket_refs = _research_refs(
        raw_ticket.get("research_refs", []), path="$.ticket.research_refs"
    )
    if ticket_refs != anchor["research_refs"]:
        _fail(
            "ticket_research_refs_mismatch",
            "$.ticket.research_refs",
            "must equal selected candidate research_refs",
        )
    return anchor


def _deduplicated_artifact_declarations(
    declarations: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        locator = str(declaration["locator"])
        digest = str(declaration["sha256"])
        prior = result.get(locator)
        if prior is not None and prior["sha256"] != digest:
            _fail(
                "research_artifact_locator_digest_conflict",
                "$.surface_registry.artifact_snapshot_hashes",
                f"{locator} declares both {prior['sha256']} and {digest}",
            )
        result[locator] = {
            "sha256": digest,
            "path": Path(declaration["path"]),
        }
    return result


def _verify_claim_receipt_artifact_set(
    declarations: Sequence[Mapping[str, Any]],
    snapshots: Mapping[str, Mapping[str, Any]],
) -> None:
    declared = _deduplicated_artifact_declarations(declarations)
    expected = {locator: item["sha256"] for locator, item in declared.items()}
    received = {locator: item["sha256"] for locator, item in snapshots.items()}
    if received != expected:
        _fail(
            "claim_receipt_artifact_set_mismatch",
            "$.ticket.alpha_promotion_claim_receipt.research_artifact_snapshots",
            f"receipt={received!r} declared={expected!r}",
        )


def _preflight_claim_snapshot_copy_sizes(
    declarations: Mapping[str, Mapping[str, Any]],
) -> None:
    """Enforce bounded receipt copies before creating the first CAS object."""

    total_bytes = 0
    for locator, declaration in sorted(declarations.items()):
        source_path = Path(declaration["path"])
        try:
            size = source_path.stat().st_size
        except OSError as exc:
            _fail(
                "claim_snapshot_source_stat_failed",
                "$.surface_registry.artifact_snapshot_hashes",
                f"cannot stat {locator}: {exc}",
            )
        if size > CLAIM_SNAPSHOT_MAX_FILE_BYTES:
            _fail(
                "claim_snapshot_source_too_large",
                "$.surface_registry.artifact_snapshot_hashes",
                (
                    f"{locator} is {size} bytes; receipt snapshots allow at most "
                    f"{CLAIM_SNAPSHOT_MAX_FILE_BYTES} bytes per file. Bind a compact "
                    "manifest/hash artifact for large database or warehouse surfaces."
                ),
            )
        total_bytes += size
    if total_bytes > CLAIM_SNAPSHOT_MAX_TOTAL_BYTES:
        _fail(
            "claim_snapshot_batch_too_large",
            "$.surface_registry.artifact_snapshot_hashes",
            (
                f"receipt snapshot batch is {total_bytes} bytes; the aggregate limit is "
                f"{CLAIM_SNAPSHOT_MAX_TOTAL_BYTES} bytes. Bind compact manifest/hash "
                "artifacts for large database or warehouse surfaces."
            ),
        )


def _persist_content_addressed_snapshot(
    source_path: Path,
    *,
    expected_digest: str,
    repo_root: Path,
) -> str:
    snapshot_dir = repo_root / PROMOTION_ARTIFACT_SNAPSHOT_DIR
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        _fail(
            "claim_snapshot_directory_outside_repo",
            "$.ticket.alpha_promotion_claim_receipt",
            "snapshot directory must stay inside repo_root",
        )
    destination = snapshot_dir / expected_digest
    if destination.is_symlink():
        _fail(
            "claim_snapshot_conflict",
            "$.ticket.alpha_promotion_claim_receipt",
            f"refusing symlink at {destination}",
        )
    if destination.exists():
        if not destination.is_file():
            _fail(
                "claim_snapshot_conflict",
                "$.ticket.alpha_promotion_claim_receipt",
                f"refusing non-file at {destination}",
            )
        actual = _file_sha256(destination)
        if actual != expected_digest:
            _fail(
                "claim_snapshot_conflict",
                "$.ticket.alpha_promotion_claim_receipt",
                f"existing {destination} hashes to {actual}, expected {expected_digest}",
            )
        return _normalise_locator(destination, repo_root=repo_root)

    temp_name: str | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            dir=snapshot_dir,
            prefix=f".{expected_digest}.",
            suffix=".tmp",
        )
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as source, os.fdopen(descriptor, "wb") as target:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
                    target.write(block)
                target.flush()
                os.fsync(target.fileno())
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise
        actual = digest.hexdigest()
        if actual != expected_digest:
            _fail(
                "research_artifact_sha256_mismatch",
                "$.surface_registry.artifact_snapshot_hashes",
                f"expected {expected_digest}, actual {actual}",
            )
        try:
            # Same-directory hard-link publication is atomic and cannot replace
            # an existing digest path.  The temporary name is removed below,
            # leaving the verified inode reachable only through the CAS path.
            os.link(temp_name, destination)
        except FileExistsError:
            if destination.is_symlink() or not destination.is_file():
                _fail(
                    "claim_snapshot_conflict",
                    "$.ticket.alpha_promotion_claim_receipt",
                    f"refusing concurrent non-regular file at {destination}",
                )
            actual = _file_sha256(destination)
            if actual != expected_digest:
                _fail(
                    "claim_snapshot_conflict",
                    "$.ticket.alpha_promotion_claim_receipt",
                    (
                        f"concurrent {destination} hashes to {actual}, "
                        f"expected {expected_digest}"
                    ),
                )
        return _normalise_locator(destination, repo_root=repo_root)
    except DebateContractError:
        raise
    except OSError as exc:
        _fail(
            "claim_snapshot_write_failed",
            "$.ticket.alpha_promotion_claim_receipt",
            f"{destination}: {exc}",
        )
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def build_ticket_promotion_claim_receipt(
    ticket: Mapping[str, Any],
    *,
    claimed_validation_at: str | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Strictly validate live bytes, snapshot research artifacts, and bind claim."""

    root = Path(repo_root or REPO_ROOT).resolve()
    raw_ticket = _mapping(ticket, path="$.ticket")
    declarations: list[dict[str, Any]] = []
    anchor = _revalidate_ticket_promotion_anchor(
        raw_ticket,
        repo_root=root,
        research_artifact_declarations=declarations,
    )
    by_locator = _deduplicated_artifact_declarations(declarations)
    _preflight_claim_snapshot_copy_sizes(by_locator)
    entries: list[dict[str, str]] = []
    for locator, declaration in sorted(by_locator.items()):
        digest = declaration["sha256"]
        snapshot_path = _persist_content_addressed_snapshot(
            declaration["path"],
            expected_digest=digest,
            repo_root=root,
        )
        entries.append(
            {
                "locator": locator,
                "sha256": digest,
                "snapshot_path": snapshot_path,
            }
        )
    validation_time = claimed_validation_at or datetime.now(timezone.utc).isoformat()
    validation_time = _validate_claim_clock_order(raw_ticket, validation_time)
    receipt: dict[str, Any] = {
        "schema_version": CLAIM_RECEIPT_SCHEMA_VERSION,
        "record_type": CLAIM_RECEIPT_RECORD_TYPE,
        "experiment_id": _text(
            raw_ticket.get("experiment_id"),
            path="$.ticket.experiment_id",
        ),
        "experiment_uid": _text(
            raw_ticket.get("experiment_uid"),
            path="$.ticket.experiment_uid",
        ),
        "promotion_hash": anchor["promotion_hash"],
        "promotion_request_sha256": anchor["promotion_request_sha256"],
        "claimed_validation_at": _text(
            validation_time,
            path="$.ticket.alpha_promotion_claim_receipt.claimed_validation_at",
        ),
        "research_artifact_snapshots": entries,
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def validate_ticket_promotion_claim_receipt(
    ticket: Mapping[str, Any], repo_root: str | Path | None = None
) -> dict[str, Any]:
    """Verify receipt bindings, canonical shape, and immutable CAS bytes."""

    root = Path(repo_root or REPO_ROOT).resolve()
    raw_ticket = _mapping(ticket, path="$.ticket")
    receipt, snapshots = _normalise_claim_receipt(
        raw_ticket.get("alpha_promotion_claim_receipt"),
        ticket=raw_ticket,
        repo_root=root,
    )
    declarations: list[dict[str, Any]] = []
    _revalidate_ticket_promotion_anchor(
        raw_ticket,
        repo_root=root,
        research_artifact_snapshots=snapshots,
        research_artifact_declarations=declarations,
    )
    _verify_claim_receipt_artifact_set(declarations, snapshots)
    return receipt


def revalidate_ticket_promotion(
    ticket: Mapping[str, Any], repo_root: str | Path | None = None
) -> dict[str, Any]:
    """Revalidate a ticket, using CAS bytes only through a verified receipt."""

    root = Path(repo_root or REPO_ROOT).resolve()
    raw_ticket = _mapping(ticket, path="$.ticket")
    status = str(raw_ticket.get("status") or "").strip().lower()
    if status == "proposed" and raw_ticket.get("claimed_at"):
        _fail(
            "proposed_ticket_claimed_at_forbidden",
            "$.ticket.claimed_at",
            "proposed tickets cannot carry a claim timestamp",
        )
    if status == "proposed" and "alpha_promotion_claim_receipt" in raw_ticket:
        _fail(
            "proposed_ticket_claim_receipt_forbidden",
            "$.ticket.alpha_promotion_claim_receipt",
            "claim receipts exist only after a successful claim",
        )
    snapshots: Mapping[str, Mapping[str, Any]] | None = None
    receipt_present = "alpha_promotion_claim_receipt" in raw_ticket
    if _ticket_can_use_claim_receipt(raw_ticket):
        if receipt_present:
            _, snapshots = _normalise_claim_receipt(
                raw_ticket["alpha_promotion_claim_receipt"],
                ticket=raw_ticket,
                repo_root=root,
            )
        elif _claim_receipt_required(raw_ticket):
            _fail(
                "alpha_promotion_claim_receipt_missing",
                "$.ticket.alpha_promotion_claim_receipt",
                "claimed/closed ticket requires its canonical claim receipt",
            )
    declarations: list[dict[str, Any]] = []
    anchor = _revalidate_ticket_promotion_anchor(
        raw_ticket,
        repo_root=root,
        research_artifact_snapshots=snapshots,
        research_artifact_declarations=declarations,
    )
    if snapshots is not None:
        _verify_claim_receipt_artifact_set(declarations, snapshots)
    return anchor


def _write_or_print(value: Mapping[str, Any], output: str | None) -> None:
    if output:
        atomic_write_json(value, Path(output), indent=2, ensure_ascii=False)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _cmd_lock(args: argparse.Namespace) -> dict[str, Any]:
    raw = _mapping(_read_json(args.input), path="$" )
    return build_debate_lock(
        raw, repo_root=args.repo_root, mailbox_root=args.mailbox_root
    )


def _cmd_validate_lock(args: argparse.Namespace) -> dict[str, Any]:
    return validate_debate_lock(
        args.lock, repo_root=args.repo_root, mailbox_root=args.mailbox_root
    )


def _cmd_validate_promotion(args: argparse.Namespace) -> dict[str, Any]:
    expected = None
    if args.proposal:
        expected = _mapping(_read_json(args.proposal), path="$.proposal")
    return validate_promotion_request(
        args.promotion,
        expected_proposal=expected,
        repo_root=args.repo_root,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    lock = subparsers.add_parser(
        "lock", help="validate a debate draft and add its immutable debate_hash"
    )
    lock.add_argument("input")
    lock.add_argument("--output", required=True)
    lock.add_argument("--repo-root")
    lock.add_argument("--mailbox-root")
    lock.set_defaults(handler=_cmd_lock)

    validate_lock = subparsers.add_parser(
        "validate-lock", help="validate receipts, role separation, verdict, and hash"
    )
    validate_lock.add_argument("lock")
    validate_lock.add_argument("--output")
    validate_lock.add_argument("--repo-root")
    validate_lock.add_argument("--mailbox-root")
    validate_lock.set_defaults(handler=_cmd_validate_lock)

    validate_promotion = subparsers.add_parser(
        "validate-promotion", help="re-open and verify a promotion request"
    )
    validate_promotion.add_argument("promotion")
    validate_promotion.add_argument("--proposal")
    validate_promotion.add_argument("--repo-root")
    validate_promotion.add_argument("--output")
    validate_promotion.set_defaults(handler=_cmd_validate_promotion)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args)
        _write_or_print(result, getattr(args, "output", None))
    except (DebateContractError, AlphaSearchError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        print(f"error[{code}]: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "PROMOTION_REQUIRED_LANES",
    "DEBATE_REQUIRED_LANES",
    "RUNTIME_PROVIDERS",
    "DebateContractError",
    "normalize_ticket_proposal",
    "candidate_pool_hash",
    "build_debate_lock",
    "validate_debate_lock",
    "build_promotion_request",
    "validate_promotion_request",
    "build_ticket_promotion_claim_receipt",
    "validate_ticket_promotion_claim_receipt",
    "claim_receipt_required_for_ticket",
    "revalidate_ticket_promotion",
]


if __name__ == "__main__":
    raise SystemExit(main())
