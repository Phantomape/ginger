"""Immutable, research-only SEC 8-K universe materialization for Ginger V2.

The bounded source population is the exact ``8-K`` subset of one SEC daily
form index.  Every row is retained and conservatively dispositioned against
the company/exchange association snapshot frozen in the same bundle.  This
module grants neither market-wide coverage nor paper/live eligibility.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import time
import urllib.request
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, time as datetime_time, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .data_paths import atomic_write_json
from .v2_contracts import (
    CalendarSession,
    EvidenceRecord,
    SecurityMappingSnapshot,
    SessionClock,
    SourceContract,
    UniverseEvent,
    V2ContractValidationError,
    calendar_session_snapshot_payload,
    canonical_hash,
    universe_input_snapshot_hash,
    validate_evidence_against_source,
    validate_session_clock_against_calendar,
    validate_universe_event_against_evidence,
    validate_universe_event_against_session_clocks,
)
from .v2_universe_coverage import (
    ExternalUniverseCoverageSnapshot,
    V2UniverseCoverageError,
    validate_external_universe_coverage_against_inputs,
)
from .v2_universe_ledger import (
    V2UniverseLedgerError,
    append_v2_universe_batch,
    build_universe_membership_manifest,
    load_v2_universe_ledger,
    validate_external_universe_coverage_against_manifest,
)


SCHEMA_VERSION = 1
BUNDLE_RECORD_TYPE = "v2_sec_8k_source_bundle"
MATERIALIZATION_RECORD_TYPE = "v2_sec_8k_universe_materialization"
FORM_TYPE = "8-K"
CALENDAR_ID = "SEC_EDGAR_BUSINESS_DAY"
CALENDAR_VERSION = "2026-official-calendar-v1"
CALENDAR_TIMEZONE = "America/New_York"
UNIVERSE_ID = "v2-sec-edgar-8k-forward-universe"
UNIVERSE_DEFINITION_ID = "sec-edgar-8k-forward-association-universe"
UNIVERSE_DEFINITION_VERSION = "1"
NORMALIZER_ID = "ginger-v2-sec-8k-universe"
NORMALIZER_VERSION = "1"
MAPPING_NORMALIZER_ID = "ginger-v2-sec-company-exchange-association"
MAPPING_NORMALIZER_VERSION = "1"
CALENDAR_NORMALIZER_ID = "ginger-v2-sec-edgar-business-day"
CALENDAR_NORMALIZER_VERSION = "1"

SEC_ACCESS_URL = (
    "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data"
)
SEC_FAQ_URL = "https://www.sec.gov/about/webmaster-frequently-asked-questions"
SEC_CALENDAR_URL = (
    "https://www.sec.gov/submit-filings/filer-support-resources/edgar-calendar"
)
SEC_MAPPING_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

_ARTIFACT_ROLES = {
    "sec_access.html": ("authorization_access", SEC_ACCESS_URL),
    "sec_webmaster_faq.html": ("authorization_reuse", SEC_FAQ_URL),
    "sec_edgar_calendar.html": ("calendar", SEC_CALENDAR_URL),
    "company_tickers_exchange.json": ("security_mapping", SEC_MAPPING_URL),
}
_EXPECTED_2026_CLOSURES = {
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-05-25",
    "2026-06-19",
    "2026-07-03",
    "2026-09-07",
    "2026-10-12",
    "2026-11-11",
    "2026-11-26",
    "2026-12-25",
}
_MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        start=1,
    )
}
_INDEX_NAME_RE = re.compile(r"^form\.(\d{8})\.idx$")
_FILING_PATH_RE = re.compile(
    r"^edgar/data/(?P<cik>\d+)/(?P<accession>\d{10}-\d{2}-\d{6})\.txt$"
)
_ACCEPTED_EXCHANGES = {"Nasdaq": "XNAS", "NYSE": "XNYS"}


class V2SEC8KUniverseError(RuntimeError):
    """SEC source materialization failed with a stable machine code."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.detail = str(message)
        super().__init__(f"[{self.code}] {self.detail}")


