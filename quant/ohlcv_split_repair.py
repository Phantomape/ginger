"""Split-discontinuity detection and back-adjustment for the OHLCV warehouse.

exp-20260709-008: the warehouse freezes stored rows (``update_existing=False``
everywhere on the daily path), so when a ticker splits after its rows were
written, later vendor fetches (auto-adjusted) insert post-split-scale rows next
to frozen pre-split-scale history. The discontinuity is permanent and corrupts
returns/ATR/drawdown for every consumer of ``ohlcv_overlay`` (first cases:
KLAC 10:1 effective 2026-06-12, CRWD 4:1 effective 2026-07-02).

Three surfaces:

- ``detect_frame_split`` / ``check_frames_against_warehouse``: write-path guard.
  Fetched frames overlap already-stored dates (the refresh pads its lookback),
  so a stale tier shows a *constant round-factor ratio on identical dates* —
  much stronger evidence than jump heuristics, and immune to real moves.
- ``back_adjust_ticker``: divide OHLC and multiply volume by the split divisor
  for every stored row at or before the boundary date, in both tiers, and
  record the repair in a ``split_adjustments`` ledger table (cold DB) so the
  operation is idempotent and auditable.
- ``scan_overlay_discontinuities``: standing audit — cross-write-batch close
  jumps that match a round factor with a consistent volume move. Same-batch
  jumps are vendor-consistent by construction and are never flagged.

Deliberately NOT touched: the deterministic snapshot JSON files, the
``ohlcv_snapshot_versions`` table (fixed-window replay contract), and the
``source`` column of adjusted rows. If a repaired ticker ever appears in a
snapshot file, re-seeding would regress the repaired window — the ledger table
plus ``scan`` exists to catch that; as of 2026-07-09 no repaired ticker is in
any snapshot.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

try:
    from ohlcv_warehouse import (
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
    )
except ImportError:  # pragma: no cover - package-style imports for tests
    from quant.ohlcv_warehouse import (
        DEFAULT_WAREHOUSE_PATH,
        connect_overlay_reader,
        hot_path_for,
    )

log = logging.getLogger(__name__)

# Same generous busy timeout as ohlcv_warehouse: concurrent agent runs hold
# the warehouse open and a default-timeout write would fail instantly.
_BUSY_TIMEOUT_S = 60.0

ADJUSTMENT_TABLE = "split_adjustments"
# Round split factors seen in US equities; forward (price/k) and reverse (price*k).
ROUND_FACTORS = (2, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 50)
# Per-day tolerance for stored/fetched close ratio against a candidate factor.
# Overlap-day comparison has no market-move component (same date on both
# sides), so this can be tight; vendor dividend-adjustment drift is ~1-3% and
# never reaches the nearest candidate (2x).
FACTOR_TOLERANCE = 0.02
# The jump scan compares CONSECUTIVE days, so a real one-day move rides on top
# of the split ratio (CRWD's actual boundary jump was 2.7% off exact 4:1).
SCAN_FACTOR_TOLERANCE = 0.06
# Auto-repair needs at least this many overlapping days agreeing on one factor.
MIN_OVERLAP_DAYS = 2
# Sanity band when comparing the adjusted boundary close against the first
# post-boundary close: allows a real market move across the boundary gap.
BOUNDARY_CONTINUITY_TOLERANCE = 0.35
# scan: minimum single-day move to consider at all.
SCAN_JUMP_THRESHOLD = 0.30
# scan: ignore sub-dollar rows — tick-size noise matches 2:1 constantly.
SCAN_MIN_PREV_CLOSE = 1.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_adjustment_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ADJUSTMENT_TABLE} (
            ticker TEXT NOT NULL,
            boundary_date TEXT NOT NULL,
            price_divisor REAL NOT NULL,
            volume_multiplier REAL NOT NULL,
            detected_from TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            experiment TEXT,
            note TEXT,
            cold_rows_adjusted INTEGER NOT NULL,
            hot_rows_adjusted INTEGER NOT NULL,
            PRIMARY KEY (ticker, boundary_date)
        )
        """
    )


