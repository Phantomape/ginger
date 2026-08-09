#!/usr/bin/env python3
"""CLI for Ginger's outcome-blind alpha discovery layer.

This command intentionally has no experiment-reservation or trading action.
It validates contracts, evaluates source/preflight metadata, freezes complete
selection panels, and builds read-only reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.alpha_search_engine import (  # noqa: E402
    AlphaSearchError,
    build_failure_taxonomy,
    build_search_report,
    build_selection_scope_manifest,
    evaluate_preflight,
    freeze_selection_panel,
    verify_selection_panel,
)
from quant.alpha_search_history import (  # noqa: E402
    HistoricalPriorError,
    build_historical_prior_snapshot,
    require_nonempty_snapshot,
    validate_repository_historical_snapshot,
)
from quant.alpha_mechanism_generator import build_mechanism_lead_batch  # noqa: E402
from quant.data_paths import atomic_write_json  # noqa: E402
from scripts.alpha_debate import build_promotion_request  # noqa: E402


def _load_json(path: str | Path) -> Any:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise AlphaSearchError("input_read_failed", f"{source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AlphaSearchError("invalid_json", f"{source}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    return value


def _write_or_print(value: Any, output: str | None) -> None:
    if output:
        atomic_write_json(value, Path(output), indent=2, ensure_ascii=False)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _candidate_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and isinstance(value.get("candidate"), Mapping):
        value = value["candidate"]
    if not isinstance(value, Mapping):
        raise AlphaSearchError("invalid_candidate", "candidate JSON must be an object")
    return dict(value)


def _candidate_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        value = value.get("candidates")
    if not isinstance(value, list):
        raise AlphaSearchError("invalid_candidate_pool", "expected a JSON list or {candidates: [...]} object")
    if any(not isinstance(row, Mapping) for row in value):
        raise AlphaSearchError("invalid_candidate_pool", "every candidate must be an object")
    return [dict(row) for row in value]


def _surface_payload(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("surfaces"), list):
        payload = dict(value)
        payload.setdefault("schema_version", 1)
    elif isinstance(value, list):
        payload = {"schema_version": 1, "surfaces": value}
    else:
        raise AlphaSearchError("invalid_surface_registry", "surface registry must be {schema_version, surfaces}")
    try:
        from quant.alpha_search_registry import EvidenceSurfaceRegistry
        return EvidenceSurfaceRegistry.from_dict(payload)
    except ImportError:  # pragma: no cover - incomplete checkout guard.
        return payload


def _history_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        for key in ("records", "experiments", "rows"):
            if isinstance(value.get(key), list):
                value = value[key]
                break
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise AlphaSearchError("invalid_failure_history", "history must contain a list of objects")
    return [dict(row) for row in value]


def _prior_fingerprint_rows(
    path: str,
    *,
    snapshot_required: bool = False,
    isolated_history_fixture: bool = False,
) -> Any:
    value = _load_json(path)
    if isinstance(value, Mapping):
        try:
            snapshot = require_nonempty_snapshot(value)
            if not isolated_history_fixture:
                snapshot = validate_repository_historical_snapshot(
                    snapshot, repo_root=REPO_ROOT
                )
        except HistoricalPriorError as exc:
            raise AlphaSearchError(exc.code, exc.detail) from exc
        return snapshot
    if snapshot_required:
        raise AlphaSearchError(
            "historical_snapshot_required",
            "new strict scopes require a canonical historical snapshot object, not a bare list",
        )
    if not isinstance(value, list):
        raise AlphaSearchError(
            "invalid_prior_fingerprints", "expected a historical snapshot or legacy JSON list"
        )
    return value


def _validate_contract(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Use the strict contract model when present; keep CLI import-light."""
    try:
        from quant.alpha_search_contract import HypothesisCandidate
    except ImportError:
        # During a partial checkout the preflight remains fail-closed on its
        # mandatory fields.  The completed Phase-1 tree always has the model.
        return dict(candidate)
    parsed = HypothesisCandidate.from_dict(candidate)
    parsed.validate_semantic_id()
    return parsed.to_dict()