def _fail(code: str, message: str) -> None:
    raise V2SEC8KUniverseError(code, message)


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (V2ContractValidationError, V2UniverseCoverageError, V2UniverseLedgerError) as exc:
        raise V2SEC8KUniverseError(exc.code, exc.detail) from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _instant(value: str, *, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str):
        _fail("timezone_aware_instant_required", f"{field} must be an ISO instant")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise V2SEC8KUniverseError(
            "timezone_aware_instant_required", f"{field} is not a valid ISO instant"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail("timezone_aware_instant_required", f"{field} must include an offset")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json_bytes(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise V2SEC8KUniverseError("invalid_json_artifact", f"cannot parse {path}: {exc}") from exc


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        _fail("immutable_artifact_conflict", f"refusing to overwrite {path}")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


@contextmanager
def _exclusive_path_lock(path: Path, *, timeout_seconds: float = 10.0):
    """Serialize one immutable path transaction across cooperating publishers."""

    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + timeout_seconds
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - CI may exercise POSIX.
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, BlockingIOError) as exc:
                if time.monotonic() >= deadline:
                    raise V2SEC8KUniverseError(
                        "immutable_path_lock_timeout", f"timed out waiting for {lock_path}"
                    ) from exc
                time.sleep(0.02)
        yield
    finally:
        if locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _html_text(payload: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return " ".join(html.unescape(part) for part in parser.parts)


def _assert_official_policy_artifacts(artifacts: Mapping[str, bytes]) -> list[str]:
    access = _html_text(artifacts["sec_access.html"]).lower()
    if not (
        "monday through friday" in access
        and "6:00 a.m." in access
        and "10:00 p.m." in access
        and "10 requests/second" in access
        and "company_tickers_exchange.json" in access
    ):
        _fail("sec_access_policy_mismatch", "SEC access artifact lacks required hours/access facts")
    faq = _html_text(artifacts["sec_webmaster_faq.html"]).lower()
    research_use_stated = "investment research" in faq or (
        "research companies and funds" in faq and "research investments" in faq
    )
    if not ("free to access and reuse" in faq and research_use_stated and "user-agent" in faq):
        _fail("sec_reuse_policy_mismatch", "SEC FAQ artifact lacks required reuse/research facts")
    calendar = _html_text(artifacts["sec_edgar_calendar.html"])
    lowered = calendar.lower()
    if not (
        "federal holidays" in lowered
        and "2026" in lowered
        and "edgar" in lowered
        and ("not receive, process, or accept" in lowered or "not accept filings" in lowered)
    ):
        _fail("sec_calendar_policy_mismatch", "SEC calendar artifact lacks closure declaration")
    match = re.search(
        r"(?:Federal Holidays(?: in)? 2026|2026 Federal Holidays)(.*?)(?:Peak Filings|$)",
        calendar,
        flags=re.IGNORECASE,
    )
    if match is None:
        _fail("sec_calendar_parse_failed", "cannot isolate the 2026 closure table")
    closures = {
        f"2026-{_MONTHS[month.title()]:02d}-{int(day):02d}"
        for month, day in re.findall(
            r"(" + "|".join(_MONTHS) + r")\s+0?(\d{1,2})(?:,\s*2026)?",
            match.group(1),
            flags=re.IGNORECASE,
        )
    }
    if closures != _EXPECTED_2026_CLOSURES:
        _fail("sec_calendar_closure_mismatch", "2026 EDGAR closures were not enumerated exactly")
    return sorted(closures)


def _form_index_filename(form_date: str) -> str:
    if not re.fullmatch(r"\d{8}", form_date):
        _fail("invalid_form_date", "form_date must be YYYYMMDD")
    datetime.strptime(form_date, "%Y%m%d")
    return f"form.{form_date}.idx"


def _form_index_url(form_date: str) -> str:
    parsed = datetime.strptime(form_date, "%Y%m%d")
    quarter = (parsed.month - 1) // 3 + 1
    return (
        f"https://www.sec.gov/Archives/edgar/daily-index/{parsed.year}/"
        f"QTR{quarter}/form.{form_date}.idx"
    )


def _parse_daily_index(payload: bytes, *, form_date: str) -> list[dict[str, Any]]:
    try:
        lines = payload.decode("latin-1").splitlines()
    except UnicodeError as exc:  # pragma: no cover - latin-1 is total.
        raise V2SEC8KUniverseError("daily_index_decode_failed", str(exc)) from exc
    separators = [index for index, line in enumerate(lines) if re.fullmatch(r"-{80,}", line.strip())]
    if len(separators) != 1:
        _fail("daily_index_header_mismatch", "daily index must contain one field separator")
    index_date = datetime.strptime(form_date, "%Y%m%d")
    expected_received = f"{index_date:%b} {index_date.day}, {index_date.year}"
    header = "\n".join(lines[: separators[0]])
    if (
        "Description:           Daily Index of EDGAR Dissemination Feed by Form Type"
        not in header
        or f"Last Data Received:    {expected_received}" not in header
    ):
        _fail("daily_index_header_mismatch", "daily index identity header does not match its date")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines[separators[0] + 1 :], start=separators[0] + 2):
        if not line.strip():
            continue
        fields = re.split(r"\s{2,}", line.strip())
        if len(fields) != 5:
            _fail("daily_index_row_parse_failed", f"line {line_number} does not have five fields")
        form, company, cik, filed, filing_path = fields
        path_match = _FILING_PATH_RE.fullmatch(filing_path)
        try:
            datetime.strptime(filed, "%Y%m%d")
            valid_filed_date = True
        except ValueError:
            valid_filed_date = False
        if (
            not form
            or not company
            or not cik.isdigit()
            or not valid_filed_date
            or path_match is None
            or int(path_match.group("cik")) != int(cik)
        ):
            _fail("daily_index_row_parse_failed", f"line {line_number} is malformed")
        records.append(
            {
                "line_number": line_number,
                "form_type": form,
                "company_name": company,
                "cik": f"{int(cik):010d}",
                "date_filed": filed,
                "filing_path": filing_path,
                "accession": path_match.group("accession"),
            }
        )
    if not records:
        _fail("daily_index_empty", "daily index contains no filing rows")
    return records


def _parse_company_exchange(payload: bytes) -> list[dict[str, Any]]:
    try:
        raw = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise V2SEC8KUniverseError("company_exchange_parse_failed", str(exc)) from exc
    if not isinstance(raw, dict) or raw.get("fields") != ["cik", "name", "ticker", "exchange"]:
        _fail("company_exchange_schema_mismatch", "unexpected SEC company/exchange schema")
    data = raw.get("data")
    if not isinstance(data, list) or not data:
        _fail("company_exchange_schema_mismatch", "company/exchange data must be nonempty")
    result: list[dict[str, Any]] = []
    for ordinal, row in enumerate(data):
        if (
            not isinstance(row, list)
            or len(row) != 4
            or isinstance(row[0], bool)
            or not isinstance(row[0], int)
            or not isinstance(row[1], str)
            or not isinstance(row[2], str)
            or (row[3] is not None and not isinstance(row[3], str))
            or not row[1].strip()
            or not row[2].strip()
            or (isinstance(row[3], str) and not row[3].strip())
        ):
            _fail("company_exchange_row_parse_failed", f"association row {ordinal} is malformed")
        result.append(
            {
                "association_ordinal": ordinal,
                "cik": f"{row[0]:010d}",
                "name": row[1].strip(),
                "ticker": row[2].strip().upper(),
                "exchange": None if row[3] is None else row[3].strip(),
            }
        )
    return result


def _artifact_urls(form_date: str) -> dict[str, str]:
    result = {name: url for name, (_, url) in _ARTIFACT_ROLES.items()}
    result[_form_index_filename(form_date)] = _form_index_url(form_date)
    return result


def create_source_bundle_manifest(
    source_dir: str | Path,
    form_date: str,
    retrieved_at_by_artifact: Mapping[str, str],
    frozen_at: str,
    *,
    retrieval_metadata_by_artifact: Mapping[str, Mapping[str, Any]] | None = None,
    _lock_held: bool = False,
) -> dict[str, Any]:
    """Validate already-frozen members and create ``bundle.json`` last."""

    root = Path(source_dir).resolve()
    if not _lock_held:
        with _exclusive_path_lock(root / "bundle.json"):
            return create_source_bundle_manifest(
                root,
                form_date,
                retrieved_at_by_artifact,
                frozen_at,
                retrieval_metadata_by_artifact=retrieval_metadata_by_artifact,
                _lock_held=True,
            )
    urls = _artifact_urls(form_date)
    if set(retrieved_at_by_artifact) != set(urls):
        _fail("bundle_artifact_set_mismatch", "retrieval clocks must name every required artifact exactly")
    frozen_text, frozen_dt = _instant(frozen_at, field="frozen_at")
    index_date = datetime.strptime(form_date, "%Y%m%d").date()
    frozen_local_date = frozen_dt.astimezone(ZoneInfo(CALENDAR_TIMEZONE)).date()
    if index_date >= frozen_local_date:
        _fail(
            "daily_index_not_complete",
            "the SEC daily index date must strictly precede the bundle freeze date",
        )
    payloads: dict[str, bytes] = {}
    artifact_rows: list[dict[str, Any]] = []
    for filename in sorted(urls):
        path = root / filename
        if not path.is_file():
            _fail("source_artifact_missing", f"required source artifact is missing: {path}")
        payload = path.read_bytes()
        if not payload:
            _fail("source_artifact_empty", f"required source artifact is empty: {path}")
        payloads[filename] = payload
        retrieved_text, retrieved_dt = _instant(
            retrieved_at_by_artifact[filename], field=f"retrieved_at.{filename}"
        )
        if retrieved_dt > frozen_dt:
            _fail("artifact_retrieved_after_freeze", f"{filename} was retrieved after bundle freeze")
        metadata = dict((retrieval_metadata_by_artifact or {}).get(filename, {}))
        request_headers = dict(metadata.get("request_headers", {}))
        if (
            set(request_headers) != {"User-Agent", "Accept-Encoding"}
            or not isinstance(request_headers["User-Agent"], str)
            or "@" not in request_headers["User-Agent"]
            or request_headers["User-Agent"] != request_headers["User-Agent"].strip()
            or request_headers["Accept-Encoding"] != "identity"
        ):
            _fail(
                "declared_request_headers_required",
                f"{filename} must retain its declared SEC User-Agent and identity encoding",
            )
        response_headers = dict(metadata.get("response_headers", {}))
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in response_headers.items()):
            _fail("invalid_response_headers", f"{filename} response headers must be strings")
        http_status = metadata.get("http_status")
        if http_status != 200:
            _fail("invalid_http_status", f"{filename} must retain a successful HTTP 200 status")
        role = "daily_form_index" if _INDEX_NAME_RE.fullmatch(filename) else _ARTIFACT_ROLES[filename][0]
        artifact_rows.append(
            {
                "role": role,
                "filename": filename,
                "url": urls[filename],
                "retrieved_at": retrieved_text,
                "sha256": _sha256_bytes(payload),
                "bytes": len(payload),
                "http_status": http_status,
                "request_headers": dict(sorted(request_headers.items())),
                "response_headers": dict(sorted(response_headers.items())),
            }
        )
    closures = _assert_official_policy_artifacts(payloads)
    index_rows = _parse_daily_index(payloads[_form_index_filename(form_date)], form_date=form_date)
    association_rows = _parse_company_exchange(payloads["company_tickers_exchange.json"])
    exact_rows = [row for row in index_rows if row["form_type"] == FORM_TYPE]
    if not exact_rows:
        _fail("exact_8k_population_empty", "daily index contains no exact 8-K rows")
    policy = {
        "form_type": FORM_TYPE,
        "form_match": "exact_case_sensitive",
        "daily_index_completion": (
            "index_date_strictly_precedes_bundle_freeze_date_in_America/New_York"
        ),
        "association_join": "zero_padded_cik_exact",
        "association_cardinality": "exactly_one_required",
        "accepted_exchanges": dict(sorted(_ACCEPTED_EXCHANGES.items())),
        "security_identity": "research_only_cik_plus_ticker_association",
        "listing_identity": "research_only_cik_plus_ticker_plus_mic_association",
        "mapping_effective_from": "company_exchange_artifact_retrieved_at",
        "row_known_at": "max(daily_index_retrieved_at,company_exchange_retrieved_at)",
        "limitations": [
            "CIK identifies an issuer, not every security or share class.",
            "The SEC association file does not guarantee association accuracy or scope.",
            "This bounded source coverage is not market-wide coverage.",
        ],
    }
    core = {
        "form_date": form_date,
        "artifact_identities": artifact_rows,
        "disposition_policy": policy,
        "calendar_closures_2026": closures,
    }
    revision_id = canonical_hash(core)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": BUNDLE_RECORD_TYPE,
        "bundle_id": f"sec-edgar-8k-{form_date}-{revision_id[:16]}",
        "revision_id": revision_id,
        "form_date": form_date,
        "form_type": FORM_TYPE,
        "artifacts": artifact_rows,
        "daily_index_total_rows": len(index_rows),
        "exact_form_rows": len(exact_rows),
        "company_exchange_rows": len(association_rows),
        "calendar_closures_2026": closures,
        "disposition_policy": policy,
        "frozen_at": frozen_text,
        "pit_tier": "research_pit",
        "authority": "research_only",
        "trade_enabled": False,
    }
    manifest["bundle_sha256"] = canonical_hash(manifest)
    target = root / "bundle.json"
    if target.exists():
        existing = _json_bytes(target)
        if existing != manifest:
            _fail("immutable_bundle_manifest_conflict", f"refusing to overwrite {target}")
    else:
        atomic_write_json(manifest, target, indent=2, ensure_ascii=False)
    return manifest


