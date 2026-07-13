import json


def _open_positions(
    ticker,
    shares,
    *,
    entry_date="2026-04-01",
    direction="long",
    position_id=1234567890123456789,
    account="moomoo_futusg",
):
    return {
        "account": account,
        "positions": [
            {
                "ticker": ticker,
                "shares": shares,
                "direction": direction,
                "entry_date": entry_date,
                "position_id": position_id,
            }
        ],
        "core_positions": [],
        "observations": [],
    }


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
    open_positions = _open_positions("MCD", 22)

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
    assert action["pending_action_id"] == "20260414:MCD:REDUCE:TRAILING_STOP"
    assert (
        action["position_lifecycle_id"]
        == "v1:moomoo_futusg:MCD:long:2026-04-01"
    )


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

    open_positions = _open_positions("MCD", 11)

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
    open_positions = _open_positions("MU", 1)

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
    open_positions = _open_positions("SNXX", 20)

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
    assert record["broker_position_id"] == "1234567890123456789"
    assert (
        record["position_lifecycle_id"]
        == "v1:moomoo_futusg:SNXX:long:2026-04-01"
    )


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
    open_positions = _open_positions("SNXX", 20)

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
            "pending_action_id": "20260501:SNXX:ADD:code_followthrough_addon",
            "position_lifecycle_id": (
                "v1:moomoo_futusg:SNXX:long:2026-04-01"
            ),
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

    open_positions = _open_positions("SNXX", 30)

    assert get_open_pending_actions(
        open_positions,
        data_dir=str(tmp_path),
        as_of_date="20260504",
    ) == []


def test_legacy_action_is_superseded_when_ticker_was_reopened(tmp_path):
    from pending_actions import apply_pending_action_overrides

    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
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
        "position_actions": [
            {
                "ticker": "MCD",
                "action": "HOLD",
                "exit_rule_triggered": "NONE",
                "shares_to_sell": None,
                "decision_mode": "forced_rule",
            }
        ]
    }
    reopened = _open_positions(
        "MCD",
        15,
        entry_date="2026-07-08",
        # Broker ids are explicitly allowed to be reused across lots.
        position_id=5025531777523043462,
    )

    patched, overrides = apply_pending_action_overrides(
        advice,
        reopened,
        data_dir=str(tmp_path),
        as_of_date="20260711",
    )

    assert overrides == []
    assert patched["position_actions"][0]["action"] == "HOLD"
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "superseded"
    assert saved["close_reason"] == "legacy_action_predates_current_lifecycle"
    assert saved["current_position_entry_date"] == "2026-07-08"
    assert "position_lifecycle_id" not in saved


def test_executed_action_cannot_resurrect_after_reentry(tmp_path):
    from pending_actions import get_open_pending_actions

    lifecycle_id = "v1:moomoo_futusg:MCD:long:2026-04-01"
    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
        "pending_actions": [
            {
                "id": f"20260414:MCD:EXIT:TRAILING_STOP:{lifecycle_id}",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "EXIT",
                "original_shares": 22.0,
                "expected_remaining_shares": 0.0,
                "position_lifecycle_id": lifecycle_id,
                "position_identity_status": "bound_at_creation",
            }
        ]
    }), encoding="utf-8")
    flat_snapshot = {
        "account": "moomoo_futusg",
        "positions": [],
        "core_positions": [],
        "observations": [],
    }

    assert get_open_pending_actions(
        flat_snapshot,
        data_dir=str(tmp_path),
        as_of_date="20260707",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "executed"
    assert saved["close_reason"] == "position_absent_from_valid_snapshot"

    reopened = _open_positions(
        "MCD",
        15,
        entry_date="2026-07-08",
        position_id=5025531777523043462,
    )
    assert get_open_pending_actions(
        reopened,
        data_dir=str(tmp_path),
        as_of_date="20260708",
    ) == []
    saved_again = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved_again["status"] == "executed"


def test_missing_entry_date_blocks_legacy_reconciliation(tmp_path):
    from pending_actions import apply_pending_action_overrides

    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
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
            }
        ]
    }), encoding="utf-8")
    incomplete = _open_positions("MCD", 22, entry_date=None)
    advice = {"position_actions": [{"ticker": "MCD", "action": "HOLD"}]}

    patched, overrides = apply_pending_action_overrides(
        advice,
        incomplete,
        data_dir=str(tmp_path),
        as_of_date="20260427",
    )

    assert overrides == []
    assert patched["position_actions"][0]["action"] == "HOLD"
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "open"
    assert saved["position_identity_status"] == "snapshot_unavailable"


