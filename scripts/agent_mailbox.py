"""File-based mailbox so same-machine agents can talk by listening to files.

Protocol, conventions, and the deadlock-free turn recipe are documented in
``docs/agent_mailbox.md`` -- read that to participate. This module is both a
library (import the functions) and a CLI.

Design (matches the repo's ticket-reservation idioms):
- A *channel* is a directory ``data/agent_mailbox/<channel>/``.
- Each message is one atomic file ``<seq>-<sender>.json`` created with
  ``O_EXCL``: the file's existence IS the turn, so concurrent senders never
  clobber each other and the sequence is globally ordered per channel.
- ``recv`` blocks by polling for the next message whose sequence is past this
  agent's per-agent cursor (``.cursor-<me>``) and whose sender is not itself,
  then advances the cursor. Listening lives here; agents never call ``sleep``.

The mailbox lives under ``data/agent_mailbox/`` which is gitignored: it is
local same-machine coordination, deliberately NOT tracked (tracking an
append-only chat is exactly what caused the experiment_log.jsonl merge
conflicts this repo retired).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAILBOX_ROOT = REPO_ROOT / "data" / "agent_mailbox"
POLL_SECONDS = 1.0
DEFAULT_TIMEOUT = 100  # < the Bash tool's 120s default; retry recv on timeout
_MAX_SEQ_ATTEMPTS = 10000
_MAX_SLUG_LENGTH = 128
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_WINDOWS_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

RUNTIME_PROVIDERS = {"codex": "openai", "claude": "anthropic"}
LAUNCH_RECEIPT_SCHEMA_VERSION = 1


def canonical_hash(value) -> str:
    """Return a stable SHA-256 over canonical UTF-8 JSON."""
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_hash_or_none(value) -> str | None:
    try:
        return canonical_hash(value)
    except (TypeError, ValueError):
        return None


def _validate_slug(value: str, kind: str) -> str:
    """Validate a mailbox path component before it reaches the filesystem."""
    if not isinstance(value, str):
        raise ValueError(f"{kind} must be a string slug")
    if not value or len(value) > _MAX_SLUG_LENGTH or not _SLUG_RE.fullmatch(value):
        raise ValueError(
            f"invalid {kind} slug {value!r}; use ASCII letters, numbers, '.', "
            "'_' or '-' and start with a letter or number"
        )
    if value.upper().split(".", 1)[0] in _WINDOWS_DEVICE_NAMES:
        raise ValueError(f"invalid {kind} slug {value!r}: reserved device name")
    return value


def _validate_runtime(runtime: str, *, allow_auto: bool = False) -> str:
    allowed = set(RUNTIME_PROVIDERS)
    if allow_auto:
        allowed.add("auto")
    if not isinstance(runtime, str) or runtime not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"runtime must be one of: {choices}")
    return runtime


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_launch_receipt(
    *,
    channel: str,
    participant: str,
    role: str,
    runtime: str,
    run_id: str,
    executable: str | os.PathLike,
    executable_version: str,
    requested_model: str | None = None,
    cross_provider_acknowledged: bool = False,
    nonce: str | None = None,
    initiator_runtime: str | None = None,
) -> dict:
    """Create a launcher-attested (not cryptographic) runtime receipt.

    The executable is read and hashed here. Runtime/provider is a fixed mapping;
    callers cannot self-declare an arbitrary provider for a known runtime.
    """
    channel = _validate_slug(channel, "channel")
    participant = _validate_slug(participant, "participant")
    role = _validate_slug(role, "role")
    runtime = _validate_runtime(runtime)
    run_id = _validate_slug(run_id, "run_id")
    if initiator_runtime is not None:
        initiator_runtime = _validate_runtime(initiator_runtime)
    if not isinstance(executable_version, str) or not executable_version.strip():
        raise ValueError("executable_version must be a non-empty string")
    if requested_model is not None and not isinstance(requested_model, str):
        raise ValueError("requested_model must be a string or None")
    if not isinstance(cross_provider_acknowledged, bool):
        raise ValueError("cross_provider_acknowledged must be boolean")
    if nonce is not None and (not isinstance(nonce, str) or not nonce):
        raise ValueError("nonce must be a non-empty string or None")

    exe_path = Path(executable).expanduser().resolve(strict=True)
    if not exe_path.is_file():
        raise ValueError(f"runtime executable is not a file: {exe_path}")
    receipt = {
        "schema_version": LAUNCH_RECEIPT_SCHEMA_VERSION,
        "channel": channel,
        "participant": participant,
        "role": role,
        "runtime": runtime,
        "provider": RUNTIME_PROVIDERS[runtime],
        "run_id": run_id,
        "nonce": nonce or secrets.token_hex(16),
        "executable": str(exe_path),
        "executable_sha256": _sha256_file(exe_path),
        "executable_version": executable_version.strip(),
        "requested_model": requested_model,
        "cross_provider_acknowledged": cross_provider_acknowledged,
    }
    if initiator_runtime is not None:
        receipt["initiator_runtime"] = initiator_runtime
    receipt["receipt_hash"] = canonical_hash(receipt)
    return receipt


def validate_launch_receipt(
    receipt,
    expected_channel=None,
    expected_participant=None,
    expected_role=None,
    expected_runtime=None,
    expected_provider=None,
    expected_run_id=None,
) -> dict:
    """Validate a launch receipt and return a non-throwing report.

    This proves only local launch provenance/self-consistency. It is not a
    cryptographic provider identity assertion; another local process can edit
    the temporary mailbox.
    """
    errors: list[str] = []
    if not isinstance(receipt, Mapping):
        return {"valid": False, "errors": ["receipt_not_object"], "receipt": {}}
    try:
        original = dict(receipt)
        normalized = dict(receipt)
    except Exception:
        return {"valid": False, "errors": ["receipt_not_object"], "receipt": {}}
    if (
        "cross_provider_acknowledged" not in normalized
        and "cross_provider_ack" in normalized
    ):
        normalized["cross_provider_acknowledged"] = normalized.pop(
            "cross_provider_ack"
        )

    required = {
        "schema_version", "channel", "participant", "role", "runtime",
        "provider", "run_id", "nonce", "executable", "executable_sha256",
        "executable_version", "requested_model",
        "cross_provider_acknowledged", "receipt_hash",
    }
    missing = sorted(required - normalized.keys())
    errors.extend(f"missing:{field}" for field in missing)
    if normalized.get("schema_version") != LAUNCH_RECEIPT_SCHEMA_VERSION:
        errors.append("schema_version_invalid")

    for field, kind in (
        ("channel", "channel"), ("participant", "participant"),
        ("role", "role"), ("run_id", "run_id"),
    ):
        if field in normalized:
            try:
                _validate_slug(normalized[field], kind)
            except (TypeError, ValueError):
                errors.append(f"{field}_invalid")

    runtime = normalized.get("runtime")
    runtime_valid = isinstance(runtime, str) and runtime in RUNTIME_PROVIDERS
    if not runtime_valid:
        errors.append("runtime_invalid")
    elif normalized.get("provider") != RUNTIME_PROVIDERS[runtime]:
        errors.append("provider_runtime_mismatch")
    initiator_runtime = normalized.get("initiator_runtime")
    initiator_valid = (
        isinstance(initiator_runtime, str)
        and initiator_runtime in RUNTIME_PROVIDERS
    )
    if initiator_runtime is not None and not initiator_valid:
        errors.append("initiator_runtime_invalid")
    if not isinstance(normalized.get("nonce"), str) or not normalized.get("nonce"):
        errors.append("nonce_invalid")
    if not isinstance(normalized.get("executable_version"), str) or not normalized.get(
        "executable_version", ""
    ).strip():
        errors.append("executable_version_invalid")
    if normalized.get("requested_model") is not None and not isinstance(
        normalized.get("requested_model"), str
    ):
        errors.append("requested_model_invalid")
    if not isinstance(normalized.get("cross_provider_acknowledged"), bool):
        errors.append("cross_provider_acknowledged_invalid")
    if (
        initiator_valid
        and runtime_valid
        and RUNTIME_PROVIDERS[initiator_runtime] != RUNTIME_PROVIDERS[runtime]
        and normalized.get("cross_provider_acknowledged") is not True
    ):
        errors.append("cross_provider_ack_required")

    exe_hash = normalized.get("executable_sha256")
    if not isinstance(exe_hash, str) or not _SHA256_RE.fullmatch(exe_hash):
        errors.append("executable_sha256_invalid")
    exe_value = normalized.get("executable")
    if not isinstance(exe_value, str) or not exe_value:
        errors.append("executable_invalid")
    else:
        try:
            exe_path = Path(exe_value).expanduser().resolve(strict=True)
            if not exe_path.is_file():
                errors.append("executable_not_file")
            elif isinstance(exe_hash, str) and _SHA256_RE.fullmatch(exe_hash):
                if _sha256_file(exe_path) != exe_hash:
                    errors.append("executable_sha256_mismatch")
            normalized["executable"] = str(exe_path)
        except (OSError, RuntimeError, ValueError):
            errors.append("executable_unreadable")

    claimed_hash = normalized.get("receipt_hash")
    hash_payload = {k: v for k, v in normalized.items() if k != "receipt_hash"}
    if not isinstance(claimed_hash, str) or not _SHA256_RE.fullmatch(claimed_hash):
        errors.append("receipt_hash_invalid")
    else:
        normalized_hash = _canonical_hash_or_none(hash_payload)
        hash_candidates = {normalized_hash} if normalized_hash else set()
        if "cross_provider_ack" in original:
            alias_hash = _canonical_hash_or_none({
                key: value for key, value in original.items()
                if key != "receipt_hash"
            })
            if alias_hash:
                hash_candidates.add(alias_hash)
        if not hash_candidates:
            errors.append("receipt_not_canonical_json")
        elif claimed_hash not in hash_candidates:
            errors.append("receipt_hash_mismatch")

    expected = {
        "channel": expected_channel,
        "participant": expected_participant,
        "role": expected_role,
        "runtime": expected_runtime,
        "provider": expected_provider,
        "run_id": expected_run_id,
    }
    for field, value in expected.items():
        if value is not None and normalized.get(field) != value:
            errors.append(f"expected_{field}_mismatch")
    return {"valid": not errors, "errors": errors, "receipt": normalized}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _channel_dir(channel: str, root=MAILBOX_ROOT) -> Path:
    return Path(root) / _validate_slug(channel, "channel")


def _message_files(cdir: Path):
    if not cdir.is_dir():
        return []
    return sorted(p for p in cdir.glob("*.json") if not p.name.startswith("."))


def _seq_of(path: Path) -> int:
    return int(path.name.split("-", 1)[0])


def _attachment_path(cdir: Path, raw_path: str | os.PathLike) -> tuple[Path, str]:
    """Resolve an attachment inside this channel's attachments directory."""
    if not isinstance(raw_path, (str, os.PathLike)):
        raise ValueError("attachment path must be a string or Path")
    raw = Path(raw_path)
    base = (cdir / "attachments").resolve()
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        # CLI callers often pass a cwd-relative repo path, while library callers
        # normally use channel-relative ``attachments/name`` or a bare name.
        candidates.extend((Path.cwd() / raw, cdir / raw))
        if not raw.parts or raw.parts[0] != "attachments":
            candidates.append(base / raw)
    selected = next((p for p in candidates if p.exists()), candidates[-1])
    try:
        resolved = selected.resolve(strict=True)
        relative = resolved.relative_to(base)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(
            "attachment must be an existing file inside this channel's "
            "attachments directory"
        ) from exc
    if not resolved.is_file():
        raise ValueError("attachment must resolve to a regular file")
    return resolved, (Path("attachments") / relative).as_posix()