def list_adjustments(
    cold_path: str | Path = DEFAULT_WAREHOUSE_PATH,
) -> list[dict[str, Any]]:
    cold = Path(cold_path)
    if not cold.exists():
        return []
    conn = sqlite3.connect(cold, timeout=_BUSY_TIMEOUT_S)
    try:
        _ensure_adjustment_table(conn)
        rows = conn.execute(
            f"""
            SELECT ticker, boundary_date, price_divisor, volume_multiplier,
                   detected_from, applied_at, experiment, note,
                   cold_rows_adjusted, hot_rows_adjusted
            FROM {ADJUSTMENT_TABLE}
            ORDER BY ticker, boundary_date
            """
        ).fetchall()
    finally:
        conn.close()
    keys = (
        "ticker",
        "boundary_date",
        "price_divisor",
        "volume_multiplier",
        "detected_from",
        "applied_at",
        "experiment",
        "note",
        "cold_rows_adjusted",
        "hot_rows_adjusted",
    )
    return [dict(zip(keys, row)) for row in rows]


def _match_round_factor(
    ratio: float, tolerance: float = FACTOR_TOLERANCE
) -> tuple[float, str] | None:
    """Match a stored/fetched close ratio to a round split divisor.

    Returns ``(divisor, kind)`` where dividing stored prices by ``divisor``
    (and multiplying volume by it) restores consistency with the fetched
    (adjusted) scale. Forward k:1 split -> divisor k; reverse 1:k -> 1/k.
    """
    best: tuple[float, str, float] | None = None
    for k in ROUND_FACTORS:
        for divisor, kind in ((float(k), f"split_{k}:1"), (1.0 / k, f"reverse_{k}:1")):
            err = abs(ratio / divisor - 1.0)
            if err < tolerance and (best is None or err < best[2]):
                best = (divisor, kind, err)
    if best is None:
        return None
    return best[0], best[1]


def detect_frame_split(
    stored_closes: Mapping[str, float],
    fetched_closes: Mapping[str, float],
) -> dict[str, Any] | None:
    """Compare stored vs freshly fetched closes on identical dates.

    Expects the stale pattern: every common date up to some boundary shows the
    same round-factor ratio, and any common dates after the boundary match
    ~1:1 (rows written post-split are already adjusted). Mixed/non-monotone
    patterns are reported with ``consistent=False`` and must not be auto-fixed.
    """
    common = sorted(set(stored_closes) & set(fetched_closes))
    per_day: list[tuple[str, float, tuple[float, str] | None]] = []
    for day in common:
        stored = float(stored_closes[day])
        fetched = float(fetched_closes[day])
        if stored <= 0 or fetched <= 0:
            continue
        ratio = stored / fetched
        if abs(ratio - 1.0) <= FACTOR_TOLERANCE:
            per_day.append((day, ratio, (1.0, "unchanged")))
        else:
            per_day.append((day, ratio, _match_round_factor(ratio)))
    if not per_day:
        return None

    mismatched = [
        (day, ratio, match)
        for day, ratio, match in per_day
        if match is None or match[0] != 1.0
    ]
    if not mismatched:
        return None

    factors = {match[1] for _day, _ratio, match in mismatched if match is not None}
    unmatched_days = [day for day, _ratio, match in mismatched if match is None]
    boundary = max(day for day, _ratio, _match in mismatched)
    # every day <= boundary must mismatch with the SAME factor, and every day
    # after must be unchanged, otherwise the stored state is mixed.
    consistent = not unmatched_days and len(factors) == 1
    if consistent:
        for day, _ratio, match in per_day:
            expected_unchanged = day > boundary
            is_unchanged = match is not None and match[0] == 1.0
            if expected_unchanged != is_unchanged:
                consistent = False
                break
    divisor = None
    kind = None
    if not unmatched_days and len(factors) == 1:
        first = next(m for _d, _r, m in mismatched if m is not None)
        divisor, kind = first
    return {
        "boundary_date": boundary,
        "divisor": divisor,
        "kind": kind,
        "consistent": consistent,
        "mismatched_days": len(mismatched),
        "overlap_days": len(per_day),
        "unmatched_days": unmatched_days,
        "ratios": {day: round(ratio, 6) for day, ratio, _match in per_day},
    }


