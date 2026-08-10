from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from quant.alpha_search_contract import HypothesisCandidate, canonical_hash


REPO_ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
WINDOW_ARTIFACTS = {
    "late_strong": REPO_ROOT
    / "data/backtests/cash_feasible_20260715/late_strong_exp-20260715-010.json",
    "mid_weak": REPO_ROOT
    / "data/backtests/cash_feasible_20260715/mid_weak_exp-20260715-010.json",
    "old_thin": REPO_ROOT
    / "data/backtests/cash_feasible_20260715/old_thin_exp-20260715-010.json",
}
GATE1_ANCHOR = (
    REPO_ROOT
    / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_core_slot_identities(
    window_artifacts: Mapping[str, Path],
) -> list[dict[str, str]]:
    """Project only entry-time core-slot identity fields from frozen Gate 1 trades."""

    slots: list[dict[str, str]] = []
    for window, path in sorted(window_artifacts.items()):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for trade in payload.get("trades", []):
            entry_price = format(Decimal(str(trade["entry_price"])), ".4f")
            ticker = str(trade["ticker"])
            entry_date = str(trade["entry_date"])
            slots.append(
                {
                    "core_slot_id": f"{ticker}:{entry_date}:{entry_price}",
                    "ticker": ticker,
                    "entry_date": entry_date,
                    "gate1_window": window,
                }
            )
    return sorted(slots, key=lambda row: (row["entry_date"], row["core_slot_id"]))


def allocate_comparators(
    treatment_rows: Iterable[Mapping[str, Any]],
    core_slots: Iterable[Mapping[str, str]],
    *,
    allocator_input_hashes: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Allocate each actual core slot once; unmatched decisions receive cash."""

    slots_by_date: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for slot in core_slots:
        slots_by_date[str(slot["entry_date"])].append(slot)
    for slots in slots_by_date.values():
        slots.sort(key=lambda row: str(row["core_slot_id"]))

    consumed: set[str] = set()
    ordered = sorted(
        treatment_rows,
        key=lambda row: (
            str(row["entry_session"]),
            str(row["declaration_date"]),
            str(row["ticker"]),
        ),
    )
    allocations: list[dict[str, Any]] = []
    for ordinal, row in enumerate(ordered, start=1):
        ticker = str(row["ticker"])
        entry_session = str(row["entry_session"])
        available = [
            slot
            for slot in slots_by_date.get(entry_session, [])
            if str(slot["core_slot_id"]) not in consumed
        ]
        eligible = [slot for slot in available if str(slot["ticker"]) != ticker]
        if eligible:
            selected = eligible[0]
            core_slot_id = str(selected["core_slot_id"])
            consumed.add(core_slot_id)
            comparator_kind = "core_slot"
            collision_reason = None
        else:
            core_slot_id = None
            comparator_kind = "cash"
            collision_reason = (
                "same_ticker_core_slot_collision"
                if available
                else "no_core_slot_same_entry_session"
            )
        allocations.append(
            {
                "decision_key": str(row["decision_key"]),
                "ordinal": ordinal,
                "comparator_kind": comparator_kind,
                "core_slot_id": core_slot_id,
                "collision_reason": collision_reason,
                "allocator_input_hashes": dict(sorted(allocator_input_hashes.items())),
            }
        )
    return allocations


def build_contract_artifacts(
    *,
    parent_candidate_path: Path,
    parent_panel_path: Path,
    preflight_path: Path,
    attachment_path: Path,
    amended_candidate_path: Path,
    declared_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    parent_raw = json.loads(parent_candidate_path.read_text(encoding="utf-8"))
    parent_contract = HypothesisCandidate.from_dict(parent_raw).validate_semantic_id()
    panel = json.loads(parent_panel_path.read_text(encoding="utf-8"))
    parent_id = parent_contract.candidate_id
    parent = next(
        (
            row
            for row in panel.get("candidate_snapshots", [])
            if row.get("candidate_id") == parent_id
        ),
        None,
    )
    if parent is None:
        raise ValueError("parent candidate snapshot is absent from its panel")
    HypothesisCandidate.from_dict(parent).validate_semantic_id()
    parent_hash = canonical_hash(parent)
    claimed_hash = panel["candidate_snapshot_hashes"].get(parent_id)
    if claimed_hash != parent_hash:
        raise ValueError(
            f"parent panel snapshot mismatch: claimed={claimed_hash} actual={parent_hash}"
        )
    scope_id = str(panel["selection_scope_id"])
    if parent_id not in panel.get("selected_candidate_ids", []):
        raise ValueError("parent candidate was not selected by its outcome-blind panel")

    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    treatment_rows = list(preflight["timestamp_verified_bundle_rows"])
    core_slots = load_core_slot_identities(WINDOW_ARTIFACTS)
    input_hashes = {
        "gate1_anchor_summary": _sha256_file(GATE1_ANCHOR),
        **{
            f"gate1_{window}_artifact": _sha256_file(path)
            for window, path in sorted(WINDOW_ARTIFACTS.items())
        },
        "core_slot_identity_projection": canonical_hash(core_slots),
    }
    allocations = allocate_comparators(
        treatment_rows,
        core_slots,
        allocator_input_hashes=input_hashes,
    )
    attachment = {
        "schema_version": 1,
        "record_type": "alpha_search_comparator_allocation_v1",
        "parent_candidate_id": parent_id,
        "parent_candidate_snapshot_hash": parent_hash,
        "created_at": declared_at,
        "data_cutoff": str(parent["created_at"]),
        "outcome_blind": True,
        "row_count": len(allocations),
        "rows": allocations,
    }
    _write_json(attachment_path, attachment)
    attachment_hash = _sha256_file(attachment_path)

    child_raw = json.loads(json.dumps(parent))
    child_raw["candidate_id"] = "cand-pending-semantic-hash"
    child_raw["created_at"] = declared_at
    child_raw["baseline"]["comparator_allocation_attachment"] = attachment_path.relative_to(
        REPO_ROOT
    ).as_posix()
    child_raw["baseline"]["comparator_allocation_attachment_hash"] = attachment_hash
    child_raw["next_machine_action"] = (
        "Revalidate the hash-bound 19-row comparator allocation on a fresh D0-D3 "
        "panel; if it passes, freeze promotion and reserve one research_pit private "
        "replay with observed_only ceiling and no paper/live changes."
    )
    child_raw["amendment_lineage"] = {
        "parent_candidate_id": parent_id,
        "parent_candidate_snapshot": parent,
        "parent_candidate_snapshot_hash": parent_hash,
        "parent_selection_scope_id": scope_id,
        "amendment_reason": "outcome_blind_contract_completion",
        "changed_fields": [
            "baseline.comparator_allocation_attachment",
            "baseline.comparator_allocation_attachment_hash",
            "next_machine_action",
        ],
        "parent_outcome_accessed": False,
        "parent_experiment_id": None,
        "declared_at": declared_at,
    }
    child = HypothesisCandidate.with_computed_id(child_raw).to_dict()
    _write_json(amended_candidate_path, child)
    return attachment, child


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the recurring-dividend bundle comparator amendment."
    )
    parser.add_argument(
        "--parent-candidate",
        default=str(
            REPO_ROOT
            / "data/alpha_search/dividend_recurring_bundle_candidate_raw_20260801.json"
        ),
    )
    parser.add_argument(
        "--parent-panel",
        default=str(REPO_ROOT / "data/alpha_search/dividend_recurring_bundle_panel_20260801.json"),
    )
    parser.add_argument(
        "--preflight",
        default=str(
            REPO_ROOT
            / "data/alpha_search/dividend_recurring_public_timestamp_preflight_20260801.json"
        ),
    )
    parser.add_argument(
        "--attachment-output",
        default=str(
            REPO_ROOT
            / "data/alpha_search/dividend_recurring_bundle_comparator_allocation_20260801.json"
        ),
    )
    parser.add_argument(
        "--candidate-output",
        default=str(
            REPO_ROOT
            / "data/alpha_search/dividend_recurring_bundle_candidate_amended_20260801.json"
        ),
    )
    parser.add_argument(
        "--declared-at",
        default=dt.datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    args = parser.parse_args(argv)
    attachment, child = build_contract_artifacts(
        parent_candidate_path=Path(args.parent_candidate),
        parent_panel_path=Path(args.parent_panel),
        preflight_path=Path(args.preflight),
        attachment_path=Path(args.attachment_output),
        amended_candidate_path=Path(args.candidate_output),
        declared_at=args.declared_at,
    )
    print(
        json.dumps(
            {
                "candidate_id": child["candidate_id"],
                "cash_rows": sum(
                    row["comparator_kind"] == "cash" for row in attachment["rows"]
                ),
                "core_slot_rows": sum(
                    row["comparator_kind"] == "core_slot"
                    for row in attachment["rows"]
                ),
                "row_count": attachment["row_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
