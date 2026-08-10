#!/usr/bin/env python3
"""Three-command facade for Ginger's alpha-search operator workflow.

The facade removes redundant human invocations; it does not replace the
Investment Team card contract, D0-D3, promotion validation, experiment
reservation/claim receipts, Gate judging, or the repository audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alpha_debate import normalize_ticket_proposal, revalidate_ticket_promotion  # noqa: E402
from create_experiment_ticket import _novelty_check  # noqa: E402
from experiment_registry import (  # noqa: E402
    ACTIVE_STATUSES,
    build_log_draft,
    FINAL_STATUSES,
    claim_experiment_decontended,
    file_lock,
    judge_results,
    lean_reflection_quality_reasons,
    rebuild_registry_from_tickets,
    reservation_intent_for,
    reserve_experiment,
    save_experiment_log_entry,
    strip_oversized_fields,
    update_result_decontended,
)
from quant.data_paths import atomic_write_json  # noqa: E402


QUALIFICATION_SCHEMA_VERSION = 1
EXECUTION_SPEC_SCHEMA_VERSION = 1
QUALIFICATION_RECORD_TYPE = "alpha_workflow_qualification"
EXECUTION_SPEC_RECORD_TYPE = "alpha_workflow_execution_spec"
FINISH_INTENT_SCHEMA_VERSION = 1
FINISH_INTENT_RECORD_TYPE = "alpha_workflow_finish_intent"
FINISH_REFLECTION_FIELDS = {
    "change_summary",
    "why_result_happened",
    "realized_failure_mode",
    "forbidden_near_neighbor_retry",
    "new_evidence_required",
}


class WorkflowError(RuntimeError):
    """A fail-closed facade error with a stable machine code."""

    def __init__(self, code: str, detail: str, **context: Any) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.context = context

    def payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": self.code,
            "detail": self.detail,
            **self.context,
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise WorkflowError("input_read_failed", f"{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(
            "invalid_json",
            f"{path}:{exc.lineno}:{exc.colno}: {exc.msg}",
        ) from exc


def _write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise WorkflowError(
            "output_exists",
            f"refusing to overwrite existing workflow artifact: {path}",
        ) from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _ensure_command_output(path: Path, value: Any) -> None:
    """Accept a delegate-created output only when it equals returned JSON."""

    if not path.exists():
        _write_json_exclusive(path, value)
        return
    observed = _load_json(path)
    if _canonical_hash(observed) != _canonical_hash(value):
        raise WorkflowError(
            "delegate_output_mismatch",
            f"delegate stdout does not match its output file: {path}",
        )


def _resolve_repo_path(
    value: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
    must_exist: bool = False,
) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise WorkflowError(
            "path_outside_repo",
            f"workflow paths must stay inside the repository: {value}",
        ) from exc
    if must_exist and not resolved.exists():
        raise WorkflowError("input_missing", f"required input does not exist: {resolved}")
    return resolved


def _repo_relative(path: Path, *, repo_root: Path = REPO_ROOT) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _resolve_default_registry(
    value: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    path = _resolve_repo_path(value, repo_root=repo_root)
    expected = (repo_root / "docs" / "experiment_registry.json").resolve()
    if path != expected:
        raise WorkflowError(
            "custom_registry_unsupported",
            "the three-command facade only operates on this workspace's canonical registry",
        )
    return path


def _artifact(path: Path, *, repo_root: Path = REPO_ROOT) -> dict[str, str]:
    return {
        "path": _repo_relative(path, repo_root=repo_root),
        "sha256": _sha256_file(path),
    }


def _ticket_file(ticket: Mapping[str, Any], *, repo_root: Path = REPO_ROOT) -> Path:
    value = ticket.get("ticket_file") or (
        f"experiments/tickets/{ticket.get('experiment_id')}.json"
    )
    return _resolve_repo_path(value, repo_root=repo_root, must_exist=True)


def _persist_novelty(
    ticket: dict[str, Any],
    novelty: Mapping[str, Any],
    *,
    spec: Mapping[str, Any],
    repo_root: Path = REPO_ROOT,
) -> None:
    """Merge the reservation guard receipt under the ticket lock.

    The legacy helper performs an unlocked best-effort read/write.  That can
    overwrite a concurrent claim with an old proposed copy.  The facade instead
    reloads under the same per-ticket lock used by claim and refuses to invent a
    missing receipt after the ticket has advanced.
    """

    if not isinstance(novelty, Mapping) or novelty.get("enforced") is not True:
        raise WorkflowError(
            "invalid_novelty_receipt",
            "start requires an enforced dynamic-guard receipt before claim",
        )
    path = _ticket_file(ticket, repo_root=repo_root)
    with file_lock(path):
        current = _load_json(path)
        if not isinstance(current, dict):
            raise WorkflowError("invalid_ticket", f"ticket is not an object: {path}")
        existing = current.get("novelty")
        if existing is None:
            if current.get("status") != "proposed":
                raise WorkflowError(
                    "novelty_receipt_missing_after_claim",
                    "a claimed/running ticket cannot acquire reservation evidence later",
                    experiment_id=current.get("experiment_id"),
                    status=current.get("status"),
                )
            current["novelty"] = dict(novelty)
        else:
            validated_existing = _require_guard_receipt_health(
                existing,
                lane=str(current.get("lane") or ""),
                spec=spec,
            )
            if _canonical_hash(validated_existing) != _canonical_hash(existing):
                if current.get("status") != "proposed":
                    raise WorkflowError(
                        "invalid_novelty_receipt",
                        "an active ticket cannot acquire missing guard-health evidence later",
                        experiment_id=current.get("experiment_id"),
                    )
                current["novelty"] = validated_existing

        claim_guard = {
            "schema_version": 1,
            "receipt": dict(novelty),
            "receipt_hash": _canonical_hash(novelty),
        }
        existing_claim_guard = current.get("alpha_workflow_claim_guard")
        if current.get("status") == "proposed":
            current["alpha_workflow_claim_guard"] = claim_guard
        elif not isinstance(existing_claim_guard, Mapping):
            raise WorkflowError(
                "claim_guard_receipt_missing_after_claim",
                "an active ticket cannot acquire its claim guard receipt after claim",
                experiment_id=current.get("experiment_id"),
            )
        else:
            stored_receipt = existing_claim_guard.get("receipt")
            if (
                not isinstance(stored_receipt, Mapping)
                or existing_claim_guard.get("receipt_hash")
                != _canonical_hash(stored_receipt)
            ):
                raise WorkflowError(
                    "invalid_claim_guard_receipt",
                    "the stored claim guard receipt is missing or corrupt",
                    experiment_id=current.get("experiment_id"),
                )
            _require_guard_receipt_health(
                stored_receipt,
                lane=str(current.get("lane") or ""),
                spec=spec,
            )
        atomic_write_json(current, path, indent=2, ensure_ascii=False)
        ticket.clear()
        ticket.update(current)


def _timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError("invalid_clock", f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkflowError("invalid_clock", f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkflowError("invalid_clock", f"{field} must include a timezone")
    return parsed


def _validate_card_clock(card: Mapping[str, Any], scope: Mapping[str, Any]) -> None:
    card_cutoff = _timestamp(card.get("data_cutoff"), field="card.data_cutoff")
    card_created = _timestamp(card.get("created_at"), field="card.created_at")
    scope_preregistered = _timestamp(
        scope.get("preregistered_at"), field="scope.preregistered_at"
    )
    scope_cutoff = _timestamp(scope.get("data_cutoff"), field="scope.data_cutoff")
    scope_freeze = _timestamp(scope.get("freeze_at"), field="scope.freeze_at")
    if card_cutoff != scope_cutoff:
        raise WorkflowError(
            "card_scope_cutoff_mismatch",
            "Investment Team card data_cutoff must exactly match the frozen scope",
        )
    if not (scope_preregistered <= card_cutoff <= card_created <= scope_freeze):
        raise WorkflowError(
            "card_scope_clock_order_invalid",
            "required order is scope.preregistered_at <= card.data_cutoff <= "
            "card.created_at <= scope.freeze_at",
        )


def _parse_json_stdout(stdout: str, *, command: Sequence[str]) -> Any:
    text = stdout.strip()
    if not text:
        raise WorkflowError(
            "delegate_missing_json",
            f"delegate returned no JSON: {' '.join(command)}",
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkflowError(
            "delegate_invalid_json",
            f"delegate stdout is not one JSON value: {' '.join(command)}",
        ) from exc


def _run_json(command: Sequence[str]) -> Any:
    process = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        shell=False,
    )
    if process.stderr:
        sys.stderr.write(process.stderr)
    if process.returncode != 0:
        raise WorkflowError(
            "delegate_failed",
            f"delegate exited {process.returncode}: {' '.join(command)}",
            delegate_stdout=process.stdout.strip(),
            delegate_stderr=process.stderr.strip(),
        )
    return _parse_json_stdout(process.stdout, command=command)


def _run_process(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        shell=False,
    )


def _receipt_hash(receipt: Mapping[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("receipt_hash", None)
    return _canonical_hash(payload)


def _qualification_receipt(
    *,
    disposition: str,
    cards: list[dict[str, Any]],
    artifacts: dict[str, Any],
    candidate_count: int,
    selected_candidate_id: str | None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "record_type": QUALIFICATION_RECORD_TYPE,
        "disposition": disposition,
        "outcome_accessed": False,
        "trade_enabled": False,
        "experiment_id_reserved": False,
        "candidate_count": candidate_count,
        "selected_candidate_id": selected_candidate_id,
        "cards": cards,
        "artifacts": artifacts,
    }
    receipt["receipt_hash"] = _receipt_hash(receipt)
    return receipt


def qualify(
    args: argparse.Namespace,
    *,
    run_json: Callable[[Sequence[str]], Any] = _run_json,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    card_paths = [
        _resolve_repo_path(path, repo_root=repo_root, must_exist=True)
        for path in args.card
    ]
    scope_path = _resolve_repo_path(
        args.scope_manifest, repo_root=repo_root, must_exist=True
    )
    surfaces_path = _resolve_repo_path(args.surfaces, repo_root=repo_root, must_exist=True)
    prior_path = _resolve_repo_path(
        args.prior_fingerprints, repo_root=repo_root, must_exist=True
    )
    proposal_path = (
        _resolve_repo_path(args.proposal, repo_root=repo_root, must_exist=True)
        if args.proposal
        else None
    )
    output_dir = _resolve_repo_path(args.output_dir, repo_root=repo_root)
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise WorkflowError(
            "output_dir_exists",
            f"qualification output directory must be new: {output_dir}",
        ) from exc

    scope = _load_json(scope_path)
    if not isinstance(scope, Mapping):
        raise WorkflowError("invalid_scope", "scope manifest must be a JSON object")

    card_records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for index, source_path in enumerate(card_paths, start=1):
        normalised = run_json(
            [
                sys.executable,
                "-B",
                str(repo_root / "scripts" / "investment_team_research_card.py"),
                "normalise",
                str(source_path),
            ]
        )
        if not isinstance(normalised, Mapping):
            raise WorkflowError("invalid_card", "normalise must return a card object")
        normalised = dict(normalised)
        _validate_card_clock(normalised, scope)
        card_output = output_dir / f"card_{index:03d}.json"
        _write_json_exclusive(card_output, normalised)
        decision = normalised.get("decision")
        if not isinstance(decision, Mapping):
            raise WorkflowError("invalid_card", "normalised card is missing decision")
        disposition = decision.get("disposition")
        record = {
            "card_id": normalised.get("card_id"),
            "disposition": disposition,
            "next_machine_action": decision.get("next_machine_action"),
            "artifact": _artifact(card_output, repo_root=repo_root),
            "source": _artifact(source_path, repo_root=repo_root),
        }
        card_records.append(record)
        if disposition != "test":
            continue
        candidate = run_json(
            [
                sys.executable,
                "-B",
                str(repo_root / "scripts" / "investment_team_research_card.py"),
                "project",
                str(card_output),
            ]
        )
        if not isinstance(candidate, Mapping):
            raise WorkflowError("invalid_candidate", "project must return a candidate object")
        candidate = dict(candidate)
        candidate_output = output_dir / f"candidate_{len(candidates) + 1:03d}.json"
        _write_json_exclusive(candidate_output, candidate)
        record["candidate"] = _artifact(candidate_output, repo_root=repo_root)
        candidates.append(candidate)

    expected_count = scope.get("expected_candidate_count")
    if isinstance(expected_count, bool) or not isinstance(expected_count, int):
        raise WorkflowError(
            "invalid_scope",
            "scope.expected_candidate_count must be an integer",
        )
    # Investment Team can stop every idea before candidate projection.  That is
    # a safe zero-ID outcome even though the upstream canonical scope reserved a
    # positive generation budget.  Once at least one candidate is projected,
    # however, the complete-pool count must match exactly.
    if candidates and expected_count != len(candidates):
        raise WorkflowError(
            "incomplete_selection_pool",
            f"scope froze {expected_count} candidates but cards projected {len(candidates)}",
        )

    artifacts: dict[str, Any] = {
        "scope_manifest": _artifact(scope_path, repo_root=repo_root),
        "surface_registry": _artifact(surfaces_path, repo_root=repo_root),
        "prior_fingerprints": _artifact(prior_path, repo_root=repo_root),
    }
    if proposal_path is not None:
        artifacts["proposal"] = _artifact(proposal_path, repo_root=repo_root)

    if not candidates:
        receipt = _qualification_receipt(
            disposition="no_candidate",
            cards=card_records,
            artifacts=artifacts,
            candidate_count=0,
            selected_candidate_id=None,
        )
        receipt_path = output_dir / "qualification.json"
        _write_json_exclusive(receipt_path, receipt)
        return {**receipt, "qualification_path": _repo_relative(receipt_path, repo_root=repo_root)}

    candidates_path = output_dir / "candidates.json"
    _write_json_exclusive(candidates_path, {"candidates": candidates})
    panel = run_json(
        [
            sys.executable,
            "-B",
            str(repo_root / "scripts" / "alpha_search.py"),
            "build-panel",
            str(candidates_path),
            "--surfaces",
            str(surfaces_path),
            "--scope-manifest",
            str(scope_path),
            "--prior-fingerprints",
            str(prior_path),
            "--selection-pool-complete",
        ]
    )
    if not isinstance(panel, Mapping):
        raise WorkflowError("invalid_panel", "build-panel must return an object")
    panel = dict(panel)
    panel_path = output_dir / "panel.json"
    _write_json_exclusive(panel_path, panel)
    artifacts["candidates"] = _artifact(candidates_path, repo_root=repo_root)
    artifacts["panel"] = _artifact(panel_path, repo_root=repo_root)
    selected_candidate_id = panel.get("selected_candidate_id")
    if not selected_candidate_id:
        receipt = _qualification_receipt(
            disposition="not_promoted",
            cards=card_records,
            artifacts=artifacts,
            candidate_count=len(candidates),
            selected_candidate_id=None,
        )
        receipt_path = output_dir / "qualification.json"
        _write_json_exclusive(receipt_path, receipt)
        return {**receipt, "qualification_path": _repo_relative(receipt_path, repo_root=repo_root)}

    if proposal_path is None:
        raise WorkflowError(
            "proposal_required",
            "a selected candidate requires --proposal before promotion",
        )
    promotion_path = output_dir / "promotion.json"
    promotion = run_json(
        [
            sys.executable,
            "-B",
            str(repo_root / "scripts" / "alpha_search.py"),
            "build-promotion",
            str(panel_path),
            "--surfaces",
            str(surfaces_path),
            "--scope-manifest",
            str(scope_path),
            "--prior-fingerprints",
            str(prior_path),
            "--proposal",
            str(proposal_path),
            "--output",
            str(promotion_path),
        ]
    )
    if not isinstance(promotion, Mapping):
        raise WorkflowError("invalid_promotion", "build-promotion must return an object")
    _ensure_command_output(promotion_path, promotion)
    artifacts["promotion"] = _artifact(promotion_path, repo_root=repo_root)
    receipt = _qualification_receipt(
        disposition="promoted",
        cards=card_records,
        artifacts=artifacts,
        candidate_count=len(candidates),
        selected_candidate_id=str(selected_candidate_id),
    )
    receipt_path = output_dir / "qualification.json"
    _write_json_exclusive(receipt_path, receipt)
    return {**receipt, "qualification_path": _repo_relative(receipt_path, repo_root=repo_root)}


def _verify_artifact_entry(
    entry: Any,
    *,
    name: str,
    repo_root: Path = REPO_ROOT,
) -> Path:
    if not isinstance(entry, Mapping):
        raise WorkflowError("invalid_qualification", f"artifact {name} must be an object")
    path = _resolve_repo_path(entry.get("path", ""), repo_root=repo_root, must_exist=True)
    expected = entry.get("sha256")
    actual = _sha256_file(path)
    if not isinstance(expected, str) or expected != actual:
        raise WorkflowError(
            "qualification_artifact_tampered",
            f"artifact hash mismatch for {name}: {path}",
        )
    return path


def _load_qualification(
    path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], dict[str, Path]]:
    value = _load_json(path)
    if not isinstance(value, Mapping):
        raise WorkflowError("invalid_qualification", "qualification must be an object")
    receipt = dict(value)
    if receipt.get("schema_version") != QUALIFICATION_SCHEMA_VERSION:
        raise WorkflowError("invalid_qualification", "unsupported qualification schema")
    if receipt.get("record_type") != QUALIFICATION_RECORD_TYPE:
        raise WorkflowError("invalid_qualification", "wrong qualification record_type")
    if receipt.get("receipt_hash") != _receipt_hash(receipt):
        raise WorkflowError("qualification_tampered", "qualification receipt hash mismatch")
    if (
        receipt.get("outcome_accessed") is not False
        or receipt.get("trade_enabled") is not False
        or receipt.get("experiment_id_reserved") is not False
    ):
        raise WorkflowError(
            "qualification_boundary_violation",
            "qualification must be outcome-blind, trade-disabled, and zero-ID",
        )
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise WorkflowError("invalid_qualification", "qualification artifacts are missing")
    verified = {
        name: _verify_artifact_entry(entry, name=name, repo_root=repo_root)
        for name, entry in artifacts.items()
        if isinstance(entry, Mapping) and "path" in entry
    }
    cards = receipt.get("cards")
    if not isinstance(cards, list):
        raise WorkflowError("invalid_qualification", "qualification cards are missing")
    for index, card in enumerate(cards):
        if not isinstance(card, Mapping):
            raise WorkflowError("invalid_qualification", f"cards[{index}] must be an object")
        for field in ("source", "artifact", "candidate"):
            if field in card:
                _verify_artifact_entry(
                    card[field],
                    name=f"cards[{index}].{field}",
                    repo_root=repo_root,
                )
    return receipt, verified


_EXECUTION_FIELDS = {
    "schema_version",
    "record_type",
    "baseline_result_file",
    "allowed_write_scope",
    "must_not_touch",
    "locked_variables",
    "evaluation_windows",
    "acceptance_rule",
    "file_slug",
    "trial_variant_id",
    "prior_trial_count",
    "nearby_prior_experiments",
    "multiple_testing_risk_bucket",
    "new_evidence_type",
    "new_evidence_axis",
}


def _string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise WorkflowError("invalid_execution_spec", f"{field} must be a list of strings")
    return [item.strip() for item in value]


def _load_execution_spec(path: Path, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    value = _load_json(path)
    if not isinstance(value, Mapping):
        raise WorkflowError("invalid_execution_spec", "execution spec must be an object")
    spec = dict(value)
    unknown = sorted(set(spec) - _EXECUTION_FIELDS)
    if unknown:
        raise WorkflowError(
            "invalid_execution_spec",
            f"unknown execution spec fields: {', '.join(unknown)}",
        )
    if spec.get("schema_version") != EXECUTION_SPEC_SCHEMA_VERSION:
        raise WorkflowError("invalid_execution_spec", "unsupported execution spec schema")
    if spec.get("record_type") != EXECUTION_SPEC_RECORD_TYPE:
        raise WorkflowError("invalid_execution_spec", "wrong execution spec record_type")
    for field in ("allowed_write_scope", "must_not_touch", "locked_variables"):
        spec[field] = _string_list(spec.get(field, []), field=field)
    if not spec["allowed_write_scope"]:
        raise WorkflowError(
            "invalid_execution_spec",
            "allowed_write_scope must explicitly name the experiment's files",
        )
    spec["nearby_prior_experiments"] = _string_list(
        spec.get("nearby_prior_experiments", []), field="nearby_prior_experiments"
    )
    windows = spec.get("evaluation_windows", [])
    if not isinstance(windows, list) or any(
        not isinstance(row, Mapping)
        or not isinstance(row.get("start"), str)
        or not isinstance(row.get("end"), str)
        or not row.get("start", "").strip()
        or not row.get("end", "").strip()
        for row in windows
    ):
        raise WorkflowError(
            "invalid_execution_spec",
            "evaluation_windows must be [{start, end}, ...]",
        )
    spec["evaluation_windows"] = [
        {"start": row["start"].strip(), "end": row["end"].strip()} for row in windows
    ]
    prior_count = spec.get("prior_trial_count", 0)
    if isinstance(prior_count, bool) or not isinstance(prior_count, int) or prior_count < 0:
        raise WorkflowError(
            "invalid_execution_spec",
            "prior_trial_count must be a non-negative integer",
        )
    spec["prior_trial_count"] = prior_count
    risk = spec.get("multiple_testing_risk_bucket", "minimal")
    if risk not in {"minimal", "low", "moderate", "high"}:
        raise WorkflowError("invalid_execution_spec", "invalid multiple-testing risk bucket")
    spec["multiple_testing_risk_bucket"] = risk
    for field in ("file_slug", "trial_variant_id", "new_evidence_type", "new_evidence_axis"):
        value = spec.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise WorkflowError(
                "invalid_execution_spec",
                f"{field} must be a non-empty string when provided",
            )
        if isinstance(value, str):
            spec[field] = value.strip()
    acceptance_rule = spec.get("acceptance_rule")
    if not isinstance(acceptance_rule, str) or not acceptance_rule.strip():
        raise WorkflowError("invalid_execution_spec", "acceptance_rule is required")
    baseline = spec.get("baseline_result_file")
    if not isinstance(baseline, str) or not baseline.strip():
        raise WorkflowError("invalid_execution_spec", "baseline_result_file is required")
    _resolve_repo_path(baseline, repo_root=repo_root, must_exist=True)
    return spec


def _novelty_namespace(
    proposal: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    owner: str,
    registry: str,
) -> argparse.Namespace:
    prediction = proposal.get("prediction") or {}
    return SimpleNamespace(
        experiment_id=None,
        lane=proposal["lane"],
        hypothesis=proposal["hypothesis"],
        change_type=proposal["change_type"],
        promotion_request=None,
        single_causal_variable=proposal["single_causal_variable"],
        causal_components=", ".join(proposal["causal_components"]),
        mechanism_family=proposal["mechanism_family"],
        trial_family=proposal["trial_family"],
        trial_variant_id=spec.get("trial_variant_id"),
        changed_variable=proposal["changed_variable"],
        prior_trial_count=spec["prior_trial_count"],
        nearby_prior_experiments=",".join(spec["nearby_prior_experiments"]),
        multiple_testing_risk_bucket=spec["multiple_testing_risk_bucket"],
        new_evidence_type=spec.get("new_evidence_type", "not_declared"),
        baseline_result_file=spec["baseline_result_file"],
        allowed_write_scope=",".join(spec["allowed_write_scope"]),
        file_slug=spec.get("file_slug"),
        exclusive_scope_ok=False,
        must_not_touch=",".join(spec["must_not_touch"]),
        locked_variables=",".join(spec["locked_variables"]),
        window=[],
        acceptance_rule=spec["acceptance_rule"],
        owner=owner,
        success_probability=prediction.get("success_probability"),
        expected_ev_delta=prediction.get("expected_ev_delta"),
        expected_pnl_delta=prediction.get("expected_pnl_delta"),
        main_failure_modes=",".join(prediction.get("main_failure_modes") or []),
        confidence_reason=prediction.get("confidence_reason"),
        new_evidence_axis=spec.get("new_evidence_axis", ""),
        novelty_override=False,
        saturated_source_override=False,
        observed_only_override=False,
        routine_materialization_override=False,
        recipe_lane_override=False,
        in_flight_duplicate_override=False,
        enforce_novelty=True,
        no_enforce_novelty=False,
        registry=registry,
        lock_timeout_seconds=30.0,
    )


def _ticket_for_intent(registry: str | Path, intent_key: str) -> dict[str, Any] | None:
    view = rebuild_registry_from_tickets(registry)
    for ticket in view.get("experiments", []):
        intent = ticket.get("reservation_intent")
        if isinstance(intent, Mapping) and intent.get("key") == intent_key:
            return ticket
    return None


def _ticket_for_promotion(
    registry: str | Path, promotion_hash: str
) -> dict[str, Any] | None:
    view = rebuild_registry_from_tickets(registry)
    for ticket in view.get("experiments", []):
        anchor = ticket.get("alpha_promotion")
        if isinstance(anchor, Mapping) and anchor.get("promotion_hash") == promotion_hash:
            return ticket
    return None


def _require_guard_receipt_health(
    receipt: Any,
    *,
    lane: str,
    spec: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(receipt, dict) or receipt.get("enforced") is not True:
        raise WorkflowError(
            "start_guard_unavailable",
            "dynamic reservation guards did not return an enforced receipt",
        )
    required_objects = (
        "fingerprint",
        "source_saturation",
        "reopen_condition_guard",
        "observed_only_streak_guard",
        "routine_materialization_guard",
        "recipe_lane_guard",
        "in_flight_duplicate_guard",
    )
    missing = [name for name in required_objects if not isinstance(receipt.get(name), Mapping)]
    if missing:
        raise WorkflowError(
            "start_guard_unavailable",
            "dynamic guard receipt is incomplete: " + ", ".join(missing),
        )
    fingerprint = receipt["fingerprint"]
    saturation = receipt["source_saturation"]
    if any(
        not isinstance(fingerprint.get(field), str) or not fingerprint.get(field)
        for field in ("data_source", "gate_shape")
    ) or any(
        field not in saturation
        for field in ("applicable", "saturated", "source", "gate_shape", "trials")
    ):
        raise WorkflowError(
            "start_guard_unavailable",
            "fingerprint or saturation guard returned an unverifiable fallback receipt",
        )
    if not isinstance(saturation.get("applicable"), bool) or not isinstance(
        saturation.get("saturated"), bool
    ):
        raise WorkflowError(
            "start_guard_unavailable",
            "saturation guard applicability is not machine-verifiable",
        )
    for name in (
        "reopen_condition_guard",
        "observed_only_streak_guard",
        "routine_materialization_guard",
        "recipe_lane_guard",
        "in_flight_duplicate_guard",
    ):
        guard = receipt[name]
        if not isinstance(guard.get("applicable"), bool) or not isinstance(
            guard.get("blocked"), bool
        ):
            raise WorkflowError(
                "start_guard_unavailable",
                f"{name} applicability is not machine-verifiable",
            )
    classifier_coverage_required = False
    if lane in {"alpha_search", "alpha_discovery", "universe_scout"}:
        if receipt.get("data_source_unclassified") is True:
            scopes = {
                str(item).replace("\\", "/")
                for item in ((spec or {}).get("allowed_write_scope") or [])
            }
            if (
                (spec or {}).get("new_evidence_type") != "new_data_source"
                or "scripts/experiment_fingerprint.py" not in scopes
            ):
                raise WorkflowError(
                    "classifier_coverage_required",
                    "an unclassified new source must declare new_data_source and include "
                    "scripts/experiment_fingerprint.py in this ticket's write scope",
                )
            classifier_coverage_required = True
        if receipt["in_flight_duplicate_guard"].get("applicable") is not True:
            raise WorkflowError(
                "start_guard_unavailable",
                "in-flight duplicate guard could not inspect the ticket directory",
            )
        if receipt["reopen_condition_guard"].get("applicable") is not True:
            raise WorkflowError(
                "start_guard_unavailable",
                "parked-surface reopen guard was not applicable to an alpha lane",
            )
    receipt = dict(receipt)
    receipt["alpha_workflow_guard_health"] = {
        "validated": True,
        "classifier_coverage_required": classifier_coverage_required,
    }
    return receipt


def _start_under_promotion_lock(
    args: argparse.Namespace,
    *,
    repo_root: Path = REPO_ROOT,
    novelty_check: Callable[[Any], Any] = _novelty_check,
    reserve: Callable[..., dict[str, Any]] = reserve_experiment,
    claim: Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]] = claim_experiment_decontended,
    revalidate_promotion: Callable[..., Any] = revalidate_ticket_promotion,
) -> dict[str, Any]:
    qualification_path = _resolve_repo_path(
        args.qualification, repo_root=repo_root, must_exist=True
    )
    receipt, artifacts = _load_qualification(qualification_path, repo_root=repo_root)
    if receipt.get("disposition") != "promoted":
        raise WorkflowError(
            "qualification_not_promoted",
            f"qualification disposition is {receipt.get('disposition')!r}; no ID reserved",
        )
    promotion_path = artifacts.get("promotion")
    if promotion_path is None:
        raise WorkflowError("invalid_qualification", "promoted receipt has no promotion artifact")
    promotion = _load_json(promotion_path)
    if not isinstance(promotion, Mapping) or not isinstance(promotion.get("proposal"), Mapping):
        raise WorkflowError("invalid_promotion", "promotion is missing its proposal")
    promotion_hash = promotion.get("promotion_hash")
    if not isinstance(promotion_hash, str) or len(promotion_hash) != 64:
        raise WorkflowError("invalid_promotion", "promotion_hash must be a SHA-256 string")
    proposal = normalize_ticket_proposal(promotion["proposal"])
    execution_path = _resolve_repo_path(
        args.execution_spec, repo_root=repo_root, must_exist=True
    )
    spec = _load_execution_spec(execution_path, repo_root=repo_root)
    owner = str(args.owner or "").strip()
    if not owner:
        raise WorkflowError("owner_required", "start requires a non-empty owner")
    registry_path = str(
        _resolve_default_registry(
            getattr(args, "registry", repo_root / "docs" / "experiment_registry.json"),
            repo_root=repo_root,
        )
    )

    ticket_kwargs = {
        "lane": proposal["lane"],
        "hypothesis": proposal["hypothesis"],
        "change_type": proposal["change_type"],
        "single_causal_variable": proposal["single_causal_variable"],
        "causal_components": list(proposal["causal_components"]),
        "mechanism_family": proposal["mechanism_family"],
        "trial_family": proposal["trial_family"],
        "trial_variant_id": spec.get("trial_variant_id"),
        "changed_variable": proposal["changed_variable"],
        "prior_trial_count": spec["prior_trial_count"],
        "nearby_prior_experiments": spec["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": spec["multiple_testing_risk_bucket"],
        "new_evidence_type": spec.get("new_evidence_type", "not_declared"),
        "baseline_result_file": spec["baseline_result_file"],
        "allowed_write_scope": spec["allowed_write_scope"],
        "must_not_touch": spec["must_not_touch"],
        "locked_variables": spec["locked_variables"],
        "evaluation_windows": spec["evaluation_windows"],
        "acceptance_rule": spec["acceptance_rule"],
        "owner": owner,
        "file_slug": spec.get("file_slug"),
        "exclusive_scope_ok": False,
        "prediction": dict(proposal["prediction"]),
        "promotion_request": _repo_relative(promotion_path, repo_root=repo_root),
    }
    intent = reservation_intent_for(ticket_kwargs)
    intent_ticket = _ticket_for_intent(registry_path, intent["key"])
    promotion_ticket = _ticket_for_promotion(registry_path, promotion_hash)
    if (
        intent_ticket is not None
        and promotion_ticket is not None
        and intent_ticket.get("experiment_id") != promotion_ticket.get("experiment_id")
    ):
        raise WorkflowError(
            "qualification_binding_conflict",
            "reservation intent and promotion are bound to different tickets",
            intent_experiment_id=intent_ticket.get("experiment_id"),
            promotion_experiment_id=promotion_ticket.get("experiment_id"),
        )
    existing = promotion_ticket or intent_ticket
    if existing is not None:
        existing_intent = existing.get("reservation_intent") or {}
        if existing_intent.get("key") != intent["key"]:
            raise WorkflowError(
                "qualification_already_bound",
                "this promotion is already bound to a different execution spec",
                experiment_id=existing.get("experiment_id"),
                status=existing.get("status"),
            )
        if _is_terminal(existing.get("status")):
            raise WorkflowError(
                "qualification_already_consumed",
                "a closed experiment permanently consumes its qualification",
                experiment_id=existing.get("experiment_id"),
                status=existing.get("status"),
            )
        if existing.get("owner") not in (None, "", owner):
            raise WorkflowError(
                "qualification_owner_conflict",
                "the qualification is already bound to another owner",
                experiment_id=existing.get("experiment_id"),
                owner=existing.get("owner"),
            )
    guard_args = _novelty_namespace(proposal, spec, owner=owner, registry=registry_path)
    # An exact retry is not an in-flight duplicate.  Supplying the already
    # reserved ID lets the existing guard ignore only that ticket while still
    # checking every other open near-neighbour and all dynamic guard surfaces.
    if existing is not None:
        guard_args.experiment_id = existing.get("experiment_id")
    try:
        novelty = novelty_check(guard_args)
    except SystemExit as exc:
        raise WorkflowError("start_guard_blocked", str(exc)) from exc
    novelty = _require_guard_receipt_health(
        novelty,
        lane=proposal["lane"],
        spec=spec,
    )

    ticket = reserve(registry_path, **ticket_kwargs)
    _persist_novelty(ticket, novelty, spec=spec, repo_root=repo_root)
    experiment_id = ticket.get("experiment_id")
    if ticket.get("status") in ACTIVE_STATUSES:
        revalidate_promotion(ticket, repo_root=repo_root)
        return {
            "ok": True,
            "command": "start",
            "experiment_id": experiment_id,
            "experiment_uid": ticket.get("experiment_uid"),
            "status": ticket.get("status"),
            "reused_reservation": True,
            "qualification_receipt_hash": receipt.get("receipt_hash"),
            "promotion_hash": promotion_hash,
            "outcome_access_allowed": True,
            "already_started": True,
        }
    try:
        claimed_ticket, conflicts = claim(
            registry_path,
            experiment_id,
            owner,
            force=False,
        )
    except Exception as exc:
        raise WorkflowError(
            "claim_failed_after_reservation",
            str(exc),
            experiment_id=experiment_id,
            reservation_status=ticket.get("status"),
        ) from exc
    if conflicts:
        raise WorkflowError(
            "claim_conflict_after_reservation",
            "ticket was reserved but could not be claimed; retry reuses this ID",
            experiment_id=experiment_id,
            reservation_status=ticket.get("status"),
            conflicts=conflicts,
        )
    return {
        "ok": True,
        "command": "start",
        "experiment_id": experiment_id,
        "experiment_uid": claimed_ticket.get("experiment_uid"),
        "status": claimed_ticket.get("status"),
        "reused_reservation": existing is not None,
        "qualification_receipt_hash": receipt.get("receipt_hash"),
        "promotion_hash": promotion.get("promotion_hash"),
        "outcome_access_allowed": True,
    }


def start(
    args: argparse.Namespace,
    *,
    repo_root: Path = REPO_ROOT,
    novelty_check: Callable[[Any], Any] = _novelty_check,
    reserve: Callable[..., dict[str, Any]] = reserve_experiment,
    claim: Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]] = claim_experiment_decontended,
    revalidate_promotion: Callable[..., Any] = revalidate_ticket_promotion,
) -> dict[str, Any]:
    """Serialize one-time promotion consumption through claim completion."""

    qualification_path = _resolve_repo_path(
        args.qualification,
        repo_root=repo_root,
        must_exist=True,
    )
    receipt, artifacts = _load_qualification(qualification_path, repo_root=repo_root)
    if receipt.get("disposition") != "promoted" or "promotion" not in artifacts:
        raise WorkflowError(
            "qualification_not_promoted",
            f"qualification disposition is {receipt.get('disposition')!r}; no ID reserved",
        )
    promotion = _load_json(artifacts["promotion"])
    promotion_hash = promotion.get("promotion_hash") if isinstance(promotion, Mapping) else None
    if not isinstance(promotion_hash, str) or len(promotion_hash) != 64:
        raise WorkflowError("invalid_promotion", "promotion_hash must be a SHA-256 string")
    # Admission is intentionally serialized for the short guard/reserve/claim
    # transaction.  A promotion-only lock prevents duplicate consumption of
    # one qualification, but two different near-neighbour promotions could
    # otherwise both pass the in-flight scan before either ticket exists.
    lock_target = repo_root / "experiments" / "tickets" / "alpha-start-admission"
    with file_lock(lock_target):
        return _start_under_promotion_lock(
            args,
            repo_root=repo_root,
            novelty_check=novelty_check,
            reserve=reserve,
            claim=claim,
            revalidate_promotion=revalidate_promotion,
        )


def _is_terminal(status: Any) -> bool:
    value = str(status or "")
    return value in FINAL_STATUSES or value.startswith(
        ("accepted", "rejected", "observed_only")
    )


def _ticket_from_registry(registry: str | Path, experiment_id: str) -> dict[str, Any]:
    view = rebuild_registry_from_tickets(registry)
    for ticket in view.get("experiments", []):
        if ticket.get("experiment_id") == experiment_id:
            return ticket
    raise WorkflowError("unknown_experiment", f"unknown experiment_id: {experiment_id}")


def _load_finish_reflection(path: Path) -> dict[str, str]:
    value = _load_json(path)
    if not isinstance(value, Mapping):
        raise WorkflowError("invalid_finish_reflection", "reflection must be an object")
    unknown = sorted(set(value) - (FINISH_REFLECTION_FIELDS | {"notes"}))
    missing = sorted(FINISH_REFLECTION_FIELDS - set(value))
    if unknown or missing:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise WorkflowError("invalid_finish_reflection", "; ".join(details))
    reflection: dict[str, str] = {}
    for field in sorted(FINISH_REFLECTION_FIELDS | {"notes"}):
        if field not in value:
            continue
        item = value[field]
        if not isinstance(item, str) or not item.strip():
            raise WorkflowError(
                "invalid_finish_reflection",
                f"{field} must be a non-empty string",
            )
        reflection[field] = item.strip()
    return reflection


def _finish_request(
    ticket: Mapping[str, Any],
    *,
    before: Path,
    after: Path,
    reflection: Mapping[str, str],
    force_reject: bool,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": FINISH_INTENT_SCHEMA_VERSION,
        "experiment_id": ticket.get("experiment_id"),
        "experiment_uid": ticket.get("experiment_uid"),
        "before": _artifact(before, repo_root=repo_root),
        "after": _artifact(after, repo_root=repo_root),
        "reflection": dict(reflection),
        "force_reject": force_reject,
    }


def _resolve_finish_decision(
    ticket: Mapping[str, Any],
    judgement: Mapping[str, Any],
    *,
    force_reject: bool,
) -> str:
    natural = judgement.get("decision")
    if natural not in {"accepted", "rejected"}:
        raise WorkflowError(
            "unsupported_gate_decision",
            f"judge returned unsupported decision {natural!r}",
        )
    if force_reject:
        return "rejected"
    anchor = ticket.get("alpha_promotion")
    result_ceiling = anchor.get("result_ceiling") if isinstance(anchor, Mapping) else None
    if natural == "accepted" and result_ceiling == "observed_only":
        return "observed_only"
    return str(natural)


def _build_finish_intent(
    ticket: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    before: Path,
    after: Path,
    reflection: Mapping[str, str],
    force_reject: bool,
    judge: Callable[[Path, Path], dict[str, Any]],
) -> dict[str, Any]:
    try:
        judgement = judge(before, after)
        decision = _resolve_finish_decision(
            ticket,
            judgement,
            force_reject=force_reject,
        )
        log_row = build_log_draft(
            ticket,
            judgement,
            before,
            after,
            status_override=decision,
            change_summary=reflection["change_summary"],
            notes=reflection.get("notes"),
            realized_failure_mode=reflection["realized_failure_mode"],
            surprise_note=reflection["why_result_happened"],
            allow_missing_prediction=False,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise WorkflowError("finish_preflight_failed", str(exc)) from exc
    log_row["post_run_reflection"] = {
        field: reflection[field]
        for field in (
            "why_result_happened",
            "realized_failure_mode",
            "forbidden_near_neighbor_retry",
            "new_evidence_required",
        )
    }
    log_row["artifact_hashes"] = {
        "before": request["before"],
        "after": request["after"],
    }
    log_row = strip_oversized_fields(log_row)
    weak = lean_reflection_quality_reasons(ticket, log_row)
    if weak:
        raise WorkflowError(
            "weak_finish_reflection",
            "reflection does not pass lean-strict quality: " + ", ".join(weak),
        )
    intent: dict[str, Any] = {
        "schema_version": FINISH_INTENT_SCHEMA_VERSION,
        "record_type": FINISH_INTENT_RECORD_TYPE,
        "request": dict(request),
        "request_hash": _canonical_hash(request),
        "resolved_decision": decision,
        "judgement": judgement,
        "log_row": log_row,
        "log_row_hash": _canonical_hash(log_row),
    }
    intent["intent_hash"] = _canonical_hash(intent)
    return intent


def _validate_finish_intent(
    value: Any,
    *,
    request: Mapping[str, Any],
    ticket: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowError(
            "finish_receipt_missing",
            "a terminal ticket without an alpha-workflow finish receipt cannot be replayed",
        )
    intent = dict(value)
    if (
        intent.get("schema_version") != FINISH_INTENT_SCHEMA_VERSION
        or intent.get("record_type") != FINISH_INTENT_RECORD_TYPE
    ):
        raise WorkflowError("invalid_finish_receipt", "unsupported finish receipt")
    observed_intent_hash = intent.pop("intent_hash", None)
    if observed_intent_hash != _canonical_hash(intent):
        raise WorkflowError("invalid_finish_receipt", "finish receipt hash mismatch")
    intent["intent_hash"] = observed_intent_hash
    bound_request = intent.get("request")
    request_hash = intent.get("request_hash")
    if not isinstance(bound_request, Mapping) or request_hash != _canonical_hash(
        bound_request
    ):
        raise WorkflowError(
            "invalid_finish_receipt",
            "finish receipt's bound request does not match request_hash",
        )
    if request_hash != _canonical_hash(request):
        raise WorkflowError(
            "finish_retry_conflict",
            "finish was already bound to different artifacts, reflection, or disposition",
        )
    judgement = intent.get("judgement")
    if not isinstance(judgement, Mapping):
        raise WorkflowError("invalid_finish_receipt", "finish judgement is missing")
    expected_decision = _resolve_finish_decision(
        ticket,
        judgement,
        force_reject=bool(bound_request.get("force_reject")),
    )
    if intent.get("resolved_decision") != expected_decision:
        raise WorkflowError(
            "invalid_finish_receipt",
            "finish decision does not follow Gate judgement and the evidence ceiling",
        )
    log_row = intent.get("log_row")
    if not isinstance(log_row, Mapping) or intent.get("log_row_hash") != _canonical_hash(
        log_row
    ):
        raise WorkflowError("invalid_finish_receipt", "bound log row hash mismatch")
    reflection = bound_request.get("reflection") or {}
    expected_reflection = {
        field: reflection.get(field)
        for field in (
            "why_result_happened",
            "realized_failure_mode",
            "forbidden_near_neighbor_retry",
            "new_evidence_required",
        )
    }
    if (
        log_row.get("experiment_id") != ticket.get("experiment_id")
        or log_row.get("status") != expected_decision
        or log_row.get("decision") != expected_decision
        or log_row.get("artifact_hashes")
        != {"before": bound_request.get("before"), "after": bound_request.get("after")}
        or log_row.get("post_run_reflection") != expected_reflection
    ):
        raise WorkflowError(
            "invalid_finish_receipt",
            "bound log row is inconsistent with the finish request or decision",
        )
    return intent


def _persist_finish_intent(
    ticket: Mapping[str, Any],
    intent: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    path = _ticket_file(ticket, repo_root=repo_root)
    with file_lock(path):
        current = _load_json(path)
        if not isinstance(current, dict):
            raise WorkflowError("invalid_ticket", f"ticket is not an object: {path}")
        existing = current.get("alpha_workflow_finish_intent")
        if existing is not None:
            _validate_finish_intent(
                existing,
                request=intent["request"],
                ticket=current,
            )
            return current
        if _is_terminal(current.get("status")):
            raise WorkflowError(
                "finish_receipt_missing",
                "terminal ticket predates the recoverable finish contract",
                experiment_id=current.get("experiment_id"),
            )
        if current.get("status") not in ACTIVE_STATUSES:
            raise WorkflowError(
                "finish_requires_claim",
                f"finish requires claimed/running, got {current.get('status')!r}",
            )
        current["alpha_workflow_finish_intent"] = dict(intent)
        atomic_write_json(current, path, indent=2, ensure_ascii=False)
        return current


def _result_path_matches(
    value: Any,
    expected: str,
    *,
    repo_root: Path,
) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    observed = Path(value)
    expected_path = (repo_root / expected).resolve()
    if observed.is_absolute():
        return observed.resolve() == expected_path
    return any(
        (root / observed).resolve() == expected_path
        for root in {repo_root.resolve(), REPO_ROOT.resolve()}
    )


def _bind_terminal_finish_result(
    ticket: Mapping[str, Any],
    intent: Mapping[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    path = _ticket_file(ticket, repo_root=repo_root)
    with file_lock(path):
        current = _load_json(path)
        if not isinstance(current, dict):
            raise WorkflowError("invalid_ticket", f"ticket is not an object: {path}")
        result = current.get("result")
        decision = intent.get("resolved_decision")
        request = intent.get("request") or {}
        before = request.get("before") or {}
        after = request.get("after") or {}
        if (
            current.get("status") != decision
            or not isinstance(result, dict)
            or result.get("decision") != decision
        ):
            raise WorkflowError(
                "finish_terminal_conflict",
                "terminal ticket does not match its bound finish decision",
                status=current.get("status"),
                expected_status=decision,
            )
        if not _result_path_matches(
            result.get("before_result_file"),
            before.get("path"),
            repo_root=repo_root,
        ) or not _result_path_matches(
            result.get("after_result_file"),
            after.get("path"),
            repo_root=repo_root,
        ):
            raise WorkflowError(
                "finish_terminal_conflict",
                "terminal ticket was closed against different before/after artifacts",
            )
        expected_binding = {
            "intent_hash": intent.get("intent_hash"),
            "before": before,
            "after": after,
        }
        existing_binding = result.get("alpha_workflow_finish_binding")
        if existing_binding is not None and _canonical_hash(
            existing_binding
        ) != _canonical_hash(expected_binding):
            raise WorkflowError(
                "finish_terminal_conflict",
                "terminal result has a different finish-intent or artifact hash binding",
            )
        if existing_binding is None:
            result["alpha_workflow_finish_binding"] = expected_binding
            current["result"] = result
            atomic_write_json(current, path, indent=2, ensure_ascii=False)
        return current


def _verify_terminal_finish(ticket: Mapping[str, Any], intent: Mapping[str, Any]) -> None:
    decision = intent.get("resolved_decision")
    result = ticket.get("result")
    if ticket.get("status") != decision or not isinstance(result, Mapping):
        raise WorkflowError(
            "finish_terminal_conflict",
            "terminal ticket does not match its bound finish decision",
            status=ticket.get("status"),
            expected_status=decision,
        )
    if result.get("decision") != decision:
        raise WorkflowError(
            "finish_terminal_conflict",
            "terminal result decision does not match its finish receipt",
        )
    binding = result.get("alpha_workflow_finish_binding")
    if not isinstance(binding, Mapping) or binding.get("intent_hash") != intent.get(
        "intent_hash"
    ):
        raise WorkflowError(
            "finish_terminal_conflict",
            "terminal result is missing its finish-intent binding",
        )


def _write_or_verify_finish_log(
    intent: Mapping[str, Any],
    *,
    experiment_id: str,
    log_path: Path,
    save_log: Callable[..., Path],
) -> bool:
    expected_row = intent["log_row"]
    expected_hash = intent["log_row_hash"]
    if log_path.exists():
        existing = _load_json(log_path)
        if _canonical_hash(existing) != expected_hash:
            raise WorkflowError(
                "finish_log_conflict",
                "durable log differs from the hash-bound finish receipt",
                log_path=str(log_path),
            )
        return False
    try:
        save_log(
            expected_row,
            allow_duplicate=False,
            expected_experiment_id=experiment_id,
            logs_dir=log_path.parent,
            timeout_seconds=30.0,
        )
    except (OSError, ValueError, TimeoutError) as exc:
        if not log_path.exists():
            raise WorkflowError(
                "finish_log_write_failed",
                f"ticket is terminal and retry can recover the log: {exc}",
                experiment_id=experiment_id,
            ) from exc
    if not log_path.exists() or _canonical_hash(_load_json(log_path)) != expected_hash:
        raise WorkflowError(
            "finish_log_write_failed",
            "log writer returned without the exact hash-bound row",
            experiment_id=experiment_id,
        )
    return True


def _run_finish_maintenance(
    *,
    registry_path: str,
    run_process: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    repo_root: Path,
) -> tuple[bool, dict[str, Any]]:
    commands = [
        [sys.executable, "-B", str(repo_root / "scripts" / "build_frozen_families.py")],
        [sys.executable, "-B", str(repo_root / "scripts" / "build_alpha_memory.py")],
        [
            sys.executable,
            "-B",
            str(repo_root / "scripts" / "experiment.py"),
            "audit",
            "--registry",
            registry_path,
            "--lean-strict",
        ],
    ]
    labels = ("frozen_families", "alpha_memory", "audit")
    details: dict[str, Any] = {}
    for label, command in zip(labels, commands):
        process = run_process(command)
        if process.stderr:
            sys.stderr.write(process.stderr)
        details[label] = {
            "passed": process.returncode == 0,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
        }
        if process.returncode != 0:
            return False, details
    return True, details


def finish(
    args: argparse.Namespace,
    *,
    run_process: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = _run_process,
    judge: Callable[[Path, Path], dict[str, Any]] = judge_results,
    update_result: Callable[..., dict[str, Any]] = update_result_decontended,
    save_log: Callable[..., Path] = save_experiment_log_entry,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], int]:
    registry_path = str(
        _resolve_default_registry(
            getattr(args, "registry", repo_root / "docs" / "experiment_registry.json"),
            repo_root=repo_root,
        )
    )
    before_path = _resolve_repo_path(args.before, repo_root=repo_root, must_exist=True)
    after_path = _resolve_repo_path(args.after, repo_root=repo_root, must_exist=True)
    reflection_path = _resolve_repo_path(
        args.reflection_file,
        repo_root=repo_root,
        must_exist=True,
    )
    reflection = _load_finish_reflection(reflection_path)
    experiment_id = str(args.experiment_id)
    log_path = repo_root / "experiments" / "logs" / f"{experiment_id}.json"
    facade_lock_target = (
        repo_root / "experiments" / "tickets" / f"{experiment_id}.alpha-workflow-finish"
    )
    with file_lock(facade_lock_target):
        ticket = _ticket_from_registry(registry_path, experiment_id)
        if ticket.get("lane") not in {"alpha_search", "alpha_discovery", "universe_scout"}:
            raise WorkflowError(
                "finish_wrong_lane",
                "the three-command finish facade is only for alpha-search lanes",
            )
        already_closed = _is_terminal(ticket.get("status"))
        request = _finish_request(
            ticket,
            before=before_path,
            after=after_path,
            reflection=reflection,
            force_reject=bool(args.reject),
            repo_root=repo_root,
        )
        existing_intent = ticket.get("alpha_workflow_finish_intent")
        if existing_intent is None:
            if already_closed:
                raise WorkflowError(
                    "finish_receipt_missing",
                    "terminal ticket was not closed by this recoverable facade",
                    experiment_id=experiment_id,
                )
            intent = _build_finish_intent(
                ticket,
                request,
                before=before_path,
                after=after_path,
                reflection=reflection,
                force_reject=bool(args.reject),
                judge=judge,
            )
            ticket = _persist_finish_intent(ticket, intent, repo_root=repo_root)
        else:
            intent = _validate_finish_intent(
                existing_intent,
                request=request,
                ticket=ticket,
            )

        if _is_terminal(ticket.get("status")):
            ticket = _bind_terminal_finish_result(
                ticket,
                intent,
                repo_root=repo_root,
            )
            _verify_terminal_finish(ticket, intent)
        else:
            if ticket.get("status") not in ACTIVE_STATUSES:
                raise WorkflowError(
                    "finish_requires_claim",
                    f"finish requires claimed/running, got {ticket.get('status')!r}",
                )
            try:
                update_result(
                    registry_path,
                    experiment_id,
                    intent["judgement"],
                    before_path,
                    after_path,
                    status_override=intent["resolved_decision"],
                    realized_failure_mode=reflection["realized_failure_mode"],
                    surprise_note=reflection["why_result_happened"],
                    allow_missing_prediction=False,
                    timeout_seconds=30.0,
                )
            except Exception as exc:
                current = _ticket_from_registry(registry_path, experiment_id)
                raise WorkflowError(
                    "close_failed_after_commit"
                    if _is_terminal(current.get("status"))
                    else "close_failed",
                    "finish intent is durable; retrying the same command is safe",
                    experiment_id=experiment_id,
                    status=current.get("status"),
                    detail_from_close=str(exc),
                ) from exc
            ticket = _ticket_from_registry(registry_path, experiment_id)
            if not _is_terminal(ticket.get("status")):
                raise WorkflowError(
                    "close_incomplete",
                    "result writer returned without a terminal ticket",
                    experiment_id=experiment_id,
                    status=ticket.get("status"),
                )
            ticket = _bind_terminal_finish_result(
                ticket,
                intent,
                repo_root=repo_root,
            )
            _verify_terminal_finish(ticket, intent)

        log_recovered = _write_or_verify_finish_log(
            intent,
            experiment_id=experiment_id,
            log_path=log_path,
            save_log=save_log,
        )
        maintenance_passed, maintenance = _run_finish_maintenance(
            registry_path=registry_path,
            run_process=run_process,
            repo_root=repo_root,
        )
        payload = {
            "ok": maintenance_passed,
            "command": "finish",
            "experiment_id": experiment_id,
            "status": ticket.get("status"),
            "decision": (ticket.get("result") or {}).get("decision"),
            "already_closed": already_closed,
            "close_committed": True,
            "log_recovered": log_recovered,
            "log_path": _repo_relative(log_path, repo_root=repo_root),
            "maintenance": maintenance,
            "audit_passed": bool(maintenance.get("audit", {}).get("passed")),
        }
        if not maintenance_passed:
            payload.update(
                {
                    "error": "maintenance_failed_after_close",
                    "detail": "close and log are durable; fix the reported derived step and retry",
                }
            )
            return payload, 2
        return payload, 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compress alpha-search operations to qualify, start, and finish while "
            "delegating all existing safety checks."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    qualify_parser = subparsers.add_parser(
        "qualify",
        help="Investment Team cards -> D0-D3 panel -> promotion; never reserves an ID",
    )
    qualify_parser.add_argument("--card", action="append", required=True)
    qualify_parser.add_argument("--scope-manifest", required=True)
    qualify_parser.add_argument("--surfaces", required=True)
    qualify_parser.add_argument("--prior-fingerprints", required=True)
    qualify_parser.add_argument("--proposal")
    qualify_parser.add_argument("--output-dir", required=True)

    start_parser = subparsers.add_parser(
        "start",
        help="revalidate qualification, run dynamic guards, reserve, and claim",
    )
    start_parser.add_argument("--qualification", required=True)
    start_parser.add_argument("--execution-spec", required=True)
    start_parser.add_argument("--owner", required=True)

    finish_parser = subparsers.add_parser(
        "finish",
        help="judge existing artifacts, close once, refresh derived state, and audit",
    )
    finish_parser.add_argument("--experiment-id", required=True)
    finish_parser.add_argument("--before", required=True)
    finish_parser.add_argument("--after", required=True)
    finish_parser.add_argument("--reflection-file", required=True)
    finish_parser.add_argument(
        "--reject",
        action="store_true",
        help="conservatively reject even if numeric Gate metrics pass",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "qualify":
            result = qualify(args)
            code = 0
        elif args.command == "start":
            result = start(args)
            code = 0
        else:
            result, code = finish(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return code
    except WorkflowError as exc:
        print(json.dumps(exc.payload(), ensure_ascii=False, sort_keys=True, indent=2), file=sys.stderr)
        return 2
    except (KeyError, TypeError, ValueError) as exc:
        payload = {"ok": False, "error": "workflow_contract_error", "detail": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