def back_adjust_ticker(
    cold_path: str | Path,
    ticker: str,
    boundary_date: str,
    divisor: float,
    *,
    hot_path: str | Path | None = None,
    detected_from: str = "manual",
    experiment: str | None = None,
    note: str | None = None,
    expected_adjusted_close: float | None = None,
) -> dict[str, Any]:
    """Back-adjust all stored rows at or before ``boundary_date`` in both tiers.

    OHLC are divided by ``divisor`` and volume multiplied by it, restoring the
    vendor's post-split adjusted scale. The repair is recorded in the
    ``split_adjustments`` ledger (cold DB); a second call with the same
    ``(ticker, boundary_date)`` is refused so re-runs can never double-divide.

    ``expected_adjusted_close``: adjusted-scale close near the boundary (from
    the first post-boundary stored row when omitted). The boundary row divided
    by ``divisor`` must land within ``BOUNDARY_CONTINUITY_TOLERANCE`` of it —
    a mixed-scale history fails this and the repair is refused.
    """
    cold = Path(cold_path)
    hot = Path(hot_path) if hot_path is not None else hot_path_for(cold)
    ticker = str(ticker).upper().strip()
    boundary_date = str(boundary_date)[:10]
    divisor = float(divisor)
    if divisor <= 0 or abs(divisor - 1.0) < 1e-9:
        raise ValueError(f"invalid split divisor {divisor}")
    now = _utc_now()

    update_sql = (
        "UPDATE ohlcv SET open = open / :d, high = high / :d, "
        "low = low / :d, close = close / :d, volume = volume * :d, "
        "updated_at = :now WHERE ticker = :ticker AND date <= :boundary"
    )
    params = {"d": divisor, "now": now, "ticker": ticker, "boundary": boundary_date}

    def _adjust_hot() -> int:
        if not hot.exists():
            return 0
        hot_conn = sqlite3.connect(hot, timeout=_BUSY_TIMEOUT_S)
        try:
            cur = hot_conn.execute(update_sql, params)
            count = int(cur.rowcount or 0)
            hot_conn.commit()
            return count
        except sqlite3.Error:
            hot_conn.rollback()
            raise
        finally:
            hot_conn.close()

    cold_conn = sqlite3.connect(cold, timeout=_BUSY_TIMEOUT_S)
    try:
        _ensure_adjustment_table(cold_conn)
        existing = cold_conn.execute(
            f"SELECT price_divisor, applied_at, hot_rows_adjusted FROM {ADJUSTMENT_TABLE} "
            "WHERE ticker = ? AND boundary_date = ?",
            (ticker, boundary_date),
        ).fetchone()
        if existing is not None:
            # hot_rows_adjusted = -1 marks a repair that committed cold+ledger
            # but died before the hot tier was adjusted: resume hot-only. Any
            # other value means the repair completed — never divide twice.
            if int(existing[2]) == -1 and abs(float(existing[0]) - divisor) < 1e-9:
                hot_count = _adjust_hot()
                cold_conn.execute(
                    f"UPDATE {ADJUSTMENT_TABLE} SET hot_rows_adjusted = ?, note = "
                    "COALESCE(note, '') || ' [hot resumed ' || ? || ']' "
                    "WHERE ticker = ? AND boundary_date = ?",
                    (hot_count, now, ticker, boundary_date),
                )
                cold_conn.commit()
                return {
                    "status": "applied",
                    "resumed_hot_only": True,
                    "ticker": ticker,
                    "boundary_date": boundary_date,
                    "price_divisor": divisor,
                    "applied_at": now,
                    "cold_rows_adjusted": 0,
                    "hot_rows_adjusted": hot_count,
                }
            return {
                "status": "already_applied",
                "ticker": ticker,
                "boundary_date": boundary_date,
                "price_divisor": existing[0],
                "applied_at": existing[1],
                "cold_rows_adjusted": 0,
                "hot_rows_adjusted": 0,
            }

        boundary_close_row = cold_conn.execute(
            "SELECT close FROM ohlcv WHERE ticker = ? AND date <= ? "
            "ORDER BY date DESC LIMIT 1",
            (ticker, boundary_date),
        ).fetchone()
        if expected_adjusted_close is None:
            overlay = connect_overlay_reader(cold)
            try:
                post = overlay.execute(
                    "SELECT close FROM ohlcv_overlay WHERE ticker = ? AND date > ? "
                    "ORDER BY date ASC LIMIT 1",
                    (ticker, boundary_date),
                ).fetchone()
            finally:
                overlay.close()
            expected_adjusted_close = float(post[0]) if post else None
        if boundary_close_row is not None and expected_adjusted_close:
            implied = float(boundary_close_row[0]) / divisor
            drift = abs(implied / float(expected_adjusted_close) - 1.0)
            if drift > BOUNDARY_CONTINUITY_TOLERANCE:
                return {
                    "status": "refused_inconsistent_boundary",
                    "ticker": ticker,
                    "boundary_date": boundary_date,
                    "price_divisor": divisor,
                    "implied_adjusted_close": implied,
                    "expected_adjusted_close": expected_adjusted_close,
                    "drift": drift,
                    "cold_rows_adjusted": 0,
                    "hot_rows_adjusted": 0,
                }

        # Phase 1 (atomic): adjust cold and write the ledger row in one
        # transaction, with hot marked pending (-1). If this fails nothing
        # changed; once it commits a re-run can only resume the hot phase.
        adjusted_counts: dict[str, int] = {"cold": 0, "hot": 0}
        cur = cold_conn.execute(update_sql, params)
        adjusted_counts["cold"] = int(cur.rowcount or 0)
        cold_conn.execute(
            f"""
            INSERT INTO {ADJUSTMENT_TABLE} (
                ticker, boundary_date, price_divisor, volume_multiplier,
                detected_from, applied_at, experiment, note,
                cold_rows_adjusted, hot_rows_adjusted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, -1)
            """,
            (
                ticker,
                boundary_date,
                divisor,
                divisor,
                detected_from,
                now,
                experiment,
                note,
                adjusted_counts["cold"],
            ),
        )
        cold_conn.commit()
        # Phase 2: adjust hot, then finalize the ledger row.
        adjusted_counts["hot"] = _adjust_hot()
        cold_conn.execute(
            f"UPDATE {ADJUSTMENT_TABLE} SET hot_rows_adjusted = ? "
            "WHERE ticker = ? AND boundary_date = ?",
            (adjusted_counts["hot"], ticker, boundary_date),
        )
        cold_conn.commit()
    except Exception:
        cold_conn.rollback()
        raise
    finally:
        cold_conn.close()

    log.warning(
        "split back-adjustment applied: %s rows<=%s divided by %s "
        "(cold=%d hot=%d, detected_from=%s)",
        ticker,
        boundary_date,
        divisor,
        adjusted_counts["cold"],
        adjusted_counts["hot"],
        detected_from,
    )
    return {
        "status": "applied",
        "ticker": ticker,
        "boundary_date": boundary_date,
        "price_divisor": divisor,
        "volume_multiplier": divisor,
        "detected_from": detected_from,
        "applied_at": now,
        "cold_rows_adjusted": adjusted_counts["cold"],
        "hot_rows_adjusted": adjusted_counts["hot"],
    }


