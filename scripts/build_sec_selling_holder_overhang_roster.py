"""Freeze an outcome-blind executable roster for S-1/F-1 selling-holder overhang."""

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
SOURCE_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_offering_economics_tradeable" / "rows.jsonl"
)
SOURCE_MANIFEST = SOURCE_ROWS.parent / "manifest.json"
IDENTITY_AUDIT = (
    REPO_ROOT / "data" / "alpha_search" / "massive_asof_identity_readiness_20260728.json"
)
DATABASE = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
OUTPUT = (
    REPO_ROOT / "data" / "alpha_search" / "sec_selling_holder_overhang_roster_20260824.json"
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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            if raw.strip():
                rows.append(json.loads(raw))
    return rows


def load_membership(
    connection: sqlite3.Connection,
) -> list[tuple[datetime, str, frozenset[str]]]:
    audit = json.loads(IDENTITY_AUDIT.read_text(encoding="utf-8"))
    cutoffs = {
        date: datetime.fromisoformat(value.replace("Z", "+00:00"))
        for date, value in audit["decision_cutoff_utc_by_date"].items()
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


def build() -> dict[str, Any]:
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
        datetime.combine(datetime.fromisoformat(date).date(), time(9, 30), ny).astimezone(
            timezone.utc
        )
        for date in calendar
    ]
    closes = [
        datetime.combine(datetime.fromisoformat(date).date(), time(16, 0), ny).astimezone(
            timezone.utc
        )
        for date in calendar
    ]
    counts: Counter[str] = Counter()
    by_window: dict[str, Counter[str]] = defaultdict(Counter)
    candidates = []

    for row in load_jsonl(SOURCE_ROWS):
        window = str(row.get("window") or "unknown")
        counts["source_rows"] += 1
        by_window[window]["source_rows"] += 1
        if row.get("status") != "ok":
            counts["source_failed"] += 1
            by_window[window]["source_failed"] += 1
            continue
        if not row.get("selling_holder_present"):
            counts["not_selling_holder"] += 1
            by_window[window]["not_selling_holder"] += 1
            continue
        accepted = datetime.fromisoformat(str(row["accepted_at"]).replace("Z", "+00:00"))
        membership = [item for item in snapshots if item[0] <= accepted]
        if not membership or row.get("ticker") not in membership[-1][2]:
            counts["fails_exact_membership"] += 1
            by_window[window]["fails_exact_membership"] += 1
            continue
        entry_index = bisect.bisect_right(opens, accepted)
        completed_index = bisect.bisect_right(closes, accepted) - 1
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
                (row.get("ticker"), completed_date, LIQUIDITY_LOOKBACK),
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
            counts["fails_exact_liquidity_or_price"] += 1
            by_window[window]["fails_exact_liquidity_or_price"] += 1
            continue
        candidates.append(
            {
                "window": window,
                "ticker": row.get("ticker"),
                "accession": row.get("accession"),
                "form_type": row.get("form_type"),
                "accepted_at": row.get("accepted_at"),
                "entry_session": calendar[entry_index],
                "h10_exit_session": calendar[entry_index + HOLD_SESSIONS - 1],
                "membership_asof": membership[-1][1],
                "resale_vs_primary": row.get("resale_vs_primary"),
                "selling_holder_present": True,
                "registered_or_offering_amount_usd": row.get(
                    "registered_or_offering_amount_usd"
                ),
                "primary_document_sha256": row.get("primary_document_sha256"),
                "resale_evidence": row.get("resale_evidence"),
            }
        )

    connection.close()
    candidates.sort(key=lambda row: (row["entry_session"], row["accepted_at"], row["ticker"], row["accession"]))
    deduped = []
    seen_ticker_entry: set[tuple[str, str]] = set()
    for row in candidates:
        key = (str(row["ticker"]), str(row["entry_session"]))
        if key not in seen_ticker_entry:
            deduped.append(row)
            seen_ticker_entry.add(key)
        else:
            counts["same_ticker_entry_deduped"] += 1
            by_window[row["window"]]["same_ticker_entry_deduped"] += 1

    calendar_index = {date: index for index, date in enumerate(calendar)}
    rows = []
    last_entry: dict[str, int] = {}
    for row in deduped:
        ticker = str(row["ticker"])
        index = calendar_index[row["entry_session"]]
        if ticker in last_entry and index - last_entry[ticker] < COOLDOWN_SESSIONS:
            counts["cooldown_dropped"] += 1
            by_window[row["window"]]["cooldown_dropped"] += 1
            continue
        rows.append(row)
        last_entry[ticker] = index
        counts["roster_rows"] += 1
        by_window[row["window"]]["roster_rows"] += 1

    rows_by_date = Counter(row["entry_session"] for row in rows)
    return {
        "schema_version": 1,
        "record_type": "outcome_blind_sec_selling_holder_overhang_roster",
        "policy_version": "sec_selling_holder_overhang_h10_v1",
        "source_rows": SOURCE_ROWS.relative_to(REPO_ROOT).as_posix(),
        "source_rows_sha256": sha256_file(SOURCE_ROWS),
        "source_manifest": SOURCE_MANIFEST.relative_to(REPO_ROOT).as_posix(),
        "source_manifest_sha256": sha256_file(SOURCE_MANIFEST),
        "identity_audit": IDENTITY_AUDIT.relative_to(REPO_ROOT).as_posix(),
        "identity_audit_sha256": sha256_file(IDENTITY_AUDIT),
        "predicate": {
            "event": "parsed S-1/F-1 primary document has affirmative selling-holder resale evidence",
            "decision_clock": "SEC accepted_at",
            "entry": "first regular-session open strictly after accepted_at",
            "exit": "tenth session close counting entry",
            "membership": "latest known research-PIT active=true,type=CS snapshot",
            "liquidity_lookback": LIQUIDITY_LOOKBACK,
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_last_completed_close": MIN_CLOSE,
            "same_ticker_entry_dedup": "earliest accepted filing, then accession",
            "cooldown_sessions": COOLDOWN_SESSIONS,
        },
        "counts": dict(counts),
        "counts_by_window": {key: dict(value) for key, value in sorted(by_window.items())},
        "unique_tickers": len({row["ticker"] for row in rows}),
        "unique_entry_dates": len(rows_by_date),
        "max_rows_on_one_entry_date": max(rows_by_date.values(), default=0),
        "rows": rows,
        "outcome_fields_read": False,
        "post_decision_price_values_read": False,
        "trade_enabled": False,
    }


def main() -> int:
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
