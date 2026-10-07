"""Synthetic prospective order identity and complete-cycle attribution regressions."""

from copy import deepcopy

import pytest

import broker_execution_ledger as L
import broker_performance as P
import execution_attribution as A
from test_broker_performance import _capture


def _plan(side="BUY", strategy="core:fixture"):
    return {"strategy_id": strategy, "code": "US.AAPL", "side": side, "quantity": 10,
            "action_kind": "entry" if side == "BUY" else "bracket",
            "source_payload": {"strategy": "fixture", "entry": 100, "stop": 90}}


def _record(path, plans=None, **kwargs):
    return A.record_decisions(plans or [_plan(), _plan("SELL")], as_of="2026-06-30",
        account_key="synthetic-account", source_ref="synthetic-machine-advice",
        policy_hashes={"fixture.py": "a" * 64}, directory=path,
        recorded_at=kwargs.pop("recorded_at", "2026-06-30T20:00:00Z"), **kwargs)


def _tagged_capture(snapshots):
    capture = _capture()
    for order, snapshot in zip(capture["orders"], snapshots):
        order.update(qty=10, trd_side=snapshot["decision"]["side"], remark=snapshot["broker_remark"])
    return capture


def _measure(tmp_path, capture, decisions):
    broker = tmp_path / "broker"
    L.persist_broker_execution_capture(capture, ledger_dir=broker)
    return P.compute_broker_performance(broker, attribution_dir=decisions)


def test_complete_explicit_cycle_counts_partial_fills_and_fees_once(tmp_path):
    decisions = tmp_path / "decisions"
    snapshots = _record(decisions)["decisions"]
    summary = _measure(tmp_path, _tagged_capture(snapshots), decisions)
    attribution = summary["strategy_attribution"]
    assert attribution["attributed_lifecycle_count"] == 1
    assert attribution["unattributed_lifecycle_count"] == 0
    assert attribution["net_trading_pnl_after_order_fees"] == 95
    assert attribution["by_strategy"]["core:fixture"]["order_fee_total"] == 5
    assert summary["pnl_by_currency"]["USD"]["net_trading_pnl_after_order_fees"] == 95
    assert attribution["binding_coverage"]["bound_order_count"] == 2
    assert attribution["binding_coverage"]["broker_event_timezone_verified"] is False


def test_repeated_payload_keeps_first_clock_token_and_bytes(tmp_path):
    first = _record(tmp_path)
    before = (tmp_path / "decisions.jsonl").read_bytes()
    second = _record(tmp_path, recorded_at="2026-07-01T12:00:00Z")
    assert second["rows_appended"] == 0
    assert first["decisions"] == second["decisions"]
    assert before == (tmp_path / "decisions.jsonl").read_bytes()
    changed = _plan(); changed["quantity"] = 11
    third = _record(tmp_path, [changed])
    assert third["rows_appended"] == 1
    assert third["decisions"][0]["decision_id"] != first["decisions"][0]["decision_id"]
    assert (tmp_path / "decisions.jsonl").read_bytes().startswith(before)


@pytest.mark.parametrize("mutation", ["empty", "unknown", "quantity", "side", "code", "account", "clock", "duplicate"])
def test_no_inferred_or_conflicting_order_ownership(tmp_path, mutation):
    decisions = tmp_path / "decisions"
    snapshots = _record(decisions, recorded_at=("2026-07-04T00:00:00Z" if mutation == "clock" else "2026-06-30T20:00:00Z"))["decisions"]
    capture = _tagged_capture(snapshots)
    order = capture["orders"][0]
    if mutation == "empty": order["remark"] = ""
    if mutation == "unknown": order["remark"] = "GNG-" + "0" * 28
    if mutation == "quantity": order["qty"] = 11
    if mutation == "side": order["trd_side"] = "SELL"
    if mutation == "code": order["code"] = "US.MSFT"
    if mutation == "account": capture["account_key"] = "other-account"
    if mutation == "duplicate": capture["orders"].append(dict(order, order_id="other-order", dealt_qty=0))
    summary = _measure(tmp_path, capture, decisions)
    assert summary["strategy_attribution"]["attributed_lifecycle_count"] == 0
    assert summary["strategy_attribution"]["net_trading_pnl_after_order_fees"] is None


def test_manual_exit_and_two_strategies_do_not_inherit_entry_profit(tmp_path):
    decisions = tmp_path / "decisions"
    snapshots = _record(decisions, [_plan(), _plan("SELL", "pilot:other")])["decisions"]
    summary = _measure(tmp_path, _tagged_capture(snapshots), decisions)
    assert summary["strategy_attribution"]["coverage_reasons"] == {"mixed_strategy_lifecycle": 1}
    assert summary["strategy_attribution"]["by_strategy"] == {}


