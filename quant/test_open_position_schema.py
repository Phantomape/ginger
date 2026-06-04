from pathlib import Path
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from open_position_schema import (  # noqa: E402
    account_position_tickers,
    account_positions,
    core_slot_positions,
    legacy_positions_payload,
    position_consumes_core_slot,
)


def test_account_positions_merges_operator_groups_with_sleeve_metadata():
    payload = {
        "observations": [
            {"ticker": "APP", "shares": 17, "avg_cost": 100},
        ],
        "core_positions": [
            {"ticker": "MRVL", "shares": 24, "avg_cost": 200},
        ],
        "positions": [
            {"ticker": "SNXX", "shares": 48, "avg_cost": 22, "opened_by_strategy": "fomo"},
            {"ticker": "AMZN", "shares": 4, "avg_cost": 248, "opened_by_strategy": "breakout_long"},
        ],
    }

    rows = account_positions(payload, positive_only=True)

    assert [row["ticker"] for row in rows] == ["SNXX", "AMZN", "MRVL", "APP"]
    assert rows[0]["sleeve"] == "fomo"
    assert rows[0]["slot_policy"] == "no_core_slot"
    assert rows[1]["sleeve"] == "core_strategy"
    assert rows[1]["slot_policy"] == "consumes_core_slot"
    assert rows[2]["position_group"] == "core_positions"
    assert rows[2]["slot_policy"] == "consumes_core_slot"
    assert rows[3]["sleeve"] == "observation"
    assert rows[3]["slot_policy"] == "no_core_slot"
    assert account_position_tickers(payload) == {"APP", "AMZN", "MRVL", "SNXX"}


def test_core_slot_positions_honor_explicit_non_core_override():
    payload = {
        "core_positions": [
            {"ticker": "MRVL", "shares": 24},
        ],
        "positions": [
            {
                "ticker": "AMZN",
                "shares": 4,
                "opened_by_strategy": "breakout_long",
                "slot_policy": "no_core_slot",
            },
        ],
    }

    assert [row["ticker"] for row in core_slot_positions(payload)] == ["MRVL"]
    assert not position_consumes_core_slot(payload["positions"][0])


def test_legacy_positions_payload_exposes_all_rows_under_positions():
    payload = {
        "core_positions": [{"ticker": "MRVL", "shares": 24}],
        "positions": [{"ticker": "SNXX", "shares": 48}],
        "observations": [{"ticker": "APP", "shares": 17}],
    }

    compat = legacy_positions_payload(payload)

    assert [row["ticker"] for row in compat["positions"]] == ["SNXX", "MRVL", "APP"]
    assert payload["positions"] == [{"ticker": "SNXX", "shares": 48}]
