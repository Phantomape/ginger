"""Prospective USAspending obligation-conversion observer.

USAspending transaction downloads are current snapshots, not historical
point-in-time archives.  Policy availability begins only at the
caller-supplied ``observed_at`` clock.  Source dates never set availability;
``initial_report_date`` is used solely as a conservative post-initialization
freshness guard for prospective-evidence eligibility.

The first snapshot seeds transaction identities and can never create forward
evidence.  Later snapshots append a row only when a transaction key is seen
locally for the first time; that does not prove first public availability.
Department of Defense and U.S. Army Corps of Engineers rows are excluded for
their publication delay and never enter the ledger.  This module is
observer-only and cannot create signals, prices, or orders.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text


OBSERVER_NAME = "usaspending_obligation_observer"
SCHEMA_VERSION = 2
RULE_VERSION = "usaspending_positive_obligation_without_ceiling_expansion_v2"
OUTPUT_ROOT = DATA_ROOT / "non_ohlcv" / OBSERVER_NAME
DEFAULT_RAW_DIR = OUTPUT_ROOT / "raw"
DEFAULT_RAW_ZIP_PATH = (
    DEFAULT_RAW_DIR
    / "SubawardsAndPrimeTransactions_2026-07-13_H20M51S32580747.zip"
)
EXPECTED_DEFAULT_RAW_ZIP_SHA256 = (
    "bc54b96abe4e9a54ae6a022e867d21e9865ae2b2cf5b9ee57c6adab469d6c773"
)
HISTORICAL_PIT_STATUS = "current_snapshot_not_historical_PIT"
SOURCE_DATE_ROLE = "source_metadata_only_not_policy_availability"
FORWARD_EVENT_SEMANTICS = (
    "prospective_local_first_seen_not_proof_of_first_publication"
)
SOURCE_FRESHNESS_GUARD = (
    "initial_report_date_utc_date_gte_observer_initialized_at_utc_date"
)
SOURCE_FRESHNESS_ROLE = "eligibility_guard_only_not_policy_availability"
ELIGIBILITY_RULE = (
    "federal_action_obligation > 0 and base_and_all_options_value <= 0"
)


_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "transaction_key": (
        "contract_transaction_unique_key",
        "contract transaction unique key",
        "contracttransactionuniquekey",
        "detached_award_proc_unique",
        "transaction_unique_key",
    ),
    "federal_action_obligation": (
        "federal_action_obligation",
        "federal action obligation",
        "action obligation",
        "transaction amount",
        "dollarsobligated",
    ),
    "base_and_all_options_value": (
        "base_and_all_options_value",
        "base and all options value",
        "baseandalloptionsvalue",
    ),
    "base_and_exercised_options_value": (
        "base_and_exercised_options_value",
        "base and exercised options value",
        "baseandexercisedoptionsvalue",
    ),
    "current_total_value_of_award": (
        "current_total_value_of_award",
        "current total value of award",
        "total base and exercised options value",
    ),
    "potential_total_value_of_award": (
        "potential_total_value_of_award",
        "potential total value of award",
        "total base and all options value",
    ),
    "action_date": ("action_date", "action date"),
    "initial_report_date": ("initial_report_date", "initial report date"),
    "last_modified_date": ("last_modified_date", "last modified date"),
    "award_id": ("award_id_piid", "award id", "piid"),
    "modification_number": (
        "modification_number",
        "modification number",
        "mod",
    ),
    "recipient_name": (
        "recipient_name",
        "recipient name",
        "legal_entity_name",
    ),
    "recipient_uei": ("recipient_uei", "recipient uei"),
    "recipient_parent_name": (
        "recipient_parent_name",
        "recipient parent name",
        "parent recipient name",
        "ultimate_parent_legal_entity_name",
    ),
    "recipient_parent_uei": (
        "recipient_parent_uei",
        "recipient parent uei",
        "parent recipient uei",
    ),
    "awarding_agency_name": (
        "awarding_agency_name",
        "awarding agency",
        "awarding_toptier_agency_name",
    ),
    "awarding_sub_agency_name": (
        "awarding_sub_agency_name",
        "awarding sub agency",
        "awarding_subtier_agency_name",
    ),
    "awarding_office_name": ("awarding_office_name", "awarding office"),
    "funding_agency_name": ("funding_agency_name", "funding agency"),
    "funding_sub_agency_name": (
        "funding_sub_agency_name",
        "funding sub agency",
    ),
    "naics_code": ("naics_code", "naics code"),
    "naics_description": ("naics_description", "naics description"),
    "transaction_description": (
        "transaction_description",
        "transaction description",
        "description",
    ),
    "action_type_code": ("action_type_code", "action type code"),
    "action_type": ("action_type", "action type"),
}

_REQUIRED_COLUMNS = frozenset(
    {
        "transaction_key",
        "federal_action_obligation",
        "base_and_all_options_value",
        "awarding_agency_name",
    }
)


def _normalise_column_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _normalise_text(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def _alias_lookup(fieldnames: Iterable[str]) -> dict[str, str]:
    available: dict[str, str] = {}
    for name in fieldnames:
        available.setdefault(_normalise_column_name(name), name)
    resolved: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            source = available.get(_normalise_column_name(alias))
            if source is not None:
                resolved[canonical] = source
                break
    missing = sorted(_REQUIRED_COLUMNS - resolved.keys())
    if missing:
        raise ValueError(f"USAspending transaction CSV missing required columns: {missing}")
    return resolved


def _parse_timestamp(value: Any) -> datetime:
    if value in (None, ""):
        raise ValueError("observed_at is required")
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


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_csv_bytes(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("cp1252")


def _csv_payloads(path: Path) -> list[tuple[str, bytes]]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            csv_names = sorted(
                name
                for name in archive.namelist()
                if name.casefold().endswith(".csv")
                and "subaward" not in Path(name).name.casefold()
            )
            prime_names = [
                name
                for name in csv_names
                if "primetransaction" in Path(name).name.casefold()
            ]
            selected = prime_names or csv_names
            if not selected:
                raise ValueError(f"no transaction CSV member found in {path}")
            return [(name, archive.read(name)) for name in selected]
    if path.suffix.casefold() != ".csv":
        raise ValueError(f"expected a USAspending CSV or ZIP snapshot: {path}")
    return [(path.name, path.read_bytes())]


def _parse_money(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    negative_parentheses = text.startswith("(") and text.endswith(")")
    if negative_parentheses:
        text = text[1:-1]
    text = text.replace(",", "").replace("$", "").strip()
    try:
        number = float(text)
    except ValueError:
        return None
    if negative_parentheses:
        number = -number
    return number if math.isfinite(number) else None


def _embargo_reason(row: Mapping[str, Any]) -> str | None:
    agency_text = " ".join(
        _normalise_text(row.get(key))
        for key in (
            "awarding_agency_name",
            "awarding_sub_agency_name",
            "awarding_office_name",
            "funding_agency_name",
            "funding_sub_agency_name",
        )
        if row.get(key)
    )
    if any(
        marker in agency_text
        for marker in (
            "u s army corps of engineers",
            "us army corps of engineers",
            "army corps of engineers",
            "usace",
        )
    ):
        return "usace_90_day_publication_embargo"
    if (
        "department of defense" in agency_text
        or "dept of defense" in agency_text
        or re.search(r"(?:^| )dod(?: |$)", agency_text)
    ):
        return "dod_90_day_publication_embargo"
    return None


def _canonical_row(
    raw: Mapping[str, Any], aliases: Mapping[str, str], *, source_member: str
) -> dict[str, Any]:
    row = {
        canonical: str(raw.get(source, "") or "").strip()
        for canonical, source in aliases.items()
    }
    transaction_key = row.get("transaction_key", "").strip()
    if not transaction_key:
        raise ValueError("USAspending transaction row has an empty transaction key")
    obligation = _parse_money(row.get("federal_action_obligation"))
    ceiling_change = _parse_money(row.get("base_and_all_options_value"))
    if obligation is None:
        eligibility_reason = "missing_or_invalid_federal_action_obligation"
        eligible = False
    elif ceiling_change is None:
        eligibility_reason = "missing_or_invalid_base_and_all_options_value"
        eligible = False
    elif obligation <= 0:
        eligibility_reason = "nonpositive_federal_action_obligation"
        eligible = False
    elif ceiling_change > 0:
        eligibility_reason = "positive_ceiling_expansion"
        eligible = False
    else:
        eligibility_reason = "positive_obligation_without_ceiling_expansion"
        eligible = True
    row.update(
        {
            "transaction_key": transaction_key,
            "federal_action_obligation": obligation,
            "base_and_all_options_value": ceiling_change,
            "base_and_exercised_options_value": _parse_money(
                row.get("base_and_exercised_options_value")
            ),
            "current_total_value_of_award": _parse_money(
                row.get("current_total_value_of_award")
            ),
            "potential_total_value_of_award": _parse_money(
                row.get("potential_total_value_of_award")
            ),
            "eligible": eligible,
            "eligibility_reason": eligibility_reason,
            "eligibility_rule": ELIGIBILITY_RULE,
            "embargo_exclusion_reason": None,
            "source_member_name": source_member,
        }
    )
    row["embargo_exclusion_reason"] = _embargo_reason(row)
    return row


def parse_usaspending_transaction_snapshot(
    snapshot_path: str | Path,
) -> list[dict[str, Any]]:
    """Parse and deduplicate one official transaction CSV/ZIP snapshot."""
    path = Path(snapshot_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    by_key: dict[str, dict[str, Any]] = {}
    for member_name, payload in _csv_payloads(path):
        reader = csv.DictReader(io.StringIO(_decode_csv_bytes(payload), newline=""))
        aliases = _alias_lookup(reader.fieldnames or [])
        for raw in reader:
            row = _canonical_row(raw, aliases, source_member=member_name)
            key = row["transaction_key"]
            existing = by_key.get(key)
            if existing is not None and existing != row:
                raise ValueError(f"conflicting rows for transaction key {key!r}")
            by_key.setdefault(key, row)
    return [by_key[key] for key in sorted(by_key)]


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
                raise ValueError(f"malformed ledger row {path}:{line_number}") from exc
            if not isinstance(row, dict) or not row.get("record_id"):
                raise ValueError(f"invalid ledger row {path}:{line_number}")
            rows.append(row)
    return rows


def _record_hash(transaction_key: str) -> str:
    return hashlib.sha256(transaction_key.encode("utf-8")).hexdigest()


def _validated_state_observation_clock(
    state: Mapping[str, Any], observed: datetime
) -> datetime | None:
    """Reject observation-clock regression once the observer is initialized."""
    if not bool(state.get("initialized")):
        return None
    clocks: list[datetime] = []
    for field in ("initialized_at", "updated_at"):
        value = state.get(field)
        if value in (None, ""):
            continue
        try:
            clocks.append(_parse_timestamp(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"initialized observer state has invalid {field}: {value!r}"
            ) from exc
    if not clocks:
        raise ValueError(
            "initialized observer state is missing initialized_at/updated_at"
        )
    floor = max(clocks)
    if observed < floor:
        raise ValueError(
            f"observed_at {_iso_utc(observed)} precedes prior observer clock "
            f"{_iso_utc(floor)}"
        )
    return floor


def _source_freshness(
    transaction: Mapping[str, Any], *, observer_initialized_at: datetime
) -> tuple[bool, str | None, str]:
    """Use the source date only to guard evidence eligibility, never availability."""
    raw = transaction.get("initial_report_date")
    if raw in (None, ""):
        return False, None, "missing_initial_report_date"
    try:
        reported = _parse_timestamp(raw)
    except (TypeError, ValueError):
        return False, None, "invalid_initial_report_date"
    reported_date = reported.date()
    initialized_date = observer_initialized_at.astimezone(timezone.utc).date()
    if reported_date < initialized_date:
        return (
            False,
            reported_date.isoformat(),
            "initial_report_date_precedes_observer_initialization",
        )
    return True, reported_date.isoformat(), "fresh_initial_report_date"


def _ledger_row(
    transaction: Mapping[str, Any],
    *,
    observed: datetime,
    observer_initialized_at: datetime,
    snapshot_path: Path,
    snapshot_sha256: str,
    forward_event: bool,
) -> dict[str, Any]:
    transaction_key = str(transaction["transaction_key"])
    first_seen_at = _iso_utc(observed)
    row_type = (
        "prospective_local_first_seen"
        if forward_event
        else "historical_snapshot_seed"
    )
    eligible = bool(transaction.get("eligible"))
    freshness_passed, source_initial_report_date_utc, freshness_status = (
        _source_freshness(
            transaction,
            observer_initialized_at=observer_initialized_at,
        )
    )
    prospective_evidence_eligible = forward_event and eligible and freshness_passed
    return {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "rule_version": RULE_VERSION,
        "row_type": row_type,
        "record_id": f"{row_type}:{_record_hash(transaction_key)}",
        **dict(transaction),
        "first_seen_at": first_seen_at,
        "observed_at": first_seen_at,
        "availability_timestamp_field": "first_seen_at",
        "availability_timestamp_source": "local_snapshot_observation_clock",
        "first_seen_scope": "local_observer_state",
        "forward_event_semantics": FORWARD_EVENT_SEMANTICS,
        "does_not_prove_first_publication": True,
        "action_date_role": SOURCE_DATE_ROLE,
        "initial_report_date_role": SOURCE_DATE_ROLE,
        "initial_report_date_freshness_role": SOURCE_FRESHNESS_ROLE,
        "last_modified_date_role": SOURCE_DATE_ROLE,
        "source_freshness_guard": SOURCE_FRESHNESS_GUARD,
        "source_freshness_guard_passed": freshness_passed,
        "source_freshness_status": freshness_status,
        "source_initial_report_date_utc": source_initial_report_date_utc,
        "observer_initialized_at": _iso_utc(observer_initialized_at),
        "historical_pit_status": HISTORICAL_PIT_STATUS,
        "current_snapshot_not_historical_pit": True,
        "source_snapshot_path": str(snapshot_path),
        "source_snapshot_sha256": snapshot_sha256,
        "forward_event": forward_event,
        "prospective_local_first_seen": forward_event,
        "seed_not_forward": not forward_event,
        "prospective_evidence_eligible": prospective_evidence_eligible,
        "candidate_eligible": False,
        "candidate_eligibility_status": (
            "seed_not_forward"
            if not forward_event
            else (
                "ineligible_obligation_conversion_rule"
                if not eligible
                else (
                    "blocked_source_freshness_guard"
                    if not freshness_passed
                    else "blocked_no_audited_ticker_mapping"
                )
            )
        ),
        "candidate_tickers": [],
        "ticker": None,
        "ticker_mapping_status": "not_attempted_no_audited_mapping_contract",
        "entry_date": None,
        "target_price": None,
        "observer_only": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }


def persist_usaspending_obligation_observer(
    snapshot_path: str | Path = DEFAULT_RAW_ZIP_PATH,
    *,
    observed_at: str | datetime,
    output_root: str | Path | None = None,
    state_path: str | Path | None = None,
    ledger_path: str | Path | None = None,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """Persist first-seen transaction rows from one local official snapshot."""
    observed = _parse_timestamp(observed_at)
    source = Path(snapshot_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    output = Path(output_root) if output_root is not None else OUTPUT_ROOT
    state_file = Path(state_path) if state_path is not None else output / "state.json"
    ledger_file = Path(ledger_path) if ledger_path is not None else output / "ledger.jsonl"
    summary_file = (
        Path(summary_path) if summary_path is not None else output / "latest_summary.json"
    )
    source_hash = file_sha256(source)
    if (
        source.resolve() == DEFAULT_RAW_ZIP_PATH.resolve()
        and source_hash != EXPECTED_DEFAULT_RAW_ZIP_SHA256
    ):
        raise ValueError(
            "frozen default USAspending snapshot SHA-256 mismatch: "
            f"expected {EXPECTED_DEFAULT_RAW_ZIP_SHA256}, got {source_hash}"
        )
    parsed = parse_usaspending_transaction_snapshot(source)

    state = _load_json(
        state_file,
        {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "initialized": False,
            "seen_transactions": {},
            "source_snapshots": {},
        },
    )
    if not isinstance(state, dict):
        raise ValueError(f"observer state must be a JSON object: {state_file}")
    _validated_state_observation_clock(state, observed)
    seen = state.get("seen_transactions")
    if not isinstance(seen, dict):
        raise ValueError("seen_transactions must be a JSON object")
    snapshots = state.get("source_snapshots")
    if not isinstance(snapshots, dict):
        snapshots = {}
    ledger_rows = _load_ledger(ledger_file)
    for row in ledger_rows:
        key = str(row.get("transaction_key") or "")
        if key:
            seen.setdefault(
                key,
                {
                    "record_id": row["record_id"],
                    "first_seen_at": row.get("first_seen_at"),
                    "source_snapshot_sha256": row.get("source_snapshot_sha256"),
                    "embargo_excluded": False,
                },
            )
    bootstrap = not bool(state.get("initialized")) and not seen and not ledger_rows
    if bootstrap:
        observer_initialized_at = observed
    elif state.get("initialized_at") not in (None, ""):
        observer_initialized_at = _parse_timestamp(state["initialized_at"])
    else:
        raise ValueError(
            "non-bootstrap observer state is missing initialized_at"
        )

    appended: list[dict[str, Any]] = []
    seed_rows: list[dict[str, Any]] = []
    forward_rows: list[dict[str, Any]] = []
    snapshot_excluded_counts: dict[str, int] = {}
    for transaction in parsed:
        exclusion = transaction.get("embargo_exclusion_reason")
        if exclusion:
            exclusion_text = str(exclusion)
            snapshot_excluded_counts[exclusion_text] = (
                snapshot_excluded_counts.get(exclusion_text, 0) + 1
            )
    new_excluded_counts: dict[str, int] = {}
    already_seen_count = 0
    for transaction in parsed:
        key = str(transaction["transaction_key"])
        if key in seen:
            already_seen_count += 1
            continue
        exclusion = transaction.get("embargo_exclusion_reason")
        if exclusion:
            exclusion_text = str(exclusion)
            new_excluded_counts[exclusion_text] = (
                new_excluded_counts.get(exclusion_text, 0) + 1
            )
            seen[key] = {
                "first_seen_at": _iso_utc(observed),
                "source_snapshot_sha256": source_hash,
                "embargo_excluded": True,
                "embargo_exclusion_reason": exclusion_text,
            }
            continue
        row = _ledger_row(
            transaction,
            observed=observed,
            observer_initialized_at=observer_initialized_at,
            snapshot_path=source,
            snapshot_sha256=source_hash,
            forward_event=not bootstrap,
        )
        appended.append(row)
        (forward_rows if row["forward_event"] else seed_rows).append(row)
        seen[key] = {
            "record_id": row["record_id"],
            "first_seen_at": row["first_seen_at"],
            "source_snapshot_sha256": source_hash,
            "embargo_excluded": False,
            "eligible": row["eligible"],
            "forward_event": row["forward_event"],
        }

    if appended:
        existing_text = ledger_file.read_text(encoding="utf-8") if ledger_file.exists() else ""
        if existing_text and not existing_text.endswith("\n"):
            existing_text += "\n"
        atomic_write_text(
            existing_text
            + "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
                for row in appended
            ),
            ledger_file,
        )

    snapshots.setdefault(
        source_hash,
        {
            "path": str(source),
            "sha256": source_hash,
            "bytes": source.stat().st_size,
            "first_observed_at": _iso_utc(observed),
            "historical_pit_status": HISTORICAL_PIT_STATUS,
        },
    )
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "rule_version": RULE_VERSION,
            "initialized": True,
            "initialized_at": state.get("initialized_at") or _iso_utc(observed),
            "updated_at": _iso_utc(observed),
            "seen_transactions": seen,
            "source_snapshots": snapshots,
            "historical_pit_status": HISTORICAL_PIT_STATUS,
            "first_seen_scope": "local_observer_state",
            "forward_event_semantics": FORWARD_EVENT_SEMANTICS,
            "does_not_prove_first_publication": True,
            "source_freshness_guard": SOURCE_FRESHNESS_GUARD,
            "source_freshness_role": SOURCE_FRESHNESS_ROLE,
            "observer_only": True,
            "trade_enabled": False,
        }
    )
    atomic_write_json(state, state_file, default=str)

    all_rows = ledger_rows + appended
    all_forward = [row for row in all_rows if row.get("forward_event") is True]
    all_seed = [row for row in all_rows if row.get("seed_not_forward") is True]
    all_eligible_forward = [
        row for row in all_forward if row.get("prospective_evidence_eligible") is True
    ]
    summary = {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "rule_version": RULE_VERSION,
        "observed_at": _iso_utc(observed),
        "source_snapshot_path": str(source),
        "source_snapshot_sha256": source_hash,
        "source_snapshot_bytes": source.stat().st_size,
        "historical_pit_status": HISTORICAL_PIT_STATUS,
        "current_snapshot_not_historical_pit": True,
        "availability_timestamp_field": "first_seen_at",
        "availability_timestamp_source": "local_snapshot_observation_clock",
        "first_seen_scope": "local_observer_state",
        "forward_event_semantics": FORWARD_EVENT_SEMANTICS,
        "does_not_prove_first_publication": True,
        "source_freshness_guard": SOURCE_FRESHNESS_GUARD,
        "source_freshness_role": SOURCE_FRESHNESS_ROLE,
        "observer_initialized_at": _iso_utc(observer_initialized_at),
        "eligibility_rule": ELIGIBILITY_RULE,
        "bootstrap_snapshot": bootstrap,
        "parsed_transaction_count": len(parsed),
        "already_seen_count": already_seen_count,
        "embargo_excluded_count": sum(snapshot_excluded_counts.values()),
        "embargo_excluded_counts": dict(sorted(snapshot_excluded_counts.items())),
        "new_embargo_excluded_count": sum(new_excluded_counts.values()),
        "new_embargo_excluded_counts": dict(sorted(new_excluded_counts.items())),
        "historical_seed_rows_appended": len(seed_rows),
        "new_forward_rows_appended": len(forward_rows),
        "new_eligible_forward_rows_appended": sum(
            1 for row in forward_rows if row["prospective_evidence_eligible"]
        ),
        "new_source_freshness_blocked_forward_rows_appended": sum(
            1
            for row in forward_rows
            if row.get("source_freshness_guard_passed") is False
        ),
        "rows_appended": len(appended),
        "ledger_row_count": len(all_rows),
        "historical_seed_count": len(all_seed),
        "forward_event_count_total": len(all_forward),
        "eligible_forward_event_count_total": len(all_eligible_forward),
        "source_freshness_blocked_forward_event_count_total": sum(
            1
            for row in all_forward
            if row.get("source_freshness_guard_passed") is False
        ),
        "seen_transaction_count": len(seen),
        "state_path": str(state_file),
        "ledger_path": str(ledger_file),
        "summary_path": str(summary_file),
        "entry_date": None,
        "target_price": None,
        "observer_only": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }
    atomic_write_json(summary, summary_file, default=str)
    return summary


def persist_daily_usaspending_obligation_observer(
    snapshot_path: str | Path = DEFAULT_RAW_ZIP_PATH,
    *,
    observed_at: str | datetime,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Daily alias for :func:`persist_usaspending_obligation_observer`."""
    return persist_usaspending_obligation_observer(
        snapshot_path,
        observed_at=observed_at,
        output_root=output_root,
    )


