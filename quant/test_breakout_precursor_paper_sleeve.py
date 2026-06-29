"""Tests for exp-20260628-015 breakout-without-2x-volume precursor sleeve."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import breakout_precursor_paper_sleeve as bps  # noqa: E402


def _rising_bars(n=260, vol=1_000_000.0, spike_index=None, spike_mult=3.0):
    """Monotonically rising series: every bar past the 200-bar warmup is a
    breakout-above-200ma. Volume is flat so no bar is a volume_spike unless
    ``spike_index`` is set."""
    bars = []
    start = dt.date(2025, 1, 1)
    for k in range(n):
        close = 100.0 + k * 0.5
        volume = vol if spike_index != k else vol * spike_mult
        bars.append(
            (
                (start + dt.timedelta(days=k)).isoformat(),
                round(close - 0.2, 4),  # open
                round(close + 0.3, 4),  # high
                round(close - 0.5, 4),  # low
                round(close, 4),        # close
                volume,
            )
        )
    return bars


def test_rising_series_emits_precursors_with_forward_outcomes():
    bars = _rising_bars()
    events = bps.scan_ticker_precursors("TEST", bars)
    assert events, "rising breakout series should emit precursor events"
    # All emitted events satisfy the no-volume-spike condition.
    for e in events:
        assert e["precursor"]["volume_spike_ratio"] <= bps.VOL_SPIKE_MULT
        assert e["ticker"] == "TEST"
    # A mid-series event has both horizons settled with positive forward return.
    settled = [e for e in events if e["forward"]["status"] == "settled"]
    assert settled
    fully = [
        e
        for e in settled
        if all(
            e["forward"]["horizons"][str(h)]["status"] == "settled"
            for h in bps.FORWARD_HORIZONS
        )
    ]
    assert fully, "mid-series events should fully settle both horizons"
    sample = fully[0]
    for h in bps.FORWARD_HORIZONS:
        leg = sample["forward"]["horizons"][str(h)]
        assert leg["forward_net_return_pct"] > 0.0  # rising series, net of costs
        assert leg["forward_mae_pct"] is not None


def test_volume_spike_day_is_excluded():
    spike_k = 210
    bars = _rising_bars(spike_index=spike_k)
    spike_date = bars[spike_k][0]
    events = bps.scan_ticker_precursors("TEST", bars)
    signal_dates = {e["signal_date"] for e in events}
    assert spike_date not in signal_dates, "a >2x volume day is a trend_long, not a precursor"
    # The very next day is still a precursor (spike not in its forward window).
    assert bars[spike_k + 1][0] in signal_dates


def test_tail_events_are_unsettled():
    bars = _rising_bars(n=260)
    events = bps.scan_ticker_precursors("TEST", bars)
    last = max(events, key=lambda e: e["signal_date"])
    # The final signal day has no next-open/horizon bars -> not fully settled.
    assert last["forward"]["status"] != "settled" or any(
        last["forward"]["horizons"][str(h)]["status"] == "unsettled"
        for h in bps.FORWARD_HORIZONS
    )


def test_survivorship_subset_flag():
    bars = _rising_bars()
    actual_entry = bars[207][0]
    events = bps.scan_ticker_precursors(
        "TEST", bars, actual_entry_dates=[actual_entry]
    )
    matched = [e for e in events if e["became_trend_long_entry"]]
    assert matched, "a real entry within 5 sessions should mark the subset"
    assert all(
        e["matched_actual_entry_gap_sessions"] <= bps.ACTUAL_ENTRY_MATCH_MAX_GAP_SESSIONS
        for e in matched
    )
    assert any(e["matched_actual_entry_date"] == actual_entry for e in matched)
    # Far-away events are not falsely matched.
    assert any(not e["became_trend_long_entry"] for e in events)


def test_summary_separates_population_from_subset():
    bars = _rising_bars()
    actual_entry = bars[207][0]
    events = bps.scan_ticker_precursors(
        "TEST", bars, actual_entry_dates=[actual_entry]
    )
    summary = bps.summarize_events(events)
    assert summary["events_total"] == len(events)
    assert summary["events_became_actual_entry"] >= 1
    assert summary["forward_full_population"]["10d"]["n"] >= summary[
        "forward_actual_entry_subset"
    ]["10d"]["n"]


def test_idempotent_deterministic_scan():
    bars = _rising_bars()
    a = bps.scan_ticker_precursors("TEST", bars)
    b = bps.scan_ticker_precursors("TEST", bars)
    assert a == b


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