def _normalize_attachment(attachment, cdir: Path) -> dict:
    supplied_hash = None
    supplied_size = None
    if isinstance(attachment, Mapping):
        if "path" not in attachment:
            raise ValueError("attachment object requires path")
        raw_path = attachment["path"]
        supplied_hash = attachment.get("sha256")
        supplied_size = attachment.get("bytes")
    else:
        raw_path = attachment
    path, relative = _attachment_path(cdir, raw_path)
    actual_hash = _sha256_file(path)
    actual_size = path.stat().st_size
    if supplied_hash is not None and supplied_hash != actual_hash:
        raise ValueError("attachment sha256 does not match file bytes")
    if supplied_size is not None and supplied_size != actual_size:
        raise ValueError("attachment byte count does not match file size")
    return {"path": relative, "bytes": actual_size, "sha256": actual_hash}


def send_message(
    channel: str,
    sender: str,
    text: str,
    *,
    role: str | None = None,
    runtime: str | None = None,
    provider: str | None = None,
    run_id: str | None = None,
    identity_receipt: Mapping | None = None,
    attachment=None,
    root=MAILBOX_ROOT,
) -> int:
    """Append a message to a channel. Returns its allocated sequence number.

    Sequence allocation is lock-free: scan the max existing seq, try to O_EXCL
    create seq+1, and on collision (a concurrent sender won the race) recompute
    and retry -- the same pattern as ticket id reservation.
    """
    channel = _validate_slug(channel, "channel")
    sender = _validate_slug(sender, "sender")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if role is not None:
        role = _validate_slug(role, "role")
    if runtime is not None:
        runtime = _validate_runtime(runtime)
        expected_provider = RUNTIME_PROVIDERS[runtime]
        if provider is None:
            provider = expected_provider
        elif provider != expected_provider:
            raise ValueError("provider does not match runtime")
    elif provider is not None:
        raise ValueError("provider requires runtime")
    if run_id is not None:
        run_id = _validate_slug(run_id, "run_id")
    cdir = _channel_dir(channel, root)
    cdir.mkdir(parents=True, exist_ok=True)
    normalized_attachment = (
        _normalize_attachment(attachment, cdir) if attachment is not None else None
    )
    normalized_receipt = None
    if identity_receipt is not None:
        report = validate_launch_receipt(
            identity_receipt,
            expected_channel=channel,
            expected_role=role,
            expected_runtime=runtime,
            expected_provider=provider,
            expected_run_id=run_id,
        )
        if not report["valid"]:
            raise ValueError(
                "invalid identity_receipt: " + ",".join(report["errors"])
            )
        normalized_receipt = report["receipt"]
    for _ in range(_MAX_SEQ_ATTEMPTS):
        files = _message_files(cdir)
        nxt = (_seq_of(files[-1]) + 1) if files else 1
        path = cdir / f"{nxt:04d}-{sender}.json"
        message = {
            "channel": channel, "seq": nxt, "from": sender,
            "text": text, "ts": _now_iso(),
        }
        optional = {
            "role": role,
            "runtime": runtime,
            "provider": provider,
            "run_id": run_id,
            "identity_receipt": normalized_receipt,
            "attachment": normalized_attachment,
        }
        message.update({key: value for key, value in optional.items() if value is not None})
        payload = json.dumps(message, ensure_ascii=False)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        return nxt
    raise RuntimeError(f"could not allocate a message sequence in {cdir}")