def freeze_sec_8k_source_bundle(
    output_dir: str | Path,
    form_date: str,
    user_agent: str,
) -> dict[str, Any]:
    """Fetch five official SEC artifacts and freeze their retrieval metadata."""

    if not isinstance(user_agent, str) or "@" not in user_agent or len(user_agent.strip()) < 8:
        _fail("declared_user_agent_required", "SEC retrieval requires a declared contact user-agent")
    root = Path(output_dir).resolve()
    if (root / "bundle.json").exists():
        _, existing, _ = _load_source_bundle(root)
        if existing["form_date"] != form_date:
            _fail("immutable_bundle_manifest_conflict", "existing bundle has another form date")
        return {"status": "duplicate", "source_dir": str(root), "bundle": existing}
    urls = _artifact_urls(form_date)
    retrievals: dict[str, str] = {}
    metadata: dict[str, dict[str, Any]] = {}
    downloaded: dict[str, bytes] = {}
    for index, (filename, url) in enumerate(sorted(urls.items())):
        if index:
            time.sleep(0.16)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": user_agent.strip(), "Accept-Encoding": "identity"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                status = int(getattr(response, "status", 200))
                headers = {
                    key: value
                    for key in ("Content-Type", "Content-Length", "ETag", "Last-Modified")
                    if (value := response.headers.get(key)) is not None
                }
        except OSError as exc:
            raise V2SEC8KUniverseError("sec_download_failed", f"{url}: {exc}") from exc
        if status != 200 or not payload:
            _fail("sec_download_failed", f"{url} returned status {status} or an empty body")
        downloaded[filename] = payload
        retrievals[filename] = _utc_now()
        metadata[filename] = {
            "http_status": status,
            "request_headers": {
                "User-Agent": user_agent.strip(),
                "Accept-Encoding": "identity",
            },
            "response_headers": headers,
        }
    frozen_at = _utc_now()
    existing_after_wait = False
    with _exclusive_path_lock(root / "bundle.json"):
        if (root / "bundle.json").exists():
            existing_after_wait = True
        else:
            for filename, payload in downloaded.items():
                _atomic_write_bytes(root / filename, payload)
            manifest = create_source_bundle_manifest(
                root,
                form_date,
                retrievals,
                frozen_at,
                retrieval_metadata_by_artifact=metadata,
                _lock_held=True,
            )
    if existing_after_wait:
        _, existing, _ = _load_source_bundle(root)
        if existing["form_date"] != form_date:
            _fail("immutable_bundle_manifest_conflict", "existing bundle has another form date")
        return {"status": "duplicate", "source_dir": str(root), "bundle": existing}
    return {"status": "frozen", "source_dir": str(root), "bundle": manifest}


def _load_source_bundle(source_dir: str | Path) -> tuple[Path, dict[str, Any], dict[str, bytes]]:
    root = Path(source_dir).resolve()
    manifest_path = root / "bundle.json"
    if not manifest_path.is_file():
        _fail("source_bundle_manifest_missing", f"source bundle manifest is missing: {manifest_path}")
    raw = _json_bytes(manifest_path)
    if not isinstance(raw, dict):
        _fail("source_bundle_manifest_invalid", "bundle.json must be an object")
    required = {
        "schema_version", "record_type", "bundle_id", "revision_id", "form_date",
        "form_type", "artifacts", "daily_index_total_rows", "exact_form_rows",
        "company_exchange_rows", "calendar_closures_2026", "disposition_policy",
        "frozen_at", "pit_tier", "authority", "trade_enabled", "bundle_sha256",
    }
    if set(raw) != required or raw.get("schema_version") != SCHEMA_VERSION:
        _fail("source_bundle_manifest_invalid", "bundle.json must have the exact v1 fields")
    if raw.get("record_type") != BUNDLE_RECORD_TYPE or raw.get("form_type") != FORM_TYPE:
        _fail("source_bundle_manifest_invalid", "bundle type or exact form scope changed")
    if raw.get("pit_tier") != "research_pit" or raw.get("authority") != "research_only":
        _fail("source_bundle_boundary_violation", "bundle must remain research-only")
    if raw.get("trade_enabled") is not False:
        _fail("trade_enabled_forbidden", "source bundle must remain default-off")
    hash_payload = deepcopy(raw)
    supplied_hash = hash_payload.pop("bundle_sha256", None)
    if supplied_hash != canonical_hash(hash_payload):
        _fail("source_bundle_hash_mismatch", "bundle_sha256 is incorrect")
    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, list):
        _fail("source_bundle_manifest_invalid", "artifacts must be a list")
    retrieved: dict[str, str] = {}
    retrieval_metadata: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            _fail("source_bundle_manifest_invalid", "artifact entries must be objects")
        expected = {
            "role", "filename", "url", "retrieved_at", "sha256", "bytes",
            "http_status", "request_headers", "response_headers",
        }
        if set(item) != expected or item["filename"] in retrieved:
            _fail("source_bundle_manifest_invalid", "artifact entries changed shape or identity")
        retrieved[item["filename"]] = item["retrieved_at"]
        retrieval_metadata[item["filename"]] = {
            "http_status": item["http_status"],
            "request_headers": item["request_headers"],
            "response_headers": item["response_headers"],
        }
        member_path = root / item["filename"]
        if not member_path.is_file():
            _fail("source_artifact_missing", f"required source artifact is missing: {member_path}")
        member_payload = member_path.read_bytes()
        if (
            len(member_payload) != item["bytes"]
            or _sha256_bytes(member_payload) != item["sha256"]
        ):
            _fail("source_artifact_sha256_mismatch", f"frozen artifact changed: {member_path}")
    rebuilt = create_source_bundle_manifest(
        root,
        raw["form_date"],
        retrieved,
        raw["frozen_at"],
        retrieval_metadata_by_artifact=retrieval_metadata,
    )
    if rebuilt != raw:
        _fail("source_bundle_manifest_mismatch", "bundle metadata does not match its raw members")
    payloads = {item["filename"]: (root / item["filename"]).read_bytes() for item in artifacts}
    return root, raw, payloads


def _artifact(manifest: Mapping[str, Any], role: str) -> dict[str, Any]:
    matches = [item for item in manifest["artifacts"] if item["role"] == role]
    if len(matches) != 1:
        _fail("source_bundle_role_mismatch", f"bundle must contain one {role} artifact")
    return dict(matches[0])


def _seal_source(payload: dict[str, Any]) -> SourceContract:
    payload["raw_identity_fields"] = sorted(payload["raw_identity_fields"])
    payload["decision_content_fields"] = sorted(payload["decision_content_fields"])
    payload["permitted_uses"] = sorted(payload["permitted_uses"])
    payload["source_contract_hash"] = canonical_hash(payload)
    return _call(SourceContract.from_dict, payload)


