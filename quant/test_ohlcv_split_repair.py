from __future__ import annotations

import sqlite3

import pandas as pd

from quant.ohlcv_split_repair import (
    ADJUSTMENT_TABLE,
    back_adjust_ticker,
    check_frames_against_warehouse,
    detect_frame_split,
    list_adjustments,
    scan_overlay_discontinuities,
)
from quant.ohlcv_warehouse import hot_path_for, upsert_ohlcv_frames


def _frame(days_closes: dict[str, float], volume: float = 1000.0) -> pd.DataFrame:
    index = pd.to_datetime(sorted(days_closes))
    closes = [days_closes[str(d.date())] for d in index]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": [volume] * len(closes),
        },
        index=index,
    )


def _closes(db_path, ticker: str) -> dict[str, float]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            str(day): float(close)
            for day, close in conn.execute(
                "SELECT date, close FROM ohlcv WHERE ticker = ? ORDER BY date",
                (ticker,),
            )
        }
    finally:
        conn.close()


def _volumes(db_path, ticker: str) -> dict[str, float]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            str(day): float(vol)
            for day, vol in conn.execute(
                "SELECT date, volume FROM ohlcv WHERE ticker = ? ORDER BY date",
                (ticker,),
            )
        }
    finally:
        conn.close()


# ---------------------------------------------------------------- detection


def test_detect_frame_split_forward() -> None:
    stored = {"2026-06-26": 740.0, "2026-06-29": 742.9}
    fetched = {"2026-06-26": 185.0, "2026-06-29": 185.7, "2026-06-30": 190.8}
    detection = detect_frame_split(stored, fetched)
    assert detection is not None
    assert detection["consistent"] is True
    assert detection["divisor"] == 4.0
    assert detection["kind"] == "split_4:1"
    assert detection["boundary_date"] == "2026-06-29"
    assert detection["mismatched_days"] == 2


def test_detect_frame_split_with_already_adjusted_suffix() -> None:
    # Stored rows after the split are already adjusted; only the prefix is stale.
    stored = {"2026-06-29": 742.9, "2026-06-30": 190.8}
    fetched = {"2026-06-29": 185.7, "2026-06-30": 190.8}
    detection = detect_frame_split(stored, fetched)
    assert detection is not None
    assert detection["consistent"] is True
    assert detection["boundary_date"] == "2026-06-29"


def test_detect_frame_split_reverse() -> None:
    stored = {"2026-06-26": 0.98, "2026-06-29": 1.02}
    fetched = {"2026-06-26": 9.8, "2026-06-29": 10.2}
    detection = detect_frame_split(stored, fetched)
    assert detection is not None
    assert detection["consistent"] is True
    assert detection["divisor"] == 1.0 / 10
    assert detection["kind"] == "reverse_10:1"


def test_detect_ignores_dividend_drift_and_matches_nothing_weird() -> None:
    # ~1% adjustment drift: not a discontinuity.
    assert detect_frame_split({"2026-06-29": 100.0}, {"2026-06-29": 99.1}) is None
    # A 37% real gap between stored and fetched matches no round factor:
    # reported but not consistent, so it can never auto-repair.
    detection = detect_frame_split(
        {"2026-06-26": 137.0, "2026-06-29": 137.0},
        {"2026-06-26": 100.0, "2026-06-29": 100.0},
    )
    assert detection is not None
    assert detection["consistent"] is False
    assert detection["divisor"] is None


def test_detect_mixed_factors_is_inconsistent() -> None:
    detection = detect_frame_split(
        {"2026-06-26": 400.0, "2026-06-29": 1000.0},
        {"2026-06-26": 100.0, "2026-06-29": 100.0},
    )
    assert detection is not None
    assert detection["consistent"] is False


# ------------------------------------------------------------- back-adjust


