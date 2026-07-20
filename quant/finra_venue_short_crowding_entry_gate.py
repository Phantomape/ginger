"""Shared default-off FINRA venue/short-crowding entry-admission gate.

The rule is intentionally narrow and fixed by ``exp-20260720-003``.  On each
signal session it uses only source releases dated strictly before that session,
joins the latest FINRA weekly ATS and non-ATS rows to the latest global FINRA
biweekly short-interest release, and excludes a fresh core entry on the next
session when all three crowding conditions hold.  Missing or stale source data
fails open to the caller's base universe.
"""

from __future__ import annotations

import json
import math
import csv
from bisect import bisect_left, bisect_right
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping

try:  # Package import and quant/ script-style import are both supported.
    from .entry_universe_ledger import canonical_hash, membership_hash
except ImportError:  # pragma: no cover
    from entry_universe_ledger import canonical_hash, membership_hash


SOURCE = "finra_venue_short_interest"
RULE_VERSION = "finra_ats_otc_x_short_interest_crowding_entry_exclusion_v1"
TRADE_ENABLED = False
MAX_VENUE_AGE_DAYS = 14
MAX_SHORT_INTEREST_AGE_DAYS = 21

# Exact outcome-blind preflight denylist.  Do not replace this with name,
# suffix, exchange, or asset-type heuristics.
NON_COMMON_STOCK_TICKERS = frozenset(
    {"GLD", "IAU", "IWM", "MUU", "QQQ", "SLV", "SNXX", "SPY", "TQQQ"}
)

_POLICY = {
    "source_cutoff": "publication_date_strictly_before_signal_date",
    "venue_join": "exact_ticker_week_start_published_date_tier",
    "short_interest_join": "latest_global_release_then_exact_ticker_presence",
    "max_venue_age_calendar_days": MAX_VENUE_AGE_DAYS,
    "max_short_interest_age_calendar_days": MAX_SHORT_INTEREST_AGE_DAYS,
    "venue_share_gate": "ats_share_over_ats_plus_otc_strictly_above_joined_median",
    "short_interest_change_gate": "strictly_positive",
    "days_to_cover_gate": "at_or_above_joined_median",
    "entry_response": "exclude_fresh_core_entry_on_strict_next_session",
    "missing_or_stale_policy": "fail_open",
    "non_common_stock_tickers": sorted(NON_COMMON_STOCK_TICKERS),
}

_VENUE_SOURCES = {
    "ats": "finra_otc_transparency_weekly_ats",
    "otc": "finra_otc_transparency_weekly_nonats",
}
_VENUE_PUBLICATION_METHOD = "finra_weekly_otc_transparency_publication_date"
_SHORT_PUBLICATION_METHOD = "finra_7th_business_day_rule"


class FinraVenueShortCrowdingGateError(ValueError):
    """The joined source or hash-bound resolver contract is invalid."""


def _date10(value: Any, *, field: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError) as exc:
        raise FinraVenueShortCrowdingGateError(
            f"{field} must be an ISO date, got {value!r}"
        ) from exc


