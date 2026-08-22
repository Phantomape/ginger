"""Outcome-blind repository-anchor integration check for exp-20260729-004."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from quant.alpha_search_contract import (
    HypothesisCandidate,
    canonical_hash,
    normalize_hypothesis_candidate,
)
from quant.alpha_search_engine import evaluate_preflight
from quant.alpha_search_history import build_historical_prior_snapshot
from quant.alpha_search_registry import EvidenceSurfaceRegistry

PARENT_ID = "cand-d3d84780295914d0f19a"
DATA_CUTOFF = "2026-07-29T04:38:00Z"
CREATED_AT = "2026-07-29T04:38:30Z"


def main() -> None:
    parent_event = None
    for line in (ROOT / "data/alpha_search/events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        event = json.loads(line)
        if (
            event.get("record_type") == "candidate_snapshot"
            and (event.get("identity") or {}).get("candidate_id") == PARENT_ID
        ):
            parent_event = event
            break
    if parent_event is None:
        raise RuntimeError("canonical parent event missing")

    parent = normalize_hypothesis_candidate(parent_event["payload"])
    attachment = (
        ROOT
        / "data/experiments/exp-20260729-004/"
        "massive_parent_comparator_allocation_integration_v1.json"
    )
    attachment_locator = attachment.relative_to(ROOT).as_posix()
    attachment_hash = hashlib.sha256(attachment.read_bytes()).hexdigest()
    child = json.loads(json.dumps(parent))
    child["candidate_id"] = "pending"
    child["created_at"] = CREATED_AT
    child["created_by"] = "exp-20260729-004-integration-check"
    child["baseline"]["comparator_allocation_attachment"] = attachment_locator
    child["baseline"]["comparator_allocation_attachment_hash"] = attachment_hash
    child["next_machine_action"] = "verify repository-authenticated lineage only"
    child["amendment_lineage"] = {
        "parent_candidate_id": PARENT_ID,
        "parent_candidate_snapshot": parent,
        "parent_candidate_snapshot_hash": canonical_hash(parent),
        "parent_selection_scope_id": parent_event["identity"]["selection_scope_id"],
        "amendment_reason": "outcome_blind_contract_completion",
        "changed_fields": [
            "baseline.comparator_allocation_attachment",
            "baseline.comparator_allocation_attachment_hash",
            "next_machine_action",
        ],
        "parent_outcome_accessed": False,
        "parent_experiment_id": None,
        "declared_at": CREATED_AT,
    }
    child = HypothesisCandidate.with_computed_id(child).to_dict()

    history = build_historical_prior_snapshot(
        ROOT / "docs/frozen_families.jsonl",
        history_cutoff=DATA_CUTOFF,
        repo_root=ROOT,
    )
    registry = EvidenceSurfaceRegistry.from_dict(
        json.loads(
            (ROOT / "data/reference/alpha_search_evidence_surfaces.json").read_text(
                encoding="utf-8"
            )
        )
    )
    preflight = evaluate_preflight(
        child,
        registry,
        prior_fingerprints=history,
        data_cutoff=DATA_CUTOFF,
        evaluated_at="2026-07-29T04:39:00Z",
        selection_scope_id="scope-222222222222222222222222",
    )
    print(
        json.dumps(
            {
                "candidate_id": child["candidate_id"],
                "parent_candidate_id": PARENT_ID,
                "history_record_count": history["record_count"],
                "history_snapshot_hash": history["snapshot_hash"],
                "outcome_blind": preflight["outcome_blind"],
                "d3": preflight["gates"]["D3"],
                "decision": preflight["decision"],
                "failure_reasons": preflight["failure_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