def test_pending_override_is_not_reregistered_as_fresh_advice():
    from pending_actions import register_pending_actions_from_advice

    existing = {
        "id": (
            "20260414:MCD:REDUCE:TRAILING_STOP:"
            "v1:moomoo_futusg:MCD:long:2026-04-01"
        ),
        "status": "open",
        "first_advice_date": "20260414",
        "ticker": "MCD",
        "action": "REDUCE",
        "shares_to_sell": 11,
        "original_shares": 22.0,
        "expected_remaining_shares": 11.0,
        "position_lifecycle_id": "v1:moomoo_futusg:MCD:long:2026-04-01",
        "position_identity_status": "bound_at_creation",
    }
    repeated = {
        "position_actions": [
            {
                "ticker": "MCD",
                "action": "REDUCE",
                "shares_to_sell": 11,
                "decision_mode": "pending_unexecuted_action",
                "pending_action_id": existing["id"],
            }
        ]
    }

    records = register_pending_actions_from_advice(
        repeated,
        _open_positions("MCD", 22),
        existing_actions=[existing],
        as_of_date="20260427",
    )

    assert len(records) == 1
    assert records[0]["id"] == existing["id"]


def test_direction_change_supersedes_bound_action(tmp_path):
    from pending_actions import get_open_pending_actions

    lifecycle_id = "v1:moomoo_futusg:MCD:long:2026-04-01"
    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
        "pending_actions": [
            {
                "id": f"20260414:MCD:EXIT:TRAILING_STOP:{lifecycle_id}",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "EXIT",
                "original_shares": 22.0,
                "expected_remaining_shares": 0.0,
                "position_lifecycle_id": lifecycle_id,
                "position_identity_status": "bound_at_creation",
            }
        ]
    }), encoding="utf-8")

    assert get_open_pending_actions(
        _open_positions("MCD", 22, direction="short"),
        data_dir=str(tmp_path),
        as_of_date="20260427",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "superseded"
    assert saved["close_reason"] == "position_lifecycle_changed"


def test_archive_bootstrap_fails_closed_without_pit_position_snapshots():
    from pending_actions import bootstrap_pending_actions_from_archives

    assert bootstrap_pending_actions_from_archives(
        "data",
        _open_positions("MCD", 15, entry_date="2026-07-08"),
        "20260711",
    ) == []


def test_malformed_position_snapshot_does_not_close_action(tmp_path):
    from pending_actions import get_open_pending_actions

    lifecycle_id = "v1:moomoo_futusg:MCD:long:2026-04-01"
    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
        "pending_actions": [
            {
                "id": f"20260414:MCD:EXIT:TRAILING_STOP:{lifecycle_id}",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "EXIT",
                "original_shares": 22.0,
                "expected_remaining_shares": 0.0,
                "position_lifecycle_id": lifecycle_id,
                "position_identity_status": "bound_at_creation",
            }
        ]
    }), encoding="utf-8")

    assert get_open_pending_actions(
        {"account": "moomoo_futusg", "positions": None},
        data_dir=str(tmp_path),
        as_of_date="20260427",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "open"
    assert saved["position_identity_status"] == "snapshot_unavailable"
    assert "closed_date" not in saved


def test_malformed_position_row_does_not_close_action(tmp_path):
    from pending_actions import get_open_pending_actions

    lifecycle_id = "v1:moomoo_futusg:MCD:long:2026-04-01"
    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
        "pending_actions": [
            {
                "id": f"20260414:MCD:EXIT:TRAILING_STOP:{lifecycle_id}",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "EXIT",
                "original_shares": 22.0,
                "expected_remaining_shares": 0.0,
                "position_lifecycle_id": lifecycle_id,
                "position_identity_status": "bound_at_creation",
            }
        ]
    }), encoding="utf-8")

    assert get_open_pending_actions(
        {"account": "moomoo_futusg", "positions": [None]},
        data_dir=str(tmp_path),
        as_of_date="20260427",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "open"
    assert saved["position_identity_status"] == "snapshot_unavailable"
    assert "closed_date" not in saved


def test_malformed_sibling_blocks_reconciliation_of_valid_target(tmp_path):
    from pending_actions import get_open_pending_actions

    lifecycle_id = "v1:moomoo_futusg:MCD:long:2026-04-01"
    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
        "pending_actions": [
            {
                "id": f"20260414:MCD:REDUCE:TRAILING_STOP:{lifecycle_id}",
                "status": "open",
                "first_advice_date": "20260414",
                "ticker": "MCD",
                "action": "REDUCE",
                "shares_to_sell": 11,
                "original_shares": 22.0,
                "expected_remaining_shares": 11.0,
                "position_lifecycle_id": lifecycle_id,
                "position_identity_status": "bound_at_creation",
            }
        ]
    }), encoding="utf-8")
    partial_snapshot = _open_positions("MCD", 11)
    partial_snapshot["positions"].append(None)

    assert get_open_pending_actions(
        partial_snapshot,
        data_dir=str(tmp_path),
        as_of_date="20260427",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "open"
    assert saved["position_identity_status"] == "snapshot_unavailable"
    assert "closed_date" not in saved


def test_backdated_reconciliation_does_not_close_future_action(tmp_path):
    from pending_actions import get_open_pending_actions

    lifecycle_id = "v1:moomoo_futusg:MCD:long:2026-07-10"
    original = {
        "id": f"20260710:MCD:EXIT:TRAILING_STOP:{lifecycle_id}",
        "status": "open",
        "first_advice_date": "20260710",
        "ticker": "MCD",
        "action": "EXIT",
        "original_shares": 15.0,
        "expected_remaining_shares": 0.0,
        "position_lifecycle_id": lifecycle_id,
        "position_identity_status": "bound_at_creation",
    }
    path = tmp_path / "pending_actions.json"
    path.write_text(
        json.dumps({"pending_actions": [original]}),
        encoding="utf-8",
    )
    flat_snapshot = {
        "account": "moomoo_futusg",
        "positions": [],
        "core_positions": [],
        "observations": [],
    }

    assert get_open_pending_actions(
        flat_snapshot,
        data_dir=str(tmp_path),
        as_of_date="20260420",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved == original


def test_same_day_legacy_identity_is_quarantined(tmp_path):
    from pending_actions import get_open_pending_actions

    path = tmp_path / "pending_actions.json"
    path.write_text(json.dumps({
        "pending_actions": [
            {
                "id": "20260708:MCD:REDUCE:TRAILING_STOP",
                "status": "open",
                "first_advice_date": "20260708",
                "ticker": "MCD",
                "action": "REDUCE",
                "shares_to_sell": 5,
                "original_shares": 15.0,
                "expected_remaining_shares": 10.0,
            }
        ]
    }), encoding="utf-8")

    assert get_open_pending_actions(
        _open_positions("MCD", 15, entry_date="2026-07-08"),
        data_dir=str(tmp_path),
        as_of_date="20260708",
    ) == []
    saved = json.loads(path.read_text(encoding="utf-8"))["pending_actions"][0]
    assert saved["status"] == "open"
    assert (
        saved["position_identity_status"]
        == "quarantined_same_day_identity_ambiguous"
    )
