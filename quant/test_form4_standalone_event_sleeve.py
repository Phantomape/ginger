from __future__ import annotations

from quant.experiments.exp_20260503_052_form4_standalone_event_sleeve import (
    PRIMARY_HORIZON,
    _event_matches,
    _summarize_events,
    _variant_summary,
)


def _event(
    *,
    ticker: str = "ABC",
    window: str = "late_strong",
    value: float = 500_000.0,
    gross_return: float = 5.0,
    excess_return: float = 3.0,
    meaningful: bool = True,
) -> dict:
    return {
        "ticker": ticker,
        "window": window,
        "usable_trade_date": "2025-11-03",
        "meaningful_purchase_v1": meaningful,
        "total_purchase_value": value,
        "outcomes": {
            PRIMARY_HORIZON: {
                "return_pct": gross_return,
                "excess_vs_spy_pct": excess_return,
            }
        },
    }


def test_event_matches_requires_meaningful_and_min_purchase_value() -> None:
    assert _event_matches(_event(value=500_000.0), 500_000.0)
    assert not _event_matches(_event(value=499_999.0), 500_000.0)
    assert not _event_matches(_event(value=1_000_000.0, meaningful=False), 500_000.0)


def test_summary_applies_round_trip_cost_to_net_return() -> None:
    summary = _summarize_events([
        _event(gross_return=5.0, excess_return=2.0),
        _event(ticker="XYZ", gross_return=-1.0, excess_return=-2.0),
    ])

    assert summary["event_count"] == 2
    assert summary["valid_event_count"] == 2
    assert summary["avg_gross_return_pct"] == 2.0
    assert summary["avg_net_return_pct"] == 1.65
    assert summary["win_rate_net"] == 0.5
    assert summary["avg_excess_vs_spy_pct"] == 0.0


def test_variant_summary_marks_all_valid_windows_positive() -> None:
    events = [
        _event(window="late_strong", excess_return=1.0),
        _event(window="mid_weak", ticker="DEF", excess_return=2.0),
        _event(window="old_thin", ticker="GHI", excess_return=0.5),
    ]

    summary = _variant_summary(events, 500_000.0)

    assert summary["aggregate"]["windows_with_valid_events"] == 3
    assert summary["aggregate"]["positive_excess_windows"] == 3
    assert summary["aggregate"]["all_valid_windows_positive"] is True
