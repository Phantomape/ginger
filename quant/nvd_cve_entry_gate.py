"""Point-in-time NVD CVE change-history entry-exclusion observer.

Only ``Initial Analysis`` changes whose detail is exactly an ``Added``
``CPE Configuration`` are eligible.  The event clock is the change-history
``created`` timestamp; CVE publication dates and later Reanalysis records are
never used.  Three distinct CVEs for one mapped issuer in one UTC
Monday-based calendar week trigger a five-trading-session entry exclusion,
starting on the first session strictly after the third change timestamp.

The helper is shared by historical replay and the daily paper snapshot.  It is
deliberately default-off and has no order, ranking, sizing, or exit adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from bisect import bisect_left, bisect_right
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

try:  # Package and script-style imports are both used in this repository.
    from .entry_universe_ledger import canonical_hash, membership_hash
    from .us_market_calendar import is_us_equity_session
except ImportError:  # pragma: no cover - exercised by script runners.
    from entry_universe_ledger import canonical_hash, membership_hash
    from us_market_calendar import is_us_equity_session


SOURCE = "nvd_cve_change_history"
SOURCE_ENDPOINT = "https://services.nvd.nist.gov/rest/json/cvehistory/2.0"
SOURCE_RULE_VERSION = "nvd_initial_analysis_added_cpe_pit_v1"
RULE_VERSION = "nvd_initial_analysis_cluster3_next_session_5d_v1"
EVENT_NAME = "Initial Analysis"
DETAIL_ACTION = "Added"
DETAIL_TYPE = "CPE Configuration"
CLUSTER_THRESHOLD = 3
EXCLUSION_SESSIONS = 5
TRADE_ENABLED = False
MAX_QUERY_DAYS = 120

# Frozen before outcome inspection in exp-20260717-007.  Matching is exact
# against the CPE 2.3 vendor component; an unknown vendor fails closed.
VENDOR_TO_TICKER: dict[str, str] = {
    "microsoft": "MSFT",
    "apple": "AAPL",
    "google": "GOOG",
    "cisco": "CSCO",
    "oracle": "ORCL",
    "ibm": "IBM",
    "adobe": "ADBE",
    "broadcom": "AVGO",
    "vmware": "AVGO",
    "palo_alto_networks": "PANW",
    "fortinet": "FTNT",
    "crowdstrike": "CRWD",
    "okta": "OKTA",
    "cloudflare": "NET",
    "juniper": "JNPR",
    "juniper_networks": "JNPR",
    "dell": "DELL",
    "hp": "HPQ",
    "hewlett_packard_enterprise": "HPE",
    "amd": "AMD",
    "intel": "INTC",
    "nvidia": "NVDA",
    "qualcomm": "QCOM",
    "amazon": "AMZN",
    "atlassian": "TEAM",
    "zoom": "ZM",
    "salesforce": "CRM",
    "servicenow": "NOW",
    "mongodb": "MDB",
    "snowflake": "SNOW",
    "elastic": "ESTC",
    "gitlab": "GTLB",
    "rapid7": "RPD",
    "tenable": "TENB",
    "cyberark": "CYBR",
    "checkpoint": "CHKP",
    "f5": "FFIV",
    "arista": "ANET",
    "netapp": "NTAP",
    "sap": "SAP",
    "splunk": "CSCO",
    "blackberry": "BB",
}
VENDOR_MAP_HASH = canonical_hash(VENDOR_TO_TICKER)

# The contract intentionally recognises only CPE 2.3 part a/h/o and captures
# only the immediately following vendor component.
CPE_VENDOR_RE = re.compile(r"cpe:2\.3:[aho]:([^:\s\"'\\]+):")
_NEW_YORK = ZoneInfo("America/New_York")


class NvdSourceContractError(ValueError):
    """The NVD archive or event stream violates the fixed source contract."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _normalise_date(value: Any, *, field: str = "date") -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise NvdSourceContractError(f"invalid {field}: {value!r}") from exc