def _cursor_path(cdir: Path, me: str) -> Path:
    return cdir / f".cursor-{_validate_slug(me, 'agent')}"


def _read_cursor(cdir: Path, me: str) -> int:
    p = _cursor_path(cdir, me)
    if p.exists():
        try:
            return int(p.read_text().strip() or 0)
        except ValueError:
            return 0
    return 0


def _write_cursor(cdir: Path, me: str, seq: int) -> None:
    _cursor_path(cdir, me).write_text(str(seq))


def recv_message(channel: str, me: str, *, peer: str | None = None,
                 timeout=DEFAULT_TIMEOUT, root=MAILBOX_ROOT, poll=POLL_SECONDS):
    """Block until the next unread message for ``me`` arrives; return it (dict)
    or ``None`` on timeout.

    "Next unread" = lowest sequence past this agent's cursor that was NOT sent
    by ``me`` (and, if ``peer`` is given, was sent by ``peer``). The cursor is
    advanced to the returned message, so plain alternating send/recv just works
    without tracking sequence numbers by hand. Own messages passed over while
    waiting are skipped permanently.
    """
    channel = _validate_slug(channel, "channel")
    me = _validate_slug(me, "agent")
    if peer is not None:
        peer = _validate_slug(peer, "peer")
    cdir = _channel_dir(channel, root)
    cdir.mkdir(parents=True, exist_ok=True)
    cursor = _read_cursor(cdir, me)
    deadline = time.time() + timeout
    while True:
        for path in _message_files(cdir):
            seq = _seq_of(path)
            if seq <= cursor:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue  # mid-write or unreadable; try again next poll
            sender = data.get("from")
            if sender == me:
                cursor = seq
                _write_cursor(cdir, me, seq)
                continue
            if peer is not None and sender != peer:
                continue
            _write_cursor(cdir, me, seq)
            return data
        if time.time() >= deadline:
            return None
        time.sleep(poll)


def read_transcript(channel: str, *, root=MAILBOX_ROOT):
    """Return all messages in a channel, ordered by sequence."""
    cdir = _channel_dir(channel, root)
    out = []
    for path in _message_files(cdir):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


_EXP_ID_RE = re.compile(r"exp-\d{8}-\d{3}")
_PATH_RE = re.compile(
    r"(?:data|docs|experiments|quant|scripts|operator_inputs)/"
    r"[A-Za-z0-9_./\-*]+"
)


def extract_references(text: str):
    """Pull checkable references out of a message: experiment ids and repo
    paths. Returns (exp_ids, paths) as sets. Used by the dangling-ref pre-filter.
    """
    exp_ids = set(_EXP_ID_RE.findall(text or ""))
    paths = {p.rstrip(".,);:") for p in _PATH_RE.findall(text or "")}
    return exp_ids, paths