def check_frames_against_warehouse(
    cold_path: str | Path,
    frames_by_ticker: Mapping[str, pd.DataFrame | None],
    *,
    repair: bool = True,
    detected_from: str = "refresh_overlap_guard",
    experiment: str | None = None,
) -> list[dict[str, Any]]:
    """Write-path guard: compare fetched frames against stored overlay closes.

    Returns one event dict per ticker with a detected discontinuity. With
    ``repair=True`` a consistent detection is immediately back-adjusted in both
    tiers (rare — one split per universe ticker per multi-year stretch — so the
    cold-blob LFS churn of an in-place update is accepted; a corrupt series is
    strictly worse). Inconsistent/mixed detections are reported only.
    """
    cold = Path(cold_path)
    events: list[dict[str, Any]] = []
    items = [
        (str(t).upper().strip(), f)
        for t, f in frames_by_ticker.items()
        if f is not None and not getattr(f, "empty", True)
    ]
    if not items or not (cold.exists() or hot_path_for(cold).exists()):
        return events

    # Phase 1: detect while holding only the read connection. Repairs open
    # write connections to both tiers, so they must run after the overlay
    # reader is closed or the cold DB stays read-locked.
    detections: list[tuple[str, dict[str, Any], dict[str, float]]] = []
    overlay = connect_overlay_reader(cold)
    try:
        for ticker, frame in items:
            dates: list[str] = []
            fetched: dict[str, float] = {}
            for day, row in frame.iterrows():
                day_text = str(day)[:10]
                close = row.get("Close") if "Close" in row else row.get("close")
                try:
                    close_f = float(close)
                except (TypeError, ValueError):
                    continue
                if close_f > 0:
                    dates.append(day_text)
                    fetched[day_text] = close_f
            if not dates:
                continue
            placeholders = ",".join("?" for _ in dates)
            stored = {
                str(day)[:10]: float(close)
                for day, close in overlay.execute(
                    f"SELECT date, close FROM ohlcv_overlay "
                    f"WHERE ticker = ? AND date IN ({placeholders})",
                    (ticker, *dates),
                )
                if close is not None and float(close) > 0
            }
            detection = detect_frame_split(stored, fetched)
            if detection is not None:
                detections.append((ticker, detection, fetched))
    finally:
        overlay.close()

    # Phase 2: repair.
    for ticker, detection, fetched in detections:
        event: dict[str, Any] = {"ticker": ticker, **detection, "repaired": False}
        if (
            repair
            and detection["consistent"]
            and detection["divisor"] is not None
            and detection["mismatched_days"] >= MIN_OVERLAP_DAYS
        ):
            boundary = detection["boundary_date"]
            result = back_adjust_ticker(
                cold,
                ticker,
                boundary,
                detection["divisor"],
                detected_from=detected_from,
                experiment=experiment,
                note=f"auto-detected on refresh overlap ({detection['kind']})",
                expected_adjusted_close=fetched.get(boundary),
            )
            event["repair_result"] = result
            event["repaired"] = result.get("status") == "applied"
        elif detection["consistent"] and detection["mismatched_days"] < MIN_OVERLAP_DAYS:
            event["skip_reason"] = "insufficient_overlap_days"
        elif not detection["consistent"]:
            event["skip_reason"] = "mixed_or_unmatched_ratios"
        events.append(event)
    return events