def _seed_split_db(tmp_path):
    """Cold tier with stale pre-split rows + hot tier with mixed rows."""
    cold = tmp_path / "warehouse.sqlite"
    hot = hot_path_for(cold)
    upsert_ohlcv_frames(
        cold,
        {"SPLT": _frame({"2026-06-25": 736.0, "2026-06-26": 740.0}, volume=1000.0)},
        source="test_cold",
    )
    upsert_ohlcv_frames(
        hot,
        {
            "SPLT": _frame(
                {"2026-06-29": 742.9, "2026-06-30": 190.8}, volume=1000.0
            )
        },
        source="test_hot",
    )
    return cold, hot


def test_back_adjust_updates_both_tiers_and_is_idempotent(tmp_path) -> None:
    cold, hot = _seed_split_db(tmp_path)
    result = back_adjust_ticker(
        cold, "SPLT", "2026-06-29", 4.0, detected_from="test", experiment="exp-test"
    )
    assert result["status"] == "applied"
    assert result["cold_rows_adjusted"] == 2
    assert result["hot_rows_adjusted"] == 1  # only the 06-29 stale hot row

    cold_closes = _closes(cold, "SPLT")
    hot_closes = _closes(hot, "SPLT")
    assert cold_closes["2026-06-25"] == 184.0
    assert cold_closes["2026-06-26"] == 185.0
    assert hot_closes["2026-06-29"] == 742.9 / 4.0
    assert hot_closes["2026-06-30"] == 190.8  # post-split row untouched
    assert _volumes(cold, "SPLT")["2026-06-25"] == 4000.0

    ledger = list_adjustments(cold)
    assert len(ledger) == 1
    assert ledger[0]["ticker"] == "SPLT"
    assert ledger[0]["experiment"] == "exp-test"

    again = back_adjust_ticker(cold, "SPLT", "2026-06-29", 4.0, detected_from="test")
    assert again["status"] == "already_applied"
    assert _closes(cold, "SPLT")["2026-06-25"] == 184.0  # never double-divided


def test_back_adjust_refuses_mixed_scale_history(tmp_path) -> None:
    cold = tmp_path / "warehouse.sqlite"
    # Boundary row is ALREADY at the adjusted scale: dividing again would be
    # wrong, and the continuity check against the post-boundary row catches it.
    upsert_ohlcv_frames(
        cold,
        {"MIXD": _frame({"2026-06-29": 185.7, "2026-06-30": 190.8})},
        source="test",
    )
    result = back_adjust_ticker(cold, "MIXD", "2026-06-29", 4.0, detected_from="test")
    assert result["status"] == "refused_inconsistent_boundary"
    assert _closes(cold, "MIXD")["2026-06-29"] == 185.7
    assert list_adjustments(cold) == []


def test_back_adjust_resumes_pending_hot_phase(tmp_path) -> None:
    cold, hot = _seed_split_db(tmp_path)
    result = back_adjust_ticker(cold, "SPLT", "2026-06-29", 4.0, detected_from="test")
    assert result["status"] == "applied"
    # Simulate a crash between the cold+ledger commit and the hot phase by
    # reverting the hot row and marking the ledger row pending.
    conn = sqlite3.connect(hot)
    conn.execute(
        "UPDATE ohlcv SET close = 742.9, open = 742.9, high = 742.9 * 1.01, "
        "low = 742.9 * 0.99, volume = 1000.0 WHERE ticker = 'SPLT' AND date = '2026-06-29'"
    )
    conn.commit()
    conn.close()
    conn = sqlite3.connect(cold)
    conn.execute(f"UPDATE {ADJUSTMENT_TABLE} SET hot_rows_adjusted = -1")
    conn.commit()
    conn.close()

    resumed = back_adjust_ticker(cold, "SPLT", "2026-06-29", 4.0, detected_from="test")
    assert resumed["status"] == "applied"
    assert resumed.get("resumed_hot_only") is True
    assert _closes(hot, "SPLT")["2026-06-29"] == 742.9 / 4.0
    # Cold untouched by the resume (would have been 46.25 if double-divided).
    assert _closes(cold, "SPLT")["2026-06-25"] == 184.0


