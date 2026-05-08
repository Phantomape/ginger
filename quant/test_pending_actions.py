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


def test_register_pending_add_on_trade_waits_for_share_increase():
    from pending_actions import register_pending_actions_from_advice

    advice = {
        "add_on_trades": [
            {
                "ticker": "SNXX",
                "action": "ADD",
                "shares_to_buy": 10,
                "fill_timing": "next_session_open",
                "decision_mode": "code_followthrough_addon",
                "reason": "day-2 follow-through",
            }
        ],
        "position_actions": [
            {
                "ticker": "SNXX",
                "action": "HOLD",
                "exit_rule_triggered": "NONE",
                "shares_to_sell": None,
            }
        ],
    }
    open_positions = {"positions": [{"ticker": "SNXX", "shares": 20}]}

    records = register_pending_actions_from_advice(
        advice,
        open_positions,
        as_of_date="20260501",
        source_file="llm_prompt_resp_20260501.json",
    )

    assert len(records) == 1
    record = records[0]
    assert record["ticker"] == "SNXX"
    assert record["action"] == "ADD"
    assert record["shares_to_buy"] == 10
    assert record["original_shares"] == 20
    assert record["expected_remaining_shares"] == 30
    assert record["decision_mode"] == "code_followthrough_addon"


def test_pending_add_on_repeats_until_shares_reconcile(tmp_path):
    from pending_actions import apply_pending_action_overrides

    (tmp_path / "pending_actions.json").write_text(json.dumps({
        "pending_actions": [
            {
                "id": "20260501:SNXX:ADD:code_followthrough_addon",
                "status": "open",
                "first_advice_date": "20260501",
                "ticker": "SNXX",
                "action": "ADD",
                "shares_to_buy": 10,
                "original_shares": 20.0,
                "expected_remaining_shares": 30.0,
                "original_reason": "day-2 follow-through",
                "decision_mode": "code_followthrough_addon",
                "fill_timing": "next_session_open",
            }
        ]
    }), encoding="utf-8")

    advice = {
        "new_trade": "NO NEW TRADE",
        "add_on_trades": [],
        "position_actions": [
            {
                "ticker": "SNXX",
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
    open_positions = {"positions": [{"ticker": "SNXX", "shares": 20}]}

    patched, overrides = apply_pending_action_overrides(
        advice,
        open_positions,
        data_dir=str(tmp_path),
        as_of_date="20260504",
    )

    assert overrides and overrides[0]["ticker"] == "SNXX"
    assert patched["position_actions"][0]["action"] == "HOLD"
    assert patched["add_on_trades"] == [
        {
            "ticker": "SNXX",
            "action": "ADD",
            "shares_to_buy": 10,
            "fill_timing": "next_session_open",
            "decision_mode": "pending_unexecuted_action",
            "reason": (
                "Previous ADD from 20260501 was not reflected in open_positions; "
                "repeating until shares reconcile. Original reason: day-2 follow-through"
            ),
        }
    ]


def test_pending_add_on_closes_after_share_count_reconciles(tmp_path):
    from pending_actions import get_open_pending_actions

    (tmp_path / "pending_actions.json").write_text(json.dumps({
        "pending_actions": [
            {
                "id": "20260501:SNXX:ADD:code_followthrough_addon",
                "status": "open",
                "first_advice_date": "20260501",
                "ticker": "SNXX",
                "action": "ADD",
                "shares_to_buy": 10,
                "original_shares": 20.0,
                "expected_remaining_shares": 30.0,
            }
        ]
    }), encoding="utf-8")

    open_positions = {"positions": [{"ticker": "SNXX", "shares": 30}]}

    assert get_open_pending_actions(
        open_positions,
        data_dir=str(tmp_path),
        as_of_date="20260504",
    ) == []
