"""Outcome-blind forward readiness for the structured-news pair lead.

This observer measures whether one immutable local first-seen batch contains
diversified long/short candidate sets and point-in-time indicative borrow
coverage for every proposed short-side ticker.  It does not read settled
returns, emit signals, size paper positions, or create orders.  iBorrowDesk is
an indicative research surface, not a broker locate.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from data_paths import atomic_write_json, atomic_write_text


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = (
    REPO_ROOT / "data" / "non_ohlcv" / "news_propagation_pair_forward_readiness"
)
IBORROWDESK_HISTORY_DIR = REPO_ROOT / "data" / "non_ohlcv" / "iborrowdesk" / "history"

SCHEMA_VERSION = "news_propagation_pair_forward_readiness_v1"
EXPOSURE_SCHEMA_VERSION = "news_event_exposure_observation_v2"
LONG_POLARITY = "negative"
SHORT_POLARITY = "positive"
MAX_TICKER_ROW_WEIGHT = 0.40
MAX_BORROW_AGE_CALENDAR_DAYS = 3
# exp-20260923-004 borrow-coverage contract review: for batches first seen at
# or after the effective timestamp a short-side ticker without valid PIT
# borrow evidence is EXCLUDED and recorded (borrow_coverage.uncovered_tickers)
# instead of blocking the whole batch; the batch blocks only when no
# short-side ticker is covered.  Earlier batches keep the frozen v1
# semantics byte-for-byte (same record_id, same blockers, no new keys).
BORROW_COVERAGE_RULE_VERSION = "news_propagation_pair_borrow_coverage_v2"
BORROW_COVERAGE_RULE_EFFECTIVE_AT = "2026-09-23T17:00:00+00:00"
# exp-20260924-004 cross-side-overlap contract review: for batches first seen
# at or after the effective timestamp a ticker present on BOTH sides (one
# negative and one positive event of the same peer group in one batch) is
# EXCLUDED from both sides for readiness evaluation and recorded
# (overlap_exclusion) instead of blocking the whole batch; the concentration
# cap and the borrow coverage are evaluated on the residual sides and the
# batch blocks only when a side empties.  Earlier batches keep the frozen
# blocker byte-for-byte (same record_id, same blockers, no new keys).
OVERLAP_EXCLUSION_RULE_VERSION = "news_propagation_pair_cross_side_overlap_exclusion_v2"
OVERLAP_EXCLUSION_RULE_EFFECTIVE_AT = "2026-09-24T17:00:00+00:00"
NEW_YORK = ZoneInfo("America/New_York")


def _aware_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_iborrowdesk_histories(
    tickers: Iterable[str],
    *,
    history_dir: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    base = Path(history_dir) if history_dir else IBORROWDESK_HISTORY_DIR
    histories: dict[str, dict[str, Any]] = {}
    for ticker in sorted({str(value).upper() for value in tickers if value}):
        path = base / f"{ticker}.json"
        if path.exists():
            histories[ticker] = json.loads(path.read_text(encoding="utf-8"))
    return histories


def _borrow_as_of(
    ticker: str,
    first_seen: datetime,
    histories: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    history = histories.get(ticker) or histories.get(ticker.upper()) or {}
    rows = history.get("rows") or {}
    first_seen_date = first_seen.astimezone(NEW_YORK).date()
    candidates: list[tuple[str, Mapping[str, Any], datetime]] = []
    for row_date, row in rows.items():
        try:
            source_date = datetime.strptime(str(row_date), "%Y-%m-%d").date()
        except ValueError:
            continue
        archived_at = _aware_datetime(row.get("archived_at"))
        if (
            source_date <= first_seen_date
            and archived_at is not None
            and archived_at <= first_seen
        ):
            candidates.append((str(row_date), row, archived_at))
    if not candidates:
        return None, "missing_pit_borrow"

    row_date, row, archived_at = max(candidates, key=lambda item: (item[0], item[2]))
    age_days = (first_seen_date - datetime.strptime(row_date, "%Y-%m-%d").date()).days
    if age_days > MAX_BORROW_AGE_CALENDAR_DAYS:
        return None, "stale_pit_borrow"
    available = row.get("available")
    fee = row.get("fee")
    if not isinstance(available, (int, float)) or not math.isfinite(float(available)):
        return None, "invalid_pit_borrow"
    if float(available) <= 0:
        return None, "unavailable_pit_borrow"
    if not isinstance(fee, (int, float)) or not math.isfinite(float(fee)) or float(fee) < 0:
        return None, "invalid_pit_borrow"
    return {
        "ticker": ticker,
        "source_date": row_date,
        "archived_at": archived_at.isoformat(),
        "age_calendar_days": age_days,
        "available": available,
        "fee": fee,
        "source": "iborrowdesk_indicative_not_broker_locate",
    }, None


def _side_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    identities = {
        (str(row.get("event_id")), str(row.get("exposure_ticker")).upper())
        for row in rows
        if row.get("event_id") and row.get("exposure_ticker")
    }
    counts = Counter(ticker for _, ticker in identities)
    row_count = len(identities)
    max_weight = max(counts.values(), default=0) / row_count if row_count else None
    return {
        "row_count": row_count,
        "event_count": len({event_id for event_id, _ in identities}),
        "tickers": sorted(counts),
        "ticker_row_counts": dict(sorted(counts.items())),
        "max_ticker_row_weight": round(max_weight, 6) if max_weight is not None else None,
    }


def _residual_side(
    side: Mapping[str, Any], excluded: Iterable[str]
) -> dict[str, Any]:
    """Side summary restricted to tickers outside ``excluded`` (exp-20260924-004)."""
    dropped = set(excluded)
    counts = {
        ticker: count
        for ticker, count in (side.get("ticker_row_counts") or {}).items()
        if ticker not in dropped
    }
    row_count = sum(counts.values())
    max_weight = max(counts.values(), default=0) / row_count if row_count else None
    return {
        "ticker_count": len(counts),
        "row_count": row_count,
        "tickers": sorted(counts),
        "max_ticker_row_weight": round(max_weight, 6) if max_weight is not None else None,
    }


def build_readiness_records(
    exposure_rows: Iterable[Mapping[str, Any]],
    borrow_histories: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build deterministic readiness records without consulting outcomes."""
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in exposure_rows:
        if row.get("schema_version") != EXPOSURE_SCHEMA_VERSION:
            continue
        batch_id = row.get("first_seen_batch_id")
        first_seen = _aware_datetime(row.get("first_seen_at"))
        if not batch_id or first_seen is None:
            continue
        groups.setdefault(str(batch_id), []).append(row)

    records = []
    for batch_id, rows in sorted(groups.items()):
        first_seen_values = sorted({str(row.get("first_seen_at")) for row in rows})
        first_seen = _aware_datetime(first_seen_values[0])
        assert first_seen is not None
        long_side = _side_summary(
            row for row in rows if row.get("event_polarity") == LONG_POLARITY
        )
        short_side = _side_summary(
            row for row in rows if row.get("event_polarity") == SHORT_POLARITY
        )

        blockers: list[str] = []
        if len(first_seen_values) != 1:
            blockers.append("mixed_first_seen_at")
        if not long_side["row_count"]:
            blockers.append("missing_long_polarity")
        if not short_side["row_count"]:
            blockers.append("missing_short_polarity")
        overlap = sorted(set(long_side["tickers"]) & set(short_side["tickers"]))
        overlap_rule = first_seen >= _aware_datetime(
            OVERLAP_EXCLUSION_RULE_EFFECTIVE_AT
        )
        # exp-20260924-004: post-effective batches evaluate concentration and
        # borrow coverage on the residual sides (overlap tickers removed from
        # BOTH sides); pre-effective batches keep the frozen whole-batch blocker.
        long_eval: Mapping[str, Any] = long_side
        short_eval: Mapping[str, Any] = short_side
        overlap_exclusion: dict[str, Any] | None = None
        if overlap_rule:
            long_eval = _residual_side(long_side, overlap)
            short_eval = _residual_side(short_side, overlap)
            overlap_exclusion = {
                "rule_version": OVERLAP_EXCLUSION_RULE_VERSION,
                "excluded_tickers": overlap,
                "long_side_residual": {
                    key: long_eval[key]
                    for key in ("ticker_count", "row_count", "max_ticker_row_weight")
                },
                "short_side_residual": {
                    key: short_eval[key]
                    for key in ("ticker_count", "row_count", "max_ticker_row_weight")
                },
            }
            if long_side["row_count"] and not long_eval["row_count"]:
                blockers.append("long_side_emptied_by_overlap")
            if short_side["row_count"] and not short_eval["row_count"]:
                blockers.append("short_side_emptied_by_overlap")
        elif overlap:
            blockers.append("cross_side_ticker_overlap")
        if (
            long_eval["max_ticker_row_weight"] is not None
            and long_eval["max_ticker_row_weight"] > MAX_TICKER_ROW_WEIGHT
        ):
            blockers.append("long_side_concentration")
        if (
            short_eval["max_ticker_row_weight"] is not None
            and short_eval["max_ticker_row_weight"] > MAX_TICKER_ROW_WEIGHT
        ):
            blockers.append("short_side_concentration")

        exclusion_rule = first_seen >= _aware_datetime(
            BORROW_COVERAGE_RULE_EFFECTIVE_AT
        )
        borrow_evidence = []
        uncovered: list[dict[str, str]] = []
        for ticker in short_eval["tickers"]:
            evidence, blocker = _borrow_as_of(ticker, first_seen, borrow_histories)
            if blocker and exclusion_rule:
                uncovered.append({"ticker": ticker, "blocker": blocker})
            elif blocker:
                blockers.append(f"{blocker}:{ticker}")
            else:
                borrow_evidence.append(evidence)
        if exclusion_rule and short_eval["row_count"] and not borrow_evidence:
            blockers.append("short_side_no_borrow_coverage")
        borrow_coverage: dict[str, Any] = {
            "required_tickers": len(short_eval["tickers"]),
            "covered_tickers": len(borrow_evidence),
            "max_age_calendar_days": MAX_BORROW_AGE_CALENDAR_DAYS,
            "evidence": borrow_evidence,
            "is_broker_locate": False,
        }
        if exclusion_rule:
            borrow_coverage["coverage_rule_version"] = BORROW_COVERAGE_RULE_VERSION
            borrow_coverage["uncovered_tickers"] = uncovered

        record_id = "pair-ready-" + _stable_id(SCHEMA_VERSION, batch_id)[:24]
        record: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "record_id": record_id,
                "first_seen_batch_id": batch_id,
                "first_seen_at": first_seen_values[0],
                "status": "measurement_ready" if not blockers else "blocked",
                "blockers": sorted(set(blockers)),
                "long_side_polarity": LONG_POLARITY,
                "short_side_polarity": SHORT_POLARITY,
                "long_side": long_side,
                "short_side": short_side,
                "cross_side_ticker_overlap": overlap,
                "borrow_coverage": borrow_coverage,
                "max_ticker_row_weight": MAX_TICKER_ROW_WEIGHT,
                "pnl_measured": False,
                "strategy_behavior_changed": False,
                "trade_enabled": False,
                "signals": [],
                "order_intents": [],
                "orders": [],
        }
        if overlap_exclusion is not None:
            record["overlap_exclusion"] = overlap_exclusion
        records.append(record)
    return records


