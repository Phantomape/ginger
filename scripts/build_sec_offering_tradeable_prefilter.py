"""Freeze an outcome-blind, pre-filing tradeability prefilter for S-1/F-1 text.

The filter exists only to avoid downloading thousands of IPO/SPAC filings that
could not have been traded in the historical replay. It reads no price after a
filing date and no return, PnL, outcome, or experiment result.
"""

from __future__ import annotations

import argparse
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
DEFAULT_EVENTS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
DEFAULT_DATABASE = REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"
DEFAULT_IDENTITY_AUDIT = (
    REPO_ROOT / "data" / "alpha_search" / "massive_asof_identity_readiness_20260728.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / "data" / "alpha_search" / "sec_offering_tradeable_prefilter_20260824.json"
)
WINDOWS = (
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
)
FORMS = {"S-1", "S-1/A", "F-1", "F-1/A"}
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0
MIN_CLOSE = 3.0
LIQUIDITY_LOOKBACK = 20


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


def window_of(date_text: str) -> str | None:
    value = str(date_text or "")[:10]
    for name, start, end in WINDOWS:
        if start <= value <= end:
            return name
    return None


def load_membership(
    connection: sqlite3.Connection, identity_audit: Path
) -> list[tuple[datetime, str, frozenset[str]]]:
    audit = json.loads(identity_audit.read_text(encoding="utf-8"))
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
        if as_of not in cutoffs:
            continue
        members = frozenset(
            row[0]
            for row in connection.execute(
                "SELECT ticker FROM instrument_master WHERE snapshot_key=?", (key,)
            )
        )
        snapshots.append((cutoffs[as_of], as_of, members))
    return snapshots


def latest_membership_before_date(
    snapshots: list[tuple[datetime, str, frozenset[str]]], filed_date: str
) -> tuple[str, frozenset[str]] | None:
    midnight = datetime.combine(
        datetime.fromisoformat(filed_date).date(),
        time(0, 0),
        ZoneInfo("America/New_York"),
    ).astimezone(timezone.utc)
    eligible = [item for item in snapshots if item[0] < midnight]
    return (eligible[-1][1], eligible[-1][2]) if eligible else None


def build(args: argparse.Namespace) -> dict[str, Any]:
    events_path = Path(args.events).resolve()
    database = Path(args.database).resolve()
    identity_audit = Path(args.identity_audit).resolve()
    connection = sqlite3.connect(str(database))
    snapshots = load_membership(connection, identity_audit)
    counts: Counter[str] = Counter()
    by_window: dict[str, Counter[str]] = defaultdict(Counter)
    selected = []
    seen: set[str] = set()

    for row in load_jsonl(events_path):
        accession = str(row.get("accession") or "")
        filed_date = str(row.get("filed_date") or "")[:10]
        window = window_of(filed_date)
        if (
            not accession
            or accession in seen
            or not window
            or row.get("ticker_status") != "resolved"
            or row.get("form_type") not in FORMS
        ):
            continue
        seen.add(accession)
        counts["eligible_index_rows"] += 1
        by_window[window]["eligible_index_rows"] += 1
        membership = latest_membership_before_date(snapshots, filed_date)
        if membership is None:
            counts["missing_prior_membership_snapshot"] += 1
            by_window[window]["missing_prior_membership_snapshot"] += 1
            continue
        membership_asof, members = membership
        ticker = str(row.get("ticker") or "")
        if ticker not in members:
            counts["not_prior_active_common_stock"] += 1
            by_window[window]["not_prior_active_common_stock"] += 1
            continue
        counts["prior_active_common_stock"] += 1
        by_window[window]["prior_active_common_stock"] += 1
        bars = list(
            connection.execute(
                "SELECT trade_date,close,vwap,volume FROM daily_bars "
                "WHERE ticker=? AND trade_date<? AND close>0 AND vwap>0 AND volume>0 "
                "ORDER BY trade_date DESC LIMIT ?",
                (ticker, filed_date, LIQUIDITY_LOOKBACK),
            )
        )
        if len(bars) < LIQUIDITY_LOOKBACK:
            counts["missing_prior_liquidity_history"] += 1
            by_window[window]["missing_prior_liquidity_history"] += 1
            continue
        median_dollar_volume = statistics.median(
            float(bar[2]) * float(bar[3]) for bar in bars
        )
        prior_close = float(bars[0][1])
        if median_dollar_volume < MIN_MEDIAN_DOLLAR_VOLUME or prior_close < MIN_CLOSE:
            counts["fails_prior_liquidity_or_price"] += 1
            by_window[window]["fails_prior_liquidity_or_price"] += 1
            continue
        counts["selected_rows"] += 1
        by_window[window]["selected_rows"] += 1
        selected.append(
            {
                **row,
                "prefilter_window": window,
                "prefilter_membership_asof": membership_asof,
                "prefilter_latest_completed_session": bars[0][0],
                "prefilter_rule_version": "sec_s1_f1_prior_tradeability_v1",
            }
        )

    connection.close()
    return {
        "schema_version": 1,
        "record_type": "outcome_blind_sec_offering_text_prefilter",
        "policy_version": "sec_s1_f1_prior_tradeability_v1",
        "source_events": events_path.relative_to(REPO_ROOT).as_posix(),
        "source_events_sha256": sha256_file(events_path),
        "identity_audit": identity_audit.relative_to(REPO_ROOT).as_posix(),
        "identity_audit_sha256": sha256_file(identity_audit),
        "warehouse": database.relative_to(REPO_ROOT).as_posix(),
        "predicate": {
            "membership": "latest research-PIT active=true,type=CS snapshot known strictly before filing-date midnight ET",
            "liquidity": "20 completed sessions strictly before filed_date",
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_prior_close": MIN_CLOSE,
            "forms": sorted(FORMS),
        },
        "counts": dict(counts),
        "counts_by_window": {key: dict(value) for key, value in sorted(by_window.items())},
        "unique_tickers": len({row.get("ticker") for row in selected}),
        "rows": selected,
        "outcome_fields_read": False,
        "post_filing_price_values_read": False,
        "trade_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default=str(DEFAULT_EVENTS))
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--identity-audit", default=str(DEFAULT_IDENTITY_AUDIT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    payload = build(args)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