def _created_utc(value: Any) -> tuple[datetime, str]:
    text = str(value or "").strip()
    if not text:
        raise NvdSourceContractError("change.created is required")
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise NvdSourceContractError(f"invalid change.created: {value!r}") from exc
    # NVD's API timestamps historically omit an explicit suffix but are UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed, parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _api_clock(value: Any, *, end: bool) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = datetime.combine(
            value,
            datetime.max.time() if end else datetime.min.time(),
            tzinfo=timezone.utc,
        )
    else:
        text = str(value or "").strip()
        if len(text) in (8, 10) and (text.replace("-", "").isdigit()):
            day = date.fromisoformat(_normalise_date(text))
            parsed = datetime.combine(
                day,
                datetime.max.time() if end else datetime.min.time(),
                tzinfo=timezone.utc,
            )
        else:
            parsed, _ = _created_utc(value)
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _default_http_get(url: str, *, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ginger-research/1.0 (NVD CVE PIT archive)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return response.read()


def _call_http_get(
    http_get: Callable[..., Any], url: str, *, timeout: float
) -> bytes:
    try:
        response = http_get(url, timeout=timeout)
    except TypeError:
        response = http_get(url, timeout)
    if isinstance(response, bytes):
        return response
    if isinstance(response, str):
        return response.encode("utf-8")
    if isinstance(response, Mapping):
        return _canonical_bytes(dict(response))
    if hasattr(response, "content"):
        content = response.content
        return content if isinstance(content, bytes) else bytes(content)
    raise NvdSourceContractError("HTTP getter must return bytes, text, or a mapping")


def fetch_nvd_change_history_archive(
    *,
    start: Any,
    end: Any,
    archive_dir: Path | str,
    page_size: int = 5000,
    timeout: float = 30.0,
    min_interval_seconds: float = 6.1,
    http_get: Callable[..., Any] | None = None,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> dict[str, Any]:
    """Fetch all Initial-Analysis pages and commit a hash-bound manifest.

    NVD limits change-history date queries to 120 consecutive days.  A longer
    requested range is split into contiguous millisecond-resolution chunks;
    each chunk restarts pagination at zero and is independently audited.
    """
    if page_size < 1 or page_size > 5000:
        raise ValueError("page_size must be in [1, 5000]")
    start_clock = _api_clock(start, end=False)
    end_clock = _api_clock(end, end=True)
    if _created_utc(start_clock)[0] > _created_utc(end_clock)[0]:
        raise ValueError("start must not be after end")

    range_start = _created_utc(start_clock)[0]
    range_end = _created_utc(end_clock)[0]
    one_millisecond = timedelta(milliseconds=1)
    max_span = timedelta(days=MAX_QUERY_DAYS) - one_millisecond
    chunk_bounds: list[tuple[datetime, datetime]] = []
    chunk_start = range_start
    while chunk_start <= range_end:
        chunk_end = min(range_end, chunk_start + max_span)
        chunk_bounds.append((chunk_start, chunk_end))
        chunk_start = chunk_end + one_millisecond

    target = Path(archive_dir)
    target.mkdir(parents=True, exist_ok=True)
    getter = http_get or _default_http_get
    pages: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    request_number = 0
    grand_total = 0
    for chunk_index, (chunk_start, chunk_end) in enumerate(chunk_bounds):
        chunk_start_text = chunk_start.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        chunk_end_text = chunk_end.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        expected_start = 0
        chunk_total: int | None = None
        chunk_page_start = len(pages)
        while chunk_total is None or expected_start < chunk_total:
            if request_number and min_interval_seconds > 0:
                sleep_fn(float(min_interval_seconds))
            params = {
                "eventName": EVENT_NAME,
                "changeStartDate": chunk_start_text,
                "changeEndDate": chunk_end_text,
                "startIndex": expected_start,
                "resultsPerPage": int(page_size),
            }
            url = f"{SOURCE_ENDPOINT}?{urllib.parse.urlencode(params)}"
            raw = _call_http_get(getter, url, timeout=timeout)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise NvdSourceContractError("NVD page is not valid UTF-8 JSON") from exc
            if not isinstance(payload, dict):
                raise NvdSourceContractError("NVD page root must be a JSON object")
            try:
                page_start = int(payload.get("startIndex"))
                page_size_actual = int(payload.get("resultsPerPage"))
                page_total = int(payload.get("totalResults"))
            except (TypeError, ValueError) as exc:
                raise NvdSourceContractError("NVD pagination metadata is incomplete") from exc
            changes = payload.get("cveChanges")
            if page_start != expected_start or not isinstance(changes, list):
                raise NvdSourceContractError("NVD pagination start or cveChanges drift")
            if chunk_total is None:
                chunk_total = page_total
            elif page_total != chunk_total:
                raise NvdSourceContractError("NVD totalResults changed within a query chunk")
            if page_size_actual < 0 or (page_size_actual == 0 and expected_start < page_total):
                raise NvdSourceContractError("NVD pagination made no progress")
            if page_total == 0 or page_start + len(changes) >= page_total:
                next_start = page_total
            else:
                next_start = page_start + page_size_actual
                if next_start <= page_start or next_start > page_total:
                    raise NvdSourceContractError("NVD pagination next index is invalid")

            filename = (
                f"chunk_{chunk_index:03d}_page_{len(pages) - chunk_page_start:04d}_"
                f"{page_start:09d}.json"
            )
            page_path = target / filename
            _atomic_write(page_path, raw)
            pages.append(
                {
                    "file": filename,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "chunk_index": chunk_index,
                    "start_index": page_start,
                    "results_per_page": page_size_actual,
                    "change_count": len(changes),
                    "next_start_index": next_start,
                    "total_results": page_total,
                    "url": url,
                }
            )
            request_number += 1
            if page_total == 0:
                break
            expected_start = next_start
        chunk_total = int(chunk_total or 0)
        grand_total += chunk_total
        chunks.append(
            {
                "chunk_index": chunk_index,
                "change_start_date": chunk_start_text,
                "change_end_date": chunk_end_text,
                "total_results": chunk_total,
                "page_count": len(pages) - chunk_page_start,
                "first_page_ordinal": chunk_page_start,
                "last_page_ordinal": len(pages) - 1,
            }
        )

    manifest: dict[str, Any] = {
        "schema": "nvd_cve_change_history_raw_manifest_v1",
        "source": SOURCE,
        "source_endpoint": SOURCE_ENDPOINT,
        "source_rule_version": SOURCE_RULE_VERSION,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "query": {
            "event_name": EVENT_NAME,
            "change_start_date": start_clock,
            "change_end_date": end_clock,
            "requested_results_per_page": int(page_size),
            "maximum_consecutive_days_per_chunk": MAX_QUERY_DAYS,
        },
        "vendor_map_hash": VENDOR_MAP_HASH,
        "chunk_count": len(chunks),
        "chunks": chunks,
        "total_results": grand_total,
        "page_count": len(pages),
        "pages": pages,
    }
    manifest["manifest_payload_sha256"] = canonical_hash(manifest)
    manifest_path = target / "manifest.json"
    _atomic_write(
        manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return {
        **manifest,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _file_sha256(manifest_path),
    }


def _manifest_path(value: Path | str | Mapping[str, Any]) -> Path:
    if isinstance(value, Mapping):
        path = value.get("manifest_path")
        if not path:
            raise NvdSourceContractError("manifest mapping lacks manifest_path")
        return Path(str(path))
    path = Path(value)
    return path / "manifest.json" if path.is_dir() else path


def load_nvd_change_history_archive(
    manifest: Path | str | Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Verify manifest/page hashes and return exact API ``cveChanges`` rows."""
    path = _manifest_path(manifest)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NvdSourceContractError(f"cannot read NVD manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise NvdSourceContractError("NVD manifest root must be an object")
    expected_payload_hash = payload.pop("manifest_payload_sha256", None)
    if expected_payload_hash != canonical_hash(payload):
        raise NvdSourceContractError("NVD manifest payload hash mismatch")
    if (
        payload.get("schema") != "nvd_cve_change_history_raw_manifest_v1"
        or payload.get("source") != SOURCE
        or payload.get("source_endpoint") != SOURCE_ENDPOINT
        or payload.get("source_rule_version") != SOURCE_RULE_VERSION
        or payload.get("vendor_map_hash") != VENDOR_MAP_HASH
    ):
        raise NvdSourceContractError("NVD manifest source identity mismatch")
    query = payload.get("query")
    if not isinstance(query, dict) or query.get("event_name") != EVENT_NAME:
        raise NvdSourceContractError("NVD manifest does not bind Initial Analysis")
    pages = payload.get("pages")
    if not isinstance(pages, list) or payload.get("page_count") != len(pages):
        raise NvdSourceContractError("NVD manifest page count mismatch")
    chunks = payload.get("chunks")
    if not isinstance(chunks, list) or payload.get("chunk_count") != len(chunks) or not chunks:
        raise NvdSourceContractError("NVD manifest chunk count mismatch")

    one_millisecond = timedelta(milliseconds=1)
    previous_end: datetime | None = None
    expected_page_ordinal = 0
    chunk_lookup: dict[int, dict[str, Any]] = {}
    for expected_chunk_index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict) or int(chunk.get("chunk_index", -1)) != expected_chunk_index:
            raise NvdSourceContractError("NVD manifest chunk ordering mismatch")
        start_dt, _ = _created_utc(chunk.get("change_start_date"))
        end_dt, _ = _created_utc(chunk.get("change_end_date"))
        if start_dt > end_dt or end_dt - start_dt >= timedelta(days=MAX_QUERY_DAYS):
            raise NvdSourceContractError("NVD manifest chunk exceeds 120 consecutive days")
        if previous_end is None:
            query_start, _ = _created_utc(query.get("change_start_date"))
            if start_dt != query_start:
                raise NvdSourceContractError("NVD first chunk does not match query start")
        elif start_dt != previous_end + one_millisecond:
            raise NvdSourceContractError("NVD manifest chunks have a gap or overlap")
        page_count = int(chunk.get("page_count", -1))
        first_ordinal = int(chunk.get("first_page_ordinal", -1))
        last_ordinal = int(chunk.get("last_page_ordinal", -1))
        if (
            page_count < 1
            or first_ordinal != expected_page_ordinal
            or last_ordinal != first_ordinal + page_count - 1
        ):
            raise NvdSourceContractError("NVD chunk page ordinals are inconsistent")
        expected_page_ordinal += page_count
        previous_end = end_dt
        chunk_lookup[expected_chunk_index] = chunk
    query_end, _ = _created_utc(query.get("change_end_date"))
    if previous_end != query_end or expected_page_ordinal != len(pages):
        raise NvdSourceContractError("NVD chunk coverage does not match requested range")

    rows: list[dict[str, Any]] = []
    expected_start_by_chunk: dict[int, int] = defaultdict(int)
    loaded_by_chunk: dict[int, int] = defaultdict(int)
    for page_ordinal, page in enumerate(pages):
        chunk_index = int(page.get("chunk_index", -1)) if isinstance(page, dict) else -1
        chunk = chunk_lookup.get(chunk_index)
        expected_start = expected_start_by_chunk[chunk_index]
        if (
            not isinstance(page, dict)
            or chunk is None
            or int(page.get("start_index", -1)) != expected_start
            or not (int(chunk["first_page_ordinal"]) <= page_ordinal <= int(chunk["last_page_ordinal"]))
        ):
            raise NvdSourceContractError("NVD manifest pagination is not contiguous")
        page_path = path.parent / str(page.get("file") or "")
        try:
            raw = page_path.read_bytes()
        except OSError as exc:
            raise NvdSourceContractError(f"cannot read NVD page {page_path}: {exc}") from exc
        if len(raw) != page.get("bytes") or hashlib.sha256(raw).hexdigest() != page.get("sha256"):
            raise NvdSourceContractError(f"NVD raw page hash mismatch: {page_path.name}")
        try:
            page_payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NvdSourceContractError(f"invalid archived NVD page: {page_path.name}") from exc
        changes = page_payload.get("cveChanges") if isinstance(page_payload, dict) else None
        if (
            not isinstance(changes, list)
            or int(page_payload.get("startIndex", -1)) != expected_start
            or int(page_payload.get("totalResults", -1)) != int(chunk.get("total_results", -2))
            or len(changes) != int(page.get("change_count", -1))
        ):
            raise NvdSourceContractError("archived NVD page metadata mismatch")
        rows.extend(dict(row) for row in changes if isinstance(row, dict))
        loaded_by_chunk[chunk_index] += len(changes)
        expected_start_by_chunk[chunk_index] = int(page.get("next_start_index", -1))
    if any(
        loaded_by_chunk[index] != int(chunk["total_results"])
        for index, chunk in chunk_lookup.items()
    ) or len(rows) != int(payload.get("total_results", -1)):
        raise NvdSourceContractError("archived NVD rows do not match chunk totals")
    return rows


def _iter_change_rows(rows: Iterable[Mapping[str, Any]] | Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    if isinstance(rows, Mapping):
        changes = rows.get("cveChanges")
        if isinstance(changes, list):
            yield from (row for row in changes if isinstance(row, Mapping))
        else:
            yield rows
        return
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        changes = row.get("cveChanges")
        if isinstance(changes, list):
            yield from (item for item in changes if isinstance(item, Mapping))
        else:
            yield row


def normalize_nvd_initial_analysis_events(
    rows: Iterable[Mapping[str, Any]] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Normalize only strict Initial-Analysis/Added/CPE-Configuration rows."""
    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    for wrapper in _iter_change_rows(rows):
        nested = wrapper.get("change")
        change = nested if isinstance(nested, Mapping) else wrapper
        if change.get("eventName") != EVENT_NAME:
            continue
        cve_id = str(change.get("cveId") or "").strip().upper()
        if not re.fullmatch(r"CVE-\d{4}-\d{4,}", cve_id):
            continue
        try:
            created_dt, created = _created_utc(change.get("created"))
        except NvdSourceContractError:
            continue
        details = change.get("details")
        if not isinstance(details, list):
            continue
        week_monday = (created_dt.date() - timedelta(days=created_dt.weekday())).isoformat()
        for detail in details:
            if not isinstance(detail, Mapping):
                continue
            if detail.get("action") != DETAIL_ACTION or detail.get("type") != DETAIL_TYPE:
                continue
            new_value = detail.get("newValue")
            if not isinstance(new_value, str):
                continue
            for match in CPE_VENDOR_RE.finditer(new_value):
                vendor = match.group(1)
                ticker = VENDOR_TO_TICKER.get(vendor)
                if ticker is None:
                    continue
                key = (ticker, cve_id, created)
                events[key] = {
                    "cve_id": cve_id,
                    "cve_change_id": str(change.get("cveChangeId") or "") or None,
                    "ticker": ticker,
                    "vendor": vendor,
                    "created": created,
                    "created_date": created_dt.date().isoformat(),
                    "utc_week_monday": week_monday,
                    "event_name": EVENT_NAME,
                    "detail_action": DETAIL_ACTION,
                    "detail_type": DETAIL_TYPE,
                    "cpe": match.group(0),
                    "source": SOURCE,
                    "source_rule_version": SOURCE_RULE_VERSION,
                    "vendor_map_hash": VENDOR_MAP_HASH,
                    "published_clock_used": False,
                    "reanalysis_used": False,
                    "trade_enabled": False,
                    "alters_live_orders": False,
                }
    return sorted(
        events.values(), key=lambda row: (row["created"], row["ticker"], row["cve_id"])
    )


def build_nvd_cve_clusters(
    events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build fixed UTC-week clusters; the third distinct CVE is the trigger."""
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw in events:
        row = dict(raw)
        ticker = str(row.get("ticker") or "").upper()
        cve_id = str(row.get("cve_id") or "").upper()
        if ticker not in VENDOR_TO_TICKER.values() or not cve_id:
            continue
        try:
            created_dt, created = _created_utc(row.get("created"))
        except NvdSourceContractError:
            continue
        week = (created_dt.date() - timedelta(days=created_dt.weekday())).isoformat()
        candidate = {**row, "ticker": ticker, "cve_id": cve_id, "created": created}
        previous = grouped[(ticker, week)].get(cve_id)
        if previous is None or candidate["created"] < previous["created"]:
            grouped[(ticker, week)][cve_id] = candidate

    clusters: list[dict[str, Any]] = []
    for (ticker, week), by_cve in sorted(grouped.items()):
        ordered = sorted(by_cve.values(), key=lambda row: (row["created"], row["cve_id"]))
        if len(ordered) < CLUSTER_THRESHOLD:
            continue
        trigger = ordered[CLUSTER_THRESHOLD - 1]
        clusters.append(
            {
                "ticker": ticker,
                "utc_week_monday": week,
                "trigger_created": trigger["created"],
                "trigger_cve_id": trigger["cve_id"],
                "trigger_cve_ids": [row["cve_id"] for row in ordered[:CLUSTER_THRESHOLD]],
                "week_cve_ids": [row["cve_id"] for row in ordered],
                "distinct_cve_count": len(ordered),
                "cluster_threshold": CLUSTER_THRESHOLD,
                "rule_version": RULE_VERSION,
                "vendor_map_hash": VENDOR_MAP_HASH,
                "trade_enabled": False,
                "alters_live_orders": False,
            }
        )
    return clusters


def _normalise_sessions(values: Iterable[Any]) -> list[str]:
    return sorted({_normalise_date(value, field="trading session") for value in values})


def _first_session_open_after(sessions: list[str], trigger: datetime) -> int:
    local_day = trigger.astimezone(_NEW_YORK).date().isoformat()
    for index in range(bisect_left(sessions, local_day), len(sessions)):
        session_day = date.fromisoformat(sessions[index])
        session_open = datetime(
            session_day.year,
            session_day.month,
            session_day.day,
            9,
            30,
            tzinfo=_NEW_YORK,
        ).astimezone(timezone.utc)
        if session_open > trigger:
            return index
    return len(sessions)


def build_nvd_exclusion_index(
    clusters: Iterable[Mapping[str, Any]],
    trading_sessions: Iterable[Any],
    *,
    source_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Schedule each trigger from its next session for five sessions."""
    sessions = _normalise_sessions(trading_sessions)
    by_session: dict[str, set[str]] = defaultdict(set)
    scheduled: list[dict[str, Any]] = []
    for raw in clusters:
        cluster = dict(raw)
        ticker = str(cluster.get("ticker") or "").upper()
        try:
            trigger_dt, trigger_created = _created_utc(cluster.get("trigger_created"))
        except NvdSourceContractError:
            continue
        start_index = _first_session_open_after(sessions, trigger_dt)
        exclusion = sessions[start_index : start_index + EXCLUSION_SESSIONS]
        if not ticker or not exclusion:
            continue
        for session in exclusion:
            by_session[session].add(ticker)
        scheduled.append(
            {
                **cluster,
                "ticker": ticker,
                "trigger_created": trigger_created,
                "activation_session": exclusion[0],
                "exclusion_sessions": exclusion,
                "scheduled_session_count": len(exclusion),
            }
        )
    payload: dict[str, Any] = {
        "schema": "nvd_cve_entry_exclusion_index_v1",
        "source": SOURCE,
        "source_rule_version": SOURCE_RULE_VERSION,
        "rule_version": RULE_VERSION,
        "vendor_map_hash": VENDOR_MAP_HASH,
        "cluster_threshold": CLUSTER_THRESHOLD,
        "exclusion_session_count": EXCLUSION_SESSIONS,
        "activation_semantics": "first_NYSE_0930_America_New_York_open_strictly_after_third_created_timestamp",
        "resolver_semantics": "signal_day_resolve_tests_next_session_fill_eligibility",
        "source_manifest_sha256": source_manifest_sha256,
        "trading_sessions": sessions,
        "trading_sessions_hash": canonical_hash(sessions),
        "clusters": sorted(
            scheduled, key=lambda row: (row["trigger_created"], row["ticker"])
        ),
        "by_session": {
            session: sorted(tickers) for session, tickers in sorted(by_session.items())
        },
        "trade_enabled": False,
        "alters_live_orders": False,
    }
    payload["index_hash"] = canonical_hash(payload)
    return payload


class NvdEntryUniverseResolver:
    """BacktestEngine-compatible resolver for next-open entry admission.

    BacktestEngine resolves on the signal day but fills on the next session.
    Therefore this resolver deliberately looks up the *next* configured
    trading session and removes issuers excluded on that fill session.
    """

    def __init__(
        self,
        base_tickers: Iterable[str],
        exclusion_index: Mapping[str, Any],
        *,
        trading_sessions: Iterable[Any] | None = None,
        source_manifest_sha256: str | None = None,
    ) -> None:
        self._base = frozenset(str(value).strip().upper() for value in base_tickers if str(value).strip())
        self._index = deepcopy(dict(exclusion_index))
        stored_hash = self._index.pop("index_hash", None)
        if stored_hash != canonical_hash(self._index):
            raise NvdSourceContractError("NVD exclusion index hash mismatch")
        if (
            self._index.get("source") != SOURCE
            or self._index.get("rule_version") != RULE_VERSION
            or self._index.get("vendor_map_hash") != VENDOR_MAP_HASH
        ):
            raise NvdSourceContractError("NVD exclusion index identity mismatch")
        self._index["index_hash"] = stored_hash
        indexed_sessions = _normalise_sessions(self._index.get("trading_sessions") or [])
        supplied_sessions = (
            _normalise_sessions(trading_sessions)
            if trading_sessions is not None
            else indexed_sessions
        )
        if supplied_sessions != indexed_sessions:
            raise NvdSourceContractError(
                "resolver trading_sessions differ from the hash-bound exclusion index"
            )
        self._sessions = tuple(indexed_sessions)
        self._by_session = {
            str(day): frozenset(str(t).upper() for t in tickers)
            for day, tickers in (self._index.get("by_session") or {}).items()
        }
        self._source_hash = (
            source_manifest_sha256
            or self._index.get("source_manifest_sha256")
            or str(stored_hash)
        )
        self._metadata = {
            "schema": "nvd_cve_entry_universe_resolver_metadata_v1",
            "source": SOURCE,
            "source_hash": self._source_hash,
            "source_rule_version": SOURCE_RULE_VERSION,
            "rule_version": RULE_VERSION,
            "vendor_map_hash": VENDOR_MAP_HASH,
            "index_hash": stored_hash,
            "base_ticker_count": len(self._base),
            "base_membership_hash": membership_hash(self._base),
            "cluster_count": len(self._index.get("clusters") or []),
            "fill_semantics": "resolve(signal_day) excludes when next_trading_session fill is in five-session window",
            "trade_enabled": False,
            "alters_live_orders": False,
        }

    @property
    def data_tickers(self) -> frozenset[str]:
        return self._base

    @property
    def metadata(self) -> dict[str, Any]:
        return deepcopy(self._metadata)

    def resolve(self, as_of: Any) -> dict[str, Any]:
        day = _normalise_date(as_of, field="as_of")
        next_index = bisect_right(self._sessions, day)
        if next_index >= len(self._sessions):
            return {
                "status": "unknown_no_next_trading_session",
                "reason": "next-session fill cannot be identified from the configured calendar",
                "as_of": day,
                "tickers": [],
                "ticker_count": 0,
                "membership_hash": None,
                "provenance": {},
            }
        entry_session = self._sessions[next_index]
        excluded = self._by_session.get(entry_session, frozenset())
        eligible = sorted(self._base - excluded)
        semantic = {
            "as_of": day,
            "entry_session": entry_session,
            "eligible": eligible,
            "excluded": sorted(self._base & excluded),
            "source_hash": self._source_hash,
            "index_hash": self._index["index_hash"],
            "rule_version": RULE_VERSION,
        }
        snapshot_hash = canonical_hash({"record_type": "nvd_entry_membership", **semantic})
        record_hash = canonical_hash({"record_type": "nvd_entry_resolution", **semantic})
        provenance = {
            "source_rule_version": SOURCE_RULE_VERSION,
            "rule_version": RULE_VERSION,
            "vendor_map_hash": VENDOR_MAP_HASH,
            "index_hash": self._index["index_hash"],
            "entry_session": entry_session,
            "excluded_tickers": semantic["excluded"],
            "fill_semantics": self._metadata["fill_semantics"],
            "trade_enabled": False,
            "alters_live_orders": False,
        }
        return {
            "status": "resolved",
            "as_of": day,
            "snapshot_as_of": day,
            "effective_as_of": day,
            "snapshot_sha256": snapshot_hash,
            "snapshot_hash": snapshot_hash,
            "record_hash": record_hash,
            "tickers": eligible,
            "ticker_count": len(eligible),
            "membership_hash": membership_hash(eligible),
            "source": SOURCE,
            "source_hash": self._source_hash,
            "rule_version": RULE_VERSION,
            "clean_cutoff": day,
            "reason": "next_session_entry_exclusion" if semantic["excluded"] else "no_active_next_session_exclusion",
            "provenance": provenance,
        }

    def __call__(self, as_of: Any) -> set[str]:
        return set(self.resolve(as_of).get("tickers") or [])


def _daily_flags() -> dict[str, bool]:
    return {
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_live_orders": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }


def empty_nvd_cve_entry_gate_snapshot(as_of_date: Any, reason: str) -> dict[str, Any]:
    as_of = _normalise_date(as_of_date, field="as_of_date")
    return {
        "schema": "nvd_cve_entry_gate_daily_snapshot_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "vendor_map_hash": VENDOR_MAP_HASH,
        "as_of_date": as_of,
        "status": "empty",
        "reason": str(reason),
        "event_count": 0,
        "cluster_count": 0,
        "candidate_count": 0,
        "excluded_tickers_for_next_session": [],
        "candidates": [],
        **_daily_flags(),
    }


def _default_daily_sessions(as_of: str) -> list[str]:
    center = date.fromisoformat(as_of)
    return [
        day.isoformat()
        for offset in range(-21, 22)
        if is_us_equity_session(day := center + timedelta(days=offset))
    ]


def build_nvd_cve_entry_gate_snapshot(
    *,
    as_of_date: Any,
    events: Iterable[Mapping[str, Any]],
    trading_sessions: Iterable[Any] | None = None,
    source_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    as_of = _normalise_date(as_of_date, field="as_of_date")
    event_rows = [dict(row) for row in events]
    clusters = build_nvd_cve_clusters(event_rows)
    sessions = _normalise_sessions(trading_sessions or _default_daily_sessions(as_of))
    index = build_nvd_exclusion_index(
        clusters, sessions, source_manifest_sha256=source_manifest_sha256
    )
    next_position = bisect_right(sessions, as_of)
    next_session = sessions[next_position] if next_position < len(sessions) else None
    excluded = list((index.get("by_session") or {}).get(next_session, [])) if next_session else []
    candidates = [
        {
            "ticker": ticker,
            "signal_date": as_of,
            "entry_session": next_session,
            "decision": "observe_entry_exclusion_default_off",
            "rule_version": RULE_VERSION,
            "trade_enabled": False,
            "alters_live_orders": False,
        }
        for ticker in excluded
    ]
    return {
        "schema": "nvd_cve_entry_gate_daily_snapshot_v1",
        "source": SOURCE,
        "source_rule_version": SOURCE_RULE_VERSION,
        "rule_version": RULE_VERSION,
        "vendor_map_hash": VENDOR_MAP_HASH,
        "as_of_date": as_of,
        "status": "ok",
        "calendar_source": "explicit_sessions" if trading_sessions is not None else "rule_generated_nyse_regular_sessions",
        "next_trading_session": next_session,
        "event_count": len(event_rows),
        "cluster_count": len(clusters),
        "cluster_hash": canonical_hash(clusters),
        "exclusion_index_hash": index["index_hash"],
        "candidate_count": len(candidates),
        "excluded_tickers_for_next_session": excluded,
        "candidates": candidates,
        "clusters": clusters,
        **_daily_flags(),
    }


def prepare_nvd_cve_entry_gate_snapshot(
    *,
    as_of_date: Any,
    existing_events: Iterable[Mapping[str, Any]],
    fetched_change_rows: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    trading_sessions: Iterable[Any] | None = None,
    source_manifest_sha256: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = normalize_nvd_initial_analysis_events(fetched_change_rows)
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in [*(dict(value) for value in existing_events), *normalized]:
        key = (
            str(row.get("ticker") or ""),
            str(row.get("cve_id") or ""),
            str(row.get("created") or ""),
        )
        if all(key):
            merged[key] = row
    events = sorted(merged.values(), key=lambda row: (row["created"], row["ticker"], row["cve_id"]))
    snapshot = build_nvd_cve_entry_gate_snapshot(
        as_of_date=as_of_date,
        events=events,
        trading_sessions=trading_sessions,
        source_manifest_sha256=source_manifest_sha256,
    )
    return snapshot, events


# Naming used by other shared-paper helpers and parity tests.
prep_and_build_nvd_cve_entry_gate_snapshot = prepare_nvd_cve_entry_gate_snapshot


def persist_daily_nvd_cve_entry_gate_snapshot(
    *,
    today: Any,
    repo_root: Path | str | None = None,
    fetched_change_rows: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None = None,
    trading_sessions: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Persist one forward default-off snapshot and cumulative event state."""
    as_of = _normalise_date(today, field="today")
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    base = root / "data" / "paper_sleeves" / "nvd_cve_entry_gate"
    state_path = base / "events.json"
    existing: list[dict[str, Any]] = []
    if state_path.exists():
        try:
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            existing = [dict(row) for row in state_payload.get("events") or [] if isinstance(row, dict)]
        except (OSError, json.JSONDecodeError) as exc:
            raise NvdSourceContractError(f"cannot read NVD daily state: {exc}") from exc

    source_manifest_sha256: str | None = None
    rows = fetched_change_rows
    if rows is None:
        day = date.fromisoformat(as_of)
        archive = fetch_nvd_change_history_archive(
            start=day - timedelta(days=14),
            end=day,
            archive_dir=base / "source_archives" / as_of.replace("-", ""),
        )
        source_manifest_sha256 = str(archive["manifest_sha256"])
        rows = load_nvd_change_history_archive(archive)
    else:
        rows = [dict(row) for row in _iter_change_rows(rows)]
        source_manifest_sha256 = canonical_hash(rows)

    snapshot, events = prepare_nvd_cve_entry_gate_snapshot(
        as_of_date=as_of,
        existing_events=existing,
        fetched_change_rows=rows,
        trading_sessions=trading_sessions,
        source_manifest_sha256=source_manifest_sha256,
    )
    state_payload = {
        "schema": "nvd_cve_entry_gate_forward_events_v1",
        "source": SOURCE,
        "source_rule_version": SOURCE_RULE_VERSION,
        "vendor_map_hash": VENDOR_MAP_HASH,
        "last_successful_observation_date": as_of,
        "source_manifest_sha256": source_manifest_sha256,
        "event_count": len(events),
        "events": events,
        **_daily_flags(),
    }
    snapshot_path = base / f"snapshot_{as_of.replace('-', '')}.json"
    _atomic_write(
        state_path,
        json.dumps(state_payload, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    _atomic_write(
        snapshot_path,
        json.dumps(snapshot, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    return {
        **snapshot,
        "state_path": str(state_path),
        "snapshot_path": str(snapshot_path),
        "source_manifest_sha256": source_manifest_sha256,
    }


__all__ = [
    "CLUSTER_THRESHOLD",
    "CPE_VENDOR_RE",
    "DETAIL_ACTION",
    "DETAIL_TYPE",
    "EVENT_NAME",
    "EXCLUSION_SESSIONS",
    "NvdEntryUniverseResolver",
    "NvdSourceContractError",
    "RULE_VERSION",
    "SOURCE",
    "SOURCE_ENDPOINT",
    "SOURCE_RULE_VERSION",
    "TRADE_ENABLED",
    "VENDOR_MAP_HASH",
    "VENDOR_TO_TICKER",
    "build_nvd_cve_clusters",
    "build_nvd_cve_entry_gate_snapshot",
    "build_nvd_exclusion_index",
    "empty_nvd_cve_entry_gate_snapshot",
    "fetch_nvd_change_history_archive",
    "load_nvd_change_history_archive",
    "normalize_nvd_initial_analysis_events",
    "persist_daily_nvd_cve_entry_gate_snapshot",
    "prep_and_build_nvd_cve_entry_gate_snapshot",
    "prepare_nvd_cve_entry_gate_snapshot",
]