def build_snapshot(
    exposure_rows: Iterable[Mapping[str, Any]],
    borrow_histories: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    rows = list(exposure_rows)
    records = build_readiness_records(rows, borrow_histories)
    blocker_counts = Counter(
        blocker.split(":", 1)[0]
        for record in records
        for blocker in record["blockers"]
    )
    eligible_rows = sum(
        1
        for row in rows
        if row.get("schema_version") == EXPOSURE_SCHEMA_VERSION
        and _aware_datetime(row.get("first_seen_at")) is not None
        and row.get("first_seen_batch_id")
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of": max((record["first_seen_at"] for record in records), default=None),
        "batches": len(records),
        "measurement_ready_batches": sum(
            record["status"] == "measurement_ready" for record in records
        ),
        "blocked_batches": sum(record["status"] == "blocked" for record in records),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "first_seen_eligible_rows": eligible_rows,
        "legacy_or_ineligible_rows": len(rows) - eligible_rows,
        "records": records,
        "evidence_ceiling": "forward_measurement_readiness_only",
        "iborrowdesk_is_broker_locate": False,
        "pnl_measured": False,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "signals": [],
        "order_intents": [],
        "orders": [],
    }


def _persist(snapshot: Mapping[str, Any], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = out_dir / "readiness_decisions.jsonl"
    existing: list[dict[str, Any]] = []
    if decisions_path.exists():
        for line in decisions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing.append(json.loads(line))
    seen = {row.get("record_id") for row in existing}
    appended = 0
    for record in snapshot.get("records") or []:
        if record["record_id"] in seen:
            continue
        existing.append(record)
        seen.add(record["record_id"])
        appended += 1
    body = "\n".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) for row in existing
    )
    atomic_write_text(body + ("\n" if body else ""), decisions_path)
    atomic_write_json(dict(snapshot), out_dir / "latest_snapshot.json")
    return appended


def run(
    *,
    exposure_rows: Iterable[Mapping[str, Any]],
    borrow_histories: Mapping[str, Mapping[str, Any]] | None = None,
    history_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    rows = list(exposure_rows)
    short_tickers = {
        str(row.get("exposure_ticker")).upper()
        for row in rows
        if row.get("schema_version") == EXPOSURE_SCHEMA_VERSION
        and row.get("event_polarity") == SHORT_POLARITY
        and row.get("exposure_ticker")
    }
    histories = (
        borrow_histories
        if borrow_histories is not None
        else load_iborrowdesk_histories(short_tickers, history_dir=history_dir)
    )
    snapshot = build_snapshot(rows, histories)
    base = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    appended = _persist(snapshot, base)
    result = dict(snapshot)
    result["appended_this_run"] = appended
    result["decisions_path"] = str(base / "readiness_decisions.jsonl")
    result["latest_snapshot_path"] = str(base / "latest_snapshot.json")
    return result
