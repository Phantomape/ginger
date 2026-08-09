"""exp-20260717-004: PIT Fed H.8 bank-size weekly relative value.

This runner owns the immutable source and market-data boundary plus the
preregistered three-window evaluation.  It freezes exact official dated H.8
HTML bytes before using outcomes, delegates parsing/signal/timing semantics to
the shared default-off helper, and evaluates one locked weekly KRE/KBE pair.

The policy is deliberately not configurable here: positive H.8 small-minus-
large four-release growth is long KRE/short KBE, negative is the reverse,
$4,000 per leg, one pair maximum, and 35 bps round trip per leg.  No neutral
band, threshold, sign, lag, cost, or holding-period retune is exposed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260717-004"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from fed_h8_bank_size_relative_value_paper_sleeve import (  # noqa: E402
    KBE_TICKER,
    KRE_TICKER,
    LAG_RELEASES,
    MAX_CONCURRENT_PAIRS,
    NOTIONAL_USD_PER_LEG,
    ROUND_TRIP_COST_PCT_PER_LEG,
    RULE_VERSION,
    SLEEVE_NAME,
    TRADE_ENABLED,
    build_weekly_pair_decisions,
    compute_h8_signal,
    parse_h8_release_html,
)


WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
CANONICAL_START = "2024-10-02"
CANONICAL_END = "2026-04-21"
CANONICAL_RELEASE_COUNT = 81
LAG_ANCHOR_STAMPS = ("20240906", "20240913", "20240920", "20240927")
TOTAL_RELEASE_COUNT = CANONICAL_RELEASE_COUNT + len(LAG_ANCHOR_STAMPS)

RELEASE_DATES_URL = (
    "https://www.federalreserve.gov/releases/h8/releaseDates.json"
)
DATED_RELEASE_URL = "https://www.federalreserve.gov/releases/h8/{stamp}/"
EXPECTED_RELEASE_DATES_BYTES = 79_228
EXPECTED_RELEASE_DATES_SHA256 = (
    "c9caa76a2f69a13e93cfc8aafb94e5ef17f368f18294239575241ce8eef51d6b"
)
PREFLIGHT_REFERENCE_CANONICAL_RAW_MANIFEST_SHA256 = (
    "231b3531beeef7b414583eea10a8fb2fba9f7288c4f73a1c6ac916914010d4e0"
)
PREFLIGHT_REFERENCE_ANCHOR_RAW_MANIFEST_SHA256 = (
    "696f56228204c22c2337522226fa356374edc09941ef2d6c04a9bc97e2345e25"
)
PREFLIGHT_REFERENCE_ANCHOR_RAW_IDENTITIES = {
    "20240906": (671_448, "12bea755076bcbc0d7a5da876b89f74e5aa833038bed7b4a124453911f10b363"),
    "20240913": (671_435, "3d4ca97139ca3dc6654cb663476a5f741221621849fb31f432e81a074da3e6fb"),
    "20240920": (673_573, "1e4bb1761609d8c4dd64380b5de1f31c4b93e2609ea2042f48bb8d2bf8649c22"),
    "20240927": (673_243, "35b1e45b5b386ddfe55355785541d9394dba689efbbd5714e31d8eaa9e1d066c"),
}
SEMANTIC_SOURCE_SCHEMA = "fed_h8_locked_table_values_v1"
EXPECTED_SEMANTIC_ALL_BYTES = 11_135
EXPECTED_SEMANTIC_ALL_SHA256 = (
    "cb8508c1509d674d41e441b007ee9f8826cd1f73bc933051c492fac9c29c7820"
)
EXPECTED_SEMANTIC_CANONICAL_BYTES = 10_611
EXPECTED_SEMANTIC_CANONICAL_SHA256 = (
    "2e4038ad501bb44a8d1d51d85347b8a2e9016b30ed05f49e2e1d9392db85e545"
)
EXPECTED_SEMANTIC_ANCHOR_BYTES = 524
EXPECTED_SEMANTIC_ANCHOR_SHA256 = (
    "c71451dccc2cfb71740d665f4bffa34d31ddba44f002ced01173e4144ced312a"
)
PREFLIGHT_REFERENCE_PARSER_AUDIT_SHA256 = (
    "e9432f18b335d0c8eb4acc6420f1a7e2510d023ab769cf2e4cc0f6b1f1b038e8"
)

HTTP_TIMEOUT_SECONDS = 45
HTTP_ATTEMPTS = 3
HTTP_WORKERS = 6
MAX_HTTP_BYTES = 4_000_000
USER_AGENT = (
    "ginger-research/exp-20260717-004 "
    "(read-only official-source archival; no trading)"
)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
SOURCE_DIR = OUT_DIR / "source"
RELEASE_DATES_PATH = SOURCE_DIR / "releaseDates.json"
RAW_HTML_ARCHIVE_PATH = SOURCE_DIR / "raw_h8_release_html.zip"
CANONICAL_RELEASES_PATH = SOURCE_DIR / "canonical_releases.json"
SOURCE_MANIFEST_PATH = OUT_DIR / "source_manifest.json"
AUXILIARY_OHLCV_PATH = OUT_DIR / "auxiliary_ohlcv.json"
RESULT_PATH = OUT_DIR / "fed_h8_bank_size_relative_value_replay.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
VERDICT_PATH = OUT_DIR / "full_stack_verdict.json"
PAPER_SEED_PATH = OUT_DIR / "daily_default_off_seed.json"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260715-010"
    / "after_measurement.json"
)
EXPECTED_BASELINE_BYTES = 19_435
EXPECTED_BASELINE_SHA256 = (
    "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731"
)

AUXILIARY_QUERY_START = "2024-09-03"
# yfinance end is exclusive; 2026-04-24 is retained as an exit/calendar buffer.
AUXILIARY_QUERY_END_EXCLUSIVE = "2026-04-25"
AUXILIARY_REQUIRED_LAST_DATE = "2026-04-21"
PAIR_TICKERS = (KRE_TICKER, KBE_TICKER)
LONG_ONLY_COMPARATORS = ("SPY", "QQQ", KRE_TICKER, KBE_TICKER)
AUXILIARY_TICKERS = (KRE_TICKER, KBE_TICKER, "SPY", "QQQ")
STATIC_PAIR_COMPARATORS = (
    "STATIC_LONG_KRE_SHORT_KBE",
    "STATIC_LONG_KBE_SHORT_KRE",
)
REQUIRED_COMPARATORS = (
    "CASH",
    *LONG_ONLY_COMPARATORS,
)

MIN_SETTLED_PAIRS_PER_WINDOW = 20
MIN_POSITIVE_WINDOWS = 2
MIN_WINDOW_RETURN = -0.02
MAX_PAIR_DRAWDOWN = 0.10
MAX_TOP_FIVE_POSITIVE_CONTRIBUTION = 0.60
MAX_COMBINED_DRAWDOWN_WORSE = 0.005
PAIR_INITIAL_CAPITAL = 2.0 * NOTIONAL_USD_PER_LEG
AUXILIARY_ACTION_SEMANTICS = (
    "adjusted OHLC incorporates split and distribution total-return effects; "
    "no separate dividend cashflows are added"
)


class SourceContractError(RuntimeError):
    """Official, frozen, policy, or evaluation input violated its contract."""


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _bytes_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_bytes(path, _json_bytes(payload))


def _fetch_bytes(url: str, *, accept: str) -> tuple[bytes, dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(HTTP_ATTEMPTS):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": USER_AGENT,
                "Connection": "close",
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed Fed HTTPS only
                request, timeout=HTTP_TIMEOUT_SECONDS
            ) as response:
                status = int(getattr(response, "status", 200))
                if status != 200:
                    raise SourceContractError(f"HTTP {status} for {url}")
                raw = response.read(MAX_HTTP_BYTES + 1)
                if not raw or len(raw) > MAX_HTTP_BYTES:
                    raise SourceContractError(
                        f"invalid response size {len(raw)} for {url}"
                    )
                final_url = str(response.geturl())
                host = (urllib.parse.urlsplit(final_url).hostname or "").lower()
                if host not in {"www.federalreserve.gov", "federalreserve.gov"}:
                    raise SourceContractError(
                        f"unexpected redirect host for {url}: {final_url}"
                    )
                return raw, {
                    "status": status,
                    "final_url": final_url,
                    "content_type": response.headers.get_content_type(),
                    "bytes": len(raw),
                    "attempts": attempt + 1,
                }
        except Exception as error:
            last_error = error
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(0.5 * (2**attempt))
    raise SourceContractError(
        f"failed to fetch {url} after {HTTP_ATTEMPTS} attempts: {last_error}"
    ) from last_error


def _release_date_stamps(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        raise SourceContractError("releaseDates.json root is not a list")
    stamps: list[str] = []
    for year in payload:
        if not isinstance(year, Mapping) or not isinstance(year.get("Months"), list):
            raise SourceContractError("releaseDates.json year/month schema drift")
        for month in year["Months"]:
            if not isinstance(month, Mapping) or not isinstance(month.get("Dates"), list):
                raise SourceContractError("releaseDates.json month/date schema drift")
            for raw_stamp in month["Dates"]:
                stamp = str(raw_stamp)
                try:
                    parsed = datetime.strptime(stamp, "%Y%m%d").date()
                except ValueError as error:
                    raise SourceContractError(
                        f"invalid H.8 release stamp {stamp!r}"
                    ) from error
                if parsed.strftime("%Y%m%d") != stamp:
                    raise SourceContractError(f"non-canonical release stamp {stamp}")
                stamps.append(stamp)
    if len(stamps) != len(set(stamps)):
        raise SourceContractError("duplicate H.8 release date in official list")
    return sorted(stamps)


def _selected_stamps(release_dates_raw: bytes) -> tuple[list[str], list[str]]:
    if len(release_dates_raw) != EXPECTED_RELEASE_DATES_BYTES:
        raise SourceContractError(
            "releaseDates.json byte length drift: "
            f"{len(release_dates_raw)} != {EXPECTED_RELEASE_DATES_BYTES}"
        )
    actual_sha = _bytes_sha(release_dates_raw)
    if actual_sha != EXPECTED_RELEASE_DATES_SHA256:
        raise SourceContractError(
            f"releaseDates.json SHA drift: {actual_sha}"
        )
    try:
        payload = json.loads(release_dates_raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceContractError("releaseDates.json is not valid UTF-8 JSON") from error
    stamps = _release_date_stamps(payload)
    canonical = [
        stamp
        for stamp in stamps
        if CANONICAL_START.replace("-", "")
        <= stamp
        <= CANONICAL_END.replace("-", "")
    ]
    if len(canonical) != CANONICAL_RELEASE_COUNT:
        raise SourceContractError(
            f"canonical release count drift: {len(canonical)}"
        )
    if canonical[0] != "20241004" or canonical[-1] != "20260417":
        raise SourceContractError(
            f"canonical release boundary drift: {canonical[0]}..{canonical[-1]}"
        )
    missing_anchors = [stamp for stamp in LAG_ANCHOR_STAMPS if stamp not in stamps]
    if missing_anchors:
        raise SourceContractError(f"lag anchor release dates missing: {missing_anchors}")
    return canonical, [*LAG_ANCHOR_STAMPS, *canonical]


def _raw_member(stamp: str) -> str:
    return f"h8/{stamp}/index.html"


def _deterministic_zip(raw_by_stamp: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for stamp in sorted(raw_by_stamp):
            info = zipfile.ZipInfo(_raw_member(stamp), ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, raw_by_stamp[stamp])
    return buffer.getvalue()


def _parse_release(stamp: str, raw: bytes) -> dict[str, Any]:
    release_date = datetime.strptime(stamp, "%Y%m%d").date().isoformat()
    url = DATED_RELEASE_URL.format(stamp=stamp)
    parsed = parse_h8_release_html(
        raw,
        release_date=release_date,
        source_url=url,
        source_sha256=_bytes_sha(raw),
    )
    if not isinstance(parsed, Mapping) or parsed.get("release_date") != release_date:
        raise SourceContractError(f"helper release identity drift for {stamp}")
    if parsed.get("trade_enabled") is not False:
        raise SourceContractError(f"helper release not default-off for {stamp}")
    return dict(parsed)


def _parser_audit(releases: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(releases, key=lambda row: str(row["release_date"]))
    if len(ordered) != TOTAL_RELEASE_COUNT:
        raise SourceContractError(f"parsed release count drift: {len(ordered)}")
    rows: list[dict[str, Any]] = []
    active_count = 0
    exact_zero_count = 0
    for index, current in enumerate(ordered):
        release_date = str(current["release_date"])
        is_anchor = release_date.replace("-", "") in LAG_ANCHOR_STAMPS
        row: dict[str, Any] = {
            "release_date": release_date,
            "role": "lag_anchor" if is_anchor else "canonical",
            "source_sha256": current["source_sha256"],
            "table_6_valid": current.get("tables", {}).get("large", {}).get(
                "table_number"
            )
            == 6,
            "table_8_valid": current.get("tables", {}).get("small", {}).get(
                "table_number"
            )
            == 8,
        }
        if not row["table_6_valid"] or not row["table_8_valid"]:
            raise SourceContractError(f"parsed table audit failed for {release_date}")
        if index >= LAG_RELEASES:
            lagged = ordered[index - LAG_RELEASES]
            signal = compute_h8_signal(current, lagged)
            row.update(
                {
                    "lag4_release_date": signal["lag4_release_date"],
                    "lag_span_days": signal["lag_span_days"],
                    "signal": signal["signal"],
                    "direction": signal["direction"],
                    "active_pair": signal["active_pair"],
                }
            )
            active_count += int(bool(signal["active_pair"]))
            exact_zero_count += int(not bool(signal["active_pair"]))
        rows.append(row)
    audit = {
        "schema": "fed_h8_parser_lag_audit_v1",
        "release_count": len(ordered),
        "canonical_count": sum(row["role"] == "canonical" for row in rows),
        "lag_anchor_count": sum(row["role"] == "lag_anchor" for row in rows),
        "lag4_signal_count": sum("lag4_release_date" in row for row in rows),
        "active_pair_count": active_count,
        "exact_zero_signal_count": exact_zero_count,
        "all_table_flags_valid": all(
            row["table_6_valid"] and row["table_8_valid"] for row in rows
        ),
        "rows": rows,
        "preflight_reference_audit_sha256": (
            PREFLIGHT_REFERENCE_PARSER_AUDIT_SHA256
        ),
        "preflight_hash_comparable": False,
        "preflight_hash_noncomparison_reason": (
            "original_preflight_serialization_unavailable_after_compaction"
        ),
    }
    audit["canonical_structured_sha256"] = _canonical_sha(
        {key: value for key, value in audit.items() if key != "canonical_structured_sha256"}
    )
    if audit["canonical_count"] != CANONICAL_RELEASE_COUNT:
        raise SourceContractError("parser audit canonical count failed")
    if audit["lag_anchor_count"] != len(LAG_ANCHOR_STAMPS):
        raise SourceContractError("parser audit lag-anchor count failed")
    if audit["lag4_signal_count"] != CANONICAL_RELEASE_COUNT:
        raise SourceContractError("parser audit lag4 mapping count failed")
    return audit


def _semantic_source_text(
    releases: Iterable[Mapping[str, Any]], *, role: str
) -> bytes:
    if role not in {"all", "canonical", "lag_anchor"}:
        raise SourceContractError(f"invalid semantic source role {role}")
    selected: list[Mapping[str, Any]] = []
    for release in releases:
        stamp = str(release.get("release_date") or "").replace("-", "")
        is_anchor = stamp in LAG_ANCHOR_STAMPS
        if role == "all" or (role == "lag_anchor" and is_anchor) or (
            role == "canonical" and not is_anchor
        ):
            selected.append(release)
    selected.sort(key=lambda row: str(row["release_date"]))
    lines: list[str] = []
    field_order = (
        ("large", "commercial_and_industrial_loans"),
        ("large", "other_deposits"),
        ("small", "commercial_and_industrial_loans"),
        ("small", "other_deposits"),
    )
    for release in selected:
        encoded_fields: list[str] = []
        for bank_size, field in field_order:
            values = (
                release.get("tables", {})
                .get(bank_size, {})
                .get("fields", {})
                .get(field, {})
                .get("weekly_values")
            )
            if not isinstance(values, list) or len(values) != 4:
                raise SourceContractError(
                    f"semantic weekly-values contract missing for "
                    f"{release.get('release_date')} {bank_size}/{field}"
                )
            normalized: list[float] = []
            for value in values:
                number = _number(value)
                if number is None or number <= 0:
                    raise SourceContractError(
                        f"semantic weekly value invalid for "
                        f"{release.get('release_date')} {bank_size}/{field}"
                    )
                normalized.append(float(number))
            encoded_fields.append(
                json.dumps(
                    normalized,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                )
            )
        lines.append(
            "|".join([str(release["release_date"]), *encoded_fields]) + "\n"
        )
    return "".join(lines).encode("utf-8")


def _semantic_source_identity(releases: list[dict[str, Any]]) -> dict[str, Any]:
    contracts = {
        "all": (EXPECTED_SEMANTIC_ALL_BYTES, EXPECTED_SEMANTIC_ALL_SHA256),
        "canonical": (
            EXPECTED_SEMANTIC_CANONICAL_BYTES,
            EXPECTED_SEMANTIC_CANONICAL_SHA256,
        ),
        "lag_anchor": (
            EXPECTED_SEMANTIC_ANCHOR_BYTES,
            EXPECTED_SEMANTIC_ANCHOR_SHA256,
        ),
    }
    identities: dict[str, Any] = {}
    for role, (expected_bytes, expected_sha) in contracts.items():
        raw = _semantic_source_text(releases, role=role)
        actual = {"bytes": len(raw), "sha256": _bytes_sha(raw)}
        if actual != {"bytes": expected_bytes, "sha256": expected_sha}:
            raise SourceContractError(
                f"semantic H.8 {role} identity drift: {actual}"
            )
        identities[role] = {
            **actual,
            "expected_bytes": expected_bytes,
            "expected_sha256": expected_sha,
            "passed": True,
        }
    first_line = _semantic_source_text(releases, role="canonical").splitlines(
        keepends=True
    )[0]
    expected_first = (
        b"2024-10-04|[1545.9,1545.1,1549.5,1554.8]|"
        b"[10156.7,10127.6,10142.1,10145.4]|"
        b"[730.9,731.0,732.9,731.9]|[4699.6,4688.6,4693.8,4696.3]\n"
    )
    if first_line != expected_first:
        raise SourceContractError(
            f"semantic H.8 first-line sanity vector drift: {first_line!r}"
        )
    return {
        "schema": SEMANTIC_SOURCE_SCHEMA,
        "serialization": (
            "UTF-8 no BOM/no header/final LF; ISO date ascending; compact JSON "
            "arrays for T6 CI10, T6 Other36, T8 CI10, T8 Other36 four weekly values"
        ),
        "units": "seasonally_adjusted_billions_usd",
        "identities": identities,
        "first_canonical_line_sanity_passed": True,
        "last_canonical_release_date": "2026-04-17",
        "binding_source_gate": True,
    }


def _response_manifest_text(
    pages: Iterable[Mapping[str, Any]], *, role: str
) -> str:
    selected = sorted(
        (
            row
            for row in pages
            if row.get("role") == role
        ),
        key=lambda row: str(row["release_date"]),
    )
    # The preflight identity includes one terminating newline per dated page.
    return "".join(
        f"{row['release_date']}|{row['url']}|{row['status']}|"
        f"{row['bytes']}|{row['sha256']}\n"
        for row in selected
    )


def _validate_response_manifest(pages: list[dict[str, Any]]) -> dict[str, str]:
    if len(pages) != TOTAL_RELEASE_COUNT:
        raise SourceContractError(f"source page count drift: {len(pages)}")
    text = _response_manifest_text(pages, role="canonical")
    actual = _bytes_sha(text.encode("utf-8"))
    anchor_text = _response_manifest_text(pages, role="lag_anchor")
    anchor_actual = _bytes_sha(anchor_text.encode("utf-8"))
    role_counts = {
        role: sum(row.get("role") == role for row in pages)
        for role in ("canonical", "lag_anchor")
    }
    if role_counts != {
        "canonical": CANONICAL_RELEASE_COUNT,
        "lag_anchor": len(LAG_ANCHOR_STAMPS),
    }:
        raise SourceContractError(f"raw page role-count drift: {role_counts}")
    for row in pages:
        stamp = str(row["release_date"]).replace("-", "")
        expected_url = DATED_RELEASE_URL.format(stamp=stamp)
        if (
            row.get("url") != expected_url
            or int(row.get("status", 0)) != 200
            or int(row.get("bytes", 0)) <= 0
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or ""))
        ):
            raise SourceContractError(
                f"raw dated-page provenance contract invalid for {stamp}: {row}"
            )
    return {"canonical": actual, "lag_anchor": anchor_actual}


def _validate_frozen_source() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required = (
        RELEASE_DATES_PATH,
        RAW_HTML_ARCHIVE_PATH,
        CANONICAL_RELEASES_PATH,
        SOURCE_MANIFEST_PATH,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SourceContractError(f"frozen H.8 source incomplete: {missing}")
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    release_dates_raw = RELEASE_DATES_PATH.read_bytes()
    canonical_stamps, all_stamps = _selected_stamps(release_dates_raw)
    identities = manifest.get("files") or {}
    for key, path in (
        ("release_dates", RELEASE_DATES_PATH),
        ("raw_html_archive", RAW_HTML_ARCHIVE_PATH),
        ("canonical_releases", CANONICAL_RELEASES_PATH),
    ):
        identity = identities.get(key) or {}
        if identity.get("sha256") != _file_sha(path):
            raise SourceContractError(f"frozen source file SHA mismatch: {key}")
        if int(identity.get("bytes", -1)) != path.stat().st_size:
            raise SourceContractError(f"frozen source file size mismatch: {key}")
    pages = list(manifest.get("pages") or [])
    response_sha = _validate_response_manifest(pages)
    stored_raw_manifests = manifest.get("raw_response_manifests") or {}
    if (
        (stored_raw_manifests.get("canonical") or {}).get("actual_sha256")
        != response_sha["canonical"]
        or (stored_raw_manifests.get("lag_anchor") or {}).get("actual_sha256")
        != response_sha["lag_anchor"]
    ):
        raise SourceContractError("stored raw response provenance identity mismatch")
    page_by_stamp = {
        str(row["release_date"]).replace("-", ""): row for row in pages
    }
    if sorted(page_by_stamp) != sorted(all_stamps):
        raise SourceContractError("frozen page/date selection drift")
    parsed: list[dict[str, Any]] = []
    with zipfile.ZipFile(RAW_HTML_ARCHIVE_PATH) as archive:
        if sorted(archive.namelist()) != sorted(_raw_member(s) for s in all_stamps):
            raise SourceContractError("raw H.8 archive member set drift")
        for stamp in all_stamps:
            raw = archive.read(_raw_member(stamp))
            page = page_by_stamp[stamp]
            if len(raw) != int(page["bytes"]) or _bytes_sha(raw) != page["sha256"]:
                raise SourceContractError(f"raw H.8 member identity drift: {stamp}")
            parsed.append(_parse_release(stamp, raw))
    stored_releases = _read_json(CANONICAL_RELEASES_PATH)
    if stored_releases.get("releases") != parsed:
        raise SourceContractError("canonical H.8 parse drift against frozen bytes")
    audit = _parser_audit(parsed)
    if manifest.get("parser_audit") != audit:
        raise SourceContractError("frozen H.8 parser/lag audit drift")
    if manifest.get("canonical_release_stamps") != canonical_stamps:
        raise SourceContractError("frozen canonical release list drift")
    semantic_identity = _semantic_source_identity(parsed)
    if manifest.get("semantic_source_identity") != semantic_identity:
        raise SourceContractError("frozen semantic H.8 source identity drift")
    return parsed, manifest


def materialize_source(*, offline: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if SOURCE_MANIFEST_PATH.is_file():
        return _validate_frozen_source()
    partial = [
        path
        for path in (RELEASE_DATES_PATH, RAW_HTML_ARCHIVE_PATH, CANONICAL_RELEASES_PATH)
        if path.exists()
    ]
    if partial:
        raise SourceContractError(
            "orphan H.8 source files exist without commit-marker manifest: "
            f"{[_repo_rel(path) for path in partial]}"
        )
    if offline:
        raise SourceContractError("offline mode requires a complete frozen H.8 source")

    release_dates_raw, release_meta = _fetch_bytes(
        RELEASE_DATES_URL, accept="application/json"
    )
    canonical_stamps, all_stamps = _selected_stamps(release_dates_raw)
    canonical_set = set(canonical_stamps)

    raw_by_stamp: dict[str, bytes] = {}
    meta_by_stamp: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {
            pool.submit(
                _fetch_bytes,
                DATED_RELEASE_URL.format(stamp=stamp),
                accept="text/html,application/xhtml+xml",
            ): stamp
            for stamp in all_stamps
        }
        for future in as_completed(futures):
            stamp = futures[future]
            raw, metadata = future.result()
            raw_by_stamp[stamp] = raw
            meta_by_stamp[stamp] = metadata

    releases = [_parse_release(stamp, raw_by_stamp[stamp]) for stamp in all_stamps]
    audit = _parser_audit(releases)
    semantic_identity = _semantic_source_identity(releases)
    pages: list[dict[str, Any]] = []
    for stamp in all_stamps:
        metadata = meta_by_stamp[stamp]
        release_date = datetime.strptime(stamp, "%Y%m%d").date().isoformat()
        url = DATED_RELEASE_URL.format(stamp=stamp)
        if metadata["final_url"].rstrip("/") != url.rstrip("/"):
            raise SourceContractError(
                f"dated release redirected unexpectedly: {url} -> {metadata['final_url']}"
            )
        pages.append(
            {
                "release_date": release_date,
                "role": "canonical" if stamp in canonical_set else "lag_anchor",
                "url": url,
                "final_url": metadata["final_url"],
                "status": metadata["status"],
                "content_type": metadata["content_type"],
                "bytes": len(raw_by_stamp[stamp]),
                "sha256": _bytes_sha(raw_by_stamp[stamp]),
                "raw_zip_member": _raw_member(stamp),
            }
        )
    response_sha = _validate_response_manifest(pages)
    archive_raw = _deterministic_zip(raw_by_stamp)
    releases_payload = {
        "schema": "fed_h8_canonical_releases_v1",
        "rule_version": RULE_VERSION,
        "release_count": len(releases),
        "canonical_count": len(canonical_stamps),
        "lag_anchor_count": len(LAG_ANCHOR_STAMPS),
        "releases": releases,
    }
    manifest = {
        "schema": "fed_h8_pit_source_manifest_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "official_release_dates_url": RELEASE_DATES_URL,
        "release_dates_http": release_meta,
        "release_dates_expected_bytes": EXPECTED_RELEASE_DATES_BYTES,
        "release_dates_expected_sha256": EXPECTED_RELEASE_DATES_SHA256,
        "raw_response_manifest_schema": (
            "date|url|status|bytes|sha256 plus terminating newline per row"
        ),
        "raw_response_manifests": {
            "canonical": {
                "actual_sha256": response_sha["canonical"],
                "preflight_reference_sha256": (
                    PREFLIGHT_REFERENCE_CANONICAL_RAW_MANIFEST_SHA256
                ),
                "hash_comparable": False,
            },
            "lag_anchor": {
                "actual_sha256": response_sha["lag_anchor"],
                "preflight_reference_sha256": (
                    PREFLIGHT_REFERENCE_ANCHOR_RAW_MANIFEST_SHA256
                ),
                "preflight_reference_page_identities": {
                    stamp: {"bytes": identity[0], "sha256": identity[1]}
                    for stamp, identity in PREFLIGHT_REFERENCE_ANCHOR_RAW_IDENTITIES.items()
                },
                "hash_comparable": False,
            },
            "noncomparability_reason": (
                "official Fed HTML raw bytes vary by HTTP client while the locked "
                "Table 6/8 weekly values are cross-client identical"
            ),
            "binding_source_gate": False,
        },
        "semantic_source_identity": semantic_identity,
        "canonical_release_stamps": canonical_stamps,
        "lag_anchor_stamps": list(LAG_ANCHOR_STAMPS),
        "coverage": {
            "canonical_start": canonical_stamps[0],
            "canonical_end": canonical_stamps[-1],
            "canonical_count": len(canonical_stamps),
            "lag_anchor_count": len(LAG_ANCHOR_STAMPS),
            "total_page_count": len(pages),
        },
        "pages": pages,
        "parser_audit": audit,
        "files": {
            "release_dates": {
                "path": _repo_rel(RELEASE_DATES_PATH),
                "bytes": len(release_dates_raw),
                "sha256": _bytes_sha(release_dates_raw),
            },
            "raw_html_archive": {
                "path": _repo_rel(RAW_HTML_ARCHIVE_PATH),
                "bytes": len(archive_raw),
                "sha256": _bytes_sha(archive_raw),
            },
            "canonical_releases": {
                "path": _repo_rel(CANONICAL_RELEASES_PATH),
                "bytes": len(_json_bytes(releases_payload)),
                "sha256": _bytes_sha(_json_bytes(releases_payload)),
            },
        },
        "commit_marker_semantics": (
            "manifest_written_last_after_all_exact_bytes_and_parses_validate"
        ),
    }
    _atomic_write_bytes(RELEASE_DATES_PATH, release_dates_raw)
    _atomic_write_bytes(RAW_HTML_ARCHIVE_PATH, archive_raw)
    _atomic_write_json(CANONICAL_RELEASES_PATH, releases_payload)
    _atomic_write_json(SOURCE_MANIFEST_PATH, manifest)
    return _validate_frozen_source()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _bar_date(row: Mapping[str, Any]) -> str:
    return str(row.get("date") or row.get("Date") or "")[:10]


def _validate_auxiliary_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise SourceContractError("auxiliary OHLCV root is not a mapping")
    if payload.get("schema") != "yfinance_auto_adjusted_ohlcv_v1":
        raise SourceContractError("auxiliary OHLCV schema drift")
    if payload.get("source") != "Yahoo Finance via yfinance":
        raise SourceContractError("auxiliary OHLCV source drift")
    if payload.get("auto_adjust") is not True:
        raise SourceContractError("KRE/KBE OHLCV must be total-return adjusted")
    expected_query = {
        "tickers": list(AUXILIARY_TICKERS),
        "start_inclusive": AUXILIARY_QUERY_START,
        "end_exclusive": AUXILIARY_QUERY_END_EXCLUSIVE,
        "interval": "1d",
    }
    if payload.get("query") != expected_query:
        raise SourceContractError("auxiliary OHLCV query contract drift")
    if payload.get("action_semantics") != AUXILIARY_ACTION_SEMANTICS:
        raise SourceContractError("auxiliary OHLCV action semantics drift")
    runtime = payload.get("runtime") or {}
    if {
        key: runtime.get(key)
        for key in ("actions", "repair", "threads", "group_by")
    } != {
        "actions": False,
        "repair": False,
        "threads": False,
        "group_by": "ticker",
    }:
        raise SourceContractError("auxiliary yfinance runtime contract drift")
    if not str(runtime.get("yfinance_version") or ""):
        raise SourceContractError("auxiliary yfinance version missing")
    rows_by_ticker = payload.get("ohlcv") or {}
    if set(rows_by_ticker) != set(AUXILIARY_TICKERS):
        raise SourceContractError("auxiliary OHLCV ticker set drift")
    calendars: dict[str, list[str]] = {}
    for ticker in AUXILIARY_TICKERS:
        rows = rows_by_ticker[ticker]
        if not isinstance(rows, list) or len(rows) < 400:
            raise SourceContractError(f"insufficient auxiliary rows for {ticker}")
        dates: list[str] = []
        for row in rows:
            day = _bar_date(row)
            values = [_number(row.get(field)) for field in ("open", "high", "low", "close")]
            volume = _number(row.get("volume"))
            if (
                not day
                or any(value is None or value <= 0 for value in values)
                or volume is None
                or volume < 0
            ):
                raise SourceContractError(f"invalid auxiliary bar {ticker} {day}")
            dates.append(day)
        if dates != sorted(dates) or len(dates) != len(set(dates)):
            raise SourceContractError(f"auxiliary calendar invalid for {ticker}")
        if dates[0] > AUXILIARY_QUERY_START or dates[-1] < AUXILIARY_REQUIRED_LAST_DATE:
            raise SourceContractError(
                f"auxiliary coverage insufficient for {ticker}: {dates[0]}..{dates[-1]}"
            )
        calendars[ticker] = dates
    canonical_calendar = calendars[KRE_TICKER]
    if any(calendars[ticker] != canonical_calendar for ticker in AUXILIARY_TICKERS):
        raise SourceContractError("adjusted KRE/KBE/SPY/QQQ calendars disagree")
    identity_payload = {
        "schema": payload["schema"],
        "source": payload.get("source"),
        "query": payload.get("query"),
        "auto_adjust": payload.get("auto_adjust"),
        "action_semantics": payload.get("action_semantics"),
        "runtime": payload.get("runtime"),
        "ohlcv": rows_by_ticker,
    }
    actual = _canonical_sha(identity_payload)
    if payload.get("canonical_rowset_sha256") != actual:
        raise SourceContractError("auxiliary OHLCV rowset SHA drift")
    return dict(payload)


def _download_auxiliary_ohlcv() -> dict[str, Any]:
    import importlib.metadata

    from yfinance_bootstrap import (  # imported only when online materialization is needed
        configure_yfinance_runtime,
        download_with_rate_limit_retry,
    )

    configure_yfinance_runtime()
    data = download_with_rate_limit_retry(
        tickers=list(AUXILIARY_TICKERS),
        start=AUXILIARY_QUERY_START,
        end=AUXILIARY_QUERY_END_EXCLUSIVE,
        auto_adjust=True,
        actions=False,
        progress=False,
        threads=False,
        group_by="ticker",
        repair=False,
    )
    if data is None or getattr(data, "empty", True):
        raise SourceContractError("yfinance returned no KRE/KBE OHLCV")
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ticker in AUXILIARY_TICKERS:
        try:
            frame = data[ticker]
        except Exception as error:
            raise SourceContractError(f"yfinance missing ticker frame {ticker}") from error
        rows: list[dict[str, Any]] = []
        for index, row in frame.iterrows():
            values = {
                "open": _number(row.get("Open")),
                "high": _number(row.get("High")),
                "low": _number(row.get("Low")),
                "close": _number(row.get("Close")),
                "volume": _number(row.get("Volume")),
            }
            if any(values[key] is None for key in ("open", "high", "low", "close")):
                raise SourceContractError(f"yfinance NA adjusted OHLCV for {ticker} {index}")
            if values["volume"] is None:
                raise SourceContractError(f"yfinance NA volume for {ticker} {index}")
            day = index.date().isoformat() if hasattr(index, "date") else str(index)[:10]
            rows.append(
                {
                    "date": day,
                    "open": float(values["open"]),
                    "high": float(values["high"]),
                    "low": float(values["low"]),
                    "close": float(values["close"]),
                    "volume": float(values["volume"]),
                }
            )
        rows_by_ticker[ticker] = rows
    identity_payload = {
        "schema": "yfinance_auto_adjusted_ohlcv_v1",
        "source": "Yahoo Finance via yfinance",
        "query": {
            "tickers": list(AUXILIARY_TICKERS),
            "start_inclusive": AUXILIARY_QUERY_START,
            "end_exclusive": AUXILIARY_QUERY_END_EXCLUSIVE,
            "interval": "1d",
        },
        "auto_adjust": True,
        "action_semantics": AUXILIARY_ACTION_SEMANTICS,
        "runtime": {
            "actions": False,
            "repair": False,
            "threads": False,
            "group_by": "ticker",
            "yfinance_version": importlib.metadata.version("yfinance"),
        },
        "ohlcv": rows_by_ticker,
    }
    return {
        **identity_payload,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "canonical_rowset_sha256": _canonical_sha(identity_payload),
        "row_counts": {
            ticker: len(rows_by_ticker[ticker]) for ticker in AUXILIARY_TICKERS
        },
        "coverage": {
            ticker: {
                "first": rows_by_ticker[ticker][0]["date"],
                "last": rows_by_ticker[ticker][-1]["date"],
            }
            for ticker in AUXILIARY_TICKERS
        },
        "survivorship_contract": (
            "fixed preregistered ETFs KRE/KBE; no constituent or future membership selection"
        ),
    }


def materialize_auxiliary_ohlcv(*, offline: bool) -> dict[str, Any]:
    if AUXILIARY_OHLCV_PATH.is_file():
        return _validate_auxiliary_payload(_read_json(AUXILIARY_OHLCV_PATH))
    if offline:
        raise SourceContractError("offline mode requires frozen KRE/KBE OHLCV")
    payload = _download_auxiliary_ohlcv()
    _validate_auxiliary_payload(payload)
    _atomic_write_json(AUXILIARY_OHLCV_PATH, payload)
    return _validate_auxiliary_payload(_read_json(AUXILIARY_OHLCV_PATH))


def _assert_locked_policy() -> None:
    failures: list[str] = []
    if TRADE_ENABLED is not False:
        failures.append("helper_trade_enabled")
    if LAG_RELEASES != 4:
        failures.append("lag_releases_not_4")
    if NOTIONAL_USD_PER_LEG != 4_000.0:
        failures.append("notional_not_4000_per_leg")
    if ROUND_TRIP_COST_PCT_PER_LEG != 0.0035:
        failures.append("cost_not_35bps_per_leg")
    if MAX_CONCURRENT_PAIRS != 1:
        failures.append("max_concurrent_pairs_not_1")
    if (KRE_TICKER, KBE_TICKER) != ("KRE", "KBE"):
        failures.append("pair_ticker_contract_drift")
    if failures:
        raise SourceContractError(f"locked helper policy drift: {failures}")


def _baseline_window_map(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {str(row["label"]): dict(row) for row in summary.get("windows") or []}
    if set(rows) != set(WINDOWS):
        raise SourceContractError(f"active baseline windows drift: {sorted(rows)}")
    for label, (start, end) in WINDOWS.items():
        if rows[label].get("start") != start or rows[label].get("end") != end:
            raise SourceContractError(f"active baseline dates drift for {label}")
    return rows


def _baseline_curve(window: Mapping[str, Any]) -> list[tuple[str, float]]:
    artifact_path = REPO_ROOT / str(window["path"])
    artifact = _read_json(artifact_path)
    series = artifact.get("sharpe_inference", {}).get("return_series") or []
    equity = 100_000.0
    curve: list[tuple[str, float]] = []
    for row in series:
        day = str(row.get("date") or "")[:10]
        periodic_return = _number(row.get("return"))
        if not day or periodic_return is None or periodic_return <= -1.0:
            raise SourceContractError(
                f"invalid baseline daily return for {window['label']} {day}"
            )
        equity *= 1.0 + periodic_return
        curve.append((day, equity))
    if not curve or [day for day, _ in curve] != sorted(day for day, _ in curve):
        raise SourceContractError(f"baseline curve order drift for {window['label']}")
    expected = 100_000.0 + float(window["total_pnl"])
    if abs(curve[-1][1] - expected) > 0.02:
        raise SourceContractError(
            f"baseline curve PnL reconstruction drift for {window['label']}"
        )
    return curve


def _snapshot_spy_sessions(
    baseline_windows: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    sessions: set[str] = set()
    snapshots: list[dict[str, Any]] = []
    for label in WINDOWS:
        path = REPO_ROOT / str(baseline_windows[label]["source"])
        payload = _read_json(path)
        rows = (payload.get("ohlcv") or {}).get("SPY") or []
        if not rows:
            raise SourceContractError(f"baseline SPY calendar missing for {label}")
        for row in rows:
            day = _bar_date(row)
            if AUXILIARY_QUERY_START <= day <= AUXILIARY_REQUIRED_LAST_DATE:
                sessions.add(day)
        snapshots.append(
            {
                "window": label,
                "path": _repo_rel(path),
                "sha256": _file_sha(path),
                "calendar_ticker": "SPY",
            }
        )
    ordered = sorted(sessions)
    if not ordered or ordered[0] != AUXILIARY_QUERY_START:
        raise SourceContractError("frozen SPY regular-session calendar starts late")
    if ordered[-1] != AUXILIARY_REQUIRED_LAST_DATE:
        raise SourceContractError("frozen SPY regular-session calendar ends early")
    if any(date.fromisoformat(day).weekday() >= 5 for day in ordered):
        raise SourceContractError("frozen SPY calendar contains a weekend")
    return ordered, {
        "schema": "frozen_spy_regular_session_proxy_v1",
        "coverage": {"first": ordered[0], "last": ordered[-1], "count": len(ordered)},
        "session_dates_sha256": _canonical_sha(ordered),
        "snapshots": snapshots,
        "independence_note": (
            "pre-existing Gate1 frozen SPY snapshot dates independently check the "
            "new auxiliary vendor panel calendar; prices are not reused"
        ),
    }


def _bar_index(
    rows_by_ticker: Mapping[str, Iterable[Mapping[str, Any]]]
) -> dict[str, dict[str, dict[str, float]]]:
    output: dict[str, dict[str, dict[str, float]]] = {}
    for ticker, rows in rows_by_ticker.items():
        output[str(ticker)] = {}
        for row in rows:
            day = _bar_date(row)
            values: dict[str, float] = {}
            for lower, upper in (
                ("open", "Open"),
                ("high", "High"),
                ("low", "Low"),
                ("close", "Close"),
            ):
                value = _number(row.get(lower) if lower in row else row.get(upper))
                if value is None or value <= 0:
                    raise SourceContractError(f"invalid {ticker} {lower} on {day}")
                values[lower] = value
            if not day or day in output[str(ticker)]:
                raise SourceContractError(f"duplicate/blank {ticker} bar date {day}")
            output[str(ticker)][day] = values
    return output


def _validate_auxiliary_calendar(
    auxiliary: Mapping[str, Any], frozen_sessions: list[str]
) -> list[str]:
    rows = auxiliary.get("ohlcv") or {}
    aux_sessions = [_bar_date(row) for row in rows["SPY"]]
    through_window = [
        day
        for day in aux_sessions
        if AUXILIARY_QUERY_START <= day <= AUXILIARY_REQUIRED_LAST_DATE
    ]
    if through_window != frozen_sessions:
        missing = sorted(set(frozen_sessions) - set(through_window))
        extras = sorted(set(through_window) - set(frozen_sessions))
        raise SourceContractError(
            "auxiliary calendar disagrees with frozen SPY calendar: "
            f"missing={missing[:10]} extras={extras[:10]}"
        )
    for ticker in AUXILIARY_TICKERS:
        ticker_dates = [_bar_date(row) for row in rows[ticker]]
        if ticker_dates != aux_sessions:
            raise SourceContractError(f"auxiliary ticker calendar drift for {ticker}")
    return frozen_sessions


def _atr14_sentinel(
    ticker: str,
    entry_date: str,
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    ticker_bars = bars.get(ticker) or {}
    prior_dates = sorted(day for day in ticker_bars if day < entry_date)
    if len(prior_dates) < 15:
        raise SourceContractError(
            f"insufficient PIT ATR history for {ticker} entry {entry_date}"
        )
    true_ranges: list[tuple[str, float]] = []
    for previous_day, day in zip(prior_dates, prior_dates[1:]):
        previous_close = float(ticker_bars[previous_day]["close"])
        row = ticker_bars[day]
        true_range = max(
            row["high"] - row["low"],
            abs(row["high"] - previous_close),
            abs(row["low"] - previous_close),
        )
        true_ranges.append((day, true_range))
    if len(true_ranges) < 14:
        raise SourceContractError(f"ATR14 unavailable for {ticker} {entry_date}")
    selected = true_ranges[-14:]
    atr = sum(value for _, value in selected) / 14.0
    if not math.isfinite(atr) or atr <= 0:
        raise SourceContractError(f"ATR14 invalid for {ticker} {entry_date}")
    return {
        "atr14": atr,
        "atr_as_of": selected[-1][0],
        "atr_first_session": selected[0][0],
        "atr_session_count": 14,
        "uses_entry_or_future_high_low_close": False,
    }


def _enrich_gate2_target_sentinel(
    decision: Mapping[str, Any],
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    row = dict(decision)
    if row.get("status") != "settled":
        return row
    entry_date = str(row.get("entry_date") or "")
    long_ticker = str(row.get("long_ticker") or "")
    entry_bar = bars.get(long_ticker, {}).get(entry_date)
    if not entry_date or entry_bar is None:
        raise SourceContractError(
            f"Gate2 sentinel entry bar missing for {row.get('decision_id')}"
        )
    atr = _atr14_sentinel(long_ticker, entry_date, bars)
    if not atr["atr_as_of"] < entry_date:
        raise SourceContractError("Gate2 ATR sentinel has look-ahead")
    target_price = float(entry_bar["open"]) + 3.5 * float(atr["atr14"])
    if not math.isfinite(target_price) or target_price <= 0:
        raise SourceContractError("Gate2 ATR target price invalid")
    row.update(
        {
            "helper_target_price": decision.get("target_price"),
            "target_price": target_price,
            "target_price_ticker": long_ticker,
            "target_price_atr14": atr["atr14"],
            "target_price_atr_as_of": atr["atr_as_of"],
            "target_price_atr_first_session": atr["atr_first_session"],
            "target_price_role": "gate2_signal_contract_sentinel_only",
            "target_price_execution_enabled": False,
            "actual_exit_policy": "strict_next_release_open",
            "replay_reads_target_price": False,
        }
    )
    enriched_legs: list[dict[str, Any]] = []
    for raw_leg in row.get("legs") or []:
        leg = dict(raw_leg)
        if leg.get("side") == "long":
            leg.update(
                {
                    "entry_date": entry_date,
                    "target_price": target_price,
                    "target_price_applicable": True,
                    "target_price_role": "gate2_signal_contract_sentinel_only",
                    "target_price_execution_enabled": False,
                }
            )
        else:
            leg.update(
                {
                    "entry_date": entry_date,
                    "target_price": None,
                    "target_price_applicable": False,
                    "target_price_role": "not_applicable_short_leg",
                    "target_price_execution_enabled": False,
                }
            )
        enriched_legs.append(leg)
    row["legs"] = enriched_legs
    return row


def _decision_trade(
    decision: Mapping[str, Any],
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    # Intentionally never read target_price: the locked exit is next-release open.
    entry_date = str(decision.get("entry_date") or "")
    exit_date = str(decision.get("exit_date") or "")
    if decision.get("status") != "settled" or not entry_date or not exit_date:
        raise SourceContractError(f"non-settled decision passed to replay: {decision}")
    if not entry_date < exit_date:
        raise SourceContractError(f"non-positive pair holding interval: {decision}")
    long_ticker = str(decision.get("long_ticker") or "")
    short_ticker = str(decision.get("short_ticker") or "")
    if {long_ticker, short_ticker} != set(PAIR_TICKERS):
        raise SourceContractError(f"unexpected pair orientation: {decision}")
    prices: dict[str, dict[str, float]] = {}
    for ticker in PAIR_TICKERS:
        entry = bars.get(ticker, {}).get(entry_date)
        exit_row = bars.get(ticker, {}).get(exit_date)
        if entry is None or exit_row is None:
            raise SourceContractError(
                f"missing adjusted entry/exit open for {ticker} "
                f"{entry_date}->{exit_date}"
            )
        prices[ticker] = {
            "entry_open": float(entry["open"]),
            "exit_open": float(exit_row["open"]),
        }
    long_shares = NOTIONAL_USD_PER_LEG / prices[long_ticker]["entry_open"]
    short_shares = NOTIONAL_USD_PER_LEG / prices[short_ticker]["entry_open"]
    long_gross_pnl = long_shares * (
        prices[long_ticker]["exit_open"] - prices[long_ticker]["entry_open"]
    )
    short_gross_pnl = short_shares * (
        prices[short_ticker]["entry_open"] - prices[short_ticker]["exit_open"]
    )
    cost_per_leg = NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
    net_pnl = long_gross_pnl + short_gross_pnl - 2.0 * cost_per_leg
    return {
        **dict(decision),
        "price_basis": "split_and_distribution_adjusted_ohlc",
        "fixed_share_semantics": "$4000 divided by adjusted entry open per leg",
        "long_shares": long_shares,
        "short_shares": short_shares,
        "prices": prices,
        "long_gross_pnl": long_gross_pnl,
        "short_gross_pnl": short_gross_pnl,
        "gross_pair_pnl": long_gross_pnl + short_gross_pnl,
        "round_trip_cost_usd_per_leg": cost_per_leg,
        "round_trip_cost_usd_pair": 2.0 * cost_per_leg,
        "net_pair_pnl": net_pnl,
        "net_pair_return_on_8000_gross": net_pnl / PAIR_INITIAL_CAPITAL,
        "net_pair_return_on_100000_protocol_capital": net_pnl / 100_000.0,
    }


def _pair_mark_on_date(
    trades: Iterable[Mapping[str, Any]],
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
    day: str,
) -> float:
    total = 0.0
    half_cost_per_leg = (
        NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG / 2.0
    )
    for trade in trades:
        entry_date = str(trade["entry_date"])
        exit_date = str(trade["exit_date"])
        if day < entry_date:
            continue
        if day >= exit_date:
            total += float(trade["net_pair_pnl"])
            continue
        long_ticker = str(trade["long_ticker"])
        short_ticker = str(trade["short_ticker"])
        long_close = bars.get(long_ticker, {}).get(day)
        short_close = bars.get(short_ticker, {}).get(day)
        if long_close is None or short_close is None:
            raise SourceContractError(
                f"missing adjusted pair MTM close on {day} for {trade['decision_id']}"
            )
        prices = trade["prices"]
        long_mark = float(trade["long_shares"]) * (
            long_close["close"] - prices[long_ticker]["entry_open"]
        )
        short_mark = float(trade["short_shares"]) * (
            prices[short_ticker]["entry_open"] - short_close["close"]
        )
        # Entry half-cost is visible while open. At exit the realized PnL above
        # includes the second half. A same-day rebalance therefore closes one
        # pair and opens the next with both distinct half-cost events.
        total += long_mark + short_mark - 2.0 * half_cost_per_leg
    return total


def _curve_metrics(
    curve: list[tuple[str, float]],
    *,
    initial_capital: float,
    trade_count: int,
) -> dict[str, Any]:
    if not curve:
        raise SourceContractError("cannot calculate metrics on empty curve")
    previous = initial_capital
    peak = initial_capital
    drawdown = 0.0
    returns: list[dict[str, Any]] = []
    for day, equity in curve:
        if not math.isfinite(equity) or equity <= 0:
            raise SourceContractError(f"non-positive equity on {day}: {equity}")
        periodic_return = equity / previous - 1.0
        returns.append({"date": day, "return": periodic_return})
        previous = equity
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
    samples = [float(row["return"]) for row in returns]
    sharpe: float | None = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(252.0)
    total_pnl = curve[-1][1] - initial_capital
    total_return = total_pnl / initial_capital
    total_return_public = round(total_return, 4)
    sharpe_public = round(sharpe, 2) if sharpe is not None else None
    return {
        "initial_capital": initial_capital,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_full_precision": total_pnl,
        "benchmarks": {"strategy_total_return_pct": total_return_public},
        "strategy_total_return_full_precision": total_return,
        "sharpe_daily": sharpe_public,
        "sharpe_daily_full_precision": sharpe,
        "expected_value_score": (
            round(total_return_public * abs(sharpe_public), 4)
            if sharpe_public is not None
            else None
        ),
        "max_drawdown_pct": round(drawdown, 4),
        "max_drawdown_full_precision": drawdown,
        "total_trades": trade_count,
        "return_series": returns,
        "return_series_sha256": _canonical_sha(
            {"schema": "dated_daily_return_series_v1", "rows": returns}
        ),
    }


def _aggregate_metrics(
    window_metrics: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    ordered_labels = sorted(WINDOWS, key=lambda label: WINDOWS[label][0])
    returns = [
        dict(point, window=label)
        for label in ordered_labels
        for point in window_metrics[label]["return_series"]
    ]
    samples = [float(row["return"]) for row in returns]
    sharpe: float | None = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(252.0)
    initial_capital = sum(float(window_metrics[label]["initial_capital"]) for label in WINDOWS)
    total_pnl_full = sum(
        float(window_metrics[label]["total_pnl_full_precision"])
        for label in WINDOWS
    )
    total_pnl = sum(float(window_metrics[label]["total_pnl"]) for label in WINDOWS)
    total_return = total_pnl / initial_capital
    total_return_public = round(total_return, 4)
    sharpe_public = round(sharpe, 2) if sharpe is not None else None
    ev_sum = round(
        sum(float(window_metrics[label]["expected_value_score"]) for label in WINDOWS),
        4,
    )
    pooled_ev = (
        round(total_return_public * abs(sharpe_public), 4)
        if sharpe_public is not None
        else None
    )
    return {
        "aggregation": (
            "daily returns concatenated chronologically across disjoint windows; "
            "PnL divided by summed independent window capital; drawdown is worst rebuilt window"
        ),
        "initial_capital": initial_capital,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_full_precision": total_pnl_full,
        "benchmarks": {"strategy_total_return_pct": total_return_public},
        "strategy_total_return_full_precision": total_return,
        "expected_value_score": ev_sum,
        "expected_value_score_sum": ev_sum,
        "pooled_daily_diagnostic": {
            "sharpe_daily": sharpe_public,
            "sharpe_daily_full_precision": sharpe,
            "expected_value_score": pooled_ev,
            "binding_gate_role": False,
        },
        "max_drawdown_pct": max(
            float(window_metrics[label]["max_drawdown_pct"]) for label in WINDOWS
        ),
        "total_trades": sum(int(window_metrics[label]["total_trades"]) for label in WINDOWS),
        "positive_return_windows": sum(
            float(window_metrics[label]["benchmarks"]["strategy_total_return_pct"]) > 0
            for label in WINDOWS
        ),
        "minimum_window_return": min(
            float(window_metrics[label]["benchmarks"]["strategy_total_return_pct"])
            for label in WINDOWS
        ),
        "return_series": returns,
        "return_series_sha256": _canonical_sha(
            {"schema": "segmented_daily_return_series_v1", "rows": returns}
        ),
    }


def _baseline_metrics(
    window: Mapping[str, Any], curve: list[tuple[str, float]]
) -> dict[str, Any]:
    calculated = _curve_metrics(
        curve, initial_capital=100_000.0, trade_count=int(window["trade_count"])
    )
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    source_series = artifact["sharpe_inference"]["return_series"]
    source_series_sha = _canonical_sha(
        {"schema": "dated_periodic_return_series_v1", "rows": source_series}
    )
    hard_checks = {
        "total_pnl_within_2c": abs(
            float(calculated["total_pnl"]) - float(window["total_pnl"])
        )
        <= 0.02,
        "public_sharpe_equal": calculated["sharpe_daily"] == window["sharpe_daily"],
        "public_ev_equal": (
            calculated["expected_value_score"] == window["expected_value_score"]
        ),
        "public_drawdown_equal": (
            calculated["max_drawdown_pct"] == window["max_drawdown_pct"]
        ),
        "trade_count_equal": calculated["total_trades"] == window["trade_count"],
        "daily_return_hash_equal": (
            source_series_sha == window["daily_return_series_sha256"]
            == artifact["sharpe_inference"]["return_series_sha256"]
        ),
    }
    if not all(hard_checks.values()):
        raise SourceContractError(
            f"accepted baseline public/curve contract drift for {window['label']}: "
            f"{hard_checks}"
        )
    # Binding public fields stay byte-for-byte aligned with the accepted Gate1
    # anchor; full-precision curve fields remain available for diagnostics and
    # for the combined daily-equity reconstruction.
    calculated.update(
        {
            "total_pnl": float(window["total_pnl"]),
            "sharpe_daily": float(window["sharpe_daily"]),
            "expected_value_score": float(window["expected_value_score"]),
            "max_drawdown_pct": float(window["max_drawdown_pct"]),
            "return_series": source_series,
            "return_series_sha256": source_series_sha,
            "accepted_baseline_expected_value_score": window["expected_value_score"],
            "accepted_baseline_sharpe_daily": window["sharpe_daily"],
            "accepted_baseline_sharpe_daily_full_precision": window[
                "sharpe_daily_full_precision"
            ],
            "accepted_baseline_max_drawdown_pct": window["max_drawdown_pct"],
            "signals_generated": window["signals_generated"],
            "signals_survived": window["signals_survived"],
            "survival_rate": window["survival_rate"],
            "gate1_hard_checks": hard_checks,
        }
    )
    return calculated


def _window_curves(
    baseline: Mapping[str, Any],
    trades: list[dict[str, Any]],
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    baseline_curve = _baseline_curve(baseline)
    pair_curve = [
        (day, 100_000.0 + _pair_mark_on_date(trades, bars, day))
        for day, _ in baseline_curve
    ]
    combined_curve = [
        (day, equity + _pair_mark_on_date(trades, bars, day))
        for day, equity in baseline_curve
    ]
    before = _baseline_metrics(baseline, baseline_curve)
    pair = _curve_metrics(
        pair_curve, initial_capital=100_000.0, trade_count=len(trades)
    )
    pair_pnl = sum(float(trade["net_pair_pnl"]) for trade in trades)
    if abs(float(pair["total_pnl"]) - pair_pnl) > 0.02:
        raise SourceContractError(
            f"pair daily MTM/final PnL drift for {baseline['label']}"
        )
    pair["return_on_fixed_8000_gross"] = pair_pnl / PAIR_INITIAL_CAPITAL
    pair["fixed_gross_capital"] = PAIR_INITIAL_CAPITAL
    after = _curve_metrics(
        combined_curve,
        initial_capital=100_000.0,
        trade_count=int(baseline["trade_count"]) + len(trades),
    )
    after.update(
        {
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
        }
    )
    if abs((float(after["total_pnl"]) - float(before["total_pnl"])) - pair_pnl) > 0.02:
        raise SourceContractError(
            f"after-before PnL does not equal pair PnL for {baseline['label']}"
        )
    return before, pair, after


def _orientation_pnl(
    *,
    long_ticker: str,
    short_ticker: str,
    entry_date: str,
    exit_date: str,
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> float:
    long_entry = bars[long_ticker][entry_date]["open"]
    long_exit = bars[long_ticker][exit_date]["open"]
    short_entry = bars[short_ticker][entry_date]["open"]
    short_exit = bars[short_ticker][exit_date]["open"]
    return (
        NOTIONAL_USD_PER_LEG * (long_exit / long_entry - 1.0)
        + NOTIONAL_USD_PER_LEG * (1.0 - short_exit / short_entry)
        - 2.0 * NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
    )


def _benchmark_trade_pnls(
    trade: Mapping[str, Any],
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, float]:
    entry_date = str(trade["entry_date"])
    exit_date = str(trade["exit_date"])
    result = {"TARGET": float(trade["net_pair_pnl"]), "CASH": 0.0}
    pair_cost = 2.0 * NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
    for ticker in LONG_ONLY_COMPARATORS:
        entry = bars.get(ticker, {}).get(entry_date)
        exit_row = bars.get(ticker, {}).get(exit_date)
        if entry is None or exit_row is None:
            raise SourceContractError(
                f"missing adjusted comparator open for {ticker} {entry_date}->{exit_date}"
            )
        result[ticker] = PAIR_INITIAL_CAPITAL * (
            exit_row["open"] / entry["open"] - 1.0
        ) - pair_cost
    result["STATIC_LONG_KRE_SHORT_KBE"] = _orientation_pnl(
        long_ticker=KRE_TICKER,
        short_ticker=KBE_TICKER,
        entry_date=entry_date,
        exit_date=exit_date,
        bars=bars,
    )
    result["STATIC_LONG_KBE_SHORT_KRE"] = _orientation_pnl(
        long_ticker=KBE_TICKER,
        short_ticker=KRE_TICKER,
        entry_date=entry_date,
        exit_date=exit_date,
        bars=bars,
    )
    return result


def _benchmark_diagnostics(
    trades_by_window: Mapping[str, list[dict[str, Any]]],
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    totals = {
        name: 0.0
        for name in (
            "TARGET",
            *REQUIRED_COMPARATORS,
            *STATIC_PAIR_COMPARATORS,
        )
    }
    by_window: dict[str, Any] = {}
    event_rows: list[dict[str, Any]] = []
    for label in WINDOWS:
        window_totals = {name: 0.0 for name in totals}
        for trade in trades_by_window[label]:
            pnls = _benchmark_trade_pnls(trade, bars)
            event_rows.append(
                {
                    "window": label,
                    "decision_id": trade["decision_id"],
                    "entry_date": trade["entry_date"],
                    "exit_date": trade["exit_date"],
                    "matched_pnl": pnls,
                }
            )
            for name, pnl in pnls.items():
                window_totals[name] += pnl
                totals[name] += pnl
        by_window[label] = {
            "event_count": len(trades_by_window[label]),
            "matched_total_pnl": window_totals,
            "target_beats": {
                name: window_totals["TARGET"] > window_totals[name]
                for name in REQUIRED_COMPARATORS
            },
        }
    failed = [name for name in REQUIRED_COMPARATORS if totals["TARGET"] <= totals[name]]
    return {
        "schema": "matched_weekly_open_to_open_comparators_v1",
        "price_basis": "split_and_distribution_adjusted_ohlc",
        "event_equal_clocked": True,
        "gross_usd_per_event": PAIR_INITIAL_CAPITAL,
        "round_trip_cost_usd_per_event": (
            2.0 * NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
        ),
        "long_only_semantics": (
            "two identical $4000 long legs on the same adjusted open-open clock"
        ),
        "static_pair_semantics": (
            "one $4000 long and one $4000 short leg on the same adjusted open-open clock"
        ),
        "event_count": len(event_rows),
        "events": event_rows,
        "by_window": by_window,
        "aggregate_matched_total_pnl": totals,
        "required_comparators": list(REQUIRED_COMPARATORS),
        "diagnostic_only_comparators": list(STATIC_PAIR_COMPARATORS),
        "failed_comparators": failed,
        "missing_bars_is_hard_failure": True,
        "passed": bool(event_rows) and not failed,
    }


def _full_window_buy_hold(
    bars: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    pair_cost = 2.0 * NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
    all_sessions = sorted(bars["SPY"])
    for label, (start, end) in WINDOWS.items():
        sessions = [day for day in all_sessions if start <= day <= end]
        if not sessions:
            raise SourceContractError(f"no full-window comparator sessions for {label}")
        entry_date, exit_date = sessions[0], sessions[-1]
        values: dict[str, float] = {"CASH": 0.0}
        for ticker in LONG_ONLY_COMPARATORS:
            values[ticker] = PAIR_INITIAL_CAPITAL * (
                bars[ticker][exit_date]["close"] / bars[ticker][entry_date]["open"]
                - 1.0
            ) - pair_cost
        values["STATIC_LONG_KRE_SHORT_KBE"] = (
            NOTIONAL_USD_PER_LEG
            * (
                bars[KRE_TICKER][exit_date]["close"]
                / bars[KRE_TICKER][entry_date]["open"]
                - 1.0
            )
            + NOTIONAL_USD_PER_LEG
            * (
                1.0
                - bars[KBE_TICKER][exit_date]["close"]
                / bars[KBE_TICKER][entry_date]["open"]
            )
            - pair_cost
        )
        values["STATIC_LONG_KBE_SHORT_KRE"] = (
            NOTIONAL_USD_PER_LEG
            * (
                bars[KBE_TICKER][exit_date]["close"]
                / bars[KBE_TICKER][entry_date]["open"]
                - 1.0
            )
            + NOTIONAL_USD_PER_LEG
            * (
                1.0
                - bars[KRE_TICKER][exit_date]["close"]
                / bars[KRE_TICKER][entry_date]["open"]
            )
            - pair_cost
        )
        diagnostics[label] = {
            "entry_date": entry_date,
            "entry_price": "adjusted open",
            "exit_date": exit_date,
            "exit_price": "adjusted close",
            "matched_total_pnl": values,
            "gate_role": "diagnostic_only_not_weekly_replacement_gate",
        }
    return diagnostics


def _concentration(trades: list[dict[str, Any]]) -> dict[str, Any]:
    positive = sorted(
        (float(trade["net_pair_pnl"]) for trade in trades if trade["net_pair_pnl"] > 0),
        reverse=True,
    )
    positive_total = sum(positive)
    top_five = sum(positive[:5]) / positive_total if positive_total > 0 else None
    return {
        "week_count": len(trades),
        "positive_week_count": len(positive),
        "positive_week_pnl_total": positive_total,
        "top_five_positive_week_contribution": top_five,
        "denominator": "total positive weekly net PnL",
        "no_positive_weeks_is_failure": True,
    }


def _capital_accounting_gate(
    baseline_windows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    min_cash = {
        label: float((baseline_windows[label].get("cash_ledger") or {}).get("min_cash", 0.0))
        for label in WINDOWS
    }
    insufficient = [label for label, value in min_cash.items() if value < PAIR_INITIAL_CAPITAL]
    return {
        "passed": not insufficient,
        "capital_accounting": "external_overlay_not_cash_conserving",
        "required_gross_pair_capital_usd": PAIR_INITIAL_CAPITAL,
        "baseline_min_cash_by_window": min_cash,
        "insufficient_cash_windows": insufficient,
        "margin_and_short_borrow_modelled": False,
        "short_availability_modelled": False,
        "core_displacement_policy_modelled": False,
        "live_eligible": False,
        "hard_failures": (
            []
            if not insufficient
            else ["combined_cash_feasibility_unproven_external_overlay"]
        ),
        "interpretation": (
            "Combined curves are additive alpha diagnostics only. The accepted core "
            "cash ledger nearly exhausts cash, and no $8k gross reserve, displacement, "
            "margin, locate, or borrow policy was preregistered."
        ),
    }


def _gate2_audit(trades: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    for trade in trades:
        decision_id = str(trade.get("decision_id") or "")
        target = _number(trade.get("target_price"))
        if not trade.get("entry_date") or target is None or target <= 0:
            failures.append(f"missing_entry_or_scalar_target:{decision_id}")
        if not str(trade.get("target_price_atr_as_of") or "") < str(
            trade.get("entry_date") or ""
        ):
            failures.append(f"target_atr_not_pit:{decision_id}")
        if trade.get("target_price_role") != "gate2_signal_contract_sentinel_only":
            failures.append(f"target_role_drift:{decision_id}")
        if trade.get("target_price_execution_enabled") is not False:
            failures.append(f"target_execution_enabled:{decision_id}")
        if trade.get("actual_exit_policy") != "strict_next_release_open":
            failures.append(f"actual_exit_policy_drift:{decision_id}")
        if trade.get("replay_reads_target_price") is not False:
            failures.append(f"replay_target_read_not_disproved:{decision_id}")
    return {
        "passed": bool(trades) and not failures,
        "settled_pair_count": len(trades),
        "entry_date_present_count": sum(bool(row.get("entry_date")) for row in trades),
        "scalar_target_price_present_count": sum(
            (_number(row.get("target_price")) or 0.0) > 0 for row in trades
        ),
        "target_role": "gate2_signal_contract_sentinel_only",
        "target_calculation": (
            "adjusted long-leg entry open + 3.5 * ATR14; ATR uses high/low/close "
            "only through the prior session"
        ),
        "target_execution_enabled": False,
        "actual_exit_policy": "strict_next_release_open",
        "hard_failures": failures,
    }


def _build_evaluation(*, offline: bool) -> dict[str, Any]:
    _assert_locked_policy()
    releases, source_manifest = materialize_source(offline=offline)
    auxiliary = materialize_auxiliary_ohlcv(offline=offline)
    if not BASELINE_PATH.is_file():
        raise SourceContractError(f"active baseline missing: {BASELINE_PATH}")
    if (
        BASELINE_PATH.stat().st_size != EXPECTED_BASELINE_BYTES
        or _file_sha(BASELINE_PATH) != EXPECTED_BASELINE_SHA256
    ):
        raise SourceContractError("active baseline file identity drift")
    baseline_summary = _read_json(BASELINE_PATH)
    if baseline_summary.get("experiment_id") != "exp-20260715-010":
        raise SourceContractError("active baseline experiment identity drift")
    baseline_windows = _baseline_window_map(baseline_summary)
    frozen_sessions, calendar_identity = _snapshot_spy_sessions(baseline_windows)
    trading_sessions = _validate_auxiliary_calendar(auxiliary, frozen_sessions)
    bars = _bar_index(auxiliary["ohlcv"])

    decisions = build_weekly_pair_decisions(releases, trading_sessions)
    if len(decisions) != CANONICAL_RELEASE_COUNT:
        raise SourceContractError(f"helper decision count drift: {len(decisions)}")
    if any(decision.get("trade_enabled") is not False for decision in decisions):
        raise SourceContractError("helper emitted a trade-enabled decision")

    enriched_decisions: list[dict[str, Any]] = []
    for decision in decisions:
        release_date = str(decision.get("release_date") or "")
        if not CANONICAL_START <= release_date <= CANONICAL_END:
            raise SourceContractError(f"decision release outside canonical span: {release_date}")
        if decision.get("entry_date") and not str(decision["entry_date"]) > release_date:
            raise SourceContractError(f"entry is not strict post-release: {decision}")
        if decision.get("exit_date") and not str(decision["exit_date"]) > str(
            decision.get("next_release_date") or "9999-12-31"
        ):
            raise SourceContractError(f"exit is not strict post-next-release: {decision}")
        enriched_decisions.append(_enrich_gate2_target_sentinel(decision, bars))

    trades_by_window: dict[str, list[dict[str, Any]]] = {label: [] for label in WINDOWS}
    decision_audits: dict[str, Any] = {}
    generated_total = 0
    survived_total = 0
    market_data_rejects: list[dict[str, Any]] = []
    for label, (start, end) in WINDOWS.items():
        generated = [
            decision
            for decision in enriched_decisions
            if decision.get("entry_date")
            and start <= str(decision["entry_date"]) <= end
        ]
        generated_total += len(generated)
        reject_counts: dict[str, int] = {}
        for decision in generated:
            reason: str | None = None
            if decision.get("status") == "no_pair_exact_zero_signal":
                reason = "exact_zero_signal"
            elif decision.get("status") != "settled":
                reason = str(decision.get("status") or "not_settled")
            elif not str(decision.get("exit_date") or "") <= end:
                reason = "exit_outside_window"
            if reason is not None:
                reject_counts[reason] = reject_counts.get(reason, 0) + 1
                continue
            try:
                trade = _decision_trade(decision, bars)
            except SourceContractError as error:
                reject_counts["market_data_contract"] = (
                    reject_counts.get("market_data_contract", 0) + 1
                )
                market_data_rejects.append(
                    {"decision_id": decision.get("decision_id"), "error": str(error)}
                )
                continue
            trade["window"] = label
            trades_by_window[label].append(trade)
        survived = len(trades_by_window[label])
        survived_total += survived
        decision_audits[label] = {
            "statistical_unit": "one lag4-eligible H.8 release pair-week",
            "signals_generated": len(generated),
            "signals_survived": survived,
            "survival_rate": survived / len(generated) if generated else 0.0,
            "reject_counts": reject_counts,
        }

    windows: dict[str, Any] = {}
    before_metrics: dict[str, dict[str, Any]] = {}
    pair_metrics: dict[str, dict[str, Any]] = {}
    after_metrics: dict[str, dict[str, Any]] = {}
    for label in WINDOWS:
        before, pair, after = _window_curves(
            baseline_windows[label], trades_by_window[label], bars
        )
        before_metrics[label] = before
        pair_metrics[label] = pair
        after_metrics[label] = after
        windows[label] = {
            "start": WINDOWS[label][0],
            "end": WINDOWS[label][1],
            "before": before,
            "pair": pair,
            "after": after,
            "delta": {
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 2),
                "expected_value_score": round(
                    after["expected_value_score"] - before["expected_value_score"], 4
                ),
                "max_drawdown_pct": round(
                    after["max_drawdown_pct"] - before["max_drawdown_pct"], 4
                ),
                "survival_rate": 0.0,
            },
            "decision_audit": decision_audits[label],
            "settled_pairs": trades_by_window[label],
        }

    aggregate_before = _aggregate_metrics(before_metrics)
    aggregate_pair = _aggregate_metrics(pair_metrics)
    aggregate_after = _aggregate_metrics(after_metrics)
    accepted_aggregate = baseline_summary.get("aggregate") or {}
    baseline_aggregate_checks = {
        "expected_value_score_sum": (
            aggregate_before["expected_value_score_sum"]
            == accepted_aggregate.get("expected_value_score_sum")
            == 6.2057
        ),
        "total_pnl_sum": (
            aggregate_before["total_pnl"]
            == accepted_aggregate.get("total_pnl_sum")
            == 130_992.36
        ),
        "trade_count_sum": (
            aggregate_before["total_trades"]
            == accepted_aggregate.get("trade_count_sum")
            == 49
        ),
    }
    if not all(baseline_aggregate_checks.values()):
        raise SourceContractError(
            f"active Gate1 aggregate anchor drift: {baseline_aggregate_checks}"
        )
    pair_pnl_total = sum(
        float(trade["net_pair_pnl"])
        for label in WINDOWS
        for trade in trades_by_window[label]
    )
    if abs(
        (
            aggregate_after["total_pnl_full_precision"]
            - aggregate_before["total_pnl_full_precision"]
        )
        - pair_pnl_total
    ) > 0.03:
        raise SourceContractError("aggregate after-before PnL does not equal pair PnL")

    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    benchmarks = _benchmark_diagnostics(trades_by_window, bars)
    buy_hold = _full_window_buy_hold(bars)
    concentration = _concentration(all_trades)
    gate2 = _gate2_audit(all_trades)
    gate3_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0
        and gate3_rate >= 0.05
        and all(
            decision_audits[label]["survival_rate"] >= 0.05 for label in WINDOWS
        )
        and not market_data_rejects,
        "statistical_unit": "one lag4-eligible H.8 release pair-week",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": gate3_rate,
        "by_window": decision_audits,
        "market_data_contract_rejects": market_data_rejects,
    }
    combined_dd_worse = max(
        float(windows[label]["delta"]["max_drawdown_pct"]) for label in WINDOWS
    )
    capital_gate = _capital_accounting_gate(baseline_windows)

    numeric_failures: list[str] = []
    if not gate2["passed"]:
        numeric_failures.append("gate2_entry_target_sentinel_failed")
    if not gate3["passed"]:
        numeric_failures.append("gate3_pair_week_survival_failed")
    for label in WINDOWS:
        if len(trades_by_window[label]) < MIN_SETTLED_PAIRS_PER_WINDOW:
            numeric_failures.append(f"settled_pair_count_below_20:{label}")
    if aggregate_pair["total_pnl"] <= 0:
        numeric_failures.append("aggregate_pair_net_pnl_not_positive")
    if (aggregate_pair["expected_value_score"] or 0.0) <= 0:
        numeric_failures.append("aggregate_pair_ev_not_positive")
    if aggregate_pair["positive_return_windows"] < MIN_POSITIVE_WINDOWS:
        numeric_failures.append("fewer_than_two_positive_pair_windows")
    if aggregate_pair["minimum_window_return"] < MIN_WINDOW_RETURN:
        numeric_failures.append("pair_window_return_below_minus_2pct")
    if aggregate_after["total_pnl"] <= aggregate_before["total_pnl"]:
        numeric_failures.append("combined_aggregate_pnl_not_improved")
    if (aggregate_after["expected_value_score"] or -math.inf) <= (
        aggregate_before["expected_value_score"] or -math.inf
    ):
        numeric_failures.append("combined_aggregate_ev_not_improved")
    if combined_dd_worse > MAX_COMBINED_DRAWDOWN_WORSE:
        numeric_failures.append("combined_drawdown_worse_over_0_5pct")
    if aggregate_pair["max_drawdown_pct"] > MAX_PAIR_DRAWDOWN:
        numeric_failures.append("standalone_pair_drawdown_over_10pct")
    top_five = concentration["top_five_positive_week_contribution"]
    if top_five is None or top_five > MAX_TOP_FIVE_POSITIVE_CONTRIBUTION:
        numeric_failures.append("top_five_positive_week_contribution_over_60pct")
    if not benchmarks["passed"]:
        numeric_failures.append("matched_replacement_comparator_not_beaten")
    numeric_failures = list(dict.fromkeys(numeric_failures))
    numeric_gate4 = {
        "passed": not numeric_failures,
        "status": "passed" if not numeric_failures else "rejected",
        "hard_failures": numeric_failures,
        "thresholds": {
            "min_settled_pairs_per_window": MIN_SETTLED_PAIRS_PER_WINDOW,
            "min_positive_windows": MIN_POSITIVE_WINDOWS,
            "min_window_return": MIN_WINDOW_RETURN,
            "max_pair_drawdown": MAX_PAIR_DRAWDOWN,
            "max_combined_drawdown_worse": MAX_COMBINED_DRAWDOWN_WORSE,
            "max_top_five_positive_contribution": (
                MAX_TOP_FIVE_POSITIVE_CONTRIBUTION
            ),
        },
        "metrics": {
            "aggregate_before": aggregate_before,
            "aggregate_pair": aggregate_pair,
            "aggregate_after": aggregate_after,
            "combined_drawdown_worse_max": combined_dd_worse,
            "concentration": concentration,
        },
    }
    # Gate4 judges the preregistered default-off alpha measurement. Capital,
    # margin, locate, and displacement remain a binding Gate5/live constraint;
    # they do not turn a valid paper alpha into a numeric Gate4 rejection.
    binding_failures = list(numeric_failures)
    gate4 = {
        "passed": not binding_failures,
        "status": "passed" if not binding_failures else "blocked",
        "hard_failures": binding_failures,
        "numeric_alpha_measurement": numeric_gate4,
        "capital_accounting_gate": capital_gate,
        "interpretation": (
            "The combined curve is an external-capital diagnostic, not a claim of "
            "cash feasibility. Capital accounting blocks Gate5/live eligibility, "
            "while Gate4 remains the default-off alpha measurement."
        ),
    }
    gate5 = {
        "passed": False,
        "status": "blocked",
        "prospective_closed_pair_count": 0,
        "minimum_prospective_closed_pairs": 30,
        "deflated_sharpe_status": "not_computable_single_preregistered_trial",
        "capital_accounting_passed": capital_gate["passed"],
        "kill_switch_parity_passed": False,
        "live_eligible": False,
        "hard_failures": [
            "fewer_than_30_prospective_closed_pairs",
            "deflated_sharpe_not_computable",
            "capital_margin_borrow_policy_unproven",
            "kill_switch_parity_not_proven",
        ],
    }
    accepted = bool(gate4["passed"])
    decision = (
        "accepted_default_off_external_capital_pending_forward"
        if accepted
        else "rejected_numeric_gate4"
    )
    deterministic_generated_at = max(
        str(source_manifest["generated_at"]), str(auxiliary["retrieved_at"])
    )
    return {
        "schema": "fed_h8_bank_size_relative_value_full_stack_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": deterministic_generated_at,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted_alpha": accepted,
        "hypothesis": (
            "The sum of small-minus-large-bank four-release log-growth spreads "
            "in other deposits and C&I loans predicts the next weekly KRE/KBE "
            "relative return."
        ),
        "locked_policy": {
            "rule_version": RULE_VERSION,
            "source": "official Fed H.8 as-released dated HTML vintages",
            "signal": (
                "sum of small-minus-large 4-release log-growth spreads for "
                "Other deposits and Commercial and industrial loans"
            ),
            "positive": "long KRE / short KBE",
            "negative": "long KBE / short KRE",
            "neutral_band": None,
            "entry": "first adjusted regular-session open strictly after publication",
            "exit": "first adjusted regular-session open strictly after next publication",
            "notional_usd_per_leg": NOTIONAL_USD_PER_LEG,
            "max_concurrent_pairs": MAX_CONCURRENT_PAIRS,
            "round_trip_cost_pct_per_leg": ROUND_TRIP_COST_PCT_PER_LEG,
            "round_trip_cost_usd_per_leg": (
                NOTIONAL_USD_PER_LEG * ROUND_TRIP_COST_PCT_PER_LEG
            ),
            "trade_enabled": TRADE_ENABLED,
            "retunes": [],
        },
        "source": {
            "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
            "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
            "canonical_releases": _repo_rel(CANONICAL_RELEASES_PATH),
            "canonical_releases_sha256": _file_sha(CANONICAL_RELEASES_PATH),
            "raw_html_archive": _repo_rel(RAW_HTML_ARCHIVE_PATH),
            "raw_html_archive_sha256": _file_sha(RAW_HTML_ARCHIVE_PATH),
            "coverage": source_manifest["coverage"],
            "semantic_source_identity": source_manifest[
                "semantic_source_identity"
            ],
            "raw_response_manifests": source_manifest[
                "raw_response_manifests"
            ],
            "parser_audit": source_manifest["parser_audit"],
        },
        "market_data": {
            "path": _repo_rel(AUXILIARY_OHLCV_PATH),
            "file_sha256": _file_sha(AUXILIARY_OHLCV_PATH),
            "canonical_rowset_sha256": auxiliary["canonical_rowset_sha256"],
            "price_basis": "split_and_distribution_adjusted_ohlc",
            "query": auxiliary["query"],
            "runtime": auxiliary["runtime"],
            "calendar_identity": calendar_identity,
        },
        "calculation_identity": {
            "helper": {
                "path": "quant/fed_h8_bank_size_relative_value_paper_sleeve.py",
                "sha256": _file_sha(
                    REPO_ROOT
                    / "quant"
                    / "fed_h8_bank_size_relative_value_paper_sleeve.py"
                ),
            },
            "runner": {
                "path": _repo_rel(Path(__file__)),
                "sha256": _file_sha(Path(__file__)),
            },
            "baseline": {
                "path": _repo_rel(BASELINE_PATH),
                "sha256": _file_sha(BASELINE_PATH),
                "experiment_id": baseline_summary["experiment_id"],
            },
        },
        "windows": windows,
        "aggregate": {
            "before": aggregate_before,
            "pair": aggregate_pair,
            "after": aggregate_after,
            "after_minus_before_pnl": round(
                aggregate_after["total_pnl"] - aggregate_before["total_pnl"], 2
            ),
            "pair_pnl_identity": round(pair_pnl_total, 2),
            "baseline_anchor_hard_checks": baseline_aggregate_checks,
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "gate5": gate5,
        "matched_replacement_benchmarks": benchmarks,
        "full_window_buy_hold_diagnostics": buy_hold,
        "concentration": concentration,
        "decisions": enriched_decisions,
        "production_impact": {
            "shared_helper_used": True,
            "daily_default_off_seed_written": True,
            "live_orders_changed": False,
            "backtester_changed": False,
            "trade_enabled": False,
            "capital_accounting": capital_gate["capital_accounting"],
            "live_eligible": False,
        },
    }


def _before_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "fed_h8_bank_size_relative_value_before_v1",
        "experiment_id": EXPERIMENT_ID,
        "baseline": result["calculation_identity"]["baseline"],
        "windows": {
            label: result["windows"][label]["before"] for label in WINDOWS
        },
        "aggregate": result["aggregate"]["before"],
        "note": "accepted cash-feasible Gate1 baseline, raw daily curves rebuilt",
    }


def _after_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "fed_h8_bank_size_relative_value_after_v1",
        "experiment_id": EXPERIMENT_ID,
        "windows": {
            label: {
                "pair": result["windows"][label]["pair"],
                "combined": result["windows"][label]["after"],
                "delta": result["windows"][label]["delta"],
            }
            for label in WINDOWS
        },
        "aggregate": result["aggregate"],
        "capital_accounting": result["gate4"]["capital_accounting_gate"],
    }


def _verdict_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "fed_h8_bank_size_relative_value_full_verdict_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": result["generated_at"],
        "status": result["status"],
        "decision": result["decision"],
        "accepted_alpha": result["accepted_alpha"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "gate5": result["gate5"],
        "production_impact": result["production_impact"],
    }


def _paper_seed(result: Mapping[str, Any]) -> dict[str, Any]:
    latest = max(result["decisions"], key=lambda row: str(row["release_date"]))
    return {
        "schema": "fed_h8_bank_size_relative_value_daily_seed_v1",
        "experiment_id": EXPERIMENT_ID,
        "as_of_date": CANONICAL_END,
        "sleeve_name": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "orders": [],
        "latest_observation": latest,
        "source_manifest_sha256": result["source"]["manifest_sha256"],
        "market_data_file_sha256": result["market_data"]["file_sha256"],
        "one_shot_parity_seed": True,
        "daily_wiring_retained": False,
        "live_orders_changed": False,
        "capital_accounting": "external_overlay_not_cash_conserving",
        "live_eligible": False,
    }


def _write_evaluation_outputs(result: dict[str, Any]) -> None:
    if RESULT_PATH.exists():
        existing = _read_json(RESULT_PATH)
        identity_checks = {
            "source_manifest": (
                existing.get("source", {}).get("manifest_sha256")
                == result["source"]["manifest_sha256"]
            ),
            "market_data": (
                existing.get("market_data", {}).get("file_sha256")
                == result["market_data"]["file_sha256"]
            ),
            "helper": (
                existing.get("calculation_identity", {})
                .get("helper", {})
                .get("sha256")
                == result["calculation_identity"]["helper"]["sha256"]
            ),
            "runner": (
                existing.get("calculation_identity", {})
                .get("runner", {})
                .get("sha256")
                == result["calculation_identity"]["runner"]["sha256"]
            ),
            "baseline": (
                existing.get("calculation_identity", {})
                .get("baseline", {})
                .get("sha256")
                == result["calculation_identity"]["baseline"]["sha256"]
            ),
        }
        if not all(identity_checks.values()):
            raise SourceContractError(
                f"existing evaluation commit marker has mixed identities: {identity_checks}"
            )
        raise SourceContractError(
            "existing evaluation commit marker is identity-valid; refusing to "
            "overwrite the immutable result bundle"
        )
    before = _before_payload(result)
    after = _after_payload(result)
    verdict = _verdict_payload(result)
    seed = _paper_seed(result)
    result["output_bundle"] = {
        "schema": "fed_h8_evaluation_output_bundle_v1",
        "commit_marker": _repo_rel(RESULT_PATH),
        "payloads": {
            "before": {
                "path": _repo_rel(BEFORE_PATH),
                "canonical_payload_sha256": _canonical_sha(before),
            },
            "after": {
                "path": _repo_rel(AFTER_PATH),
                "canonical_payload_sha256": _canonical_sha(after),
            },
            "full_stack_verdict": {
                "path": _repo_rel(VERDICT_PATH),
                "canonical_payload_sha256": _canonical_sha(verdict),
            },
            "daily_default_off_seed": {
                "path": _repo_rel(PAPER_SEED_PATH),
                "canonical_payload_sha256": _canonical_sha(seed),
            },
        },
        "write_semantics": "four payloads atomically written before result commit marker",
    }
    # Result is written last and acts as the evaluation commit marker.
    _atomic_write_json(BEFORE_PATH, before)
    _atomic_write_json(AFTER_PATH, after)
    _atomic_write_json(VERDICT_PATH, verdict)
    _atomic_write_json(PAPER_SEED_PATH, seed)
    _atomic_write_json(RESULT_PATH, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Require and revalidate frozen official bytes and adjusted OHLCV.",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Freeze/revalidate the outcome-blind Fed source bundle only.",
    )
    parser.add_argument(
        "--ohlcv-only",
        action="store_true",
        help="Freeze/revalidate adjusted KRE/KBE/SPY/QQQ OHLCV only.",
    )
    args = parser.parse_args()
    if args.source_only and args.ohlcv_only:
        parser.error("--source-only and --ohlcv-only are mutually exclusive")
    try:
        _assert_locked_policy()
        if args.source_only:
            releases, manifest = materialize_source(offline=args.offline)
            print(
                json.dumps(
                    {
                        "experiment_id": EXPERIMENT_ID,
                        "mode": "source_only",
                        "release_count": len(releases),
                        "source_manifest": _repo_rel(SOURCE_MANIFEST_PATH),
                        "source_manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
                        "coverage": manifest["coverage"],
                    },
                    indent=2,
                )
            )
            return 0
        if args.ohlcv_only:
            payload = materialize_auxiliary_ohlcv(offline=args.offline)
            print(
                json.dumps(
                    {
                        "experiment_id": EXPERIMENT_ID,
                        "mode": "ohlcv_only",
                        "path": _repo_rel(AUXILIARY_OHLCV_PATH),
                        "file_sha256": _file_sha(AUXILIARY_OHLCV_PATH),
                        "canonical_rowset_sha256": payload[
                            "canonical_rowset_sha256"
                        ],
                        "row_counts": payload["row_counts"],
                    },
                    indent=2,
                )
            )
            return 0
        result = _build_evaluation(offline=args.offline)
        _write_evaluation_outputs(result)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": result["status"],
                    "numeric_gate4_passed": result["gate4"][
                        "numeric_alpha_measurement"
                    ]["passed"],
                    "binding_gate4_passed": result["gate4"]["passed"],
                    "hard_failures": result["gate4"]["hard_failures"],
                    "result": _repo_rel(RESULT_PATH),
                },
                indent=2,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": "failed_closed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
