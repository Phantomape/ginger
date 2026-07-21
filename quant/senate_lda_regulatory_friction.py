"""Shared default-off Senate LDA regulatory-friction entry scalar.

The fixed policy is owned by ``exp-20260720-005``.  It consumes official
Senate Lobbying Disclosure Act (LDA) quarterly filings on their as-filed
``dt_posted`` clock, maps only a frozen set of direct client names to core
issuers, and measures the breadth of distinct ``general_issue_code`` values in
completed Monday-through-Sunday issuer weeks.

A ticker-week triggers when breadth is at least three and is strictly above
the median of that ticker's four prior *non-empty* filing weeks.  The response
is a 0.50 opening-notional scalar beginning on the first caller-supplied
trading session strictly after the completed Sunday and lasting ten sessions
inclusive of activation.  Missing, filtered, or malformed source rows do not
create a downweight.  Conflicting rows sharing one ``filing_uuid`` raise,
because silently choosing a filing vintage would violate the publication
clock.

The index, source identity, issuer map, calendar, weekly decisions, and session
provenance are canonical-SHA256 bound.  Historical replay and daily snapshots
both use :class:`SenateLDARegulatoryFrictionResolver`; this module never places
orders and remains default-off unless a separately validated caller applies
the returned scalar.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

try:  # Package imports and quant/ script-style imports are both used here.
    from .entry_universe_ledger import canonical_hash
except ImportError:  # pragma: no cover - exercised by experiment runners.
    from entry_universe_ledger import canonical_hash


SOURCE = "senate_lda_quarterly_filings"
RULE_VERSION = "senate_lda_issue_breadth_regulatory_friction_scalar_v1"
TRADE_ENABLED = False

ENTRY_SCALAR = 0.50
NEUTRAL_SCALAR = 1.00
ACTIVE_SESSIONS = 10
MIN_ISSUE_BREADTH = 3
PRIOR_NONEMPTY_WEEKS = 4

_DEFAULT_EFFECTIVE_FROM = "2023-01-01"
_RTX_EFFECTIVE_FROM = "2023-07-17"

# This map is deliberately direct-name only.  The regular expressions are the
# exact outcome-blind preflight contract; do not broaden them with subsidiary,
# parent, product, fuzzy-name, or token-overlap heuristics.
FROZEN_ISSUER_MAP: dict[str, dict[str, str | None]] = {
    "AAPL": {
        "name_regex": r"^APPLE.*\bINC\b",
        "query_name": "Apple",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "AMZN": {
        "name_regex": r"^AMAZON(?:\.COM)?\b",
        "query_name": "Amazon",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "GOOG": {
        "name_regex": r"^GOOGLE\b",
        "query_name": "Google",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "META": {
        "name_regex": r"^META PLATFORMS\b",
        "query_name": "Meta Platforms",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "MSFT": {
        "name_regex": r"^MICROSOFT\b",
        "query_name": "Microsoft",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "JPM": {
        "name_regex": r"^JPMORGAN CHASE\b",
        "query_name": "JPMorgan Chase",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "GS": {
        "name_regex": r"^GOLDMAN SACHS\b",
        "query_name": "Goldman Sachs",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "MA": {
        "name_regex": r"^MASTERCARD\b",
        "query_name": "Mastercard",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "V": {
        "name_regex": r"^VISA\s*,?\s*INC\b",
        "query_name": "Visa Inc",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "XOM": {
        "name_regex": r"^EXXON\s+MOBIL\b",
        "query_name": "Exxon Mobil",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "CVX": {
        "name_regex": r"^CHEVRON\b",
        "query_name": "Chevron",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "CAT": {
        "name_regex": r"^CATERPILLAR\b",
        "query_name": "Caterpillar",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "DE": {
        "name_regex": r"^(?:JOHN\s+)?DEERE\b",
        "query_name": "Deere",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "UNH": {
        "name_regex": r"^UNITEDHEALTH\b",
        "query_name": "UnitedHealth",
        "effective_from": _DEFAULT_EFFECTIVE_FROM,
        "effective_to": None,
    },
    "RTX": {
        "name_regex": r"^RTX\s+CORPORATION\b",
        "query_name": "RTX Corporation",
        "effective_from": _RTX_EFFECTIVE_FROM,
        "effective_to": None,
    },
}

# Descriptive aliases make the immutable mapping discoverable to experiment
# runners without creating a second source of truth.
DIRECT_ISSUER_MAP = FROZEN_ISSUER_MAP
ISSUER_NAME_REGEX_MAP = FROZEN_ISSUER_MAP
FROZEN_TICKERS = frozenset(FROZEN_ISSUER_MAP)

_EXPECTED_TICKERS = frozenset(
    {
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "JPM",
        "GS",
        "MA",
        "V",
        "XOM",
        "CVX",
        "CAT",
        "DE",
        "UNH",
        "RTX",
    }
)
_QUARTERLY_REPORT_RE = re.compile(
    r"^(?:Q[1-4]|[1-4](?:ST|ND|RD|TH)?\s+QUARTER)\s*(?:-\s*)?REPORT$",
    flags=re.IGNORECASE,
)

_POLICY = {
    "publication_clock": "official_dt_posted_utc",
    "client_mapping": "frozen_direct_name_regex_effective_dated",
    "filing_filter": "non_amendment_q1_q2_q3_q4_report_only",
    "aggregation": "completed_monday_sunday_ticker_week_unique_issue_codes",
    "breadth_floor": MIN_ISSUE_BREADTH,
    "comparison": "strictly_above_median_prior_four_nonempty_ticker_weeks",
    "activation": "first_caller_session_strictly_after_completed_sunday",
    "active_sessions": ACTIVE_SESSIONS,
    "entry_notional_scalar": ENTRY_SCALAR,
    "neutral_scalar": NEUTRAL_SCALAR,
    "missing_or_malformed_policy": "fail_open_neutral",
    "scope": "fresh_core_entry_requested_notional_only",
}


class SenateLDARegulatoryFrictionError(ValueError):
    """Base contract error for the Senate LDA shared policy."""


class SenateLDAFilingConflictError(SenateLDARegulatoryFrictionError):
    """One filing UUID was observed with conflicting semantic payloads."""


class SenateLDAIndexValidationError(SenateLDARegulatoryFrictionError):
    """A hash-bound Senate LDA index is malformed or was mutated."""


def _default_off_flags() -> dict[str, bool]:
    return {
        "trade_enabled": False,
        "can_place_orders": False,
        "alters_live_orders": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_existing_positions": False,
        "alters_addons": False,
        "alters_candidate_ranking": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_costs": False,
    }


def _json_copy(value: Any, *, field: str) -> Any:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise SenateLDARegulatoryFrictionError(
            f"{field} must be deterministic JSON: {exc}"
        ) from exc


def _date10(value: Any, *, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        raise SenateLDARegulatoryFrictionError(f"{field} is required")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except (TypeError, ValueError) as exc:
        raise SenateLDARegulatoryFrictionError(
            f"{field} must be an ISO date, got {value!r}"
        ) from exc


def _try_date10(value: Any) -> str | None:
    try:
        return _date10(value, field="date")
    except SenateLDARegulatoryFrictionError:
        return None


def _utc_timestamp(value: Any, *, field: str) -> tuple[str, str]:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise SenateLDARegulatoryFrictionError(f"{field} is required")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise SenateLDARegulatoryFrictionError(
                f"{field} must be an ISO timestamp, got {value!r}"
            ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SenateLDARegulatoryFrictionError(
            f"{field} must include an explicit timezone"
        )
    # Senate's display timestamp carries the publication-local calendar date.
    # Keep that date for Monday-Sunday grouping before normalising the instant
    # to UTC for deterministic ordering and identity.  Otherwise a Sunday
    # evening US filing becomes Monday in UTC and leaks into the next week.
    posted_local_date = parsed.date().isoformat()
    utc = parsed.astimezone(timezone.utc)
    # Preserve the API timestamp's full sub-second precision; only the timezone
    # representation is canonicalised.
    timestamp = utc.isoformat().replace("+00:00", "Z")
    return timestamp, posted_local_date


def _normalise_name(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _normalise_ticker(value: Any, *, field: str = "ticker") -> str:
    ticker = str(value or "").strip().upper()
    if not ticker or any(character.isspace() for character in ticker):
        raise SenateLDARegulatoryFrictionError(
            f"{field} must be a compact non-empty ticker"
        )
    return ticker


def _normalise_sessions(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise SenateLDARegulatoryFrictionError(
            "trading_sessions must be a collection, not one string"
        )
    try:
        return sorted(
            {_date10(value, field="trading session") for value in values}
        )
    except TypeError as exc:
        raise SenateLDARegulatoryFrictionError(
            "trading_sessions must be an iterable collection"
        ) from exc


def normalise_senate_lda_issuer_map(
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Validate and canonicalise an effective-dated direct-name map.

    Custom maps are supported for focused tests and diagnostics.  The default
    contract additionally asserts the exact frozen fifteen-ticker universe.
    """

    raw_map = FROZEN_ISSUER_MAP if issuer_map is None else issuer_map
    if not isinstance(raw_map, Mapping) or not raw_map:
        raise SenateLDARegulatoryFrictionError(
            "issuer_map must be a non-empty ticker mapping"
        )

    rows: list[dict[str, Any]] = []
    for raw_ticker, raw_spec in raw_map.items():
        ticker = _normalise_ticker(raw_ticker, field="issuer_map ticker")
        if not isinstance(raw_spec, Mapping):
            raise SenateLDARegulatoryFrictionError(
                f"issuer_map[{ticker}] must be a mapping"
            )
        name_regex = str(raw_spec.get("name_regex") or "").strip()
        query_name = str(raw_spec.get("query_name") or "").strip()
        if not name_regex or not query_name:
            raise SenateLDARegulatoryFrictionError(
                f"issuer_map[{ticker}] requires name_regex and query_name"
            )
        try:
            re.compile(name_regex, flags=re.IGNORECASE)
        except re.error as exc:
            raise SenateLDARegulatoryFrictionError(
                f"issuer_map[{ticker}] has invalid name_regex: {exc}"
            ) from exc
        effective_from_raw = str(raw_spec.get("effective_from") or "").strip()
        effective_from = _try_date10(effective_from_raw)
        if effective_from is None or effective_from != effective_from_raw:
            raise SenateLDARegulatoryFrictionError(
                f"issuer_map[{ticker}].effective_from must be canonical YYYY-MM-DD"
            )
        raw_effective_to = raw_spec.get("effective_to")
        if raw_effective_to in (None, ""):
            effective_to = None
        else:
            effective_to_raw = str(raw_effective_to).strip()
            effective_to = _try_date10(effective_to_raw)
            if effective_to is None or effective_to != effective_to_raw:
                raise SenateLDARegulatoryFrictionError(
                    f"issuer_map[{ticker}].effective_to must be canonical YYYY-MM-DD or null"
                )
            if effective_to < effective_from:
                raise SenateLDARegulatoryFrictionError(
                    f"issuer_map[{ticker}] has effective_to before effective_from"
                )
        rows.append(
            {
                "ticker": ticker,
                "name_regex": name_regex,
                "query_name": query_name,
                "effective_from": effective_from,
                "effective_to": effective_to,
            }
        )

    rows.sort(key=lambda row: row["ticker"])
    tickers = [row["ticker"] for row in rows]
    if len(tickers) != len(set(tickers)):
        raise SenateLDARegulatoryFrictionError(
            "issuer_map contains duplicate tickers after normalisation"
        )
    if issuer_map is None and set(tickers) != _EXPECTED_TICKERS:
        raise RuntimeError("frozen Senate LDA issuer map ticker drift")
    return rows


