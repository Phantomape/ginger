"""Freeze an outcome-blind EFFECT/prospectus-clock selling-holder roster."""

from __future__ import annotations

import bisect
from collections import Counter, defaultdict
from datetime import datetime, time, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
LINKAGE = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_effectiveness_linkage_20260824.json"
)
REGISTRATION_ROSTER = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_overhang_roster_20260824.json"
)
IDENTITY_AUDIT = (
    REPO_ROOT / "data" / "alpha_search" / "massive_asof_identity_readiness_20260728.json"
)
DATABASE = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
OUTPUT = (
    REPO_ROOT
    / "data"
    / "alpha_search"
    / "sec_selling_holder_activation_roster_20260824.json"
)
HOLD_SESSIONS = 10
COOLDOWN_SESSIONS = 10
LIQUIDITY_LOOKBACK = 20
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0
MIN_CLOSE = 3.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_membership(
    connection: sqlite3.Connection,
) -> list[tuple[datetime, str, frozenset[str]]]:
    audit = json.loads(IDENTITY_AUDIT.read_text(encoding="utf-8"))
    cutoffs = {
        date_text: parse_utc(value)
        for date_text, value in audit["decision_cutoff_utc_by_date"].items()
    }
    keys = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT snapshot_key FROM instrument_master "
            "WHERE snapshot_key LIKE 'reference-asof:%:active=true:type=CS' "
            "ORDER BY snapshot_key"
        )
    ]
    snapshots = []
    for key in keys:
        as_of = key.split(":")[1]
        members = frozenset(
            row[0]
            for row in connection.execute(
                "SELECT ticker FROM instrument_master WHERE snapshot_key=?", (key,)
            )
        )
        snapshots.append((cutoffs[as_of], as_of, members))
    return snapshots


def exact_activation(row: dict[str, Any]) -> tuple[datetime, str, list[str]] | None:
    clocks: list[tuple[datetime, str, str]] = []
    effect = row.get("official_effect_clock") or {}
    if effect.get("effective_at_utc"):
        clocks.append(
            (
                parse_utc(str(effect["effective_at_utc"])),
                "official_effect_xml",
                str((row.get("effect") or {}).get("accession") or ""),
            )
        )
    prospectus = row.get("first_resale_prospectus") or {}
    if prospectus.get("acceptance_datetime_raw"):
        clocks.append(
            (
                parse_utc(str(prospectus["acceptance_datetime_raw"])),
                str(prospectus.get("form") or "resale_prospectus"),
                str(prospectus.get("accession") or ""),
            )
        )
    if not clocks:
        return None
    clocks.sort()
    activation_at = clocks[-1][0]
    sources = [kind for _clock, kind, _accession in clocks]
    accessions = [accession for _clock, _kind, accession in clocks if accession]
    return activation_at, "+".join(sources), accessions


