from pathlib import Path
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from market_state_analysis import build_market_state_snapshot  # noqa: E402
from report_generator import generate_daily_report  # noqa: E402


def test_market_state_snapshot_uses_existing_regime_and_sentiment_classifiers():
    snapshot = build_market_state_snapshot(
        market_context={
            "market_regime": "BULL",
            "spy_pct_from_ma": 0.03,
            "qqq_pct_from_ma": 0.05,
            "spy_10d_return": 0.02,
            "qqq_10d_return": 0.04,
            "spy_20d_return": 0.05,
            "qqq_20d_return": 0.10,
            "vix": 16,
        },
        signals=[
            {"strategy": "breakout_long", "sector": "Technology"},
            {"strategy": "breakout_long", "sector": "Technology"},
            {"strategy": "breakout_long", "sector": "Communication Services"},
        ],
        source="unit_test",
    )

    assert snapshot["read_only"] is True
    assert snapshot["diagnostic_only"] is True
    assert snapshot["source"] == "unit_test"
    assert snapshot["market_regime_report"]["regime"] == "theme_mania"
    assert snapshot["sentiment_surface"]["sentiment"] == "theme_mania"
    assert snapshot["signal_mix"]["breakout_signal_count"] == 3
    assert snapshot["signal_mix"]["theme_signal_count"] == 3
    assert "qqq_minus_spy_ret20" in snapshot["context_coverage"]["present_fields"]


def test_daily_report_surfaces_market_state_snapshot():
    snapshot = build_market_state_snapshot(
        market_context={
            "market_regime": "BULL",
            "spy_pct_from_ma": 0.03,
            "qqq_pct_from_ma": 0.05,
            "spy_10d_return": 0.02,
            "qqq_10d_return": 0.04,
            "spy_20d_return": 0.05,
            "qqq_20d_return": 0.10,
            "vix": 16,
        },
        signals=[
            {"strategy": "breakout_long", "sector": "Technology"},
            {"strategy": "breakout_long", "sector": "Technology"},
            {"strategy": "breakout_long", "sector": "Communication Services"},
        ],
        source="unit_test",
    )

    report = generate_daily_report(
        signals=[],
        market_state_snapshot=snapshot,
    )

    assert "MARKET STATE SNAPSHOT" in report
    assert "Regime engine: theme_mania" in report
    assert "Sentiment: theme_mania" in report
    assert "Signal mix: total=3 breakout=3 theme=3" in report