def _seal_evidence(payload: dict[str, Any]) -> EvidenceRecord:
    payload["decision_content_sha256"] = canonical_hash(payload["decision_content"])
    semantic_payload = deepcopy(payload)
    semantic_payload.pop("recorded_at")
    payload["semantic_hash"] = canonical_hash(semantic_payload)
    payload["record_hash"] = canonical_hash(payload)
    return _call(EvidenceRecord.from_dict, payload)


def _seal_mapping(payload: dict[str, Any]) -> SecurityMappingSnapshot:
    payload["mapping_sha256"] = canonical_hash(payload)
    return _call(SecurityMappingSnapshot.from_dict, payload)


def _seal_clock(payload: dict[str, Any]) -> SessionClock:
    semantic_payload = deepcopy(payload)
    semantic_payload.pop("recorded_at")
    payload["semantic_hash"] = canonical_hash(semantic_payload)
    payload["record_hash"] = canonical_hash(payload)
    return _call(SessionClock.from_dict, payload)


def _seal_event(payload: dict[str, Any]) -> UniverseEvent:
    payload["evidence_record_ids"] = sorted(payload["evidence_record_ids"])
    semantic_payload = deepcopy(payload)
    semantic_payload.pop("recorded_at")
    payload["semantic_hash"] = canonical_hash(semantic_payload)
    payload["event_hash"] = canonical_hash(payload)
    return _call(UniverseEvent.from_dict, payload)


def _seal_coverage(payload: dict[str, Any]) -> ExternalUniverseCoverageSnapshot:
    semantic_payload = deepcopy(payload)
    semantic_payload.pop("recorded_at")
    payload["semantic_hash"] = canonical_hash(semantic_payload)
    payload["record_hash"] = canonical_hash(payload)
    return _call(ExternalUniverseCoverageSnapshot.from_dict, payload)


def _source_contract(
    *,
    source_contract_id: str,
    provider: str,
    source_name: str,
    source_kind: str,
    source_locator: str,
    raw_identity_fields: Sequence[str],
    decision_content_fields: Sequence[str],
    authorization_reference: str,
    authorization_sha256: str,
    availability_reference: str,
    source_timezone: str,
    decision_calendar: str,
    revision_policy: str,
    revision_id_field: str,
    security_mapping_policy: str,
    normalizer_id: str,
    normalizer_version: str,
    effective_from: str,
    created_at: str,
) -> SourceContract:
    return _seal_source(
        {
            "schema_version": 1,
            "record_type": "v2_source_contract",
            "source_contract_id": source_contract_id,
            "contract_version": "1",
            "provider": provider,
            "source_name": source_name,
            "source_kind": source_kind,
            "source_locator": source_locator,
            "raw_identity_fields": list(raw_identity_fields),
            "decision_content_fields": list(decision_content_fields),
            "authorization_status": "pass",
            "authorization_reference": authorization_reference,
            "authorization_evidence_sha256": authorization_sha256,
            "permitted_uses": ["research"],
            "availability_status": "pass",
            "availability_reference": availability_reference,
            "source_timezone": source_timezone,
            "observed_at_rule": "immutable bundle member retrieval clock",
            "published_at_rule": "not used; no source-declared publication field",
            "published_at_field": None,
            "known_at_rule": "no earlier than the last required raw member retrieval",
            "decision_calendar": decision_calendar,
            "session_assignment_rule": "explicit evidence-bound SEC EDGAR business-day session",
            "revision_policy": revision_policy,
            "revision_id_field": revision_id_field,
            "security_mapping_policy": security_mapping_policy,
            "normalizer_id": normalizer_id,
            "normalizer_version": normalizer_version,
            "adjustment_policy": "none",
            "replay_daily_parity_status": "unknown",
            "maximum_pit_tier": "research_pit",
            "known_future_leakage": False,
            "effective_from": effective_from,
            "effective_to": None,
            "created_at": created_at,
            "trade_enabled": False,
        }
    )


def _evidence(
    *,
    evidence_id: str,
    source: SourceContract,
    raw_identity: Mapping[str, Any],
    raw_artifact_locator: str,
    raw_artifact_sha256: str,
    decision_content: Mapping[str, Any],
    observed_at: str,
    known_at: str,
    effective_from: str,
    revision_id: str,
    recorded_at: str,
    security_scope: str = "not_applicable",
    security_mapping: SecurityMappingSnapshot | None = None,
) -> EvidenceRecord:
    return _seal_evidence(
        {
            "schema_version": 1,
            "record_type": "v2_evidence_record",
            "evidence_id": evidence_id,
            "source_contract_id": source.source_contract_id,
            "source_contract_hash": source.source_contract_hash,
            "raw_identity": dict(raw_identity),
            "raw_artifact_locator": raw_artifact_locator,
            "raw_artifact_sha256": raw_artifact_sha256,
            "decision_content": deepcopy(dict(decision_content)),
            "normalizer_id": source.normalizer_id,
            "normalizer_version": source.normalizer_version,
            "source_timezone": source.source_timezone,
            "observed_at": observed_at,
            "published_at": None,
            "known_at": known_at,
            "known_at_basis": source.known_at_rule,
            "effective_from": effective_from,
            "effective_to": None,
            "revision_id": revision_id,
            "supersedes_evidence_id": None,
            "security_scope": security_scope,
            "security_mapping_kind": (
                "effective_dated" if security_mapping is not None else "not_applicable"
            ),
            "security_mapping": (
                None if security_mapping is None else security_mapping.to_dict()
            ),
            "authorization_status": source.authorization_status,
            "authorization_evidence_sha256": source.authorization_evidence_sha256,
            "pit_tier": "research_pit",
            "known_future_leakage": False,
            "recorded_at": recorded_at,
            "trade_enabled": False,
        }
    )


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result:
        _fail("invalid_identity_component", "identity component normalized to empty")
    return result


def _session_for_freeze(frozen_at: str, closures: Sequence[str]) -> tuple[dict[str, Any], str]:
    frozen_text, frozen_dt = _instant(frozen_at, field="bundle.frozen_at")
    zone = ZoneInfo(CALENDAR_TIMEZONE)
    local_date = frozen_dt.astimezone(zone).date()
    session_date = local_date.isoformat()
    if local_date.year != 2026 or local_date.weekday() >= 5 or session_date in set(closures):
        _fail("sec_session_not_open", "bundle freeze is not on a proved 2026 SEC business day")
    open_dt = datetime.combine(local_date, datetime_time(6, 0), tzinfo=zone)
    close_dt = datetime.combine(local_date, datetime_time(22, 0), tzinfo=zone)
    if not (open_dt <= frozen_dt < close_dt):
        _fail("sec_session_not_open", "bundle freeze must be inside official SEC operating hours")
    session = {
        "calendar_session_id": f"sec-edgar-{session_date}",
        "session_date": session_date,
        "open_at": open_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "close_at": close_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "session_kind": "regular",
    }
    _call(CalendarSession.from_dict, session, calendar_timezone=CALENDAR_TIMEZONE)
    return session, frozen_text


def _validate_bundle_artifact_binding(
    evidence: EvidenceRecord,
    *,
    root: Path,
    bundle: Mapping[str, Any],
) -> None:
    prefix = f"bundle:{bundle['bundle_id']}/"
    if not evidence.raw_artifact_locator.startswith(prefix):
        _fail("bundle_artifact_locator_mismatch", "evidence does not use its logical bundle locator")
    filename = evidence.raw_artifact_locator[len(prefix) :]
    allowed = {"bundle.json", *(item["filename"] for item in bundle["artifacts"])}
    if filename not in allowed or Path(filename).name != filename:
        _fail("bundle_artifact_locator_mismatch", "evidence resolves outside the frozen bundle")
    path = root / filename
    if not path.is_file() or _sha256_bytes(path.read_bytes()) != evidence.raw_artifact_sha256:
        _fail("bundle_artifact_sha256_mismatch", f"evidence raw hash does not resolve: {filename}")


