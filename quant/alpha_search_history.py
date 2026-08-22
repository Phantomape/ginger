"""Canonical, time-anchored research history for outcome-blind discovery.

The experiment registry remains the source of truth.  This module only turns
its frozen-family view (and, optionally, discovery ledgers/open tickets) into a
stable snapshot that can be bound into a Phase-1 selection scope.  It never
reads candidate outcomes and never reserves an experiment.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .alpha_search_contract import (
    canonical_hash,
    normalize_hypothesis_candidate,
    validate_candidate_semantic_id,
)

try:
    from scripts.experiment_fingerprint import (
        WARN_THRESHOLD,
        canonical_data_source,
        distance,
        infer_fingerprint,
    )
except ImportError:  # pragma: no cover - direct quant/ test import fallback.
    from experiment_fingerprint import (  # type: ignore
        WARN_THRESHOLD,
        canonical_data_source,
        distance,
        infer_fingerprint,
    )


SCHEMA_VERSION = 1
SNAPSHOT_VERSION = "alpha_search_historical_prior_v2"
CANONICAL_FROZEN_LOCATOR = "docs/frozen_families.jsonl"
CANONICAL_ANCHOR_KIND = "canonical_experiment_history_asof_projection"
FIXTURE_ANCHOR_KIND = "isolated_frozen_families_asof_projection"
DISCOVERY_ANCHOR_KIND = "discovery_ledger_asof_projection"
TICKET_ANCHOR_KIND = "open_ticket_asof_projection"

# Rich discovery registries use transport/storage identities, while the
# experiment novelty registry historically split some of them by mechanism.
# Project to every compatible legacy bucket so a rename cannot bypass D3.
_LEGACY_SOURCE_PROJECTIONS: dict[str, tuple[str, ...]] = {
    "ohlcv_warehouse": ("ohlcv_relation", "ohlcv_momentum"),
    "sec_official_event": ("sec_text_event",),
}


class HistoricalPriorError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _clock(value: Any, *, path: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise HistoricalPriorError("invalid_historical_cutoff", f"{path} is required")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HistoricalPriorError("invalid_historical_cutoff", f"{path}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalPriorError("invalid_historical_cutoff", f"{path} requires timezone")
    return parsed.astimezone(timezone.utc)


def _clock_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normal_locator(path: Path, *, repo_root: Path | None = None) -> str:
    resolved = path.resolve()
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        # Test/external sources still get a deterministic caller-provided path
        # spelling; the content hash, not the local absolute path, is identity.
        return path.as_posix()


def _exp_day(experiment_id: Any) -> date | None:
    match = re.search(r"exp-(20\d{6})-\d+", str(experiment_id or ""))
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _known_by(experiment_id: str, cutoff: datetime) -> bool:
    day = _exp_day(experiment_id)
    if day is None:
        return False
    # Experiment IDs have day resolution only.  Treat the row as known at the
    # end of that UTC day; this intentionally excludes same-day ambiguity.
    known_at = datetime.combine(day, time.max, tzinfo=timezone.utc)
    return known_at <= cutoff


def _normal_tags(values: Iterable[Any]) -> list[str]:
    return sorted(
        {
            re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
            for value in values
            if str(value or "").strip()
        }
    )


def _normal_mechanism(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def canonical_legacy_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    row = {
        "data_source": canonical_data_source(value.get("data_source")),
        "field_tags": _normal_tags(value.get("field_tags") or []),
        "gate_shape": re.sub(
            r"[^a-z0-9]+", "_", str(value.get("gate_shape") or "other").lower()
        ).strip("_") or "other",
    }
    # Optional passthrough: discovery-origin records keep the rich economic
    # mechanism so D3 can distinguish a genuinely different mechanism on the
    # same data source from a near-neighbor retry. Absent on legacy records,
    # and never synthesized here, so historical snapshots stay canonical.
    mechanism = _normal_mechanism(value.get("economic_mechanism"))
    if mechanism:
        row["economic_mechanism"] = mechanism
    return row


def _anchor(
    *, kind: str, locator: str, projection_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    # The anchor commits only to rows knowable at history_cutoff.  Hashing the
    # mutable source file would make an old cutoff drift when a future row is
    # appended even though no old evidence changed.
    content_hash = canonical_hash(list(projection_rows))
    anchor_id = canonical_hash(
        {"kind": kind, "locator": locator, "sha256": content_hash}
    )
    return {
        "anchor_id": anchor_id,
        "kind": kind,
        "locator": locator,
        "sha256": content_hash,
        "row_count": len(projection_rows),
    }


def _record_identity(record: Mapping[str, Any]) -> dict[str, Any]:
    identity = {
        "origin": str(record.get("origin") or ""),
        "known_at": str(record.get("known_at") or ""),
        "family_key": str(record.get("family_key") or ""),
        "fingerprint": record.get("fingerprint"),
        "representative_exps": list(record.get("representative_exps") or []),
        "historical_status": str(record.get("historical_status") or ""),
        "reopen_condition": record.get("reopen_condition"),
    }
    if record.get("candidate_metadata") is not None:
        identity["candidate_metadata"] = record["candidate_metadata"]
    return identity


def _history_record(
    *,
    origin: str,
    source_anchor_id: str,
    known_at: datetime,
    family_key: str,
    fingerprint: Mapping[str, Any],
    representative_exps: Iterable[str] = (),
    historical_status: str = "historical",
    reopen_condition: Any = None,
    candidate_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "origin": origin,
        "source_anchor_id": source_anchor_id,
        "known_at": _clock_text(known_at),
        "family_key": str(family_key).strip(),
        "fingerprint": canonical_legacy_fingerprint(fingerprint),
        "representative_exps": sorted(set(str(value) for value in representative_exps)),
        "historical_status": str(historical_status or "historical"),
        "reopen_condition": reopen_condition,
    }
    if candidate_metadata is not None:
        record["candidate_metadata"] = dict(candidate_metadata)
    record["record_id"] = canonical_hash(_record_identity(record))
    return record


def _draft_record(
    *,
    origin: str,
    known_at: datetime,
    family_key: str,
    fingerprint: Mapping[str, Any],
    representative_exps: Iterable[str] = (),
    historical_status: str = "historical",
    reopen_condition: Any = None,
    candidate_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "origin": origin,
        "known_at": _clock_text(known_at),
        "family_key": str(family_key).strip(),
        "fingerprint": canonical_legacy_fingerprint(fingerprint),
        "representative_exps": sorted(set(str(value) for value in representative_exps)),
        "historical_status": str(historical_status or "historical"),
        "reopen_condition": reopen_condition,
    }
    if candidate_metadata is not None:
        record["candidate_metadata"] = dict(candidate_metadata)
    return record


def _bind_projection(
    drafts: Sequence[Mapping[str, Any]],
    *,
    kind: str,
    locator: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    projection_by_hash = {
        canonical_hash(dict(draft)): dict(draft) for draft in drafts
    }
    projection = [projection_by_hash[digest] for digest in sorted(projection_by_hash)]
    anchor = _anchor(kind=kind, locator=locator, projection_rows=projection)
    records = [
        _history_record(
            origin=str(draft["origin"]),
            source_anchor_id=anchor["anchor_id"],
            known_at=_clock(draft["known_at"], path="projection.known_at"),
            family_key=str(draft["family_key"]),
            fingerprint=draft["fingerprint"],
            representative_exps=draft["representative_exps"],
            historical_status=str(draft["historical_status"]),
            reopen_condition=draft["reopen_condition"],
            candidate_metadata=draft.get("candidate_metadata"),
        )
        for draft in projection
    ]
    return anchor, records


def _record_clock(record: Mapping[str, Any]) -> datetime | None:
    for key in ("timestamp", "completed_at", "closed_at", "created_at", "reserved_at"):
        if not record.get(key):
            continue
        try:
            return _clock(record[key], path=f"experiment.{key}")
        except HistoricalPriorError:
            continue
    day = _exp_day(record.get("experiment_id") or record.get("id"))
    return datetime.combine(day, time.max, tzinfo=timezone.utc) if day else None


def _decision_bucket(record: Mapping[str, Any]) -> str:
    if record.get("accepted") is True or record.get("accepted_alpha") is True:
        return "accepted"
    status = str(record.get("status") or "").lower()
    decision = str(record.get("decision") or "").lower()
    if status.startswith("accept") or decision.startswith("accept"):
        return "accepted"
    if "positive_replay_lead" in decision:
        return "lead"
    if status.startswith("block") or "blocked" in decision:
        return "blocked"
    return "rejected"


def _reopen_condition(record: Mapping[str, Any]) -> Any:
    reflection = record.get("post_run_reflection")
    if isinstance(reflection, Mapping):
        for key in ("new_evidence_required", "new_evidence_needed"):
            if reflection.get(key):
                return reflection[key]
    for key in ("next_evidence_needed", "new_evidence_required", "next_retry_requires"):
        if record.get(key):
            return record[key]
    return None


def _canonical_experiment_rows(repo_root: Path, cutoff: datetime) -> list[dict[str, Any]]:
    logs_dir = repo_root / "experiments" / "logs"
    if not logs_dir.is_dir():
        raise HistoricalPriorError(
            "canonical_history_source_missing", str(logs_dir)
        )
    by_id: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for path in sorted(logs_dir.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HistoricalPriorError(
                "invalid_historical_source", f"{path}: {exc}"
            ) from exc
        if not isinstance(value, Mapping):
            continue
        known_at = _record_clock(value)
        if known_at is None or known_at > cutoff:
            continue
        experiment_id = str(value.get("experiment_id") or value.get("id") or path.stem)
        row = dict(value)
        row["experiment_id"] = experiment_id
        current = by_id.get(experiment_id)
        if current is None or len(json.dumps(row, sort_keys=True, default=str)) > len(
            json.dumps(current[1], sort_keys=True, default=str)
        ):
            by_id[experiment_id] = (known_at, row)
    return [
        {**row, "_history_known_at": _clock_text(known_at)}
        for experiment_id, (known_at, row) in sorted(by_id.items())
    ]


def _canonical_frozen_drafts(repo_root: Path, cutoff: datetime) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in _canonical_experiment_rows(repo_root, cutoff):
        family = str(record.get("trial_family") or record.get("mechanism_family") or "").strip()
        if family:
            groups.setdefault(family, []).append(record)
    drafts: list[dict[str, Any]] = []
    for family, rows in sorted(groups.items()):
        rows.sort(
            key=lambda row: (
                str(row.get("_history_known_at") or ""),
                str(row.get("experiment_id") or ""),
            )
        )
        latest = rows[-1]
        buckets = [_decision_bucket(row) for row in rows]
        accepted = buckets.count("accepted")
        rejected_or_blocked = buckets.count("rejected") + buckets.count("blocked")
        if len(rows) >= 3 and accepted / len(rows) <= 0.2:
            status = "frozen"
        elif accepted == 0 and rejected_or_blocked >= 2:
            status = "frozen_rejected"
        elif accepted > 0:
            status = "has_accepted"
        elif len(rows) == 1:
            status = "single_attempt"
        else:
            status = "active"
        fingerprint = infer_fingerprint(
            family,
            str(latest.get("changed_variable") or latest.get("single_causal_variable") or ""),
            str(latest.get("trial_variant_id") or ""),
        )
        representatives = sorted(
            {str(row.get("experiment_id") or "") for row in rows if row.get("experiment_id")}
        )[-4:]
        drafts.append(
            _draft_record(
                origin="frozen_family",
                known_at=_clock(latest["_history_known_at"], path="experiment.known_at"),
                family_key=family,
                fingerprint=fingerprint,
                representative_exps=representatives,
                historical_status=status,
                reopen_condition=_reopen_condition(latest),
            )
        )
    return drafts


def _fixture_frozen_drafts(path: Path, cutoff: datetime) -> list[dict[str, Any]]:
    _, rows = _jsonl_rows(path)
    drafts: list[dict[str, Any]] = []
    for row in rows:
        representatives = sorted(
            {str(value) for value in row.get("representative_exps") or []}
        )
        # Aggregate fields may have been computed from the latest member.  A
        # row spanning beyond cutoff cannot be safely sliced, so exclude the
        # entire row instead of leaking its future fingerprint/status/reopen.
        if not representatives or any(not _known_by(value, cutoff) for value in representatives):
            continue
        raw_fingerprint = row.get("fingerprint")
        if not isinstance(raw_fingerprint, Mapping):
            continue
        known_days = [_exp_day(value) for value in representatives]
        latest_day = max(day for day in known_days if day is not None)
        drafts.append(
            _draft_record(
                origin="frozen_family",
                known_at=datetime.combine(latest_day, time.max, tzinfo=timezone.utc),
                family_key=str(row.get("family_key") or ""),
                fingerprint=raw_fingerprint,
                representative_exps=representatives,
                historical_status=str(row.get("status") or "historical"),
                reopen_condition=row.get("reopen_condition"),
            )
        )
    return drafts


def _frozen_records(
    path: Path,
    cutoff: datetime,
    *,
    repo_root: Path,
    isolated_fixture: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    canonical_path = (repo_root / CANONICAL_FROZEN_LOCATOR).resolve()
    if not isolated_fixture and path.resolve() != canonical_path:
        raise HistoricalPriorError(
            "canonical_history_source_required",
            f"expected {canonical_path}, got {path.resolve()}",
        )
    if isolated_fixture:
        drafts = _fixture_frozen_drafts(path, cutoff)
        kind = FIXTURE_ANCHOR_KIND
    else:
        # docs/frozen_families.jsonl is the public anti-repeat view, while the
        # immutable per-experiment rows are what make the cutoff reconstruction
        # honest and append-stable.
        if not canonical_path.is_file():
            raise HistoricalPriorError("canonical_history_source_missing", str(canonical_path))
        drafts = _canonical_frozen_drafts(repo_root, cutoff)
        kind = CANONICAL_ANCHOR_KIND
    return _bind_projection(
        drafts,
        kind=kind,
        locator=_normal_locator(path, repo_root=repo_root),
    )


def _jsonl_rows(path: Path) -> tuple[bytes, list[Mapping[str, Any]]]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise HistoricalPriorError("historical_source_read_failed", f"{path}: {exc}") from exc
    rows: list[Mapping[str, Any]] = []
    for line_number, raw_line in enumerate(payload.decode("utf-8-sig").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise HistoricalPriorError(
                "invalid_historical_source", f"{path}:{line_number}: {exc.msg}"
            ) from exc
        if not isinstance(row, Mapping):
            raise HistoricalPriorError(
                "invalid_historical_source", f"{path}:{line_number}: expected object"
            )
        rows.append(row)
    return payload, rows


def _discovery_records(
    path: Path, cutoff: datetime, *, repo_root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _, rows = _jsonl_rows(path)
    drafts: list[dict[str, Any]] = []
    for event in rows:
        if str(event.get("record_type") or "") != "candidate_snapshot":
            continue
        candidate = event.get("payload") or event.get("candidate")
        if not isinstance(candidate, Mapping):
            continue
        raw_known_at = event.get("recorded_at") or candidate.get("created_at")
        try:
            known_at = _clock(raw_known_at, path="discovery_candidate.known_at")
        except HistoricalPriorError:
            continue
        if known_at > cutoff:
            continue
        family_key = str(candidate.get("candidate_id") or candidate.get("title") or "")
        candidate_metadata: dict[str, Any] | None = None
        try:
            normalised = normalize_hypothesis_candidate(candidate)
            validate_candidate_semantic_id(normalised)
            identity = event.get("identity")
            selection_scope_id = (
                str(identity.get("selection_scope_id") or "")
                if isinstance(identity, Mapping)
                else ""
            )
            lineage = normalised.get("amendment_lineage")
            candidate_metadata = {
                "candidate_id": str(normalised["candidate_id"]),
                "candidate_snapshot_hash": canonical_hash(normalised),
                "selection_scope_id": selection_scope_id,
                "amendment_parent_candidate_id": (
                    str(lineage.get("parent_candidate_id"))
                    if isinstance(lineage, Mapping)
                    else None
                ),
                "amendment_reason": (
                    str(lineage.get("amendment_reason"))
                    if isinstance(lineage, Mapping)
                    else None
                ),
            }
        except Exception:
            # Invalid legacy events still remain anti-repeat evidence, but they
            # cannot authenticate a parent/child amendment relationship.
            candidate_metadata = None
        rich = candidate.get("fingerprint")
        mechanism = (
            _normal_mechanism(rich.get("economic_mechanism"))
            if isinstance(rich, Mapping)
            else ""
        )
        for fingerprint in candidate_legacy_fingerprints(candidate):
            if mechanism:
                fingerprint = {**fingerprint, "economic_mechanism": mechanism}
            drafts.append(
                _draft_record(
                    origin="discovery_candidate",
                    known_at=known_at,
                    family_key=family_key,
                    fingerprint=fingerprint,
                    historical_status="discovery_snapshot",
                    reopen_condition=candidate.get("reopen_condition"),
                    candidate_metadata=candidate_metadata,
                )
            )
    return _bind_projection(
        drafts,
        kind=DISCOVERY_ANCHOR_KIND,
        locator=_normal_locator(path, repo_root=repo_root),
    )


def _open_ticket_window() -> timedelta:
    """Staleness window for open-ticket discovery records.

    Mirrors the reserve-time in-flight duplicate guard's rolling window
    (GINGER_IN_FLIGHT_WINDOW_DAYS, default 7): a proposed/claimed ticket older
    than the window is stale coordination state, not in-flight work, and must
    not freeze later discovery (exp-20260728-005).
    """
    raw = os.environ.get("GINGER_IN_FLIGHT_WINDOW_DAYS", "")
    try:
        days = float(raw) if raw.strip() else 7.0
    except ValueError:
        days = 7.0
    return timedelta(days=max(days, 0.0))


def _ticket_drafts(
    path: Path,
    cutoff: datetime,
    *,
    closed_experiment_ids: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    try:
        payload = path.read_bytes()
        value = json.loads(payload.decode("utf-8-sig"))
    except OSError as exc:
        raise HistoricalPriorError("historical_source_read_failed", f"{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise HistoricalPriorError("invalid_historical_source", f"{path}: {exc.msg}") from exc
    tickets = value if isinstance(value, list) else [value]
    if any(not isinstance(ticket, Mapping) for ticket in tickets):
        raise HistoricalPriorError("invalid_historical_source", f"{path}: ticket must be object")
    drafts: list[dict[str, Any]] = []
    for ticket in tickets:
        experiment_id = str(ticket.get("experiment_id") or ticket.get("id") or "")
        # Many legacy ticket files were never backfilled with completed_at even
        # though their immutable closeout shard exists.  A closeout known by
        # the cutoff is authoritative evidence that the reservation was no
        # longer in flight; otherwise hundreds of closed trials would be
        # mislabeled open_asof and over-block future discovery.
        if experiment_id and experiment_id in closed_experiment_ids:
            continue
        # An open ticket freezes discovery only while it plausibly represents
        # in-flight work. AGENTS.md section 7 already scopes in-flight
        # duplicate interception to a rolling window (default 7 days) and
        # exempts stale proposed tickets; apply the same published calibration
        # here so a months-old never-closed scout ticket cannot hard-reject
        # every later candidate that shares its source bucket
        # (exp-20260728-005: 92-day-old 2026-04-26 shadow-entry tickets).
        # Measurement-repair reservations are guard/plumbing work, not alpha
        # families, and never define a discovery near-neighbor.
        if str(ticket.get("lane") or "") == "measurement_repair":
            continue
        known_at: datetime | None = None
        # Only reservation-time fields are admissible.  Current status/result
        # may have been written after cutoff and must never leak backwards.
        for raw_clock in (ticket.get("created_at"), ticket.get("reserved_at")):
            if raw_clock:
                try:
                    known_at = _clock(raw_clock, path="ticket.known_at")
                except HistoricalPriorError:
                    known_at = None
                if known_at is not None:
                    break
        if known_at is None:
            day = _exp_day(experiment_id)
            if day is not None:
                known_at = datetime.combine(day, time.max, tzinfo=timezone.utc)
        if known_at is None or known_at > cutoff:
            continue
        if known_at < cutoff - _open_ticket_window():
            continue
        completed_at: datetime | None = None
        if ticket.get("completed_at"):
            try:
                completed_at = _clock(ticket["completed_at"], path="ticket.completed_at")
            except HistoricalPriorError:
                completed_at = None
        if completed_at is not None and completed_at <= cutoff:
            continue
        inferred = infer_fingerprint(
            str(ticket.get("hypothesis") or ""),
            str(ticket.get("trial_family") or ""),
            str(ticket.get("changed_variable") or ticket.get("single_causal_variable") or ""),
        )
        drafts.append(
            _draft_record(
                origin="open_ticket",
                known_at=known_at,
                family_key=str(ticket.get("trial_family") or experiment_id),
                fingerprint=inferred,
                representative_exps=[experiment_id] if experiment_id else [],
                historical_status="open_asof",
                reopen_condition=None,
            )
        )
    return drafts


def _ticket_records(
    path: Path,
    cutoff: datetime,
    *,
    repo_root: Path,
    closed_experiment_ids: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if path.is_dir():
        drafts = [
            draft
            for ticket_path in sorted(path.glob("*.json"))
            for draft in _ticket_drafts(
                ticket_path,
                cutoff,
                closed_experiment_ids=closed_experiment_ids,
            )
        ]
    else:
        drafts = _ticket_drafts(
            path,
            cutoff,
            closed_experiment_ids=closed_experiment_ids,
        )
    return _bind_projection(
        drafts,
        kind=TICKET_ANCHOR_KIND,
        locator=_normal_locator(path, repo_root=repo_root),
    )


def _snapshot_hash(value: Mapping[str, Any]) -> str:
    clean = dict(value)
    clean.pop("snapshot_hash", None)
    return canonical_hash(clean)


def build_historical_prior_snapshot(
    frozen_families: str | Path,
    *,
    history_cutoff: str,
    discovery_ledgers: Sequence[str | Path] = (),
    open_tickets: Sequence[str | Path] = (),
    repo_root: str | Path | None = None,
    isolated_fixture: bool = False,
) -> dict[str, Any]:
    """Build the canonical prior snapshot used by a new discovery scope."""
    cutoff = _clock(history_cutoff, path="history_cutoff")
    root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    anchor, records = _frozen_records(
        Path(frozen_families),
        cutoff,
        repo_root=root,
        isolated_fixture=isolated_fixture,
    )
    anchors = [anchor]
    closed_experiment_ids = frozenset(
        str(row.get("experiment_id") or "")
        for row in _canonical_experiment_rows(root, cutoff)
        if row.get("experiment_id")
    )
    discovery_paths = [Path(path) for path in discovery_ledgers]
    ticket_paths = [Path(path) for path in open_tickets]
    if not isolated_fixture:
        canonical_discovery = root / "data" / "alpha_search" / "events.jsonl"
        if canonical_discovery.is_file():
            discovery_paths.insert(0, canonical_discovery)
        tickets_dir = root / "experiments" / "tickets"
        if tickets_dir.is_dir():
            ticket_paths.insert(0, tickets_dir)
    discovery_paths = list(dict.fromkeys(path.resolve() for path in discovery_paths))
    ticket_paths = list(dict.fromkeys(path.resolve() for path in ticket_paths))
    for path in discovery_paths:
        extra_anchor, extra_records = _discovery_records(
            Path(path), cutoff, repo_root=root
        )
        if extra_records:
            anchors.append(extra_anchor)
            records.extend(extra_records)
    for path in ticket_paths:
        extra_anchor, extra_records = _ticket_records(
            Path(path),
            cutoff,
            repo_root=root,
            closed_experiment_ids=closed_experiment_ids,
        )
        if extra_records:
            anchors.append(extra_anchor)
            records.extend(extra_records)
    by_id = {str(record["record_id"]): record for record in records}
    records = list(by_id.values())
    records.sort(key=lambda row: (row["record_id"], row["known_at"]))
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_version": SNAPSHOT_VERSION,
        "history_cutoff": _clock_text(cutoff),
        "source_anchors": sorted(anchors, key=lambda item: str(item["anchor_id"])),
        "record_count": len(records),
        "records": records,
    }
    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return validate_historical_prior_snapshot(snapshot)


def _resolve_repo_locator(repo_root: Path, locator: str) -> Path:
    candidate = (repo_root / locator).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise HistoricalPriorError(
            "noncanonical_historical_source", f"outside repository: {locator}"
        ) from exc
    return candidate


def validate_repository_historical_snapshot(
    value: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Recompute every repository anchor at the saved cutoff and compare.

    Later experiment rows are read but excluded by the saved cutoff, so a
    previously saved snapshot remains verifiable without learning new outcome
    fields or changing its hash.
    """
    row = require_nonempty_snapshot(value)
    root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    anchors = row["source_anchors"]
    canonical = [
        anchor
        for anchor in anchors
        if anchor.get("kind") == CANONICAL_ANCHOR_KIND
        and anchor.get("locator") == CANONICAL_FROZEN_LOCATOR
    ]
    if len(canonical) != 1:
        raise HistoricalPriorError(
            "canonical_history_anchor_required",
            f"expected one {CANONICAL_FROZEN_LOCATOR} projection anchor",
        )
    discovery_paths: list[Path] = []
    ticket_paths: list[Path] = []
    for anchor in anchors:
        kind = str(anchor.get("kind") or "")
        if kind == CANONICAL_ANCHOR_KIND:
            continue
        locator = str(anchor.get("locator") or "")
        if kind == DISCOVERY_ANCHOR_KIND:
            discovery_paths.append(_resolve_repo_locator(root, locator))
        elif kind == TICKET_ANCHOR_KIND:
            ticket_paths.append(_resolve_repo_locator(root, locator))
        else:
            raise HistoricalPriorError(
                "noncanonical_historical_source", f"unsupported anchor kind: {kind}"
            )
    expected = build_historical_prior_snapshot(
        root / CANONICAL_FROZEN_LOCATOR,
        history_cutoff=row["history_cutoff"],
        discovery_ledgers=discovery_paths,
        open_tickets=ticket_paths,
        repo_root=root,
        isolated_fixture=False,
    )
    if row != expected:
        raise HistoricalPriorError(
            "repository_historical_snapshot_mismatch",
            "snapshot path/hash/records do not match canonical as-of history",
        )
    return row