def senate_lda_client_query_names(
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, str]:
    """Return the validated frozen ticker-to-official-client query strings."""

    return {
        row["ticker"]: row["query_name"]
        for row in normalise_senate_lda_issuer_map(issuer_map)
    }


FROZEN_ISSUER_MAP_HASH = canonical_hash(normalise_senate_lda_issuer_map())


def _raw_relevant_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    client = raw.get("client")
    client_map = client if isinstance(client, Mapping) else {}
    activities = raw.get("lobbying_activities")
    if isinstance(activities, list):
        issue_codes = sorted(
            str(activity.get("general_issue_code") or "").strip().upper()
            if isinstance(activity, Mapping)
            else f"<MALFORMED:{type(activity).__name__}>"
            for activity in activities
        )
    else:
        issue_codes = [f"<MALFORMED:{type(activities).__name__}>"]
    return {
        "filing_uuid": str(raw.get("filing_uuid") or "").strip(),
        "dt_posted": str(raw.get("dt_posted") or "").strip(),
        "filing_type": str(raw.get("filing_type") or "").strip() or None,
        "filing_type_display": str(
            raw.get("filing_type_display") or ""
        ).strip(),
        "client": {
            "id": (
                str(client_map.get("id")).strip()
                if client_map.get("id") not in (None, "")
                else None
            ),
            "name": str(client_map.get("name") or "").strip(),
            "effective_date": str(
                client_map.get("effective_date") or ""
            ).strip(),
        },
        "issue_codes": issue_codes,
    }


