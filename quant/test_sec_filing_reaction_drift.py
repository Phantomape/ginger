from __future__ import annotations

import json
from pathlib import Path

from experiments.exp_20260503_051_sec_filing_reaction_drift import (
    evaluate_group,
    load_event_groups,
    reaction_bucket,
)


def test_reaction_bucket_fixed_thresholds() -> None:
    assert reaction_bucket(0.021) == "positive_excess_ge_2pct"
    assert reaction_bucket(0.0) == "positive_excess_0_to_2pct"
    assert reaction_bucket(-0.021) == "negative_excess_le_minus_2pct"
    assert reaction_bucket(-0.001) == "negative_excess_0_to_minus_2pct"


def test_load_event_groups_combines_same_ticker_trade_date(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    rows = [
        {
            "ticker": "ABC",
            "usable_trade_date": "2025-01-03",
            "accepted_at": "2025-01-02T20:10:00",
            "filing_date": "2025-01-02",
            "form_type": "8-K",
            "form_base": "8-K",
            "eight_k_item_codes": ["2.02", "9.01"],
            "accession_number": "one",
            "pit_safe_flag": True,
            "size": 100,
        },
        {
            "ticker": "ABC",
            "usable_trade_date": "2025-01-03",
            "accepted_at": "2025-01-02T20:12:00",
            "filing_date": "2025-01-02",
            "form_type": "8-K",
            "form_base": "8-K",
            "eight_k_item_codes": ["7.01"],
            "accession_number": "two",
            "pit_safe_flag": True,
            "size": 200,
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    groups = load_event_groups(path)

    assert len(groups) == 1
    assert groups[0]["filing_count"] == 2
    assert groups[0]["pit_safe_count"] == 2
    assert groups[0]["filing_category"] == "8k_2_02_results"
    assert groups[0]["eight_k_item_codes"] == ["2.02", "7.01", "9.01"]


def test_evaluate_group_enters_after_reaction_close() -> None:
    group = {
        "ticker": "ABC",
        "usable_trade_date": "2025-01-03",
        "form_bases": ["8-K"],
        "eight_k_item_codes": ["2.02"],
        "filing_category": "8k_2_02_results",
    }
    snapshot = {
        "ABC": [
            {"date": "2025-01-02", "open": 100.0, "close": 100.0, "volume": 1000.0},
            {"date": "2025-01-03", "open": 101.0, "close": 106.0, "volume": 1000.0},
            {"date": "2025-01-06", "open": 107.0, "close": 108.0, "volume": 1000.0},
            {"date": "2025-01-07", "open": 108.0, "close": 109.0, "volume": 1000.0},
            {"date": "2025-01-08", "open": 109.0, "close": 110.0, "volume": 1000.0},
            {"date": "2025-01-09", "open": 110.0, "close": 111.0, "volume": 1000.0},
            {"date": "2025-01-10", "open": 111.0, "close": 112.0, "volume": 1000.0},
            {"date": "2025-01-13", "open": 112.0, "close": 113.0, "volume": 1000.0},
        ],
        "SPY": [
            {"date": "2025-01-02", "open": 100.0, "close": 100.0, "volume": 1000.0},
            {"date": "2025-01-03", "open": 100.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-06", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-07", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-08", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-09", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-10", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-13", "open": 101.0, "close": 101.0, "volume": 1000.0},
        ],
    }

    row = evaluate_group(group, snapshot, snapshot["SPY"], "test")

    assert row["price_status"] == "covered"
    assert row["reaction_date"] == "2025-01-03"
    assert row["entry_date"] == "2025-01-06"
    assert row["reaction_bucket"] == "positive_excess_ge_2pct"
    assert row["horizons"]["5d"]["status"] == "valid"