def validate_historical_prior_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise HistoricalPriorError("historical_snapshot_required", "expected snapshot object")
    required = {
        "schema_version",
        "snapshot_version",
        "history_cutoff",
        "source_anchors",
        "record_count",
        "records",
        "snapshot_hash",
    }
    if set(value) != required:
        raise HistoricalPriorError(
            "invalid_historical_snapshot",
            f"missing={sorted(required - set(value))} unknown={sorted(set(value) - required)}",
        )
    row = json.loads(json.dumps(value, ensure_ascii=False))
    if row["schema_version"] != SCHEMA_VERSION or row["snapshot_version"] != SNAPSHOT_VERSION:
        raise HistoricalPriorError("invalid_historical_snapshot", "unsupported version")
    row["history_cutoff"] = _clock_text(_clock(row["history_cutoff"], path="history_cutoff"))
    anchors = row["source_anchors"]
    if not isinstance(anchors, list) or not anchors:
        raise HistoricalPriorError("invalid_historical_snapshot", "source_anchors required")
    for anchor in anchors:
        if not isinstance(anchor, Mapping) or set(anchor) != {
            "anchor_id", "kind", "locator", "sha256", "row_count"
        }:
            raise HistoricalPriorError("invalid_historical_snapshot", "invalid source anchor")
        if not re.fullmatch(r"[0-9a-f]{64}", str(anchor.get("anchor_id") or "")):
            raise HistoricalPriorError("invalid_historical_snapshot", "invalid anchor_id")
        if not re.fullmatch(r"[0-9a-f]{64}", str(anchor.get("sha256") or "")):
            raise HistoricalPriorError("invalid_historical_snapshot", "invalid source sha256")
        if not isinstance(anchor.get("row_count"), int) or anchor["row_count"] < 0:
            raise HistoricalPriorError("invalid_historical_snapshot", "invalid source row_count")
        expected_anchor_id = canonical_hash(
            {
                "kind": anchor["kind"],
                "locator": anchor["locator"],
                "sha256": anchor["sha256"],
            }
        )
        if anchor["anchor_id"] != expected_anchor_id:
            raise HistoricalPriorError("invalid_historical_snapshot", "anchor identity mismatch")
    if anchors != sorted(anchors, key=lambda item: str(item["anchor_id"])):
        raise HistoricalPriorError("invalid_historical_snapshot", "source anchors not canonical")
    anchor_ids = {str(anchor["anchor_id"]) for anchor in anchors}
    records = row["records"]
    if not isinstance(records, list) or any(not isinstance(record, Mapping) for record in records):
        raise HistoricalPriorError("invalid_historical_snapshot", "records must be objects")
    if row["record_count"] != len(records):
        raise HistoricalPriorError("invalid_historical_snapshot", "record_count mismatch")
    if records != sorted(records, key=lambda item: (str(item["record_id"]), str(item["known_at"]))):
        raise HistoricalPriorError("invalid_historical_snapshot", "records not canonical")
    cutoff = _clock(row["history_cutoff"], path="history_cutoff")
    seen: set[str] = set()
    for record in records:
        required_record = {
            "record_id", "origin", "source_anchor_id", "known_at", "family_key",
            "fingerprint", "representative_exps", "historical_status", "reopen_condition",
        }
        allowed_record = required_record | {"candidate_metadata"}
        if not required_record.issubset(record) or not set(record).issubset(allowed_record):
            raise HistoricalPriorError("invalid_historical_snapshot", "invalid record shape")
        record_id = str(record["record_id"])
        if not re.fullmatch(r"[0-9a-f]{64}", record_id) or record_id in seen:
            raise HistoricalPriorError("invalid_historical_snapshot", "invalid/duplicate record_id")
        seen.add(record_id)
        if record["source_anchor_id"] not in anchor_ids:
            raise HistoricalPriorError("invalid_historical_snapshot", "unbound source anchor")
        if _clock(record["known_at"], path=f"record[{record_id}].known_at") > cutoff:
            raise HistoricalPriorError("historical_snapshot_after_cutoff", record_id)
        fingerprint = record.get("fingerprint")
        if not isinstance(fingerprint, Mapping) or canonical_legacy_fingerprint(fingerprint) != fingerprint:
            raise HistoricalPriorError("invalid_historical_snapshot", "noncanonical fingerprint")
        reps = record.get("representative_exps")
        if not isinstance(reps, list) or reps != sorted(set(str(item) for item in reps)):
            raise HistoricalPriorError("invalid_historical_snapshot", "noncanonical representatives")
        metadata = record.get("candidate_metadata")
        if metadata is not None:
            metadata_fields = {
                "candidate_id",
                "candidate_snapshot_hash",
                "selection_scope_id",
                "amendment_parent_candidate_id",
                "amendment_reason",
            }
            if not isinstance(metadata, Mapping) or set(metadata) != metadata_fields:
                raise HistoricalPriorError(
                    "invalid_historical_snapshot", "invalid candidate metadata"
                )
            if not re.fullmatch(r"cand-[0-9a-f]{20}", str(metadata["candidate_id"])):
                raise HistoricalPriorError(
                    "invalid_historical_snapshot", "invalid candidate metadata id"
                )
            if not re.fullmatch(
                r"[0-9a-f]{64}", str(metadata["candidate_snapshot_hash"])
            ):
                raise HistoricalPriorError(
                    "invalid_historical_snapshot", "invalid candidate snapshot hash"
                )
            scope_id = str(metadata["selection_scope_id"] or "")
            if scope_id and not re.fullmatch(r"scope-[0-9a-f]{24}", scope_id):
                raise HistoricalPriorError(
                    "invalid_historical_snapshot", "invalid candidate selection scope"
                )
            parent_id = metadata["amendment_parent_candidate_id"]
            reason = metadata["amendment_reason"]
            if (parent_id is None) != (reason is None):
                raise HistoricalPriorError(
                    "invalid_historical_snapshot", "incomplete amendment metadata"
                )
            if parent_id is not None and not re.fullmatch(
                r"cand-[0-9a-f]{20}", str(parent_id)
            ):
                raise HistoricalPriorError(
                    "invalid_historical_snapshot", "invalid amendment parent id"
                )
        if record_id != canonical_hash(_record_identity(record)):
            raise HistoricalPriorError("invalid_historical_snapshot", "record identity mismatch")
    for anchor in anchors:
        bound_projection = sorted(
            (
                {
                    key: value
                    for key, value in record.items()
                    if key not in {"record_id", "source_anchor_id"}
                }
                for record in records
                if record["source_anchor_id"] == anchor["anchor_id"]
            ),
            key=lambda projection: canonical_hash(projection),
        )
        if anchor["row_count"] != len(bound_projection):
            raise HistoricalPriorError(
                "invalid_historical_snapshot", "anchor row_count mismatch"
            )
        if anchor["sha256"] != canonical_hash(bound_projection):
            raise HistoricalPriorError(
                "invalid_historical_snapshot", "anchor projection hash mismatch"
            )
    expected_hash = _snapshot_hash(row)
    if row["snapshot_hash"] != expected_hash:
        raise HistoricalPriorError("historical_snapshot_hash_mismatch", f"expected {expected_hash}")
    return row


