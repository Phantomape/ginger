import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from position_intent_reconstruction import reconstruct_entry_intents  # noqa: E402


def _write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_reconstructs_new_trade_intended_shares(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(
        data_dir / "llm_prompt_resp_20260414.json",
        {
            "advice_parsed": {
                "new_trade": {
                    "ticker": "AMZN",
                    "shares_to_buy": 38,
                    "entry_price": 249.02,
                }
            }
        },
    )
    open_positions = {
        "positions": [
            {
                "ticker": "AMZN",
                "shares": 4,
                "entry_date": "2026-04-15",
                "opened_by_strategy": "breakout_long",
            }
        ]
    }

    report = reconstruct_entry_intents(open_positions, data_dir)

    row = report["positions"][0]
    assert row["ticker"] == "AMZN"
    assert row["recommended_intended_shares"] == 38
    assert row["confidence"] == "high"
    assert row["write_recommendation"] == "candidate_ready_for_user_confirmation"
    assert row["current_vs_recommended_shortfall"] == 34


def test_reconstructs_original_shares_from_quant_addon(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(
        data_dir / "quant_signals_20260501.json",
        {
            "addon_actions": [
                {
                    "ticker": "SNXX",
                    "shares_to_buy": 10,
                    "current_shares": 20,
                    "original_shares": 20,
                    "days_since_entry": 2,
                }
            ]
        },
    )
    open_positions = {
        "positions": [
            {
                "ticker": "SNXX",
                "shares": 12,
                "entry_date": "2026-04-29",
                "opened_by_strategy": "fomo",
            }
        ]
    }

    report = reconstruct_entry_intents(open_positions, data_dir)

    row = report["positions"][0]
    assert row["recommended_intended_shares"] == 20
    assert row["confidence"] == "high"
    assert row["top_evidence"]["evidence_type"] == "quant_addon_actions"
    assert report["summary"]["high_confidence_candidates"] == 1
    assert report["summary"]["candidate_ready_for_user_confirmation_count"] == 1


def test_reduce_action_blocks_ready_confirmation_but_keeps_high_confidence(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_json(
        data_dir / "quant_signals_20260501.json",
        {
            "addon_actions": [
                {
                    "ticker": "SNXX",
                    "shares_to_buy": 10,
                    "original_shares": 20,
                    "days_since_entry": 2,
                }
            ]
        },
    )
    _write_json(
        data_dir / "llm_prompt_resp_20260502.json",
        {
            "advice_parsed": {
                "position_actions": [
                    {
                        "ticker": "SNXX",
                        "action": "REDUCE",
                        "shares_to_sell": 8,
                        "exit_rule_triggered": "PROFIT_TARGET",
                    }
                ]
            }
        },
    )
    open_positions = {
        "positions": [
            {
                "ticker": "SNXX",
                "shares": 12,
                "entry_date": "2026-04-29",
                "opened_by_strategy": "fomo",
            }
        ]
    }

    report = reconstruct_entry_intents(open_positions, data_dir)

    row = report["positions"][0]
    assert row["recommended_intended_shares"] == 20
    assert row["write_recommendation"] == "needs_user_confirmation_conflict_or_low_confidence"
    assert report["summary"]["high_confidence_candidates"] == 1
    assert report["summary"]["candidate_ready_for_user_confirmation_count"] == 0


def test_reconstruction_marks_missing_when_no_archive_candidate(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    open_positions = {
        "positions": [
            {
                "ticker": "MSFT",
                "shares": 3,
                "entry_date": "2026-04-29",
                "opened_by_strategy": "fomo",
            }
        ]
    }

    report = reconstruct_entry_intents(open_positions, data_dir)

    row = report["positions"][0]
    assert row["recommended_intended_shares"] is None
    assert row["write_recommendation"] == "needs_user_confirmation_no_candidate"
    assert report["summary"]["missing_candidate_count"] == 1