def _debate_role_identity_errors(role_run_ids, role_participants) -> list[dict]:
    """Reject one process/participant claiming two independent debate roles."""
    failures = []
    roles = ("initiator", "challenger", "verifier")
    for index, left in enumerate(roles):
        for right in roles[index + 1:]:
            shared_runs = role_run_ids.get(left, set()) & role_run_ids.get(right, set())
            if shared_runs:
                failures.append({
                    "seq": None, "from": None,
                    "error": f"role_run_id_collision:{left}:{right}",
                })
            shared_people = (
                role_participants.get(left, set())
                & role_participants.get(right, set())
            )
            if shared_people:
                failures.append({
                    "seq": None, "from": None,
                    "error": f"role_participant_collision:{left}:{right}",
                })
    return failures


def verify_channel(channel: str, *, root=MAILBOX_ROOT, repo_root=REPO_ROOT):
    """Verify references plus opt-in launch receipts and attachments.

    Legacy rows retain the old existence-only behavior and are never labeled
    cross-model verified. Structured rows must carry complete, receipt-bound
    role/runtime/provider/run metadata. ``from`` is a routing/display string,
    not an identity credential and is deliberately not compared to the receipt
    participant.
    """
    channel = _validate_slug(channel, "channel")
    repo_root = Path(repo_root)
    rows = read_transcript(channel, root=root)
    cdir = _channel_dir(channel, root)
    dangling = []
    identity_errors = []
    attachment_errors = []
    message_errors = []
    attachment_sha256 = {}
    structured_count = 0
    legacy_count = 0
    runtimes = set()
    providers = set()
    role_run_ids: dict[str, set[str]] = {}
    role_participants: dict[str, set[str]] = {}
    requested_models_by_role: dict[str, set[str]] = {}
    normalized_models_by_role: dict[str, set[str]] = {}
    every_receipt_has_requested_model = True
    cross_provider_acknowledged = False
    checked = 0
    for m in rows:
        seq, who, text = m.get("seq"), m.get("from"), m.get("text", "")
        if m.get("channel") != channel:
            message_errors.append({"seq": seq, "from": who,
                                   "error": "message_channel_mismatch"})
        exp_ids, paths = extract_references(text)
        for eid in sorted(exp_ids):
            checked += 1
            if not (repo_root / "experiments" / "tickets" / f"{eid}.json").exists():
                dangling.append({"seq": seq, "from": who, "kind": "exp_id",
                                 "ref": eid})
        for p in sorted(paths):
            checked += 1
            if not (repo_root / p).exists():
                dangling.append({"seq": seq, "from": who, "kind": "path",
                                 "ref": p})

        structured_keys = {
            "role", "runtime", "provider", "run_id", "identity_receipt",
            "attachment",
        }
        if not (structured_keys & m.keys()):
            legacy_count += 1
            continue
        structured_count += 1
        missing = sorted(
            {"role", "runtime", "provider", "run_id", "identity_receipt"}
            - m.keys()
        )
        for field in missing:
            identity_errors.append({
                "seq": seq, "from": who, "error": f"message_missing:{field}",
            })
        report = validate_launch_receipt(
            m.get("identity_receipt"),
            expected_channel=channel,
            expected_role=m.get("role"),
            expected_runtime=m.get("runtime"),
            expected_provider=m.get("provider"),
            expected_run_id=m.get("run_id"),
        )
        for error in report["errors"]:
            identity_errors.append({"seq": seq, "from": who, "error": error})
        if report["valid"]:
            receipt = report["receipt"]
            runtimes.add(receipt["runtime"])
            providers.add(receipt["provider"])
            role_run_ids.setdefault(receipt["role"], set()).add(
                receipt["run_id"]
            )
            role_participants.setdefault(receipt["role"], set()).add(
                receipt["participant"]
            )
            requested_model = receipt.get("requested_model")
            if isinstance(requested_model, str) and requested_model.strip():
                stripped_model = requested_model.strip()
                requested_models_by_role.setdefault(receipt["role"], set()).add(
                    stripped_model
                )
                normalized_models_by_role.setdefault(receipt["role"], set()).add(
                    stripped_model.casefold()
                )
            else:
                every_receipt_has_requested_model = False
            cross_provider_acknowledged = (
                cross_provider_acknowledged
                or receipt.get("cross_provider_acknowledged") is True
            )

        descriptor = m.get("attachment")
        if descriptor is not None:
            if not isinstance(descriptor, Mapping):
                attachment_errors.append({
                    "seq": seq, "from": who, "error": "attachment_not_object",
                })
            else:
                try:
                    path, relative = _attachment_path(cdir, descriptor.get("path"))
                    actual_hash = _sha256_file(path)
                    actual_size = path.stat().st_size
                    if descriptor.get("sha256") != actual_hash:
                        raise ValueError("attachment_sha256_mismatch")
                    if descriptor.get("bytes") != actual_size:
                        raise ValueError("attachment_bytes_mismatch")
                    attachment_sha256[relative] = actual_hash
                except (OSError, TypeError, ValueError) as exc:
                    attachment_errors.append({
                        "seq": seq, "from": who,
                        "error": str(exc) or type(exc).__name__,
                    })

    identity_errors.extend(
        _debate_role_identity_errors(role_run_ids, role_participants)
    )
    errors = message_errors + identity_errors + attachment_errors
    structured_valid = structured_count > 0 and legacy_count == 0 and not errors
    cross_model_verified = (
        structured_valid
        and {"codex", "claude"}.issubset(runtimes)
        and {"openai", "anthropic"}.issubset(providers)
        and cross_provider_acknowledged
    )
    required_debate_roles = {"initiator", "challenger", "verifier"}
    required_roles_present = (
        required_debate_roles.issubset(role_run_ids)
        and required_debate_roles.issubset(role_participants)
        and required_debate_roles.issubset(normalized_models_by_role)
    )
    required_model_ids = set().union(*(
        normalized_models_by_role.get(role, set())
        for role in required_debate_roles
    ))
    codex_model_diverse_verified = (
        structured_valid
        and runtimes == {"codex"}
        and providers == {"openai"}
        and every_receipt_has_requested_model
        and required_roles_present
        and normalized_models_by_role["initiator"].isdisjoint(
            normalized_models_by_role["challenger"]
        )
        and normalized_models_by_role["verifier"].isdisjoint(
            normalized_models_by_role["challenger"]
        )
        and len(required_model_ids) >= 2
    )
    if legacy_count:
        verification_level = "legacy_existence_only"
    elif not structured_count:
        verification_level = "empty"
    elif errors:
        verification_level = "structured_invalid"
    elif cross_model_verified:
        verification_level = "launcher_attested_cross_model"
    elif codex_model_diverse_verified:
        verification_level = "launcher_attested_codex_model_diverse"
    else:
        verification_level = "launcher_attested_single_runtime"
    return {
        "channel": channel,
        "checked": checked,
        "dangling": dangling,
        "transcript_sha256": canonical_hash(rows),
        "attachment_sha256": attachment_sha256,
        "structured_messages": structured_count,
        "legacy_messages": legacy_count,
        "message_errors": message_errors,
        "identity_errors": identity_errors,
        "attachment_errors": attachment_errors,
        "errors": errors,
        "role_run_ids": {key: sorted(value) for key, value in role_run_ids.items()},
        "role_participants": {
            key: sorted(value) for key, value in role_participants.items()
        },
        "requested_models_by_role": {
            key: sorted(value)
            for key, value in requested_models_by_role.items()
        },
        "structured_valid": structured_valid,
        "cross_model_verified": cross_model_verified,
        "codex_model_diverse_verified": codex_model_diverse_verified,
        "verification_level": verification_level,
    }