def historical_record_hash(record: Mapping[str, Any]) -> str:
    """Commit to the complete snapshot row, including its source anchor.

    ``record_id`` intentionally commits only to the stable historical identity.
    Axis-C reopen proofs additionally bind this whole-row hash so a caller
    cannot transplant the identity into a different snapshot projection.
    """

    if not isinstance(record, Mapping):
        raise HistoricalPriorError(
            "historical_record_required", "expected historical record object"
        )
    return canonical_hash(dict(record))


def find_bound_historical_record(
    snapshot: Mapping[str, Any],
    *,
    record_id: str,
    record_hash: str,
    family_key: str,
    representative_experiment_id: str,
) -> dict[str, Any]:
    """Return the one exact historical row named by a quantitative reopen.

    The full snapshot is validated first.  Family and representative bindings
    are deliberately exact; fuzzy family text is never an admission input.
    """

    normal = validate_historical_prior_snapshot(snapshot)
    matches = [
        record
        for record in normal["records"]
        if str(record.get("record_id") or "") == record_id
    ]
    if len(matches) != 1:
        raise HistoricalPriorError(
            "historical_record_binding_mismatch",
            f"expected one record_id={record_id}, found {len(matches)}",
        )
    record = dict(matches[0])
    if historical_record_hash(record) != record_hash:
        raise HistoricalPriorError(
            "historical_record_hash_mismatch", record_id
        )
    if str(record.get("family_key") or "") != family_key:
        raise HistoricalPriorError(
            "historical_family_binding_mismatch",
            f"record={record.get('family_key')!r} proof={family_key!r}",
        )
    representatives = {
        str(value) for value in record.get("representative_exps") or []
    }
    if representative_experiment_id not in representatives:
        raise HistoricalPriorError(
            "historical_experiment_binding_mismatch",
            representative_experiment_id,
        )
    return record