def build_sec_8k_materialization(source_dir: str | Path) -> dict[str, Any]:
    """Build and fully cross-validate one deterministic materialization envelope."""

    root, bundle, payloads = _load_source_bundle(source_dir)
    bundle_artifact_sha = _sha256_bytes((root / "bundle.json").read_bytes())
    index_artifact = _artifact(bundle, "daily_form_index")
    mapping_artifact = _artifact(bundle, "security_mapping")
    access_artifact = _artifact(bundle, "authorization_access")
    faq_artifact = _artifact(bundle, "authorization_reuse")
    calendar_artifact = _artifact(bundle, "calendar")
    index_rows = _parse_daily_index(
        payloads[index_artifact["filename"]], form_date=bundle["form_date"]
    )
    associations = _parse_company_exchange(payloads[mapping_artifact["filename"]])
    exact_rows = [row for row in index_rows if row["form_type"] == FORM_TYPE]
    if (
        len(index_rows) != bundle["daily_index_total_rows"]
        or len(exact_rows) != bundle["exact_form_rows"]
        or len(associations) != bundle["company_exchange_rows"]
    ):
        _fail("source_bundle_count_mismatch", "raw source counts changed after bundle freeze")

    frozen_at = bundle["frozen_at"]
    calendar_session, frozen_at = _session_for_freeze(
        frozen_at, bundle["calendar_closures_2026"]
    )
    run_date = calendar_session["session_date"]
    retrieval_clock = {item["role"]: item["retrieved_at"] for item in bundle["artifacts"]}
    coverage_known = max(
        retrieval_clock["daily_form_index"], retrieval_clock["security_mapping"]
    )
    mapping_known = retrieval_clock["security_mapping"]
    calendar_known = max(retrieval_clock["authorization_access"], retrieval_clock["calendar"])
    for label, value in (
        ("coverage_known", coverage_known),
        ("mapping_known", mapping_known),
        ("calendar_known", calendar_known),
    ):
        if _instant(value, field=label)[1] > _instant(frozen_at, field="frozen_at")[1]:
            _fail("source_clock_after_freeze", f"{label} exceeds bundle freeze")

    authorization_sha = canonical_hash(
        {
            "sec_access_sha256": access_artifact["sha256"],
            "sec_webmaster_faq_sha256": faq_artifact["sha256"],
        }
    )
    calendar_raw_sha = canonical_hash(
        {
            "sec_access_sha256": access_artifact["sha256"],
            "sec_edgar_calendar_sha256": calendar_artifact["sha256"],
        }
    )
    policy_sha = canonical_hash(bundle["disposition_policy"])
    identity_policy_sha = canonical_hash(
        {
            "security_identity": bundle["disposition_policy"]["security_identity"],
            "listing_identity": bundle["disposition_policy"]["listing_identity"],
            "mapping_effective_from": bundle["disposition_policy"]["mapping_effective_from"],
        }
    )
    scope = {
        "form_type": FORM_TYPE,
        "form_match": "exact_case_sensitive",
        "daily_index_sha256": index_artifact["sha256"],
        "company_exchange_sha256": mapping_artifact["sha256"],
        "disposition_policy_sha256": policy_sha,
    }
    scope_sha = canonical_hash(scope)
    scope_id = f"sec-edgar-exact-8k-{bundle['form_date']}-{scope_sha[:16]}"
    universe_definition = {
        "source": "SEC EDGAR daily form index plus company/exchange associations",
        "form_type": FORM_TYPE,
        "mapping_rule": "exactly one CIK association on Nasdaq or NYSE",
        "identity_policy_sha256": identity_policy_sha,
        "research_only": True,
        "market_wide_coverage_claimed": False,
        "trade_enabled": False,
    }
    universe_definition_sha = canonical_hash(universe_definition)

    coverage_source = _source_contract(
        source_contract_id=f"sec-8k-coverage-{bundle['bundle_sha256'][:16]}-v1",
        provider="U.S. Securities and Exchange Commission",
        source_name="Frozen exact 8-K daily-index population and dispositions",
        source_kind="derived",
        source_locator=f"bundle:{bundle['bundle_id']}/bundle.json",
        raw_identity_fields=["bundle_id", "revision_id"],
        decision_content_fields=[
            "coverage_scope_id", "coverage_scope_version", "coverage_scope_sha256",
            "enumeration_complete", "source_reported_row_count", "source_rows",
            "daily_index_sha256", "company_exchange_sha256",
            "disposition_policy_sha256",
        ],
        authorization_reference=SEC_FAQ_URL,
        authorization_sha256=authorization_sha,
        availability_reference=SEC_ACCESS_URL,
        source_timezone=CALENDAR_TIMEZONE,
        decision_calendar=CALENDAR_ID,
        revision_policy="immutable",
        revision_id_field="revision_id",
        security_mapping_policy="not_applicable",
        normalizer_id=NORMALIZER_ID,
        normalizer_version=NORMALIZER_VERSION,
        effective_from=coverage_known,
        created_at=frozen_at,
    )
    mapping_source = _source_contract(
        source_contract_id=f"sec-company-exchange-{mapping_artifact['sha256'][:16]}-v1",
        provider="U.S. Securities and Exchange Commission",
        source_name="SEC company ticker and exchange associations",
        source_kind="official",
        source_locator=mapping_artifact["url"],
        raw_identity_fields=["association_id", "revision_id"],
        decision_content_fields=[
            "association_ordinal", "cik", "name", "ticker", "exchange",
            "identity_policy_sha256",
        ],
        authorization_reference=SEC_FAQ_URL,
        authorization_sha256=authorization_sha,
        availability_reference=SEC_ACCESS_URL,
        source_timezone=CALENDAR_TIMEZONE,
        decision_calendar=CALENDAR_ID,
        revision_policy="versioned",
        revision_id_field="revision_id",
        security_mapping_policy="effective_dated",
        normalizer_id=MAPPING_NORMALIZER_ID,
        normalizer_version=MAPPING_NORMALIZER_VERSION,
        effective_from=mapping_known,
        created_at=frozen_at,
    )
    calendar_revision = canonical_hash(
        {
            "calendar_raw_sha256": calendar_raw_sha,
            "session_date": run_date,
            "closures": bundle["calendar_closures_2026"],
        }
    )
    calendar_source = _source_contract(
        source_contract_id=f"sec-edgar-calendar-{calendar_revision[:16]}-v1",
        provider="U.S. Securities and Exchange Commission",
        source_name="SEC EDGAR 2026 open-business-day surface",
        source_kind="derived",
        source_locator=f"bundle:{bundle['bundle_id']}/bundle.json",
        raw_identity_fields=["bundle_id", "revision_id"],
        decision_content_fields=[
            "calendar_id", "calendar_version", "calendar_timezone", "coverage_start",
            "coverage_end", "coverage_complete", "sessions",
        ],
        authorization_reference=SEC_ACCESS_URL,
        authorization_sha256=authorization_sha,
        availability_reference=SEC_CALENDAR_URL,
        source_timezone=CALENDAR_TIMEZONE,
        decision_calendar=CALENDAR_ID,
        revision_policy="immutable",
        revision_id_field="revision_id",
        security_mapping_policy="not_applicable",
        normalizer_id=CALENDAR_NORMALIZER_ID,
        normalizer_version=CALENDAR_NORMALIZER_VERSION,
        effective_from=calendar_session["open_at"],
        created_at=frozen_at,
    )

    associations_by_cik: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for association in associations:
        associations_by_cik[association["cik"]].append(association)
    mapping_cache: dict[tuple[str, str, str], tuple[SecurityMappingSnapshot, EvidenceRecord]] = {}
    coverage_rows: list[dict[str, Any]] = []
    for source_row in exact_rows:
        row_id = (
            f"sec-edgar-{source_row['accession']}-line-{source_row['line_number']:06d}"
        )
        row_hash = canonical_hash(source_row)
        matches = associations_by_cik.get(source_row["cik"], [])
        mapping: SecurityMappingSnapshot | None = None
        mapping_evidence: EvidenceRecord | None = None
        if not matches:
            disposition = "unmapped"
            reason_code = "sec_company_exchange_missing"
            reason = "No exact CIK association exists in the frozen SEC mapping snapshot."
        elif len(matches) != 1:
            disposition = "unmapped"
            reason_code = "sec_company_exchange_ambiguous"
            reason = "More than one CIK association exists; share-class identity is ambiguous."
        elif matches[0]["exchange"] not in _ACCEPTED_EXCHANGES:
            disposition = "excluded"
            reason_code = "sec_exchange_unsupported"
            reason = "The sole association is outside the declared Nasdaq/NYSE scope."
        else:
            association = matches[0]
            mic = _ACCEPTED_EXCHANGES[association["exchange"]]
            key = (association["cik"], association["ticker"], mic)
            if key not in mapping_cache:
                ticker_slug = _slug(association["ticker"])
                security_id = f"sec-association-{association['cik']}-{ticker_slug}"
                listing_id = f"{security_id}-{mic.lower()}"
                mapping = _seal_mapping(
                    {
                        "mapping_id": (
                            f"sec-map-{association['cik']}-{ticker_slug}-{mic.lower()}-"
                            f"{mapping_artifact['sha256'][:12]}"
                        ),
                        "security_id": security_id,
                        "listing_id": listing_id,
                        "symbol": association["ticker"],
                        "mic": mic,
                        "effective_from": mapping_known,
                        "effective_to": None,
                        "known_at": mapping_known,
                        "source_snapshot_sha256": mapping_artifact["sha256"],
                    }
                )
                association_id = (
                    f"sec-association-row-{association['association_ordinal']:06d}-"
                    f"{association['cik']}-{ticker_slug}"
                )
                revision_id = (
                    f"{mapping_artifact['sha256']}:{association['association_ordinal']}"
                )
                mapping_evidence = _evidence(
                    evidence_id=f"evidence-{association_id}-{mapping_artifact['sha256'][:12]}",
                    source=mapping_source,
                    raw_identity={"association_id": association_id, "revision_id": revision_id},
                    raw_artifact_locator=(
                        f"bundle:{bundle['bundle_id']}/{mapping_artifact['filename']}"
                    ),
                    raw_artifact_sha256=mapping_artifact["sha256"],
                    decision_content={
                        **association,
                        "identity_policy_sha256": identity_policy_sha,
                    },
                    observed_at=mapping_known,
                    known_at=mapping_known,
                    effective_from=mapping_known,
                    revision_id=revision_id,
                    recorded_at=frozen_at,
                    security_scope="instrument",
                    security_mapping=mapping,
                )
                _call(validate_evidence_against_source, mapping_evidence, mapping_source)
                if mapping.source_snapshot_sha256 != mapping_evidence.raw_artifact_sha256:
                    _fail("mapping_source_snapshot_mismatch", "mapping does not bind its raw snapshot")
                mapping_cache[key] = (mapping, mapping_evidence)
            mapping, mapping_evidence = mapping_cache[key]
            disposition = "mapped"
            reason_code = "sec_company_exchange_mapped"
            reason = "Exactly one accepted CIK association was known at the frozen row clock."
        coverage_rows.append(
            {
                "schema_version": 2,
                "record_type": "v2_external_universe_coverage_row",
                "source_row_id": row_id,
                "source_row_sha256": row_hash,
                "known_at": coverage_known,
                "disposition": disposition,
                "reason_code": reason_code,
                "reason": reason,
                "security_mapping": None if mapping is None else mapping.to_dict(),
                "mapping_evidence_id": None if mapping_evidence is None else mapping_evidence.evidence_id,
                "mapping_evidence_semantic_hash": (
                    None if mapping_evidence is None else mapping_evidence.semantic_hash
                ),
                "mapping_evidence_record_hash": (
                    None if mapping_evidence is None else mapping_evidence.record_hash
                ),
            }
        )
    coverage_rows.sort(key=lambda item: item["source_row_id"])
    row_source_surface = [
        {
            "source_row_id": row["source_row_id"],
            "source_row_sha256": row["source_row_sha256"],
            "known_at": row["known_at"],
        }
        for row in coverage_rows
    ]
    coverage_evidence = _evidence(
        evidence_id=f"evidence-sec-8k-coverage-{bundle['bundle_sha256'][:16]}",
        source=coverage_source,
        raw_identity={"bundle_id": bundle["bundle_id"], "revision_id": bundle["revision_id"]},
        raw_artifact_locator=f"bundle:{bundle['bundle_id']}/bundle.json",
        raw_artifact_sha256=bundle_artifact_sha,
        decision_content={
            "coverage_scope_id": scope_id,
            "coverage_scope_version": "1",
            "coverage_scope_sha256": scope_sha,
            "enumeration_complete": True,
            "source_reported_row_count": len(coverage_rows),
            "source_rows": row_source_surface,
            "daily_index_sha256": index_artifact["sha256"],
            "company_exchange_sha256": mapping_artifact["sha256"],
            "disposition_policy_sha256": policy_sha,
        },
        observed_at=coverage_known,
        known_at=coverage_known,
        effective_from=coverage_known,
        revision_id=bundle["revision_id"],
        recorded_at=frozen_at,
    )
    _call(validate_evidence_against_source, coverage_evidence, coverage_source)

    calendar_payload = calendar_session_snapshot_payload(
        [calendar_session],
        calendar_id=CALENDAR_ID,
        calendar_version=CALENDAR_VERSION,
        calendar_timezone=CALENDAR_TIMEZONE,
        coverage_start=run_date,
        coverage_end=run_date,
        coverage_complete=True,
    )
    calendar_evidence = _evidence(
        evidence_id=f"evidence-sec-edgar-calendar-{calendar_revision[:16]}",
        source=calendar_source,
        raw_identity={"bundle_id": bundle["bundle_id"], "revision_id": calendar_revision},
        raw_artifact_locator=f"bundle:{bundle['bundle_id']}/bundle.json",
        raw_artifact_sha256=bundle_artifact_sha,
        decision_content=calendar_payload,
        observed_at=calendar_known,
        known_at=calendar_known,
        effective_from=calendar_session["open_at"],
        revision_id=calendar_revision,
        recorded_at=frozen_at,
    )
    _call(validate_evidence_against_source, calendar_evidence, calendar_source)
    run_id = f"sec-8k-materialization-{bundle['bundle_sha256'][:16]}"
    clock = _seal_clock(
        {
            "schema_version": 1,
            "record_type": "v2_session_clock",
            "session_clock_id": f"clock-{run_id}",
            "run_id": run_id,
            "run_date": run_date,
            "calendar_id": CALENDAR_ID,
            "calendar_version": CALENDAR_VERSION,
            "calendar_timezone": CALENDAR_TIMEZONE,
            "calendar_snapshot_sha256": calendar_evidence.decision_content_sha256,
            "calendar_snapshot_known_at": calendar_evidence.known_at,
            "calendar_coverage_start": run_date,
            "calendar_coverage_end": run_date,
            "calendar_snapshot_complete": True,
            "calendar_evidence_id": calendar_evidence.evidence_id,
            "calendar_evidence_record_hash": calendar_evidence.record_hash,
            "calendar_session_id": calendar_session["calendar_session_id"],
            "session_open_at": calendar_session["open_at"],
            "session_close_at": calendar_session["close_at"],
            "anchor_kind": "data_calendar",
            "anchor_id": calendar_evidence.evidence_id,
            "anchor_snapshot_sha256": calendar_evidence.decision_content_sha256,
            "anchor_run_date": run_date,
            "anchor_session_id": calendar_session["calendar_session_id"],
            "anchor_known_at": calendar_evidence.known_at,
            "assignment_cutoff": frozen_at,
            "frozen_at": frozen_at,
            "recorded_at": frozen_at,
            "process_wall_clock_fallback_used": False,
            "pit_tier": "research_pit",
            "authority": "research_only",
            "trade_enabled": False,
        }
    )
    _call(
        validate_session_clock_against_calendar,
        clock,
        [calendar_session],
        calendar_evidence,
        calendar_source,
    )

    mapping_evidence_records = sorted(
        (item[1] for item in mapping_cache.values()), key=lambda item: item.evidence_id
    )
    event_batch_id = f"sec-8k-discovery-{bundle['bundle_sha256'][:16]}"
    rule_sha = canonical_hash(
        {
            "rule_id": "sec-8k-exact-association-discovery",
            "rule_version": "1",
            "coverage_scope_sha256": scope_sha,
            "universe_definition_sha256": universe_definition_sha,
        }
    )
    events: list[UniverseEvent] = []
    for mapping, mapping_evidence in sorted(
        mapping_cache.values(), key=lambda item: item[0].mapping_id
    ):
        evidence_for_event = [coverage_evidence, mapping_evidence]
        input_snapshot = universe_input_snapshot_hash(
            evidence_for_event,
            rule_sha256=rule_sha,
            security_mapping_sha256=mapping.mapping_sha256,
            session_clock_id=clock.session_clock_id,
            session_clock_hash=clock.semantic_hash,
            session_clock_record_hash=clock.record_hash,
            effective_session_clock_id=clock.session_clock_id,
            effective_session_clock_hash=clock.semantic_hash,
            effective_session_clock_record_hash=clock.record_hash,
        )
        event = _seal_event(
            {
                "schema_version": 2,
                "record_type": "v2_universe_event",
                "event_id": f"universe-discovery-{mapping.mapping_id}",
                "event_batch_id": event_batch_id,
                "universe_id": UNIVERSE_ID,
                "event_type": "discovery",
                "from_state": None,
                "to_state": "discovered",
                "security_mapping": mapping.to_dict(),
                "reason_code": "sec_exact_8k_association_discovered",
                "reason": "At least one exact 8-K row has one accepted frozen SEC association.",
                "rule_id": "sec-8k-exact-association-discovery",
                "rule_version": "1",
                "rule_sha256": rule_sha,
                "evidence_record_ids": [item.evidence_id for item in evidence_for_event],
                "input_snapshot_sha256": input_snapshot,
                "pit_tier": "research_pit",
                "known_future_leakage": False,
                "run_id": run_id,
                "session_clock_id": clock.session_clock_id,
                "session_clock_hash": clock.semantic_hash,
                "session_clock_record_hash": clock.record_hash,
                "run_date": run_date,
                "calendar_session_id": calendar_session["calendar_session_id"],
                "known_at": coverage_known,
                "decided_at": frozen_at,
                "recorded_at": frozen_at,
                "effective_at": frozen_at,
                "effective_session_id": calendar_session["calendar_session_id"],
                "effective_session_clock_id": clock.session_clock_id,
                "effective_session_clock_hash": clock.semantic_hash,
                "effective_session_clock_record_hash": clock.record_hash,
                "previous_event_id": None,
                "previous_event_hash": None,
                "trade_enabled": False,
            }
        )
        _call(
            validate_universe_event_against_evidence,
            event,
            evidence_for_event,
            [coverage_source, mapping_source],
        )
        _call(
            validate_universe_event_against_session_clocks,
            event,
            run_clock=clock,
            run_calendar_sessions=[calendar_session],
            run_calendar_evidence=calendar_evidence,
            run_calendar_source_contract=calendar_source,
            effective_clock=clock,
            effective_calendar_sessions=[calendar_session],
            effective_calendar_evidence=calendar_evidence,
            effective_calendar_source_contract=calendar_source,
        )
        events.append(event)
    events.sort(key=lambda item: item.event_id)

    all_sources = [coverage_source, mapping_source, calendar_source]
    all_evidence = [coverage_evidence, *mapping_evidence_records, calendar_evidence]
    for evidence_record in all_evidence:
        _validate_bundle_artifact_binding(
            evidence_record,
            root=root,
            bundle=bundle,
        )
    manifest = _call(
        build_universe_membership_manifest,
        events,
        manifest_id=f"manifest-sec-8k-{bundle['bundle_sha256'][:16]}",
        universe_id=UNIVERSE_ID,
        event_batch_id=event_batch_id,
        universe_definition_id=UNIVERSE_DEFINITION_ID,
        universe_definition_version=UNIVERSE_DEFINITION_VERSION,
        universe_definition_sha256=universe_definition_sha,
        source_contracts=all_sources,
        evidence_records=all_evidence,
        run_clock=clock,
        effective_clock=clock,
        ledger_population_start=frozen_at,
        membership_as_of=frozen_at,
        data_cutoff=frozen_at,
        frozen_at=frozen_at,
        recorded_at=frozen_at,
        previous_manifest=None,
    )
    disposition_counts = {
        disposition: sum(row["disposition"] == disposition for row in coverage_rows)
        for disposition in ("excluded", "mapped", "unmapped")
    }
    coverage = _seal_coverage(
        {
            "schema_version": 2,
            "record_type": "v2_external_universe_coverage_snapshot",
            "coverage_snapshot_id": f"coverage-sec-8k-{bundle['bundle_sha256'][:16]}",
            "universe_id": UNIVERSE_ID,
            "universe_definition_id": UNIVERSE_DEFINITION_ID,
            "universe_definition_version": UNIVERSE_DEFINITION_VERSION,
            "universe_definition_sha256": universe_definition_sha,
            "universe_manifest_id": manifest["manifest_id"],
            "universe_manifest_hash": manifest["manifest_hash"],
            "coverage_scope_id": scope_id,
            "coverage_scope_version": "1",
            "coverage_scope_sha256": scope_sha,
            "coverage_source_contract_id": coverage_source.source_contract_id,
            "coverage_source_contract_hash": coverage_source.source_contract_hash,
            "coverage_evidence_id": coverage_evidence.evidence_id,
            "coverage_evidence_semantic_hash": coverage_evidence.semantic_hash,
            "coverage_evidence_record_hash": coverage_evidence.record_hash,
            "membership_as_of": frozen_at,
            "data_cutoff": frozen_at,
            "frozen_at": frozen_at,
            "recorded_at": frozen_at,
            "enumeration_complete": True,
            "source_reported_row_count": len(coverage_rows),
            "rows": coverage_rows,
            "disposition_counts": disposition_counts,
            "row_snapshot_sha256": canonical_hash(row_source_surface),
            "coverage_status": "verified_complete",
            "pit_tier": "research_pit",
            "external_universe_coverage_status": "unverified",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "parity_status": "contract_only_unwired",
            "known_future_leakage": False,
            "outcome_blind": True,
            "results_accessed": False,
            "authority": "research_only",
            "trade_enabled": False,
        }
    )
    coverage_input_binding = _call(
        validate_external_universe_coverage_against_inputs,
        coverage,
        coverage_evidence=coverage_evidence,
        coverage_source_contract=coverage_source,
        mapping_evidence_records=mapping_evidence_records,
        mapping_source_contracts=[mapping_source],
    )
    coverage_manifest_binding = _call(
        validate_external_universe_coverage_against_manifest,
        coverage,
        manifest,
        events,
        coverage_evidence=coverage_evidence,
        coverage_source_contract=coverage_source,
        mapping_evidence_records=mapping_evidence_records,
        mapping_source_contracts=[mapping_source],
    )
    envelope: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_type": MATERIALIZATION_RECORD_TYPE,
        "input_bundle_id": bundle["bundle_id"],
        "input_bundle_sha256": bundle["bundle_sha256"],
        "source_contracts": [item.to_dict() for item in all_sources],
        "evidence_records": [item.to_dict() for item in all_evidence],
        "calendar_sessions": [calendar_session],
        "session_clocks": [clock.to_dict()],
        "universe_events": [item.to_dict() for item in events],
        "universe_manifest": manifest,
        "coverage_snapshot": coverage.to_dict(),
        "coverage_input_binding": coverage_input_binding,
        "coverage_manifest_binding": coverage_manifest_binding,
        "boundary": {
            "external_universe_coverage_status": "unverified",
            "pit_tier": "research_pit",
            "result_ceiling": "observed_only",
            "paper_live_eligible": False,
            "parity_status": "contract_only_unwired",
            "authority": "research_only",
            "trade_enabled": False,
        },
    }
    envelope["envelope_hash"] = canonical_hash(envelope)
    return envelope