def list_channels(*, root=MAILBOX_ROOT):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and _SLUG_RE.fullmatch(p.name)
        and len(p.name) <= _MAX_SLUG_LENGTH
        and p.name.upper().split(".", 1)[0] not in _WINDOWS_DEVICE_NAMES
    )


# ---------------------------------------------------------------------------
# Dispatch: one-sided trigger that STARTS the peer agent (codex) and opens the
# conversation, so a mailbox exchange no longer requires both agents to already
# be alive. The dispatcher speaks first; the spawned peer listens first.
# ---------------------------------------------------------------------------

# The npm wrapper (codex.CMD) is broken on this machine (missing the win32-x64
# platform package), so discovery tests real binaries and falls back to the
# desktop app's bundled CLIs.
CODEX_CANDIDATES = [
    "codex",
    r"C:\Users\Administrator\.codex\plugins\.plugin-appserver\codex.exe",
    r"C:\Users\Administrator\.codex\.sandbox-bin\codex.exe",
]
CLAUDE_CANDIDATES = ["claude", "claude.exe"]  # native CLI names


def _glob_runtime_candidates(runtime: str) -> list[str]:
    home = Path.home()
    patterns = {
        "codex": [
            home / ".vscode" / "extensions" / "openai.chatgpt-*" / "bin" / "*" / "codex.exe",
            home / ".vscode" / "extensions" / "openai.chatgpt-*" / "bin" / "*" / "codex",
            home / ".codex" / "plugins" / "*" / "codex.exe",
        ],
        "claude": [
            home / ".vscode" / "extensions" / "anthropic.claude-code-*" / "resources" / "native-binary" / "claude.exe",
            home / ".vscode" / "extensions" / "anthropic.claude-code-*" / "resources" / "native-binary" / "claude",
        ],
    }
    found: list[str] = []
    for pattern in patterns[runtime]:
        relative_pattern = pattern.relative_to(home).as_posix()
        found.extend(str(p) for p in sorted(home.glob(relative_pattern)))
    if runtime == "claude":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            cache = Path(local_app_data) / "Packages"
            cache_patterns = (
                "Claude_*/LocalCache/Roaming/Claude/claude-code/*/claude.exe",
                "Claude_*/LocalCache/Roaming/Claude/claude-code-vm/*/claude",
            )
            for pattern in cache_patterns:
                found.extend(str(p) for p in sorted(cache.glob(pattern)))
    return found


def _candidate_key(candidate: str) -> str:
    try:
        return os.path.normcase(str(Path(candidate).expanduser().resolve()))
    except (OSError, RuntimeError):
        return os.path.normcase(candidate)


