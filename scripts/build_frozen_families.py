"""Generate docs/frozen_families.jsonl from experiment logs (source of truth).

Builds the reservation-time novelty registry directly from canonical,
deduplicated experiment history. The human alpha playbook and stale meta-report
artifacts are not inputs. Pure read-only over experiment logs;
writes one JSONL row per trial-family. Advisory artifact; changes no strategy
behavior.

Usage:
    .\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py
"""

from __future__ import annotations

import io
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for import_root in (REPO_ROOT, SCRIPTS_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import experiment_fingerprint as fp

from quant.experiment_history import (
    _dedupe_records_by_experiment_id,
    decision_bucket,
    load_experiment_logs,
)

OUT_PATH = REPO_ROOT / "docs" / "frozen_families.jsonl"
PRIVATE_REPLAY_SCOUT_CHANGE_TYPE = "private_replay_scout"
PRIVATE_REPLAY_SCOUT_RECORD_TYPE = "v2_private_replay_scout_result"
PRIVATE_REPLAY_SCOUT_TERMINAL_STATUSES = {"observed_only", "rejected"}
_SCOUT_FAMILY_METADATA_FIELDS = (
    "trial_family",
    "mechanism_family",
)


def _load_json(path: Path) -> Any:
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


def _private_replay_scout_tickets(
    root: Path,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for record in records:
        if record.get("record_type") != PRIVATE_REPLAY_SCOUT_RECORD_TYPE:
            continue
        experiment_id = str(record.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError("private replay scout log is missing experiment_id")
        path = root / "experiments" / "tickets" / f"{experiment_id}.json"
        ticket = _load_json(path)
        if not isinstance(ticket, dict):
            raise ValueError(
                f"private replay scout ticket is missing or malformed: {path}"
            )
        if ticket.get("change_type") != PRIVATE_REPLAY_SCOUT_CHANGE_TYPE:
            raise ValueError(
                f"private replay scout ticket change_type mismatch: {path}"
            )
        ticket_experiment_id = str(ticket.get("experiment_id") or "").strip()
        if ticket_experiment_id != experiment_id:
            raise ValueError(f"private replay scout ticket identity mismatch: {path}")
        tickets.append(ticket)
    return tickets


def overlay_private_replay_scout_trial_metadata(
    records: list[dict[str, Any]],
    tickets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fill missing derived-history keys from the matching reservation ticket.

    Experiment log shards remain the outcome source of truth.  A private replay
    scout ticket freezes its family identity before outcomes, so these two
    accounting fields may safely fill an omission in the same-ID log.
    Existing log values are never replaced; disagreement fails closed.
    """

    scout_tickets: dict[str, dict[str, Any]] = {}
    for ticket in tickets:
        if not isinstance(ticket, dict):
            raise ValueError("private replay scout ticket input is malformed")
        experiment_id = str(ticket.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError("private replay scout ticket is missing experiment_id")
        if experiment_id in scout_tickets:
            raise ValueError(f"duplicate private replay scout ticket: {experiment_id}")
        scout_tickets[experiment_id] = ticket

    overlaid: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            overlaid.append(record)
            continue
        if record.get("record_type") != PRIVATE_REPLAY_SCOUT_RECORD_TYPE:
            overlaid.append(record)
            continue
        experiment_id = str(record.get("experiment_id") or "").strip()
        if not experiment_id:
            raise ValueError("private replay scout log is missing experiment_id")
        ticket = scout_tickets.get(experiment_id)
        if ticket is None:
            raise ValueError(
                f"private replay scout ticket is missing for {experiment_id}"
            )
        if ticket.get("change_type") != PRIVATE_REPLAY_SCOUT_CHANGE_TYPE:
            raise ValueError(
                f"private replay scout ticket change_type mismatch for {experiment_id}"
            )
        for field in _SCOUT_FAMILY_METADATA_FIELDS:
            if not str(ticket.get(field) or "").strip():
                raise ValueError(
                    f"private replay scout ticket is missing {field} for {experiment_id}"
                )
        log_status = str(record.get("status") or "").strip()
        ticket_status = str(ticket.get("status") or "").strip()
        if (
            log_status not in PRIVATE_REPLAY_SCOUT_TERMINAL_STATUSES
            or ticket_status != log_status
        ):
            raise ValueError(
                f"private replay scout terminal status mismatch for {experiment_id}"
            )
        result = ticket.get("result")
        if not isinstance(result, dict) or result.get("decision") != log_status:
            raise ValueError(
                f"private replay scout result decision mismatch for {experiment_id}"
            )
        if record.get("decision") != result.get("decision"):
            raise ValueError(
                f"private replay scout log decision mismatch for {experiment_id}"
            )
        if (
            not record.get("artifact")
            or record.get("artifact") != result.get("artifact")
            or not record.get("artifact_sha256")
            or record.get("artifact_sha256") != result.get("artifact_sha256")
        ):
            raise ValueError(
                f"private replay scout artifact binding mismatch for {experiment_id}"
            )
        merged = dict(record)
        for field in _SCOUT_FAMILY_METADATA_FIELDS:
            log_value = str(record.get(field) or "").strip()
            ticket_value = str(ticket.get(field) or "").strip()
            if log_value and ticket_value and log_value != ticket_value:
                raise ValueError(
                    f"private replay scout {field} mismatch for {experiment_id}"
                )
            if not log_value and ticket_value:
                merged[field] = ticket_value
        overlaid.append(merged)
    return overlaid


def _reopen_condition(rec: dict[str, Any]) -> str | None:
    refl = rec.get("post_run_reflection")
    if isinstance(refl, dict):
        for k in ("new_evidence_required", "new_evidence_needed"):
            if refl.get(k):
                return str(refl[k])[:400]
    for k in ("next_evidence_needed", "new_evidence_required", "next_retry_requires"):
        if rec.get(k):
            return str(rec[k])[:400]
    return None


def _realized_failure_mode(rec: dict[str, Any]) -> str | None:
    """Return the canonical realized failure label when a record declares one.

    Closeout records have used three locations over time.  Reading all of them
    keeps the guard compatible with both the flat experiment log and the
    nested ticket/result representation without treating an absent label as a
    duplicate.
    """

    candidates: list[Any] = [rec.get("realized_failure_mode")]
    for mapping in (
        rec.get("post_run_reflection"),
        rec.get("calibration"),
        (rec.get("result") or {}).get("calibration")
        if isinstance(rec.get("result"), dict)
        else None,
    ):
        if isinstance(mapping, dict):
            candidates.append(mapping.get("realized_failure_mode"))
    normalized = [
        str(value).strip().lower().replace("-", "_").replace(" ", "_")
        for value in candidates
        if value is not None and str(value).strip()
    ]
    # Duplicate accounting is an ownership fact.  Prefer it if a legacy copy
    # also carries a stale generic label such as ``none``.
    if "duplicate_reservation_accounting" in normalized:
        return "duplicate_reservation_accounting"
    return normalized[0] if normalized else None


def _is_duplicate_reservation_accounting(rec: dict[str, Any]) -> bool:
    return _realized_failure_mode(rec) == "duplicate_reservation_accounting"


def build_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate substantive experiment records into frozen-family rows.

    ``duplicate_reservation_accounting`` is bookkeeping for an already-owned
    trial, not another test of the mechanism.  Counting it would inflate the
    denominator and, when its ID is later, replace the owner's quantitative
    reopen contract with duplicate-closeout text.
    """

    families: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trials": 0, "accepted": 0, "rejected": 0, "blocked": 0, "lead": 0, "exps": [], "latest": None}
    )
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if _is_duplicate_reservation_accounting(rec):
            continue
        family = str(rec.get("trial_family") or rec.get("mechanism_family") or "").strip()
        if not family:
            continue
        bucket = decision_bucket(rec)
        agg = families[family]
        agg["trials"] += 1
        agg[bucket] = agg.get(bucket, 0) + 1
        eid = rec.get("experiment_id")
        if eid:
            agg["exps"].append(str(eid))
        # keep the lexicographically-latest experiment id's record for reopen text
        if agg["latest"] is None or (eid and str(eid) > str(agg["latest"].get("experiment_id", ""))):
            agg["latest"] = rec

    rows: list[dict[str, Any]] = []
    for family, agg in sorted(families.items()):
        trials = agg["trials"]
        accepted = agg["accepted"]
        rejected = agg["rejected"]
        accept_rate = round(accepted / trials, 4) if trials else 0.0
        if trials >= 3 and accept_rate <= 0.2:
            status = "frozen"
        elif accepted == 0 and (rejected + agg.get("blocked", 0)) >= 2:
            status = "frozen_rejected"
        elif accepted > 0:
            status = "has_accepted"
        elif trials == 1 and accepted == 0:
            status = "single_attempt"
        else:
            status = "active"
        latest = agg["latest"] or {}
        fingerprint = fp.infer_fingerprint(
            family,
            latest.get("changed_variable") or "",
            latest.get("trial_variant_id") or "",
        )
        rows.append(
            {
                "family_key": family,
                "status": status,
                "trials": trials,
                "accepted": accepted,
                "rejected": rejected,
                "blocked": agg.get("blocked", 0),
                "leads": agg.get("lead", 0),
                "accept_rate": accept_rate,
                "representative_exps": sorted(set(agg["exps"]))[-4:],
                "reopen_condition": _reopen_condition(latest),
                "fingerprint": fingerprint,
            }
        )

    return rows


def main() -> int:
    records = _dedupe_records_by_experiment_id(load_experiment_logs(REPO_ROOT))
    records = overlay_private_replay_scout_trial_metadata(
        records,
        _private_replay_scout_tickets(REPO_ROOT, records),
    )
    rows = build_rows(records)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT_PATH, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    frozen = sum(1 for r in rows if r["status"] in ("frozen", "frozen_rejected"))
    has_acc = sum(1 for r in rows if r["status"] == "has_accepted")
    print(f"wrote {len(rows)} families to {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  frozen/frozen_rejected: {frozen} | has_accepted: {has_acc}")
    print("  top frozen-rejected families by trials:")
    for r in sorted([r for r in rows if r["status"] == "frozen_rejected"], key=lambda x: -x["trials"])[:8]:
        print(f"    {r['trials']:>2} trials  {r['family_key']}  ({r['fingerprint']['data_source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