def _queue_budgets(values: list[str]) -> dict[str, int]:
    budgets = {"exploration": 0, "adjacent": 0, "exploitation": 0}
    for value in values:
        if "=" not in value:
            raise AlphaSearchError("invalid_queue_budget", f"expected queue=count, got {value!r}")
        key, raw_count = value.split("=", 1)
        key = key.strip()
        if key == "explore":
            key = "exploration"
        elif key == "exploit":
            key = "exploitation"
        if key not in budgets:
            raise AlphaSearchError("invalid_queue_budget", f"unknown queue {key!r}")
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise AlphaSearchError("invalid_queue_budget", f"invalid count {raw_count!r}") from exc
        if count < 0:
            raise AlphaSearchError("invalid_queue_budget", f"negative count for {key}")
        budgets[key] = count
    return budgets


def _cmd_validate_candidate(args: argparse.Namespace) -> dict[str, Any]:
    candidate = _validate_contract(_candidate_payload(_load_json(args.candidate)))
    result: dict[str, Any] = {
        "valid": True,
        "candidate_id": candidate.get("candidate_id"),
        "evidence_grade": candidate.get("evidence_grade"),
        "outcome_blind_contract": True,
        "trade_enabled": False,
    }
    if args.surfaces:
        if not args.data_cutoff:
            raise AlphaSearchError(
                "invalid_clock", "--data-cutoff is required when --surfaces is used"
            )
        preflight = evaluate_preflight(
            candidate,
            _surface_payload(_load_json(args.surfaces)),
            data_cutoff=args.data_cutoff,
        )
        result["preflight"] = preflight
    return result


def _cmd_preflight(args: argparse.Namespace) -> dict[str, Any]:
    candidate = _validate_contract(_candidate_payload(_load_json(args.candidate)))
    prior_fingerprints = _prior_fingerprint_rows(
        args.prior_fingerprints,
        snapshot_required=True,
        isolated_history_fixture=args.isolated_history_fixture,
    )
    return evaluate_preflight(
        candidate,
        _surface_payload(_load_json(args.surfaces)),
        prior_fingerprints=prior_fingerprints,
        data_cutoff=args.data_cutoff,
    )


def _cmd_build_scope(args: argparse.Namespace) -> dict[str, Any]:
    surfaces = _surface_payload(_load_json(args.surfaces))
    generation_config = _load_json(args.generation_config)
    if not isinstance(generation_config, Mapping):
        raise AlphaSearchError(
            "invalid_generation_config", "candidate generation config must be an object"
        )
    allowed_surface_ids = sorted(set(args.allowed_surface or []))
    if not allowed_surface_ids:
        raise AlphaSearchError(
            "invalid_selection_scope_manifest", "at least one --allowed-surface is required"
        )
    unknown = sorted(set(allowed_surface_ids) - set(surfaces.surface_ids))
    if unknown:
        raise AlphaSearchError(
            "invalid_selection_scope_manifest", f"unknown allowed surfaces: {unknown}"
        )
    return build_selection_scope_manifest(
        scope_name=args.scope_name,
        preregistered_at=args.preregistered_at,
        data_cutoff=args.data_cutoff,
        freeze_at=args.freeze_at,
        generator_version=args.generator_version,
        candidate_generation_config=generation_config,
        allowed_surface_ids=allowed_surface_ids,
        surface_registry_hash=surfaces.canonical_hash,
        prior_fingerprints=_prior_fingerprint_rows(
            args.prior_fingerprints,
            snapshot_required=True,
            isolated_history_fixture=args.isolated_history_fixture,
        ),
        queue_budgets=_queue_budgets(args.queue_budget),
        expected_candidate_count=args.expected_candidate_count,
        selection_limit=args.selection_limit,
        batch_policy_bundle_id=args.batch_policy_bundle_id,
    )