def _validate_envelope_hash(envelope: Mapping[str, Any]) -> None:
    if not isinstance(envelope, Mapping):
        _fail("materialization_envelope_invalid", "materialization envelope must be an object")
    payload = deepcopy(dict(envelope))
    supplied = payload.pop("envelope_hash", None)
    if supplied != canonical_hash(payload):
        _fail("materialization_envelope_hash_mismatch", "envelope_hash is incorrect")
    if envelope.get("record_type") != MATERIALIZATION_RECORD_TYPE:
        _fail("materialization_envelope_invalid", "unexpected materialization record type")
    boundary = envelope.get("boundary")
    if not isinstance(boundary, Mapping) or boundary.get("trade_enabled") is not False:
        _fail("trade_enabled_forbidden", "materialization must remain default-off")


def _envelope_graph(envelope: Mapping[str, Any]) -> dict[str, Any]:
    contracts = {item["source_contract_id"]: item for item in envelope["source_contracts"]}
    evidence = {item["evidence_id"]: item for item in envelope["evidence_records"]}
    clocks = envelope["session_clocks"]
    sessions = envelope["calendar_sessions"]
    if len(clocks) != 1 or len(sessions) != 1:
        _fail("materialization_envelope_invalid", "one calendar session and clock are required")
    clock = clocks[0]
    calendar_evidence = evidence.get(clock["calendar_evidence_id"])
    if calendar_evidence is None:
        _fail("materialization_envelope_invalid", "calendar evidence is unresolved")
    calendar_source = contracts.get(calendar_evidence["source_contract_id"])
    if calendar_source is None:
        _fail("materialization_envelope_invalid", "calendar source is unresolved")
    coverage = envelope["coverage_snapshot"]
    coverage_evidence = evidence.get(coverage["coverage_evidence_id"])
    coverage_source = contracts.get(coverage["coverage_source_contract_id"])
    if coverage_evidence is None or coverage_source is None:
        _fail("materialization_envelope_invalid", "coverage evidence graph is unresolved")
    mapping_evidence = [item for item in evidence.values() if item["security_mapping"] is not None]
    mapping_source_ids = {item["source_contract_id"] for item in mapping_evidence}
    mapping_sources = [contracts[item] for item in sorted(mapping_source_ids)]
    writer_evidence = [
        item for item in evidence.values() if item["evidence_id"] != calendar_evidence["evidence_id"]
    ]
    writer_sources = [
        item for item in contracts.values() if item["source_contract_id"] != calendar_source["source_contract_id"]
    ]
    return {
        "contracts": contracts,
        "evidence": evidence,
        "clock": clock,
        "sessions": sessions,
        "calendar_evidence": calendar_evidence,
        "calendar_source": calendar_source,
        "coverage_evidence": coverage_evidence,
        "coverage_source": coverage_source,
        "mapping_evidence": mapping_evidence,
        "mapping_sources": mapping_sources,
        "writer_evidence": writer_evidence,
        "writer_sources": writer_sources,
    }