def require_nonempty_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    row = validate_historical_prior_snapshot(value)
    source_rows = sum(int(anchor["row_count"]) for anchor in row["source_anchors"])
    if source_rows > 0 and row["record_count"] == 0:
        raise HistoricalPriorError(
            "empty_historical_prior",
            "anchored history is nonempty but no prior record was supplied",
        )
    return row


def candidate_legacy_fingerprints(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project a rich Phase-1 fingerprint onto each legacy component source."""
    rich = candidate.get("fingerprint") if isinstance(candidate.get("fingerprint"), Mapping) else {}
    texts: list[str] = [
        str(candidate.get("title") or ""),
        str(candidate.get("hypothesis") or ""),
        *(str(value) for value in rich.values() if not isinstance(value, (list, tuple, dict))),
    ]
    inferred = infer_fingerprint(*texts)
    sources = {
        canonical_data_source(rich.get("data_source")),
        canonical_data_source(inferred.get("data_source")),
        *(canonical_data_source(value) for value in rich.get("component_sources") or []),
    }
    for source in tuple(sources):
        sources.update(_LEGACY_SOURCE_PROJECTIONS.get(source, ()))
    sources.discard("")
    return [
        canonical_legacy_fingerprint(
            {
                "data_source": source,
                "field_tags": inferred.get("field_tags") or [],
                "gate_shape": inferred.get("gate_shape") or "other",
            }
        )
        for source in sorted(sources)
    ]


# Two candidates on the same data source share a 0.60 structural score floor
# (0.45 source identity + 0.15 gate-shape identity) before any text overlap,
# which exceeds WARN_THRESHOLD (0.55). Without a mechanism check, a new
# single-source surface could therefore never produce a second discovery
# candidate family, contradicting AGENTS.md section 2.4 axes (b)/(d)
# (exp-20260728-005). A hit whose economic mechanisms are explicit on BOTH
# sides and essentially disjoint is waived unless the score reaches the
# structural-duplicate bar, which indicates near-verbatim text (a renamed
# mechanism cannot hide a copied treatment: shared treatment text keeps the
# tag jaccard, and thus the score, high).
D3_STRUCTURAL_DUPLICATE_THRESHOLD = 0.85
_MECHANISM_SAME_JACCARD = 0.2


def _mechanism_tokens(value: Any) -> frozenset[str]:
    return frozenset(
        token for token in _normal_mechanism(value).split("_") if token
    )


def _mechanisms_disjoint(mech_a: Any, mech_b: Any) -> bool:
    a, b = _mechanism_tokens(mech_a), _mechanism_tokens(mech_b)
    if not a or not b:
        # A missing mechanism on either side stays conservative: no waiver.
        return False
    union = len(a | b)
    return (len(a & b) / union if union else 1.0) < _MECHANISM_SAME_JACCARD


def legacy_near_neighbors(
    candidate: Mapping[str, Any],
    prior_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return legacy neighbors using the experiment guard's own calibration.

    The reserve-time novelty gate — the authority on frozen families — scores
    a ticket against its own declared source. Here every candidate is
    additionally projected onto legacy alias buckets and its text-inferred
    source so a renamed primary cannot dodge D3, but those extra projections
    carry a 0.60 structural score floor shared by essentially every
    price-based candidate. Therefore (exp-20260728-005):

    - a hit whose prior source is one of the candidate's DECLARED evidence
      faces (primary data_source or an explicit component source, after
      canonical aliasing) rejects at WARN_THRESHOLD, exactly like the
      reserve-time gate;
    - a hit reachable only through an inferred/alias-expanded projection
      rejects at the structural-duplicate bar (near-verbatim text);
    - explicit, essentially-disjoint economic mechanisms on both sides waive
      sub-structural hits (section 2.4 axes (b)/(d)).
    """
    candidate_fingerprints = candidate_legacy_fingerprints(candidate)
    rich = candidate.get("fingerprint")
    candidate_mechanism = (
        rich.get("economic_mechanism") if isinstance(rich, Mapping) else None
    )
    declared_faces: set[str] = set()
    if isinstance(rich, Mapping):
        declared_faces.add(canonical_data_source(rich.get("data_source")))
        for component in rich.get("component_sources") or []:
            declared_faces.add(canonical_data_source(component))
    declared_faces.discard("")
    declared_faces.discard("other")
    hits: list[dict[str, Any]] = []
    for record in prior_records:
        raw = record.get("fingerprint")
        if not isinstance(raw, Mapping) or "field_tags" not in raw:
            continue
        prior = canonical_legacy_fingerprint(raw)
        best = max((distance(current, prior) for current in candidate_fingerprints), default=0.0)
        if best < WARN_THRESHOLD:
            continue
        declared_hit = (
            not declared_faces or prior.get("data_source") in declared_faces
        )
        if not declared_hit and best < D3_STRUCTURAL_DUPLICATE_THRESHOLD:
            continue
        if (
            best < D3_STRUCTURAL_DUPLICATE_THRESHOLD
            and _mechanisms_disjoint(
                candidate_mechanism, prior.get("economic_mechanism")
            )
        ):
            continue
        representatives = sorted(str(value) for value in record.get("representative_exps") or [])
        hits.append(
            {
                "score": best,
                "family_key": str(record.get("family_key") or ""),
                "representative_exps": representatives,
                "record_id": str(record.get("record_id") or ""),
            }
        )
    return sorted(
        hits,
        key=lambda item: (-float(item["score"]), item["family_key"], item["record_id"]),
    )
