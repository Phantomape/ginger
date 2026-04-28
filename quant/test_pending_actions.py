import json


def test_pending_action_repeats_hold_until_shares_reconcile(tmp_path):
    from pending_actions import apply_pending_action_overrides

    (tmp_path / "pending_actions.json").write_text(json.dumps({
        "pending_actions": [
            {
                "id": "20260414:MCD:REDUCE:TRAILING_STOP",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "REDUCE",
                "shares_to_sell": 11,
                "original_shares": 22.0,
                "expected_remaining_shares": 11.0,
                "exit_rule_triggered": "TRAILING_STOP",
            }
        ]
    }), encoding="utf-8")

    advice = {
        "new_trade": "NO NEW TRADE",
        "position_actions": [
            {
                "ticker": "MCD",
                "current_position": "long",
                "action": "HOLD",
                "reason": "fresh rules say HOLD",
                "exit_rule_triggered": "NONE",
                "shares_to_sell": None,
                "decision_mode": "forced_rule",
                "suggested_new_stop": None,
            }
        ],
    }
    open_positions = {"positions": [{"ticker": "MCD", "shares": 22}]}

    patched, overrides = apply_pending_action_overrides(
        advice,
        open_positions,
        data_dir=str(tmp_path),
        as_of_date="20260427",
    )

    action = patched["position_actions"][0]
    assert overrides and overrides[0]["ticker"] == "MCD"
    assert action["action"] == "REDUCE"
    assert action["shares_to_sell"] == 11
    assert action["decision_mode"] == "pending_unexecuted_action"
    assert action["exit_rule_triggered"] == "TRAILING_STOP"


def test_pending_action_closes_after_share_count_reconciles(tmp_path):
    from pending_actions import get_open_pending_actions

    (tmp_path / "pending_actions.json").write_text(json.dumps({
        "pending_actions": [
            {
                "id": "20260414:MCD:REDUCE:TRAILING_STOP",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "REDUCE",
                "shares_to_sell": 11,
                "original_shares": 22.0,
                "expected_remaining_shares": 11.0,
                "exit_rule_triggered": "TRAILING_STOP",
            }
        ]
    }), encoding="utf-8")

    open_positions = {"positions": [{"ticker": "MCD", "shares": 11}]}

    assert get_open_pending_actions(
        open_positions,
        data_dir=str(tmp_path),
        as_of_date="20260427",
    ) == []


def test_register_pending_action_ignores_zero_share_reduce():
    from pending_actions import register_pending_actions_from_advice

    advice = {
        "position_actions": [
            {
                "ticker": "MU",
                "action": "REDUCE",
                "shares_to_sell": 0,
                "exit_rule_triggered": "PROFIT_LADDER_50",
            }
        ]
    }
    open_positions = {"positions": [{"ticker": "MU", "shares": 1}]}

    assert register_pending_actions_from_advice(
        advice,
        open_positions,
        as_of_date="20260424",
    ) == []