def _runtime_candidates(runtime: str, explicit: str | None = None) -> list[str]:
    candidates = [explicit] if explicit else []
    which = shutil.which(runtime)
    if which:
        candidates.append(which)
    candidates.extend(CODEX_CANDIDATES if runtime == "codex" else CLAUDE_CANDIDATES)
    candidates.extend(_glob_runtime_candidates(runtime))
    seen = set()
    unique = []
    for candidate in candidates:
        if not candidate:
            continue
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _probe_runtime_exe(candidate: str) -> dict | None:
    """Return executable/version only when the native CLI answers --version."""
    try:
        out = subprocess.run(
            [candidate, "--version"], capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    resolved = shutil.which(candidate) or candidate
    try:
        path = Path(resolved).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not path.is_file():
        return None
    version_text = (out.stdout or out.stderr or "unknown").strip()
    version = version_text.splitlines()[0] if version_text else "unknown"
    return {"exe": str(path), "version": version}


def _find_runtime_info(runtime: str, explicit: str | None = None) -> dict | None:
    runtime = _validate_runtime(runtime)
    for candidate in _runtime_candidates(runtime, explicit):
        info = _probe_runtime_exe(candidate)
        if info is not None:
            return info
    return None


def find_codex_exe(explicit: str | None = None) -> str | None:
    """Return the first codex binary that answers ``--version`` with rc 0."""
    info = _find_runtime_info("codex", explicit)
    return info["exe"] if info else None


def find_claude_exe(explicit: str | None = None) -> str | None:
    """Return the first native Claude CLI that passes a ``--version`` probe."""
    info = _find_runtime_info("claude", explicit)
    return info["exe"] if info else None


def find_runtime_exe(runtime: str, explicit: str | None = None) -> str | None:
    info = _find_runtime_info(runtime, explicit)
    return info["exe"] if info else None


def _bootstrap_prompt(*, channel: str, me: str, peer: str, rounds: int,
                      python_exe: str, repo_root: Path, role: str,
                      runtime: str, provider: str, run_id: str,
                      receipt_path: Path) -> str:
    attachments = f"data/agent_mailbox/{channel}/attachments"
    mailbox = "scripts/agent_mailbox.py"
    return (
        f"You are agent \"{peer}\" in a file-mailbox conversation with agent "
        f"\"{me}\" inside the repo at {repo_root}. The protocol is documented "
        f"in docs/agent_mailbox.md. You LISTEN FIRST.\n\n"
        f"Loop (at most {rounds} of your turns):\n"
        f"1. Receive: run\n"
        f"   {python_exe} {mailbox} recv --channel {channel} --me {peer} --timeout 300\n"
        f"   Exit code 2 means timeout: just re-run the same command. The first\n"
        f"   message you receive is your task brief from {me}.\n"
        f"2. Do what the message asks. If the task needs unavailable network\n"
        f"   access, report that boundary rather than inventing evidence.\n"
        f"3. Reply: for anything longer than a few lines, write the full body\n"
        f"   to a new file under {attachments}/ (create the directory if\n"
        f"   needed) and send a SHORT pointer message instead, e.g.\n"
        f"   {python_exe} {mailbox} send --channel {channel} --me {peer} "
        f"--role {role} --runtime {runtime} --provider {provider} "
        f"--run-id {run_id} --identity-receipt {receipt_path} "
        f"--attachment {attachments}/round1.md "
        f"--text \"reply in attachment\"\n"
        f"   Avoid shell-quoting pitfalls: keep --text short, plain, no nested "
        f"quotes.\n"
        f"4. Then go back to step 1 and wait for {me}'s next message.\n"
        f"5. Stop when you send or receive a message containing the token DONE,"
        f" or when you have used your {rounds} turns.\n\n"
        f"Hard rules: do not modify tracked repo files; write only under "
        f"data/agent_mailbox/{channel}/; do not run git commit; do not reserve "
        f"experiment ids. Your final message must contain DONE."
    )


def _resolve_dispatch_runtime(runtime: str, peer: str,
                              runtime_exe: str | None,
                              codex_exe: str | None) -> str:
    runtime = _validate_runtime(runtime, allow_auto=True)
    if runtime != "auto":
        if codex_exe and runtime != "codex":
            raise ValueError("--codex-exe can only be used with codex runtime")
        return runtime
    if codex_exe:
        return "codex"
    peer_hint = peer.lower()
    if peer_hint in RUNTIME_PROVIDERS:
        return peer_hint
    if runtime_exe and "claude" in Path(runtime_exe).name.lower():
        return "claude"
    return "codex"  # backwards-compatible dispatch default


def _runtime_command(exe: str, runtime: str, prompt: str, *, sandbox: str,
                     model: str | None) -> list[str]:
    if runtime == "codex":
        cmd = [exe, "exec", "--sandbox", sandbox]
        if model:
            cmd += ["--model", model]
        cmd.append(prompt)
        return cmd
    cmd = [exe, "--print"]
    if sandbox == "danger-full-access":
        cmd.append("--dangerously-skip-permissions")
    elif sandbox == "workspace-write":
        cmd += ["--permission-mode", "acceptEdits"]
    else:
        cmd += ["--permission-mode", "plan"]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    return cmd


def _write_json_exclusive(path: Path, value: Mapping) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")


def dispatch_peer(channel: str, me: str, task: str, *,
                  peer: str = "codex",
                  rounds: int = 3,
                  codex_exe: str | None = None,
                  sandbox: str = "workspace-write",
                  model: str | None = None,
                  initiator_runtime: str = "auto",
                  initiator_model: str | None = None,
                  initiator_role: str = "initiator",
                  initiator_runtime_exe: str | None = None,
                  initiator_run_id: str | None = None,
                  runtime: str = "auto",
                  peer_role: str = "challenger",
                  acknowledge_cross_provider: bool = False,
                  runtime_exe: str | None = None,
                  run_id: str | None = None,
                  root=MAILBOX_ROOT,
                  repo_root: Path = REPO_ROOT) -> dict:
    """Send the opener and spawn the peer agent in the background.

    Returns {seq, pid, exe, log}. The caller then simply alternates
    ``recv``/``send`` as the speaks-first side of the normal turn recipe.
    """
    channel = _validate_slug(channel, "channel")
    me = _validate_slug(me, "agent")
    peer = _validate_slug(peer, "peer")
    peer_role = _validate_slug(peer_role, "role")
    initiator_role = _validate_slug(initiator_role, "role")
    if rounds < 1:
        raise ValueError("rounds must be at least 1")
    if initiator_model is not None and not isinstance(initiator_model, str):
        raise ValueError("initiator_model must be a string or None")
    if initiator_runtime == "auto" and initiator_model is not None:
        raise ValueError(
            "initiator_model requires an explicit initiator_runtime"
        )
    if runtime_exe and codex_exe and runtime_exe != codex_exe:
        raise ValueError("pass only one of runtime_exe or codex_exe")
    resolved_runtime = _resolve_dispatch_runtime(
        runtime, peer, runtime_exe, codex_exe,
    )
    explicit_exe = runtime_exe or codex_exe
    info = _find_runtime_info(resolved_runtime, explicit_exe)
    if info is None:
        raise RuntimeError(
            f"no working {resolved_runtime} binary found (tried PATH, VS Code "
            "extensions, and known app caches); pass --runtime-exe explicitly"
        )
    exe = info["exe"]
    if initiator_runtime == "auto":
        resolved_initiator = resolved_runtime  # legacy dispatch is unverified
    else:
        resolved_initiator = _validate_runtime(initiator_runtime)
    cross_provider = (
        RUNTIME_PROVIDERS[resolved_initiator]
        != RUNTIME_PROVIDERS[resolved_runtime]
    )
    if cross_provider and not acknowledge_cross_provider:
        raise RuntimeError(
            "cross-provider launch requires --acknowledge-cross-provider"
        )
    initiator_info = None
    if initiator_runtime != "auto":
        if resolved_initiator == resolved_runtime and not initiator_runtime_exe:
            initiator_info = info
        else:
            initiator_info = _find_runtime_info(
                resolved_initiator, initiator_runtime_exe,
            )
        if initiator_info is None:
            raise RuntimeError(
                f"no working {resolved_initiator} initiator binary found; "
                "pass --initiator-runtime-exe explicitly"
            )
    run_id = _validate_slug(run_id or f"run-{uuid.uuid4().hex}", "run_id")
    receipt = make_launch_receipt(
        channel=channel,
        participant=peer,
        role=peer_role,
        runtime=resolved_runtime,
        run_id=run_id,
        executable=exe,
        executable_version=info["version"],
        requested_model=model,
        cross_provider_acknowledged=acknowledge_cross_provider,
        initiator_runtime=resolved_initiator,
    )
    initiator_receipt = None
    resolved_initiator_run_id = None
    if initiator_info is not None:
        resolved_initiator_run_id = _validate_slug(
            initiator_run_id or f"run-{uuid.uuid4().hex}", "initiator_run_id",
        )
        if resolved_initiator_run_id == run_id:
            raise ValueError("initiator and peer run IDs must be distinct")
        initiator_receipt = make_launch_receipt(
            channel=channel,
            participant=me,
            role=initiator_role,
            runtime=resolved_initiator,
            run_id=resolved_initiator_run_id,
            executable=initiator_info["exe"],
            executable_version=initiator_info["version"],
            requested_model=initiator_model,
            cross_provider_acknowledged=acknowledge_cross_provider,
            initiator_runtime=resolved_initiator,
        )
    cdir = _channel_dir(channel, root)
    (cdir / "attachments").mkdir(parents=True, exist_ok=True)
    receipt_path = cdir / f".launch-{peer}-{run_id}.json"
    _write_json_exclusive(receipt_path, receipt)
    initiator_receipt_path = None
    if initiator_receipt is not None:
        initiator_receipt_path = (
            cdir / f".launch-{me}-{resolved_initiator_run_id}.json"
        )
        _write_json_exclusive(initiator_receipt_path, initiator_receipt)
        seq = send_message(
            channel, me, task,
            role=initiator_role,
            runtime=resolved_initiator,
            provider=RUNTIME_PROVIDERS[resolved_initiator],
            run_id=resolved_initiator_run_id,
            identity_receipt=initiator_receipt,
            root=root,
        )
    else:
        seq = send_message(channel, me, task, root=root)
    # A peer launched into an existing channel must consume this dispatch's
    # opener, not the channel's first historical message.  Seed its cursor to
    # immediately before the opener; on a fresh channel this is the legacy 0.
    _write_cursor(cdir, peer, max(_read_cursor(cdir, peer), seq - 1))
    prompt = _bootstrap_prompt(
        channel=channel, me=me, peer=peer, rounds=rounds,
        python_exe="python", repo_root=repo_root, role=peer_role,
        runtime=resolved_runtime, provider=RUNTIME_PROVIDERS[resolved_runtime],
        run_id=run_id, receipt_path=receipt_path,
    )
    log_path = cdir / f".{peer}-exec.log"
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 - handed to child
    cmd = _runtime_command(
        exe, resolved_runtime, prompt, sandbox=sandbox, model=model,
    )
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        )
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    except Exception:
        log_f.close()
        for path in (receipt_path, initiator_receipt_path):
            if path is not None:
                try:
                    path.unlink()
                except OSError:
                    pass
        raise
    log_f.close()
    (cdir / f".{peer}-exec.pid").write_text(str(proc.pid))
    return {
        "seq": seq, "pid": proc.pid, "exe": exe, "log": str(log_path),
        "runtime": resolved_runtime,
        "provider": RUNTIME_PROVIDERS[resolved_runtime],
        "model": model,
        "run_id": run_id,
        "role": peer_role,
        "receipt": receipt,
        "receipt_path": str(receipt_path),
        "initiator_run_id": resolved_initiator_run_id,
        "initiator_role": initiator_role if initiator_receipt else None,
        "initiator_model": initiator_model if initiator_receipt else None,
        "initiator_receipt": initiator_receipt,
        "initiator_receipt_path": (
            str(initiator_receipt_path) if initiator_receipt_path else None
        ),
    }