# ----------------------------------------------------------- write-path guard


def test_check_frames_detects_and_repairs(tmp_path) -> None:
    cold, hot = _seed_split_db(tmp_path)
    fetched = {
        "SPLT": _frame(
            {
                "2026-06-26": 185.0,
                "2026-06-29": 742.9 / 4.0,
                "2026-06-30": 190.8,
                "2026-07-01": 195.0,
            },
            volume=4000.0,
        )
    }
    events = check_frames_against_warehouse(cold, fetched, repair=True)
    assert len(events) == 1
    assert events[0]["ticker"] == "SPLT"
    assert events[0]["repaired"] is True
    assert events[0]["boundary_date"] == "2026-06-29"
    assert _closes(cold, "SPLT")["2026-06-26"] == 185.0
    assert _closes(hot, "SPLT")["2026-06-29"] == 742.9 / 4.0

    # Clean state: no further events.
    assert check_frames_against_warehouse(cold, fetched, repair=True) == []


def test_check_frames_report_only_mode(tmp_path) -> None:
    cold, _hot = _seed_split_db(tmp_path)
    fetched = {"SPLT": _frame({"2026-06-25": 184.0, "2026-06-26": 185.0})}
    events = check_frames_against_warehouse(cold, fetched, repair=False)
    assert len(events) == 1
    assert events[0]["repaired"] is False
    assert _closes(cold, "SPLT")["2026-06-25"] == 736.0  # untouched


def test_check_frames_requires_min_overlap(tmp_path) -> None:
    cold, _hot = _seed_split_db(tmp_path)
    fetched = {"SPLT": _frame({"2026-06-26": 185.0, "2026-07-01": 195.0})}
    events = check_frames_against_warehouse(cold, fetched, repair=True)
    assert len(events) == 1
    assert events[0]["repaired"] is False
    assert events[0]["skip_reason"] == "insufficient_overlap_days"
    assert _closes(cold, "SPLT")["2026-06-26"] == 740.0


def test_check_frames_ignores_clean_series(tmp_path) -> None:
    cold = tmp_path / "warehouse.sqlite"
    upsert_ohlcv_frames(
        cold, {"OK": _frame({"2026-06-29": 100.0, "2026-06-30": 131.0})}, source="t"
    )
    fetched = {"OK": _frame({"2026-06-29": 100.0, "2026-06-30": 131.0, "2026-07-01": 129.0})}
    assert check_frames_against_warehouse(cold, fetched, repair=True) == []


# -------------------------------------------------------------------- scan


def test_scan_flags_cross_batch_round_factor_jump_only(tmp_path) -> None:
    cold = tmp_path / "warehouse.sqlite"
    # Stale pre-split rows written in one batch...
    upsert_ohlcv_frames(
        cold,
        {"SPLT": _frame({"2026-06-26": 740.0, "2026-06-29": 742.9}, volume=1000.0)},
        source="batch_a",
        fetched_at="2026-06-30T00:00:00+00:00",
    )
    # ...post-split rows written by a later batch.
    upsert_ohlcv_frames(
        cold,
        {"SPLT": _frame({"2026-06-30": 190.8, "2026-07-01": 195.0}, volume=3500.0)},
        source="batch_b",
        fetched_at="2026-07-02T00:00:00+00:00",
    )
    # A same-batch real crash must not be flagged (same updated_at).
    upsert_ohlcv_frames(
        cold,
        {"CRSH": _frame({"2026-06-29": 10.0, "2026-06-30": 5.0}, volume=1000.0)},
        source="batch_a",
        fetched_at="2026-06-30T00:00:00+00:00",
    )
    hits = scan_overlay_discontinuities(cold)
    assert [h["ticker"] for h in hits] == ["SPLT"]
    assert hits[0]["boundary_date"] == "2026-06-29"
    assert hits[0]["kind"] == "split_4:1"
    assert hits[0]["suggested_divisor"] == 4.0