def _try_date(value: Any) -> str | None:
    try:
        return _date10(value, field="source date")
    except FinraVenueShortCrowdingGateError:
        return None


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _tickers(values: Iterable[Any]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise FinraVenueShortCrowdingGateError("tickers must be an iterable")
    return sorted({str(value).strip().upper() for value in values if str(value).strip()})


def _sessions(values: Iterable[Any]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise FinraVenueShortCrowdingGateError("trading_sessions must be an iterable")
    return sorted({_date10(value, field="trading session") for value in values})


def _age(later: str, earlier: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def _available_date(
    raw: Mapping[str, Any], *, publication_field: str
) -> tuple[str | None, str | None]:
    """Return parseable publication and conservative usable dates.

    A malformed explicit usable date does not erase the raw publication clock:
    callers use that clock to ensure an unusable newest batch fails open rather
    than silently falling back to an older release.
    """
    published = _try_date(raw.get(publication_field))
    if published is None:
        return None, None
    raw_usable = raw.get("usable_trade_date")
    if raw_usable in (None, ""):
        return published, published
    usable = _try_date(raw_usable)
    return published, (max(published, usable) if usable else None)


def _raw_release_dates(
    rows: Iterable[Mapping[str, Any]], *, publication_field: str
) -> list[str]:
    """Extract release clocks before row validation or cross-source joining."""
    clocks: set[str] = set()
    for raw in rows:
        published, usable = _available_date(
            raw, publication_field=publication_field
        )
        if published:
            # Preserve a parseable newest publication even when an explicit
            # usable date is malformed; that batch must block stale fallback.
            clocks.add(usable or published)
    return sorted(clocks)


def _dedupe_rows(
    rows: Iterable[dict[str, Any]],
    *,
    key_fn: Callable[[Mapping[str, Any]], tuple[Any, ...]],
    label: str,
) -> list[dict[str, Any]]:
    """Deduplicate byte-equivalent normalized rows and reject conflicts."""
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        prior = unique.get(key)
        if prior is None:
            unique[key] = row
        elif prior != row:
            raise FinraVenueShortCrowdingGateError(
                f"conflicting duplicate {label} key: {key!r}"
            )
    return list(unique.values())


def load_jsonl_rows(path: Path | str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, Mapping):
            rows.append(dict(value))
    return rows


def load_short_interest_rows(path: Path | str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    values = payload.get("rows") if isinstance(payload, Mapping) else payload
    if not isinstance(values, list):
        raise FinraVenueShortCrowdingGateError("short-interest payload has no rows list")
    return [dict(row) for row in values if isinstance(row, Mapping)]


def load_revision_safe_short_interest_rows(
    normalized_path: Path | str,
    raw_source_dir: Path | str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach raw FINRA revision flags and fail closed on revised records.

    FINRA historical downloads expose the latest corrected row rather than an
    as-published vintage.  A row carrying ``revisionFlag=R`` therefore cannot
    be replayed as the value known at its original publication time.  The row
    is retained for audit but marked non-PIT so normalization excludes it.
    Every normalized row must match exactly one raw ``(ticker, settlement)``
    key; missing, duplicate, or unknown revision flags abort the source load.
    """
    normalized = load_short_interest_rows(normalized_path)
    raw_dir = Path(raw_source_dir)
    raw_paths = sorted(raw_dir.glob("*.csv"))
    if not raw_paths:
        raise FinraVenueShortCrowdingGateError(
            "no raw FINRA short-interest source files"
        )

    flags: dict[tuple[str, str], str] = {}
    raw_row_count = 0
    for path in raw_paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle, delimiter="|"):
                raw_row_count += 1
                ticker = str(raw.get("symbolCode") or "").strip().upper()
                settlement = _try_date(raw.get("settlementDate"))
                if not ticker or settlement is None:
                    continue
                flag = str(raw.get("revisionFlag") or "").strip().upper()
                if flag not in {"", "R"}:
                    raise FinraVenueShortCrowdingGateError(
                        f"unsupported FINRA revisionFlag {flag!r} in {path.name}"
                    )
                key = (ticker, settlement)
                if key in flags:
                    raise FinraVenueShortCrowdingGateError(
                        f"duplicate raw FINRA short-interest key: {key!r}"
                    )
                flags[key] = flag

    revised = 0
    attached: list[dict[str, Any]] = []
    missing: list[tuple[str, str]] = []
    for raw in normalized:
        row = dict(raw)
        ticker = str(row.get("ticker") or "").strip().upper()
        settlement = _try_date(row.get("settlement_date"))
        key = (ticker, settlement or "")
        if key not in flags:
            missing.append(key)
            continue
        flag = flags[key]
        row["revision_flag"] = flag or None
        row["as_published_vintage_available"] = flag != "R"
        if flag == "R":
            revised += 1
            row["pit_safe"] = False
            row["pit_caveat"] = "revised_latest_value_without_as_published_vintage"
        attached.append(row)
    if missing:
        raise FinraVenueShortCrowdingGateError(
            "normalized FINRA short-interest rows lack raw provenance: "
            f"{missing[:5]!r}"
        )
    audit = {
        "schema": "finra_short_interest_revision_provenance_audit_v1",
        "raw_source_file_count": len(raw_paths),
        "raw_row_count": raw_row_count,
        "raw_unique_key_count": len(flags),
        "normalized_row_count": len(normalized),
        "matched_normalized_row_count": len(attached),
        "revised_normalized_row_count": revised,
        "unrevised_normalized_row_count": len(attached) - revised,
        "missing_normalized_key_count": 0,
        "revision_policy": "revisionFlag_R_fails_closed_no_as_published_vintage",
        "all_normalized_rows_raw_matched": len(attached) == len(normalized),
    }
    return attached, audit


def _normalise_venue_rows(
    rows: Iterable[Mapping[str, Any]], *, side: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    quantity_field = "ats_share_quantity" if side == "ats" else "otc_share_quantity"
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        ticker = str(raw.get("ticker") or "").strip().upper()
        week = _try_date(raw.get("week_start_date"))
        published, available = _available_date(
            raw, publication_field="published_date"
        )
        tier = str(raw.get("tier") or "").strip().upper()
        quantity = _number(raw.get(quantity_field))
        expected_source = _VENUE_SOURCES[side]
        source = str(raw.get("source") or expected_source).strip()
        if (
            not ticker
            or ticker in NON_COMMON_STOCK_TICKERS
            or not week
            or not published
            or not available
            or week > published
            or published > available
            or not tier
            or quantity is None
            or quantity <= 0
            or source != expected_source
        ):
            invalid.append({"index": index, "ticker": ticker or None, "reason": "invalid_or_excluded"})
            continue
        valid.append(
            {
                "ticker": ticker,
                "week_start_date": week,
                "published_date": published,
                "usable_trade_date": available,
                "publication_date_method": str(
                    raw.get("publication_date_method")
                    or _VENUE_PUBLICATION_METHOD
                ),
                "source": source,
                "tier": tier,
                quantity_field: quantity,
            }
        )
    valid = _dedupe_rows(
        valid,
        key_fn=lambda row: (
            row["ticker"],
            row["week_start_date"],
            row["published_date"],
            row["tier"],
        ),
        label=side,
    )
    valid.sort(key=lambda row: (row["usable_trade_date"], row["ticker"], row["week_start_date"], row["tier"]))
    return valid, invalid


def _normalise_short_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        ticker = str(raw.get("ticker") or "").strip().upper()
        published, available = _available_date(
            raw, publication_field="publication_date"
        )
        settlement = _try_date(raw.get("settlement_date"))
        change = _number(raw.get("short_interest_change_pct"))
        dtc = _number(raw.get("days_to_cover"))
        pit_safe = raw.get("pit_safe") is True
        revision_flag = str(raw.get("revision_flag") or "").strip().upper()
        as_published_available = raw.get(
            "as_published_vintage_available", True
        ) is True
        if (
            not ticker
            or ticker in NON_COMMON_STOCK_TICKERS
            or not published
            or not available
            or not settlement
            or settlement >= published
            or published > available
            or change is None
            or dtc is None
            or dtc < 0
            or not pit_safe
            or revision_flag not in {"", "R"}
            or revision_flag == "R"
            or not as_published_available
        ):
            invalid.append({"index": index, "ticker": ticker or None, "reason": "invalid_or_excluded"})
            continue
        valid.append(
            {
                "ticker": ticker,
                "publication_date": published,
                "usable_trade_date": available,
                "publication_date_method": str(
                    raw.get("publication_date_method")
                    or _SHORT_PUBLICATION_METHOD
                ),
                "settlement_date": settlement,
                "short_interest_change_pct": change,
                "days_to_cover": dtc,
                "pit_safe": True,
                "revision_flag": revision_flag or None,
                "as_published_vintage_available": True,
                "source_url": str(raw.get("source_url") or ""),
            }
        )
    valid = _dedupe_rows(
        valid,
        key_fn=lambda row: (row["usable_trade_date"], row["ticker"]),
        label="short_interest",
    )
    valid.sort(key=lambda row: (row["usable_trade_date"], row["ticker"]))
    return valid, invalid


def build_finra_venue_short_crowding_exclusion_index(
    ats_rows: Iterable[Mapping[str, Any]],
    otc_rows: Iterable[Mapping[str, Any]],
    short_interest_rows: Iterable[Mapping[str, Any]],
    trading_sessions: Iterable[Any],
    *,
    source_identities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the hash-bound signal-day exclusion index for replay and daily use."""
    raw_ats, raw_otc, raw_short = list(ats_rows), list(otc_rows), list(short_interest_rows)
    sessions = _sessions(trading_sessions)
    ats_release_dates = _raw_release_dates(
        raw_ats, publication_field="published_date"
    )
    otc_release_dates = _raw_release_dates(
        raw_otc, publication_field="published_date"
    )
    short_release_dates = _raw_release_dates(
        raw_short, publication_field="publication_date"
    )
    ats, invalid_ats = _normalise_venue_rows(raw_ats, side="ats")
    otc, invalid_otc = _normalise_venue_rows(raw_otc, side="otc")
    short, invalid_short = _normalise_short_rows(raw_short)

    exact_otc = {
        (row["ticker"], row["week_start_date"], row["published_date"], row["tier"]): row
        for row in otc
    }
    venue_by_release: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched_ats = 0
    for row in ats:
        key = (row["ticker"], row["week_start_date"], row["published_date"], row["tier"])
        other = exact_otc.get(key)
        if other is None:
            unmatched_ats += 1
            continue
        denominator = row["ats_share_quantity"] + other["otc_share_quantity"]
        if denominator <= 0:
            continue
        venue_by_release[row["usable_trade_date"]].append(
            {
                "ticker": row["ticker"],
                "week_start_date": row["week_start_date"],
                "published_date": row["published_date"],
                "usable_trade_date": row["usable_trade_date"],
                "publication_date_method": row["publication_date_method"],
                "source": row["source"],
                "tier": row["tier"],
                "ats_share_quantity": row["ats_share_quantity"],
                "otc_share_quantity": other["otc_share_quantity"],
                "venue_share": row["ats_share_quantity"] / denominator,
            }
        )
    short_by_release: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in short:
        short_by_release[row["usable_trade_date"]][row["ticker"]] = row

    by_signal_day: dict[str, list[str]] = {}
    coverage_by_signal_day: dict[str, list[str]] = {}
    state_by_signal_day: dict[str, dict[str, Any]] = {}
    for signal_day in sessions:
        ats_pos = bisect_left(ats_release_dates, signal_day) - 1
        otc_pos = bisect_left(otc_release_dates, signal_day) - 1
        short_pos = bisect_left(short_release_dates, signal_day) - 1
        if ats_pos < 0 or otc_pos < 0 or short_pos < 0:
            by_signal_day[signal_day] = []
            coverage_by_signal_day[signal_day] = []
            state_by_signal_day[signal_day] = {"status": "uncovered_no_prior_release"}
            continue
        ats_date = ats_release_dates[ats_pos]
        otc_date = otc_release_dates[otc_pos]
        short_date = short_release_dates[short_pos]
        if ats_date != otc_date:
            by_signal_day[signal_day] = []
            coverage_by_signal_day[signal_day] = []
            state_by_signal_day[signal_day] = {
                "status": "uncovered_latest_venue_release_mismatch",
                "ats_usable_trade_date": ats_date,
                "otc_usable_trade_date": otc_date,
                "short_interest_usable_trade_date": short_date,
            }
            continue
        venue_date = ats_date
        venue_age = _age(signal_day, venue_date)
        short_age = _age(signal_day, short_date)
        if venue_age > MAX_VENUE_AGE_DAYS or short_age > MAX_SHORT_INTEREST_AGE_DAYS:
            by_signal_day[signal_day] = []
            coverage_by_signal_day[signal_day] = []
            state_by_signal_day[signal_day] = {
                "status": "uncovered_stale_release",
                "venue_publication_date": venue_date,
                "short_interest_publication_date": short_date,
                "venue_age_days": venue_age,
                "short_interest_age_days": short_age,
            }
            continue
        current_venue = venue_by_release.get(venue_date) or []
        if not current_venue:
            by_signal_day[signal_day] = []
            coverage_by_signal_day[signal_day] = []
            state_by_signal_day[signal_day] = {
                "status": "uncovered_unusable_latest_venue_release",
                "venue_usable_trade_date": venue_date,
                "short_interest_usable_trade_date": short_date,
            }
            continue
        current_short = short_by_release.get(short_date) or {}
        if not current_short:
            by_signal_day[signal_day] = []
            coverage_by_signal_day[signal_day] = []
            state_by_signal_day[signal_day] = {
                "status": "uncovered_unusable_latest_short_interest_release",
                "venue_usable_trade_date": venue_date,
                "short_interest_usable_trade_date": short_date,
            }
            continue
        joined: list[dict[str, Any]] = []
        for venue in current_venue:
            short_row = current_short.get(venue["ticker"])
            if short_row is None:
                continue
            joined.append({**venue, **short_row})
        if not joined:
            by_signal_day[signal_day] = []
            coverage_by_signal_day[signal_day] = []
            state_by_signal_day[signal_day] = {"status": "uncovered_empty_join"}
            continue
        venue_median = float(median(row["venue_share"] for row in joined))
        dtc_median = float(median(row["days_to_cover"] for row in joined))
        excluded = sorted(
            row["ticker"]
            for row in joined
            if row["venue_share"] > venue_median
            and row["short_interest_change_pct"] > 0
            and row["days_to_cover"] >= dtc_median
        )
        covered = sorted({row["ticker"] for row in joined})
        by_signal_day[signal_day] = excluded
        coverage_by_signal_day[signal_day] = covered
        state_by_signal_day[signal_day] = {
            "status": "covered",
            "venue_publication_date": sorted(
                {row["published_date"] for row in joined}
            )[-1],
            "venue_usable_trade_date": venue_date,
            "venue_week_start_dates": sorted(
                {row["week_start_date"] for row in joined}
            ),
            "short_interest_publication_date": sorted(
                {row["publication_date"] for row in joined}
            )[-1],
            "short_interest_usable_trade_date": short_date,
            "venue_age_days": venue_age,
            "short_interest_age_days": short_age,
            "joined_ticker_count": len(covered),
            "excluded_ticker_count": len(excluded),
            "venue_share_median": venue_median,
            "days_to_cover_median": dtc_median,
        }

    row_hashes = {
        "ats_rows": canonical_hash(ats),
        "otc_rows": canonical_hash(otc),
        "short_interest_rows": canonical_hash(short),
    }
    bound_source_identities = deepcopy(
        dict(source_identities or {"mode": "in_memory_rows"})
    )
    source_hashes = {
        **row_hashes,
        "source_identities": canonical_hash(bound_source_identities),
    }
    source_hash = canonical_hash(
        {
            "row_hashes": row_hashes,
            "source_identities": bound_source_identities,
            "raw_release_clocks": {
                "ats": ats_release_dates,
                "otc": otc_release_dates,
                "short_interest": short_release_dates,
            },
        }
    )
    payload: dict[str, Any] = {
        "schema": "finra_venue_short_crowding_exclusion_index_v2",
        "source": SOURCE,
        "source_hash": source_hash,
        "source_hashes": source_hashes,
        "source_identities": bound_source_identities,
        "raw_release_clocks": {
            "ats": ats_release_dates,
            "otc": otc_release_dates,
            "short_interest": short_release_dates,
        },
        "rule_version": RULE_VERSION,
        "policy": deepcopy(_POLICY),
        "trading_sessions": sessions,
        "trading_sessions_hash": canonical_hash(sessions),
        "input_row_counts": {"ats": len(raw_ats), "otc": len(raw_otc), "short_interest": len(raw_short)},
        "valid_row_counts": {"ats": len(ats), "otc": len(otc), "short_interest": len(short)},
        "invalid_row_counts": {"ats": len(invalid_ats), "otc": len(invalid_otc), "short_interest": len(invalid_short)},
        "unmatched_ats_exact_keys": unmatched_ats,
        "by_signal_day": by_signal_day,
        "coverage_by_signal_day": coverage_by_signal_day,
        "state_by_signal_day": state_by_signal_day,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_live_orders": False,
    }
    payload["index_hash"] = canonical_hash(payload)
    return payload


class FinraVenueShortCrowdingEntryAdmissionPolicy:
    """Hash-bound fresh-core entry policy plus daily diagnostic resolver.

    ``resolve`` is intentionally diagnostic: it describes the next-session
    exclusion set for replay/daily parity.  Backtest execution must call
    ``evaluate`` after qualification and fill-date selection; this object must
    never be installed as an entry-universe membership resolver.
    """

    def __init__(
        self,
        base_tickers: Iterable[str],
        exclusion_index: Mapping[str, Any],
        trading_sessions: Iterable[Any] | None = None,
        source_hash: str | None = None,
    ) -> None:
        self._base = frozenset(_tickers(base_tickers))
        self._index = deepcopy(dict(exclusion_index))
        stored_hash = self._index.pop("index_hash", None)
        if stored_hash != canonical_hash(self._index):
            raise FinraVenueShortCrowdingGateError("exclusion index hash mismatch")
        if (
            self._index.get("schema") != "finra_venue_short_crowding_exclusion_index_v2"
            or self._index.get("source") != SOURCE
            or self._index.get("rule_version") != RULE_VERSION
            or self._index.get("policy") != _POLICY
        ):
            raise FinraVenueShortCrowdingGateError("exclusion index identity mismatch")
        self._index["index_hash"] = stored_hash
        indexed_sessions = _sessions(self._index.get("trading_sessions") or [])
        supplied = _sessions(trading_sessions) if trading_sessions is not None else indexed_sessions
        if supplied != indexed_sessions:
            raise FinraVenueShortCrowdingGateError("resolver sessions differ from index")
        if source_hash is not None and source_hash != self._index.get("source_hash"):
            raise FinraVenueShortCrowdingGateError("resolver source hash differs from index")
        self._sessions = tuple(indexed_sessions)
        self._source_hash = str(self._index["source_hash"])
        self._metadata = {
            "schema": "finra_venue_short_crowding_entry_admission_metadata_v2",
            "source": SOURCE,
            "source_hash": self._source_hash,
            "source_hashes": deepcopy(self._index["source_hashes"]),
            "source_identities": deepcopy(self._index["source_identities"]),
            "rule_version": RULE_VERSION,
            "index_hash": stored_hash,
            "trading_sessions_hash": self._index["trading_sessions_hash"],
            "base_ticker_count": len(self._base),
            "base_membership_hash": membership_hash(self._base),
            "fill_semantics": "evaluate denies only when actual fill_date equals the strict next trading session after signal_date",
            "unknown_coverage_policy": "fail_open_to_base_universe_with_provenance",
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_live_orders": False,
        }

    @property
    def data_tickers(self) -> frozenset[str]:
        return self._base

    @property
    def metadata(self) -> dict[str, Any]:
        return deepcopy(self._metadata)

    def resolve(self, as_of: Any) -> dict[str, Any]:
        day = _date10(as_of, field="as_of")
        next_pos = bisect_right(self._sessions, day)
        entry_session = self._sessions[next_pos] if next_pos < len(self._sessions) else None
        excluded_all = set(self._index.get("by_signal_day", {}).get(day, []))
        covered_all = set(self._index.get("coverage_by_signal_day", {}).get(day, []))
        state = deepcopy(self._index.get("state_by_signal_day", {}).get(day) or {"status": "uncovered_signal_day"})
        # Without a known next session there is no execution date to which the
        # policy can attach.  This must be a true fail-open resolution.
        if entry_session is None:
            excluded_all = set()
            covered_all = set()
        excluded = sorted(self._base & excluded_all)
        covered = sorted(self._base & covered_all)
        missing = sorted(self._base - covered_all)
        eligible = sorted(self._base - excluded_all)
        if entry_session is None:
            coverage_status = "unknown_no_next_trading_session"
        elif state.get("status") != "covered":
            coverage_status = str(state.get("status") or "uncovered")
        elif not missing:
            coverage_status = "covered"
        elif covered:
            coverage_status = "partial"
        else:
            coverage_status = "uncovered"
        semantic = {
            "as_of": day,
            "entry_session": entry_session,
            "eligible": eligible,
            "excluded": excluded,
            "covered": covered,
            "missing": missing,
            "coverage_status": coverage_status,
            "source_hash": self._source_hash,
            "index_hash": self._index["index_hash"],
            "rule_version": RULE_VERSION,
            "state": state,
        }
        snapshot_hash = canonical_hash({"record_type": "finra_venue_short_entry_membership", **semantic})
        record_hash = canonical_hash({"record_type": "finra_venue_short_entry_resolution", **semantic})
        provenance = {
            "signal_date": day,
            "rule_version": RULE_VERSION,
            "index_hash": self._index["index_hash"],
            "source_hash": self._source_hash,
            "source_hashes": deepcopy(self._index["source_hashes"]),
            "source_identities": deepcopy(self._index["source_identities"]),
            "entry_session": entry_session,
            "excluded_tickers": excluded,
            "coverage_status": coverage_status,
            "source_coverage_complete": not missing and state.get("status") == "covered",
            "covered_tickers": covered,
            "missing_tickers": missing,
            "state": state,
            "fill_semantics": self._metadata["fill_semantics"],
            "unknown_coverage_policy": self._metadata["unknown_coverage_policy"],
            "trade_enabled": False,
            "strategy_behavior_changed": False,
            "alters_live_orders": False,
        }
        reason = "next_session_joint_crowding_entry_exclusion" if excluded else (
            "no_active_next_session_exclusion" if state.get("status") == "covered" else f"fail_open_{coverage_status}"
        )
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
            "reason": reason,
            "provenance": provenance,
        }

    def evaluate(
        self, *, signal_date: Any, ticker: Any, fill_date: Any
    ) -> dict[str, Any]:
        """Evaluate one already-qualified fresh entry at its actual fill date."""
        signal_day = _date10(signal_date, field="signal_date")
        actual_fill = _date10(fill_date, field="fill_date")
        symbol = str(ticker or "").strip().upper()
        if not symbol:
            raise FinraVenueShortCrowdingGateError("ticker must be non-empty")
        resolved = self.resolve(signal_day)
        provenance = deepcopy(resolved["provenance"])
        expected_fill = provenance.get("entry_session")
        excluded = set(provenance.get("excluded_tickers") or [])
        strict_next_session = bool(expected_fill and actual_fill == expected_fill)
        deny = strict_next_session and symbol in excluded
        if deny:
            status = "denied"
            reason = "finra_joint_crowding_strict_next_session"
        elif not expected_fill:
            status = "admitted_fail_open"
            reason = "no_next_trading_session"
        elif not strict_next_session:
            status = "admitted_not_strict_next_session"
            reason = "actual_fill_date_differs_from_strict_next_session"
        elif provenance.get("coverage_status") not in {"covered", "partial"}:
            status = "admitted_fail_open"
            reason = f"source_{provenance.get('coverage_status') or 'uncovered'}"
        else:
            status = "admitted"
            reason = "ticker_not_joint_crowding_excluded"
        decision_provenance = {
            **provenance,
            "ticker": symbol,
            "actual_fill_date": actual_fill,
            "strict_next_session_match": strict_next_session,
            "resolution_snapshot_sha256": resolved["snapshot_sha256"],
            "resolution_record_hash": resolved["record_hash"],
        }
        return {
            "admit": not deny,
            "status": status,
            "reason": reason,
            "provenance": decision_provenance,
        }

    def __call__(self, as_of: Any) -> set[str]:
        return set(self.resolve(as_of)["tickers"])


# Compatibility name for historical artifacts only.  New callers must pass
# this object through BacktestEngine.entry_admission_policy, never through the
# entry-universe resolver interface.
FinraVenueShortCrowdingEntryUniverseResolver = (
    FinraVenueShortCrowdingEntryAdmissionPolicy
)


def build_daily_entry_admission_snapshot(
    ats_rows: Iterable[Mapping[str, Any]],
    otc_rows: Iterable[Mapping[str, Any]],
    short_interest_rows: Iterable[Mapping[str, Any]],
    as_of: Any,
    trading_sessions: Iterable[Any],
    base_tickers: Iterable[str],
    *,
    source_identities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    sessions = list(trading_sessions)
    base = _tickers(base_tickers)
    index = build_finra_venue_short_crowding_exclusion_index(
        list(ats_rows),
        list(otc_rows),
        list(short_interest_rows),
        sessions,
        source_identities=source_identities,
    )
    resolver = FinraVenueShortCrowdingEntryAdmissionPolicy(
        base, index, trading_sessions=sessions, source_hash=index["source_hash"]
    )
    resolved = resolver.resolve(as_of)
    provenance = resolved["provenance"]
    excluded = list(provenance["excluded_tickers"])
    return {
        "schema": "finra_venue_short_crowding_daily_snapshot_v2",
        "record_id": f"finra_venue_short_crowding:{resolved['as_of']}",
        "source": SOURCE,
        "source_hash": resolved["source_hash"],
        "source_hashes": deepcopy(provenance["source_hashes"]),
        "source_identities": deepcopy(provenance["source_identities"]),
        "rule_version": RULE_VERSION,
        "policy": deepcopy(_POLICY),
        "as_of": resolved["as_of"],
        "next_trading_session": provenance["entry_session"],
        "status": "ok" if provenance["entry_session"] else "calendar_uncovered",
        "decision": "observe_entry_admission_default_off",
        "base_tickers": base,
        "base_ticker_count": len(base),
        "eligible_tickers": list(resolved["tickers"]),
        "eligible_ticker_count": resolved["ticker_count"],
        "excluded_tickers_for_next_session": excluded,
        "candidate_count": len(excluded),
        "candidates": [
            {
                "ticker": ticker,
                "signal_date": resolved["as_of"],
                "entry_session": provenance["entry_session"],
                "decision": "observe_fresh_entry_exclusion_default_off",
                "rule_version": RULE_VERSION,
                "trade_enabled": False,
                "alters_live_orders": False,
            }
            for ticker in excluded
        ],
        "coverage_status": provenance["coverage_status"],
        "source_coverage_complete": provenance["source_coverage_complete"],
        "covered_tickers": list(provenance["covered_tickers"]),
        "missing_tickers": list(provenance["missing_tickers"]),
        "state": deepcopy(provenance["state"]),
        "exclusion_index_hash": index["index_hash"],
        "resolver_snapshot_hash": resolved["snapshot_sha256"],
        "resolver_record_hash": resolved["record_hash"],
        "membership_hash": resolved["membership_hash"],
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


__all__ = [
    "MAX_SHORT_INTEREST_AGE_DAYS",
    "MAX_VENUE_AGE_DAYS",
    "NON_COMMON_STOCK_TICKERS",
    "RULE_VERSION",
    "SOURCE",
    "TRADE_ENABLED",
    "FinraVenueShortCrowdingEntryAdmissionPolicy",
    "FinraVenueShortCrowdingEntryUniverseResolver",
    "FinraVenueShortCrowdingGateError",
    "build_daily_entry_admission_snapshot",
    "build_finra_venue_short_crowding_exclusion_index",
    "load_jsonl_rows",
    "load_revision_safe_short_interest_rows",
    "load_short_interest_rows",
]
