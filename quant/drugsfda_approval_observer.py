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
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse


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
OFFICIAL_DOWNLOAD_URL = "https://www.fda.gov/media/89850/download?attachment"
PRODUCER_MODE = "official_daily_drugsfda_download"
PRODUCER_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
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


def _parse_run_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid run_date value: {value!r}")


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


def _daily_snapshot_paths(output_root: Path, run_day: date) -> tuple[Path, Path]:
    suffix = run_day.strftime("%Y%m%d")
    raw_dir = output_root / "raw"
    return (
        raw_dir / f"drugsatfda_{suffix}.zip",
        raw_dir / f"snapshot_manifest_{suffix}.json",
    )


def _atomic_write_immutable_bytes(path: Path, payload: bytes) -> None:
    """Create an immutable artifact, accepting only an identical rerun."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise FileExistsError(f"immutable artifact already differs: {path}")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            if path.read_bytes() != payload:
                raise FileExistsError(f"immutable artifact raced and differs: {path}")
        else:
            os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True, default=str)
        + "\n"
    ).encode("utf-8")


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


def _validate_official_url(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host:
        raise ValueError(f"{field_name} must be an HTTPS FDA URL")
    if host != "fda.gov" and not host.endswith(".fda.gov"):
        raise ValueError(f"{field_name} left the official FDA host boundary: {host}")
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not contain URL credentials")
    return text


def _validate_snapshot_payload(payload: bytes) -> dict[str, Any]:
    if not payload:
        raise ValueError("Drugs@FDA download is empty")
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError(
            f"Drugs@FDA download exceeds {MAX_SNAPSHOT_BYTES} byte limit"
        )
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise ValueError(
                    f"Drugs@FDA ZIP has a corrupt member: {corrupt_member}"
                )
            table_rows: dict[str, int] = {}
            for member in sorted(_REQUIRED_COLUMNS):
                table_rows[member] = sum(1 for _ in _table_rows(archive, member))
            if any(count <= 0 for count in table_rows.values()):
                raise ValueError(
                    f"Drugs@FDA required table is empty: {table_rows}"
                )
            return {
                "archive_table_count": len(archive.namelist()),
                "required_table_rows": table_rows,
                "required_tables": sorted(_REQUIRED_COLUMNS),
            }
    except zipfile.BadZipFile as exc:
        raise ValueError("Drugs@FDA response is not a valid ZIP archive") from exc


def _manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_producer_snapshot_manifest(
    *,
    snapshot_path: str | Path,
    manifest_path: str | Path,
    run_date: Any | None = None,
) -> dict[str, Any]:
    """Revalidate one immutable official snapshot/manifest pair."""
    snapshot = Path(snapshot_path)
    manifest_file = Path(manifest_path)
    if not snapshot.is_file() or not manifest_file.is_file():
        raise FileNotFoundError("Drugs@FDA snapshot/manifest pair is incomplete")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, Mapping):
        raise ValueError("Drugs@FDA producer manifest must be a JSON object")
    expected = {
        "schema_version": PRODUCER_MANIFEST_SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "download_url": OFFICIAL_DOWNLOAD_URL,
        "frozen": True,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"Drugs@FDA producer manifest has invalid {key}")
    manifest_day = _parse_run_date(manifest.get("run_date"))
    if run_date is not None and manifest_day != _parse_run_date(run_date):
        raise ValueError("Drugs@FDA producer manifest is stale for run_date")
    expected_snapshot, expected_manifest = _daily_snapshot_paths(
        snapshot.parent.parent, manifest_day
    )
    if snapshot.resolve() != expected_snapshot.resolve():
        raise ValueError("Drugs@FDA snapshot path is not the dated canonical path")
    if manifest_file.resolve() != expected_manifest.resolve():
        raise ValueError("Drugs@FDA manifest path is not the dated canonical path")
    if Path(str(manifest.get("snapshot_path") or "")).resolve() != snapshot.resolve():
        raise ValueError("Drugs@FDA manifest snapshot_path mismatch")
    if Path(str(manifest.get("manifest_path") or "")).resolve() != manifest_file.resolve():
        raise ValueError("Drugs@FDA manifest manifest_path mismatch")
    _validate_official_url(manifest.get("resolved_download_url"), field_name="resolved_download_url")
    if not manifest.get("retrieved_at_utc") or not manifest.get("requested_at_utc"):
        raise ValueError("Drugs@FDA producer manifest is missing retrieval clocks")
    retrieved_at = _iso_utc(_parse_timestamp(manifest.get("retrieved_at_utc")))
    requested_at = _iso_utc(_parse_timestamp(manifest.get("requested_at_utc")))
    payload = snapshot.read_bytes()
    snapshot_sha = hashlib.sha256(payload).hexdigest()
    if snapshot_sha != manifest.get("raw_file_sha256"):
        raise ValueError("Drugs@FDA immutable snapshot SHA-256 mismatch")
    if len(payload) != manifest.get("raw_file_size_bytes"):
        raise ValueError("Drugs@FDA immutable snapshot size mismatch")
    validation = _validate_snapshot_payload(payload)
    if validation["required_table_rows"] != manifest.get("required_table_rows"):
        raise ValueError("Drugs@FDA manifest required-table counts mismatch")
    if validation["archive_table_count"] != manifest.get("archive_table_count"):
        raise ValueError("Drugs@FDA manifest archive table count mismatch")
    return {
        "status": "ok",
        "run_date": manifest_day.isoformat(),
        "snapshot_path": str(snapshot),
        "snapshot_sha256": snapshot_sha,
        "snapshot_size_bytes": len(payload),
        "manifest_path": str(manifest_file),
        "manifest_sha256": _manifest_sha256(manifest_file),
        "retrieved_at_utc": retrieved_at,
        "requested_at_utc": requested_at,
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "validation_status": "validated",
        **validation,
    }


def _default_http_get(url: str, *, timeout: float) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ginger-drugsfda-observer/1.0",
            "Accept": "application/zip, application/octet-stream;q=0.9, */*;q=0.1",
        },
        method="GET",
    )
    return urllib.request.urlopen(request, timeout=timeout)


def _download_response(
    response: Any,
) -> tuple[bytes, str, str | None, str | None]:
    if isinstance(response, (bytes, bytearray)):
        return bytes(response), OFFICIAL_DOWNLOAD_URL, None, None
    context = response if hasattr(response, "__enter__") else None
    opened = context.__enter__() if context is not None else response
    try:
        payload = opened.read(MAX_SNAPSHOT_BYTES + 1)
        final_url = (
            opened.geturl()
            if callable(getattr(opened, "geturl", None))
            else getattr(opened, "url", OFFICIAL_DOWNLOAD_URL)
        )
        headers = getattr(opened, "headers", None)
        last_modified = headers.get("Last-Modified") if headers is not None else None
        content_type = headers.get("Content-Type") if headers is not None else None
        return bytes(payload), str(final_url), last_modified, content_type
    finally:
        if context is not None:
            context.__exit__(None, None, None)
        elif callable(getattr(opened, "close", None)):
            opened.close()


def _producer_non_ok_result(
    *, run_day: date, output_root: Path, attempted_at: str, error: str
) -> dict[str, Any]:
    snapshot_path, manifest_path = _daily_snapshot_paths(output_root, run_day)
    return {
        "status": "unavailable",
        "reason": "official_download_or_validation_failed",
        "run_date": run_day.isoformat(),
        "producer_mode": PRODUCER_MODE,
        "source_mode": "official_producer",
        "download_url": OFFICIAL_DOWNLOAD_URL,
        "attempted_at_utc": attempted_at,
        "retrieved_at_utc": None,
        "snapshot_path": None,
        "expected_snapshot_path": str(snapshot_path),
        "manifest_path": None,
        "expected_manifest_path": str(manifest_path),
        "validation_status": "not_validated",
        "snapshot_fresh": False,
        "error": error,
    }


def fetch_daily_drugsfda_snapshot(
    run_date: Any,
    output_root: str | Path = OUTPUT_ROOT,
    *,
    http_get: Callable[..., Any] | None = None,
    now_fn: Callable[[], datetime] | None = None,
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Download, validate, and immutably freeze the official daily ZIP.

    Upstream and validation failures are returned as fail-closed health input;
    they never fall back to the historical seed ZIP.
    """
    run_day = _parse_run_date(run_date)
    output = Path(output_root)
    if http_timeout_seconds <= 0:
        raise ValueError("Drugs@FDA HTTP timeout must be positive")
    clock = now_fn or (lambda: datetime.now(timezone.utc))
    attempted_at = _iso_utc(_parse_timestamp(clock()))
    snapshot_path, manifest_path = _daily_snapshot_paths(output, run_day)
    try:
        if snapshot_path.exists() or manifest_path.exists():
            verified = validate_producer_snapshot_manifest(
                snapshot_path=snapshot_path,
                manifest_path=manifest_path,
                run_date=run_day,
            )
            return {
                **verified,
                "attempted_at_utc": attempted_at,
                "download_status": "reused_immutable_snapshot",
                "snapshot_reused": True,
                "snapshot_fresh": True,
                "error": None,
            }

        getter = http_get or _default_http_get
        response = getter(OFFICIAL_DOWNLOAD_URL, timeout=http_timeout_seconds)
        payload, resolved_url, last_modified, content_type = _download_response(response)
        _validate_official_url(resolved_url, field_name="resolved_download_url")
        validation = _validate_snapshot_payload(payload)
        retrieved_at = _iso_utc(_parse_timestamp(clock()))
        snapshot_sha = hashlib.sha256(payload).hexdigest()
        manifest = {
            "schema_version": PRODUCER_MANIFEST_SCHEMA_VERSION,
            "observer_name": OBSERVER_NAME,
            "producer_mode": PRODUCER_MODE,
            "source_mode": "official_producer",
            "run_date": run_day.isoformat(),
            "download_url": OFFICIAL_DOWNLOAD_URL,
            "resolved_download_url": resolved_url,
            "requested_at_utc": attempted_at,
            "retrieved_at_utc": retrieved_at,
            "source_last_modified": last_modified,
            "response_content_type": content_type,
            "snapshot_path": str(snapshot_path),
            "manifest_path": str(manifest_path),
            "raw_file_sha256": snapshot_sha,
            "raw_file_size_bytes": len(payload),
            "archive_table_count": validation["archive_table_count"],
            "required_table_rows": validation["required_table_rows"],
            "required_tables": validation["required_tables"],
            "point_in_time_contract": (
                "retrieved_at_utc is policy availability; source approval dates are metadata"
            ),
            "frozen": True,
        }
        manifest_payload = _json_bytes(manifest)
        _atomic_write_immutable_bytes(snapshot_path, payload)
        _atomic_write_immutable_bytes(manifest_path, manifest_payload)
        verified = validate_producer_snapshot_manifest(
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            run_date=run_day,
        )
        return {
            **verified,
            "attempted_at_utc": attempted_at,
            "download_status": "downloaded",
            "snapshot_reused": False,
            "snapshot_fresh": True,
            "error": None,
        }
    except Exception as exc:
        return _producer_non_ok_result(
            run_day=run_day,
            output_root=output,
            attempted_at=attempted_at,
            error=f"{type(exc).__name__}: {exc}",
        )


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
    availability_timestamp_source: str = "snapshot_retrieval_utc",
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
        "availability_timestamp_source": availability_timestamp_source,
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
    snapshot_manifest_path: str | Path | None = None,
    output_root: str | Path | None = None,
    observed_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Persist unseen application-level approvals to an append-only ledger.

    ``today`` labels the daily run only; it never supplies availability.
    Official production snapshots must supply ``snapshot_manifest_path``;
    ``first_seen_at`` is then bound to that immutable manifest's retrieval
    clock.  Explicit local replay snapshots may continue to supply
    ``observed_at`` directly.
    """
    output = Path(output_root) if output_root is not None else OUTPUT_ROOT
    source = Path(raw_zip_path) if raw_zip_path is not None else DEFAULT_RAW_ZIP_PATH
    if not source.is_file():
        raise FileNotFoundError(source)

    verified_manifest: dict[str, Any] | None = None
    availability_source = "snapshot_retrieval_utc"
    if snapshot_manifest_path is not None:
        verified_manifest = validate_producer_snapshot_manifest(
            snapshot_path=source,
            manifest_path=snapshot_manifest_path,
            run_date=today,
        )
        manifest_observed = _parse_timestamp(verified_manifest["retrieved_at_utc"])
        if observed_at is not None and _iso_utc(_parse_timestamp(observed_at)) != _iso_utc(
            manifest_observed
        ):
            raise ValueError(
                "observed_at does not match immutable Drugs@FDA producer manifest"
            )
        observed = manifest_observed
        availability_source = "immutable_producer_manifest_retrieval_utc"
    else:
        observed = _parse_timestamp(observed_at)
    as_of_date = _as_of_date(today, observed)

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
            availability_timestamp_source=availability_source,
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
        "source_snapshot_manifest_path": (
            str(snapshot_manifest_path) if snapshot_manifest_path is not None else None
        ),
        "source_snapshot_manifest_sha256": (
            verified_manifest.get("manifest_sha256")
            if verified_manifest is not None
            else None
        ),
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
        "availability_timestamp_source": availability_source,
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


def _load_summary_for_health(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def persist_producer_health_summary(
    *,
    run_date: Any,
    producer_result: Mapping[str, Any],
    observer_summary: Mapping[str, Any] | None = None,
    output_root: str | Path = OUTPUT_ROOT,
    error: str | None = None,
) -> dict[str, Any]:
    """Persist fail-closed producer health and an explicit zero-event heartbeat."""
    run_day = _parse_run_date(run_date)
    output = Path(output_root)
    summary_path = output / "latest_summary.json"
    existing = _load_summary_for_health(summary_path)
    base = dict(observer_summary) if observer_summary is not None else dict(existing)
    producer = dict(producer_result)
    prior_health_raw = existing.get("producer_health")
    prior_health = dict(prior_health_raw) if isinstance(prior_health_raw, Mapping) else {}

    producer_status = str(producer.get("status") or "missing").casefold()
    top_status = "unavailable"
    health_status = "unavailable"
    heartbeat_status = f"producer_{producer_status}"
    verification_error = error or str(producer.get("error") or "") or None
    verified: dict[str, Any] | None = None
    snapshot_fresh = False
    zero_event_heartbeat = False

    if error:
        heartbeat_status = "observer_or_producer_error"
    elif producer_status != "ok":
        heartbeat_status = f"producer_{producer_status}"
    elif producer.get("producer_mode") != PRODUCER_MODE or producer.get(
        "source_mode"
    ) != "official_producer":
        heartbeat_status = "unverified_local_override"
        verification_error = (
            "local snapshot override has no immutable official producer manifest"
        )
    else:
        try:
            verified = validate_producer_snapshot_manifest(
                snapshot_path=producer.get("snapshot_path"),
                manifest_path=producer.get("manifest_path"),
                run_date=run_day,
            )
            if producer.get("snapshot_sha256") != verified["snapshot_sha256"]:
                raise ValueError("producer result snapshot hash mismatch")
            if producer.get("manifest_sha256") != verified["manifest_sha256"]:
                raise ValueError("producer result manifest hash mismatch")
            producer_clock = _iso_utc(
                _parse_timestamp(producer.get("retrieved_at_utc"))
            )
            if producer_clock != verified["retrieved_at_utc"]:
                raise ValueError("producer result retrieval clock mismatch")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            verified = None
            heartbeat_status = "producer_manifest_unverified"
            verification_error = f"{type(exc).__name__}: {exc}"
        else:
            if observer_summary is None:
                heartbeat_status = "observer_pending"
                verification_error = "validated snapshot has not been consumed"
            elif observer_summary.get("status") != "ok":
                heartbeat_status = "observer_unavailable"
                verification_error = "observer summary is not ok"
            else:
                try:
                    observer_clock = _iso_utc(
                        _parse_timestamp(observer_summary.get("observed_at"))
                    )
                    if observer_clock != verified["retrieved_at_utc"]:
                        raise ValueError(
                            "observer clock does not match immutable manifest"
                        )
                    if (
                        observer_summary.get("source_snapshot_sha256")
                        != verified["snapshot_sha256"]
                    ):
                        raise ValueError("observer snapshot hash mismatch")
                    if (
                        observer_summary.get("source_snapshot_manifest_sha256")
                        != verified["manifest_sha256"]
                    ):
                        raise ValueError("observer manifest hash mismatch")
                    if int(observer_summary.get("parsed_application_count") or 0) <= 0:
                        raise ValueError("observer parsed zero eligible applications")
                except (TypeError, ValueError) as exc:
                    heartbeat_status = "observer_manifest_contract_failed"
                    verification_error = f"{type(exc).__name__}: {exc}"
                else:
                    top_status = "ok"
                    health_status = "ok"
                    snapshot_fresh = True
                    new_forward = int(
                        observer_summary.get("new_forward_event_count") or 0
                    )
                    zero_event_heartbeat = new_forward == 0
                    heartbeat_status = (
                        "fresh_success_zero_forward"
                        if zero_event_heartbeat
                        else "fresh_success_new_forward"
                    )
                    verification_error = None

    last_success_at = prior_health.get("last_success_at_utc")
    last_success_snapshot = prior_health.get("last_success_snapshot_path")
    last_success_manifest = prior_health.get("last_success_manifest_path")
    last_success_manifest_sha = prior_health.get("last_success_manifest_sha256")
    if health_status == "ok" and verified is not None:
        last_success_at = verified["retrieved_at_utc"]
        last_success_snapshot = verified["snapshot_path"]
        last_success_manifest = verified["manifest_path"]
        last_success_manifest_sha = verified["manifest_sha256"]

    health = {
        "schema_version": 1,
        "status": health_status,
        "run_date": run_day.isoformat(),
        "expected_cadence": "each_weekday_pipeline_run_after_fda_morning_refresh",
        "producer_mode": producer.get("producer_mode"),
        "source_mode": producer.get("source_mode"),
        "attempted_at_utc": producer.get("attempted_at_utc"),
        "retrieved_at_utc": verified.get("retrieved_at_utc") if verified else None,
        "download_status": producer.get("download_status") or producer_status,
        "validation_status": "validated" if verified else "unverified",
        "snapshot_fresh": snapshot_fresh,
        "snapshot_path": verified.get("snapshot_path") if verified else None,
        "snapshot_sha256": verified.get("snapshot_sha256") if verified else None,
        "manifest_path": verified.get("manifest_path") if verified else None,
        "manifest_sha256": verified.get("manifest_sha256") if verified else None,
        "parsed_application_count": (
            observer_summary.get("parsed_application_count")
            if observer_summary is not None
            else None
        ),
        "rows_appended": (
            observer_summary.get("rows_appended")
            if observer_summary is not None
            else None
        ),
        "new_forward_event_count": (
            observer_summary.get("new_forward_event_count")
            if observer_summary is not None
            else None
        ),
        "forward_event_count_total": (
            observer_summary.get("forward_event_count_total")
            if observer_summary is not None
            else None
        ),
        "zero_event_heartbeat": zero_event_heartbeat,
        "heartbeat_status": heartbeat_status,
        "last_success_at_utc": last_success_at,
        "last_success_snapshot_path": last_success_snapshot,
        "last_success_manifest_path": last_success_manifest,
        "last_success_manifest_sha256": last_success_manifest_sha,
        "error": verification_error,
        "observer_only": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
    }
    base.update(
        {
            "status": top_status,
            "reason": heartbeat_status,
            "producer_status": health_status,
            "producer_health_status": health_status,
            "producer_mode": producer.get("producer_mode"),
            "source_mode": producer.get("source_mode"),
            "producer_health": health,
            "producer_attempted_at_utc": health["attempted_at_utc"],
            "producer_retrieved_at_utc": health["retrieved_at_utc"],
            "producer_manifest_path": health["manifest_path"],
            "producer_manifest_sha256": health["manifest_sha256"],
            "producer_validation_status": health["validation_status"],
            "producer_download_status": health["download_status"],
            "snapshot_fresh": snapshot_fresh,
            "snapshot_age_days": 0 if snapshot_fresh else None,
            "zero_event_heartbeat": zero_event_heartbeat,
            "heartbeat_status": heartbeat_status,
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
    _atomic_write_json(summary_path, base)
    _atomic_write_json(output / "producer_health" / "latest.json", health)
    _atomic_write_json(
        output / "producer_health" / f"producer_health_{run_day:%Y%m%d}.json",
        health,
    )
    return base


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
    "OFFICIAL_DOWNLOAD_URL",
    "OBSERVER_NAME",
    "OUTPUT_ROOT",
    "PRODUCER_MODE",
    "RULE_VERSION",
    "application_id",
    "fetch_daily_drugsfda_snapshot",
    "file_sha256",
    "parse_drugsfda_approval_snapshot",
    "persist_daily_drugsfda_approval_observer",
    "persist_drugsfda_approval_observer",
    "persist_producer_health_summary",
    "validate_producer_snapshot_manifest",
]