def validate_persisted_sec_8k_materialization(
    source_dir: str | Path,
    ledger_path: str | Path,
    envelope_path: str | Path,
) -> dict[str, Any]:
    """Re-read raw inputs, immutable envelope, and strict ledger as one graph."""

    ledger_target = Path(ledger_path).resolve()
    target = Path(envelope_path).resolve()
    if ledger_target == target:
        _fail("persistence_path_collision", "ledger and envelope paths must be distinct")
    expected = build_sec_8k_materialization(source_dir)
    if not target.is_file():
        _fail("materialization_envelope_missing", f"materialization envelope is missing: {target}")
    persisted = _json_bytes(target)
    _validate_envelope_hash(persisted)
    if persisted != expected:
        _fail("materialization_envelope_mismatch", "persisted envelope differs from rebuilt evidence")
    loaded = _call(load_v2_universe_ledger, ledger_target)
    manifest_id = persisted["universe_manifest"]["manifest_id"]
    manifest = next(
        (item for item in loaded["manifests"] if item["manifest_id"] == manifest_id), None
    )
    if manifest is None or manifest != persisted["universe_manifest"]:
        _fail("persisted_manifest_mismatch", "ledger does not contain the exact bound manifest")
    event_ids = set(manifest["universe_event_ids"])
    events = [item for item in loaded["events"] if item["event_id"] in event_ids]
    if sorted(events, key=lambda item: item["event_id"]) != sorted(
        persisted["universe_events"], key=lambda item: item["event_id"]
    ):
        _fail("persisted_event_population_mismatch", "ledger event population changed")
    graph = _envelope_graph(persisted)
    _call(
        validate_external_universe_coverage_against_manifest,
        persisted["coverage_snapshot"],
        manifest,
        events,
        coverage_evidence=graph["coverage_evidence"],
        coverage_source_contract=graph["coverage_source"],
        mapping_evidence_records=graph["mapping_evidence"],
        mapping_source_contracts=graph["mapping_sources"],
    )
    return {
        "status": "verified",
        "ledger_path": str(ledger_target),
        "envelope_path": str(target),
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "coverage_snapshot_id": persisted["coverage_snapshot"]["coverage_snapshot_id"],
        "coverage_snapshot_hash": persisted["coverage_snapshot"]["record_hash"],
        "envelope_hash": persisted["envelope_hash"],
    }


