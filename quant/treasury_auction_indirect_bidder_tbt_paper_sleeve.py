"""Shared default-off Treasury indirect-bidder-share TBT paper helper.

Callers supply already archived Treasury auction rows and adjusted market
bars.  This module performs no network access, persistence, or order routing.
Historical replay and daily paper snapshots therefore use one fail-closed
point-in-time event rule while leaving every executable strategy path alone.
"""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from quant import treasury_auction_weak_demand_tbt_paper_sleeve as execution


SLEEVE_NAME = "TREASURY_AUCTION_INDIRECT_BIDDER_SHARE_TBT_PAPER"
RULE_VERSION = "treasury_nominal_coupon_weak_indirect_share_tbt_nextopen_5d_v1"
LOOKBACK_AUCTIONS = execution.LOOKBACK_AUCTIONS
HOLD_SESSIONS = execution.HOLD_SESSIONS
NOTIONAL_USD = execution.NOTIONAL_USD
ROUND_TRIP_COST_PCT = execution.ROUND_TRIP_COST_PCT
TICKER = execution.TICKER
MAX_CONCURRENT_POSITIONS = execution.MAX_CONCURRENT_POSITIONS

_ALLOWED_SECURITY_TYPES = {"note", "bond"}
ALLOWED_ORIGINAL_TERMS = {
    "2-Year",
    "3-Year",
    "5-Year",
    "7-Year",
    "10-Year",
    "20-Year",
    "30-Year",
}
_RELEASE_TIME_RE = re.compile(r"^(?P<hour>[0-2][0-9]):(?P<minute>[0-5][0-9])$")


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _yes(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _term_key(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalise_auction_rows(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return unique, fail-closed nominal coupon auction observations."""

    canonical: dict[tuple[str, str], dict[str, Any]] = {}
    conflicted: set[tuple[str, str]] = set()
    for source in records:
        if not isinstance(source, Mapping):
            continue
        security_type = str(source.get("security_type") or "").strip()
        if security_type.lower() not in _ALLOWED_SECURITY_TYPES:
            continue
        if "tips" not in source or _yes(source.get("tips")):
            continue
        if _yes(source.get("floating_rate")) or _yes(source.get("frn")):
            continue

        auction_date = _iso_date(source.get("auction_date"))
        publication_value = (
            source.get("result_publication_date")
            or source.get("first_public_result_date")
            or source.get("first_public_date")
            or source.get("result_date")
        )
        signal_date = _iso_date(publication_value) if publication_value else None
        original_term = str(source.get("original_security_term") or "").strip()
        term_key = _term_key(original_term)
        cusip = str(source.get("cusip") or "").strip().upper()
        indirect = _finite_float(source.get("indirect_bidder_accepted"))
        total = _finite_float(source.get("total_accepted"))
        release_time = str(source.get("result_release_time_et") or "").strip()
        release_match = _RELEASE_TIME_RE.fullmatch(release_time)
        if (
            auction_date is None
            or signal_date is None
            or signal_date < auction_date
            or original_term not in ALLOWED_ORIGINAL_TERMS
            or not cusip
            or release_match is None
            or int(release_match.group("hour")) >= 16
            or indirect is None
            or total is None
            or indirect < 0
            or total <= 0
            or indirect > total
        ):
            continue

        share = indirect / total
        key = (auction_date, cusip)
        if key in conflicted:
            continue
        row = {
            "auction_date": auction_date,
            "signal_date": signal_date,
            "cusip": cusip,
            "security_type": security_type.title(),
            "security_term": str(source.get("security_term") or "").strip(),
            "original_security_term": original_term,
            "term_key": term_key,
            "indirect_bidder_accepted": indirect,
            "total_accepted": total,
            "indirect_bidder_accepted_share": share,
            "result_release_time_et": release_time or None,
            "result_filename": str(source.get("result_filename") or "").strip() or None,
            "result_sha256": str(source.get("result_sha256") or "").strip() or None,
            "tips": "No",
            "availability_semantics": "explicit_result_publication_date_before_16_et",
        }
        previous = canonical.get(key)
        if previous is not None and previous != row:
            canonical.pop(key, None)
            conflicted.add(key)
            continue
        canonical[key] = row

    return sorted(
        canonical.values(),
        key=lambda row: (
            row["signal_date"],
            row["auction_date"],
            row["term_key"],
            row["cusip"],
        ),
    )


def build_weak_indirect_bidder_events(
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Emit one decision day when indirect share is below its PIT baseline.

    Each auction is compared with exactly the prior twelve completed auctions
    of the same original tenor.  All decisions in one publication-date group
    are frozen before any row in that group enters history.  Multiple weak
    tenors on a day collapse into one TBT decision.
    """

    history_by_term: dict[str, list[dict[str, Any]]] = {}
    weak_rows: list[dict[str, Any]] = []
    rows = _normalise_auction_rows(records)
    group_start = 0
    while group_start < len(rows):
        signal_date = rows[group_start]["signal_date"]
        group_end = group_start
        while group_end < len(rows) and rows[group_end]["signal_date"] == signal_date:
            group_end += 1
        release_group = rows[group_start:group_end]

        for row in release_group:
            trailing = history_by_term.get(row["term_key"], [])[-LOOKBACK_AUCTIONS:]
            if len(trailing) != LOOKBACK_AUCTIONS:
                continue
            lookback = [float(item["indirect_bidder_accepted_share"]) for item in trailing]
            baseline = statistics.median(lookback)
            share = float(row["indirect_bidder_accepted_share"])
            if share < baseline:
                weak_rows.append(
                    {
                        **row,
                        "lookback_auction_count": LOOKBACK_AUCTIONS,
                        "lookback_indirect_bidder_accepted_shares": lookback,
                        "trailing_12_indirect_bidder_share_median": baseline,
                        "current_auction_excluded_from_baseline": True,
                        "strict_below_median": True,
                    }
                )
        for row in release_group:
            history_by_term.setdefault(row["term_key"], []).append(row)
        group_start = group_end

    events: list[dict[str, Any]] = []
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in weak_rows:
        by_date.setdefault(str(row["signal_date"]), []).append(row)
    for signal_date in sorted(by_date):
        weak = sorted(
            by_date[signal_date],
            key=lambda row: (row["term_key"], row["cusip"]),
        )
        tenors = sorted({str(row["original_security_term"]) for row in weak})
        ids = "|".join(str(row["cusip"]) for row in weak)
        events.append(
            {
                "signal_date": signal_date,
                "auction_date": min(str(row["auction_date"]) for row in weak),
                "decision_id": f"treasury-indirect-share:{signal_date}:{ids}",
                "rule_version": RULE_VERSION,
                "ticker": TICKER,
                "tenors": tenors,
                "auction_count": len(weak),
                "same_day_merged": len(weak) > 1,
                "weak_auctions": weak,
                "paper_notional_usd": NOTIONAL_USD,
                "hold_sessions": HOLD_SESSIONS,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "paper_enabled": True,
                "trade_enabled": False,
                "orders": [],
            }
        )
    return events


def replay_weak_indirect_bidder_tbt(
    events: Iterable[Mapping[str, Any]],
    tbt_bars: Iterable[Mapping[str, Any]],
    benchmark_bars: Mapping[str, Iterable[Mapping[str, Any]]],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Reuse the audited execution envelope with the new event decisions."""

    replay = execution.replay_weak_auction_tbt(
        events,
        tbt_bars,
        benchmark_bars,
        start_date,
        end_date,
    )
    replay["rule_version"] = RULE_VERSION
    return replay


def build_treasury_auction_indirect_bidder_tbt_snapshot(
    as_of_date: str,
    events: Iterable[Mapping[str, Any]],
    price_rows: Any,
    previous_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an idempotent default-off view using the shared execution helper."""

    snapshot = execution.build_treasury_auction_tbt_snapshot(
        as_of_date,
        events,
        price_rows,
        previous_state=previous_state,
    )
    snapshot["sleeve"] = SLEEVE_NAME
    snapshot["rule_version"] = RULE_VERSION
    snapshot["decision_field"] = "indirect_bidder_accepted / total_accepted"
    return snapshot


__all__ = [
    "ALLOWED_ORIGINAL_TERMS",
    "HOLD_SESSIONS",
    "LOOKBACK_AUCTIONS",
    "MAX_CONCURRENT_POSITIONS",
    "NOTIONAL_USD",
    "ROUND_TRIP_COST_PCT",
    "RULE_VERSION",
    "SLEEVE_NAME",
    "TICKER",
    "build_treasury_auction_indirect_bidder_tbt_snapshot",
    "build_weak_indirect_bidder_events",
    "replay_weak_indirect_bidder_tbt",
]