def test_later_remark_edit_cannot_claim_an_existing_order(tmp_path):
    decisions, broker = tmp_path / "decisions", tmp_path / "broker"
    original = _capture()
    L.persist_broker_execution_capture(original, ledger_dir=broker)
    snapshots = _record(decisions)["decisions"]
    revised = _tagged_capture(snapshots)
    revised.update(collection_id="c2", collection_completed_at_utc="2026-07-04T20:00:00Z")
    L.persist_broker_execution_capture(revised, ledger_dir=broker)
    summary = P.compute_broker_performance(broker, attribution_dir=decisions)
    assert summary["strategy_attribution"]["attributed_lifecycle_count"] == 0
    assert summary["strategy_attribution"]["binding_coverage"]["blockers"]["remark_not_present_on_all_order_versions"] == 2


def test_corrupt_decision_chain_never_changes_account_measurement(tmp_path):
    decisions = tmp_path / "decisions"
    snapshots = _record(decisions)["decisions"]
    path = decisions / "decisions.jsonl"
    path.write_text(path.read_text().replace("core:fixture", "core:tampered"), encoding="utf-8")
    with pytest.raises(L.BrokerLedgerCorruptionError): _record(decisions)
    summary = _measure(tmp_path, _tagged_capture(snapshots), decisions)
    assert summary["pnl_by_currency"]["USD"]["net_trading_pnl_after_order_fees"] == 95
    assert summary["strategy_attribution"]["net_trading_pnl_after_order_fees"] is None
    assert summary["strategy_attribution"]["binding_coverage"]["status"] == "decision_ledger_corrupt_or_unreadable"


def test_read_only_resolution_and_missing_decisions_do_not_create_files(tmp_path):
    broker = tmp_path / "broker"
    L.persist_broker_execution_capture(_capture(), ledger_dir=broker)
    before = {p.name: p.read_bytes() for p in broker.glob("*.jsonl")}
    summary = P.compute_broker_performance(broker, attribution_dir=tmp_path / "absent")
    assert not (tmp_path / "absent").exists()
    assert summary["strategy_attribution"]["unattributed_lifecycle_count"] == 1
    assert before == {p.name: p.read_bytes() for p in broker.glob("*.jsonl")}


def test_daily_builder_records_advice_without_mutating_inputs_or_adopting_old_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "utc_now_iso", lambda: "2026-07-04T10:00:00Z")
    broker = tmp_path / "broker"
    capture = _capture()
    L.persist_broker_execution_capture(capture, ledger_dir=broker)
    signals = [{"ticker": "AAPL", "strategy": "fixture", "sizing": {"shares_to_buy": 10}, "trade_enabled": False}]
    bracket = {"orders": [{"ticker": "AAPL", "side": "SELL", "quantity": 10, "price": 110}]}
    before = deepcopy((signals, bracket))
    result = A.build_daily_attribution_decisions(as_of="2026-07-04", signals=signals,
        pilot_signals=[], addon_actions=[], bracket_orders=bracket,
        broker_dir=broker, directory=tmp_path / "decisions", refresh_status="refreshed",
        capture_not_before="2026-07-03T19:59:00Z")
    assert len(result["decisions"]) == 1
    assert result["unassigned_advice_count"] == 1
    assert result["decisions"][0]["decision"]["stage"] == "machine_advice_not_order_authorization"
    assert (signals, bracket) == before
    assert result["trade_enabled"] is False


def test_open_explicit_entry_can_provide_identity_for_later_exit_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "utc_now_iso", lambda: "2026-07-04T10:00:00Z")
    decisions, broker = tmp_path / "decisions", tmp_path / "broker"
    snapshots = _record(decisions, [_plan()])["decisions"]
    capture = _tagged_capture(snapshots)
    capture["deals"] = capture["deals"][:2]
    capture["orders"] = capture["orders"][:1]
    capture["order_fees"] = capture["order_fees"][:1]
    capture["positions"] = [{"code": "US.AAPL", "qty": 10}]
    L.persist_broker_execution_capture(capture, ledger_dir=broker)
    result = A.build_daily_attribution_decisions(as_of="2026-07-04", signals=[],
        pilot_signals=[], addon_actions=[], bracket_orders={"orders": [{"ticker": "AAPL", "quantity": 10}]},
        broker_dir=broker, directory=decisions, refresh_status="refreshed",
        capture_not_before="2026-07-03T19:59:00Z")
    assert len(result["decisions"]) == 1
    decision = result["decisions"][0]["decision"]
    assert decision["side"] == "SELL"
    assert decision["strategy_id"] == "core:fixture"
    assert decision["parent_decision_ids"] == [snapshots[0]["decision_id"]]


