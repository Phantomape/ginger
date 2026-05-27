from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path


EXPERIMENTS_DIR = Path(__file__).resolve().parent / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_023_kova_remaining_ohlcv_attributions import (  # noqa: E402
    BREAKOUT_HIGH_CLOSE_ONLY,
    BREAKOUT_NEITHER,
    BREAKOUT_STRONG,
    MA_ABOVE_50,
    MA_BULLISH,
    MA_UNAVAILABLE,
    WEEKLY_NOT_TIGHT,
    WEEKLY_TIGHT,
    compute_ma_structure_context,
    compute_signal_day_breakout_quality_context,
    compute_weekly_tightness_context,
)


def _daily_rows(
    closes: list[float],
    *,
    start: date = date(2026, 1, 1),
    volumes: list[float] | None = None,
) -> list[dict]:
    rows = []
    for idx, close in enumerate(closes):
        volume = volumes[idx] if volumes is not None else 1_000_000
        rows.append(
            {
                "Date": (start + timedelta(days=idx)).isoformat(),
                "Open": close,
                "High": close + 1.0,
                "Low": close - 1.0,
                "Close": close,
                "Volume": volume,
            }
        )
    return rows


def _trade(signal_date: str = "2026-01-21", **overrides):
    trade = {
        "ticker": "AAA",
        "signal_date": signal_date,
        "date": signal_date,
        "pnl": 0.0,
    }
    trade.update(overrides)
    return trade


def test_signal_day_breakout_quality_excludes_signal_volume_from_prior_average():
    closes = [100.0] * 21
    volumes = [100.0] * 20 + [130.0]
    context = compute_signal_day_breakout_quality_context(
        _daily_rows(closes, volumes=volumes),
        _trade(),
    )

    context_rows = _daily_rows(closes, volumes=volumes)
    context_rows[-1]["High"] = 101.0
    context_rows[-1]["Low"] = 99.0
    context_rows[-1]["Close"] = 100.75
    context = compute_signal_day_breakout_quality_context(context_rows, _trade())

    assert context["signal_day_breakout_quality_bucket_v1"] == BREAKOUT_STRONG
    assert context["signal_day_volume_ratio_20"] == 1.3
    assert context["signal_day_close_location"] == 0.875


def test_signal_day_high_close_without_volume_expansion_is_separate_bucket():
    rows = _daily_rows([100.0] * 21, volumes=[100.0] * 20 + [100.0])
    rows[-1]["High"] = 101.0
    rows[-1]["Low"] = 99.0
    rows[-1]["Close"] = 100.75

    context = compute_signal_day_breakout_quality_context(rows, _trade())

    assert context["signal_day_breakout_quality_bucket_v1"] == BREAKOUT_HIGH_CLOSE_ONLY


def test_signal_day_future_rows_do_not_affect_context():
    base_rows = _daily_rows([100.0] * 21, volumes=[100.0] * 20 + [100.0])
    future_rows = base_rows + _daily_rows(
        [200.0, 10.0],
        start=date(2026, 1, 22),
        volumes=[10_000.0, 10_000.0],
    )

    before = compute_signal_day_breakout_quality_context(base_rows, _trade())
    after = compute_signal_day_breakout_quality_context(future_rows, _trade())

    assert before["signal_day_breakout_quality_bucket_v1"] == BREAKOUT_NEITHER
    assert after["signal_day_breakout_quality_bucket_v1"] == BREAKOUT_NEITHER
    assert after["signal_day_volume_ratio_20"] == before["signal_day_volume_ratio_20"]


def test_weekly_tightness_uses_completed_weeks_and_excludes_signal_week():
    rows = []
    week_ends = [
        ("2025-12-05", 100.0),
        ("2025-12-12", 100.8),
        ("2025-12-19", 101.2),
        ("2025-12-26", 100.6),
        ("2026-01-02", 100.9),
    ]
    for idx, (row_date, close) in enumerate(week_ends):
        rows.append(
            {
                "Date": row_date,
                "Open": close,
                "High": close + 1.0,
                "Low": close - 1.0,
                "Close": close,
                "Volume": 1_000_000 + idx,
            }
        )
    rows.append(
        {
            "Date": "2026-01-05",
            "Open": 180.0,
            "High": 181.0,
            "Low": 179.0,
            "Close": 180.0,
            "Volume": 10_000_000,
        }
    )

    context = compute_weekly_tightness_context(rows, _trade("2026-01-06"))

    assert context["pre_signal_weekly_tightness_bucket_v1"] == WEEKLY_TIGHT
    assert context["three_week_tight_weekly_closes"][-1]["week_end_date"] == "2026-01-02"


def test_weekly_tightness_marks_wide_completed_weeks_not_tight():
    rows = []
    for row_date, close in [
        ("2025-12-05", 100.0),
        ("2025-12-12", 105.0),
        ("2025-12-19", 98.0),
        ("2025-12-26", 110.0),
        ("2026-01-02", 90.0),
    ]:
        rows.append(
            {
                "Date": row_date,
                "Open": close,
                "High": close + 1.0,
                "Low": close - 1.0,
                "Close": close,
                "Volume": 1_000_000,
            }
        )

    context = compute_weekly_tightness_context(rows, _trade("2026-01-06"))

    assert context["pre_signal_weekly_tightness_bucket_v1"] == WEEKLY_NOT_TIGHT


def test_ma_structure_uses_only_rows_before_signal_date():
    closes = [100.0 + idx * 0.5 for idx in range(60)]
    rows = _daily_rows(closes, start=date(2025, 11, 1))
    rows.append(
        {
            "Date": "2025-12-31",
            "Open": 1.0,
            "High": 2.0,
            "Low": 0.5,
            "Close": 1.0,
            "Volume": 10_000_000,
        }
    )

    context = compute_ma_structure_context(rows, _trade("2025-12-31"))

    assert context["pre_signal_ma_structure_bucket_v1"] == MA_BULLISH
    assert context["pre_signal_ma_asof_date"] == "2025-12-30"


def test_ma_structure_separates_above_50_without_full_stack():
    closes = [100.0] * 30 + [120.0] * 10 + [110.0] * 10
    context = compute_ma_structure_context(
        _daily_rows(closes, start=date(2025, 11, 1)),
        _trade("2025-12-21"),
    )

    assert context["pre_signal_ma_structure_bucket_v1"] == MA_ABOVE_50


def test_ma_structure_unavailable_with_less_than_50_prior_rows():
    context = compute_ma_structure_context(
        _daily_rows([100.0] * 10, start=date(2026, 1, 1)),
        _trade("2026-01-11"),
    )

    assert context["pre_signal_ma_structure_bucket_v1"] == MA_UNAVAILABLE
