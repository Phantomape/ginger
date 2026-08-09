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
import os
import re
import tempfile
import time as time_lib
import urllib.request
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from data_paths import DATA_ROOT, atomic_write_json, atomic_write_text


OBSERVER_NAME = "usaspending_obligation_observer"
SCHEMA_VERSION = 2
RULE_VERSION = "usaspending_positive_obligation_without_ceiling_expansion_v2"
OUTPUT_ROOT = DATA_ROOT / "non_ohlcv" / OBSERVER_NAME
DEFAULT_OUTPUT_DIR = OUTPUT_ROOT
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
DOWNLOAD_TRANSACTIONS_URL = (
    "https://api.usaspending.gov/api/v2/download/transactions/"
)
OFFICIAL_API_HOST = "api.usaspending.gov"
OFFICIAL_DOWNLOAD_HOSTS = frozenset(
    {OFFICIAL_API_HOST, "files.usaspending.gov"}
)
PRODUCER_MODE = "official_daily_transaction_download"
PRODUCER_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_DOWNLOAD_LOOKBACK_DAYS = 2
DEFAULT_MAX_STATUS_POLLS = 15
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_PENDING_JOB_MAX_AGE_HOURS = 24
PENDING_JOB_SCHEMA_VERSION = 1
MAX_PENDING_STATUS_HISTORY = 256
PENDING_JOB_JOURNAL_NAME = "pending_job_receipt.json"
MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024
MAX_PRIME_CSV_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


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


def _parse_run_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"run_date must be an ISO date, got {value!r}") from exc


def build_daily_transaction_download_request(
    run_date: date | str,
) -> dict[str, Any]:
    """Return the fixed exp-20260713-007-compatible daily request."""
    run_day = _parse_run_date(run_date)
    start_day = run_day - timedelta(days=DEFAULT_DOWNLOAD_LOOKBACK_DAYS)
    return {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": [
                {
                    "start_date": start_day.isoformat(),
                    "end_date": run_day.isoformat(),
                    "date_type": "last_modified_date",
                }
            ],
        },
        "columns": [],
        "file_format": "csv",
        "limit": 5000,
    }


def _validate_https_url(
    value: Any,
    *,
    allowed_hosts: Iterable[str],
    field_name: str,
) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"USAspending response is missing {field_name}")
    parsed = urlparse(text)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {text!r}") from exc
    allowed = {host.casefold() for host in allowed_hosts}
    if (
        parsed.scheme.casefold() != "https"
        or (parsed.hostname or "").casefold() not in allowed
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or not parsed.path.startswith("/")
    ):
        raise ValueError(
            f"{field_name} must use HTTPS on an official USAspending host"
        )
    return text


def _validate_remote_file_name(value: Any) -> str:
    name = str(value or "").strip()
    if (
        not name
        or name != Path(name).name
        or "/" in name
        or "\\" in name
        or not name.casefold().endswith(".zip")
    ):
        raise ValueError("USAspending response has an invalid file_name")
    return name


class _OfficialHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects away from the two fixed official hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        _validate_https_url(
            newurl,
            allowed_hosts=OFFICIAL_DOWNLOAD_HOSTS,
            field_name="redirect_url",
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_http_request(request: urllib.request.Request, *, timeout: float) -> bytes:
    opener = urllib.request.build_opener(_OfficialHostRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        _validate_https_url(
            response.geturl(),
            allowed_hosts=OFFICIAL_DOWNLOAD_HOSTS,
            field_name="final_response_url",
        )
        payload = response.read(MAX_SNAPSHOT_BYTES + 1)
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("USAspending response exceeds the bounded byte limit")
    return payload


def _default_http_post(
    url: str,
    payload: Mapping[str, Any],
    *,
    timeout: float,
) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(dict(payload), separators=(",", ":")).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ginger-usaspending-observer/1",
        },
        method="POST",
    )
    return _default_http_request(request, timeout=timeout)


def _default_http_get(url: str, *, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json, application/zip",
            "User-Agent": "ginger-usaspending-observer/1",
        },
        method="GET",
    )
    return _default_http_request(request, timeout=timeout)


def _response_bytes(response: Any) -> bytes:
    if isinstance(response, bytes):
        return response
    if isinstance(response, bytearray):
        return bytes(response)
    if isinstance(response, str):
        return response.encode("utf-8")
    content = getattr(response, "content", None)
    if isinstance(content, (bytes, bytearray)):
        return bytes(content)
    read = getattr(response, "read", None)
    if callable(read):
        payload = read()
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)
    raise TypeError("HTTP response does not expose a bytes payload")


def _response_json_object(response: Any) -> dict[str, Any]:
    if isinstance(response, Mapping):
        return dict(response)
    json_method = getattr(response, "json", None)
    if callable(json_method):
        parsed = json_method()
    else:
        parsed = json.loads(_response_bytes(response).decode("utf-8-sig"))
    if not isinstance(parsed, Mapping):
        raise ValueError("USAspending HTTP response must be a JSON object")
    return dict(parsed)