def _publish_sec_8k_materialization_locked(
    source_dir: str | Path,
    ledger_path: str | Path,
    envelope_path: str | Path,
    envelope: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish while the caller holds the envelope-specific advisory lock."""

    target = Path(envelope_path)
    if target.exists():
        existing = _json_bytes(target)
        if existing != envelope:
            _fail("immutable_materialization_conflict", f"refusing to overwrite {target}")
        envelope_status = "duplicate"
    else:
        envelope_status = "pending"
    graph = _envelope_graph(envelope)
    ledger_result = _call(
        append_v2_universe_batch,
        ledger_path,
        envelope["universe_events"],
        envelope["universe_manifest"],
        run_clock=graph["clock"],
        effective_clock=graph["clock"],
        evidence_records=graph["writer_evidence"],
        source_contracts=graph["writer_sources"],
        run_calendar_sessions=graph["sessions"],
        run_calendar_evidence=graph["calendar_evidence"],
        run_calendar_source_contract=graph["calendar_source"],
        effective_calendar_sessions=graph["sessions"],
        effective_calendar_evidence=graph["calendar_evidence"],
        effective_calendar_source_contract=graph["calendar_source"],
    )
    loaded = _call(load_v2_universe_ledger, ledger_path)
    committed_manifest = next(
        (
            item
            for item in loaded["manifests"]
            if item["manifest_id"] == envelope["universe_manifest"]["manifest_id"]
        ),
        None,
    )
    if committed_manifest != envelope["universe_manifest"]:
        _fail("persisted_manifest_mismatch", "ledger commit did not preserve the proposed manifest")
    event_ids = set(committed_manifest["universe_event_ids"])
    committed_events = [item for item in loaded["events"] if item["event_id"] in event_ids]
    _call(
        validate_external_universe_coverage_against_manifest,
        envelope["coverage_snapshot"],
        committed_manifest,
        committed_events,
        coverage_evidence=graph["coverage_evidence"],
        coverage_source_contract=graph["coverage_source"],
        mapping_evidence_records=graph["mapping_evidence"],
        mapping_source_contracts=graph["mapping_sources"],
    )
    if envelope_status == "pending":
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(envelope, target, indent=2, ensure_ascii=False)
        envelope_status = "committed"
    verified = validate_persisted_sec_8k_materialization(source_dir, ledger_path, target)
    ledger_status = ledger_result["status"]
    status = (
        "duplicate"
        if ledger_status == "duplicate" and envelope_status == "duplicate"
        else "committed"
    )
    return {
        "status": status,
        "ledger_status": ledger_status,
        "envelope_status": envelope_status,
        "manifest_id": verified["manifest_id"],
        "manifest_hash": verified["manifest_hash"],
        "coverage_snapshot_id": verified["coverage_snapshot_id"],
        "coverage_snapshot_hash": verified["coverage_snapshot_hash"],
        "envelope_hash": verified["envelope_hash"],
        "ledger_path": str(Path(ledger_path)),
        "envelope_path": str(target),
    }


def publish_sec_8k_materialization(
    source_dir: str | Path,
    ledger_path: str | Path,
    envelope_path: str | Path,
) -> dict[str, Any]:
    """Atomically serialize conflict-check, ledger append, and envelope commit."""

    target = Path(envelope_path).resolve()
    ledger_target = Path(ledger_path).resolve()
    if ledger_target == target:
        _fail("persistence_path_collision", "ledger and envelope paths must be distinct")
    envelope = build_sec_8k_materialization(source_dir)
    with _exclusive_path_lock(target):
        return _publish_sec_8k_materialization_locked(
            source_dir, ledger_target, target, envelope
        )


__all__ = [
    "V2SEC8KUniverseError",
    "build_sec_8k_materialization",
    "create_source_bundle_manifest",
    "freeze_sec_8k_source_bundle",
    "publish_sec_8k_materialization",
    "validate_persisted_sec_8k_materialization",
]