def _cmd_build_panel(args: argparse.Namespace) -> dict[str, Any]:
    candidates = [
        _validate_contract(candidate)
        for candidate in _candidate_rows(_load_json(args.candidates))
    ]
    prior_fingerprints = _prior_fingerprint_rows(
        args.prior_fingerprints,
        isolated_history_fixture=args.isolated_history_fixture,
    )
    scope_manifest = _load_json(args.scope_manifest)
    if not isinstance(scope_manifest, Mapping):
        raise AlphaSearchError("invalid_selection_scope_manifest", "scope manifest must be an object")
    panel = freeze_selection_panel(
        candidates,
        _surface_payload(_load_json(args.surfaces)),
        scope_manifest=scope_manifest,
        selection_pool_complete=args.selection_pool_complete,
        prior_fingerprints=prior_fingerprints,
    )
    if args.ledger:
        from quant.alpha_search_ledger import append_discovery_batch

        events: list[dict[str, Any]] = []
        for candidate in panel["candidate_snapshots"]:
            events.append(
                {
                    "record_type": "candidate_snapshot",
                    "payload": candidate,
                    "selection_scope_id": panel["selection_scope_id"],
                }
            )
        for candidate_id, preflight in panel["preflight_decisions"].items():
            events.append(
                {
                    "record_type": "preflight_decision",
                    "payload": preflight,
                }
            )
        events.append(
            {
                "record_type": "panel_selection",
                "payload": panel,
            }
        )
        # One lock and one atomic replace: a scope can never be half-written.
        append_discovery_batch(args.ledger, events)
    return panel


def _cmd_verify_panel(args: argparse.Namespace) -> dict[str, Any]:
    value = _load_json(args.panel)
    if not isinstance(value, Mapping):
        raise AlphaSearchError("invalid_panel", "panel must be an object")
    scope_manifest = _load_json(args.scope_manifest)
    if not isinstance(scope_manifest, Mapping):
        raise AlphaSearchError("invalid_selection_scope_manifest", "scope manifest must be an object")
    prior_fingerprints = _prior_fingerprint_rows(
        args.prior_fingerprints,
        isolated_history_fixture=args.isolated_history_fixture,
    )
    return verify_selection_panel(
        value,
        surfaces=_surface_payload(_load_json(args.surfaces)),
        scope_manifest=scope_manifest,
        prior_fingerprints=prior_fingerprints,
        require_external_context=True,
    )


def _cmd_report(args: argparse.Namespace) -> dict[str, Any]:
    value = _load_json(args.panel)
    if not isinstance(value, Mapping):
        raise AlphaSearchError("invalid_panel", "panel must be an object")
    scope_manifest = _load_json(args.scope_manifest)
    if not isinstance(scope_manifest, Mapping):
        raise AlphaSearchError("invalid_selection_scope_manifest", "scope manifest must be an object")
    prior_fingerprints = _prior_fingerprint_rows(
        args.prior_fingerprints,
        isolated_history_fixture=args.isolated_history_fixture,
    )
    return build_search_report(
        value,
        surfaces=_surface_payload(_load_json(args.surfaces)),
        scope_manifest=scope_manifest,
        prior_fingerprints=prior_fingerprints,
        require_external_context=True,
    )


def _cmd_failure_map(args: argparse.Namespace) -> dict[str, Any]:
    return build_failure_taxonomy(_history_rows(_load_json(args.history)))