def _cmd_send(a):
    receipt = None
    if a.identity_receipt is not None:
        try:
            receipt = json.loads(a.identity_receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"could not read identity receipt: {exc}") from exc
    seq = send_message(
        a.channel, a.me, a.text,
        role=a.role, runtime=a.runtime, provider=a.provider, run_id=a.run_id,
        identity_receipt=receipt, attachment=a.attachment, root=a.root,
    )
    print(f"[sent channel={a.channel} seq={seq} from={a.me}]")


def _cmd_recv(a):
    msg = recv_message(a.channel, a.me, peer=a.peer, timeout=a.timeout,
                       root=a.root)
    if msg is None:
        print(f"[TIMEOUT channel={a.channel} me={a.me}; re-run this recv]",
              file=sys.stderr)
        raise SystemExit(2)
    print(f"[from={msg['from']} seq={msg['seq']}]", file=sys.stderr)
    print(msg["text"])


def _cmd_transcript(a):
    for m in read_transcript(a.channel, root=a.root):
        print(f"{m['from']} (seq {m['seq']}): {m['text']}")


def _cmd_list(a):
    for name in list_channels(root=a.root):
        print(name)


def _cmd_dispatch(a):
    info = dispatch_peer(
        a.channel, a.me, a.task,
        peer=a.peer, rounds=a.rounds, codex_exe=a.codex_exe,
        sandbox=a.sandbox, model=a.model,
        initiator_runtime=a.initiator_runtime,
        initiator_model=a.initiator_model,
        initiator_role=a.initiator_role,
        initiator_runtime_exe=a.initiator_runtime_exe,
        initiator_run_id=a.initiator_run_id,
        runtime=a.runtime,
        peer_role=a.peer_role,
        acknowledge_cross_provider=a.acknowledge_cross_provider,
        runtime_exe=a.runtime_exe, run_id=a.run_id, root=a.root,
    )
    print(f"[dispatched channel={a.channel} opener_seq={info['seq']} "
          f"peer={a.peer} pid={info['pid']}]")
    print(f"[exe={info['exe']}]")
    print(f"[log={info['log']}]")
    print(f"next: python scripts/agent_mailbox.py recv --channel {a.channel} "
          f"--me {a.me} --peer {a.peer}", file=sys.stderr)