def _atomic_write_immutable_bytes(path: Path, payload: bytes) -> bool:
    """Atomically create an immutable artifact; identical reuse is allowed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return False
        raise FileExistsError(f"immutable artifact already exists with new bytes: {path}")
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_name, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise FileExistsError(
                    f"immutable artifact race produced different bytes: {path}"
                )
            return False
        return True
    finally:
        if tmp_name is not None:
            try:
                os.remove(tmp_name)
            except FileNotFoundError:
                pass


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str,
    ).encode("utf-8")


def _validate_transaction_zip_payload(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("USAspending ZIP exceeds the bounded byte limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("USAspending download is not a valid ZIP") from exc
    with archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"USAspending ZIP has a bad CRC member: {bad_member}")
        prime_infos = [
            info
            for info in archive.infolist()
            if info.filename.casefold().endswith(".csv")
            and Path(info.filename).name.casefold().startswith(
                "contracts_primetransactions"
            )
        ]
        if not prime_infos:
            raise ValueError(
                "USAspending ZIP is missing Contracts_PrimeTransactions CSV"
            )
        uncompressed_bytes = sum(info.file_size for info in prime_infos)
        if uncompressed_bytes > MAX_PRIME_CSV_UNCOMPRESSED_BYTES:
            raise ValueError("USAspending prime CSV payload exceeds the bounded limit")
        member_rows: dict[str, int] = {}
        resolved_headers: dict[str, dict[str, str]] = {}
        total_rows = 0
        for info in sorted(prime_infos, key=lambda item: item.filename):
            reader = csv.DictReader(
                io.StringIO(
                    _decode_csv_bytes(archive.read(info)),
                    newline="",
                )
            )
            aliases = _alias_lookup(reader.fieldnames or [])
            row_count = sum(1 for _ in reader)
            total_rows += row_count
            if total_rows > 5000:
                raise ValueError(
                    "USAspending prime transaction row count exceeds request limit"
                )
            member_rows[info.filename] = row_count
            resolved_headers[info.filename] = {
                key: aliases[key] for key in sorted(_REQUIRED_COLUMNS)
            }
    return {
        "row_count": total_rows,
        "archive_member_rows": member_rows,
        "resolved_required_headers": resolved_headers,
    }


def _daily_snapshot_paths(output_dir: Path, run_day: date) -> tuple[Path, Path]:
    stem = f"transaction_snapshot_{run_day:%Y%m%d}"
    raw_dir = output_dir / "raw"
    return raw_dir / f"{stem}.zip", raw_dir / f"{stem}.manifest.json"


def _manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _PendingJobContinuationError(ValueError):
    """A persisted async receipt is unsafe to resume."""

    def __init__(self, message: str, *, validation_status: str = "invalid") -> None:
        super().__init__(message)
        self.validation_status = validation_status


def _validated_pending_job_continuation(
    value: Any,
    *,
    run_day: date,
    expected_request: Mapping[str, Any],
    attempted_at: datetime,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _PendingJobContinuationError(
            "USAspending pending health is missing its async job receipt"
        )
    required_matches = {
        "schema_version": PENDING_JOB_SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "run_date": run_day.isoformat(),
    }
    for key, expected in required_matches.items():
        if value.get(key) != expected:
            raise _PendingJobContinuationError(
                f"USAspending pending job receipt has invalid {key}"
            )
    if value.get("download_request") != dict(expected_request):
        raise _PendingJobContinuationError(
            "USAspending pending job request does not match the frozen daily contract"
        )

    requested_at = _parse_timestamp(value.get("job_requested_at_utc"))
    age = attempted_at - requested_at
    if age.total_seconds() < 0:
        raise _PendingJobContinuationError(
            "USAspending pending job receipt is future-dated"
        )
    if age > timedelta(hours=DEFAULT_PENDING_JOB_MAX_AGE_HOURS):
        raise _PendingJobContinuationError(
            "USAspending pending job receipt expired before resume",
            validation_status="expired",
        )

    status_url = _validate_https_url(
        value.get("status_url"),
        allowed_hosts={OFFICIAL_API_HOST},
        field_name="pending_status_url",
    )
    file_name = _validate_remote_file_name(value.get("file_name"))
    file_url = _validate_https_url(
        value.get("file_url"),
        allowed_hosts=OFFICIAL_DOWNLOAD_HOSTS,
        field_name="pending_file_url",
    )
    history_raw = value.get("status_history")
    if not isinstance(history_raw, list):
        raise _PendingJobContinuationError(
            "USAspending pending job receipt has no status history list"
        )
    if len(history_raw) > MAX_PENDING_STATUS_HISTORY:
        raise _PendingJobContinuationError(
            "USAspending pending job status history exceeds its bounded limit"
        )
    status_history = [str(item or "").strip().casefold() for item in history_raw]
    if any(item not in {"ready", "running", "finished"} for item in status_history):
        raise _PendingJobContinuationError(
            "USAspending pending job receipt has an invalid status history"
        )
    if "finished" in status_history and (
        status_history[-1] != "finished" or status_history.count("finished") != 1
    ):
        raise _PendingJobContinuationError(
            "USAspending pending job receipt continues after a finished status"
        )
    status_poll_count = value.get("status_poll_count")
    if (
        isinstance(status_poll_count, bool)
        or not isinstance(status_poll_count, int)
        or status_poll_count != len(status_history)
    ):
        raise _PendingJobContinuationError(
            "USAspending pending job receipt has an invalid poll count"
        )
    job_status = str(value.get("job_status") or "").strip().casefold()
    if job_status not in {"submitted", "ready", "running", "finished"}:
        raise _PendingJobContinuationError(
            "USAspending pending job receipt has an invalid job status"
        )
    if job_status == "submitted" and status_history:
        raise _PendingJobContinuationError(
            "USAspending submitted job receipt must have empty status history"
        )
    if job_status != "submitted" and (
        not status_history or job_status != status_history[-1]
    ):
        raise _PendingJobContinuationError(
            "USAspending pending job status does not match its status history"
        )
    return {
        **required_matches,
        "download_request": dict(expected_request),
        "job_requested_at_utc": _iso_utc(requested_at),
        "status_url": status_url,
        "file_name": file_name,
        "file_url": file_url,
        "job_status": job_status,
        "status_history": status_history,
        "status_poll_count": len(status_history),
    }


def _build_pending_job_receipt(
    *,
    run_day: date,
    request_payload: Mapping[str, Any],
    job_requested_at_utc: str,
    status_url: str,
    file_name: str,
    file_url: str,
    job_status: str,
    status_history: Sequence[str],
) -> dict[str, Any]:
    history = [str(item) for item in status_history]
    return {
        "schema_version": PENDING_JOB_SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "run_date": run_day.isoformat(),
        "download_request": dict(request_payload),
        "job_requested_at_utc": job_requested_at_utc,
        "status_url": status_url,
        "file_name": file_name,
        "file_url": file_url,
        "job_status": job_status,
        "status_history": history,
        "status_poll_count": len(history),
    }


def _persist_pending_job_journal(
    output_dir: Path,
    receipt: Mapping[str, Any],
    *,
    validation_status: str,
    written_at_utc: str,
    error: str | None = None,
) -> None:
    atomic_write_json(
        {
            "schema_version": PENDING_JOB_SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "run_date": receipt.get("run_date"),
            "state": "pending",
            "validation_status": validation_status,
            "written_at_utc": written_at_utc,
            "error": error,
            "receipt": dict(receipt),
        },
        output_dir / PENDING_JOB_JOURNAL_NAME,
        default=str,
    )


def _persist_completed_job_journal(
    output_dir: Path,
    receipt: Mapping[str, Any],
    *,
    completed_at_utc: str,
    snapshot_path: str,
    snapshot_sha256: str,
    manifest_path: str,
    manifest_sha256: str,
) -> None:
    """Retire one completed receipt with an idempotent, verifiable tombstone."""
    completed = {
        "schema_version": PENDING_JOB_SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "run_date": receipt.get("run_date"),
        "state": "completed",
        "validation_status": "validated",
        "written_at_utc": completed_at_utc,
        "completed_at_utc": completed_at_utc,
        "error": None,
        "receipt": dict(receipt),
        "completion": {
            "snapshot_path": snapshot_path,
            "snapshot_sha256": snapshot_sha256,
            "manifest_path": manifest_path,
            "manifest_sha256": manifest_sha256,
        },
    }
    journal_path = output_dir / PENDING_JOB_JOURNAL_NAME
    if journal_path.is_file():
        try:
            existing = json.loads(journal_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing == completed:
            return
    atomic_write_json(completed, journal_path, default=str)


def _validated_completed_job_journal(
    journal: Mapping[str, Any],
    *,
    journal_run_day: date,
    output_dir: Path,
    expected_request: Mapping[str, Any],
    attempted_at: datetime,
) -> None:
    completed_at = _parse_timestamp(journal.get("completed_at_utc"))
    if completed_at > attempted_at:
        raise _PendingJobContinuationError(
            "USAspending completed job journal is future-dated"
        )
    receipt = _validated_pending_job_continuation(
        journal.get("receipt"),
        run_day=journal_run_day,
        expected_request=expected_request,
        attempted_at=completed_at,
    )
    completion = journal.get("completion")
    if not isinstance(completion, Mapping):
        raise _PendingJobContinuationError(
            "USAspending completed job journal has no completion proof"
        )
    try:
        existing = _validated_existing_daily_snapshot(
            run_day=journal_run_day,
            output_dir=output_dir,
            expected_request=expected_request,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _PendingJobContinuationError(
            f"USAspending completed job journal cannot verify its snapshot: {exc}"
        ) from exc
    if existing is None:
        raise _PendingJobContinuationError(
            "USAspending completed job journal snapshot is missing"
        )
    expected_completion = {
        "snapshot_path": existing["snapshot_path"],
        "snapshot_sha256": existing["snapshot_sha256"],
        "manifest_path": existing["manifest_path"],
        "manifest_sha256": existing["manifest_sha256"],
    }
    if dict(completion) != expected_completion:
        raise _PendingJobContinuationError(
            "USAspending completed job journal proof does not match its snapshot"
        )
    if receipt["run_date"] != journal_run_day.isoformat():
        raise _PendingJobContinuationError(
            "USAspending completed job journal receipt date is invalid"
        )


def _load_pending_job_journal(
    *,
    requested_run_day: date,
    output_dir: Path,
    attempted_at: datetime,
) -> tuple[bool, dict[str, Any] | None]:
    journal_path = output_dir / PENDING_JOB_JOURNAL_NAME
    if not journal_path.exists():
        return False, None
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _PendingJobContinuationError(
            "USAspending pending job journal cannot be read safely"
        ) from exc
    if not isinstance(journal, Mapping):
        raise _PendingJobContinuationError(
            "USAspending pending job journal must be a JSON object"
        )
    if (
        journal.get("schema_version") != PENDING_JOB_SCHEMA_VERSION
        or journal.get("observer_name") != OBSERVER_NAME
    ):
        raise _PendingJobContinuationError(
            "USAspending pending job journal identity is invalid"
        )
    try:
        journal_run_day = _parse_run_date(journal.get("run_date"))
    except ValueError as exc:
        raise _PendingJobContinuationError(
            "USAspending pending job journal run_date is invalid"
        ) from exc
    if journal_run_day > requested_run_day:
        raise _PendingJobContinuationError(
            "USAspending pending job journal is future-dated"
        )
    expected_request = build_daily_transaction_download_request(journal_run_day)
    validation_status = str(
        journal.get("validation_status") or ""
    ).strip().casefold()
    if validation_status in {"invalid", "expired"}:
        raise _PendingJobContinuationError(
            str(journal.get("error") or "USAspending pending job journal is quarantined"),
            validation_status=validation_status,
        )
    if validation_status != "validated":
        raise _PendingJobContinuationError(
            "USAspending pending job journal validation state is invalid"
        )
    state = str(journal.get("state") or "pending").strip().casefold()
    if state == "completed":
        try:
            _validated_completed_job_journal(
                journal,
                journal_run_day=journal_run_day,
                output_dir=output_dir,
                expected_request=expected_request,
                attempted_at=attempted_at,
            )
        except _PendingJobContinuationError:
            raise
        except (TypeError, ValueError) as exc:
            raise _PendingJobContinuationError(
                f"USAspending completed job journal is invalid: {exc}"
            ) from exc
        return True, None
    if state != "pending":
        raise _PendingJobContinuationError(
            "USAspending pending job journal state is invalid"
        )
    try:
        continuation = _validated_pending_job_continuation(
            journal.get("receipt"),
            run_day=journal_run_day,
            expected_request=expected_request,
            attempted_at=attempted_at,
        )
    except _PendingJobContinuationError:
        raise
    except (TypeError, ValueError) as exc:
        raise _PendingJobContinuationError(
            f"USAspending pending job journal is invalid: {exc}"
        ) from exc
    return True, continuation


def _load_pending_job_continuation(
    *,
    requested_run_day: date,
    output_dir: Path,
    attempted_at: datetime,
) -> dict[str, Any] | None:
    journal_found, journal = _load_pending_job_journal(
        requested_run_day=requested_run_day,
        output_dir=output_dir,
        attempted_at=attempted_at,
    )
    if journal_found:
        return journal
    summary_path = output_dir / "latest_summary.json"
    if not summary_path.exists():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _PendingJobContinuationError(
            "USAspending producer health cannot be read safely"
        ) from exc
    if not isinstance(summary, Mapping):
        raise _PendingJobContinuationError(
            "USAspending producer health must be a JSON object"
        )
    health_raw = summary.get("producer_health")
    if not isinstance(health_raw, Mapping):
        if str(summary.get("status") or "").casefold() == "pending":
            raise _PendingJobContinuationError(
                "USAspending pending summary has no producer health receipt"
            )
        return None
    health = dict(health_raw)
    try:
        health_run_day = _parse_run_date(health.get("run_date"))
    except ValueError as exc:
        raise _PendingJobContinuationError(
            "USAspending pending producer health run_date is invalid"
        ) from exc
    if health_run_day > requested_run_day:
        raise _PendingJobContinuationError(
            "USAspending pending producer health is future-dated"
        )
    validation_status = str(
        health.get("pending_job_validation_status") or ""
    ).strip().casefold()
    if validation_status in {"invalid", "expired"}:
        raise _PendingJobContinuationError(
            str(health.get("error") or "USAspending pending job receipt is quarantined"),
            validation_status=validation_status,
        )
    if str(health.get("status") or "").strip().casefold() != "pending":
        return None
    try:
        return _validated_pending_job_continuation(
            health.get("pending_job"),
            run_day=health_run_day,
            expected_request=build_daily_transaction_download_request(
                health_run_day
            ),
            attempted_at=attempted_at,
        )
    except _PendingJobContinuationError:
        raise
    except (TypeError, ValueError) as exc:
        raise _PendingJobContinuationError(
            f"USAspending pending job receipt is invalid: {exc}"
        ) from exc


def _validated_existing_daily_snapshot(
    *,
    run_day: date,
    output_dir: Path,
    expected_request: Mapping[str, Any],
) -> dict[str, Any] | None:
    snapshot_path, manifest_path = _daily_snapshot_paths(output_dir, run_day)
    if not snapshot_path.exists() and not manifest_path.exists():
        return None
    if not snapshot_path.is_file() or not manifest_path.is_file():
        raise ValueError("dated USAspending snapshot/manifest pair is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, Mapping):
        raise ValueError("USAspending producer manifest must be a JSON object")
    required_matches = {
        "schema_version": PRODUCER_MANIFEST_SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "producer_mode": PRODUCER_MODE,
        "run_date": run_day.isoformat(),
        "api_url": DOWNLOAD_TRANSACTIONS_URL,
        "job_status": "finished",
        "frozen": True,
    }
    for key, expected in required_matches.items():
        if manifest.get(key) != expected:
            raise ValueError(f"USAspending manifest has invalid {key}")
    if manifest.get("download_request") != dict(expected_request):
        raise ValueError("USAspending manifest request does not match fixed contract")
    if Path(str(manifest.get("snapshot_path") or "")).resolve() != snapshot_path.resolve():
        raise ValueError("USAspending manifest snapshot_path does not match dated path")
    retrieved = _iso_utc(_parse_timestamp(manifest.get("retrieved_at_utc")))
    _iso_utc(_parse_timestamp(manifest.get("requested_at_utc")))
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot_sha = hashlib.sha256(snapshot_bytes).hexdigest()
    if snapshot_sha != manifest.get("raw_file_sha256"):
        raise ValueError("USAspending immutable snapshot SHA-256 mismatch")
    if len(snapshot_bytes) != manifest.get("raw_file_size_bytes"):
        raise ValueError("USAspending immutable snapshot size mismatch")
    validation = _validate_transaction_zip_payload(snapshot_bytes)
    if validation["row_count"] != manifest.get("row_count"):
        raise ValueError("USAspending manifest row_count mismatch")
    if validation["archive_member_rows"] != manifest.get("archive_member_rows"):
        raise ValueError("USAspending manifest archive member counts mismatch")
    return {
        "status": "ok",
        "run_date": run_day.isoformat(),
        "snapshot_path": str(snapshot_path),
        "retrieved_at_utc": retrieved,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _manifest_sha256(manifest_path),
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "download_status": "finished",
        "validation_status": "validated",
        "job_status": "finished",
        "row_count": validation["row_count"],
        "snapshot_sha256": snapshot_sha,
        "snapshot_size_bytes": len(snapshot_bytes),
        "requested_at_utc": manifest["requested_at_utc"],
        "download_request": dict(expected_request),
        "snapshot_reused": True,
        "zero_row_snapshot": validation["row_count"] == 0,
        "error": None,
    }


def _producer_non_ok_result(
    *,
    status: str,
    run_day: date,
    output_dir: Path,
    request_payload: Mapping[str, Any],
    requested_at_utc: str,
    job_status: str | None,
    error: str,
    poll_count: int = 0,
    attempt_poll_count: int = 0,
    attempted_at_utc: str | None = None,
    status_url: str | None = None,
    file_name: str | None = None,
    file_url: str | None = None,
    status_history: Sequence[str] | None = None,
    resumed_pending_job: bool = False,
    pending_job_validation_status: str | None = None,
) -> dict[str, Any]:
    snapshot_path, manifest_path = _daily_snapshot_paths(output_dir, run_day)
    history = [str(item) for item in (status_history or [])]
    pending_job = None
    if (
        status == "pending"
        and status_url is not None
        and file_name is not None
        and file_url is not None
        and job_status is not None
    ):
        pending_job = _build_pending_job_receipt(
            run_day=run_day,
            request_payload=request_payload,
            job_requested_at_utc=requested_at_utc,
            status_url=status_url,
            file_name=file_name,
            file_url=file_url,
            job_status=job_status,
            status_history=history,
        )
    return {
        "status": status,
        "run_date": run_day.isoformat(),
        "snapshot_path": None,
        "expected_snapshot_path": str(snapshot_path),
        "retrieved_at_utc": None,
        "manifest_path": None,
        "expected_manifest_path": str(manifest_path),
        "manifest_sha256": None,
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "download_status": job_status or status,
        "validation_status": "not_validated",
        "job_status": job_status,
        "row_count": None,
        "requested_at_utc": requested_at_utc,
        "job_requested_at_utc": requested_at_utc,
        "attempted_at_utc": attempted_at_utc or requested_at_utc,
        "download_request": dict(request_payload),
        "status_poll_count": poll_count,
        "attempt_poll_count": attempt_poll_count,
        "status_history": history,
        "status_url": status_url,
        "file_name": file_name,
        "file_url": file_url,
        "resumed_pending_job": resumed_pending_job,
        "pending_job_validation_status": pending_job_validation_status,
        "pending_job": pending_job,
        "snapshot_reused": False,
        "zero_row_snapshot": False,
        "error": error,
    }


def fetch_daily_transaction_snapshot(
    run_date: date | str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    http_post: Callable[..., Any] | None = None,
    http_get: Callable[..., Any] | None = None,
    sleep_fn: Callable[[float], Any] = time_lib.sleep,
    now_fn: Callable[[], datetime] | None = None,
    max_status_polls: int = DEFAULT_MAX_STATUS_POLLS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch, validate, and immutably freeze one official daily snapshot.

    Network and upstream failures are converted to ``pending`` or
    ``unavailable`` results so daily orchestration can persist fail-closed
    health without disrupting the strategy run.
    """
    requested_run_day = _parse_run_date(run_date)
    run_day = requested_run_day
    if max_status_polls < 1:
        raise ValueError("max_status_polls must be at least one")
    if poll_interval_seconds < 0 or http_timeout_seconds <= 0:
        raise ValueError("poll interval/HTTP timeout must be bounded and positive")
    output = Path(output_dir)
    request_payload = build_daily_transaction_download_request(run_day)
    clock = now_fn or (lambda: datetime.now(timezone.utc))
    attempted_at_dt = _parse_timestamp(clock())
    attempted_at = _iso_utc(attempted_at_dt)
    job_requested_at = attempted_at
    status_url: str | None = None
    file_name: str | None = None
    file_url: str | None = None
    status_history: list[str] = []
    resumed_pending_job = False
    job_status: str | None = None
    expired_pending_resume_error: str | None = None

    def persist_current_job(
        validation_status: str = "validated",
        error: str | None = None,
    ) -> bool:
        if (
            status_url is None
            or file_name is None
            or file_url is None
            or job_status is None
        ):
            return False
        receipt = _build_pending_job_receipt(
            run_day=run_day,
            request_payload=request_payload,
            job_requested_at_utc=job_requested_at,
            status_url=status_url,
            file_name=file_name,
            file_url=file_url,
            job_status=job_status,
            status_history=status_history,
        )
        _persist_pending_job_journal(
            output,
            receipt,
            validation_status=validation_status,
            written_at_utc=attempted_at,
            error=error,
        )
        return True

    try:
        try:
            continuation = _load_pending_job_continuation(
                requested_run_day=requested_run_day,
                output_dir=output,
                attempted_at=attempted_at_dt,
            )
        except _PendingJobContinuationError as exc:
            if exc.validation_status != "expired":
                raise
            expired_pending_resume_error = f"{type(exc).__name__}: {exc}"
            continuation = None
        if continuation is not None:
            resumed_pending_job = True
            run_day = _parse_run_date(continuation["run_date"])
            request_payload = dict(continuation["download_request"])
            job_requested_at = continuation["job_requested_at_utc"]
            status_url = continuation["status_url"]
            file_name = continuation["file_name"]
            file_url = continuation["file_url"]
            status_history = list(continuation["status_history"])
            job_status = continuation["job_status"]

        existing = _validated_existing_daily_snapshot(
            run_day=run_day,
            output_dir=output,
            expected_request=request_payload,
        )
        if existing is not None:
            existing["attempted_at_utc"] = attempted_at
            if continuation is not None:
                receipt = _build_pending_job_receipt(
                    run_day=run_day,
                    request_payload=request_payload,
                    job_requested_at_utc=job_requested_at,
                    status_url=status_url,
                    file_name=file_name,
                    file_url=file_url,
                    job_status=job_status,
                    status_history=status_history,
                )
                _persist_completed_job_journal(
                    output,
                    receipt,
                    completed_at_utc=existing["retrieved_at_utc"],
                    snapshot_path=existing["snapshot_path"],
                    snapshot_sha256=existing["snapshot_sha256"],
                    manifest_path=existing["manifest_path"],
                    manifest_sha256=existing["manifest_sha256"],
                )
                existing["resumed_pending_job"] = True
                existing["pending_job_validation_status"] = "validated"
            return existing

        get = http_get or _default_http_get
        if continuation is not None:
            persist_current_job()
        else:
            post = http_post or _default_http_post
            initial = _response_json_object(
                post(
                    DOWNLOAD_TRANSACTIONS_URL,
                    request_payload,
                    timeout=http_timeout_seconds,
                )
            )
            status_url = _validate_https_url(
                initial.get("status_url"),
                allowed_hosts={OFFICIAL_API_HOST},
                field_name="status_url",
            )
            file_name = _validate_remote_file_name(initial.get("file_name"))
            file_url = _validate_https_url(
                initial.get("file_url"),
                allowed_hosts=OFFICIAL_DOWNLOAD_HOSTS,
                field_name="file_url",
            )
            job_status = "submitted"
            persist_current_job()

        prior_poll_count = len(status_history)
        finished_payload: dict[str, Any] | None = (
            {} if job_status == "finished" else None
        )
        remaining_history_capacity = MAX_PENDING_STATUS_HISTORY - len(status_history)
        poll_budget = min(max_status_polls, max(0, remaining_history_capacity))
        for poll_index in range(poll_budget if finished_payload is None else 0):
            status_payload = _response_json_object(
                get(status_url, timeout=http_timeout_seconds)
            )
            job_status = str(status_payload.get("status") or "").strip().casefold()
            status_history.append(job_status or "missing")
            if job_status == "finished":
                persist_current_job()
                finished_payload = status_payload
                break
            if job_status == "failed":
                failure = "USAspending async download job failed"
                persist_current_job("invalid", failure)
                return _producer_non_ok_result(
                    status="unavailable",
                    run_day=run_day,
                    output_dir=output,
                    request_payload=request_payload,
                    requested_at_utc=job_requested_at,
                    attempted_at_utc=attempted_at,
                    job_status=job_status,
                    error=failure,
                    poll_count=len(status_history),
                    attempt_poll_count=len(status_history) - prior_poll_count,
                    status_url=status_url,
                    file_name=file_name,
                    file_url=file_url,
                    status_history=status_history,
                    resumed_pending_job=resumed_pending_job,
                    pending_job_validation_status="invalid",
                )
            if job_status not in {"ready", "running"}:
                failure = (
                    f"unexpected USAspending job status: {job_status or 'missing'}"
                )
                persist_current_job("invalid", failure)
                return _producer_non_ok_result(
                    status="unavailable",
                    run_day=run_day,
                    output_dir=output,
                    request_payload=request_payload,
                    requested_at_utc=job_requested_at,
                    attempted_at_utc=attempted_at,
                    job_status=job_status or None,
                    error=failure,
                    poll_count=len(status_history),
                    attempt_poll_count=len(status_history) - prior_poll_count,
                    status_url=status_url,
                    file_name=file_name,
                    file_url=file_url,
                    status_history=status_history,
                    resumed_pending_job=resumed_pending_job,
                    pending_job_validation_status="invalid",
                )
            persist_current_job()
            if poll_index + 1 < poll_budget:
                sleep_fn(poll_interval_seconds)

        if finished_payload is None:
            pending_error = (
                "USAspending pending job status history reached its bounded limit"
                if poll_budget == 0
                else "USAspending status poll budget exhausted"
            )
            persist_current_job()
            return _producer_non_ok_result(
                status="pending",
                run_day=run_day,
                output_dir=output,
                request_payload=request_payload,
                requested_at_utc=job_requested_at,
                attempted_at_utc=attempted_at,
                job_status=status_history[-1],
                error=pending_error,
                poll_count=len(status_history),
                attempt_poll_count=len(status_history) - prior_poll_count,
                status_url=status_url,
                file_name=file_name,
                file_url=file_url,
                status_history=status_history,
                resumed_pending_job=resumed_pending_job,
                pending_job_validation_status="validated",
            )

        finished_name = finished_payload.get("file_name")
        if finished_name not in (None, ""):
            if _validate_remote_file_name(finished_name) != file_name:
                failure = "USAspending job file_name changed while polling"
                persist_current_job("invalid", failure)
                return _producer_non_ok_result(
                    status="unavailable",
                    run_day=run_day,
                    output_dir=output,
                    request_payload=request_payload,
                    requested_at_utc=job_requested_at,
                    attempted_at_utc=attempted_at,
                    job_status=job_status,
                    error=failure,
                    poll_count=len(status_history),
                    attempt_poll_count=len(status_history) - prior_poll_count,
                    status_url=status_url,
                    file_name=file_name,
                    file_url=file_url,
                    status_history=status_history,
                    resumed_pending_job=resumed_pending_job,
                    pending_job_validation_status="invalid",
                )
        finished_url = finished_payload.get("file_url")
        if finished_url not in (None, ""):
            try:
                file_url = _validate_https_url(
                    finished_url,
                    allowed_hosts=OFFICIAL_DOWNLOAD_HOSTS,
                    field_name="file_url",
                )
            except ValueError as exc:
                failure = f"invalid finished USAspending file_url: {exc}"
                persist_current_job("invalid", failure)
                return _producer_non_ok_result(
                    status="unavailable",
                    run_day=run_day,
                    output_dir=output,
                    request_payload=request_payload,
                    requested_at_utc=job_requested_at,
                    attempted_at_utc=attempted_at,
                    job_status=job_status,
                    error=failure,
                    poll_count=len(status_history),
                    attempt_poll_count=len(status_history) - prior_poll_count,
                    status_url=status_url,
                    file_name=file_name,
                    file_url=file_url,
                    status_history=status_history,
                    resumed_pending_job=resumed_pending_job,
                    pending_job_validation_status="invalid",
                )
            persist_current_job()
        zip_payload = _response_bytes(
            get(file_url, timeout=http_timeout_seconds)
        )
        try:
            validation = _validate_transaction_zip_payload(zip_payload)
        except ValueError as exc:
            failure = f"invalid USAspending ZIP contract: {exc}"
            persist_current_job("invalid", failure)
            return _producer_non_ok_result(
                status="unavailable",
                run_day=run_day,
                output_dir=output,
                request_payload=request_payload,
                requested_at_utc=job_requested_at,
                attempted_at_utc=attempted_at,
                job_status=job_status,
                error=failure,
                poll_count=len(status_history),
                attempt_poll_count=len(status_history) - prior_poll_count,
                status_url=status_url,
                file_name=file_name,
                file_url=file_url,
                status_history=status_history,
                resumed_pending_job=resumed_pending_job,
                pending_job_validation_status="invalid",
            )
        retrieved_at_dt = _parse_timestamp(clock())
        if retrieved_at_dt < attempted_at_dt or retrieved_at_dt < _parse_timestamp(
            job_requested_at
        ):
            failure = "USAspending producer clock moved backward before retrieval"
            persist_current_job("invalid", failure)
            return _producer_non_ok_result(
                status="unavailable",
                run_day=run_day,
                output_dir=output,
                request_payload=request_payload,
                requested_at_utc=job_requested_at,
                attempted_at_utc=attempted_at,
                job_status=job_status,
                error=failure,
                poll_count=len(status_history),
                attempt_poll_count=len(status_history) - prior_poll_count,
                status_url=status_url,
                file_name=file_name,
                file_url=file_url,
                status_history=status_history,
                resumed_pending_job=resumed_pending_job,
                pending_job_validation_status="invalid",
            )
        retrieved_at = _iso_utc(retrieved_at_dt)
        snapshot_path, manifest_path = _daily_snapshot_paths(output, run_day)
        snapshot_sha = hashlib.sha256(zip_payload).hexdigest()
        manifest = {
            "schema_version": PRODUCER_MANIFEST_SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "producer_mode": PRODUCER_MODE,
            "source_mode": "official_producer",
            "run_date": run_day.isoformat(),
            "api_url": DOWNLOAD_TRANSACTIONS_URL,
            "download_request": request_payload,
            "requested_at_utc": job_requested_at,
            "attempted_at_utc": attempted_at,
            "retrieved_at_utc": retrieved_at,
            "status_url": status_url,
            "file_name": file_name,
            "file_url": file_url,
            "job_status": "finished",
            "status_history": status_history,
            "status_poll_count": len(status_history),
            "attempt_poll_count": len(status_history) - prior_poll_count,
            "resumed_pending_job": resumed_pending_job,
            "snapshot_path": str(snapshot_path),
            "raw_file_sha256": snapshot_sha,
            "raw_file_size_bytes": len(zip_payload),
            "row_count": validation["row_count"],
            "archive_member_rows": validation["archive_member_rows"],
            "resolved_required_headers": validation["resolved_required_headers"],
            "parser_required_columns": sorted(_REQUIRED_COLUMNS),
            "frozen": True,
        }
        manifest_payload = _json_bytes(manifest)
        _atomic_write_immutable_bytes(snapshot_path, zip_payload)
        _atomic_write_immutable_bytes(manifest_path, manifest_payload)
        completed_receipt = _build_pending_job_receipt(
            run_day=run_day,
            request_payload=request_payload,
            job_requested_at_utc=job_requested_at,
            status_url=status_url,
            file_name=file_name,
            file_url=file_url,
            job_status="finished",
            status_history=status_history,
        )
        _persist_completed_job_journal(
            output,
            completed_receipt,
            completed_at_utc=retrieved_at,
            snapshot_path=str(snapshot_path),
            snapshot_sha256=snapshot_sha,
            manifest_path=str(manifest_path),
            manifest_sha256=hashlib.sha256(manifest_payload).hexdigest(),
        )
        return {
            "status": "ok",
            "run_date": run_day.isoformat(),
            "snapshot_path": str(snapshot_path),
            "retrieved_at_utc": retrieved_at,
            "manifest_path": str(manifest_path),
            "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
            "producer_mode": PRODUCER_MODE,
            "source_mode": "official_producer",
            "download_status": "finished",
            "validation_status": "validated",
            "job_status": "finished",
            "row_count": validation["row_count"],
            "snapshot_sha256": snapshot_sha,
            "snapshot_size_bytes": len(zip_payload),
            "requested_at_utc": job_requested_at,
            "job_requested_at_utc": job_requested_at,
            "attempted_at_utc": attempted_at,
            "download_request": request_payload,
            "status_poll_count": len(status_history),
            "attempt_poll_count": len(status_history) - prior_poll_count,
            "status_history": status_history,
            "status_url": status_url,
            "file_name": file_name,
            "file_url": file_url,
            "resumed_pending_job": resumed_pending_job,
            "pending_job_validation_status": "validated",
            "pending_job": None,
            "snapshot_reused": False,
            "zero_row_snapshot": validation["row_count"] == 0,
            "error": None,
        }
    except _PendingJobContinuationError as exc:
        return _producer_non_ok_result(
            status="stale" if exc.validation_status == "expired" else "unavailable",
            run_day=run_day,
            output_dir=output,
            request_payload=request_payload,
            requested_at_utc=job_requested_at,
            attempted_at_utc=attempted_at,
            job_status=None,
            error=f"{type(exc).__name__}: {exc}",
            status_history=status_history,
            resumed_pending_job=False,
            pending_job_validation_status=exc.validation_status,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        receipt_retained = False
        try:
            receipt_retained = persist_current_job(error=error)
        except Exception as journal_exc:
            error = f"{error}; pending receipt persistence failed: {journal_exc}"
        if expired_pending_resume_error and not receipt_retained:
            return _producer_non_ok_result(
                status="stale",
                run_day=run_day,
                output_dir=output,
                request_payload=request_payload,
                requested_at_utc=job_requested_at,
                attempted_at_utc=attempted_at,
                job_status=None,
                error=f"{expired_pending_resume_error}; fresh request failed: {error}",
                status_history=status_history,
                resumed_pending_job=False,
                pending_job_validation_status="expired",
            )
        if receipt_retained:
            return _producer_non_ok_result(
                status="pending",
                run_day=run_day,
                output_dir=output,
                request_payload=request_payload,
                requested_at_utc=job_requested_at,
                attempted_at_utc=attempted_at,
                job_status=job_status,
                error=error,
                poll_count=len(status_history),
                attempt_poll_count=len(status_history),
                status_url=status_url,
                file_name=file_name,
                file_url=file_url,
                status_history=status_history,
                resumed_pending_job=resumed_pending_job,
                pending_job_validation_status="validated",
            )
        return _producer_non_ok_result(
            status="unavailable",
            run_day=run_day,
            output_dir=output,
            request_payload=request_payload,
            requested_at_utc=job_requested_at,
            attempted_at_utc=attempted_at,
            job_status=None,
            error=error,
            status_url=status_url,
            file_name=file_name,
            file_url=file_url,
            status_history=status_history,
            resumed_pending_job=resumed_pending_job,
        )


def _load_summary_for_health(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _verify_official_result_for_health(
    *,
    run_day: date,
    producer_result: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    if producer_result.get("producer_mode") != PRODUCER_MODE:
        raise ValueError("producer_mode is not the official daily producer")
    if producer_result.get("source_mode") != "official_producer":
        raise ValueError("source_mode is not an official producer snapshot")
    if producer_result.get("run_date") != run_day.isoformat():
        raise ValueError("producer result is stale for the requested run_date")
    expected_snapshot, expected_manifest = _daily_snapshot_paths(output_dir, run_day)
    if Path(str(producer_result.get("snapshot_path") or "")).resolve() != expected_snapshot.resolve():
        raise ValueError("producer snapshot path is not the immutable dated path")
    if Path(str(producer_result.get("manifest_path") or "")).resolve() != expected_manifest.resolve():
        raise ValueError("producer manifest path is not the immutable dated path")
    verified = _validated_existing_daily_snapshot(
        run_day=run_day,
        output_dir=output_dir,
        expected_request=build_daily_transaction_download_request(run_day),
    )
    if verified is None:
        raise ValueError("official producer snapshot/manifest is missing")
    if producer_result.get("manifest_sha256") != verified["manifest_sha256"]:
        raise ValueError("producer result manifest hash is absent or mismatched")
    if producer_result.get("snapshot_sha256") != verified["snapshot_sha256"]:
        raise ValueError("producer result snapshot hash is absent or mismatched")
    result_clock = _iso_utc(
        _parse_timestamp(producer_result.get("retrieved_at_utc"))
    )
    if result_clock != verified["retrieved_at_utc"]:
        raise ValueError("producer retrieval clock does not match immutable manifest")
    return verified


def persist_producer_health_summary(
    *,
    run_date: date | str,
    producer_result: Mapping[str, Any],
    observer_summary: Mapping[str, Any] | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    error: str | None = None,
) -> dict[str, Any]:
    """Merge fail-closed producer health into ``latest_summary.json``.

    Only an automatically produced snapshot whose immutable manifest, hashes,
    run date, and retrieval clock revalidate can emit a fresh heartbeat.  A
    configured local override remains parser-compatible but is explicitly
    unverified and cannot refresh producer health.
    """
    run_day = _parse_run_date(run_date)
    output = Path(output_dir)
    summary_path = output / "latest_summary.json"
    existing = _load_summary_for_health(summary_path)
    base = dict(observer_summary) if observer_summary is not None else dict(existing)
    producer = dict(producer_result)
    prior_health_raw = existing.get("producer_health")
    prior_health = (
        dict(prior_health_raw) if isinstance(prior_health_raw, Mapping) else {}
    )

    last_success_at = prior_health.get("last_success_at_utc")
    last_success_snapshot = prior_health.get("last_success_snapshot_path")
    last_success_manifest = prior_health.get("last_success_manifest_path")
    last_success_manifest_sha = prior_health.get("last_success_manifest_sha256")
    last_success_source = prior_health.get("last_success_source")

    producer_status = str(producer.get("status") or "missing").casefold()
    health_status = producer_status
    top_level_status = producer_status
    heartbeat_status = producer_status
    snapshot_fresh = False
    zero_event_heartbeat = False
    verification_error: str | None = None
    verified: dict[str, Any] | None = None

    if error:
        health_status = "unavailable"
        top_level_status = "unavailable"
        heartbeat_status = "observer_error"
        verification_error = error
    elif producer_status in {"missing", "pending", "unavailable", "stale"}:
        health_status = producer_status
        top_level_status = producer_status
        heartbeat_status = f"producer_{producer_status}"
        verification_error = str(producer.get("error") or "") or None
    elif producer_status != "ok":
        health_status = "unavailable"
        top_level_status = "unavailable"
        heartbeat_status = "producer_invalid_status"
        verification_error = f"unexpected producer status: {producer_status}"
    elif producer.get("producer_mode") != PRODUCER_MODE or producer.get(
        "source_mode"
    ) != "official_producer":
        health_status = "unverified_local_override"
        top_level_status = "unavailable"
        heartbeat_status = "unverified_local_override"
        verification_error = (
            "local snapshot override has no verified automatic producer manifest"
        )
    elif producer.get("run_date") != run_day.isoformat():
        health_status = "stale"
        top_level_status = "stale"
        heartbeat_status = "producer_stale"
        verification_error = "producer run_date does not match health run_date"
    else:
        try:
            verified = _verify_official_result_for_health(
                run_day=run_day,
                producer_result=producer,
                output_dir=output,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            health_status = "unavailable"
            top_level_status = "unavailable"
            heartbeat_status = "producer_manifest_unverified"
            verification_error = f"{type(exc).__name__}: {exc}"
        else:
            if observer_summary is None:
                health_status = "pending"
                top_level_status = "pending"
                heartbeat_status = "observer_pending"
                verification_error = "validated snapshot has not been observed"
            elif observer_summary.get("status") != "ok":
                health_status = "unavailable"
                top_level_status = "unavailable"
                heartbeat_status = "observer_unavailable"
                verification_error = "observer summary is not ok"
            elif int(verified.get("row_count") or 0) <= 0:
                health_status = "unavailable"
                top_level_status = "unavailable"
                heartbeat_status = "source_zero_rows"
                verification_error = (
                    "validated producer snapshot contains zero source rows"
                )
            elif observer_summary.get("parsed_transaction_count") != verified.get(
                "row_count"
            ):
                health_status = "unavailable"
                top_level_status = "unavailable"
                heartbeat_status = "observer_parse_count_mismatch"
                verification_error = (
                    "observer parsed_transaction_count does not match manifest row_count"
                )
            else:
                try:
                    observer_clock = _iso_utc(
                        _parse_timestamp(observer_summary.get("observed_at"))
                    )
                except (TypeError, ValueError) as exc:
                    health_status = "unavailable"
                    top_level_status = "unavailable"
                    heartbeat_status = "observer_clock_unverified"
                    verification_error = f"{type(exc).__name__}: {exc}"
                else:
                    if observer_clock != verified["retrieved_at_utc"]:
                        health_status = "unavailable"
                        top_level_status = "unavailable"
                        heartbeat_status = "observer_clock_manifest_mismatch"
                        verification_error = (
                            "observer observed_at is not manifest retrieved_at_utc"
                        )
                    else:
                        health_status = "ok"
                        top_level_status = "ok"
                        snapshot_fresh = True
                        new_forward = int(
                            observer_summary.get("new_forward_rows_appended") or 0
                        )
                        zero_event_heartbeat = new_forward == 0
                        heartbeat_status = (
                            "fresh_success_zero_forward"
                            if zero_event_heartbeat
                            else "fresh_success_new_forward"
                        )
                        last_success_at = verified["retrieved_at_utc"]
                        last_success_snapshot = verified["snapshot_path"]
                        last_success_manifest = verified["manifest_path"]
                        last_success_manifest_sha = verified["manifest_sha256"]
                        last_success_source = "official_producer_manifest"

    attempted_at = (
        producer.get("attempted_at_utc")
        or producer.get("requested_at_utc")
        or _iso_utc(datetime.now(timezone.utc))
    )
    parsed_transaction_count = (
        observer_summary.get("parsed_transaction_count")
        if observer_summary is not None
        else None
    )
    rows_appended = (
        observer_summary.get("rows_appended")
        if observer_summary is not None
        else None
    )
    new_forward_rows = (
        observer_summary.get("new_forward_rows_appended")
        if observer_summary is not None
        else None
    )
    health = {
        "schema_version": 1,
        "status": health_status,
        "run_date": run_day.isoformat(),
        "producer_mode": producer.get("producer_mode"),
        "source_mode": producer.get("source_mode"),
        "attempted_at_utc": attempted_at,
        "requested_at_utc": producer.get("requested_at_utc"),
        "job_requested_at_utc": (
            producer.get("job_requested_at_utc")
            or producer.get("requested_at_utc")
        ),
        "resumed_pending_job": bool(producer.get("resumed_pending_job")),
        "pending_job_validation_status": producer.get(
            "pending_job_validation_status"
        ),
        "status_poll_count": producer.get("status_poll_count"),
        "attempt_poll_count": producer.get("attempt_poll_count"),
        "pending_job": (
            dict(producer["pending_job"])
            if producer_status == "pending"
            and isinstance(producer.get("pending_job"), Mapping)
            else None
        ),
        "retrieved_at_utc": (
            verified.get("retrieved_at_utc") if verified is not None else None
        ),
        "download_status": producer.get("download_status") or producer_status,
        "validation_status": (
            "validated" if verified is not None else "unverified"
        ),
        "snapshot_fresh": snapshot_fresh,
        "snapshot_path": verified.get("snapshot_path") if verified else None,
        "snapshot_sha256": verified.get("snapshot_sha256") if verified else None,
        "manifest_path": verified.get("manifest_path") if verified else None,
        "manifest_sha256": (
            verified.get("manifest_sha256") if verified else None
        ),
        "snapshot_row_count": verified.get("row_count") if verified else None,
        "parsed_transaction_count": parsed_transaction_count,
        "rows_appended": rows_appended,
        "new_forward_rows_appended": new_forward_rows,
        "zero_event_heartbeat": zero_event_heartbeat,
        "heartbeat_status": heartbeat_status,
        "last_success_at_utc": last_success_at,
        "last_success_snapshot_path": last_success_snapshot,
        "last_success_manifest_path": last_success_manifest,
        "last_success_manifest_sha256": last_success_manifest_sha,
        "last_success_source": last_success_source,
        "error": verification_error,
        "observer_only": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
    }
    snapshot_age_days: int | None = None
    if health["retrieved_at_utc"]:
        snapshot_age_days = (
            run_day - _parse_timestamp(health["retrieved_at_utc"]).date()
        ).days
    base.update(
        {
            "status": top_level_status,
            "reason": heartbeat_status,
            "producer_health": health,
            "producer_health_status": health_status,
            "producer_status": health_status,
            "producer_mode": health["producer_mode"],
            "source_mode": health["source_mode"],
            "producer_attempted_at_utc": attempted_at,
            "producer_retrieved_at_utc": health["retrieved_at_utc"],
            "retrieved_at_utc": health["retrieved_at_utc"],
            "producer_manifest_path": health["manifest_path"],
            "manifest_path": health["manifest_path"],
            "producer_manifest_sha256": health["manifest_sha256"],
            "manifest_sha256": health["manifest_sha256"],
            "producer_download_status": health["download_status"],
            "producer_validation_status": health["validation_status"],
            "producer_job_requested_at_utc": health["job_requested_at_utc"],
            "producer_status_poll_count": health["status_poll_count"],
            "producer_attempt_poll_count": health["attempt_poll_count"],
            "resumed_pending_job": health["resumed_pending_job"],
            "pending_job_validation_status": health[
                "pending_job_validation_status"
            ],
            "snapshot_path": health["snapshot_path"],
            "snapshot_sha256": health["snapshot_sha256"],
            "raw_sha256": health["snapshot_sha256"],
            "snapshot_fresh": snapshot_fresh,
            "snapshot_age_days": snapshot_age_days,
            "zero_event_heartbeat": zero_event_heartbeat,
            "heartbeat_status": heartbeat_status,
            "last_producer_success_at_utc": last_success_at,
            "error": verification_error,
            "observer_only": True,
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        }
    )
    atomic_write_json(base, summary_path, default=str)
    return base


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
    prior_summary = _load_summary_for_health(summary_file)
    prior_producer_health = prior_summary.get("producer_health")
    if isinstance(prior_producer_health, Mapping):
        summary["producer_health"] = dict(prior_producer_health)
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
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RAW_DIR",
    "DEFAULT_RAW_ZIP_PATH",
    "DOWNLOAD_TRANSACTIONS_URL",
    "ELIGIBILITY_RULE",
    "EXPECTED_DEFAULT_RAW_ZIP_SHA256",
    "HISTORICAL_PIT_STATUS",
    "OBSERVER_NAME",
    "OUTPUT_ROOT",
    "PRODUCER_MODE",
    "RULE_VERSION",
    "build_daily_transaction_download_request",
    "fetch_daily_transaction_snapshot",
    "file_sha256",
    "main",
    "parse_usaspending_transaction_snapshot",
    "persist_daily_usaspending_obligation_observer",
    "persist_producer_health_summary",
    "persist_usaspending_obligation_observer",
    "run_observer",
]


if __name__ == "__main__":
    raise SystemExit(main())