def run_observer(
    snapshot_path: str | Path | None = None,
    observed_at: str | datetime | None = None,
    state_path: str | Path | None = None,
    ledger_path: str | Path | None = None,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """Production-facing default-off entry point used by daily orchestration.

    When the scheduler does not supply an observation time, the local UTC
    retrieval clock is used.  Source-reported dates still never determine
    availability.
    """
    observed = observed_at if observed_at is not None else datetime.now(timezone.utc)
    return persist_usaspending_obligation_observer(
        snapshot_path or DEFAULT_RAW_ZIP_PATH,
        observed_at=observed,
        state_path=state_path,
        ledger_path=ledger_path,
        summary_path=summary_path,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot_path",
        nargs="?",
        default=str(DEFAULT_RAW_ZIP_PATH),
        help="Local USAspending transaction CSV or ZIP (defaults to frozen snapshot)",
    )
    parser.add_argument(
        "--observed-at",
        required=True,
        help="Explicit UTC policy observation time (ISO-8601)",
    )
    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_ROOT),
        help="Directory for state.json, ledger.jsonl, and latest_summary.json",
    )
    args = parser.parse_args(argv)
    summary = persist_usaspending_obligation_observer(
        args.snapshot_path,
        observed_at=args.observed_at,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


__all__ = [
    "DEFAULT_RAW_DIR",
    "DEFAULT_RAW_ZIP_PATH",
    "ELIGIBILITY_RULE",
    "EXPECTED_DEFAULT_RAW_ZIP_SHA256",
    "HISTORICAL_PIT_STATUS",
    "OBSERVER_NAME",
    "OUTPUT_ROOT",
    "RULE_VERSION",
    "file_sha256",
    "main",
    "parse_usaspending_transaction_snapshot",
    "persist_daily_usaspending_obligation_observer",
    "persist_usaspending_obligation_observer",
    "run_observer",
]


if __name__ == "__main__":
    raise SystemExit(main())
