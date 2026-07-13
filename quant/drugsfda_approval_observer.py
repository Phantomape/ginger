"""Default-off Drugs@FDA original-approval first-seen observer.

The Drugs@FDA bulk download is a *current historical snapshot*, not a
point-in-time archive.  ``SubmissionStatusDate`` is therefore retained only as
regulatory metadata.  Policy availability begins at the UTC retrieval clock
recorded in ``first_seen_at`` when a frozen snapshot is processed.

This module is deliberately standard-library only.  It does not map sponsors
or products to tickers and cannot create signals or orders.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
OBSERVER_NAME = "drugsfda_approval_observer"
SCHEMA_VERSION = 1
RULE_VERSION = "drugsfda_cder_original_nda_bla_first_seen_v1"
OUTPUT_ROOT = ROOT / "data" / "non_ohlcv" / OBSERVER_NAME
DEFAULT_RAW_ZIP_PATH = (
    OUTPUT_ROOT / "raw" / "drugsatfda_20260710.zip"
)
EXPECTED_DEFAULT_RAW_ZIP_SHA256 = (
    "53ebd9c74e0c383b6857e80fdfbbf99ddf12dcbb0fbe31f5e9416aee24f5cb17"
)
HISTORICAL_PIT_STATUS = "historical_current_snapshot_not_PIT"
APPROVAL_DATE_ROLE = "historical_regulatory_metadata_not_availability"
TARGET_PRICE_STATUS = "not_applicable_observer_only_no_trade_adapter"
ELIGIBLE_APPLICATION_TYPES = frozenset({"NDA", "BLA"})
ELIGIBLE_SUBMISSION_TYPE = "ORIG"
ELIGIBLE_SUBMISSION_STATUS = "AP"

_REQUIRED_COLUMNS = {
    "Applications.txt": {"ApplNo", "ApplType", "SponsorName"},
    "Products.txt": {"ApplNo", "DrugName", "ActiveIngredient"},
    "Submissions.txt": {
        "ApplNo",
        "SubmissionType",
        "SubmissionStatus",
        "SubmissionStatusDate",
    },
}


def _normalise_appl_no(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.zfill(6) if text.isdigit() else text.upper()


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _as_of_date(today: Any, observed: datetime) -> str:
    if today in (None, ""):
        return observed.date().isoformat()
    if isinstance(today, datetime):
        return today.date().isoformat()
    if isinstance(today, date):
        return today.isoformat()
    text = str(today).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"invalid today value: {today!r}")


def _parse_status_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return None


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member_name(archive: zipfile.ZipFile, required: str) -> str:
    matches = [
        name
        for name in archive.namelist()
        if Path(name).name.casefold() == required.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {required!r} in Drugs@FDA ZIP; found {matches}"
        )
    return matches[0]


def _table_rows(
    archive: zipfile.ZipFile, member: str
) -> Iterable[dict[str, str]]:
    name = _member_name(archive, member)
    # Official files contain Windows smart punctuation in free-text columns.
    # cp1252 is deterministic and is a strict superset of ASCII field values.
    with archive.open(name) as raw:
        with io.TextIOWrapper(raw, encoding="cp1252", newline="") as text:
            reader = csv.DictReader(text, delimiter="\t")
            fieldnames = set(reader.fieldnames or [])
            missing = _REQUIRED_COLUMNS[member] - fieldnames
            if missing:
                raise ValueError(
                    f"{member} is missing required columns: {sorted(missing)}"
                )
            for raw_row in reader:
                yield {
                    str(key): str(value or "").strip()
                    for key, value in raw_row.items()
                    if key is not None
                }


def application_id(appl_type: str, appl_no: str) -> str:
    """Return a stable ID for one application-level approval event."""
    key = f"{str(appl_type).strip().upper()}:{_normalise_appl_no(appl_no)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_drugsfda_approval_snapshot(
    raw_zip_path: str | Path,
) -> list[dict[str, Any]]:
    """Parse one frozen Drugs@FDA ZIP into deduplicated NDA/BLA approvals.

    Only ``ORIG`` submissions whose status is ``AP`` qualify.  When malformed
    source history contains multiple qualifying rows for one application, the
    earliest valid status date is retained.  No availability timestamp is
    inferred here.
    """
    path = Path(raw_zip_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    with zipfile.ZipFile(path) as archive:
        applications: dict[str, dict[str, str]] = {}
        for row in _table_rows(archive, "Applications.txt"):
            appl_type = row.get("ApplType", "").upper()
            appl_no = _normalise_appl_no(row.get("ApplNo"))
            if appl_type not in ELIGIBLE_APPLICATION_TYPES or not appl_no:
                continue
            candidate = {
                "appl_no": appl_no,
                "appl_type": appl_type,
                "sponsor_name": row.get("SponsorName", ""),
            }
            existing = applications.get(appl_no)
            if existing is not None and existing != candidate:
                raise ValueError(
                    f"conflicting Applications.txt rows for application {appl_no}"
                )
            applications[appl_no] = candidate

        product_names: dict[str, set[str]] = defaultdict(set)
        active_ingredients: dict[str, set[str]] = defaultdict(set)
        product_rows: dict[str, int] = defaultdict(int)
        for row in _table_rows(archive, "Products.txt"):
            appl_no = _normalise_appl_no(row.get("ApplNo"))
            if appl_no not in applications:
                continue
            product_rows[appl_no] += 1
            if row.get("DrugName"):
                product_names[appl_no].add(row["DrugName"])
            if row.get("ActiveIngredient"):
                active_ingredients[appl_no].add(row["ActiveIngredient"])

        approval_dates: dict[str, list[str]] = defaultdict(list)
        qualifying_submission_rows: dict[str, int] = defaultdict(int)
        invalid_approval_date_rows: dict[str, int] = defaultdict(int)
        for row in _table_rows(archive, "Submissions.txt"):
            appl_no = _normalise_appl_no(row.get("ApplNo"))
            if appl_no not in applications:
                continue
            if row.get("SubmissionType", "").upper() != ELIGIBLE_SUBMISSION_TYPE:
                continue
            if row.get("SubmissionStatus", "").upper() != ELIGIBLE_SUBMISSION_STATUS:
                continue
            qualifying_submission_rows[appl_no] += 1
            status_date = _parse_status_date(row.get("SubmissionStatusDate"))
            if status_date is None:
                invalid_approval_date_rows[appl_no] += 1
                continue
            approval_dates[appl_no].append(status_date)

    parsed: list[dict[str, Any]] = []
    for appl_no, application in applications.items():
        dates = approval_dates.get(appl_no) or []
        if not dates:
            continue
        parsed.append(
            {
                **application,
                "application_id": application_id(
                    application["appl_type"], application["appl_no"]
                ),
                "approval_date": min(dates),
                "approval_date_role": APPROVAL_DATE_ROLE,
                "qualifying_original_approved_submission_rows": (
                    qualifying_submission_rows[appl_no]
                ),
                "invalid_qualifying_approval_date_rows": (
                    invalid_approval_date_rows[appl_no]
                ),
                "product_names": sorted(product_names.get(appl_no, set())),
                "active_ingredients": sorted(
                    active_ingredients.get(appl_no, set())
                ),
                "product_row_count": product_rows.get(appl_no, 0),
                "historical_pit_status": HISTORICAL_PIT_STATUS,
            }
        )
    return sorted(
        parsed,
        key=lambda row: (
            row["approval_date"],
            row["appl_type"],
            row["appl_no"],
        ),
    )


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"malformed ledger row {path}:{line_number}"
                ) from exc
            if not isinstance(row, dict) or not row.get("record_id"):
                raise ValueError(f"invalid ledger row {path}:{line_number}")
            rows.append(row)
    return rows


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(
            payload,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
    )


def _decision_row(
    application: Mapping[str, Any],
    *,
    observed: datetime,
    raw_zip_path: Path,
    raw_zip_sha256: str,
    forward_event: bool,
) -> dict[str, Any]:
    first_seen_at = _iso_utc(observed)
    appl_id = str(application["application_id"])
    if forward_event:
        row_type = "prospective_application_first_seen_decision"
        record_prefix = "first_seen"
        entry_status = "pending_no_ticker_mapping_or_trade_adapter"
        entry_rule = "pending_future_contract_after_separate_mapping_and_gate"
        outcome_status = "pending"
    else:
        row_type = "historical_snapshot_seed"
        record_prefix = "historical_seed"
        entry_status = "not_applicable_historical_snapshot_seed"
        entry_rule = None
        outcome_status = "not_applicable_historical_snapshot_seed"
    return {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "rule_version": RULE_VERSION,
        "row_type": row_type,
        "record_id": f"{record_prefix}:{appl_id}",
        "decision_id": appl_id,
        "application_id": appl_id,
        "appl_no": application["appl_no"],
        "appl_type": application["appl_type"],
        "sponsor_name": application["sponsor_name"],
        "product_names": list(application["product_names"]),
        "active_ingredients": list(application["active_ingredients"]),
        "product_row_count": application["product_row_count"],
        "approval_date": application["approval_date"],
        "approval_date_role": APPROVAL_DATE_ROLE,
        "qualifying_original_approved_submission_rows": application[
            "qualifying_original_approved_submission_rows"
        ],
        "first_seen_at": first_seen_at,
        "snapshot_retrieved_at": first_seen_at,
        "availability_timestamp_field": "first_seen_at",
        "availability_timestamp_source": "snapshot_retrieval_utc",
        "historical_pit_status": HISTORICAL_PIT_STATUS,
        "forward_event": forward_event,
        "prospective_evidence_eligible": forward_event,
        "candidate_eligible": False,
        "forward_eligibility_status": (
            "prospective_first_seen" if forward_event else "seed_not_forward"
        ),
        "seed_not_forward": not forward_event,
        "seed_status": (
            None if forward_event else "historical_snapshot_seed_not_forward"
        ),
        "source_snapshot_path": str(raw_zip_path),
        "source_snapshot_sha256": raw_zip_sha256,
        "candidate_tickers": [],
        "ticker": None,
        "ticker_mapping_status": "not_attempted_no_mapping_contract",
        "entry_status": entry_status,
        "entry_date": None,
        "entry_rule": entry_rule,
        "target_price": None,
        "target_price_status": TARGET_PRICE_STATUS,
        "outcome_status": outcome_status,
        "observer_only": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }


def persist_drugsfda_approval_observer(
    today: Any = None,
    *,
    raw_zip_path: str | Path | None = None,
    output_root: str | Path | None = None,
    observed_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Persist unseen application-level approvals to an append-only ledger.

    ``today`` labels the daily run only; it never supplies availability.
    ``first_seen_at`` always comes from ``observed_at`` (or the current UTC
    retrieval clock when omitted).
    """
    observed = _parse_timestamp(observed_at)
    as_of_date = _as_of_date(today, observed)
    output = Path(output_root) if output_root is not None else OUTPUT_ROOT
    source = Path(raw_zip_path) if raw_zip_path is not None else DEFAULT_RAW_ZIP_PATH
    if not source.is_file():
        raise FileNotFoundError(source)

    source_hash = file_sha256(source)
    is_frozen_default_snapshot = source.resolve() == DEFAULT_RAW_ZIP_PATH.resolve()
    expected_source_hash = (
        EXPECTED_DEFAULT_RAW_ZIP_SHA256 if is_frozen_default_snapshot else None
    )
    if expected_source_hash is not None and source_hash != expected_source_hash:
        raise ValueError(
            "frozen default Drugs@FDA snapshot SHA-256 mismatch: "
            f"expected {expected_source_hash}, got {source_hash}"
        )
    parsed = parse_drugsfda_approval_snapshot(source)
    state_path = output / "state.json"
    ledger_path = output / "ledger.jsonl"
    summary_path = output / "latest_summary.json"

    state = _load_json(
        state_path,
        {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "seen_applications": {},
            "source_snapshots": {},
            "trade_enabled": False,
        },
    )
    if not isinstance(state, dict):
        raise ValueError(f"observer state must be a JSON object: {state_path}")
    seen = state.get("seen_applications")
    if not isinstance(seen, dict):
        raise ValueError("seen_applications must be a JSON object")
    snapshots = state.get("source_snapshots")
    if not isinstance(snapshots, dict):
        snapshots = {}

    ledger_rows = _load_ledger(ledger_path)
    existing_record_ids = {str(row["record_id"]) for row in ledger_rows}
    for row in ledger_rows:
        appl_id = str(row.get("application_id") or "")
        if appl_id:
            seen.setdefault(
                appl_id,
                {
                    "record_id": row["record_id"],
                    "first_seen_at": row.get("first_seen_at"),
                    "source_snapshot_sha256": row.get("source_snapshot_sha256"),
                },
            )

    bootstrap_historical_snapshot = not seen and not ledger_rows
    appended: list[dict[str, Any]] = []
    seed_rows_appended: list[dict[str, Any]] = []
    forward_rows_appended: list[dict[str, Any]] = []
    for application in parsed:
        appl_id = str(application["application_id"])
        if appl_id in seen:
            continue
        forward_event = not bootstrap_historical_snapshot
        record_prefix = "first_seen" if forward_event else "historical_seed"
        record_id = f"{record_prefix}:{appl_id}"
        if record_id in existing_record_ids:
            continue
        row = _decision_row(
            application,
            observed=observed,
            raw_zip_path=source,
            raw_zip_sha256=source_hash,
            forward_event=forward_event,
        )
        appended.append(row)
        if forward_event:
            forward_rows_appended.append(row)
        else:
            seed_rows_appended.append(row)
        existing_record_ids.add(record_id)
        seen[appl_id] = {
            "record_id": record_id,
            "appl_no": application["appl_no"],
            "appl_type": application["appl_type"],
            "first_seen_at": row["first_seen_at"],
            "source_snapshot_sha256": source_hash,
            "forward_event": forward_event,
            "forward_eligibility_status": row["forward_eligibility_status"],
            "seed_not_forward": row["seed_not_forward"],
            "seed_status": row["seed_status"],
        }

    if appended:
        existing_text = (
            ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else ""
        )
        if existing_text and not existing_text.endswith("\n"):
            existing_text += "\n"
        _atomic_write_text(
            ledger_path,
            existing_text
            + "".join(
                json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n"
                for row in appended
            ),
        )

    snapshots.setdefault(
        source_hash,
        {
            "path": str(source),
            "sha256": source_hash,
            "first_retrieved_at": _iso_utc(observed),
            "historical_pit_status": HISTORICAL_PIT_STATUS,
        },
    )
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "rule_version": RULE_VERSION,
            "updated_at": _iso_utc(observed),
            "seen_applications": seen,
            "source_snapshots": snapshots,
            "historical_pit_status": HISTORICAL_PIT_STATUS,
            "observer_only": True,
            "trade_enabled": False,
        }
    )
    _atomic_write_json(state_path, state)

    all_rows = ledger_rows + appended
    historical_seed_rows = [
        row for row in all_rows if row.get("row_type") == "historical_snapshot_seed"
    ]
    forward_event_rows = [row for row in all_rows if row.get("forward_event") is True]
    type_counts = {
        appl_type: sum(1 for row in parsed if row["appl_type"] == appl_type)
        for appl_type in sorted(ELIGIBLE_APPLICATION_TYPES)
    }
    summary = {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of_date,
        "observed_at": _iso_utc(observed),
        "snapshot_retrieved_at": _iso_utc(observed),
        "source_snapshot_path": str(source),
        "source_snapshot_sha256": source_hash,
        "source_snapshot_expected_sha256": expected_source_hash,
        "source_snapshot_sha256_matches_expected": (
            source_hash == expected_source_hash
            if expected_source_hash is not None
            else None
        ),
        "source_snapshot_bytes": source.stat().st_size,
        "historical_pit_status": HISTORICAL_PIT_STATUS,
        "approval_date_role": APPROVAL_DATE_ROLE,
        "availability_timestamp_field": "first_seen_at",
        "availability_timestamp_source": "snapshot_retrieval_utc",
        "parsed_application_count": len(parsed),
        "parsed_application_type_counts": type_counts,
        "historical_seed_count": len(historical_seed_rows),
        "historical_seed_rows_appended": len(seed_rows_appended),
        "historical_snapshot_seed_not_forward": bool(historical_seed_rows),
        "new_forward_event_count": len(forward_rows_appended),
        "forward_event_count_total": len(forward_event_rows),
        "new_application_count": len(forward_rows_appended),
        "rows_appended": len(appended),
        "ledger_row_count": len(all_rows),
        "seen_application_count": len(seen),
        "state_path": str(state_path),
        "ledger_path": str(ledger_path),
        "summary_path": str(summary_path),
        "ticker_mapping_status": "not_attempted_no_mapping_contract",
        "entry_status": (
            "historical_snapshot_seed_not_forward"
            if bootstrap_historical_snapshot
            else "pending_only_for_new_forward_events_without_ticker_mapping"
        ),
        "target_price": None,
        "target_price_status": TARGET_PRICE_STATUS,
        "observer_only": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }
    _atomic_write_json(summary_path, summary)
    return summary


def persist_daily_drugsfda_approval_observer(
    today: Any = None, **kwargs: Any
) -> dict[str, Any]:
    """Daily-run alias for :func:`persist_drugsfda_approval_observer`."""
    return persist_drugsfda_approval_observer(today, **kwargs)


__all__ = [
    "APPROVAL_DATE_ROLE",
    "DEFAULT_RAW_ZIP_PATH",
    "ELIGIBLE_APPLICATION_TYPES",
    "EXPECTED_DEFAULT_RAW_ZIP_SHA256",
    "HISTORICAL_PIT_STATUS",
    "OBSERVER_NAME",
    "OUTPUT_ROOT",
    "RULE_VERSION",
    "application_id",
    "file_sha256",
    "parse_drugsfda_approval_snapshot",
    "persist_daily_drugsfda_approval_observer",
    "persist_drugsfda_approval_observer",
]