def _cmd_build_history(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return build_historical_prior_snapshot(
            args.frozen_families,
            history_cutoff=args.history_cutoff,
            discovery_ledgers=args.discovery_ledger,
            open_tickets=args.open_ticket,
            repo_root=REPO_ROOT,
            isolated_fixture=args.isolated_history_fixture,
        )
    except HistoricalPriorError as exc:
        raise AlphaSearchError(exc.code, exc.detail) from exc


def _cmd_build_mechanism_leads(args: argparse.Namespace) -> dict[str, Any]:
    """Validate one external scan and render lead-only research-map sections."""

    scan = _load_json(args.scan)
    registry = _load_json(args.generator_registry)
    if not isinstance(scan, Mapping):
        raise AlphaSearchError("invalid_mechanism_scan", "scan must be an object")
    if not isinstance(registry, Mapping):
        raise AlphaSearchError("invalid_generator_registry", "registry must be an object")
    known_surface_ids = None
    if args.surfaces:
        surfaces = _surface_payload(_load_json(args.surfaces))
        known_surface_ids = surfaces.surface_ids
    return build_mechanism_lead_batch(
        scan,
        registry,
        known_surface_ids=known_surface_ids,
    )


def _cmd_build_promotion(args: argparse.Namespace) -> dict[str, Any]:
    """Revalidate one selected D0-D3 candidate and freeze its admission proof."""

    proposal = _load_json(args.proposal)
    if not isinstance(proposal, Mapping):
        raise AlphaSearchError("invalid_ticket_proposal", "proposal must be an object")
    if args.repo_root and not args.isolated_fixture:
        raise AlphaSearchError(
            "isolated_fixture_required",
            "--repo-root is test-only and requires --isolated-fixture",
        )
    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    return build_promotion_request(
        panel_path=args.panel,
        scope_manifest_path=args.scope_manifest,
        surface_registry_path=args.surfaces,
        prior_fingerprints_path=args.prior_fingerprints,
        debate_artifact_path=args.debate_lock,
        proposal=proposal,
        repo_root=repo_root,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Outcome-blind alpha candidate validation and panel freezing (never trades or reserves IDs)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-candidate", help="validate one HypothesisCandidate")
    validate.add_argument("candidate")
    validate.add_argument("--surfaces")
    validate.add_argument("--data-cutoff")
    validate.add_argument("--output")
    validate.set_defaults(handler=_cmd_validate_candidate)

    preflight = subparsers.add_parser("preflight", help="run outcome-blind D0-D3 preflight")
    preflight.add_argument("candidate")
    preflight.add_argument("--surfaces", required=True)
    preflight.add_argument("--data-cutoff", required=True)
    preflight.add_argument("--prior-fingerprints", required=True)
    preflight.add_argument("--isolated-history-fixture", action="store_true")
    preflight.add_argument("--output")
    preflight.set_defaults(handler=_cmd_preflight)

    scope = subparsers.add_parser(
        "build-scope", help="pre-register a complete outcome-blind selection scope"
    )
    scope.add_argument("--scope-name", required=True)
    scope.add_argument("--preregistered-at", required=True)
    scope.add_argument("--data-cutoff", required=True)
    scope.add_argument("--freeze-at", required=True)
    scope.add_argument("--generator-version", required=True)
    scope.add_argument("--generation-config", required=True)
    scope.add_argument("--surfaces", required=True)
    scope.add_argument("--prior-fingerprints", required=True)
    scope.add_argument("--isolated-history-fixture", action="store_true")
    scope.add_argument("--allowed-surface", action="append", default=[], required=True)
    scope.add_argument(
        "--queue-budget",
        action="append",
        default=[],
        metavar="QUEUE=COUNT",
        help="repeat for exploration, adjacent and exploitation",
    )
    scope.add_argument("--expected-candidate-count", required=True, type=int)
    scope.add_argument("--selection-limit", type=int, default=1)
    scope.add_argument("--batch-policy-bundle-id")
    scope.add_argument("--output")
    scope.set_defaults(handler=_cmd_build_scope)

    panel = subparsers.add_parser("build-panel", help="freeze a complete candidate selection panel")
    panel.add_argument("candidates")
    panel.add_argument("--surfaces", required=True)
    panel.add_argument("--scope-manifest", required=True)
    panel.add_argument("--prior-fingerprints", required=True)
    panel.add_argument("--isolated-history-fixture", action="store_true")
    panel.add_argument("--selection-pool-complete", action="store_true", required=True)
    panel.add_argument(
        "--ledger",
        help="optional append-only discovery ledger; never an outcome or experiment ledger",
    )
    panel.add_argument("--output")
    panel.set_defaults(handler=_cmd_build_panel)

    verify = subparsers.add_parser("verify-panel", help="recompute panel integrity")
    verify.add_argument("panel")
    verify.add_argument("--surfaces", required=True)
    verify.add_argument("--scope-manifest", required=True)
    verify.add_argument("--prior-fingerprints", required=True)
    verify.add_argument("--isolated-history-fixture", action="store_true")
    verify.add_argument("--output")
    verify.set_defaults(handler=_cmd_verify_panel)

    report = subparsers.add_parser("report", help="build a read-only report from a frozen panel")
    report.add_argument("panel")
    report.add_argument("--surfaces", required=True)
    report.add_argument("--scope-manifest", required=True)
    report.add_argument("--prior-fingerprints", required=True)
    report.add_argument("--isolated-history-fixture", action="store_true")
    report.add_argument("--output")
    report.set_defaults(handler=_cmd_report)

    failure_map = subparsers.add_parser("failure-map", help="map historical closeouts to the closed taxonomy")
    failure_map.add_argument("history")
    failure_map.add_argument("--output")
    failure_map.set_defaults(handler=_cmd_failure_map)

    history = subparsers.add_parser(
        "build-history",
        help="freeze a canonical, time-anchored historical prior snapshot",
    )
    history.add_argument(
        "--frozen-families",
        default=str(REPO_ROOT / "docs" / "frozen_families.jsonl"),
    )
    history.add_argument("--history-cutoff", required=True)
    history.add_argument("--discovery-ledger", action="append", default=[])
    history.add_argument("--open-ticket", action="append", default=[])
    history.add_argument("--isolated-history-fixture", action="store_true")
    history.add_argument("--output")
    history.set_defaults(handler=_cmd_build_history)

    mechanism = subparsers.add_parser(
        "build-mechanism-leads",
        help=(
            "validate an outcome-blind external mechanism scan and render "
            "lead-only research-map sections (never ranks, trades, reserves IDs, or builds a panel)"
        ),
    )
    mechanism.add_argument("scan")
    mechanism.add_argument(
        "--generator-registry",
        default=str(REPO_ROOT / "data" / "reference" / "alpha_mechanism_generators.json"),
    )
    mechanism.add_argument(
        "--surfaces",
        help=(
            "required only when the scan explicitly requests candidate projection; "
            "IDs must already exist in this EvidenceSurface registry"
        ),
    )
    mechanism.add_argument("--output")
    mechanism.set_defaults(handler=_cmd_build_mechanism_leads)

    promotion = subparsers.add_parser(
        "build-promotion",
        help=(
            "strictly revalidate a one-candidate D0-D3 panel and freeze an "
            "immutable admission proof (never reserves an experiment ID)"
        ),
    )
    promotion.add_argument("panel")
    promotion.add_argument("--surfaces", required=True)
    promotion.add_argument("--scope-manifest", required=True)
    promotion.add_argument("--prior-fingerprints", required=True)
    promotion.add_argument("--debate-lock", help=argparse.SUPPRESS)
    promotion.add_argument("--proposal", required=True)
    promotion.add_argument("--output", required=True)
    promotion.add_argument("--repo-root", help=argparse.SUPPRESS)
    promotion.add_argument("--isolated-fixture", action="store_true", help=argparse.SUPPRESS)
    promotion.set_defaults(handler=_cmd_build_promotion)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
        _write_or_print(result, getattr(args, "output", None))
        return 0
    except (AlphaSearchError, ValueError, TypeError, KeyError) as exc:
        code = getattr(exc, "code", "alpha_search_error")
        print(json.dumps({"ok": False, "error": code, "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
