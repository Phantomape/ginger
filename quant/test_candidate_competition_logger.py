import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from candidate_competition_logger import (  # noqa: E402
    append_decision_outcome,
    append_decision_snapshot,
    compute_decision_outcome_attribution,
    summarize_pilot_competition,
)
from performance_engine import close_trade, open_trade  # noqa: E402


def _snapshot():
    return {
        "decision_id": "2026-05-01-AI_INFRA_PILOT-LITE-trend_long-1",
        "timestamp": "2026-05-01T16:00:00+00:00",
        "sleeve": "AI_INFRA_PILOT",
        "pilot_ticker": "LITE",
        "action": "pilot_entry_candidate",
        "protocol_version": "universe_protocol_v1.0",
        "ranking_snapshot": [
            {
                "rank": 1,
                "status": "pilot",
                "ticker": "LITE",
                "strategy": "trend_long",
                "shares_to_buy": 3,
                "risk_amount_usd": 300.0,
            },
            {
                "rank": 1,
                "status": "core",
                "ticker": "AMD",
                "strategy": "breakout_long",
                "shares_to_buy": 4,
                "risk_amount_usd": 400.0,
            },
        ],
        "counterfactuals": [
            {
                "type": "primary_displaced_candidate",
                "ticker": "AMD",
                "shadow_weight": 0.5,
                "planned_risk": 400.0,
            },
            {"type": "cash_baseline", "ticker": "CASH", "shadow_weight": 0.5},
        ],
        "risk_snapshot": {
            "pilot_sizing": {"risk_amount_usd": 300.0},
        },
    }


def test_decision_outcome_attribution_computes_replacement_value():
    attribution = compute_decision_outcome_attribution(
        _snapshot(),
        {
            "decision_id": "2026-05-01-AI_INFRA_PILOT-LITE-trend_long-1",
            "pilot_pnl": 1200.0,
            "pilot_risk": 300.0,
            "counterfactual_outcomes": [
                {
                    "type": "primary_displaced_candidate",
                    "ticker": "AMD",
                    "profit_loss": 800.0,
                    "planned_risk": 400.0,
                }
            ],
        },
    )

    assert attribution["replacement_pnl"] == 400.0
    assert attribution["replacement_value"] == 800.0
    assert attribution["risk_adjusted_replacement_value"] == 2.0
    assert attribution["replacement_value_status"] == "complete"


def test_pilot_competition_summary_marks_missing_counterfactuals_pending(tmp_path):
    path = tmp_path / "pilot_competition_decisions.jsonl"
    append_decision_snapshot(_snapshot(), path=path)
    append_decision_outcome(
        "2026-05-01-AI_INFRA_PILOT-LITE-trend_long-1",
        {"pilot_pnl": 1200.0, "pilot_risk": 300.0},
        path=path,
    )

    summary = summarize_pilot_competition(path=path, sleeve="AI_INFRA_PILOT")

    assert summary["outcome_records"] == 1
    assert summary["direct_pilot_pnl"] == 1200.0
    assert summary["replacement_value"] is None
    assert summary["pending_replacement_outcomes"] == 1


def test_closing_pilot_trade_appends_outcome(tmp_path):
    trades_path = tmp_path / "trades.json"
    decisions_path = tmp_path / "pilot_competition_decisions.jsonl"
    append_decision_snapshot(_snapshot(), path=decisions_path)
    trade_id = open_trade(
        "LITE",
        "trend_long",
        100.0,
        95.0,
        10,
        filepath=trades_path,
        metadata={
            "pilot_decision_log_path": str(decisions_path),
            "pilot_sleeve": {
                "name": "AI_INFRA_PILOT",
                "decision_id": "2026-05-01-AI_INFRA_PILOT-LITE-trend_long-1",
            },
            "counterfactual_outcomes": [
                {
                    "type": "primary_displaced_candidate",
                    "ticker": "AMD",
                    "profit_loss": 40.0,
                    "planned_risk": 50.0,
                }
            ],
        },
    )

    close_trade(trade_id, 110.0, filepath=trades_path)
    summary = summarize_pilot_competition(
        path=decisions_path,
        sleeve="AI_INFRA_PILOT",
    )

    assert summary["outcome_records"] == 1
    assert summary["complete_replacement_outcomes"] == 1
    assert summary["by_ticker"]["LITE"]["outcomes"] == 1
