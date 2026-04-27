import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUANT = ROOT / "quant"
if str(QUANT) not in sys.path:
    sys.path.insert(0, str(QUANT))

from gap_cancel_threshold_sweep import _compact_result  # noqa: E402


def test_compact_result_includes_entry_reason_counts():
    result = {
        "period": "2026-01-01 -> 2026-01-31",
        "total_trades": 3,
        "win_rate": 0.6667,
        "total_pnl": 1234.56,
        "sharpe": 1.2,
        "sharpe_daily": 0.9,
        "expected_value_score": 0.111,
        "max_drawdown_pct": 0.02,
        "signals_generated": 10,
        "signals_survived": 8,
        "survival_rate": 0.8,
        "entry_execution_attribution": {
            "reason_counts": {"entered": 3, "gap_cancel": 2},
            "candidate_events": 5,
            "skipped_count": 2,
        },
    }

    compact = _compact_result(result)

    assert compact["total_trades"] == 3
    assert compact["entry_reason_counts"] == {"entered": 3, "gap_cancel": 2}
    assert compact["entry_candidate_events"] == 5
    assert compact["entry_skipped_count"] == 2