def _dedupe_raw_filings(
    filings: Iterable[Mapping[str, Any]] | None,
) -> tuple[list[tuple[int, Mapping[str, Any]]], list[dict[str, Any]], int]:
    if filings is None:
        return [], [{"index": None, "reason": "missing_source_rows"}], 0
    if isinstance(filings, (str, bytes, Mapping)):
        return [], [{"index": None, "reason": "source_rows_not_iterable_collection"}], 0
    try:
        raw_rows = list(filings)
    except TypeError:
        return [], [{"index": None, "reason": "source_rows_not_iterable_collection"}], 0

    unique: dict[str, tuple[dict[str, Any], int, Mapping[str, Any]]] = {}
    without_uuid: list[tuple[int, Mapping[str, Any]]] = []
    invalid: list[dict[str, Any]] = []
    duplicate_count = 0
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            invalid.append({"index": index, "reason": "row_not_mapping"})
            continue
        uuid = str(raw.get("filing_uuid") or "").strip()
        if not uuid:
            without_uuid.append((index, raw))
            continue
        payload = _raw_relevant_payload(raw)
        prior = unique.get(uuid)
        if prior is None:
            unique[uuid] = (payload, index, raw)
            continue
        if prior[0] != payload:
            raise SenateLDAFilingConflictError(
                f"conflicting duplicate filing_uuid {uuid!r}: rows {prior[1]} and {index}"
            )
        duplicate_count += 1

    rows = [(index, raw) for _, index, raw in unique.values()]
    rows.extend(without_uuid)
    rows.sort(key=lambda item: item[0])
    return rows, invalid, duplicate_count


