import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from gap_cancel_context_replay import make_context_gap_cancel_predicate  # noqa: E402


def test_context_gap_cancel_predicate_relaxes_strong_non_high_gap():
    dates = pd.bdate_range("2026-01-01", periods=260)
    closes = [100.0] * 254 + [100.0, 105.0, 112.0, 125.0, 135.0, 150.0]
    df = pd.DataFrame({
        "Open": closes,
        "High": [200.0] * 260,
        "Low": closes,
        "Close": closes,
        "Volume": [1000] * 260,
    }, index=dates)
    pred = make_context_gap_cancel_predicate(
        base_threshold=0.015,
        relaxed_threshold=0.05,
        min_prior_5d_return=0.20,
        max_pct_from_252d_high=-0.05,
    )

    should_cancel = pred(
        103.0,
        100.0,
        sig={"ticker": "AAA"},
        today=dates[-1],
        ohlcv_all={"AAA": df},
    )

    assert should_cancel is False
    assert pred.stats["context_relaxed_count"] == 1


def test_context_gap_cancel_predicate_rejects_gap_near_high():
    dates = pd.bdate_range("2026-01-01", periods=260)
    closes = [100.0] * 254 + [100.0, 105.0, 112.0, 125.0, 135.0, 150.0]
    df = pd.DataFrame({
        "Open": closes,
        "High": [151.0] * 260,
        "Low": closes,
        "Close": closes,
        "Volume": [1000] * 260,
    }, index=dates)
    pred = make_context_gap_cancel_predicate(
        base_threshold=0.015,
        relaxed_threshold=0.05,
        min_prior_5d_return=0.20,
        max_pct_from_252d_high=-0.05,
    )

    should_cancel = pred(
        103.0,
        100.0,
        sig={"ticker": "AAA"},
        today=dates[-1],
        ohlcv_all={"AAA": df},
    )

    assert should_cancel is True
    assert pred.stats["context_rejected_count"] == 1