@pytest.mark.parametrize("field,value", [("as_of", "not-a-date"), ("source_ref", True),
    ("policy_hashes", {"x": "bad"}), ("action_kind", None), ("source_payload", None)])
def test_incomplete_snapshot_contract_rejected_before_append(tmp_path, field, value):
    plan = _plan()
    args = dict(as_of="2026-07-01", account_key="synthetic-account", source_ref="fixture",
                policy_hashes={"fixture.py": "a" * 64}, directory=tmp_path)
    if field in args: args[field] = value
    else: plan[field] = value
    with pytest.raises(ValueError): A.record_decisions([plan], **args)
    assert not (tmp_path / "decisions.jsonl").exists()


def test_valid_decision_tail_truncation_cannot_hide_a_losing_cycle(tmp_path):
    directory, broker = tmp_path / "decisions", tmp_path / "broker"
    plans = [_plan(), _plan("SELL")]
    plans += [dict(p, code="US.MSFT") for p in plans]
    snapshots = _record(directory, plans)["decisions"]
    capture = _tagged_capture(snapshots[:2])
    other = _tagged_capture(snapshots[2:])
    for key in ["deals", "orders", "order_fees"]:
        for row in other[key]:
            row["order_id"] += "-msft"
            if "deal_id" in row: row["deal_id"] += "-msft"
            if "code" in row: row["code"] = "US.MSFT"
        capture[key] += other[key]
    capture["deals"][-1]["price"] = 90
    L.persist_broker_execution_capture(capture, ledger_dir=broker)
    assert P.compute_broker_performance(broker, attribution_dir=directory)["strategy_attribution"]["net_trading_pnl_after_order_fees"] == -10
    path = directory / "decisions.jsonl"
    path.write_bytes(b"\n".join(path.read_bytes().splitlines()[:2]) + b"\n")
    after = P.compute_broker_performance(broker, attribution_dir=directory)
    assert after["strategy_attribution"]["net_trading_pnl_after_order_fees"] is None
    assert after["pnl_by_currency"]["USD"]["net_trading_pnl_after_order_fees"] == -10


@pytest.mark.parametrize("mode", ["stale", "refresh_failed", "old_success", "fill_tail", "oversized_exit"])
def test_daily_bad_capture_or_position_cannot_issue_tracking_identity(tmp_path, monkeypatch, mode):
    broker, directory = tmp_path / "broker", tmp_path / "decisions"
    snapshots = _record(directory, [_plan()])["decisions"]
    capture = _tagged_capture(snapshots)
    capture["deals"] = capture["deals"][:2]
    capture["orders"] = capture["orders"][:1]
    capture["order_fees"] = capture["order_fees"][:1]
    capture["positions"] = [{"code": "US.AAPL", "qty": 10}]
    L.persist_broker_execution_capture(capture, ledger_dir=broker)
    monkeypatch.setattr(L, "utc_now_iso", lambda: "2026-09-09T10:00:00Z" if mode == "stale" else "2026-07-04T10:00:00Z")
    if mode == "fill_tail":
        path = broker / "fills.jsonl"
        path.write_bytes(b"\n".join(path.read_bytes().splitlines()[:-1]) + b"\n")
    kwargs = dict(as_of="2026-07-04", signals=[], pilot_signals=[], addon_actions=[],
        bracket_orders={"orders": [{"ticker": "AAPL", "quantity": 1000 if mode == "oversized_exit" else 10}]},
        broker_dir=broker, directory=directory,
        refresh_status="fallback" if mode == "refresh_failed" else "refreshed",
        capture_not_before="2026-07-04T09:59:00Z" if mode == "old_success" else "2026-07-03T19:59:00Z")
    before = (directory / "decisions.jsonl").read_bytes()
    if mode == "oversized_exit":
        result = A.build_daily_attribution_decisions(**kwargs)
        assert result["decisions"] == []
        assert result["unassigned_advice_count"] == 1
    else:
        with pytest.raises((ValueError, L.BrokerLedgerCorruptionError)):
            A.build_daily_attribution_decisions(**kwargs)
    assert (directory / "decisions.jsonl").read_bytes() == before
