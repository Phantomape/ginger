import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

if "yfinance" not in sys.modules:
    yf_stub = types.ModuleType("yfinance")
    yf_cache_stub = types.ModuleType("yfinance.cache")
    yf_stub.cache = yf_cache_stub
    sys.modules["yfinance"] = yf_stub
    sys.modules["yfinance.cache"] = yf_cache_stub

from backtester import _summarize_entry_decision_events  # noqa: E402


def test_summarize_entry_decision_events_counts_reasons_and_samples_skips():
    events = [
        {
            "date": "2026-01-02",
            "ticker": "AAA",
            "decision": "entered",
            "candidate_rank": 1,
        },
        {
            "date": "2026-01-02",
            "ticker": "BBB",
            "decision": "gap_cancel",
            "candidate_rank": 2,
        },
        {
            "date": "2026-01-03",
            "ticker": "CCC",
            "decision": "slot_sliced",
            "candidate_rank": 6,
        },
    ]

    summary = _summarize_entry_decision_events(events)

    assert summary["candidate_events"] == 3
    assert summary["entered_count"] == 1
    assert summary["skipped_count"] == 2
    assert summary["reason_counts"] == {
        "entered": 1,
        "gap_cancel": 1,
        "slot_sliced": 1,
    }
    assert summary["by_date"]["2026-01-02"] == {
        "entered": 1,
        "gap_cancel": 1,
    }
    assert [row["ticker"] for row in summary["sample_skips"]] == ["BBB", "CCC"]