def _cmd_verify(a):
    rep = verify_channel(a.channel, root=a.root)
    d = rep["dangling"]
    print(f"[verify channel={rep['channel']} checked={rep['checked']} "
          f"dangling={len(d)}]")
    for f in d:
        print(f"  DANGLING {f['kind']}: {f['ref']}  "
              f"(cited by {f['from']} seq {f['seq']})")
    print(f"[verification_level={rep['verification_level']} "
          f"cross_model_verified={str(rep['cross_model_verified']).lower()} "
          f"codex_model_diverse_verified="
          f"{str(rep['codex_model_diverse_verified']).lower()} "
          f"transcript_sha256={rep['transcript_sha256']}]",
          file=sys.stderr)
    for failure in rep["errors"]:
        print(f"  INVALID {failure['error']} "
              f"(message from {failure.get('from')} seq {failure.get('seq')})")
    print("note: launch receipts are local launcher attestations, not "
          "cryptographic provider identity. Reference existence also cannot "
          "catch a real but mis-attributed citation; see docs/agent_mailbox.md.",
          file=sys.stderr)
    if d or rep["errors"]:
        raise SystemExit(1)


def main(argv=None):
    # Messages are UTF-8; force UTF-8 on the console streams so non-ASCII text
    # (e.g. Chinese) round-trips through recv/transcript even when the Windows
    # console code page is cp936/GBK. The stored files are always UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mailbox-root", dest="root", default=MAILBOX_ROOT,
                    type=Path, help="Override the mailbox root (for tests).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send", help="Append a message to a channel.")
    s.add_argument("--channel", required=True)
    s.add_argument("--me", required=True, help="Your agent name.")
    s.add_argument("--text", required=True)
    s.add_argument("--role", default=None)
    s.add_argument("--runtime", choices=sorted(RUNTIME_PROVIDERS), default=None)
    s.add_argument("--provider", choices=sorted(set(RUNTIME_PROVIDERS.values())),
                   default=None)
    s.add_argument("--run-id", default=None)
    s.add_argument("--identity-receipt", type=Path, default=None,
                   help="Launcher receipt JSON file for a structured message.")
    s.add_argument("--attachment", default=None,
                   help="File inside this channel's attachments directory.")
    s.set_defaults(func=_cmd_send)

    r = sub.add_parser("recv", help="Block for the next message addressed to you.")
    r.add_argument("--channel", required=True)
    r.add_argument("--me", required=True, help="Your agent name.")
    r.add_argument("--peer", default=None,
                   help="Only accept messages from this sender.")
    r.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    r.set_defaults(func=_cmd_recv)

    t = sub.add_parser("transcript", help="Print a channel in order.")
    t.add_argument("--channel", required=True)
    t.set_defaults(func=_cmd_transcript)

    ls = sub.add_parser("list", help="List channels.")
    ls.set_defaults(func=_cmd_list)

    v = sub.add_parser(
        "verify",
        help="Verify references, structured launch receipts, and attachments.",
    )
    v.add_argument("--channel", required=True)
    v.set_defaults(func=_cmd_verify)

    d = sub.add_parser(
        "dispatch",
        help="Send the opener AND spawn a native Codex or Claude peer in the "
             "background so a conversation can start one-sided.",
    )
    d.add_argument("--channel", required=True)
    d.add_argument("--me", required=True, help="Your agent name (speaks first).")
    d.add_argument("--task", required=True, help="Opener/task brief text.")
    d.add_argument("--peer", default="codex", help="Spawned agent's name.")
    d.add_argument("--rounds", type=int, default=3,
                   help="Max peer turns before it must stop (default 3).")
    d.add_argument("--codex-exe", default=None,
                   help="Legacy alias for --runtime-exe with codex runtime.")
    d.add_argument("--runtime-exe", default=None,
                   help="Explicit native runtime binary; otherwise discovered.")
    d.add_argument("--runtime", default="auto",
                   choices=["auto", *sorted(RUNTIME_PROVIDERS)],
                   help="Peer runtime; auto preserves the historical codex default.")
    d.add_argument("--initiator-runtime", default="auto",
                   choices=["auto", *sorted(RUNTIME_PROVIDERS)],
                   help="Runtime starting dispatch; auto is legacy/unverified.")
    d.add_argument("--initiator-model", default=None,
                   help="Requested model bound into the initiator receipt.")
    d.add_argument("--initiator-role", default="initiator",
                   help="Receipt-bound role for an explicit initiator runtime.")
    d.add_argument("--initiator-runtime-exe", default=None,
                   help="Native initiator CLI used for its launch receipt.")
    d.add_argument("--initiator-run-id", default=None,
                   help="Optional distinct initiator run slug.")
    d.add_argument("--peer-role", default="challenger",
                   help="Receipt-bound role for the launched peer.")
    d.add_argument("--acknowledge-cross-provider", action="store_true",
                   help="Required when initiator and peer providers differ.")
    d.add_argument("--run-id", default=None,
                   help="Optional stable run slug; generated when omitted.")
    d.add_argument("--sandbox", default="workspace-write",
                   choices=["read-only", "workspace-write", "danger-full-access"],
                   help="Runtime sandbox/permission mode (network research may "
                        "need danger-full-access on this machine).")
    d.add_argument("--model", default=None, help="Optional runtime model override.")
    d.set_defaults(func=_cmd_dispatch)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