def scan_overlay_discontinuities(
    cold_path: str | Path = DEFAULT_WAREHOUSE_PATH,
) -> list[dict[str, Any]]:
    """Standing audit: cross-write-batch round-factor close jumps in the overlay.

    Same-``updated_at`` neighbours were written by one vendor fetch and are
    internally consistent whatever the market did, so only jumps across write
    batches can be frozen-tier artifacts. Volume must move consistently with a
    share-count change (loose bands — daily volume is noisy).
    """
    conn = connect_overlay_reader(cold_path)
    sql = """
    WITH seq AS (
        SELECT ticker, date, close, volume, source, updated_at,
               LAG(date)       OVER w AS prev_date,
               LAG(close)      OVER w AS prev_close,
               LAG(volume)     OVER w AS prev_volume,
               LAG(source)     OVER w AS prev_source,
               LAG(updated_at) OVER w AS prev_updated_at
        FROM ohlcv_overlay
        WINDOW w AS (PARTITION BY ticker ORDER BY date)
    )
    SELECT ticker, prev_date, date, prev_close, close, prev_volume, volume,
           prev_source, source, prev_updated_at, updated_at
    FROM seq
    WHERE prev_close IS NOT NULL AND prev_close >= ? AND close > 0
      AND (close / prev_close > 1.0 + ? OR close / prev_close < 1.0 / (1.0 + ?))
      AND prev_updated_at != updated_at
    ORDER BY ticker, date
    """
    try:
        rows = conn.execute(
            sql, (SCAN_MIN_PREV_CLOSE, SCAN_JUMP_THRESHOLD, SCAN_JUMP_THRESHOLD)
        ).fetchall()
    finally:
        conn.close()

    hits: list[dict[str, Any]] = []
    for (
        ticker,
        prev_date,
        date,
        prev_close,
        close,
        prev_volume,
        volume,
        prev_source,
        source,
        prev_updated_at,
        updated_at,
    ) in rows:
        ratio = float(close) / float(prev_close)
        # jump ratio down (price/k) matches divisor k; the stored *older* side
        # is the stale one, so the repair divisor equals 1/ratio's match.
        match = _match_round_factor(1.0 / ratio, SCAN_FACTOR_TOLERANCE)
        if match is None:
            continue
        divisor, kind = match
        vol_ratio = (
            float(volume) / float(prev_volume) if prev_volume else None
        )
        if vol_ratio is not None:
            if kind.startswith("split") and not vol_ratio > divisor * 0.25:
                continue
            if kind.startswith("reverse") and not vol_ratio < 4.0 * divisor:
                continue
        hits.append(
            {
                "ticker": str(ticker),
                "prev_date": str(prev_date),
                "boundary_date": str(prev_date),
                "date": str(date),
                "prev_close": float(prev_close),
                "close": float(close),
                "ratio": round(ratio, 6),
                "kind": kind,
                "suggested_divisor": divisor,
                "vol_ratio": round(vol_ratio, 4) if vol_ratio is not None else None,
                "prev_source": str(prev_source),
                "source": str(source),
                "prev_updated_at": str(prev_updated_at),
                "updated_at": str(updated_at),
            }
        )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and repair unadjusted split discontinuities in the OHLCV warehouse."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="Audit the overlay for cross-batch split artifacts.")
    scan.add_argument("--db", default=str(DEFAULT_WAREHOUSE_PATH))
    apply_p = sub.add_parser("apply", help="Back-adjust one ticker across a split boundary.")
    apply_p.add_argument("--db", default=str(DEFAULT_WAREHOUSE_PATH))
    apply_p.add_argument("--ticker", required=True)
    apply_p.add_argument("--boundary", required=True, help="Last stored date at the OLD (pre-split) scale, YYYY-MM-DD.")
    apply_p.add_argument("--divisor", required=True, type=float, help="Price divisor; >1 forward split, <1 reverse.")
    apply_p.add_argument("--experiment", default=None)
    apply_p.add_argument("--note", default=None)
    list_p = sub.add_parser("list", help="Show applied split adjustments.")
    list_p.add_argument("--db", default=str(DEFAULT_WAREHOUSE_PATH))
    args = parser.parse_args()

    if args.command == "scan":
        hits = scan_overlay_discontinuities(args.db)
        print(json.dumps({"count": len(hits), "hits": hits}, indent=2, sort_keys=True))
        return 0
    if args.command == "apply":
        result = back_adjust_ticker(
            args.db,
            args.ticker,
            args.boundary,
            args.divisor,
            detected_from="manual_cli",
            experiment=args.experiment,
            note=args.note,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") in ("applied", "already_applied") else 1
    if args.command == "list":
        print(json.dumps(list_adjustments(args.db), indent=2, sort_keys=True))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