def _match_issuer(
    client_name: str,
    posted_date: str,
    map_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    candidates = []
    for row in map_rows:
        if posted_date < row["effective_from"]:
            continue
        if row["effective_to"] is not None and posted_date > row["effective_to"]:
            continue
        if re.search(row["name_regex"], client_name, flags=re.IGNORECASE):
            candidates.append(row)
    if not candidates:
        return None, "unmapped_or_outside_static_effective_interval"
    if len(candidates) > 1:
        return None, "ambiguous_direct_name_mapping"
    return candidates[0], None


def _normalise_with_audit(
    filings: Iterable[Mapping[str, Any]] | None,
    *,
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    map_rows = normalise_senate_lda_issuer_map(issuer_map)
    deduped, invalid, duplicate_count = _dedupe_raw_filings(filings)
    accepted: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []

    for index, raw in deduped:
        uuid = str(raw.get("filing_uuid") or "").strip()
        if not uuid:
            invalid.append({"index": index, "reason": "missing_filing_uuid"})
            continue
        filing_display = str(raw.get("filing_type_display") or "").strip()
        if not _QUARTERLY_REPORT_RE.fullmatch(filing_display):
            filtered.append(
                {
                    "index": index,
                    "filing_uuid": uuid,
                    "reason": "not_non_amendment_quarterly_report",
                }
            )
            continue
        try:
            posted_at, posted_date = _utc_timestamp(
                raw.get("dt_posted"), field="dt_posted"
            )
        except SenateLDARegulatoryFrictionError:
            invalid.append(
                {"index": index, "filing_uuid": uuid, "reason": "invalid_dt_posted"}
            )
            continue

        client = raw.get("client")
        if not isinstance(client, Mapping):
            invalid.append(
                {"index": index, "filing_uuid": uuid, "reason": "invalid_client"}
            )
            continue
        original_client_name = str(client.get("name") or "").strip()
        client_name = _normalise_name(original_client_name)
        raw_client_effective = str(client.get("effective_date") or "").strip()
        try:
            client_effective = date.fromisoformat(raw_client_effective).isoformat()
        except (TypeError, ValueError):
            client_effective = None
        if (
            not client_name
            or client_effective is None
            or client_effective != raw_client_effective
            or client_effective > posted_date
        ):
            invalid.append(
                {
                    "index": index,
                    "filing_uuid": uuid,
                    "reason": "invalid_client_name_or_effective_date",
                }
            )
            continue
        map_row, mapping_error = _match_issuer(client_name, posted_date, map_rows)
        if map_row is None:
            filtered.append(
                {
                    "index": index,
                    "filing_uuid": uuid,
                    "reason": mapping_error,
                    "client_name": original_client_name,
                }
            )
            continue

        activities = raw.get("lobbying_activities")
        if not isinstance(activities, list):
            invalid.append(
                {
                    "index": index,
                    "filing_uuid": uuid,
                    "reason": "invalid_lobbying_activities",
                }
            )
            continue
        issue_codes: set[str] = set()
        malformed_activity = False
        for activity in activities:
            if not isinstance(activity, Mapping):
                malformed_activity = True
                break
            issue_code = str(activity.get("general_issue_code") or "").strip().upper()
            if not issue_code:
                malformed_activity = True
                break
            issue_codes.add(issue_code)
        if malformed_activity:
            invalid.append(
                {
                    "index": index,
                    "filing_uuid": uuid,
                    "reason": "invalid_general_issue_code",
                }
            )
            continue

        posted_day = date.fromisoformat(posted_date)
        week_start = posted_day - timedelta(days=posted_day.weekday())
        week_end = week_start + timedelta(days=6)
        raw_payload = _raw_relevant_payload(raw)
        row: dict[str, Any] = {
            "schema": "senate_lda_normalised_quarterly_filing_v1",
            "source": SOURCE,
            "filing_uuid": uuid,
            "dt_posted": posted_at,
            "posted_date": posted_date,
            "filing_type": str(raw.get("filing_type") or "").strip() or None,
            "filing_type_display": filing_display,
            "ticker": map_row["ticker"],
            "client_name": original_client_name,
            "client_name_normalised": client_name,
            "client_id": (
                str(client.get("id")).strip()
                if client.get("id") not in (None, "")
                else None
            ),
            "client_effective_date": client_effective,
            "mapping_name_regex": map_row["name_regex"],
            "mapping_query_name": map_row["query_name"],
            "mapping_effective_from": map_row["effective_from"],
            "mapping_effective_to": map_row["effective_to"],
            "issue_codes": sorted(issue_codes),
            "issue_code_count": len(issue_codes),
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "payload_hash": canonical_hash(raw_payload),
        }
        row["row_hash"] = canonical_hash(row)
        accepted.append(row)

    accepted.sort(
        key=lambda row: (
            row["dt_posted"],
            row["ticker"],
            row["filing_uuid"],
        )
    )
    invalid.sort(key=lambda row: (-1 if row["index"] is None else row["index"]))
    filtered.sort(key=lambda row: row["index"])
    return {
        "rows": accepted,
        "invalid_rows": invalid,
        "filtered_rows": filtered,
        "duplicate_row_count": duplicate_count,
        "issuer_map": map_rows,
        "issuer_map_hash": canonical_hash(map_rows),
    }


def normalise_senate_lda_filings(
    filings: Iterable[Mapping[str, Any]] | None,
    *,
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return valid official quarterly filings in deterministic PIT form.

    Expected filters and malformed rows are rejected without creating a
    scalar.  Conflicting UUID duplicates raise
    :class:`SenateLDAFilingConflictError`.
    """

    return _normalise_with_audit(filings, issuer_map=issuer_map)["rows"]


def load_senate_lda_filings(path: Path | str) -> list[dict[str, Any]]:
    """Load cached official API rows from JSON/JSONL files or a directory.

    Missing or malformed cache files fail open to an empty row set.  Supported
    JSON wrappers use ``results``, ``filings``, or ``rows`` arrays, matching
    common raw-page and frozen-bundle layouts.
    """

    source_path = Path(path)
    if not source_path.exists():
        return []
    paths = (
        sorted(
            item
            for item in source_path.rglob("*")
            if item.is_file() and item.suffix.lower() in {".json", ".jsonl"}
        )
        if source_path.is_dir()
        else [source_path]
    )
    output: list[dict[str, Any]] = []
    try:
        for item in paths:
            if item.suffix.lower() == ".jsonl":
                values = [
                    json.loads(line)
                    for line in item.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            else:
                payload = json.loads(item.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    values = payload
                elif isinstance(payload, Mapping):
                    values = next(
                        (
                            payload[key]
                            for key in ("results", "filings", "rows")
                            if isinstance(payload.get(key), list)
                        ),
                        [],
                    )
                else:
                    values = []
            output.extend(dict(row) for row in values if isinstance(row, Mapping))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return []
    return output


load_cached_senate_lda_filings = load_senate_lda_filings


def _completed_week_rows(
    normalised_rows: list[dict[str, Any]],
    *,
    as_of: str | None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in normalised_rows:
        if as_of is not None and row["week_end"] >= as_of:
            continue
        grouped[(row["ticker"], row["week_end"])].append(row)

    weeks: list[dict[str, Any]] = []
    for (ticker, week_end), rows in sorted(grouped.items()):
        issue_codes = sorted(
            {
                code
                for row in rows
                for code in row.get("issue_codes", [])
                if str(code).strip()
            }
        )
        if not issue_codes:
            # Prior comparisons explicitly use non-empty ticker filing weeks.
            continue
        clients = sorted(
            {
                (
                    row["client_name"],
                    row["client_id"],
                    row["client_effective_date"],
                )
                for row in rows
            },
            key=lambda value: tuple("" if item is None else str(item) for item in value),
        )
        week: dict[str, Any] = {
            "schema": "senate_lda_issuer_issue_breadth_week_v1",
            "source": SOURCE,
            "rule_version": RULE_VERSION,
            "ticker": ticker,
            "week_start": min(row["week_start"] for row in rows),
            "week_end": week_end,
            "issue_codes": issue_codes,
            "issue_breadth": len(issue_codes),
            "filing_uuids": sorted(row["filing_uuid"] for row in rows),
            "filing_count": len(rows),
            "dt_posted_min": min(row["dt_posted"] for row in rows),
            "dt_posted_max": max(row["dt_posted"] for row in rows),
            "client_provenance": [
                {
                    "client_name": name,
                    "client_id": client_id,
                    "client_effective_date": effective_date,
                }
                for name, client_id, effective_date in clients
            ],
            "filing_row_hashes": sorted(row["row_hash"] for row in rows),
        }
        week["week_source_hash"] = canonical_hash(
            {
                "ticker": ticker,
                "week_end": week_end,
                "filing_row_hashes": week["filing_row_hashes"],
            }
        )
        weeks.append(week)

    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for week in weeks:
        by_ticker[week["ticker"]].append(week)
    evaluated: list[dict[str, Any]] = []
    for ticker in sorted(by_ticker):
        prior_nonempty: list[dict[str, Any]] = []
        for week in sorted(by_ticker[ticker], key=lambda row: row["week_end"]):
            eligible_prior = [
                row
                for row in prior_nonempty
                if row["week_end"] < week["week_start"]
            ][-PRIOR_NONEMPTY_WEEKS:]
            prior_breadths = [row["issue_breadth"] for row in eligible_prior]
            prior_week_ends = [row["week_end"] for row in eligible_prior]
            has_history = len(eligible_prior) == PRIOR_NONEMPTY_WEEKS
            prior_median = float(median(prior_breadths)) if has_history else None
            triggered = (
                has_history
                and week["issue_breadth"] >= MIN_ISSUE_BREADTH
                and week["issue_breadth"] > prior_median
            )
            if not has_history:
                reason = "insufficient_prior_nonempty_weeks"
            elif week["issue_breadth"] < MIN_ISSUE_BREADTH:
                reason = "below_minimum_issue_breadth"
            elif week["issue_breadth"] <= prior_median:
                reason = "not_strictly_above_prior_four_median"
            else:
                reason = "issue_breadth_acceleration_trigger"
            evaluated_week = {
                **week,
                "prior_four_nonempty_week_ends": prior_week_ends,
                "prior_four_nonempty_issue_breadths": prior_breadths,
                "prior_four_nonempty_median": prior_median,
                "has_required_prior_history": has_history,
                "triggered": triggered,
                "trigger_reason": reason,
                "scalar": ENTRY_SCALAR if triggered else NEUTRAL_SCALAR,
            }
            evaluated_week["decision_hash"] = canonical_hash(evaluated_week)
            evaluated.append(evaluated_week)
            prior_nonempty.append(week)
    evaluated.sort(key=lambda row: (row["week_end"], row["ticker"]))
    return evaluated


def evaluate_senate_lda_regulatory_friction_weeks(
    filings: Iterable[Mapping[str, Any]] | None,
    *,
    as_of: Any | None = None,
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate completed issuer weeks without applying an execution calendar.

    When supplied, ``as_of`` represents the beginning of that calendar day;
    only weeks with a Sunday strictly earlier than it are complete.
    """

    audit = _normalise_with_audit(filings, issuer_map=issuer_map)
    as_of_text = _date10(as_of, field="as_of") if as_of is not None else None
    weekly_rows = _completed_week_rows(audit["rows"], as_of=as_of_text)
    trigger_rows = [row for row in weekly_rows if row["triggered"]]
    result: dict[str, Any] = {
        "schema": "senate_lda_regulatory_friction_weekly_evaluation_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "as_of": as_of_text,
        "policy": deepcopy(_POLICY),
        "issuer_map": deepcopy(audit["issuer_map"]),
        "issuer_map_hash": audit["issuer_map_hash"],
        "normalised_filings": deepcopy(audit["rows"]),
        "normalised_filing_count": len(audit["rows"]),
        "normalised_filings_hash": canonical_hash(audit["rows"]),
        "invalid_rows": deepcopy(audit["invalid_rows"]),
        "invalid_row_count": len(audit["invalid_rows"]),
        "filtered_rows": deepcopy(audit["filtered_rows"]),
        "filtered_row_count": len(audit["filtered_rows"]),
        "duplicate_row_count": audit["duplicate_row_count"],
        "weekly_rows": weekly_rows,
        "weekly_row_count": len(weekly_rows),
        "trigger_rows": trigger_rows,
        "trigger_count": len(trigger_rows),
        **_default_off_flags(),
    }
    result["evaluation_hash"] = canonical_hash(result)
    return result


def _source_identity_copy(
    source_identity: Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    if source_identity is None:
        return {"identity": "derived_from_normalised_official_api_rows"}
    if isinstance(source_identity, str):
        text = source_identity.strip()
        if not text:
            raise SenateLDARegulatoryFrictionError("source_identity cannot be blank")
        return {"identity": text}
    if not isinstance(source_identity, Mapping):
        raise SenateLDARegulatoryFrictionError(
            "source_identity must be a mapping or non-empty string"
        )
    copied = _json_copy(dict(source_identity), field="source_identity")
    if not copied:
        raise SenateLDARegulatoryFrictionError("source_identity cannot be empty")
    return copied


def build_senate_lda_regulatory_friction_index(
    filings: Iterable[Mapping[str, Any]] | None,
    trading_sessions: Iterable[Any] | None,
    *,
    source_identity: Mapping[str, Any] | str | None = None,
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the canonical session-to-ticker scalar and provenance index."""

    sessions = _normalise_sessions(trading_sessions)
    weekly = evaluate_senate_lda_regulatory_friction_weeks(
        filings,
        issuer_map=issuer_map,
    )
    identity = _source_identity_copy(source_identity)
    identity_hash = canonical_hash(identity)
    source_hash = canonical_hash(
        {
            "source": SOURCE,
            "source_identity": identity,
            "normalised_filings_hash": weekly["normalised_filings_hash"],
            "issuer_map_hash": weekly["issuer_map_hash"],
        }
    )

    session_scalars: dict[str, dict[str, float]] = {
        session: {} for session in sessions
    }
    session_provenance_lists: dict[
        str, dict[str, list[dict[str, Any]]]
    ] = {session: defaultdict(list) for session in sessions}
    activated_triggers: list[dict[str, Any]] = []
    for trigger in weekly["trigger_rows"]:
        first = bisect_right(sessions, trigger["week_end"])
        active = sessions[first : first + ACTIVE_SESSIONS]
        if not active:
            continue
        compact_trigger = {
            "ticker": trigger["ticker"],
            "week_start": trigger["week_start"],
            "week_end": trigger["week_end"],
            "issue_codes": deepcopy(trigger["issue_codes"]),
            "issue_breadth": trigger["issue_breadth"],
            "prior_four_nonempty_week_ends": deepcopy(
                trigger["prior_four_nonempty_week_ends"]
            ),
            "prior_four_nonempty_issue_breadths": deepcopy(
                trigger["prior_four_nonempty_issue_breadths"]
            ),
            "prior_four_nonempty_median": trigger[
                "prior_four_nonempty_median"
            ],
            "filing_uuids": deepcopy(trigger["filing_uuids"]),
            "dt_posted_min": trigger["dt_posted_min"],
            "dt_posted_max": trigger["dt_posted_max"],
            "client_provenance": deepcopy(trigger["client_provenance"]),
            "week_source_hash": trigger["week_source_hash"],
            "decision_hash": trigger["decision_hash"],
            "activation_session": active[0],
            "active_through_session": active[-1],
            "active_sessions": active,
            "scalar": ENTRY_SCALAR,
        }
        compact_trigger["activation_hash"] = canonical_hash(compact_trigger)
        activated_triggers.append(compact_trigger)
        for session in active:
            ticker = trigger["ticker"]
            session_scalars[session][ticker] = ENTRY_SCALAR
            session_provenance_lists[session][ticker].append(compact_trigger)

    session_provenance: dict[str, dict[str, dict[str, Any]]] = {}
    for session in sessions:
        by_ticker: dict[str, dict[str, Any]] = {}
        for ticker, triggers in sorted(session_provenance_lists[session].items()):
            provenance: dict[str, Any] = {
                "ticker": ticker,
                "session": session,
                "scalar": ENTRY_SCALAR,
                "active_trigger_count": len(triggers),
                "trigger_rows": deepcopy(triggers),
                "trigger_hashes": sorted(row["activation_hash"] for row in triggers),
            }
            provenance["provenance_hash"] = canonical_hash(provenance)
            by_ticker[ticker] = provenance
        session_provenance[session] = by_ticker

    activated_triggers.sort(
        key=lambda row: (row["activation_session"], row["ticker"], row["week_end"])
    )
    index: dict[str, Any] = {
        "schema": "senate_lda_regulatory_friction_index_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "policy": deepcopy(_POLICY),
        "source_identity": identity,
        "source_identity_hash": identity_hash,
        "source_hash": source_hash,
        "issuer_map": deepcopy(weekly["issuer_map"]),
        "issuer_map_hash": weekly["issuer_map_hash"],
        "normalised_filings": deepcopy(weekly["normalised_filings"]),
        "normalised_filing_count": weekly["normalised_filing_count"],
        "normalised_filings_hash": weekly["normalised_filings_hash"],
        "invalid_rows": deepcopy(weekly["invalid_rows"]),
        "invalid_row_count": weekly["invalid_row_count"],
        "filtered_rows": deepcopy(weekly["filtered_rows"]),
        "filtered_row_count": weekly["filtered_row_count"],
        "duplicate_row_count": weekly["duplicate_row_count"],
        "weekly_rows": deepcopy(weekly["weekly_rows"]),
        "weekly_rows_hash": canonical_hash(weekly["weekly_rows"]),
        "trigger_rows": deepcopy(weekly["trigger_rows"]),
        "trigger_rows_hash": canonical_hash(weekly["trigger_rows"]),
        "activated_triggers": activated_triggers,
        "activated_triggers_hash": canonical_hash(activated_triggers),
        "trading_sessions": sessions,
        "trading_session_count": len(sessions),
        "trading_sessions_hash": canonical_hash(sessions),
        "session_scalars": session_scalars,
        "session_provenance": session_provenance,
        "default_scalar": NEUTRAL_SCALAR,
        **_default_off_flags(),
    }
    index["index_hash"] = canonical_hash(index)
    return index


build_senate_lda_issue_breadth_index = build_senate_lda_regulatory_friction_index


def validate_senate_lda_regulatory_friction_index(
    index: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate hashes and scalar/provenance invariants, returning a copy."""

    if not isinstance(index, Mapping):
        raise SenateLDAIndexValidationError("index must be a mapping")
    try:
        row = _json_copy(dict(index), field="index")
    except SenateLDARegulatoryFrictionError as exc:
        raise SenateLDAIndexValidationError(str(exc)) from exc
    if row.get("schema") != "senate_lda_regulatory_friction_index_v1":
        raise SenateLDAIndexValidationError("unexpected index schema")
    if row.get("source") != SOURCE or row.get("rule_version") != RULE_VERSION:
        raise SenateLDAIndexValidationError("source or rule-version mismatch")
    supplied_hash = row.get("index_hash")
    semantic = {key: value for key, value in row.items() if key != "index_hash"}
    if supplied_hash != canonical_hash(semantic):
        raise SenateLDAIndexValidationError("index_hash mismatch")
    sessions = row.get("trading_sessions")
    if not isinstance(sessions, list) or sessions != _normalise_sessions(sessions):
        raise SenateLDAIndexValidationError(
            "trading_sessions must be canonical, sorted, and unique"
        )
    if row.get("trading_sessions_hash") != canonical_hash(sessions):
        raise SenateLDAIndexValidationError("trading_sessions_hash mismatch")
    if row.get("issuer_map_hash") != canonical_hash(row.get("issuer_map")):
        raise SenateLDAIndexValidationError("issuer_map_hash mismatch")
    if row.get("normalised_filings_hash") != canonical_hash(
        row.get("normalised_filings")
    ):
        raise SenateLDAIndexValidationError("normalised_filings_hash mismatch")
    if row.get("weekly_rows_hash") != canonical_hash(row.get("weekly_rows")):
        raise SenateLDAIndexValidationError("weekly_rows_hash mismatch")
    if row.get("trigger_rows_hash") != canonical_hash(row.get("trigger_rows")):
        raise SenateLDAIndexValidationError("trigger_rows_hash mismatch")
    if row.get("activated_triggers_hash") != canonical_hash(
        row.get("activated_triggers")
    ):
        raise SenateLDAIndexValidationError("activated_triggers_hash mismatch")
    if row.get("source_identity_hash") != canonical_hash(
        row.get("source_identity")
    ):
        raise SenateLDAIndexValidationError("source_identity_hash mismatch")
    expected_source_hash = canonical_hash(
        {
            "source": SOURCE,
            "source_identity": row.get("source_identity"),
            "normalised_filings_hash": row.get("normalised_filings_hash"),
            "issuer_map_hash": row.get("issuer_map_hash"),
        }
    )
    if row.get("source_hash") != expected_source_hash:
        raise SenateLDAIndexValidationError("source_hash mismatch")

    scalars = row.get("session_scalars")
    provenance = row.get("session_provenance")
    if not isinstance(scalars, dict) or set(scalars) != set(sessions):
        raise SenateLDAIndexValidationError("session_scalars calendar mismatch")
    if not isinstance(provenance, dict) or set(provenance) != set(sessions):
        raise SenateLDAIndexValidationError("session_provenance calendar mismatch")
    for session in sessions:
        session_scalars = scalars[session]
        session_provenance = provenance[session]
        if not isinstance(session_scalars, dict) or not isinstance(
            session_provenance, dict
        ):
            raise SenateLDAIndexValidationError("session values must be mappings")
        if set(session_scalars) != set(session_provenance):
            raise SenateLDAIndexValidationError(
                f"scalar/provenance ticker mismatch for {session}"
            )
        for ticker, scalar in session_scalars.items():
            if ticker not in FROZEN_TICKERS and ticker not in {
                mapping["ticker"] for mapping in row["issuer_map"]
            }:
                raise SenateLDAIndexValidationError(
                    f"unknown scalar ticker {ticker!r}"
                )
            if type(scalar) not in {int, float} or float(scalar) != ENTRY_SCALAR:
                raise SenateLDAIndexValidationError(
                    f"non-policy scalar for {session}/{ticker}"
                )
            details = session_provenance[ticker]
            details_semantic = {
                key: value
                for key, value in details.items()
                if key != "provenance_hash"
            }
            if details.get("provenance_hash") != canonical_hash(details_semantic):
                raise SenateLDAIndexValidationError(
                    f"provenance_hash mismatch for {session}/{ticker}"
                )
    return row


def _ticker_evaluation(
    index: Mapping[str, Any],
    *,
    session: str,
    ticker: str,
) -> dict[str, Any]:
    session_known = session in index["session_scalars"]
    ticker_known = ticker in {row["ticker"] for row in index["issuer_map"]}
    details = (
        index["session_provenance"].get(session, {}).get(ticker)
        if session_known
        else None
    )
    if details is not None:
        scalar = ENTRY_SCALAR
        status = "active_regulatory_friction_downweight"
        reason = "active_issue_breadth_acceleration_window"
        trigger_rows = deepcopy(details["trigger_rows"])
    elif not session_known:
        scalar = NEUTRAL_SCALAR
        status = "fail_open_session_uncovered"
        reason = "session_not_in_hash_bound_calendar"
        trigger_rows = []
    elif not ticker_known:
        scalar = NEUTRAL_SCALAR
        status = "fail_open_unmapped_ticker"
        reason = "ticker_not_in_frozen_direct_name_map"
        trigger_rows = []
    elif not index["normalised_filings"]:
        scalar = NEUTRAL_SCALAR
        status = "fail_open_no_valid_source_rows"
        reason = "missing_or_malformed_source_produced_no_valid_rows"
        trigger_rows = []
    else:
        scalar = NEUTRAL_SCALAR
        status = "inactive_no_trigger"
        reason = "no_active_issue_breadth_acceleration_window"
        trigger_rows = []
    provenance: dict[str, Any] = {
        "source": SOURCE,
        "source_hash": index["source_hash"],
        "source_identity_hash": index["source_identity_hash"],
        "index_hash": index["index_hash"],
        "issuer_map_hash": index["issuer_map_hash"],
        "trading_sessions_hash": index["trading_sessions_hash"],
        "ticker": ticker,
        "session": session,
        "status": status,
        "scalar": scalar,
        "trigger_rows": trigger_rows,
        "invalid_row_count": index["invalid_row_count"],
        "filtered_row_count": index["filtered_row_count"],
    }
    provenance["provenance_hash"] = canonical_hash(provenance)
    result: dict[str, Any] = {
        "schema": "senate_lda_regulatory_friction_scalar_decision_v1",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "as_of": session,
        "session": session,
        "ticker": ticker,
        "status": status,
        "reason": reason,
        "scalar": scalar,
        "notional_scalar": scalar,
        "active": scalar == ENTRY_SCALAR,
        "trigger_rows": trigger_rows,
        "source_hash": index["source_hash"],
        "index_hash": index["index_hash"],
        "provenance": provenance,
        **_default_off_flags(),
    }
    result["decision_hash"] = canonical_hash(result)
    return result


class SenateLDARegulatoryFrictionResolver:
    """Hash-bound replay/daily resolver for the fixed entry scalar."""

    def __init__(
        self,
        filings_or_index: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None,
        trading_sessions: Iterable[Any] | None = None,
        source_identity: Mapping[str, Any] | str | None = None,
        *,
        issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        if (
            isinstance(filings_or_index, Mapping)
            and filings_or_index.get("schema")
            == "senate_lda_regulatory_friction_index_v1"
            and trading_sessions is None
        ):
            index = validate_senate_lda_regulatory_friction_index(
                filings_or_index
            )
        else:
            index = build_senate_lda_regulatory_friction_index(
                filings_or_index,  # type: ignore[arg-type]
                trading_sessions,
                source_identity=source_identity,
                issuer_map=issuer_map,
            )
            index = validate_senate_lda_regulatory_friction_index(index)
        self._index = index
        self._mapped_tickers = frozenset(
            row["ticker"] for row in self._index["issuer_map"]
        )

    @classmethod
    def from_index(
        cls, index: Mapping[str, Any]
    ) -> "SenateLDARegulatoryFrictionResolver":
        return cls(index)

    @property
    def data_tickers(self) -> frozenset[str]:
        return self._mapped_tickers

    @property
    def index(self) -> dict[str, Any]:
        return deepcopy(self._index)

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "schema": "senate_lda_regulatory_friction_resolver_metadata_v1",
            "source": SOURCE,
            "rule_version": RULE_VERSION,
            "source_identity": deepcopy(self._index["source_identity"]),
            "source_identity_hash": self._index["source_identity_hash"],
            "source_hash": self._index["source_hash"],
            "index_hash": self._index["index_hash"],
            "issuer_map_hash": self._index["issuer_map_hash"],
            "trading_sessions_hash": self._index["trading_sessions_hash"],
            "normalised_filing_count": self._index[
                "normalised_filing_count"
            ],
            "invalid_row_count": self._index["invalid_row_count"],
            "filtered_row_count": self._index["filtered_row_count"],
            "trigger_count": len(self._index["trigger_rows"]),
            "activated_trigger_count": len(self._index["activated_triggers"]),
            "policy": deepcopy(_POLICY),
            **_default_off_flags(),
        }

    def evaluate(self, as_of: Any, ticker: str) -> dict[str, Any]:
        session = _date10(as_of, field="as_of")
        symbol = _normalise_ticker(ticker)
        return _ticker_evaluation(
            self._index,
            session=session,
            ticker=symbol,
        )

    def resolve(
        self, as_of: Any, ticker: str | None = None
    ) -> dict[str, Any]:
        session = _date10(as_of, field="as_of")
        if ticker is not None:
            return self.evaluate(session, ticker)
        known = session in self._index["session_scalars"]
        scalars = (
            deepcopy(self._index["session_scalars"][session]) if known else {}
        )
        provenance = (
            deepcopy(self._index["session_provenance"][session]) if known else {}
        )
        result: dict[str, Any] = {
            "schema": "senate_lda_regulatory_friction_session_resolution_v1",
            "source": SOURCE,
            "rule_version": RULE_VERSION,
            "as_of": session,
            "session": session,
            "status": "resolved" if known else "fail_open_session_uncovered",
            "reason": (
                "hash_bound_session_scalars_resolved"
                if known
                else "session_not_in_hash_bound_calendar"
            ),
            "default_scalar": NEUTRAL_SCALAR,
            "scalars": scalars,
            "ticker_scalars": scalars,
            "active_tickers": sorted(scalars),
            "provenance": provenance,
            "source_hash": self._index["source_hash"],
            "index_hash": self._index["index_hash"],
            **_default_off_flags(),
        }
        result["resolution_hash"] = canonical_hash(result)
        return result

    def __call__(self, as_of: Any, ticker: str) -> float:
        return float(self.evaluate(as_of, ticker)["scalar"])


def evaluate_senate_lda_regulatory_friction(
    index_or_resolver: Mapping[str, Any] | SenateLDARegulatoryFrictionResolver,
    as_of: Any,
    ticker: str,
) -> dict[str, Any]:
    """Standalone replay API returning one ticker/session scalar decision."""

    resolver = (
        index_or_resolver
        if isinstance(index_or_resolver, SenateLDARegulatoryFrictionResolver)
        else SenateLDARegulatoryFrictionResolver.from_index(index_or_resolver)
    )
    return resolver.evaluate(as_of, ticker)


def resolve_senate_lda_regulatory_friction(
    index_or_resolver: Mapping[str, Any] | SenateLDARegulatoryFrictionResolver,
    as_of: Any,
    ticker: str | None = None,
) -> dict[str, Any]:
    """Standalone session resolution API used by replay and daily callers."""

    resolver = (
        index_or_resolver
        if isinstance(index_or_resolver, SenateLDARegulatoryFrictionResolver)
        else SenateLDARegulatoryFrictionResolver.from_index(index_or_resolver)
    )
    return resolver.resolve(as_of, ticker)


resolve_senate_lda_entry_scalar = evaluate_senate_lda_regulatory_friction


def build_daily_snapshot(
    filings: Iterable[Mapping[str, Any]] | None,
    as_of: Any,
    trading_sessions: Iterable[Any] | None,
    candidate_tickers: Iterable[str] | None = None,
    *,
    source_identity: Mapping[str, Any] | str | None = None,
    issuer_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a default-off snapshot, constructing one hash-bound resolver."""

    resolver = SenateLDARegulatoryFrictionResolver(
        filings,
        trading_sessions,
        source_identity,
        issuer_map=issuer_map,
    )
    return build_daily_snapshot_from_resolver(
        resolver,
        as_of,
        candidate_tickers,
    )


def build_daily_snapshot_from_resolver(
    resolver: SenateLDARegulatoryFrictionResolver,
    as_of: Any,
    candidate_tickers: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build one daily snapshot without rebuilding a precomputed index.

    Historical all-session parity should construct the resolver once and call
    this function for each session.  The decision and snapshot fields are
    byte-identical to :func:`build_daily_snapshot` for the same resolver
    inputs.
    """

    if not isinstance(resolver, SenateLDARegulatoryFrictionResolver):
        raise SenateLDARegulatoryFrictionError(
            "resolver must be a SenateLDARegulatoryFrictionResolver"
        )
    as_of_text = _date10(as_of, field="as_of")
    session_resolution = resolver.resolve(as_of_text)
    if candidate_tickers is None:
        candidates = sorted(resolver.data_tickers)
    elif isinstance(candidate_tickers, (str, bytes)):
        raise SenateLDARegulatoryFrictionError(
            "candidate_tickers must be a collection, not one string"
        )
    else:
        candidates = sorted(
            {_normalise_ticker(ticker) for ticker in candidate_tickers}
        )
    candidate_rows = [resolver.evaluate(as_of_text, ticker) for ticker in candidates]
    ticker_scalars = {
        row["ticker"]: row["scalar"] for row in candidate_rows
    }
    active_tickers = sorted(
        ticker for ticker, scalar in ticker_scalars.items() if scalar == ENTRY_SCALAR
    )
    snapshot: dict[str, Any] = {
        "schema": "senate_lda_regulatory_friction_daily_snapshot_v1",
        "record_id": f"senate_lda_regulatory_friction:{as_of_text}",
        "source": SOURCE,
        "rule_version": RULE_VERSION,
        "as_of": as_of_text,
        "session": as_of_text,
        "status": session_resolution["status"],
        "decision": "observe_entry_notional_scalars_default_off",
        "policy": deepcopy(_POLICY),
        "source_identity": deepcopy(resolver.metadata["source_identity"]),
        "source_identity_hash": resolver.metadata["source_identity_hash"],
        "source_hash": resolver.metadata["source_hash"],
        "index_hash": resolver.metadata["index_hash"],
        "issuer_map_hash": resolver.metadata["issuer_map_hash"],
        "trading_sessions_hash": resolver.metadata["trading_sessions_hash"],
        "default_scalar": NEUTRAL_SCALAR,
        "candidate_tickers": candidates,
        "candidate_count": len(candidates),
        "ticker_scalars": ticker_scalars,
        "active_tickers": active_tickers,
        "active_ticker_count": len(active_tickers),
        "candidates": candidate_rows,
        "session_resolution_hash": session_resolution["resolution_hash"],
        "order_intents": [],
        "orders": [],
        **_default_off_flags(),
    }
    snapshot["snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


build_daily_senate_lda_regulatory_friction_snapshot = build_daily_snapshot
build_daily_senate_lda_regulatory_friction_snapshot_from_resolver = (
    build_daily_snapshot_from_resolver
)


def save_daily_snapshot(snapshot: Mapping[str, Any], path: Path | str) -> None:
    """Persist a validated deterministic daily snapshot as canonical JSON."""

    if not isinstance(snapshot, Mapping):
        raise SenateLDARegulatoryFrictionError("snapshot must be a mapping")
    row = _json_copy(dict(snapshot), field="snapshot")
    supplied = row.get("snapshot_hash")
    semantic = {key: value for key, value in row.items() if key != "snapshot_hash"}
    if supplied != canonical_hash(semantic):
        raise SenateLDARegulatoryFrictionError("snapshot_hash mismatch")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )


save_senate_lda_regulatory_friction_daily_snapshot = save_daily_snapshot


__all__ = [
    "ACTIVE_SESSIONS",
    "DIRECT_ISSUER_MAP",
    "ENTRY_SCALAR",
    "FROZEN_ISSUER_MAP",
    "FROZEN_ISSUER_MAP_HASH",
    "FROZEN_TICKERS",
    "ISSUER_NAME_REGEX_MAP",
    "MIN_ISSUE_BREADTH",
    "NEUTRAL_SCALAR",
    "PRIOR_NONEMPTY_WEEKS",
    "RULE_VERSION",
    "SOURCE",
    "TRADE_ENABLED",
    "SenateLDAFilingConflictError",
    "SenateLDAIndexValidationError",
    "SenateLDARegulatoryFrictionError",
    "SenateLDARegulatoryFrictionResolver",
    "build_daily_senate_lda_regulatory_friction_snapshot",
    "build_daily_senate_lda_regulatory_friction_snapshot_from_resolver",
    "build_daily_snapshot",
    "build_daily_snapshot_from_resolver",
    "build_senate_lda_issue_breadth_index",
    "build_senate_lda_regulatory_friction_index",
    "evaluate_senate_lda_regulatory_friction",
    "evaluate_senate_lda_regulatory_friction_weeks",
    "load_cached_senate_lda_filings",
    "load_senate_lda_filings",
    "normalise_senate_lda_filings",
    "normalise_senate_lda_issuer_map",
    "resolve_senate_lda_entry_scalar",
    "resolve_senate_lda_regulatory_friction",
    "save_daily_snapshot",
    "save_senate_lda_regulatory_friction_daily_snapshot",
    "senate_lda_client_query_names",
    "validate_senate_lda_regulatory_friction_index",
]
