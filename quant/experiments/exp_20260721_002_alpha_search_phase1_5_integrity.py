"""Materialize and audit the immutable Phase-1.5 integrity rerun.

This runner does not read candidate returns, run a backtest, reserve another
experiment, or alter any trading policy.  It replays the already-declared
three-candidate discovery pool against a canonical historical snapshot and the
clock-qualified estimate-revision readiness surface.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "quant"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from quant.alpha_search_contract import HypothesisCandidate  # noqa: E402
from quant.alpha_search_engine import (  # noqa: E402
    AlphaSearchError,
    build_search_report,
    freeze_selection_panel,
    verify_selection_panel,
)
from quant.alpha_search_history import (  # noqa: E402
    legacy_near_neighbors,
    validate_repository_historical_snapshot,
)
from quant.alpha_search_ledger import append_discovery_batch  # noqa: E402
from quant.alpha_search_registry import EvidenceSurfaceRegistry  # noqa: E402
from quant.data_paths import atomic_write_json  # noqa: E402
from quant.experiment_history import build_history_report  # noqa: E402


EXPERIMENT_ID = "exp-20260721-002"
BASELINE = ROOT / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
REGISTRY = ROOT / "data/reference/alpha_search_evidence_surfaces.json"
READINESS = ROOT / "data/non_ohlcv/estimate_revision_readiness_latest.json"
INSTRUMENT_MAP = ROOT / "data/reference/estimate_revision_instrument_map.jsonl"
LEGACY_POOL = ROOT / "data/alpha_search/phase1_candidate_pool_20260721.json"
PRIOR = ROOT / "data/alpha_search/phase1_5_prior_fingerprints_20260721.json"
SCOPE = ROOT / "data/alpha_search/phase1_5_scope_manifest_20260721.json"
CANDIDATE_POOL = ROOT / "data/alpha_search/phase1_5_candidate_pool_20260721.json"
PANEL = ROOT / "data/alpha_search/phase1_5_selection_panel_20260721.json"
REPORT = ROOT / "data/alpha_search/phase1_5_latest_report.json"
LEDGER = ROOT / "data/alpha_search/events.jsonl"
ARTIFACT_DIR = ROOT / f"data/experiments/{EXPERIMENT_ID}"
ARTIFACT = ARTIFACT_DIR / "alpha_search_phase1_5_integrity.json"
AFTER = ARTIFACT_DIR / "after_measurement.json"

CANDIDATE_CREATED_AT = "2026-07-21T17:14:10Z"
EXPECTED_BASELINE_SHA256 = "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731"
IMMUTABLE_PHASE1_HASHES = {
    "data/alpha_search/phase1_prior_fingerprints_20260721.json": "37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570",
    "data/alpha_search/phase1_scope_manifest_20260721.json": "fc145c9275f03fcbf48251d1f5a774407a6aab7b8ea4b1f26f3e6de19b881f31",
    "data/alpha_search/phase1_candidate_pool_20260721.json": "aa6833a31245c1a9cba020a7af040d0cc824a2dfd203cace8836629995663b67",
    "data/alpha_search/phase1_selection_panel_20260721.json": "21a8de10061527c08ffda002f59a61f610f5c109b2632ae2e671f65a6ce77fe7",
    "data/alpha_search/latest_report.json": "ce2706a0fac6b1b00d118063eca873a6ce597b9ee620944a6cfebb27a4022bad",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clock(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timezone-aware clock required: {value}")
    return parsed.astimezone(timezone.utc)


def _phase1_hash_audit() -> dict[str, Any]:
    actual = {
        locator: _sha256(ROOT / locator)
        for locator in IMMUTABLE_PHASE1_HASHES
    }
    return {
        "expected": IMMUTABLE_PHASE1_HASHES,
        "actual": actual,
        "all_unchanged": actual == IMMUTABLE_PHASE1_HASHES,
    }


def _build_candidate_pool(scope: Mapping[str, Any]) -> dict[str, Any]:
    source = _read_json(LEGACY_POOL)
    candidates = copy.deepcopy(source["candidates"])
    for row in candidates:
        row["created_at"] = CANDIDATE_CREATED_AT
        row["created_by"] = "alpha_search_phase1_5_integrity_replay"
        parsed = HypothesisCandidate.from_dict(row)
        parsed.validate_semantic_id()
    return {
        "schema_version": 1,
        "data_cutoff": scope["data_cutoff"],
        "selection_pool_complete": True,
        "queue_budgets": dict(scope["queue_budgets"]),
        "candidates": candidates,
    }


def _discovery_events(panel: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for candidate in panel["candidate_snapshots"]:
        events.append(
            {
                "record_type": "candidate_snapshot",
                "payload": candidate,
                "selection_scope_id": panel["selection_scope_id"],
            }
        )
    for preflight in panel["preflight_decisions"].values():
        events.append({"record_type": "preflight_decision", "payload": preflight})
    events.append({"record_type": "panel_selection", "payload": panel})
    return events


def _active_meta_imports() -> list[str]:
    hits: list[str] = []
    needles = ("import meta_research_engine", "from meta_research_engine", "from quant.meta_research_engine")
    for path in sorted((ROOT / "quant").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py")):
        # This integrity runner names the retired imports in its audit predicate;
        # those string literals are not an active dependency.
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if any(needle in text for needle in needles):
            hits.append(path.relative_to(ROOT).as_posix())
    return hits


def _empty_prior_fails_closed(
    candidates: list[dict[str, Any]],
    surfaces: EvidenceSurfaceRegistry,
    scope: Mapping[str, Any],
) -> tuple[bool, str | None]:
    try:
        freeze_selection_panel(
            candidates,
            surfaces,
            scope_manifest=scope,
            selection_pool_complete=True,
            prior_fingerprints=[],
        )
    except AlphaSearchError as exc:
        return True, getattr(exc, "code", type(exc).__name__)
    return False, None


def _baseline_metrics(baseline: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = baseline["aggregate"]
    return {
        "expected_value_score_sum": aggregate["expected_value_score_sum"],
        "total_pnl_sum": aggregate["total_pnl_sum"],
        "trade_count_sum": aggregate["trade_count_sum"],
        "positive_ev_windows": aggregate["positive_ev_windows"],
        "minimum_survival_rate": aggregate["minimum_survival_rate"],
        "worst_max_drawdown_pct": aggregate["worst_max_drawdown_pct"],
    }


def evaluate(*, persist: bool = True) -> dict[str, Any]:
    baseline = _read_json(BASELINE)
    scope = _read_json(SCOPE)
    prior = validate_repository_historical_snapshot(_read_json(PRIOR), repo_root=ROOT)
    candidate_pool = _read_json(CANDIDATE_POOL)
    panel = _read_json(PANEL)
    report = _read_json(REPORT)
    readiness = _read_json(READINESS)
    surfaces = EvidenceSurfaceRegistry.load(REGISTRY)
    verification = verify_selection_panel(
        panel,
        surfaces=surfaces,
        scope_manifest=scope,
        prior_fingerprints=prior,
        require_external_context=True,
    )
    candidates = candidate_pool["candidates"]
    muted = next(
        row for row in candidates if row.get("title") == "Muted price response after a consensus revision"
    )
    muted_preflight = panel["preflight_decisions"][muted["candidate_id"]]
    d3_reasons = list(muted_preflight["gates"]["D3"]["reasons"])
    muted_neighbors = legacy_near_neighbors(muted, prior["records"])
    required_muted_neighbors = [
        neighbor
        for neighbor in muted_neighbors
        if "exp-20260605-029" in neighbor.get("representative_exps", [])
    ]
    empty_failed, empty_error = _empty_prior_fails_closed(candidates, surfaces, scope)
    history_report = build_history_report(ROOT)
    forbidden_history_outputs = sorted(
        {
            "priority_formula",
            "research_priorities",
            "strategy_research_priorities",
            "measurement_repair_priorities",
            "recommendations",
            "top_experiments",
            "worst_experiments",
        }
        & set(history_report)
    )
    map_rows = [
        json.loads(line)
        for line in INSTRUMENT_MAP.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    map_keys = [
        (str(row.get("source_ticker")), str(row.get("cik")))
        for row in map_rows
    ]
    phase1_audit = _phase1_hash_audit()
    baseline_hash = _sha256(BASELINE)
    active_meta_imports = _active_meta_imports()
    acceptance = {
        "canonical_history_nonempty": prior["record_count"] > 0,
        "canonical_history_repository_verified": True,
        "empty_prior_fails_closed": empty_failed,
        "empty_prior_error_is_anchor_mismatch": empty_error
        in {"prior_fingerprint_snapshot_mismatch", "historical_snapshot_required"},
        "muted_revision_d3_rejected": muted_preflight["gates"]["D3"]["status"] == "reject",
        "muted_revision_hits_exp_20260605_029": bool(required_muted_neighbors),
        "panel_external_verification_valid": verification.get("valid") is True,
        "candidate_count_three": len(candidates) == 3,
        "selected_count_zero": panel.get("selected_candidate_id") is None,
        "readiness_parked": readiness.get("status") == "parked",
        "no_retroqualified_revision_decisions": readiness.get("independent_decisions") == 0,
        "all_legacy_rows_quarantined": readiness.get("raw_rows")
        == readiness.get("quarantined_rows"),
        "settled_h5_h10_h20_zero": readiness.get("settled_independent_decisions_by_horizon")
        == {"h5": 0, "h10": 0, "h20": 0},
        "instrument_map_unique_natural_keys": len(map_keys) == len(set(map_keys)),
        "instrument_map_forward_effective": bool(map_rows)
        and {row.get("effective_from") for row in map_rows} == {"2026-07-21"},
        "meta_ranker_deleted": not (ROOT / "quant/meta_research_engine.py").exists(),
        "no_active_meta_ranker_imports": not active_meta_imports,
        "history_report_has_no_priority_surface": not forbidden_history_outputs,
        "legacy_phase1_artifacts_unchanged": phase1_audit["all_unchanged"],
        "baseline_artifact_unchanged": baseline_hash == EXPECTED_BASELINE_SHA256,
        "trade_enabled_false": panel.get("trade_enabled") is False,
        "outcome_blind": panel.get("outcome_blind") is True,
    }
    artifact = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "accepted_measurement_repair" if all(acceptance.values()) else "blocked",
        "accepted_alpha": False,
        "phase2_decision": "NO_GO",
        "acceptance": acceptance,
        "prior_snapshot": {
            "history_cutoff": prior["history_cutoff"],
            "record_count": prior["record_count"],
            "snapshot_hash": prior["snapshot_hash"],
            "source_anchors": prior["source_anchors"],
        },
        "selection": {
            "selection_scope_id": panel["selection_scope_id"],
            "panel_hash": panel["panel_hash"],
            "candidate_count": len(candidates),
            "selected_candidate_id": panel.get("selected_candidate_id"),
            "muted_revision_candidate_id": muted["candidate_id"],
            "muted_revision_decision": muted_preflight["decision"],
            "muted_revision_d3_reasons": d3_reasons,
            "muted_revision_required_legacy_neighbors": required_muted_neighbors,
            "failure_counts": report.get("failure_counts"),
            "verification": verification,
        },
        "revision_readiness": readiness,
        "instrument_map": {
            "row_count": len(map_rows),
            "sha256": _sha256(INSTRUMENT_MAP),
            "missing_tickers": ["IWM", "MUU", "SNXX"],
            "effective_from": "2026-07-21",
        },
        "meta_retirement": {
            "deleted_module": "quant/meta_research_engine.py",
            "replacement_module": "quant/experiment_history.py",
            "active_imports": active_meta_imports,
            "forbidden_history_outputs": forbidden_history_outputs,
        },
        "legacy_phase1_hash_audit": phase1_audit,
        "before_metrics": _baseline_metrics(baseline),
        "after_metrics": _baseline_metrics(baseline),
        "delta_metrics": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "scope": "default_off_alpha_search_history_and_revision_readiness",
        },
        "reopen_condition": readiness.get("reopen_condition"),
    }
    if persist:
        atomic_write_json(artifact, ARTIFACT, indent=2, ensure_ascii=False)
        after = copy.deepcopy(baseline)
        after["schema"] = "alpha_search_phase1_5_measurement_repair_v1"
        after["experiment_id"] = EXPERIMENT_ID
        after["generated_at"] = artifact["generated_at"]
        after["decision"] = artifact["decision"]
        after["accepted_alpha"] = False
        after["measurement_repair"] = artifact
        atomic_write_json(after, AFTER, indent=2, ensure_ascii=False)
    return artifact


def materialize() -> dict[str, Any]:
    scope = _read_json(SCOPE)
    if datetime.now(timezone.utc) < _clock(scope["freeze_at"]):
        raise RuntimeError("selection scope freeze_at has not arrived")
    prior = validate_repository_historical_snapshot(_read_json(PRIOR), repo_root=ROOT)
    surfaces = EvidenceSurfaceRegistry.load(REGISTRY)
    candidate_pool = _build_candidate_pool(scope)
    atomic_write_json(candidate_pool, CANDIDATE_POOL, indent=2, ensure_ascii=False)
    panel = freeze_selection_panel(
        candidate_pool["candidates"],
        surfaces,
        scope_manifest=scope,
        selection_pool_complete=True,
        prior_fingerprints=prior,
    )
    atomic_write_json(panel, PANEL, indent=2, ensure_ascii=False)
    append_discovery_batch(LEDGER, _discovery_events(panel))
    report = build_search_report(
        panel,
        surfaces=surfaces,
        scope_manifest=scope,
        prior_fingerprints=prior,
        require_external_context=True,
    )
    atomic_write_json(report, REPORT, indent=2, ensure_ascii=False)
    return evaluate(persist=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("materialize", "evaluate"), nargs="?", default="evaluate")
    args = parser.parse_args()
    result = materialize() if args.action == "materialize" else evaluate(persist=True)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": result["decision"],
                "phase2_decision": result["phase2_decision"],
                "acceptance": result["acceptance"],
                "artifact": ARTIFACT.relative_to(ROOT).as_posix(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result["decision"] == "accepted_measurement_repair" else 2


if __name__ == "__main__":
    raise SystemExit(main())
