import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from earnings_replay import build_replayed_earnings_dict


def test_prefers_same_day_snapshot_future_event_for_dte():
    snapshots = {
        "20260601": {
            "META": {
                "next_earnings_date": "2026-06-15",
                "days_to_earnings": 99,  # stale vendor/display value; replay must recompute
                "eps_estimate": 5.25,
                "avg_historical_surprise_pct": 8.0,
            }
        }
    }

    out = build_replayed_earnings_dict(
        today=date(2026, 6, 1),
        calendar_dates=[date(2026, 6, 20)],
        ticker="META",
        earnings_snapshots=snapshots,
    )

    assert out["earnings_replay_source"] == "earnings_snapshot"
    assert out["next_earnings_date"] == "2026-06-15"
    assert out["days_to_earnings"] == 10
    assert out["eps_estimate"] == 5.25
    assert out["eps_estimate_pit_status"] == "snapshot_same_event"
    assert out["avg_historical_surprise_pct"] == 8.0


def test_blocks_eps_estimate_when_snapshot_event_is_not_replayed_event():
    snapshots = {
        "20260601": {
            "META": {
                # Snapshot is now pointing at a later event after a prior event rolled.
                "next_earnings_date": "2026-08-01",
                "eps_estimate": 6.10,
                "avg_historical_surprise_pct": 4.0,
            }
        }
    }

    out = build_replayed_earnings_dict(
        today=date(2026, 8, 2),
        calendar_dates=[date(2026, 8, 15)],
        ticker="META",
        earnings_snapshots=snapshots,
    )

    assert out["earnings_replay_source"] == "calendar_fallback"
    assert out["next_earnings_date"] == "2026-08-15"
    assert out["eps_estimate"] is None
    assert out["eps_estimate_pit_status"] == "blocked_event_mismatch"
    # Surprise history is already-known context and may still be attached.
    assert out["avg_historical_surprise_pct"] == 4.0


def test_calendar_fallback_when_no_snapshot_exists():
    out = build_replayed_earnings_dict(
        today=date(2026, 6, 1),
        calendar_dates=[date(2026, 6, 10)],
        ticker="AAPL",
        earnings_snapshots={},
    )

    assert out["earnings_replay_source"] == "calendar_fallback"
    assert out["next_earnings_date"] == "2026-06-10"
    assert out["days_to_earnings"] == 7
    assert out["eps_estimate"] is None
    assert out["earnings_event_match"] is None
