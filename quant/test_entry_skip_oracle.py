import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from entry_skip_oracle import build_entry_skip_diagnostics  # noqa: E402


def test_entry_skip_oracle_groups_future_returns_by_decision(tmp_path):
    backtest = {
        "known_biases": {
            "ohlcv_source": {
                "snapshot_path": str(tmp_path / "snapshot.json"),
            }
        },
        "entry_execution_attribution": {
            "skipped_count": 2,
            "sample_skips": [
                {
                    "date": "2026-01-02",
                    "ticker": "AAA",
                    "strategy": "trend_long",
                    "decision": "gap_cancel",
                    "candidate_rank": 1,
                    "available_slots_at_entry_loop": 2,
                    "details": {
                        "fill_date": "2026-01-05",
                        "fill_price": 10.2,
                        "signal_entry": 10.0,
                    },
                },
                {
                    "date": "2026-01-02",
                    "ticker": "BBB",
                    "strategy": "breakout_long",
                    "decision": "no_shares",
                    "candidate_rank": 2,
                    "available_slots_at_entry_loop": 2,
                    "details": {},
                },
            ],
        },
    }
    snapshot = {
        "ohlcv": {
            "AAA": [
                {"Date": "2025-12-19", "Open": 9.0, "High": 9.5, "Close": 9.0, "Volume": 100},
                {"Date": "2025-12-22", "Open": 9.1, "High": 9.6, "Close": 9.1, "Volume": 100},
                {"Date": "2025-12-23", "Open": 9.2, "High": 9.7, "Close": 9.2, "Volume": 100},
                {"Date": "2025-12-24", "Open": 9.3, "High": 9.8, "Close": 9.3, "Volume": 100},
                {"Date": "2025-12-26", "Open": 9.4, "High": 9.9, "Close": 9.4, "Volume": 100},
                {"Date": "2025-12-29", "Open": 9.5, "High": 10.0, "Close": 9.5, "Volume": 100},
                {"Date": "2025-12-30", "Open": 9.6, "High": 10.1, "Close": 9.6, "Volume": 100},
                {"Date": "2025-12-31", "Open": 9.7, "High": 10.2, "Close": 9.7, "Volume": 100},
                {"Date": "2026-01-01", "Open": 9.8, "High": 10.3, "Close": 9.8, "Volume": 100},
                {"Date": "2026-01-02", "Open": 9.9, "High": 10.4, "Close": 10.0, "Volume": 300},
                {"Date": "2026-01-05", "Open": 10.0, "High": 12.0, "Close": 11.0, "Volume": 200},
                {"Date": "2026-01-06", "Open": 11.0, "High": 14.0, "Close": 13.0, "Volume": 200},
            ],
            "BBB": [
                {"Date": "2026-01-05", "Open": 20.0, "High": 20.5},
                {"Date": "2026-01-06", "Open": 20.1, "High": 21.0},
            ],
        }
    }
    backtest_path = tmp_path / "backtest.json"
    snapshot_path = tmp_path / "snapshot.json"
    backtest_path.write_text(json.dumps(backtest), encoding="utf-8")
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = build_entry_skip_diagnostics(backtest_path, horizon_days=2)
    oracle = result["entry_skip_oracle"]

    assert oracle["evaluated_skip_event_count"] == 2
    assert oracle["by_decision"]["gap_cancel"]["sample_count"] == 1
    assert oracle["by_decision"]["no_shares"]["sample_count"] == 1
    assert oracle["top_skipped_opportunities"][0]["ticker"] == "AAA"
    assert oracle["top_skipped_opportunities"][0]["decision"] == "gap_cancel"
    gap_audit = oracle["gap_cancel_audit"]
    assert gap_audit["sample_count"] == 1
    assert gap_audit["rows"][0]["gap_pct"] == 0.02
    assert gap_audit["rows"][0]["prior_5d_return_pct"] is not None
    assert gap_audit["rows"][0]["volume_vs_20d_avg"] is not None
    assert "context_summary" in gap_audit
    assert gap_audit["threshold_sweep"]["0.015"]["would_admit_count"] == 0
    assert gap_audit["threshold_sweep"]["0.020"]["would_admit_count"] == 1