def build() -> dict[str, Any]:
    linkage = json.loads(LINKAGE.read_text(encoding="utf-8"))
    registration = json.loads(REGISTRATION_ROSTER.read_text(encoding="utf-8"))
    frozen_by_accession = {
        str(row["accession"]): row for row in registration["rows"]
    }
    connection = sqlite3.connect(str(DATABASE))
    snapshots = load_membership(connection)
    calendar = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT trade_date FROM daily_bars WHERE ticker='SPY' ORDER BY trade_date"
        )
    ]
    ny = ZoneInfo("America/New_York")
    opens = [
        datetime.combine(datetime.fromisoformat(day).date(), time(9, 30), ny).astimezone(
            timezone.utc
        )
        for day in calendar
    ]
    closes = [
        datetime.combine(datetime.fromisoformat(day).date(), time(16, 0), ny).astimezone(
            timezone.utc
        )
        for day in calendar
    ]

    counts: Counter[str] = Counter()
    by_window: dict[str, Counter[str]] = defaultdict(Counter)
    candidates: list[dict[str, Any]] = []
    for linked in linkage["rows"]:
        window = str(linked["window"])
        counts["source_rows"] += 1
        by_window[window]["source_rows"] += 1
        frozen = frozen_by_accession.get(str(linked["registration_accession"]))
        activation = exact_activation(linked)
        if frozen is None:
            counts["registration_roster_missing"] += 1
            by_window[window]["registration_roster_missing"] += 1
            continue
        if activation is None:
            counts["no_exact_activation_clock"] += 1
            by_window[window]["no_exact_activation_clock"] += 1
            continue
        activation_at, activation_source, activation_accessions = activation
        ticker = str(frozen["ticker"])
        membership = [item for item in snapshots if item[0] <= activation_at]
        if not membership or ticker not in membership[-1][2]:
            counts["fails_activation_membership"] += 1
            by_window[window]["fails_activation_membership"] += 1
            continue
        entry_index = bisect.bisect_right(opens, activation_at)
        completed_index = bisect.bisect_right(closes, activation_at) - 1
        if (
            completed_index < 0
            or entry_index >= len(calendar)
            or entry_index + HOLD_SESSIONS - 1 >= len(calendar)
        ):
            counts["missing_calendar"] += 1
            by_window[window]["missing_calendar"] += 1
            continue
        completed_date = calendar[completed_index]
        bars = list(
            connection.execute(
                "SELECT close,vwap,volume FROM daily_bars "
                "WHERE ticker=? AND trade_date<=? AND close>0 AND vwap>0 AND volume>0 "
                "ORDER BY trade_date DESC LIMIT ?",
                (ticker, completed_date, LIQUIDITY_LOOKBACK),
            )
        )
        if len(bars) < LIQUIDITY_LOOKBACK:
            counts["missing_exact_liquidity_history"] += 1
            by_window[window]["missing_exact_liquidity_history"] += 1
            continue
        median_dollar_volume = statistics.median(
            float(bar[1]) * float(bar[2]) for bar in bars
        )
        if median_dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME or float(bars[0][0]) < MIN_CLOSE:
            counts["fails_activation_liquidity_or_price"] += 1
            by_window[window]["fails_activation_liquidity_or_price"] += 1
            continue
        candidates.append(
            {
                "window": window,
                "ticker": ticker,
                "registration_accession": frozen["accession"],
                "registration_accepted_at": frozen["accepted_at"],
                "activation_at": activation_at.isoformat().replace("+00:00", "Z"),
                "activation_source": activation_source,
                "activation_accessions": activation_accessions,
                "entry_session": calendar[entry_index],
                "h10_exit_session": calendar[entry_index + HOLD_SESSIONS - 1],
                "membership_asof": membership[-1][1],
                "median_dollar_volume_20_prior": round(median_dollar_volume, 2),
                "last_completed_close": float(bars[0][0]),
                "primary_document_sha256": frozen["primary_document_sha256"],
                "resale_evidence": frozen["resale_evidence"],
            }
        )
    connection.close()

    candidates.sort(
        key=lambda row: (
            row["entry_session"],
            row["activation_at"],
            row["ticker"],
            row["registration_accession"],
        )
    )
    deduped: list[dict[str, Any]] = []
    seen_ticker_entry: set[tuple[str, str]] = set()
    for row in candidates:
        key = (str(row["ticker"]), str(row["entry_session"]))
        if key in seen_ticker_entry:
            counts["same_ticker_entry_deduped"] += 1
            by_window[row["window"]]["same_ticker_entry_deduped"] += 1
            continue
        seen_ticker_entry.add(key)
        deduped.append(row)

    calendar_index = {day: index for index, day in enumerate(calendar)}
    rows: list[dict[str, Any]] = []
    last_entry: dict[str, int] = {}
    for row in deduped:
        ticker = str(row["ticker"])
        entry_index = calendar_index[str(row["entry_session"])]
        if ticker in last_entry and entry_index - last_entry[ticker] < COOLDOWN_SESSIONS:
            counts["cooldown_dropped"] += 1
            by_window[row["window"]]["cooldown_dropped"] += 1
            continue
        rows.append(row)
        last_entry[ticker] = entry_index
        counts["roster_rows"] += 1
        by_window[row["window"]]["roster_rows"] += 1

    rows_by_date = Counter(row["entry_session"] for row in rows)
    counts_by_window = {
        window: sum(row["window"] == window for row in rows)
        for window in ("old_thin", "mid_weak", "late_strong")
    }
    return {
        "schema_version": 1,
        "record_type": "outcome_blind_sec_selling_holder_activation_roster",
        "policy_version": "sec_selling_holder_activation_h10_v1",
        "linkage_path": LINKAGE.relative_to(REPO_ROOT).as_posix(),
        "linkage_sha256": sha256_file(LINKAGE),
        "registration_roster_path": REGISTRATION_ROSTER.relative_to(REPO_ROOT).as_posix(),
        "registration_roster_sha256": sha256_file(REGISTRATION_ROSTER),
        "identity_audit_path": IDENTITY_AUDIT.relative_to(REPO_ROOT).as_posix(),
        "identity_audit_sha256": sha256_file(IDENTITY_AUDIT),
        "predicate": {
            "activation_clock": (
                "later of exact official EFFECT XML clock and first 424B3/424B4 "
                "acceptance clock when both exist; the sole exact clock otherwise"
            ),
            "entry": "first regular-session open strictly after activation_at",
            "exit": "tenth session close counting entry",
            "membership": "latest known research-PIT active=true,type=CS snapshot",
            "liquidity_lookback": LIQUIDITY_LOOKBACK,
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_last_completed_close": MIN_CLOSE,
            "same_ticker_entry_dedup": "earliest activation then registration accession",
            "cooldown_sessions": COOLDOWN_SESSIONS,
        },
        "counts": dict(counts),
        "counts_by_stage_and_window": {
            key: dict(value) for key, value in sorted(by_window.items())
        },
        "counts_by_window": counts_by_window,
        "readiness_rule": "at least 25 final rows in every frozen window",
        "readiness_passed": all(value >= 25 for value in counts_by_window.values()),
        "unique_tickers": len({row["ticker"] for row in rows}),
        "unique_entry_dates": len(rows_by_date),
        "max_rows_on_one_entry_date": max(rows_by_date.values(), default=0),
        "rows": rows,
        "outcome_fields_read": False,
        "post_decision_price_values_read": False,
        "trade_enabled": False,
    }


if __name__ == "__main__":
    payload = build()
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2))
